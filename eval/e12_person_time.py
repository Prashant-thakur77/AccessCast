"""E12: how much person-time does AccessCast save? Crossed design (PLAN §15.3).

Person 1 reviews AccessCast's queue on minute M1 and writes description from scratch on minute M2 (manual mode:
same tool, empty description lane, lines added by hand); person 2 does the opposite. Time = the review app's
active timer (idle > 60 s excluded), summed over description items. Also: AUROC of confidence vs "the reviewer
changed the text" (small sample; we say so). Published estimates (≈20–30 min per finished minute) are shown
separately and labelled, never mixed with these numbers.
Usage: python -m eval.e12_person_time --sessions eval/labels/e12_sessions.json
  sessions file: [{"person":"p1","condition":"review|scratch","project":"<sha12>","minute":"M1"}, ...]
"""

from __future__ import annotations

import argparse
import json

from accesscast.config import load_settings
from accesscast.project import read_json
from accesscast.review.store import ReviewStore
from eval.common import Experiment, run_experiment


def auroc(scores: list[float], labels: list[int]) -> float | None:
    pos = [s for s, y in zip(scores, labels, strict=True) if y]
    neg = [s for s, y in zip(scores, labels, strict=True) if not y]
    if not pos or not neg:
        return None
    # probability that a changed line has LOWER confidence than an unchanged one
    wins = sum((1.0 if p < n else 0.5 if p == n else 0.0) for p in pos for n in neg)
    return round(wins / (len(pos) * len(neg)), 4)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sessions", required=True)
    args = ap.parse_args()
    s = load_settings()
    sessions = json.loads(open(args.sessions).read())
    exp = Experiment("e12_person_time", "dev", config={"design": "crossed (2 people × 2 minutes × 2 conditions)",
                                                      "sessions": sessions, "timer": "active, idle > 60 s excluded"})

    def body(e: Experiment) -> None:
        per_cond: dict[str, list[float]] = {"review": [], "scratch": []}
        conf, changed = [], []
        for sess in sessions:
            root = s.projects_dir / sess["project"]
            store = ReviewStore(root)
            st = store.state()["items"]
            items = store.merged()
            ad = [i for i in items.values() if i.kind.value == "ad" and i.lang == "en"]
            secs = sum(float(st.get(i.id, {}).get("review_seconds") or 0) for i in ad)
            minutes = read_json(root / "project.json")["duration_ms"] / 60000
            rate = (secs / 60) / minutes if minutes else None
            per_cond[sess["condition"]].append(rate or 0.0)
            e.results.append({**sess, "active_seconds": round(secs, 1), "video_minutes": round(minutes, 3),
                              "person_minutes_per_finished_minute": round(rate, 3) if rate else None,
                              "lines": len(ad), "manual_lines": sum(1 for i in ad if i.source == "manual")})
            if sess["condition"] == "review":
                for i in ad:
                    if i.source == "auto" and i.confidence is not None and st.get(i.id, {}).get("reviewer"):
                        machine = i.repair.history[-1].text if i.repair.history else i.draft
                        conf.append(i.confidence)
                        changed.append(int((st[i.id].get("final") or machine) != machine))
        e.summary["review_minutes_per_finished_minute"] = (sum(per_cond["review"]) / len(per_cond["review"])
                                                          if per_cond["review"] else None)
        e.summary["scratch_minutes_per_finished_minute"] = (sum(per_cond["scratch"]) / len(per_cond["scratch"])
                                                           if per_cond["scratch"] else None)
        e.summary["confidence_auroc_changed"] = {"auroc": auroc(conf, changed), "n_items": len(conf),
                                                 "n_changed": sum(changed), "note": "small sample"}
        e.summary["published_estimate_label"] = "≈20–30 min per finished minute (published estimate, not measured here)"
        e.checks["both_conditions"] = bool(per_cond["review"]) and bool(per_cond["scratch"])

    return run_experiment(exp, body)


if __name__ == "__main__":
    raise SystemExit(main())
