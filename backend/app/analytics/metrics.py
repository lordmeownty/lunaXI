"""Deterministic football analytics. LLMs never compute numbers; they read these."""
from __future__ import annotations

from collections import Counter, defaultdict

from ..data.store import Match


def team_stats(m: Match, t_from: float = 0, t_to: float | None = None) -> dict:
    t_to = t_to if t_to is not None else 1e9
    ev = [e for e in m.events if t_from <= e["t"] <= t_to and e.get("side")]
    passes = Counter(e["side"] for e in ev if e["type"] == "pass")
    total = sum(passes.values()) or 1
    out = {}
    for side in ("home", "away"):
        mine = [e for e in ev if e["side"] == side]
        p = [e for e in mine if e["type"] == "pass"]
        shots = [e for e in mine if e["type"] == "shot"]
        q = lambda e, k: e.get("qualifiers", {}).get(k)
        out[side] = {"team": m.home["name"] if side == "home" else m.away["name"],
                     "possession_pct": round(100 * passes[side] / total, 1), "passes": len(p),
                     "pass_completion_pct": round(100 * sum(1 for x in p if x["outcome"] == "complete") / (len(p) or 1), 1),
                     "progressive_passes": sum(1 for x in p if q(x, "progressive")),
                     "final_third_entries": sum(1 for x in p if q(x, "final_third_entry") and x["outcome"] == "complete"),
                     "shots": len(shots), "shots_on_target": sum(1 for s in shots if s["outcome"] in ("goal", "saved")),
                     "xg": round(sum(s.get("xg", 0) for s in shots), 2), "goals": sum(1 for e in mine if e["type"] == "goal"),
                     "tackles_won": sum(1 for e in mine if e["type"] == "tackle"),
                     "interceptions": sum(1 for e in mine if e["type"] == "interception"),
                     "high_regains": sum(1 for e in mine if e["type"] in ("tackle", "interception") and q(e, "high_regain")),
                     "fouls": sum(1 for e in mine if e["type"] == "foul"),
                     "yellow_cards": sum(1 for e in mine if e["type"] == "card" and e.get("card") == "yellow"),
                     "red_cards": sum(1 for e in mine if e["type"] == "card" and e.get("card") == "red")}
    return out


def momentum_series(m: Match, window_min: int = 5, t_to: float | None = None) -> list[dict]:
    end = int((t_to if t_to is not None else m.events[-1]["t"]) // 60) + 1
    series = []
    for start in range(0, max(end, window_min), window_min):
        s = team_stats(m, start * 60, (start + window_min) * 60 - 0.1)
        threat = {sd: round(s[sd]["xg"] * 10 + s[sd]["shots"] + s[sd]["final_third_entries"] * 0.6 + s[sd]["high_regains"] * 0.8
                            + s[sd]["possession_pct"] / 25, 2) for sd in ("home", "away")}
        tot = (threat["home"] + threat["away"]) or 1
        series.append({"from_min": start, "to_min": start + window_min, "home": threat["home"], "away": threat["away"],
                       "momentum": round(100 * (threat["home"] - threat["away"]) / tot, 1), "possession_home": s["home"]["possession_pct"]})
    return series


def detect_momentum_shifts(series: list[dict], threshold: float = 45) -> list[dict]:
    return [{"at_min": b["from_min"], "delta": round(b["momentum"] - a["momentum"], 1), "towards": "home" if b["momentum"] > a["momentum"] else "away"}
            for a, b in zip(series, series[1:]) if abs(b["momentum"] - a["momentum"]) >= threshold]


def compare_halves_of_change(m: Match, minute: int, span: int = 15) -> dict:
    return {"minute": minute, "span_min": span, "before": team_stats(m, max(0, (minute - span) * 60), minute * 60),
            "after": team_stats(m, minute * 60, (minute + span) * 60)}


def player_impact(m: Match, t_to: float | None = None, top: int = 5) -> list[dict]:
    score: dict[str, float] = defaultdict(float)
    detail: dict[str, Counter] = defaultdict(Counter)
    for e in m.events_until(t_to):
        pid, typ, q = e.get("player"), e["type"], e.get("qualifiers", {})
        if not pid:
            continue
        if typ == "pass" and e["outcome"] == "complete":
            score[pid] += 0.1 + (0.4 if q.get("progressive") else 0) + (0.5 if q.get("final_third_entry") else 0)
            detail[pid]["passes"] += 1
        elif typ == "shot":
            score[pid] += 1 + e.get("xg", 0) * 5
            detail[pid]["shots"] += 1
        elif typ == "goal":
            score[pid] += 4
            detail[pid]["goals"] += 1
        elif typ in ("tackle", "interception"):
            score[pid] += 0.6
            detail[pid]["regains"] += 1
    for g in m.goals:
        if g.get("assist") and (t_to is None or g["t"] <= t_to):
            score[g["assist"]] += 2
            detail[g["assist"]]["assists"] += 1
    ranked = sorted(score.items(), key=lambda kv: kv[1], reverse=True)[:top]
    return [{"player": pid, "name": m.player_name(pid), "number": m.players.get(pid, {}).get("number"),
             "team": m.players.get(pid, {}).get("team_name"), "side": m.players.get(pid, {}).get("side"),
             "impact": round(s, 2), "detail": dict(detail[pid])} for pid, s in ranked]


def shot_danger_features(e: dict) -> dict:
    xg = e.get("xg", 0)
    return {"xg": xg, "outcome": e.get("outcome"), "penalty": e.get("qualifiers", {}).get("penalty", False),
            "heuristic_band": "high" if xg >= 0.3 else "medium" if xg >= 0.1 else "low"}


def last_event_of(m: Match, etype: str, t: float | None) -> dict | None:
    return next((e for e in reversed(m.events_until(t)) if e["type"] == etype), None)


def window_digest(m: Match, t_from: float, t_to: float) -> dict:
    notable = []
    for e in m.events:
        if t_from <= e["t"] <= t_to and (e["type"] in ("goal", "card", "substitution", "tactical_change", "save")
                                         or (e["type"] == "shot" and e.get("xg", 0) >= 0.15)):
            notable.append({"id": e["id"], "clock": e["clock"], "type": e["type"], "team": m.team_name(e.get("team")),
                            "player": m.player_name(e.get("player")) if e.get("player") else None, "outcome": e.get("outcome"),
                            "xg": e.get("xg"), "card": e.get("card"), "note": e.get("note")})
    return {"from": round(t_from / 60, 1), "to": round(t_to / 60, 1), "score_end": m.score_at(t_to),
            "stats": team_stats(m, t_from, t_to), "notable_events": notable[:25]}
