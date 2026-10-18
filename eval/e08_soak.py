"""E8: does it run for hours without leaking? Dev set in a loop; VRAM every 10 s via amd-smi.

Pass = 0 failed jobs and VRAM growth ≈ 0 (last-hour median vs first-hour median within 2%). On AMD Developer
Cloud MI300X (a virtual function) utilisation, power and temperature read zero; only VRAM is live — we
record VRAM only and say why.
Usage: python -m eval.e08_soak --hours 4 [--concurrency 2]
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import threading
import time

from accesscast.config import REPO_ROOT
from accesscast.events import now_iso
from eval.common import Experiment, run_experiment
from eval.jobs import run_concurrent


def vram_used_mb() -> float | None:
    try:
        p = subprocess.run(
            ["amd-smi", "metric", "--mem-usage", "--json"], capture_output=True, text=True, timeout=15
        )
        data = json.loads(p.stdout)
        gpus = data if isinstance(data, list) else data.get("gpu_data", [data])
        total = 0.0
        for g in gpus:
            mu = g.get("mem_usage", g)
            v = mu.get("used_vram", {})
            total += float(v.get("value", 0)) if isinstance(v, dict) else float(v)
        return total
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=float, default=4.0)
    ap.add_argument("--concurrency", type=int, default=2)
    args = ap.parse_args()
    man = json.loads((REPO_ROOT / "eval" / "datasets" / "manifests" / "dev_clips.json").read_text())
    videos = [REPO_ROOT / c["file"] for c in man["clips"] if "sha256" in c]
    exp = Experiment(
        "e08_soak",
        "dev",
        config={
            "hours": args.hours,
            "concurrency": args.concurrency,
            "videos": [v.name for v in videos],
            "vram_poll_s": 10,
            "telemetry_note": "MI300X VF: util/power/temp read zero; VRAM only",
        },
    )

    def body(e: Experiment) -> None:
        samples: list[tuple[float, float]] = []
        stop = threading.Event()
        t_start = time.time()

        def poll() -> None:
            while not stop.is_set():
                v = vram_used_mb()
                if v is not None:
                    samples.append((round(time.time() - t_start, 1), v))
                stop.wait(10)

        th = threading.Thread(target=poll, daemon=True)
        th.start()
        jobs = []
        k = 0
        try:
            while time.time() - t_start < args.hours * 3600:
                for r in run_concurrent(
                    videos[k:] + videos[:k], REPO_ROOT / "projects" / "_e08" / f"batch{k}", args.concurrency
                ):
                    jobs.append(r)
                    e.results.append(
                        {
                            "t_s": round(time.time() - t_start, 1),
                            "video": r.video,
                            "ok": r.ok,
                            "wall_s": round(r.wall_s, 2),
                            "error": r.error,
                        }
                    )
                k = (k + 1) % max(1, len(videos))
        finally:
            stop.set()
            th.join(timeout=15)
        e.summary["vram_samples"] = samples
        walls = [j.wall_s for j in jobs if j.ok]
        e.summary["jobs"] = {
            "total": len(jobs),
            "ok": sum(j.ok for j in jobs),
            "failed": sum(not j.ok for j in jobs),
            "wall_p50_s": statistics.median(walls) if walls else None,
            "wall_p95_s": sorted(walls)[int(0.95 * (len(walls) - 1))] if walls else None,
        }
        e.summary["hours_run"] = round((time.time() - t_start) / 3600, 3)
        first = [v for t, v in samples if t <= 3600]
        last = [v for t, v in samples if t >= samples[-1][0] - 3600] if samples else []
        growth = (
            (statistics.median(last) - statistics.median(first)) / statistics.median(first)
            if first and last
            else None
        )
        e.summary["vram_growth_fraction"] = growth
        e.summary["finished_at"] = now_iso()
        e.checks["no_failed_jobs"] = e.summary["jobs"]["failed"] == 0
        e.checks["vram_flat"] = growth is not None and abs(growth) <= 0.02

    return run_experiment(exp, body)


if __name__ == "__main__":
    raise SystemExit(main())
