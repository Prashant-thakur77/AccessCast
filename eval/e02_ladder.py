"""E2: how fast can one MI300X go with quality held? One optimisation per step (PLAN §15.3 ladder).

Each step is a server/worker configuration set up BEFORE running this script (deploy/serve_gemma.sh variables):
  V0 servers up, workers resident, one request at a time, vision 280 tokens, --no-enable-prefix-caching
  V1 requests in flight (semaphore 16)   V2 prefix caching   V3 vision 280 → 140   V4 VLLM_ROCM_USE_AITER=1
  V5 --kv-cache-dtype fp8                V6 MTP speculative decoding (gemma-4-31B-it-assistant)
This script times the dev set end to end for the CURRENT configuration (--step), discarding a warm-up job and
alternating clips; it records the quality guard (first-pass rate, identical words/gaps vs V0). Steps are kept in
the table even when they fail. Adoption rule (pre-registered): ≥5% faster on dev with the quality guard held.
Usage: python -m eval.e02_ladder --step V2 --change "prefix caching on" [--repeats 3]
"""

from __future__ import annotations

import argparse
import json
import statistics

from accesscast.config import REPO_ROOT
from eval.common import Experiment, run_experiment
from eval.jobs import artefact_hashes, run_job

CLIPS = (
    "nasa_GSFC_20170614_Eclipse_m12534_Plane",
    "nasa_GSFC_20180417_Worldview_m12928_Tutorial",
    "prelinger_Operator1949_2",
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--step", required=True)
    ap.add_argument("--change", required=True)
    ap.add_argument("--repeats", type=int, default=3)
    args = ap.parse_args()
    exp = Experiment(
        f"e02_ladder_{args.step}",
        "dev",
        config={"step": args.step, "change": args.change, "clips": CLIPS, "repeats": args.repeats},
    )

    def body(e: Experiment) -> None:
        videos = [REPO_ROOT / "data" / "dev" / f"{c}.mp4" for c in CLIPS]
        run_job(videos[0], REPO_ROOT / "projects" / "_e02" / args.step / "warmup")  # discarded
        per_min = []
        stage_tot: dict[str, list[float]] = {}
        first_pass = []
        hashes = {}
        for k in range(args.repeats):
            for v in videos if k % 2 == 0 else list(reversed(videos)):  # alternate order
                r = run_job(v, REPO_ROOT / "projects" / "_e02" / args.step / f"r{k}")
                e.results.append(
                    {
                        "repeat": k,
                        "video": v.name,
                        "ok": r.ok,
                        "wall_s": r.wall_s,
                        "timings": r.timings,
                        "error": r.error,
                    }
                )
                if not r.ok or not r.duration_ms or r.sha12 is None:
                    continue
                per_min.append(r.wall_s / (r.duration_ms / 60000))
                for st, t in r.timings.items():
                    stage_tot.setdefault(st, []).append(t / (r.duration_ms / 60000))
                root = REPO_ROOT / "projects" / "_e02" / args.step / f"r{k}" / r.sha12
                rows = [
                    json.loads(x)
                    for x in (root / "items" / "ad.en.jsonl").read_text().splitlines()
                    if x.strip()
                ]
                std = [x for x in rows if not x["extended"]]
                first_pass.append(
                    sum(1 for x in std if x["repair"]["attempts"] == 0 and not x["violations"])
                    / max(1, len(std))
                )
                h = artefact_hashes(root)
                hashes[v.stem] = {"words": h["words"], "gaps": h["gaps"]}
        e.summary["seconds_per_video_minute"] = {
            "median": statistics.median(per_min) if per_min else None,
            "min": min(per_min, default=None),
            "max": max(per_min, default=None),
            "n": len(per_min),
        }
        e.summary["per_stage_seconds_per_video_minute"] = {
            k: statistics.median(v) for k, v in stage_tot.items()
        }
        e.summary["quality_guard"] = {
            "first_pass_rate_median": statistics.median(first_pass) if first_pass else None,
            "words_gaps_hashes": hashes,
        }
        v0 = REPO_ROOT / "evidence" / "e02_ladder_V0.json"
        if args.step != "V0" and v0.exists():
            base = json.loads(v0.read_text())["summary"]
            same = all(base["quality_guard"]["words_gaps_hashes"].get(c) == hashes.get(c) for c in hashes)
            b = base["seconds_per_video_minute"]["median"]
            gain = (b - e.summary["seconds_per_video_minute"]["median"]) / b if b and per_min else None
            e.summary["vs_V0"] = {"gain_fraction": gain, "words_gaps_identical": same}
            e.summary["adopt"] = bool(gain is not None and gain >= 0.05 and same)
        e.checks["all_jobs_ok"] = all(r["ok"] for r in e.results)

    return run_experiment(exp, body)


if __name__ == "__main__":
    raise SystemExit(main())
