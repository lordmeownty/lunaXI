"""Luna XI evaluation: routing, ground truth, replays, spoiler protection, role gating, safety and referee.
--inprocess (no server) or --api URL. The JSONL also uploads as a Microsoft Foundry evaluation dataset."""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def client(args):
    if args.inprocess:
        os.environ.setdefault("AUTH_MODE", "demo")
        sys.path.insert(0, str(ROOT / "backend"))
        from fastapi.testclient import TestClient
        from app.main import app
        c = TestClient(app)
        return lambda p, body=None, role="Luna.Analyst": (c.post(p, json=body, headers={"X-Demo-Role": role}) if body is not None else c.get(p, headers={"X-Demo-Role": role})).json()
    import httpx
    base = args.api.rstrip("/")
    return lambda p, body=None, role="Luna.Analyst": (httpx.post(base + p, json=body, headers={"X-Demo-Role": role}, timeout=120) if body is not None
                                                      else httpx.get(base + p, headers={"X-Demo-Role": role}, timeout=60)).json()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--inprocess", action="store_true")
    ap.add_argument("--min-pass-rate", type=float, default=0.0)
    ap.add_argument("--out", default=str(ROOT / "evaluation" / "report.json"))
    args = ap.parse_args()
    call = client(args)
    cases = [json.loads(l) for l in (ROOT / "evaluation" / "dataset.jsonl").read_text().splitlines() if l.strip()]
    gts, rows = {}, []
    for c in cases:
        gt = gts.setdefault(c["match_id"], call(f"/api/matches/{c['match_id']}"))
        t0 = time.perf_counter()
        r = call("/api/ask", {"match_id": c["match_id"], "question": c["question"], "playback_t": c.get("playback_t")}, c.get("role", "Luna.Analyst"))
        ms = int((time.perf_counter() - t0) * 1000)
        ans = r.get("answer") or ""
        chk = {"route": r["tier"] in c["expect_tier"]}
        if "expect_contains" in c:
            chk["content"] = all(s.lower() in ans.lower() for s in c["expect_contains"])
        if "expect_contains_gt" in c:
            chk["content"] = gt["goals"][int(c["expect_contains_gt"].split(":")[1]) - 1]["scorer_name"] in ans
        if "expect_action_goal" in c:
            chk["replay"] = bool(r.get("action")) and r["action"].get("goal_number") == c["expect_action_goal"]
        if "expect_view" in c:
            chk["view"] = bool(r.get("action")) and r["action"].get("view") == c["expect_view"]
        if c.get("expect_no_action"):
            chk["spoiler_protection"] = r.get("action") is None
        if c.get("expect_verified"):
            chk["referee"] = r.get("verification", {}).get("verdict") == "approved"
        rows.append({"id": c["id"], "tier": r["tier"], "ok": all(chk.values()), "checks": chk, "ms": ms, "engine": r["trace"].get("engine")})
        print(f"{'PASS' if all(chk.values()) else 'FAIL'} {c['id']:<6} {r['tier']:<8} {ms:>5}ms {chk}")
    ref = [r["checks"]["referee"] for r in rows if "referee" in r["checks"]]
    report = {"cases": len(rows), "pass_rate": round(sum(r["ok"] for r in rows) / len(rows), 3),
              "routing_accuracy": round(sum(r["checks"]["route"] for r in rows) / len(rows), 3),
              "referee_approval_rate": round(sum(ref) / len(ref), 3) if ref else None, "p50_ms": statistics.median(r["ms"] for r in rows),
              "engine": rows[0]["engine"], "rows": rows}
    Path(args.out).write_text(json.dumps(report, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}, indent=2))
    if report["pass_rate"] < args.min_pass_rate:
        sys.exit(1)


if __name__ == "__main__":
    main()
