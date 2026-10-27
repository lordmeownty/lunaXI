"""Agent-to-Agent (A2A): agent card + JSON-RPC message/send so other agents can delegate to Luna XI."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request

from ..agents import orchestrator
from ..data.store import MatchNotFound, get_store
from ..platform.governance import audit
from ..security.auth import User, require
from ..security.guard import limiter

router = APIRouter(tags=["a2a"])


@router.get("/.well-known/agent.json")
def agent_card(request: Request):
    base = str(request.base_url).rstrip("/")
    return {"protocolVersion": "0.3.0", "name": "Luna XI Match Intelligence",
            "description": "Explainable football match intelligence over synthetic data: verified answers, tactical explanations, replays and recap packages.",
            "url": f"{base}/a2a", "version": "1.2.0", "preferredTransport": "JSONRPC",
            "capabilities": {"streaming": False, "pushNotifications": False},
            "defaultInputModes": ["text/plain"], "defaultOutputModes": ["application/json", "text/plain"],
            "securitySchemes": {"entra": {"type": "oauth2", "description": "Microsoft Entra ID bearer token"}}, "security": [{"entra": []}],
            "skills": [{"id": "match-question", "name": "Answer a match question", "tags": ["football", "explainable", "synthetic"],
                        "description": "Who scored, why momentum changed, shot danger, catch-up. Put matchId in message metadata.",
                        "examples": ["Why did the substitution change the match?"]},
                       {"id": "recap-package", "name": "Create a verified recap package", "tags": ["broadcast", "recap"],
                        "description": "Ask for a 'broadcaster package' to get talking points, replay reel and referee verdict."}]}


@router.post("/a2a")
async def a2a(rpc: dict, user: User = Depends(require("a2a.invoke"))):
    rid = rpc.get("id")
    if rpc.get("method") != "message/send":
        return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "Method not found"}}
    params = rpc.get("params", {})
    msg = params.get("message", {})
    text = " ".join(p.get("text", "") for p in msg.get("parts", []) if p.get("kind", "text") == "text").strip()
    meta = {**params.get("metadata", {}), **msg.get("metadata", {})}
    if not text:
        return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32602, "message": "Empty message"}}
    try:
        m = get_store().get(meta.get("matchId", "m3-goal-festival"))
    except MatchNotFound:
        return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32602, "message": "Unknown matchId"}}
    limiter.check(user.oid, "a2a")
    res = await orchestrator.handle_ask(m, text, meta.get("audience", "fan"), meta.get("playbackT"), user.public(), deep_analysis=user.can("analysis.deep"))
    audit.record(user.public(), "a2a.message", m.id, {"tier": res["tier"]})
    return {"jsonrpc": "2.0", "id": rid, "result": {
        "kind": "task", "id": uuid.uuid4().hex, "contextId": msg.get("contextId") or uuid.uuid4().hex, "status": {"state": "completed"},
        "artifacts": [{"artifactId": uuid.uuid4().hex, "name": "luna-answer",
                       "parts": [{"kind": "text", "text": res["answer"]},
                                 {"kind": "data", "data": {"tier": res["tier"], "verification": res["verification"], "evidence": res["evidence"],
                                                           "action": res["action"], "trace_id": res["trace"]["id"]}}]}]}}
