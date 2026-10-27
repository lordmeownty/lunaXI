"""Short-lived HMAC tickets for SSE (EventSource cannot send Authorization headers)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time

from fastapi import HTTPException

_SECRET = (os.getenv("STREAM_TICKET_SECRET") or os.urandom(32).hex()).encode()


def issue(oid: str, match_id: str, ttl: int = 120) -> str:
    body = base64.urlsafe_b64encode(json.dumps({"oid": oid, "m": match_id, "exp": int(time.time()) + ttl}).encode()).decode()
    return f"{body}.{hmac.new(_SECRET, body.encode(), hashlib.sha256).hexdigest()[:32]}"


def verify(ticket: str, match_id: str) -> dict:
    try:
        body, sig = ticket.rsplit(".", 1)
        if not hmac.compare_digest(sig, hmac.new(_SECRET, body.encode(), hashlib.sha256).hexdigest()[:32]):
            raise ValueError("bad signature")
        data = json.loads(base64.urlsafe_b64decode(body))
        if data["m"] != match_id or data["exp"] < time.time():
            raise ValueError("expired or wrong match")
        return data
    except Exception:
        raise HTTPException(401, "Invalid or expired stream ticket")
