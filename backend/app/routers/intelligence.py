from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from ..agents import orchestrator
from ..agents.state import AUDIENCES, SharedState
from ..config import SECRET_SOURCE, settings
from ..data.store import MatchNotFound, get_store
from ..foundry import client as foundry
from ..foundry import realtime
from ..foundry.client import FoundryUnavailable
from ..platform import packages
from ..platform.events import outbox
from ..platform.governance import audit, budget
from ..security.auth import CAPABILITIES, User, current_user, require
from ..security.guard import limiter
from ..telemetry import efficiency, recent_traces

router = APIRouter(prefix="/api", tags=["intelligence"])
Audience = Literal["fan", "new_fan", "tactical", "broadcaster", "accessible"]


def _match(mid: str):
    try:
        return get_store().get(mid)
    except MatchNotFound:
        raise HTTPException(404, f"Unknown match {mid}")


@router.get("/me")
def me(user: User = Depends(current_user)):
    pending = sum(1 for p in packages.PACKAGES.values() if p["status"] == "pending_review")
    return user.public() | {"auth_mode": settings.auth_mode, "pending_approvals": pending if user.can("package.approve") else 0}


class SessionEvent(BaseModel):
    kind: Literal["sign_in", "sign_out", "view_as"]
    value: str | None = None


@router.post("/session/event")
def session_event(ev: SessionEvent, user: User = Depends(current_user)):
    """Audits sign-in / sign-out and every 'View as' switch made by a Director."""
    if ev.kind == "view_as" and "Luna.Director" not in user.real_roles:
        raise HTTPException(403, "Only Luna.Director can preview other roles")
    rec = audit.record(user.public(), f"session.{ev.kind}", ev.value or "-")
    return {"ok": True, "audit_id": rec["id"]}


class AskRequest(BaseModel):
    match_id: str
    question: str = Field(min_length=1, max_length=600)
    audience: Audience = "fan"
    playback_t: float | None = None
    focus_moment_id: str | None = None
    goal_number: int | None = None
    view: Literal["broadcast", "overhead", "behind_shooter", "goalkeeper"] | None = None


@router.post("/ask")
async def ask(req: AskRequest, user: User = Depends(require("luna.ask"))):
    limiter.check(user.oid, "ask")
    hint = {k: v for k, v in {"goal_number": req.goal_number, "view": req.view}.items() if v is not None}
    res = await orchestrator.handle_ask(_match(req.match_id), req.question, req.audience, req.playback_t, user.public(),
                                        req.focus_moment_id, deep_analysis=user.can("analysis.deep"), replay_hint=hint)
    if res["tier"] == "BLOCKED":
        audit.record(user.public(), "safety.blocked_prompt", req.match_id, res["verification"])
    return res


class RecapRequest(BaseModel):
    match_id: str
    audience: Audience = "fan"
    phase: Literal["half", "full", "live"] = "full"
    playback_t: float | None = None


@router.post("/recap")
async def recap(req: RecapRequest, user: User = Depends(require("recap.create"))):
    limiter.check(user.oid, "recap", 20)
    return await orchestrator.build_recap(_match(req.match_id), req.audience, req.phase, req.playback_t, user=user.public())


class PosterRequest(BaseModel):
    match_id: str


@router.post("/recap/poster")
async def poster(req: PosterRequest, user: User = Depends(require("recap.create"))):
    limiter.check(user.oid, "image", 4)
    prompt = await orchestrator.producer.poster_prompt(SharedState(match=_match(req.match_id)))
    try:
        img = await foundry.generate_image(prompt)
    except FoundryUnavailable as e:
        raise HTTPException(503, f"Image model unavailable: {e}")
    audit.record(user.public(), "image.generated", req.match_id)
    return {"prompt": prompt, **img, "label": "AI-generated artwork: illustrative, not match evidence"}


class RealtimeRequest(BaseModel):
    match_id: str | None = None


@router.post("/realtime/session")
async def realtime_session(req: RealtimeRequest, user: User = Depends(require("luna.voice"))):
    limiter.check(user.oid, "voice", 10)
    title = None
    if req.match_id:
        m = _match(req.match_id)
        title = f"{m.home['name']} vs {m.away['name']} ({m.pkg['title']})"
    try:
        sess = await realtime.create_client_secret(title, user.name)
    except FoundryUnavailable as e:
        raise HTTPException(503, f"Realtime voice unavailable: {e}")
    audit.record(user.public(), "voice.session_started", req.match_id or "-")
    return sess


@router.get("/studio/{mid}/sample-commentary")
def sample_commentary(mid: str, _: User = Depends(require("studio.use"))):
    _match(mid)
    return get_store().commentary(mid)


class VerifyRequest(BaseModel):
    match_id: str
    lines: list[dict] = Field(max_length=200)


@router.post("/studio/verify")
async def studio_verify(req: VerifyRequest, user: User = Depends(require("studio.use"))):
    limiter.check(user.oid, "studio", 20)
    res = await orchestrator.verify_commentary(_match(req.match_id), req.lines, user.public())
    audit.record(user.public(), "studio.claims_verified", req.match_id,
                 {"claims": len(res["claims"]), "misleading": sum(c["verdict"] == "misleading" for c in res["claims"])})
    return res


@router.post("/studio/transcribe")
async def studio_transcribe(match_id: str = Form(...), file: UploadFile = File(...), user: User = Depends(require("studio.use"))):
    limiter.check(user.oid, "transcribe", 6)
    if not (file.content_type or "").startswith("audio/"):
        raise HTTPException(415, "Upload an audio file")
    audio = await file.read()
    if len(audio) > 25 * 1024 * 1024:
        raise HTTPException(413, "Audio must be under 25 MB")
    try:
        res = await orchestrator.transcribe_and_verify(_match(match_id), audio, file.filename or "audio.wav", user.public())
    except FoundryUnavailable as e:
        raise HTTPException(503, f"Transcription unavailable: {e}")
    audit.record(user.public(), "studio.audio_transcribed", match_id, {"bytes": len(audio)})
    return res


@router.get("/agents/workflow")
def agent_workflow(_: User = Depends(require("match.view"))):
    return orchestrator.workflow_graph() | {"agents": orchestrator.AGENT_ROSTER}


@router.get("/control-room")
def control_room(_: User = Depends(require("ops.view"))):
    return {"agents": orchestrator.AGENT_ROSTER, "workflow": orchestrator.workflow_graph(), "efficiency": efficiency.snapshot(),
            "budget": budget.snapshot(), "traces": list(recent_traces)[:10], "outbox": list(outbox)[:15],
            "models": {"Voice (GPT Realtime)": settings.realtime_deployment, "Transcription (GPT Transcribe)": settings.transcribe_deployment,
                       "Decision (Jev / Decision-1)": f"{settings.decision_deployment} · {settings.decision_mode}",
                       "Fast narratives (GPT-6 Luna)": settings.fast_deployment, "Reasoning (Sol)": settings.reasoning_deployment,
                       "Image": settings.image_deployment or "not set"},
            "security": security_status(), "foundry_connected": settings.foundry_enabled, "audiences": AUDIENCES,
            "capabilities": {k: sorted(v) for k, v in CAPABILITIES.items()}}


def security_status() -> dict:
    return {"identity": "Microsoft Entra ID (validated tokens + app roles)" if settings.entra_enabled else "Sign in with Microsoft (demo, simulated)",
            "auth_mode": settings.auth_mode,
            "key_vault": {"uri": settings.key_vault_uri or None, "status": "connected (managed identity)" if settings.key_vault_uri else "configured in Azure deployment",
                          "secrets": {k: v for k, v in SECRET_SOURCE.items()}},
            "prompt_shields": "Azure AI Content Safety" if settings.content_safety_endpoint else "local injection rules",
            "rate_limit_per_min": settings.rate_limit_per_min, "audit_chain_valid": audit.verify_chain(), "audit_records": len(audit.recent),
            "stream_auth": "2-minute HMAC tickets", "voice_auth": "ephemeral realtime client secrets"}
