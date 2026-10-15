"""E14: cost per experience, and users per GPU (PLAN §16.2, §16.3).

Users per GPU (fixed before measuring): the largest number of simultaneous video jobs for which EVERY job finishes
in no more time than its video lasts (≤ 1× real time), trying 1, 2, 4, 8, … jobs on dev clips. Reported as a lower
bound if the next step fails.
Cost: a batch of M video-minutes at the chosen concurrency; the droplet bills by the hour whatever it does, so
wall time T is the basis. Bundle cost per finished minute = (T / 3600 × $/h) / M. Per-version split uses per-stage
time. Review time (E12) is shown next to it, never converted to dollars without a sourced hourly rate.
Usage: python -m eval.e14_cost [--max-jobs 16] [--batch-concurrency 4]
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict

from accesscast.config import REPO_ROOT, load_settings
from eval.common import Experiment, run_experiment
from eval.jobs import run_concurrent

SHARED = ("asr", "shots", "scenes", "asr_crosscheck", "sounds", "gaps", "evidence")
VERSION_STAGES = {"description_en": ("plan", "write", "verify_repair", "tts"), "sdh": ("captions_sdh",),
                  "easy_read": ("captions_easy",), "hindi": ("subtitles_hi", "voiceover_hi"),
                  "italian": ("subtitles_it", "voiceover_it")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-jobs", type=int, default=16)
    ap.add_argument("--batch-concurrency", type=int, default=0, help="0 = use the users-per-GPU result")
    ap.add_argument("--split", default="dev", choices=["dev", "test"])
    args = ap.parse_args()
    s = load_settings()
    man = json.loads((REPO_ROOT / "eval" / "datasets" / "manifests" / "dev_clips.json").read_text())
    videos = [REPO_ROOT / c["file"] for c in man["clips"] if "sha256" in c and "blender" not in c["clip"]]
    exp = Experiment("e14_cost", args.split, config={"gpu_hourly_cost_usd": s.gpu_hourly_cost_usd,
                                                     "videos": [v.name for v in videos],
                                                     "users_definition": "largest N with every job ≤ 1× real time"})

    def body(e: Experiment) -> None:
        n, best = 1, 0
        sweep = []
        while n <= args.max_jobs:
            res = run_concurrent(videos, REPO_ROOT / "projects" / "_e14" / f"n{n}", n)
            rtf = [r.wall_s / (r.duration_ms / 1000) for r in res if r.ok and r.duration_ms]
            ok = len(rtf) == n and max(rtf) <= 1.0
            sweep.append({"jobs": n, "all_ok": all(r.ok for r in res), "max_rtf": max(rtf) if rtf else None,
                          "median_rtf": sorted(rtf)[len(rtf) // 2] if rtf else None})
            if not ok:
                break
            best = n
            n *= 2
        e.summary["users_per_gpu_sweep"] = sweep
        e.summary["users_per_gpu"] = best
        e.summary["users_per_gpu_is_lower_bound"] = n <= args.max_jobs
        conc = args.batch_concurrency or max(1, best)
        import time

        t0 = time.perf_counter()
        res = run_concurrent(videos, REPO_ROOT / "projects" / "_e14" / "batch", len(videos) if conc >= len(videos) else conc)
        wall = time.perf_counter() - t0
        minutes = sum((r.duration_ms or 0) for r in res if r.ok) / 60000
        stage_s: dict[str, float] = defaultdict(float)
        for r in res:
            for k, v in r.timings.items():
                stage_s[k] += v
        total_stage = sum(stage_s.values()) or 1.0
        bundle = (wall / 3600 * s.gpu_hourly_cost_usd) / minutes if minutes else None
        split = {"shared_analysis": sum(stage_s[k] for k in SHARED) / total_stage}
        for ver, stages in VERSION_STAGES.items():
            split[ver] = sum(stage_s[k] for k in stages) / total_stage
        e.summary["batch"] = {"jobs": len(res), "ok": sum(r.ok for r in res), "video_minutes": round(minutes, 3),
                              "wall_s": round(wall, 2), "concurrency": conc,
                              "bundle_usd_per_finished_minute": round(bundle, 5) if bundle else None,
                              "share_of_stage_time": {k: round(v, 4) for k, v in split.items()},
                              "per_version_usd_per_minute": {k: round(bundle * v, 6) for k, v in split.items()} if bundle else None}
        e12 = REPO_ROOT / "evidence" / "e12_person_time.json"
        e.summary["review_minutes_per_finished_minute"] = json.loads(e12.read_text())["summary"].get(
            "review_minutes_per_finished_minute") if e12.exists() else None
        e.checks["batch_all_ok"] = all(r.ok for r in res)
        e.checks["users_measured"] = best >= 1

    return run_experiment(exp, body)


if __name__ == "__main__":
    raise SystemExit(main())
