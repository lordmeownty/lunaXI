"""Editorial workflow: draft → pending_review → approved / changes_requested. Persisted to LUNA_STATE_DIR."""
from __future__ import annotations

import datetime as dt
import json
import uuid

from ..config import settings

_PATH = settings.state_dir / "packages.json"
PACKAGES: dict[str, dict] = json.loads(_PATH.read_text()) if _PATH.exists() else {}


def _save():
    try:
        _PATH.write_text(json.dumps(PACKAGES, indent=1))
    except OSError:
        pass


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def create(match_id: str, audience: str, recap: dict, user: dict, title: str) -> dict:
    pid = "PKG-" + uuid.uuid4().hex[:8].upper()
    PACKAGES[pid] = {"id": pid, "match_id": match_id, "audience": audience, "title": title, "status": "pending_review",
                     "recap": recap.get("recap"), "talking_points": recap.get("talking_points", []),
                     "replay_reel": recap.get("replay_reel", []), "verification": recap.get("verification", {}),
                     "submitted_by": user.get("name"), "submitted_at": now(), "decided_by": None, "decided_at": None,
                     "note": None, "history": [{"at": now(), "by": user.get("name"), "action": "submitted"}]}
    _save()
    return PACKAGES[pid]


def decide(pid: str, approve: bool, user: dict, note: str | None) -> dict:
    pkg = PACKAGES[pid]
    pkg["status"] = "approved" if approve else "changes_requested"
    pkg["decided_by"], pkg["decided_at"], pkg["note"] = user.get("name"), now(), note
    pkg["history"].append({"at": now(), "by": user.get("name"), "action": pkg["status"], "note": note})
    _save()
    return pkg
