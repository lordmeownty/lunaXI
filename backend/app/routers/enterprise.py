"""Enterprise workflow: editorial approval, audit, security, provenance and event-driven publishing."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..agents import orchestrator
from ..data.store import MatchNotFound, get_store
from ..platform import events, packages
from ..platform.governance import audit
from ..security.auth import DEMO_USERS, User, require
from .intelligence import security_status

router = APIRouter(prefix="/api", tags=["enterprise"])


def _match(mid: str):
    try:
        return get_store().get(mid)
    except MatchNotFound:
        raise HTTPException(404, f"Unknown match {mid}")


async def seed_demo_package() -> None:
    """One pending package from a broadcaster, so a Director/Editor can demo approval straight away."""
    if any(p["status"] == "pending_review" for p in packages.PACKAGES.values()):
        return
    name, _ = DEMO_USERS["Luna.Broadcaster"]
    who = {"name": name, "primary_role": "Luna.Broadcaster", "oid": "demo-broadcaster", "auth": "demo"}
    recap = await orchestrator.build_recap(get_store().get("m5-controversial"), "broadcaster", "full", user=who)
    pkg = packages.create("m5-controversial", "broadcaster", recap, who, "Controversial Finish · full-time package")
    audit.record(who, "package.submitted", pkg["id"], {"match": "m5-controversial", "seeded": True})


class SubmitRequest(BaseModel):
    match_id: str
    audience: Literal["fan", "new_fan", "tactical", "broadcaster", "accessible"] = "broadcaster"
    phase: Literal["half", "full", "live"] = "full"
    playback_t: float | None = None
    title: str = Field(default="Full-time package", max_length=120)


@router.post("/packages")
async def submit_package(req: SubmitRequest, user: User = Depends(require("package.submit"))):
    m = _match(req.match_id)
    recap = await orchestrator.build_recap(m, req.audience, req.phase, req.playback_t, user=user.public())
    if recap.get("verification", {}).get("verdict") != "approved":
        raise HTTPException(422, "Evidence Referee did not approve this package; regenerate before submitting")
    pkg = packages.create(req.match_id, req.audience, recap, user.public(), f"{m.pkg['title']} · {req.title}")
    pkg["event"] = await events.publish_package_event("submitted", pkg)
    audit.record(user.public(), "package.submitted", pkg["id"], {"match": req.match_id})
    return pkg


@router.get("/packages")
def list_packages(_: User = Depends(require("package.submit"))):
    return sorted(packages.PACKAGES.values(), key=lambda p: p["submitted_at"], reverse=True)


class DecisionRequest(BaseModel):
    approve: bool
    note: str | None = Field(default=None, max_length=500)


@router.post("/packages/{pid}/decision")
async def decide(pid: str, req: DecisionRequest, user: User = Depends(require("package.approve"))):
    if pid not in packages.PACKAGES:
        raise HTTPException(404, "Package not found")
    pkg = packages.PACKAGES[pid]
    if pkg["status"] != "pending_review":
        raise HTTPException(409, f"Package already {pkg['status']}")
    if pkg["submitted_by"] == user.name:
        raise HTTPException(403, "Separation of duties: you cannot approve your own package")
    pkg = packages.decide(pid, req.approve, user.public(), req.note)
    pkg["event"] = await events.publish_package_event(pkg["status"], pkg)
    audit.record(user.public(), f"package.{pkg['status']}", pid, {"note": req.note})
    return pkg


@router.get("/audit")
def audit_log(limit: int = 100, _: User = Depends(require("ops.view"))):
    return {"chain_valid": audit.verify_chain(), "records": list(audit.recent)[:limit]}


@router.get("/security")
def security(_: User = Depends(require("match.view"))):
    return security_status()


@router.post("/ops/matches/{mid}/publish-events")
async def publish_events(mid: str, user: User = Depends(require("ops.broadcast_events"))):
    res = await events.publish_match_events(mid, _match(mid).events)
    audit.record(user.public(), "ops.match_events_published", mid, res)
    return res


@router.get("/system/provenance")
def provenance(_: User = Depends(require("match.view"))):
    f = Path(__file__).resolve().parents[3] / "services" / "simulator-adapter" / "integration.json"
    return {"synthetic": True, "matches": len(get_store().index), "engine": json.loads(f.read_text()) if f.exists() else {},
            "runtime": "Luna XI reads normalised match packages; Open Football is never called by end users."}
