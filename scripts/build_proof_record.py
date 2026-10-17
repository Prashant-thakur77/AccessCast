"""Write site/data/e11_last_run.json for the proof page from evidence/e11_adversarial.json (never invented).

Picks the case with the highest measured production failure rate (PLAN §13.5, pre-registered for E11) and copies
its production tries as recorded: what Gemma wrote, whether the case's oracle says it failed, whether the checks
blocked it, and whether anything reached the viewer. Usage: python scripts/build_proof_record.py [--site site]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from accesscast.config import REPO_ROOT


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="site")
    args = ap.parse_args()
    ev_p = REPO_ROOT / "evidence" / "e11_adversarial.json"
    ev = json.loads(ev_p.read_text())
    cases = ev["summary"]["cases"]
    rate = {c: s["production"]["gemma_failed"] / max(1, s["production"]["tries"]) for c, s in cases.items()}
    case = max(sorted(rate), key=lambda c: rate[c])
    rows = [r for r in ev["results"] if r["case"] == case and r["setting"] == "production"]
    tries = [
        {
            "try": r["try"] + 1,
            "endpoint": ev["config"].get("provider", "tokenfactory"),
            "text": r["draft"],
            "failed": bool(r["gemma_failed"]),
            "blocked_by": "AccessCast checks" if r["gemma_failed"] and not r["reached_viewer"] else None,
            "final": r.get("final"),
            "reached_viewer": bool(r["reached_viewer"]),
        }
        for r in rows
    ]
    spec = json.loads((REPO_ROOT / "data" / "adversarial" / f"{case}.json").read_text())
    said = " ".join(line[2] for line in spec.get("lines", []))
    baits = spec["baits"][:1].upper() + spec["baits"][1:]
    case_text = f'The video says "{said}" {baits}.' if said else f"{baits}."
    out = {
        "recorded_at": ev["finished_at"],
        "evidence_file": "evidence/e11_adversarial.json",
        "case_id": case,
        "case_text": case_text,
        "endpoint": "Gemma 4 31B on AMD Token Factory",
        "failure_rate_production": round(rate[case], 4),
        "tries": tries,
    }
    p = REPO_ROOT / args.site / "data" / "e11_last_run.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(f"{case}: {sum(t['failed'] for t in tries)} of {len(tries)} failed → {p}")
    _ = Path
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
