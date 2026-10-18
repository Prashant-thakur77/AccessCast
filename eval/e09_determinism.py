"""E9: same input, same output? 5 fresh-process runs on 2 dev clips, separate project dirs (no cache sharing).

Reports, per artefact, how many runs match run 1 byte-for-byte, and how many description lines differ. The claim
is worded exactly as measured (we measure, not assume).
Usage: python -m eval.e09_determinism [--runs 5] [--clips nasa_GSFC_...,fixture20]
"""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path

import numpy as np
import soundfile as sf

from accesscast.config import REPO_ROOT
from eval.common import Experiment, run_experiment
from eval.jobs import ad_texts, artefact_hashes, run_job

WORK = REPO_ROOT / "projects" / "_e09"


def clip_path(cid: str) -> Path:
    if cid == "fixture20":
        return REPO_ROOT / "tests" / "fixtures" / "fixture20" / "source.mp4"
    return REPO_ROOT / "data" / "dev" / f"{cid}.mp4"


def main() -> int:
    os.environ.pop(
        "ACCESSCAST_LLM_CACHE", None
    )  # this experiment measures repeated live calls: never a cache
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument(
        "--clips",
        default="nasa_GSFC_20170614_Eclipse_m12534_Plane,nasa_GSFC_20180417_Worldview_m12928_Tutorial",
    )
    ap.add_argument("--no-rocm", action="store_true")
    args = ap.parse_args()
    exp = Experiment(
        "e09_determinism",
        "dev",
        config={
            "runs": args.runs,
            "clips": args.clips,
            "fresh_process_per_run": True,
            "separate_project_dirs": True,
            "provider": os.environ.get("ACCESSCAST_PROVIDER", "local"),
            "llm_cache": "off",
            "sound_model": os.environ.get("ACCESSCAST_SOUND_MODEL", "gemma"),
            "audio_model": os.environ.get("ACCESSCAST_AUDIO_MODEL", "gemma-4-e4b"),
        },
    )

    def body(e: Experiment) -> None:
        shutil.rmtree(WORK, ignore_errors=True)
        all_identical = True
        for cid in args.clips.split(","):
            runs = []
            for k in range(args.runs):
                r = run_job(clip_path(cid), WORK / cid / f"run{k}", require_rocm=not args.no_rocm)
                if not r.ok or r.sha12 is None:
                    e.results.append({"clip": cid, "run": k, "ok": False, "error": r.error})
                    continue
                root = WORK / cid / f"run{k}" / r.sha12
                runs.append(
                    {"hashes": artefact_hashes(root), "ad": ad_texts(root), "wall_s": r.wall_s, "root": root}
                )
            if not runs:
                all_identical = False
                continue
            ref = runs[0]
            per_art = {}
            for art in ref["hashes"]:
                same = sum(1 for x in runs if x["hashes"].get(art) == ref["hashes"][art])
                per_art[art] = f"{same}/{len(runs)}"
                all_identical &= same == len(runs)
            stem_diff_db = {}
            for stem in sorted(ref["root"].glob("render/*.desc_stem.wav")):
                worst = 0.0
                for x in runs[1:]:
                    other = x["root"] / "render" / stem.name
                    if other.exists():
                        a, _ = sf.read(str(stem), dtype="float64")
                        b, _ = sf.read(str(other), dtype="float64")
                        n = min(len(a), len(b))
                        worst = max(worst, float(np.abs(a[:n] - b[:n]).max()) if n else 0.0)
                stem_diff_db[stem.name] = None if worst == 0 else round(20 * np.log10(worst), 1)
            diff_lines = [sum(1 for i, t in x["ad"].items() if ref["ad"].get(i) != t) for x in runs[1:]]
            e.summary.setdefault("clips", {})[cid] = {
                "runs_ok": len(runs),
                "identical_to_run1": per_art,
                "description_lines": len(ref["ad"]),
                "differing_description_lines_per_run": diff_lines,
                "stem_max_sample_difference_dbfs": stem_diff_db,
            }
        e.summary["all_artefacts_identical"] = all_identical
        e.checks["all_runs_completed"] = all(not r.get("error") for r in e.results)
        e.checks["identical"] = all_identical  # a negative result is published as measured

    return run_experiment(exp, body)


if __name__ == "__main__":
    raise SystemExit(main())
