"""How much room for standard description the test videos leave: pauses ≥ MIN_GAP_MS after the guard band.

Descriptive only (counts and seconds from each test project's gap map; no model output is read). Written after E1
to explain why E1 planned so few lines; it changes nothing in the pipeline.
Usage: python scripts/test_gap_census.py
"""

from __future__ import annotations

import json

from eval.common import Experiment, run_experiment

from accesscast import constants as C
from accesscast.config import load_settings


def main() -> int:
    s = load_settings()
    exp = Experiment(
        "e01_test_gap_census", "test", config={"guard_ms": C.GUARD_MS, "min_gap_ms": C.MIN_GAP_MS}
    )

    def body(e: Experiment) -> None:
        tot_s = gap_s = 0.0
        n_gaps = 0
        for f in sorted(s.projects_dir.glob("*/project.json")):
            info = json.loads(f.read_text())
            if not info["source_name"].startswith("perspectives_"):
                continue
            gaps = json.loads((f.parent / "analysis" / "gaps.json").read_text())["gaps"]
            secs = sum(g["end_ms"] - g["start_ms"] for g in gaps) / 1000
            e.results.append(
                {
                    "video": info["source_name"],
                    "seconds": round(info["duration_ms"] / 1000, 1),
                    "pauses": len(gaps),
                    "pause_seconds": round(secs, 1),
                }
            )
            tot_s += info["duration_ms"] / 1000
            gap_s += secs
            n_gaps += len(gaps)
        e.summary = {
            "videos": len(e.results),
            "video_minutes": round(tot_s / 60, 1),
            "pauses": n_gaps,
            "pause_seconds": round(gap_s, 1),
            "pause_share": round(gap_s / tot_s, 4) if tot_s else None,
            "videos_with_no_pause": sum(1 for r in e.results if r["pauses"] == 0),
        }
        e.checks["all_ten_videos"] = len(e.results) == 10

    return run_experiment(exp, body)


if __name__ == "__main__":
    raise SystemExit(main())
