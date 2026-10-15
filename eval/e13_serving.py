"""E13: how many requests can one MI300X serve? (PLAN §15.3, §16.2)

Replays REAL description and repair requests recorded on the dev set (ACCESSCAST_RECORD_REPLAY=dir during a dev
run) against the local vLLM server at concurrency 1/4/8/16/32/64. The /metrics scraping method follows ageBand's
scripts/benchmark_roster.py (Apache-2.0, https://github.com/asishbose/ageBand); changes: every concurrency level
fires the whole request set (not one request per slot), the first pass is a discarded warm-up, each level is
repeated ≥3 times (median, min, max), metrics are parsed by name and label set, and both the old
`gpu_cache_usage_perc` and newer `kv_cache_usage_perc` names are read.

Prefix cache on/off is a server setting: run once per server configuration with --label, each arm on a disjoint
request subset (CacheForge's idea), and compare the two evidence files.

Usage: python -m eval.e13_serving --replay logs/replay --label prefix_on [--levels 1,4,8,16,32,64] [--repeats 3]
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import httpx

from accesscast.config import load_settings
from eval.common import Experiment, run_experiment

METRIC_RE = re.compile(r"^([a-zA-Z_:][\w:]*)(\{[^}]*\})?\s+([-+eE\d.]+|NaN|\+Inf)$")


def scrape(base: str) -> dict[str, float]:
    r = httpx.get(base.replace("/v1", "") + "/metrics", timeout=10)
    out: dict[str, float] = {}
    for line in r.text.splitlines():
        m = METRIC_RE.match(line.strip())
        if m and not line.startswith("#"):
            name = m.group(1)
            if name.endswith(("_total", "_perc", "_running", "_waiting")) or "cache_usage" in name:
                try:
                    out[name] = out.get(name, 0.0) + float(m.group(3))
                except ValueError:
                    pass
    return out


def pct(values: list[float], q: float) -> float | None:
    if not values:
        return None
    v = sorted(values)
    return round(v[min(len(v) - 1, max(0, round(q * (len(v) - 1))))], 4)


def fire(base: str, model: str, bodies: list[dict[str, Any]], conc: int) -> dict[str, Any]:
    client = httpx.Client(timeout=600)
    lat: list[float] = []
    ok = 0

    def one(b: dict[str, Any]) -> None:
        nonlocal ok
        t0 = time.perf_counter()
        try:
            r = client.post(f"{base}/chat/completions", json={**b, "model": model})
            if r.status_code == 200:
                ok += 1
        finally:
            lat.append(time.perf_counter() - t0)

    m0 = scrape(base)
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=conc) as ex:
        list(ex.map(one, bodies))
    wall = time.perf_counter() - t0
    m1 = scrape(base)
    gen = m1.get("vllm:generation_tokens_total", 0) - m0.get("vllm:generation_tokens_total", 0)
    prompt = m1.get("vllm:prompt_tokens_total", 0) - m0.get("vllm:prompt_tokens_total", 0)
    hits = m1.get("vllm:prefix_cache_hits_total", m1.get("vllm:gpu_prefix_cache_hits_total", 0)) - \
        m0.get("vllm:prefix_cache_hits_total", m0.get("vllm:gpu_prefix_cache_hits_total", 0))
    queries = m1.get("vllm:prefix_cache_queries_total", m1.get("vllm:gpu_prefix_cache_queries_total", 0)) - \
        m0.get("vllm:prefix_cache_queries_total", m0.get("vllm:gpu_prefix_cache_queries_total", 0))
    kv = max(m1.get("vllm:kv_cache_usage_perc", 0), m1.get("vllm:gpu_cache_usage_perc", 0))
    return {"requests": len(bodies), "ok": ok, "wall_s": round(wall, 3), "p50_s": pct(lat, 0.5),
            "p95_s": pct(lat, 0.95), "gen_tokens": gen, "prompt_tokens": prompt,
            "tokens_per_s": round(gen / wall, 2) if wall else None,
            "prefix_hit_rate": round(hits / queries, 4) if queries else None, "kv_cache_usage_end": kv}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--replay", default="logs/replay")
    ap.add_argument("--label", required=True)
    ap.add_argument("--levels", default="1,4,8,16,32,64")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--subset", default="all", help="all | even | odd (disjoint sets per A/B arm)")
    args = ap.parse_args()
    s = load_settings()
    bodies: list[dict[str, Any]] = []
    for f in sorted(Path(args.replay).glob("*.jsonl")):
        if f.stem in ("write_ad", "repair_ad"):
            bodies += [json.loads(x) for x in f.read_text().splitlines() if x.strip()]
    if args.subset != "all":
        bodies = bodies[0 if args.subset == "even" else 1 :: 2]
    exp = Experiment(f"e13_serving_{args.label}", "dev", config={
        "label": args.label, "levels": args.levels, "repeats": args.repeats, "subset": args.subset,
        "requests_per_pass": len(bodies), "endpoint": s.local_base_url, "model": s.local_model,
        "gpu_hourly_cost_usd": s.gpu_hourly_cost_usd, "strict_provider": True,
        "method": "first pass discarded as warm-up; median of repeats with min/max"})

    def body(e: Experiment) -> None:
        served = httpx.get(f"{s.local_base_url}/models", timeout=10).json()["data"][0]["id"]
        e.config["served_model_id"] = served
        fire(s.local_base_url, s.local_model, bodies[: min(len(bodies), 16)], 8)  # warm-up, discarded
        levels = [int(x) for x in args.levels.split(",")]
        rows = []
        for conc in levels:
            reps = [fire(s.local_base_url, s.local_model, bodies, conc) for _ in range(args.repeats)]
            for k, r in enumerate(reps):
                e.results.append({"concurrency": conc, "repeat": k, **r})
            med = {key: statistics.median([r[key] for r in reps if r[key] is not None])
                   for key in ("wall_s", "p50_s", "p95_s", "tokens_per_s") if any(r[key] is not None for r in reps)}
            rng = {key: [min(r[key] for r in reps), max(r[key] for r in reps)] for key in med}
            lines = len(bodies)
            usd = med["wall_s"] / 3600 * s.gpu_hourly_cost_usd
            rows.append({"concurrency": conc, "median": med, "min_max": rng,
                         "success_rate": sum(r["ok"] for r in reps) / sum(r["requests"] for r in reps),
                         "usd_per_1000_lines": round(usd / lines * 1000, 4) if lines else None})
        e.summary["levels"] = rows
        best = max(rows, key=lambda r: r["median"].get("tokens_per_s") or 0)
        e.summary["best"] = {"concurrency": best["concurrency"], "tokens_per_s": best["median"].get("tokens_per_s"),
                             "p95_s": best["median"].get("p95_s"), "usd_per_1000_lines": best["usd_per_1000_lines"]}
        e.checks["all_levels_succeeded"] = all(r["success_rate"] == 1.0 for r in rows)
        e.checks["requests_available"] = len(bodies) > 0

    return run_experiment(exp, body)


if __name__ == "__main__":
    raise SystemExit(main())
