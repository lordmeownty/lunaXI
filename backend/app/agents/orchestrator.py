"""Orchestration of the Luna XI Starting XI as a workflow graph.

The request flow is a small directed graph of steps ("executors"). Every step reads/writes the same
SharedState blackboard and returns the id of the next step (or None when finished).

Engines (ORCHESTRATOR env var):
  * agent_framework : runs the graph with Microsoft Agent Framework (WorkflowBuilder + Executors) when the
                      `agent-framework` package is installed. If it is missing or fails, Luna falls back automatically.
  * builtin         : the same graph, run by a tiny in-process loop (always available).
Both engines execute exactly the same step functions, so behaviour is identical and easy to debug.
"""
from __future__ import annotations

import logging
import re
import time
from typing import Awaitable, Callable

from ..analytics import metrics
from ..config import settings
from ..data.store import Match
from ..foundry import decision
from ..security.guard import screen_text
from ..telemetry import efficiency, recent_traces
from .state import SharedState
from .team import (DataAnalyst, DecisionRouter, EvidenceReferee, MatchObserver, MomentScout, ReplayBuilder,
                   ReplayDirector, StoryDirector, StudioProducer, TacticalAnalyst, VoiceDirector)

log = logging.getLogger("luna.orchestrator")
observer, analyst, scout, router = MatchObserver(), DataAnalyst(), MomentScout(), DecisionRouter()
tactician, builder, director = TacticalAnalyst(), ReplayBuilder(), ReplayDirector()
referee, story, voice, producer = EvidenceReferee(), StoryDirector(), VoiceDirector(), StudioProducer()

AGENT_ROSTER = [
    {"no": 1, "name": observer.name, "role": "Match state at the playback clock; applies the user's focused moment", "kind": "deterministic"},
    {"no": 2, "name": analyst.name, "role": "Verified stats; answers Tier-0 lookups instantly", "kind": "deterministic"},
    {"no": 3, "name": scout.name, "role": "Finds momentum shifts and turning points", "kind": "deterministic"},
    {"no": 4, "name": router.name, "role": "AI Efficiency Gateway via Jev / Microsoft-Decision-1", "kind": "decision model"},
    {"no": 5, "name": tactician.name, "role": "Explains why with before/after evidence", "kind": "reasoning model (Sol)"},
    {"no": 6, "name": builder.name, "role": "Loads and validates replay keyframes (spoiler-safe)", "kind": "deterministic"},
    {"no": 7, "name": director.name, "role": "Camera path and overlays for Luna Lens", "kind": "deterministic"},
    {"no": 8, "name": referee.name, "role": "Rejects unsupported numbers; publication gate", "kind": "rules + decision model"},
    {"no": 9, "name": story.name, "role": "Audience-specific narratives", "kind": "fast model (GPT-6 Luna)"},
    {"no": 10, "name": voice.name, "role": "Realtime voice and transcription", "kind": "GPT Realtime + GPT Transcribe"},
    {"no": 11, "name": producer.name, "role": "Recap packages, posters, commentary checks", "kind": "fast + image models"},
]


# ---------------------------------------------------------------------------------------------- helpers
async def _verified_story(s: SharedState, facts: dict, task: str) -> str:
    """Story Director → Evidence Referee → one retry with feedback → verified deterministic fallback."""
    s.facts.setdefault("story_inputs", []).append(facts)
    s.draft = await story.narrate(s, facts, task)
    if await referee.run(s):
        return s.draft
    s.retries += 1
    s.question = (s.question or task) + " (Use fewer numbers; only those in FACTS.)"
    s.draft = await story.narrate(s, facts, task + "_retry")
    if await referee.run(s):
        return s.draft
    with s.trace.step("Orchestrator", "fallback_to_verified_template", source="deterministic") as st:
        st.status = "fallback"
        s.draft = story.template(s, facts, task)
    await referee.run(s)
    return s.draft


# ---------------------------------------------------------------------------------------------- workflow steps
Step = Callable[[SharedState], Awaitable[str | None]]


async def step_safety(s: SharedState) -> str | None:
    with s.trace.step("Safety Guard", "screen_input") as st:
        screen = await screen_text(s.question)
        st.source, st.detail = screen["source"], screen
        if screen["blocked"]:
            st.status = "rejected"
    if screen["blocked"]:
        s.blocked, s.tier = True, "BLOCKED"
        s.answer = "I can only help with this match. Try asking about a goal, a player or a turning point."
        s.verification = {"verdict": "blocked", "reasons": screen["reasons"]}
        return None
    return "observe"


async def step_observe(s: SharedState) -> str | None:
    await observer.run(s)
    return "route"


async def step_route(s: SharedState) -> str | None:
    await router.run(s)
    if s.intent == "replay":
        return "replay"
    return {"T0": "lookup", "T1": "judge", "T2": "summarise", "T3": "explain", "T4": "package"}[s.tier]


async def step_lookup(s: SharedState) -> str | None:
    ans = await analyst.lookup(s)
    if ans:
        s.answer, s.verification = ans, {"verdict": "approved", "method": "direct event lookup"}
        return None
    s.tier = "T2"
    return "summarise"


async def step_judge(s: SharedState) -> str | None:
    shot = metrics.last_event_of(s.match, "shot", s.playback_t)
    if shot:
        f = metrics.shot_danger_features(shot)
        h = {"low": 0.1, "medium": 0.1, "high": 0.1}
        h[f["heuristic_band"]] = 0.8
        with s.trace.step("Decision Router", "judge_shot_danger") as st:
            d = await decision.choose("How dangerous was this shot?", ["low", "medium", "high"], f, heuristic=h)
            st.source, st.detail = f"decision:{d.source}", {"selected": d.selected, "probabilities": d.probabilities}
        if d.confidence >= 0.55:
            who = s.match.player_name(shot["player"])
            s.answer = {"low": f"Low danger. {who}'s {shot['clock']} effort had an xG of {f['xg']}, a hard chance.",
                        "medium": f"Moderate danger. {who}'s {shot['clock']} shot was worth {f['xg']} xG, a decent chance.",
                        "high": f"Big chance. {who}'s {shot['clock']} shot was worth {f['xg']} xG."}[d.selected]
            s.add_evidence("Shot xG", f["xg"], [shot["id"]], "event")
            s.verification = {"verdict": "approved", "method": "decision model + template"}
            return None
    s.tier = "T3" if s.deep_analysis else "T2"
    return "explain" if s.deep_analysis else "summarise"


async def step_summarise(s: SharedState) -> str | None:
    s.tier = "T2"
    await analyst.run(s)
    m = s.match
    end = s.playback_t if s.playback_t is not None else m.events[-1]["t"]
    mm = re.search(r"last (\d+) minutes", s.question.lower())
    span = int(mm.group(1)) * 60 if mm else (15 * 60 if s.intent == "catch_up" else end)
    digest = metrics.window_digest(m, max(0, end - span), end)
    s.facts["digest"] = digest
    for n in digest["notable_events"][-4:]:
        s.add_evidence(f"{n['clock']} {n['type']}", n.get("player") or n.get("note"), [n["id"]], "event")
    s.answer = await _verified_story(s, {"digest": digest, "state": s.facts["state"]}, "catch_up_summary")
    return None


async def step_explain(s: SharedState) -> str | None:
    s.tier = "T3"
    await analyst.run(s)
    await scout.run(s)
    await tactician.run(s)
    if not await referee.run(s):
        s.retries += 1
        fb = f"unsupported numbers {s.verification.get('unsupported_numbers')}"
        s.evidence = []
        await tactician.run(s, red_team_feedback=fb)
        if not await referee.run(s):
            with s.trace.step("Orchestrator", "fallback_to_verified_template", source="deterministic") as st:
                st.status = "fallback"
            s.draft = tactician.template(s)
            await referee.run(s)
    s.answer = s.draft
    fm = s.facts.get("focus_moment")
    if fm and fm.get("replay_id"):
        s.action = {"type": "suggest_replay", "replay_id": fm["replay_id"]}
    return None


async def step_replay(s: SharedState) -> str | None:
    s.tier = "R"
    await builder.run(s, s.extra.get("goal_number"))
    if not s.replay:
        s.answer = "That goal hasn't happened yet at this point of the match." if s.playback_t else "I couldn't find that goal."
        return None
    await director.run(s, s.extra.get("view"))
    m = s.match
    s.answer = await _verified_story(s, {"replay": s.replay["summary_facts"], "clock": s.replay["clock"],
                                         "scorer": m.player_name(s.replay["scorer"]), "team": m.team_name(s.replay["team"])}, "describe_replay")
    s.add_evidence("Build-up passes", s.replay["summary_facts"]["passes"], s.replay["event_ids"], "event")
    return None


async def step_package(s: SharedState) -> str | None:
    s.tier = "T4"
    pkg = await build_recap(s.match, s.audience, "full" if s.playback_t is None else "live", s.playback_t, s)
    s.extra["package"] = pkg
    s.answer = pkg["recap"]
    return None


STEPS: dict[str, Step] = {"safety": step_safety, "observe": step_observe, "route": step_route, "lookup": step_lookup,
                          "judge": step_judge, "summarise": step_summarise, "explain": step_explain, "replay": step_replay,
                          "package": step_package}
EDGES = [("safety", "observe"), ("observe", "route"), ("route", "lookup"), ("route", "judge"), ("route", "summarise"),
         ("route", "explain"), ("route", "replay"), ("route", "package"), ("lookup", "summarise"), ("judge", "explain"),
         ("judge", "summarise")]
STEP_INFO = {
    "safety": ("Safety Guard", "Prompt Shields / injection rules"), "observe": ("Match Observer", "Clock, score, user focus"),
    "route": ("Decision Router", "Jev / Decision-1 picks tier"), "lookup": ("Data Analyst", "T0 direct answer"),
    "judge": ("Decision Router", "T1 bounded judgement"), "summarise": ("Story Director + Referee", "T2 verified summary"),
    "explain": ("Scout + Tactical Analyst + Referee", "T3 reasoning with retry"),
    "replay": ("Replay Builder + Director", "R Luna Lens action"), "package": ("Studio Producer", "T4 recap package"),
}


def workflow_graph() -> dict:
    return {"engine": active_engine(), "start": "safety",
            "nodes": [{"id": k, "agents": v[0], "does": v[1]} for k, v in STEP_INFO.items()],
            "edges": [{"from": a, "to": b} for a, b in EDGES]}


# ---------------------------------------------------------------------------------------------- engines
async def _run_builtin(s: SharedState) -> None:
    node: str | None = "safety"
    hops = 0
    while node and hops < 12:
        node = await STEPS[node](s)
        hops += 1


_MAF_WORKFLOW = None
_MAF_ERROR: str | None = None


def _build_maf_workflow():
    """Build the same graph with Microsoft Agent Framework (pip install agent-framework)."""
    from agent_framework import Executor, WorkflowBuilder, WorkflowContext, handler

    def make_executor(step_id: str, fn: Step):
        class StepExecutor(Executor):
            @handler
            async def handle(self, state: SharedState, ctx: WorkflowContext[SharedState]) -> None:
                nxt = await fn(state)
                if nxt:
                    await ctx.send_message(state, target_id=nxt)
                else:
                    await ctx.yield_output(state)
        StepExecutor.__name__ = f"{step_id.title()}Executor"
        return StepExecutor(id=step_id)

    execs = {k: make_executor(k, fn) for k, fn in STEPS.items()}
    wb = WorkflowBuilder().set_start_executor(execs["safety"])
    for a, b in EDGES:
        wb = wb.add_edge(execs[a], execs[b])
    return wb.build()


def active_engine() -> str:
    global _MAF_WORKFLOW, _MAF_ERROR
    if settings.orchestrator != "agent_framework":
        return "builtin"
    if _MAF_WORKFLOW is None and _MAF_ERROR is None:
        try:
            _MAF_WORKFLOW = _build_maf_workflow()
        except Exception as e:  # noqa: BLE001  (package not installed or API mismatch)
            _MAF_ERROR = str(e)[:200]
            log.info("Microsoft Agent Framework unavailable, using builtin engine: %s", _MAF_ERROR)
    return "microsoft-agent-framework" if _MAF_WORKFLOW is not None else "builtin"


async def run_workflow(s: SharedState) -> None:
    engine = active_engine()
    s.trace.engine = engine
    if engine == "microsoft-agent-framework":
        try:
            await _MAF_WORKFLOW.run(s)
            return
        except Exception as e:  # noqa: BLE001
            log.warning("Agent Framework run failed, retrying on builtin engine: %s", e)
            with s.trace.step("Orchestrator", "engine_fallback", source="builtin") as st:
                st.status, st.detail = "fallback", {"error": str(e)[:200]}
            s.trace.engine = "builtin (fallback)"
    await _run_builtin(s)


# ---------------------------------------------------------------------------------------------- public API
def _finish(s: SharedState, t0: float, extra: dict | None = None) -> dict:
    total_ms = int((time.perf_counter() - t0) * 1000)
    tier = s.tier or "T2"
    trace = s.trace.to_dict()
    efficiency.record(tier, s.trace, total_ms)
    recent_traces.appendleft({"trace": trace, "question": s.question, "tier": tier, "match": s.match.id,
                              "user": s.user.get("name"), "role": s.user.get("primary_role")})
    out = {"answer": s.answer, "audience": s.audience, "intent": s.intent, "tier": tier, "decision": s.decision,
           "evidence": s.evidence[:12], "verification": s.verification, "action": s.action, "trace": trace,
           "latency_ms": total_ms, "clock": s.facts.get("state", {}).get("clock"), "focus": s.facts.get("focus_moment")}
    if "package" in s.extra:
        out["package"] = s.extra["package"]
    return out | (extra or {})


async def handle_ask(match: Match, question: str, audience: str = "fan", playback_t: float | None = None, user: dict | None = None,
                     focus_moment_id: str | None = None, deep_analysis: bool = True, replay_hint: dict | None = None) -> dict:
    t0 = time.perf_counter()
    s = SharedState(match=match, question=question.strip(), audience=audience, playback_t=playback_t, user=user or {},
                    focus_moment_id=focus_moment_id, deep_analysis=deep_analysis, extra=dict(replay_hint or {}))
    await run_workflow(s)
    return _finish(s, t0)


async def build_recap(match: Match, audience: str, phase: str, playback_t: float | None = None, s: SharedState | None = None,
                      user: dict | None = None) -> dict:
    standalone = s is None
    t0 = time.perf_counter()
    if s is None:
        s = SharedState(match=match, question=f"{phase} recap", audience=audience, playback_t=playback_t, user=user or {})
        s.intent, s.tier = "recap", "T4"
    end = {"half": 45 * 60 + 300, "full": None}.get(phase, playback_t)
    s.playback_t = end
    await observer.run(s)
    await analyst.run(s)
    await scout.run(s)
    digest = metrics.window_digest(match, 0, end if end is not None else match.events[-1]["t"])
    s.facts["digest"] = digest
    recap = await _verified_story(s, {"digest": digest, "turning_points": match.pkg["ground_truth"]["turning_points"],
                                      "top_players": s.facts["top_players"]}, f"{phase}_time_recap")
    replays = [r for r in match.replays if end is None or r["minute"] * 60 <= end]
    with s.trace.step(producer.name, "assemble_package", source="deterministic") as st:
        package = {"phase": phase, "audience": audience, "recap": recap, "score": digest["score_end"],
                   "talking_points": [f"{k['clock']} {k['headline']}" for k in s.facts["key_moments"]][:6],
                   "top_players": s.facts["top_players"][:3],
                   "replay_reel": [{"id": r["id"], "goal_number": r["goal_number"], "clock": r["clock"], "title": r["title"]} for r in replays],
                   "stats": digest["stats"], "verification": s.verification, "poster_prompt": await producer.poster_prompt(s),
                   "requires_editor_approval": audience == "broadcaster"}
        st.detail = {"replays": len(replays), "talking_points": len(package["talking_points"])}
    if standalone:
        package["trace"] = _finish(s, t0)["trace"]
    return package


async def verify_commentary(match: Match, lines: list[dict], user: dict | None = None) -> dict:
    t0 = time.perf_counter()
    s = SharedState(match=match, question="verify commentary", audience="broadcaster", user=user or {})
    s.intent, s.tier = "production", "T4"
    claims = await producer.extract_claims(s, [{"i": i, "text": l["text"]} for i, l in enumerate(lines)])
    results = []
    with s.trace.step(referee.name, "verify_commentary_claims", source="deterministic") as st:
        for c in claims:
            idx = int(c.get("line", 0)) if str(c.get("line", "0")).isdigit() else 0
            results.append(producer.verify_claim(s, c, lines[min(idx, len(lines) - 1)] if lines else {}))
        st.detail = {"claims": len(results), "misleading": sum(r["verdict"] == "misleading" for r in results)}
    return {"claims": results, "lines": lines, "trace": _finish(s, t0)["trace"]}


async def transcribe_and_verify(match: Match, audio: bytes, filename: str, user: dict | None = None) -> dict:
    s = SharedState(match=match, question="transcribe commentary", audience="broadcaster", user=user or {})
    tr = await voice.transcribe(s, audio, filename)
    res = await verify_commentary(match, tr["lines"], user)
    res["transcript"] = tr["text"]
    res["trace"]["steps"] = s.trace.to_dict()["steps"] + res["trace"]["steps"]
    return res


def live_narrative_for(match: Match, km: dict) -> str:
    who = match.player_name(km.get("player")) if km.get("player") else ""
    team = match.team_name(km.get("team"))
    if km["type"] == "goal":
        rep = next((r for r in match.replays if r["id"] == km.get("replay_id")), None)
        if rep:
            f, sc = rep["summary_facts"], rep["score_after"]
            return (f"GOAL {km['clock']}: {who} for {team}. {f['passes']} passes, {f['players_involved']} players involved. "
                    f"{match.home['short']} {sc['home']}-{sc['away']} {match.away['short']}.")
    if km["type"] == "red_card":
        return f"RED CARD {km['clock']}: {who} ({team}). {km.get('headline', '')}"
    if km["type"] in ("substitution", "tactical_change"):
        return f"{km['clock']} {team}: {km.get('headline')}"
    if km["type"] == "big_chance_missed":
        return f"{km['clock']} BIG CHANCE: {who} ({team}). {km.get('headline', '')}"
    return f"{km['clock']} {km.get('headline', km['type'])}"
