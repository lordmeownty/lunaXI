from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..data.store import Match
from ..telemetry import Trace

AUDIENCES = {
    "fan": "an engaged football fan: lively, clear, 2-4 sentences",
    "new_fan": "someone new to football: simple words, explain jargon in plain language, 2-4 short sentences",
    "tactical": "a tactics analyst: precise, mention shape, space, pressing and numbers, 3-5 sentences",
    "broadcaster": "a TV presenter: punchy talking points, 3 bullet points max, broadcast tone",
    "accessible": "a blind or low-vision listener: describe where on the pitch things happen (left/right, near which goal), calm pace, no visual references",
}


@dataclass
class SharedState:
    """The single blackboard every agent reads from and writes to."""
    match: Match
    question: str = ""
    audience: str = "fan"
    playback_t: float | None = None
    user: dict = field(default_factory=dict)
    focus_moment_id: str | None = None
    deep_analysis: bool = True
    trace: Trace = field(default_factory=Trace)
    intent: str | None = None
    tier: str | None = None
    decision: dict = field(default_factory=dict)
    facts: dict[str, Any] = field(default_factory=dict)
    evidence: list[dict] = field(default_factory=list)
    draft: str | None = None
    answer: str | None = None
    verification: dict = field(default_factory=dict)
    replay: dict | None = None
    action: dict | None = None
    retries: int = 0
    blocked: bool = False
    extra: dict = field(default_factory=dict)

    def add_evidence(self, label: str, value: Any = None, event_ids: list[str] | None = None, kind: str = "stat"):
        self.evidence.append({"label": label, "value": value, "event_ids": event_ids or [], "kind": kind})
