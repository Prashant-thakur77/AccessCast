"""What a person decided when reviewing one site project, read from the review app's own files (nothing typed by
hand): who-count, approvals, rejections, text edits, the time between the first and last decision, and whether the
public render carries the person's review. One reviewer on one clip: a record, not a measurement of review time
(that is E12, not run).

Writes evidence/review_<sha12>.json always, including when a check fails (passed=false). Reviewer names are counted,
never written.

Usage: python scripts/review_record.py [--project 8af59806d6b6] [--projects-dir projects/_site]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from eval.common import Experiment, run_experiment  # noqa: E402

from accesscast.project import read_json, sha256_file  # noqa: E402
from accesscast.review.store import ReviewStore  # noqa: E402

POLICY = "policy"  # the "who" of automatic routing decisions; everything else is a person
QUICK_S = 2.0  # an approval this soon after the previous decision is reported as a quick sign-off


def _ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default="8af59806d6b6")
    ap.add_argument("--projects-dir", default=str(ROOT / "projects" / "_site"))
    args = ap.parse_args()
    root = Path(args.projects_dir) / args.project
    exp = Experiment(
        f"review_{args.project}",
        "dev",
        config={
            "question": "What did a person decide when reviewing this project, and does the public render carry it?",
            "project": args.project,
            "source": "review/state.json, review/review_history.jsonl, reports/render.json (the review app's files)",
            "quick_signoff_s": QUICK_S,
        },
    )

    def body(e: Experiment) -> None:
        items = ReviewStore(root).merged()
        state = read_json(root / "review" / "state.json")["items"]
        hist = [
            json.loads(x) for x in (root / "review" / "review_history.jsonl").read_text().splitlines() if x
        ]
        by_person = [h for h in hist if h.get("who") and h["who"] != POLICY]
        last: dict[str, dict[str, Any]] = {}
        for h in hist:
            last[h["item"]] = h
        rows = []
        for iid in sorted(items):
            it, st = items[iid], state.get(iid, {})
            person = last.get(iid, {}).get("who") not in (None, POLICY)
            rows.append(
                {
                    "item": iid,
                    "kind": str(it.kind.value),
                    "status": str(it.status.value),
                    "decided_by_person": person,
                    "text": it.text,
                    "text_edited_by_person": any(
                        "final" in h.get("after", {}) for h in by_person if h["item"] == iid
                    ),
                    "seconds_on_line": st.get("review_seconds"),
                }
            )
        times = sorted(_ts(h["ts"]) for h in by_person)
        gaps = [(b - a).total_seconds() for a, b in zip(times, times[1:], strict=False)]
        render = read_json(root / "reports" / "render.json")
        files_match = all(sha256_file(root / v["file"]) == v["sha256"] for v in render["versions"].values())
        e.results = rows
        e.summary = {
            "lines": len(rows),
            "decided_by_person": sum(r["decided_by_person"] for r in rows),
            "approved_by_person": sum(r["decided_by_person"] and r["status"] == "approved" for r in rows),
            "rejected_by_person": sum(r["decided_by_person"] and r["status"] == "rejected" for r in rows),
            "text_edited_by_person": sum(r["text_edited_by_person"] for r in rows),
            "reviewers": len({h["who"] for h in by_person}),
            "decisions_by_person": len(by_person),
            "seconds_first_to_last_decision": round((times[-1] - times[0]).total_seconds())
            if times
            else None,
            "quick_signoffs": sum(1 for g in gaps if g <= QUICK_S),
            "public_render": {
                "mode": render.get("mode"),
                "watermark": render.get("watermark"),
                "human_reviewed": render.get("human_reviewed"),
                "versions": sorted(render["versions"]),
                "files_match_report": files_match,
            },
        }
        e.checks["every_line_decided_by_a_person"] = bool(rows) and all(r["decided_by_person"] for r in rows)
        e.checks["public_render_carries_the_review"] = (
            render.get("mode") == "public"
            and render.get("human_reviewed") is True
            and render.get("watermark") is False
        )
        e.checks["render_files_match_report"] = files_match

    return run_experiment(exp, body)


if __name__ == "__main__":
    raise SystemExit(main())
