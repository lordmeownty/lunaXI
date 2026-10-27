from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from ..agents.orchestrator import live_narrative_for
from ..analytics import metrics
from ..data.store import MatchNotFound, get_store
from ..security import tickets
from ..security.auth import User, require

router = APIRouter(prefix="/api/matches", tags=["matches"])


def _match(mid: str):
    try:
        return get_store().get(mid)
    except MatchNotFound:
        raise HTTPException(404, f"Unknown match {mid}")


@router.get("")
def list_matches(_: User = Depends(require("match.view"))):
    return get_store().index


@router.get("/{mid}")
def match_summary(mid: str, _: User = Depends(require("match.view"))):
    return _match(mid).summary()


@router.get("/{mid}/stats")
def stats(mid: str, t_to: float | None = None, _: User = Depends(require("match.view"))):
    m = _match(mid)
    series = metrics.momentum_series(m, 5, t_to)
    return {"stats": metrics.team_stats(m, 0, t_to), "momentum": series, "shifts": metrics.detect_momentum_shifts(series),
            "top_players": metrics.player_impact(m, t_to, 5), "score": m.score_at(t_to)}


@router.get("/{mid}/replays/{rid}")
def replay(mid: str, rid: str, _: User = Depends(require("match.view"))):
    m = _match(mid)
    r = next((r for r in m.replays if r["id"] == rid or str(r["goal_number"]) == rid), None)
    if not r:
        raise HTTPException(404, "Replay not found")
    kit = lambda t: {"colour": t["colour"], "secondary": t["kit_secondary"], "gk": t["gk_colour"], "name": t["name"], "short": t["short"]}
    return r | {"scorer_name": m.player_name(r["scorer"]), "assist_name": m.player_name(r.get("assist")), "team_name": m.team_name(r["team"]),
                "teams": {"home": kit(m.home), "away": kit(m.away)}, "numbers": {pid: p["number"] for pid, p in m.players.items()},
                "looks": {pid: {"skin": p.get("skin", 0), "hair": p.get("hair", 0)} for pid, p in m.players.items()}}


@router.post("/{mid}/stream-ticket")
def stream_ticket(mid: str, user: User = Depends(require("match.view"))):
    _match(mid)
    return {"ticket": tickets.issue(user.oid, mid), "expires_in": 120}


@router.get("/{mid}/stream")
async def stream(mid: str, ticket: str, speed: float = Query(60.0, ge=1, le=600), start_t: float = 0.0):
    tickets.verify(ticket, mid)
    m = _match(mid)
    kms = {km["event_ids"][0]: km for km in m.pkg["key_moments"]}
    shown: set = set()

    async def gen():
        last_t, tick = start_t, 0
        for e in m.events:
            if e["t"] < start_t:
                continue
            await asyncio.sleep(max(0.0, (e["t"] - last_t) / speed))
            last_t = e["t"]
            yield f"data: {json.dumps({'kind': 'event', 'event': e, 'score': m.score_at(e['t'])})}\n\n"
            km = kms.get(e["id"])
            if km:
                yield "data: " + json.dumps({"kind": "narrative", "clock": e["clock"], "moment": km, "text": live_narrative_for(m, km)}) + "\n\n"
            tick += 1
            if tick % 40 == 0:
                series = metrics.momentum_series(m, 5, e["t"])
                yield "data: " + json.dumps({"kind": "momentum", "series": series, "t": e["t"]}) + "\n\n"
                for sh in metrics.detect_momentum_shifts(series):
                    if sh["at_min"] not in shown and start_t <= sh["at_min"] * 60 <= e["t"]:
                        shown.add(sh["at_min"])
                        team = m.home["name"] if sh["towards"] == "home" else m.away["name"]
                        yield "data: " + json.dumps({"kind": "narrative", "clock": f"{sh['at_min']}'", "text": f"Momentum shift: {team} take control from {sh['at_min']}'.",
                                                     "moment": {"type": "momentum_shift", "minute": sh["at_min"]}}) + "\n\n"
        yield "data: " + json.dumps({"kind": "end"}) + "\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
