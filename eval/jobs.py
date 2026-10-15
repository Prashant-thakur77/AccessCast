"""Run complete pipeline jobs in fresh processes (for E2, E8, E9, E14 and the users-per-GPU sweep)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from accesscast.config import REPO_ROOT
from accesscast.project import sha256_file

JOB_SCRIPT = r"""
import json, sys, time
from pathlib import Path
from accesscast.config import load_settings
from accesscast.pipeline import run_all
from accesscast.render_stage import render_all, package
t0 = time.perf_counter()
s = load_settings()
r = run_all(s, Path(sys.argv[1]), strict=True, require_rocm=sys.argv[2] == "1")
analysis_s = time.perf_counter() - t0
summary = render_all(r, mode="draft")
package(r)
print(json.dumps({"sha12": r.project.sha12, "wall_s": time.perf_counter() - t0, "timings": r.timings,
                  "render_ok": all(v["ok"] for v in summary["versions"].values()), "duration_ms": r.info.duration_ms}))
"""


@dataclass
class JobResult:
    video: str
    ok: bool
    wall_s: float
    duration_ms: int | None
    sha12: str | None
    timings: dict[str, float]
    error: str | None


def run_job(video: Path, projects_dir: Path, *, require_rocm: bool = True, env: dict[str, str] | None = None,
            timeout_s: float = 7200) -> JobResult:
    projects_dir.mkdir(parents=True, exist_ok=True)
    e = {**os.environ, "ACCESSCAST_PROJECTS_DIR": str(projects_dir), "ACCESSCAST_REVIEW_POLICY": "prototype-auto",
         **(env or {})}
    t0 = time.perf_counter()
    p = subprocess.run([sys.executable, "-c", JOB_SCRIPT, str(video), "1" if require_rocm else "0"], cwd=REPO_ROOT,
                       env=e, capture_output=True, text=True, timeout=timeout_s, check=False)
    wall = time.perf_counter() - t0
    if p.returncode != 0:
        return JobResult(video.name, False, wall, None, None, {}, p.stderr.strip()[-600:])
    out = json.loads(p.stdout.strip().splitlines()[-1])
    return JobResult(video.name, bool(out["render_ok"]), wall, out["duration_ms"], out["sha12"], out["timings"], None)


def run_concurrent(videos: list[Path], base: Path, n: int, **kw: Any) -> list[JobResult]:
    """n jobs at once, each in its own projects dir so nothing is shared through the cache."""
    with ThreadPoolExecutor(max_workers=n) as ex:
        futs = [ex.submit(run_job, videos[i % len(videos)], base / f"job{i}", **kw) for i in range(n)]
        return [f.result() for f in futs]


ARTEFACTS = {
    "words": "analysis/words.json", "gaps": "analysis/gaps.json", "scenes": "analysis/scenes.json",
    "sounds": "analysis/sounds.json", "ad_drafts": "items/ad.en.jsonl", "sdh": "items/sdh.en.jsonl",
    "easy": "items/easy.en.jsonl", "subs_hi": "items/subs.hi.jsonl", "subs_it": "items/subs.it.jsonl",
}


def artefact_hashes(project_root: Path) -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    for k, rel in ARTEFACTS.items():
        f = project_root / rel
        out[k] = sha256_file(f) if f.exists() else None
    for f in sorted((project_root / "evidence").glob("*/evidence.json")):
        out[f"evidence/{f.parent.name}"] = sha256_file(f)
    for f in sorted((project_root / "render").glob("*.desc_stem.wav")):
        out[f"stem/{f.name}"] = sha256_file(f)
    return out


def ad_texts(project_root: Path) -> dict[str, str]:
    f = project_root / "items" / "ad.en.jsonl"
    if not f.exists():
        return {}
    rows = [json.loads(x) for x in f.read_text().splitlines() if x.strip()]
    return {r["id"]: (r.get("final") or r["draft"]) for r in rows}
