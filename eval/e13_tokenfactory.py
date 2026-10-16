"""E13 without a droplet (D-021): Gemma 4 31B on AMD Token Factory, measured from our side of the connection.

Replays REAL text-only requests recorded during dev runs (ACCESSCAST_RECORD_REPLAY, written by scripts/dev_local.sh)
at a few concurrency levels within our key's limits (AMD_TF_MAX_CONCURRENCY, AMD_TF_RPM). Everything here is
client-side: latency includes the network and Token Factory's queue, and generated tokens come from each
response's `usage`. Errors are counted, never retried, because the error rate is part of the result.
Each level: a discarded warm-up, then at least 3 repeats (median, min, max). Strict: every 200 response must name
the requested model. Never uses the answer cache.

Usage: python -m eval.e13_tokenfactory [--replay logs/replay_tf] [--levels 1,4] [--repeats 3] [--per-level 20]
"""

from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import httpx

from accesscast.config import REPO_ROOT, load_settings
from eval.common import Experiment, run_experiment

MODEL = "Gemma-4-31B-IT"


def pct(values: list[float], q: float) -> float | None:
    if not values:
        return None
    v = sorted(values)
    return round(v[min(len(v) - 1, int(q * len(v)))], 3)


def fire(base: str, key: str, bodies: list[dict[str, Any]], conc: int, rpm: int) -> dict[str, Any]:
    client = httpx.Client(timeout=600)
    lat: list[float] = []
    gen: list[int] = []
    errors: dict[str, int] = {}
    served: set[str] = set()
    gap = 60.0 / rpm if rpm else 0.0
    start = time.perf_counter()

    def one(k_b: tuple[int, dict[str, Any]]) -> None:
        k, b = k_b
        wait = start + k * gap - time.perf_counter()  # stay inside the key's requests-per-minute limit
        if wait > 0:
            time.sleep(wait)
        t0 = time.perf_counter()
        try:
            r = client.post(
                f"{base.rstrip('/')}/chat/completions",
                json={**b, "model": MODEL},
                headers={"Authorization": f"Bearer {key}"},
            )
        except httpx.HTTPError as e:
            errors[type(e).__name__] = errors.get(type(e).__name__, 0) + 1
            return
        if r.status_code != 200:
            errors[str(r.status_code)] = errors.get(str(r.status_code), 0) + 1
            return
        d = r.json()
        served.add(str(d.get("model")))
        lat.append(time.perf_counter() - t0)
        gen.append(int((d.get("usage") or {}).get("completion_tokens", 0)))

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=conc) as ex:
        list(ex.map(one, enumerate(bodies)))
    wall = time.perf_counter() - t0
    return {
        "requests": len(bodies),
        "ok": len(lat),
        "errors": errors,
        "wall_s": round(wall, 3),
        "p50_s": pct(lat, 0.5),
        "p95_s": pct(lat, 0.95),
        "gen_tokens": sum(gen),
        "tokens_per_s": round(sum(gen) / wall, 2) if wall and lat else None,
        "served": sorted(served),
    }


def main() -> int:
    os.environ.pop("ACCESSCAST_LLM_CACHE", None)
    ap = argparse.ArgumentParser()
    ap.add_argument("--replay", default="logs/replay_tf")
    ap.add_argument("--levels", default="1,4")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--per-level", type=int, default=20)
    args = ap.parse_args()
    s = load_settings()
    bodies: list[dict[str, Any]] = []
    for f in sorted((REPO_ROOT / args.replay).glob("*.jsonl")):
        bodies += [json.loads(line) for line in f.read_text(encoding="utf-8").splitlines() if line.strip()]
    random.Random(20261018).shuffle(bodies)
    levels = [int(x) for x in args.levels.split(",")]
    exp = Experiment(
        "e13_serving_tokenfactory",
        "dev",
        config={
            "provider": "tokenfactory",
            "model": MODEL,
            "measured": "client-side (network and provider queue included)",
            "levels": levels,
            "repeats": args.repeats,
            "per_level": args.per_level,
            "rpm_limit": s.tf_rpm,
            "max_concurrency": s.tf_max_concurrency,
            "replay_requests": len(bodies),
            "strict_provider": True,
        },
    )

    def body(e: Experiment) -> None:
        if not bodies:
            raise RuntimeError(f"no recorded requests in {args.replay}")
        n = args.per_level
        fire(s.tf_base_url, s.tf_api_key, bodies[:4], 1, s.tf_rpm)  # warm-up, discarded
        rows = []
        for conc in levels:
            if conc > s.tf_max_concurrency:
                continue
            reps = []
            for r in range(args.repeats):
                chunk = [bodies[(r * n + i) % len(bodies)] for i in range(n)]
                reps.append(fire(s.tf_base_url, s.tf_api_key, chunk, conc, s.tf_rpm))
            good = [x for x in reps if x["tokens_per_s"] is not None]

            def med(k: str, rs: list[dict[str, Any]] = good) -> float | None:
                vals = [x[k] for x in rs if x[k] is not None]
                return round(statistics.median(vals), 3) if vals else None

            rows.append(
                {
                    "concurrency": conc,
                    "repeats": reps,
                    "tokens_per_s": med("tokens_per_s"),
                    "p95_s": med("p95_s"),
                    "p50_s": med("p50_s"),
                    "tokens_per_s_min": min((x["tokens_per_s"] for x in good), default=None),
                    "tokens_per_s_max": max((x["tokens_per_s"] for x in good), default=None),
                    "requests": sum(x["requests"] for x in reps),
                    "ok": sum(x["ok"] for x in reps),
                }
            )
        e.results = rows
        scored = [r for r in rows if r["tokens_per_s"] is not None]
        best = max(scored, key=lambda r: r["tokens_per_s"]) if scored else None
        total = sum(r["requests"] for r in rows)
        ok = sum(r["ok"] for r in rows)
        served = {m for r in rows for x in r["repeats"] for m in x["served"]}
        e.summary = {
            "best": {k: best[k] for k in ("concurrency", "tokens_per_s", "p95_s", "p50_s")} if best else None,
            "requests": total,
            "ok": ok,
            "failed": total - ok,
            "served_model_ids": sorted(served),
        }
        e.checks["measured"] = best is not None
        e.checks["strict_provider"] = all(m.split("/")[-1].lower() == MODEL.lower() for m in served)

    return run_experiment(exp, body)


if __name__ == "__main__":
    raise SystemExit(main())
