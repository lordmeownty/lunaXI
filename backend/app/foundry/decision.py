"""Decision provider: Jev / Microsoft-Decision-1 (typed choices + probabilities).
FOUNDRY_DECISION_MODE: http | chat | heuristic. Heuristics are always the final fallback."""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field

import httpx

from ..config import settings
from . import client as foundry

log = logging.getLogger("luna.decision")


@dataclass
class Decision:
    selected: str
    probabilities: dict[str, float]
    confidence: float
    source: str
    latency_ms: int = 0
    extra: dict = field(default_factory=dict)


def _normalise(probs: dict[str, float]) -> dict[str, float]:
    s = sum(max(v, 0) for v in probs.values()) or 1.0
    return {k: round(max(v, 0) / s, 4) for k, v in probs.items()}


async def choose(question: str, options: list[str], context: dict | str, *, heuristic: dict[str, float] | None = None) -> Decision:
    t0 = time.perf_counter()
    ctx = context if isinstance(context, str) else json.dumps(context, default=str)[:6000]
    mode = settings.decision_mode.lower()
    if mode == "http" and settings.decision_endpoint:
        try:
            key = settings.decision_api_key or settings.foundry_api_key
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.post(settings.decision_endpoint, headers={"api-key": key, "Authorization": f"Bearer {key}"},
                                 json={"model": settings.decision_deployment, "input": ctx,
                                       "question": {"type": "choice", "text": question, "options": options}})
                r.raise_for_status()
                data = r.json()
            probs = data.get("probabilities") or {o.get("option"): o.get("probability", 0) for o in data.get("options", [])}
            probs = _normalise({k: float(v) for k, v in probs.items() if k in options})
            if probs:
                sel = max(probs, key=probs.get)
                return Decision(sel, probs, probs[sel], "http", int((time.perf_counter() - t0) * 1000))
        except Exception as e:  # noqa: BLE001
            log.warning("decision http failed: %s", e)
    if mode in ("chat", "http") and settings.foundry_enabled:
        schema = {"title": "decision", "type": "object", "required": ["probabilities"],
                  "properties": {"probabilities": {"type": "object", "properties": {o: {"type": "number"} for o in options}, "required": options}}}
        try:
            res = await foundry.chat(settings.decision_deployment, [
                {"role": "system", "content": "You are a decision model. Return only calibrated probabilities (0-1, summing to 1) for each option."},
                {"role": "user", "content": f"Question: {question}\nOptions: {options}\nContext: {ctx}"}],
                temperature=0, max_tokens=200, json_schema=schema)
            probs = _normalise({k: float(v) for k, v in res.json()["probabilities"].items() if k in options})
            sel = max(probs, key=probs.get)
            return Decision(sel, probs, probs[sel], "chat", res.latency_ms, {"input_tokens": res.input_tokens, "output_tokens": res.output_tokens})
        except Exception as e:  # noqa: BLE001
            log.info("decision chat fallback: %s", e)
    probs = _normalise(heuristic or {o: 1.0 for o in options})
    sel = max(probs, key=probs.get)
    return Decision(sel, probs, probs[sel], "heuristic", int((time.perf_counter() - t0) * 1000))


async def score(question: str, context: dict | str, *, heuristic: float) -> Decision:
    d = await choose(question, ["yes", "no"], context, heuristic={"yes": heuristic, "no": 1 - heuristic})
    p = d.probabilities.get("yes", 0.0)
    return Decision("yes" if p >= 0.5 else "no", d.probabilities, p, d.source, d.latency_ms, d.extra)


INTENT_PATTERNS: list[tuple[str, str]] = [
    ("replay", r"\b(show|replay|watch|see|play)\b.*\b(goal|moment|it|winner)\b|\bfrom the (keeper|goalkeeper)"),
    ("production", r"\b(package|broadcast(er)? pack|full[- ]time report|press release|social posts?)\b"),
    ("recap", r"\b(recap|summari[sz]e (the|this) (match|game|half)|match report|highlights)\b"),
    ("catch_up", r"\b(catch me up|what did i miss|what happened|last \d+ minutes|so far)\b"),
    ("tactical", r"\b(why|how did|how come|explain|tactic|shape|formation|press(ing)?|structure|turning point|change(d)? the|momentum)\b"),
    ("judgement", r"\b(was (that|it)|is (that|it)|dangerous|good chance|deserve|fair|harsh)\b"),
    ("lookup", r"\b(who|when|what minute|score|how many|which player|possession|shots?|cards?|scorer|assist)\b"),
]


def heuristic_intent(q: str) -> dict[str, float]:
    ql = q.lower()
    scores = {name: 0.02 for name, _ in INTENT_PATTERNS}
    for i, (name, pat) in enumerate(INTENT_PATTERNS):
        if re.search(pat, ql):
            scores[name] += 1.0 - i * 0.04
    if scores["replay"] > 0.5:
        scores["lookup"] *= 0.3
    return scores
