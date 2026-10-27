"""
Luna XI synthetic match generator.

Produces five fully fictional, football-realistic match packages (teams, players, events, coordinates).
No real Premier League (or any real) match data is used.
Pitch: x in [0,105] m, y in [0,68] m. The HOME team always attacks towards x = 105.

Usage: python data/generator/generate_matches.py
"""
from __future__ import annotations

import argparse
import json
import math
import random
from dataclasses import dataclass, field
from pathlib import Path

PITCH_L, PITCH_W = 105.0, 68.0
GOAL_Y_MIN, GOAL_Y_MAX = 30.34, 37.66

FIRST_NAMES = ["Arlo", "Teo", "Remy", "Kasim", "Joel", "Bram", "Nico", "Idris", "Luca", "Oren", "Sami",
               "Felix", "Jaden", "Marek", "Tomas", "Elio", "Ravi", "Dario", "Hugo", "Kai", "Milo", "Zane",
               "Ezra", "Callum", "Rafi", "Owen", "Leon", "Anton", "Basil", "Cyrus", "Dax", "Emre", "Finn",
               "Galen", "Ivo", "Jonah", "Kofi", "Lior", "Mateo", "Nils", "Omar", "Pavel", "Quinn", "Rune"]
LAST_NAMES = ["Varga", "Okafor", "Lindqvist", "Moreau", "Castell", "Brennan", "Asante", "Holloway", "Ferro",
              "Navarro", "Kessler", "Dumont", "Akers", "Silvan", "Rook", "Thorne", "Mbeki", "Calder", "Pryce",
              "Okoro", "Vance", "Halden", "Quill", "Ashby", "Corwin", "Draper", "Ellery", "Fenn", "Garrow",
              "Hale", "Ingram", "Jory", "Kade", "Larkin", "Merrow", "Nash", "Orrin", "Pell", "Rask", "Stroud"]

FORMATIONS = {
    "4-3-3": [("GK", 5, 34), ("RB", 30, 8), ("CB", 24, 25), ("CB", 24, 43), ("LB", 30, 60),
              ("CM", 45, 34), ("CM", 52, 20), ("CM", 52, 48), ("RW", 72, 10), ("ST", 80, 34), ("LW", 72, 58)],
    "4-4-2": [("GK", 5, 34), ("RB", 30, 8), ("CB", 24, 25), ("CB", 24, 43), ("LB", 30, 60),
              ("RM", 55, 10), ("CM", 48, 27), ("CM", 48, 41), ("LM", 55, 58), ("ST", 78, 28), ("ST", 78, 40)],
    "4-2-3-1": [("GK", 5, 34), ("RB", 30, 8), ("CB", 24, 25), ("CB", 24, 43), ("LB", 30, 60),
                ("DM", 42, 28), ("DM", 42, 40), ("RAM", 64, 14), ("CAM", 62, 34), ("LAM", 64, 54), ("ST", 80, 34)],
    "5-4-1": [("GK", 5, 34), ("RWB", 32, 6), ("CB", 22, 20), ("CB", 20, 34), ("CB", 22, 48), ("LWB", 32, 62),
              ("RM", 50, 14), ("CM", 45, 28), ("CM", 45, 40), ("LM", 50, 54), ("ST", 74, 34)],
}
ATTACKING_ROLES = {"ST", "RW", "LW", "CAM", "RAM", "LAM", "RM", "LM"}


@dataclass
class Player:
    id: str
    name: str
    number: int
    role: str
    base_x: float
    base_y: float
    attributes: dict
    skin: int = 0
    hair: int = 0


@dataclass
class Team:
    id: str
    name: str
    short: str
    colour: str
    kit_secondary: str
    gk_colour: str
    formation: str
    side: str
    players: list[Player] = field(default_factory=list)
    bench: list[Player] = field(default_factory=list)


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def to_pitch(team: Team, x: float, y: float) -> tuple[float, float]:
    if team.side == "home":
        return round(clamp(x, 0.5, 104.5), 2), round(clamp(y, 0.5, 67.5), 2)
    return round(clamp(PITCH_L - x, 0.5, 104.5), 2), round(clamp(PITCH_W - y, 0.5, 67.5), 2)


class MatchBuilder:
    def __init__(self, cfg: dict, seed: int):
        self.cfg, self.seed = cfg, seed
        self.rng = random.Random(seed)
        self.events: list[dict] = []
        self.eid = self.pos_id = 0
        self.score = {"home": 0, "away": 0}
        self.replays: list[dict] = []
        self.key_moments: list[dict] = []
        self.used_names: set[str] = set()
        self.home = self._make_team(cfg["home"], "home")
        self.away = self._make_team(cfg["away"], "away")
        self.on_pitch = {"home": list(self.home.players), "away": list(self.away.players)}
        self.cards: dict[str, int] = {}

    def _name(self) -> str:
        while True:
            n = f"{self.rng.choice(FIRST_NAMES)} {self.rng.choice(LAST_NAMES)}"
            if n not in self.used_names:
                self.used_names.add(n)
                return n

    def _attrs(self, role: str, quality: float) -> dict:
        r = self.rng

        def a(base):
            return int(clamp(base + quality * 10 + r.gauss(0, 6), 35, 95))
        attacking = role in ATTACKING_ROLES
        return {"passing": a(65 if role in {"CM", "CAM", "DM"} else 58),
                "finishing": a(70 if role == "ST" else (62 if attacking else 40)),
                "pace": a(70 if role in {"RW", "LW", "RB", "LB", "RWB", "LWB"} else 60),
                "defending": a(70 if role in {"CB", "DM", "RB", "LB"} else 45),
                "stamina": a(68), "vision": a(66 if role in {"CM", "CAM"} else 55)}

    def _make_team(self, tc: dict, side: str) -> Team:
        t = Team(id=tc["id"], name=tc["name"], short=tc["short"], colour=tc["colour"],
                 kit_secondary=tc.get("kit_secondary", "#f8fafc"), gk_colour=tc.get("gk_colour", "#facc15"),
                 formation=tc["formation"], side=side)
        q = tc.get("quality", 0.5)
        for i, (role, bx, by) in enumerate(FORMATIONS[tc["formation"]]):
            num = 1 if role == "GK" else i + 1
            t.players.append(Player(f"{tc['short']}-{num:02d}", self._name(), num, role, bx, by, self._attrs(role, q),
                                    self.rng.randrange(5), self.rng.randrange(4)))
        for j, role in enumerate(["GK", "CB", "CM", "CM", "RW", "ST", "LB"]):
            num = 12 + j
            t.bench.append(Player(f"{tc['short']}-{num:02d}", self._name(), num, role, 50, 34, self._attrs(role, q),
                                  self.rng.randrange(5), self.rng.randrange(4)))
        return t

    def team(self, side: str) -> Team:
        return self.home if side == "home" else self.away

    def _emit(self, t: float, side: str | None, player: Player | None, etype: str, **kw) -> dict:
        self.eid += 1
        ev = {"id": f"E{self.eid:05d}", "t": round(t, 1), "minute": int(t // 60), "clock": self._clock(t),
              "period": 1 if t < 45 * 60 + 240 else 2, "team": self.team(side).id if side else None,
              "side": side, "player": player.id if player else None, "type": etype}
        ev.update(kw)
        ev["score"] = dict(self.score)
        self.events.append(ev)
        return ev

    @staticmethod
    def _clock(t: float) -> str:
        m = int(t // 60)
        if m >= 90:
            return f"90+{m - 89}'"
        if m == 45 and t < 46 * 60:
            return "45'"
        return f"{m + 1}'"

    def _pick(self, side: str, roles: set[str] | None = None, exclude: Player | None = None) -> Player:
        pool = [p for p in self.on_pitch[side] if p.role != "GK" and p is not exclude]
        if roles:
            pref = [p for p in pool if p.role in roles]
            if pref:
                pool = pref
        return self.rng.choice(pool)

    def _gk(self, side: str) -> Player:
        return next(p for p in self.on_pitch[side] if p.role == "GK")

    def _xg(self, x_rel: float, y_rel: float) -> float:
        dx, dy = 105 - x_rel, abs(34 - y_rel)
        dist = math.hypot(dx, dy)
        angle = abs(math.atan2(7.32 * dx, dx * dx + dy * dy - (7.32 / 2) ** 2))
        return round(clamp(1 / (1 + math.exp(-(-1.2 + 1.6 * angle - 0.09 * dist))), 0.01, 0.85), 3)

    def possession_chain(self, t: float, side: str, phase: dict, scripted_goal: dict | None = None) -> float:
        r = self.rng
        self.pos_id += 1
        pid = f"P{self.pos_id:04d}"
        team = self.team(side)
        opp = "away" if side == "home" else "home"
        directness = phase.get("directness", {}).get(side, 0.5)
        n_passes = scripted_goal["passes"] if scripted_goal else max(1, int(r.gauss(5 - 3 * directness, 2)))
        x = scripted_goal.get("start_x", r.uniform(20, 45)) if scripted_goal else r.uniform(15, 40)
        y = r.uniform(8, 60)
        carrier = self._pick(side, {"CB", "DM", "CM", "RB", "LB"}) if x < 40 else self._pick(side)
        chain = []
        for i in range(n_passes):
            if scripted_goal:
                remaining = n_passes - i
                target_x = 105 - remaining * (105 - x) / (remaining + 1) * 0.9
                nx = clamp(x + max(4.0, (target_x - x)) + r.uniform(-2, 6), x - 5, 98)
                ny = clamp(y + r.uniform(-16, 16), 6, 62)
                if i == n_passes - 1:
                    nx, ny = r.uniform(88, 97), r.uniform(24, 44)
            else:
                nx = clamp(x + r.gauss(6 + 10 * directness, 9), 5, 100)
                ny = clamp(y + r.gauss(0, 13), 3, 65)
            receiver = self._pick(side, ATTACKING_ROLES if nx > 65 else None, exclude=carrier)
            success = True
            if not scripted_goal:
                pressure = phase.get("press", {}).get(opp, 0.5)
                fail_p = 0.08 + 0.12 * pressure + (0.08 if nx > 75 else 0) + (0.18 * pressure if nx < 45 else 0)
                success = r.random() > fail_p
            sx, sy = to_pitch(team, x, y)
            ex, ey = to_pitch(team, nx, ny)
            chain.append(self._emit(t, side, carrier, "pass", outcome="complete" if success else "intercepted",
                                    receiver=receiver.id if success else None, x=sx, y=sy, end_x=ex, end_y=ey,
                                    possession_id=pid,
                                    qualifiers={"progressive": (nx - x) > 10, "final_third_entry": x < 70 <= nx,
                                                "under_pressure": r.random() < 0.3}))
            t += r.uniform(1.6, 4.5)
            if not success:
                defender = self._pick(opp, {"CB", "DM", "CM", "RB", "LB", "RWB", "LWB"})
                dx, dy = to_pitch(team, nx, ny)
                self._emit(t, opp, defender, "interception" if r.random() < 0.55 else "tackle", outcome="won",
                           x=dx, y=dy, possession_id=pid, qualifiers={"high_regain": nx < 45})
                if r.random() < 0.07:
                    self._emit(t + 1, opp, defender, "foul", x=dx, y=dy, on=receiver.id, possession_id=pid)
                    if r.random() < 0.25:
                        self._card(t + 2, opp, defender, "yellow")
                return t + r.uniform(2, 5)
            carrier = receiver
            x, y = nx, ny
            if r.random() < 0.25 and not scripted_goal:
                cx, cy = to_pitch(team, x, y)
                self._emit(t, side, carrier, "carry", x=cx, y=cy, end_x=to_pitch(team, x + 6, y)[0], end_y=cy, possession_id=pid)
                x = clamp(x + 6, 0, 100)
                t += r.uniform(1.5, 3.0)

        if scripted_goal is not None or (x > 75 and r.random() < 0.35 + 0.2 * directness):
            shooter = carrier if carrier.role != "GK" else self._pick(side, {"ST"})
            if scripted_goal and scripted_goal.get("scorer_role"):
                cand = [p for p in self.on_pitch[side] if p.role == scripted_goal["scorer_role"]]
                if cand:
                    shooter = cand[0]
            penalty = bool(scripted_goal and scripted_goal.get("penalty"))
            sx_rel = r.uniform(88, 96) if scripted_goal else x
            sy_rel = r.uniform(26, 42) if scripted_goal else y
            if penalty:
                sx_rel, sy_rel = 94.0, 34.0
            xg = 0.76 if penalty else self._xg(sx_rel, sy_rel)
            outcome = "goal" if scripted_goal else r.choices(["saved", "off_target", "blocked"], [0.35, 0.45, 0.2])[0]
            tgt_y = r.uniform(GOAL_Y_MIN + 0.3, GOAL_Y_MAX - 0.3) if outcome in ("goal", "saved") else \
                r.choice([r.uniform(26, GOAL_Y_MIN - 0.4), r.uniform(GOAL_Y_MAX + 0.4, 42)])
            tgt_z = r.uniform(0.15, 2.3) if outcome in ("goal", "saved") else r.uniform(0.2, 3.5)
            if scripted_goal and scripted_goal.get("corner"):
                c = scripted_goal["corner"]
                tgt_y = GOAL_Y_MIN + 0.45 if "left" in c else GOAL_Y_MAX - 0.45
                tgt_z = 2.1 if "top" in c else 0.3
            px, py = to_pitch(team, sx_rel, sy_rel)
            shot = self._emit(t, side, shooter, "shot", outcome=outcome, x=px, y=py, end_x=105.0 if side == "home" else 0.0,
                              end_y=round(tgt_y if side == "home" else PITCH_W - tgt_y, 2), end_z=round(tgt_z, 2), xg=xg,
                              possession_id=pid,
                              qualifiers={"penalty": penalty,
                                          "body_part": "right_foot" if penalty else r.choice(["right_foot", "left_foot", "head"]),
                                          "speed_kmh": round(r.uniform(68, 112), 1)})
            chain.append(shot)
            t += 1.2
            if outcome == "saved":
                gx, gy = to_pitch(team, 103, tgt_y)
                self._emit(t, opp, self._gk(opp), "save", x=gx, y=gy, possession_id=pid)
            if outcome == "goal":
                self.score[side] += 1
                g = self._emit(t, side, shooter, "goal", x=px, y=py, possession_id=pid,
                               assist=chain[-2]["player"] if len(chain) > 1 else None,
                               build_up_passes=len(chain) - 1, xg=xg)
                self._make_replay(team, side, chain, g, scripted_goal)
                t += r.uniform(50, 75)
            else:
                t += r.uniform(4, 10)
        else:
            if r.random() < 0.3:
                ox, oy = to_pitch(team, x, y)
                self._emit(t, side, carrier, "ball_out", x=ox, y=oy, possession_id=pid)
            t += r.uniform(2, 6)
        return t

    def _card(self, t: float, side: str, player: Player, colour: str, note: str = ""):
        self.cards[player.id] = self.cards.get(player.id, 0) + 1
        self._emit(t, side, player, "card", card=colour, note=note)
        if colour == "red" or self.cards[player.id] >= 2:
            self.on_pitch[side] = [p for p in self.on_pitch[side] if p is not player]

    def _snapshot(self, side: str, ball_rel_x: float, ball_rel_y: float, attacking: bool) -> list[dict]:
        team = self.team(side)
        out = []
        shift = (ball_rel_x - 52) * (0.55 if attacking else 0.45)
        for p in self.on_pitch[side]:
            if p.role == "GK":
                bx, by = (4 if attacking else 3), 34 + (ball_rel_y - 34) * 0.15
            else:
                bx, by = p.base_x + shift + (6 if attacking else -4), p.base_y + (ball_rel_y - 34) * 0.25
            px, py = to_pitch(team, clamp(bx, 2, 101), clamp(by, 2, 66))
            out.append({"id": p.id, "num": p.number, "side": side, "gk": p.role == "GK", "x": px, "y": py})
        return out

    def _make_replay(self, team: Team, side: str, chain: list[dict], goal_ev: dict, script: dict | None):
        opp = "away" if side == "home" else "home"
        frames = []
        t0 = chain[0]["t"]
        for ev in chain:
            bx, by = ev["x"], ev["y"]
            rel_x = bx if side == "home" else PITCH_L - bx
            rel_y = by if side == "home" else PITCH_W - by
            att = self._snapshot(side, rel_x, rel_y, True)
            dfn = self._snapshot(opp, PITCH_L - rel_x, PITCH_W - rel_y, False)
            for p in att:
                if p["id"] == ev["player"]:
                    p["x"], p["y"] = bx, by
                if ev.get("receiver") and p["id"] == ev["receiver"]:
                    p["x"], p["y"] = ev["end_x"], ev["end_y"]
            frames.append({"t": round(ev["t"] - t0, 2), "event_id": ev["id"], "action": ev["type"], "actor": ev["player"],
                           "receiver": ev.get("receiver"), "ball": {"x": bx, "y": by, "z": 0.11},
                           "ball_to": {"x": ev.get("end_x"), "y": ev.get("end_y"), "z": ev.get("end_z", 0.11)},
                           "players": att + dfn})
        shot = chain[-1]
        goal_no = self.score["home"] + self.score["away"]
        rid = f"R{goal_no:02d}"
        side_word = "right" if shot["end_y"] > 34 else "left"
        if side == "away":
            side_word = "left" if side_word == "right" else "right"
        height = "top" if shot["end_z"] > 1.6 else ("bottom" if shot["end_z"] < 0.6 else "middle")
        self.replays.append({
            "id": rid, "goal_number": goal_no, "minute": goal_ev["minute"], "clock": goal_ev["clock"], "team": team.id,
            "side": side, "scorer": goal_ev["player"], "assist": goal_ev.get("assist"),
            "title": script.get("title") if script else f"Goal {goal_no}",
            "summary_facts": {"passes": len(chain) - 1, "players_involved": len({e["player"] for e in chain}),
                              "duration_s": round(shot["t"] - t0, 1), "xg": shot["xg"],
                              "shot_speed_kmh": shot["qualifiers"]["speed_kmh"], "target": f"{height}-{side_word}",
                              "penalty": shot["qualifiers"]["penalty"]},
            "event_ids": [e["id"] for e in chain] + [goal_ev["id"]], "frames": frames,
            "shot": {"from": {"x": shot["x"], "y": shot["y"], "z": 0.11},
                     "to": {"x": shot["end_x"], "y": shot["end_y"], "z": shot["end_z"]},
                     "curve": round(self.rng.uniform(-1.2, 1.2), 2)},
            "score_after": dict(self.score),
        })
        self.key_moments.append({"id": f"KM-{goal_ev['id']}", "type": "goal", "minute": goal_ev["minute"], "clock": goal_ev["clock"],
                                 "team": team.id, "player": goal_ev["player"], "replay_id": rid,
                                 "headline": script.get("title") if script else f"{team.name} score",
                                 "score": dict(self.score), "event_ids": [goal_ev["id"]]})

    def build(self) -> dict:
        cfg = self.cfg
        goals = sorted(cfg["goals"], key=lambda g: g["t"])
        scripted = sorted(cfg.get("scripted", []), key=lambda s: s["t"])
        t = 0.0
        end_first, start_second, end_match = 45 * 60 + 120, 45 * 60 + 300, 90 * 60 + 240
        self._emit(0, None, None, "kick_off", note="First half")
        half_done = False
        while t < end_match:
            if not half_done and t >= end_first:
                self._emit(end_first, None, None, "half_time", note="Half-time")
                t = start_second
                self._emit(t, None, None, "kick_off", note="Second half")
                half_done = True
            while scripted and scripted[0]["t"] <= t:
                self._apply_script(scripted.pop(0))
            phase = self._phase(t)
            if goals and goals[0]["t"] <= t + 30:
                g = goals.pop(0)
                t = max(t, g["t"] - g["passes"] * 3.0)
                t = self.possession_chain(t, g["side"], phase, scripted_goal=g)
                continue
            t = self.possession_chain(t, "home" if self.rng.random() < phase.get("possession_home", 0.5) else "away", phase)
        while scripted:
            self._apply_script(scripted.pop(0))
        self._emit(end_match, None, None, "full_time", note="Full-time")
        return self._package()

    def _phase(self, t: float) -> dict:
        for ph in self.cfg["phases"]:
            if ph["from"] * 60 <= t < ph["to"] * 60:
                return ph
        return self.cfg["phases"][-1]

    def _km(self, kind: str, s: dict, team: Team, player: str | None):
        self.key_moments.append({"id": f"KM-{kind.upper()}-{int(s['t'])}", "type": kind, "minute": int(s["t"] // 60),
                                 "clock": self._clock(s["t"]), "team": team.id, "player": player,
                                 "headline": s.get("note", kind), "event_ids": [self.events[-1]["id"]]})

    def _apply_script(self, s: dict):
        side = s["side"]
        team = self.team(side)
        if s["type"] == "substitution":
            off = next((p for p in self.on_pitch[side] if p.role == s["off_role"]), self.on_pitch[side][-1])
            on = next(p for p in team.bench if p.role == s["on_role"] and p not in self.on_pitch[side])
            on.base_x, on.base_y, on.role = off.base_x, off.base_y, off.role
            self.on_pitch[side] = [on if p is off else p for p in self.on_pitch[side]]
            self._emit(s["t"], side, on, "substitution", player_off=off.id, note=s.get("note", ""))
            self._km("substitution", s, team, on.id)
        elif s["type"] == "tactical_change":
            team.formation = s["formation"]
            for p, (_, bx, by) in zip(list(self.on_pitch[side]), FORMATIONS[s["formation"]]):
                p.base_x, p.base_y = bx, by
            self._emit(s["t"], side, None, "tactical_change", formation=s["formation"], note=s.get("note", ""))
            self._km("tactical_change", s, team, None)
        elif s["type"] == "card":
            p = next((p for p in self.on_pitch[side] if p.role == s.get("role", "CB")), self.on_pitch[side][2])
            fx, fy = to_pitch(team, 30, 30)
            self._emit(s["t"] - 2, side, p, "foul", x=fx, y=fy, note=s.get("note", ""))
            self._card(s["t"], side, p, s["card"], s.get("note", ""))
            self._km(f"{s['card']}_card", s, team, p.id)
        elif s["type"] == "big_chance_missed":
            shooter = next((p for p in self.on_pitch[side] if p.role == "ST"), self._pick(side))
            px, py = to_pitch(team, 97, 36)
            self._emit(s["t"], side, shooter, "shot", outcome="off_target", x=px, y=py, end_x=105.0 if side == "home" else 0.0,
                       end_y=to_pitch(team, 105, 39.2)[1], end_z=0.9, xg=0.58,
                       qualifiers={"penalty": False, "body_part": "right_foot", "speed_kmh": 74.0})
            self._km("big_chance_missed", s, team, shooter.id)

    def _package(self) -> dict:
        def team_json(t: Team):
            return {"id": t.id, "name": t.name, "short": t.short, "colour": t.colour, "kit_secondary": t.kit_secondary,
                    "gk_colour": t.gk_colour, "formation_start": self.cfg[t.side]["formation"], "side": t.side,
                    "players": [p.__dict__ for p in t.players], "bench": [p.__dict__ for p in t.bench]}
        goals = [e for e in self.events if e["type"] == "goal"]
        names = {p.id: p.name for t in (self.home, self.away) for p in t.players + t.bench}
        cfg = self.cfg
        return {"schema_version": "1.2", "id": cfg["id"], "title": cfg["title"], "subtitle": cfg["subtitle"],
                "competition": "Luna XI Synthetic League", "venue": cfg["venue"],
                "teams": {"home": team_json(self.home), "away": team_json(self.away)},
                "final_score": dict(self.score), "duration_s": self.events[-1]["t"], "events": self.events,
                "key_moments": sorted(self.key_moments, key=lambda k: k["minute"]), "replays": self.replays,
                "ground_truth": {"final_score": dict(self.score),
                                 "goals": [{"n": i + 1, "minute": g["minute"], "clock": g["clock"], "team": g["team"],
                                            "scorer": g["player"], "scorer_name": names.get(g["player"]),
                                            "build_up_passes": g["build_up_passes"]} for i, g in enumerate(goals)],
                                 "story": cfg["story"], "turning_points": cfg.get("turning_points", [])},
                "showcase": cfg["showcase"],
                "provenance": {"synthetic": True, "contains_real_match_data": False, "contains_real_players": False,
                               "generator": "luna-xi/data/generator/generate_matches.py", "seed": self.seed,
                               "orientation": "home attacks towards x=105", "pitch_m": [PITCH_L, PITCH_W]}}


def m(minute: float, second: float = 0) -> float:
    return minute * 60 + second


SCENARIOS: list[dict] = [
    {"id": "m1-comeback", "title": "The Comeback", "venue": "Harbourside Park", "subtitle": "Two goals down. One change. Everything shifts.",
     "home": {"id": "harbour-city", "name": "Harbour City FC", "short": "HCF", "colour": "#2563eb", "kit_secondary": "#e0f2fe", "gk_colour": "#a3e635", "formation": "4-4-2", "quality": 0.55},
     "away": {"id": "kingsford-rovers", "name": "Kingsford Rovers", "short": "KRV", "colour": "#dc2626", "kit_secondary": "#111827", "gk_colour": "#f59e0b", "formation": "4-3-3", "quality": 0.55},
     "phases": [{"from": 0, "to": 58, "possession_home": 0.42, "press": {"home": 0.35, "away": 0.7}, "directness": {"home": 0.4, "away": 0.6}},
                {"from": 58, "to": 100, "possession_home": 0.64, "press": {"home": 0.8, "away": 0.35}, "directness": {"home": 0.65, "away": 0.4}}],
     "goals": [{"t": m(11, 40), "side": "away", "passes": 4, "scorer_role": "ST", "title": "Rovers punish a loose pass", "corner": "bottom-left"},
               {"t": m(30, 55), "side": "away", "passes": 6, "scorer_role": "RW", "title": "Six-pass move down the right"},
               {"t": m(63, 10), "side": "home", "passes": 3, "scorer_role": "ST", "title": "High press wins it back", "start_x": 62},
               {"t": m(77, 20), "side": "home", "passes": 7, "scorer_role": "LM", "title": "Seven-pass equaliser"},
               {"t": m(88, 5), "side": "home", "passes": 5, "scorer_role": "ST", "title": "Late winner, top corner", "corner": "top-right"}],
     "scripted": [{"t": m(58), "side": "home", "type": "substitution", "off_role": "CM", "on_role": "CM", "note": "Energetic midfielder on to lead the press"},
                  {"t": m(58, 30), "side": "home", "type": "tactical_change", "formation": "4-2-3-1", "note": "Harbour City switch to a high-pressing 4-2-3-1"}],
     "story": "Kingsford Rovers control the first hour and lead 2-0. A 58th-minute substitution and switch to a high press flips control; Harbour City score three times.",
     "turning_points": [{"minute": 58, "what": "Substitution + switch to high press", "effect": "Possession and final-third entries swing to Harbour City"}],
     "showcase": ["Momentum shift", "Substitution impact", "Catch-me-up"], "seed": 1101},
    {"id": "m2-tactical-battle", "title": "The Tactical Battle", "venue": "Northgate Arena", "subtitle": "One goal. Ninety minutes of chess.",
     "home": {"id": "northbridge-united", "name": "Northbridge United", "short": "NBU", "colour": "#0f766e", "kit_secondary": "#f0fdfa", "gk_colour": "#f472b6", "formation": "4-3-3", "quality": 0.6},
     "away": {"id": "riverside-athletic", "name": "Riverside Athletic", "short": "RSA", "colour": "#7c3aed", "kit_secondary": "#faf5ff", "gk_colour": "#22d3ee", "formation": "5-4-1", "quality": 0.55},
     "phases": [{"from": 0, "to": 55, "possession_home": 0.6, "press": {"home": 0.5, "away": 0.3}, "directness": {"home": 0.35, "away": 0.6}},
                {"from": 55, "to": 100, "possession_home": 0.66, "press": {"home": 0.65, "away": 0.3}, "directness": {"home": 0.5, "away": 0.55}}],
     "goals": [{"t": m(71, 15), "side": "home", "passes": 8, "scorer_role": "CAM", "title": "Patient eight-pass breakthrough"}],
     "scripted": [{"t": m(55), "side": "home", "type": "tactical_change", "formation": "4-2-3-1", "note": "Northbridge push a #10 between Riverside's lines"},
                  {"t": m(66), "side": "away", "type": "big_chance_missed", "note": "Riverside's best chance flashes wide on the counter"}],
     "story": "Riverside's 5-4-1 block frustrates Northbridge until a 55th-minute shift to a 4-2-3-1 puts a playmaker between the lines; the goal comes from that zone.",
     "turning_points": [{"minute": 55, "what": "Switch to 4-2-3-1", "effect": "More entries between the lines"}],
     "showcase": ["Tactical explanations", "Analyst mode", "Explain simply"], "seed": 2202},
    {"id": "m3-goal-festival", "title": "The Goal Festival", "venue": "Eastport Stadium", "subtitle": "Seven goals. Every one replayable.",
     "home": {"id": "eastport-wanderers", "name": "Eastport Wanderers", "short": "EPW", "colour": "#ea580c", "kit_secondary": "#1c1917", "gk_colour": "#22d3ee", "formation": "4-3-3", "quality": 0.6},
     "away": {"id": "millbrook-town", "name": "Millbrook Town", "short": "MBT", "colour": "#16a34a", "kit_secondary": "#f0fdf4", "gk_colour": "#e879f9", "formation": "4-4-2", "quality": 0.58},
     "phases": [{"from": 0, "to": 100, "possession_home": 0.53, "press": {"home": 0.5, "away": 0.5}, "directness": {"home": 0.65, "away": 0.65}}],
     "goals": [{"t": m(8, 30), "side": "home", "passes": 4, "scorer_role": "ST", "title": "Early strike after a quick switch"},
               {"t": m(16, 50), "side": "away", "passes": 3, "scorer_role": "ST", "title": "Direct reply from Millbrook"},
               {"t": m(27, 40), "side": "home", "passes": 6, "scorer_role": "LW", "title": "Left-side overload finished low", "corner": "bottom-right"},
               {"t": m(43, 20), "side": "away", "passes": 5, "scorer_role": "RM", "title": "Level before the break"},
               {"t": m(58, 45), "side": "home", "passes": 7, "scorer_role": "RW", "title": "Wanderers' best team goal"},
               {"t": m(72, 30), "side": "away", "passes": 6, "scorer_role": "ST", "title": "Millbrook strike into the top corner", "corner": "top-right"},
               {"t": m(86, 10), "side": "home", "passes": 4, "scorer_role": "ST", "title": "The winner"}],
     "scripted": [], "story": "An end-to-end match with seven goals; Eastport win 4-3 thanks to an 86th-minute winner.",
     "turning_points": [{"minute": 86, "what": "Eastport winner", "effect": "Decides an open game"}],
     "showcase": ["Luna Lens replays", "Show me the sixth goal", "Highlight recap"], "seed": 3303},
    {"id": "m4-underdog", "title": "The Underdog", "venue": "Ashford Lane", "subtitle": "A quarter of the ball. All of the points.",
     "home": {"id": "westvale-city", "name": "Westvale City", "short": "WVC", "colour": "#0284c7", "kit_secondary": "#f0f9ff", "gk_colour": "#facc15", "formation": "4-3-3", "quality": 0.7},
     "away": {"id": "ashford-athletic", "name": "Ashford Athletic", "short": "ASA", "colour": "#ca8a04", "kit_secondary": "#1c1917", "gk_colour": "#4ade80", "formation": "5-4-1", "quality": 0.45},
     "phases": [{"from": 0, "to": 100, "possession_home": 0.68, "press": {"home": 0.55, "away": 0.35}, "directness": {"home": 0.35, "away": 0.85}}],
     "goals": [{"t": m(34, 10), "side": "away", "passes": 3, "scorer_role": "ST", "title": "Three passes, one counter", "start_x": 25},
               {"t": m(79, 40), "side": "away", "passes": 2, "scorer_role": "RM", "title": "Second counter seals it", "start_x": 35}],
     "scripted": [{"t": m(61), "side": "home", "type": "big_chance_missed", "note": "Westvale's clearest chance goes wide"}],
     "story": "Westvale City dominate the ball, but Ashford Athletic's low block and fast counters are ruthless. Ashford win 2-0.",
     "turning_points": [{"minute": 34, "what": "First counter-attack goal", "effect": "Westvale commit more players forward, leaving space"}],
     "showcase": ["Possession ≠ control", "Claim verification", "New-fan mode"], "seed": 4404},
    {"id": "m5-controversial", "title": "The Controversial Finish", "venue": "Stonebridge Road", "subtitle": "A red card, a penalty and a stoppage-time winner.",
     "home": {"id": "stonebridge-albion", "name": "Stonebridge Albion", "short": "SBA", "colour": "#be123c", "kit_secondary": "#fff1f2", "gk_colour": "#38bdf8", "formation": "4-2-3-1", "quality": 0.58},
     "away": {"id": "port-sable", "name": "Port Sable FC", "short": "PSF", "colour": "#334155", "kit_secondary": "#f8fafc", "gk_colour": "#fb923c", "formation": "4-4-2", "quality": 0.58},
     "phases": [{"from": 0, "to": 52, "possession_home": 0.52, "press": {"home": 0.5, "away": 0.5}, "directness": {"home": 0.5, "away": 0.5}},
                {"from": 52, "to": 100, "possession_home": 0.38, "press": {"home": 0.3, "away": 0.6}, "directness": {"home": 0.75, "away": 0.45}}],
     "goals": [{"t": m(23, 30), "side": "away", "passes": 5, "scorer_role": "ST", "title": "Port Sable open the scoring"},
               {"t": m(64, 20), "side": "home", "passes": 1, "scorer_role": "CAM", "title": "Penalty, coolly converted", "penalty": True, "corner": "bottom-left"},
               {"t": m(91, 50), "side": "home", "passes": 4, "scorer_role": "ST", "title": "Ten men, stoppage-time winner", "corner": "top-left"}],
     "scripted": [{"t": m(38), "side": "away", "type": "card", "card": "yellow", "role": "CM", "note": "Late challenge in midfield"},
                  {"t": m(52), "side": "home", "type": "card", "card": "red", "role": "CB", "note": "Last-man foul: straight red"},
                  {"t": m(63, 50), "side": "away", "type": "card", "card": "yellow", "role": "CB", "note": "Penalty conceded: trip in the box"}],
     "story": "Stonebridge go down to ten men at 52' while 1-0 down, equalise from the spot and win it in stoppage time.",
     "turning_points": [{"minute": 52, "what": "Red card", "effect": "Stonebridge drop deeper and play more directly"},
                        {"minute": 64, "what": "Penalty equaliser", "effect": "Restores belief"}],
     "showcase": ["Commentary verification", "Evidence Referee", "Editorial approval"], "seed": 5505},
]


def make_commentary(pkg: dict) -> list[dict]:
    """Fictional studio commentary, including deliberately wrong claims to verify."""
    goals = pkg["ground_truth"]["goals"]
    h, a = pkg["teams"]["home"]["name"], pkg["teams"]["away"]["name"]
    if pkg["id"] == "m4-underdog":
        return [{"speaker": "Commentator A", "t_match": goals[0]["minute"] * 60 + 20,
                 "text": f"{a} have barely had a sniff, but that first goal was a lovely long move of about ten passes."},
                {"speaker": "Commentator B", "t_match": 50 * 60, "text": f"{h} have had well over sixty percent of the ball and still look short of ideas."},
                {"speaker": "Commentator A", "t_match": 80 * 60, "text": f"{a} have had more shots than {h} today, that's the story."}]
    if pkg["id"] == "m5-controversial":
        return [{"speaker": "Commentator A", "t_match": 52 * 60 + 15, "text": f"That's a red card for {h}, and they're already a goal down."},
                {"speaker": "Commentator B", "t_match": 64 * 60 + 40, "text": "The penalty goes into the top right corner, the keeper had no chance."},
                {"speaker": "Commentator A", "t_match": 92 * 60,
                 "text": f"Ten men, and {h} win it with a solo run, no passes at all, pure individual brilliance."}]
    g = goals[-1]
    return [{"speaker": "Commentator A", "t_match": g["minute"] * 60 + 10,
             "text": f"What a goal, that's a {g['build_up_passes']}-pass move finished by {g['scorer_name']}."}]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "matches"))
    out = Path(ap.parse_args().out)
    out.mkdir(parents=True, exist_ok=True)
    comm_dir = out.parent / "commentary"
    comm_dir.mkdir(parents=True, exist_ok=True)
    index = []
    for sc in SCENARIOS:
        pkg = MatchBuilder(sc, sc["seed"]).build()
        (out / f"{sc['id']}.json").write_text(json.dumps(pkg, indent=1))
        (comm_dir / f"{sc['id']}.json").write_text(json.dumps({"match_id": sc["id"], "synthetic": True, "lines": make_commentary(pkg)}, indent=1))
        index.append({"id": pkg["id"], "title": pkg["title"], "subtitle": pkg["subtitle"],
                      "home": {k: pkg["teams"]["home"][k] for k in ("id", "name", "short", "colour")},
                      "away": {k: pkg["teams"]["away"][k] for k in ("id", "name", "short", "colour")},
                      "final_score": pkg["final_score"], "showcase": pkg["showcase"], "venue": pkg["venue"],
                      "events": len(pkg["events"]), "replays": len(pkg["replays"])})
        print(f"{pkg['id']:<22} {pkg['final_score']['home']}-{pkg['final_score']['away']}  events={len(pkg['events'])} replays={len(pkg['replays'])}")
    (out / "index.json").write_text(json.dumps(index, indent=1))


if __name__ == "__main__":
    main()
