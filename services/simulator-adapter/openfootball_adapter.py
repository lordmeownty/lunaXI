"""Open Football → Luna XI adapter (build-time only).
  export-db : write Luna XI fictional clubs/players (never the default real-world database)
  convert   : turn an Open Football match export into a full Luna XI package (adds coordinates + replays)"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "data" / "generator"))
from generate_matches import SCENARIOS, MatchBuilder  # noqa: E402

MANIFEST = json.loads((Path(__file__).parent / "integration.json").read_text())
FIELD_MAP = {"events": "events", "minute": "minute", "second": "second", "type": "type", "team": "team_id", "home_team": "home_team_id"}
TYPE_MAP = {"goal": "goal", "Goal": "goal", "yellow_card": "yellow", "red_card": "red", "substitution": "substitution"}


def build_fictional_db(out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    clubs = []
    for sc in SCENARIOS:
        b = MatchBuilder(sc, sc["seed"])
        for t in (b.home, b.away):
            clubs.append({"id": t.id, "name": t.name, "short": t.short, "formation": t.formation, "synthetic": True,
                          "players": [{"id": p.id, "name": p.name, "position": p.role, "attributes": p.attributes} for p in t.players + t.bench]})
    path = out_dir / "luna_fictional_clubs.json"
    path.write_text(json.dumps({"source": "Luna XI fictional dataset", "synthetic": True, "clubs": clubs}, indent=1))
    return path


def scenario_from_openfootball(of_match: dict, base: dict) -> dict:
    fm, home_id = FIELD_MAP, of_match.get(FIELD_MAP["home_team"])
    goals, scripted = [], []
    for e in of_match.get(fm["events"], []):
        kind = TYPE_MAP.get(str(e.get(fm["type"])))
        if not kind:
            continue
        t = float(e.get(fm["minute"], 0)) * 60 + float(e.get(fm["second"], 0) or 0)
        side = "home" if e.get(fm["team"]) == home_id else "away"
        if kind == "goal":
            goals.append({"t": t, "side": side, "passes": int(e.get("build_up_passes", 4) or 4), "scorer_role": "ST", "title": e.get("description") or "Goal"})
        elif kind in ("yellow", "red"):
            scripted.append({"t": t, "side": side, "type": "card", "card": kind, "role": "CM", "note": "Card (Open Football)"})
        else:
            scripted.append({"t": t, "side": side, "type": "substitution", "off_role": "CM", "on_role": "CM", "note": "Substitution (Open Football)"})
    return dict(base) | {"goals": goals or base["goals"], "scripted": scripted or base.get("scripted", [])}


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("export-db")
    conv = sub.add_parser("convert")
    conv.add_argument("--of-json", required=True)
    conv.add_argument("--scenario", required=True, choices=[s["id"] for s in SCENARIOS])
    conv.add_argument("--out", default=None)
    a = ap.parse_args()
    if a.cmd == "export-db":
        print(build_fictional_db(ROOT / "services" / "simulator-adapter" / "out"))
        return
    base = next(s for s in SCENARIOS if s["id"] == a.scenario)
    pkg = MatchBuilder(scenario_from_openfootball(json.loads(Path(a.of_json).read_text()), base), base["seed"]).build()
    pkg["provenance"]["simulation_engine"] = f"Open Football {MANIFEST['release']} ({MANIFEST['revision'][:7]}, Apache-2.0) with Luna XI fictional data"
    out = Path(a.out) if a.out else ROOT / "data" / "matches" / f"{a.scenario}.json"
    out.write_text(json.dumps(pkg, indent=1))
    print(f"wrote {out} final={pkg['final_score']}")


if __name__ == "__main__":
    main()
