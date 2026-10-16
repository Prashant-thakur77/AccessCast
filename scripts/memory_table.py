"""Must-have #6, "what 192 GB lets us fit" (PLAN §16.1) → evidence/memory.json.

Reports what is NEEDED, not what the flags reserve: model weights from vLLM's own load log ("Model loading took
X GiB"), KV cache actually used at the E13 concurrency (peak kv-cache usage fraction × allocated KV, from
evidence/e13_serving_prefix_on.json and the "Available KV cache memory" log line), and each worker's peak
allocated memory from its synchronized stage timer. VRAM totals also come from amd-smi (utilisation, power and
temperature read zero on these virtual GPUs; only VRAM is live).
Usage (on the droplet, after `deploy/run_session.sh core`): python scripts/memory_table.py
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from eval.common import Experiment, run_experiment

from accesscast.config import REPO_ROOT

LOGS = REPO_ROOT / "logs" / "vllm"


def parse_log(p: Path) -> dict[str, float | None]:
    text = p.read_text(errors="replace") if p.exists() else ""
    w = re.findall(r"Model loading took ([\d.]+) GiB", text)
    kv = re.findall(r"Available KV cache memory: ([\d.]+) GiB", text)
    conc = re.findall(r"Maximum concurrency for (\d+) tokens per request: ([\d.]+)x", text)
    return {"weights_gib": float(w[-1]) if w else None, "kv_allocated_gib": float(kv[-1]) if kv else None,
            "max_concurrency_at_tokens": float(conc[-1][1]) if conc else None}


def amd_smi_vram() -> dict[str, float | None]:
    try:
        out = subprocess.run(["amd-smi", "metric", "--mem-usage", "--json"], capture_output=True, text=True, timeout=20).stdout
        data = json.loads(out)
        g = (data if isinstance(data, list) else data.get("gpu_data", [data]))[0]
        mu = g.get("mem_usage", g)

        def val(k: str) -> float | None:
            v = mu.get(k)
            return float(v["value"]) if isinstance(v, dict) else (float(v) if v is not None else None)

        return {"total_vram_mb": val("total_vram"), "used_vram_mb": val("used_vram")}
    except Exception:
        return {"total_vram_mb": None, "used_vram_mb": None}


def main() -> int:
    exp = Experiment("memory", "none", config={"sources": ["logs/vllm/g4-31b.log", "logs/vllm/g4-e4b.log",
                                                         "evidence/e13_serving_prefix_on.json", "projects/*/analysis/asr_meta.json",
                                                         "amd-smi"]})

    def body(e: Experiment) -> None:
        rows = {}
        for name, log in (("gemma-4-31b", "g4-31b.log"), ("gemma-4-e4b", "g4-e4b.log")):
            rows[name] = parse_log(LOGS / log)
        e13 = REPO_ROOT / "evidence" / "e13_serving_prefix_on.json"
        kv_peak = None
        if e13.exists():
            res = json.loads(e13.read_text())["results"]
            kv_peak = max((r.get("kv_cache_usage_end") or 0) for r in res) if res else None
        if rows["gemma-4-31b"]["kv_allocated_gib"] is not None and kv_peak is not None:
            rows["gemma-4-31b"]["kv_used_gib_at_e13_peak"] = round(rows["gemma-4-31b"]["kv_allocated_gib"] * kv_peak, 2)
        workers: dict[str, float] = {}
        for meta in sorted(REPO_ROOT.glob("projects/*/analysis/asr_meta.json")):
            for st, t in json.loads(meta.read_text()).get("timing", {}).items():
                if isinstance(t, dict) and t.get("peak_vram_mb"):
                    workers[f"asr:{st}"] = max(workers.get(f"asr:{st}", 0.0), float(t["peak_vram_mb"]))
        doctor = REPO_ROOT / "evidence" / "doctor.json"
        if doctor.exists():
            for role, r in json.loads(doctor.read_text()).get("deep", {}).items():
                for st, t in (r.get("timing") or {}).items() if isinstance(r, dict) else []:
                    if isinstance(t, dict) and t.get("peak_vram_mb"):
                        workers[f"{role}:{st}"] = float(t["peak_vram_mb"])
        needed = sum(v for r in rows.values() for k, v in r.items()
                     if k in ("weights_gib", "kv_used_gib_at_e13_peak") and v) + sum(workers.values()) / 1024
        e.results = [{"component": k, **v} for k, v in rows.items()] + [{"component": k, "peak_gib": round(v / 1024, 3)}
                                                                        for k, v in workers.items()]
        e.summary = {"total_needed_gib": round(needed, 2), "amd_smi": amd_smi_vram(),
                     "over_80gb": needed > 80 * 0.931,  # 80 GB = 74.5 GiB
                     "framing": "by memory accounting" if needed > 74.5 else "fits with room on one MI300X"}
        e.checks["weights_found"] = all(r["weights_gib"] for r in rows.values())

    return run_experiment(exp, body)


if __name__ == "__main__":
    raise SystemExit(main())
