"""Loads the five synthetic match packages and exposes fast lookups."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from ..config import settings


class MatchNotFound(KeyError):
    pass


class Match:
    def __init__(self, pkg: dict):
        self.pkg, self.id = pkg, pkg["id"]
        self.events: list[dict] = pkg["events"]
        self.home, self.away = pkg["teams"]["home"], pkg["teams"]["away"]
        self.players: dict[str, dict] = {}
        for side in ("home", "away"):
            t = pkg["teams"][side]
            for p in t["players"] + t["bench"]:
                self.players[p["id"]] = {**p, "team": t["id"], "team_name": t["name"], "side": side}
        self.events_by_id = {e["id"]: e for e in self.events}
        self.replays = pkg["replays"]
        self.goals = [e for e in self.events if e["type"] == "goal"]

    def team_name(self, team_id: str | None) -> str:
        return self.home["name"] if team_id == self.home["id"] else self.away["name"] if team_id == self.away["id"] else "-"

    def player_name(self, pid: str | None) -> str:
        return self.players.get(pid or "", {}).get("name", "Unknown")

    def events_until(self, t: float | None) -> list[dict]:
        return self.events if t is None else [e for e in self.events if e["t"] <= t]

    def score_at(self, t: float | None) -> dict:
        s = {"home": 0, "away": 0}
        for g in self.goals:
            if t is None or g["t"] <= t:
                s[g["side"]] += 1
        return s

    def replay_for_goal(self, n: int) -> dict | None:
        return next((r for r in self.replays if r["goal_number"] == n), None)

    def summary(self) -> dict:
        p = self.pkg
        team = lambda t: {k: t[k] for k in ("id", "name", "short", "colour", "kit_secondary", "gk_colour", "formation_start")}
        return {k: p[k] for k in ("id", "title", "subtitle", "venue", "final_score", "showcase", "provenance", "duration_s")} | {
            "home": team(self.home), "away": team(self.away), "key_moments": p["key_moments"],
            "goals": p["ground_truth"]["goals"], "story": p["ground_truth"]["story"],
            "replays": [{k: r[k] for k in ("id", "goal_number", "clock", "minute", "team", "scorer", "title", "summary_facts")}
                        | {"goal_event_id": r["event_ids"][-1]} for r in self.replays],
            "players": {pid: {k: v[k] for k in ("name", "number", "role", "team_name", "side")} for pid, v in self.players.items()}}


class MatchStore:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        mdir = data_dir / "matches"
        self.index = json.loads((mdir / "index.json").read_text())
        self._matches = {e["id"]: Match(json.loads((mdir / f"{e['id']}.json").read_text())) for e in self.index}

    def get(self, match_id: str) -> Match:
        try:
            return self._matches[match_id]
        except KeyError as e:
            raise MatchNotFound(match_id) from e

    def commentary(self, match_id: str) -> dict:
        f = self.data_dir / "commentary" / f"{match_id}.json"
        return json.loads(f.read_text()) if f.exists() else {"match_id": match_id, "lines": []}


@lru_cache
def get_store() -> MatchStore:
    return MatchStore(settings.data_dir)
