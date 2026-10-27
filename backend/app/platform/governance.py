"""Governance: persistent, hash-chained audit log + daily AI budget guard."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import threading
import uuid
from collections import deque

from ..config import settings


class AuditLog:
    """Append-only and tamper-evident: every record stores the hash of the previous one. Persisted to
    LUNA_STATE_DIR/audit.jsonl and reloaded on start (in Azure, also exported to Log Analytics)."""

    def __init__(self):
        self.lock = threading.Lock()
        self.recent: deque = deque(maxlen=500)
        self.last_hash = "genesis"
        settings.state_dir.mkdir(parents=True, exist_ok=True)
        self.path = settings.state_dir / "audit.jsonl"
        if self.path.exists():
            for line in self.path.read_text().splitlines()[-500:]:
                try:
                    rec = json.loads(line)
                    self.recent.appendleft(rec)
                    self.last_hash = rec["hash"]
                except (ValueError, KeyError):
                    continue

    def record(self, actor: dict | None, action: str, target: str = "", detail: dict | None = None) -> dict:
        with self.lock:
            rec = {"id": uuid.uuid4().hex[:12], "ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                   "actor": {k: (actor or {}).get(k) for k in ("oid", "name", "primary_role", "auth", "viewing_as")},
                   "action": action, "target": target, "detail": detail or {}, "prev": self.last_hash}
            rec["hash"] = hashlib.sha256(json.dumps(rec, sort_keys=True).encode()).hexdigest()[:16]
            self.last_hash = rec["hash"]
            self.recent.appendleft(rec)
            try:
                with self.path.open("a") as f:
                    f.write(json.dumps(rec) + "\n")
            except OSError:
                pass
            return rec

    def verify_chain(self) -> bool:
        items = list(reversed(self.recent))
        for a, b in zip(items, items[1:]):
            body = {k: v for k, v in b.items() if k != "hash"}
            if b["prev"] != a["hash"] or hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()[:16] != b["hash"]:
                return False
        return True


class Budget:
    def __init__(self):
        self.day, self.spent = dt.date.today(), 0.0

    def add(self, usd: float):
        if dt.date.today() != self.day:
            self.day, self.spent = dt.date.today(), 0.0
        self.spent += usd

    def exhausted(self) -> bool:
        return self.spent >= settings.daily_budget_usd

    def snapshot(self) -> dict:
        return {"day": self.day.isoformat(), "spent_usd": round(self.spent, 4), "limit_usd": settings.daily_budget_usd,
                "remaining_usd": round(max(0, settings.daily_budget_usd - self.spent), 4)}


audit = AuditLog()
budget = Budget()
