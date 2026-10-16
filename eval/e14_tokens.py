"""E14 without a droplet (D-021): Gemma tokens per finished minute of video, from real runs' call logs.

No GPU dollars: Gemma 4 31B ran on AMD Token Factory, so the cost basis is tokens. Reads `logs/llm_calls.jsonl` of
every project in a projects directory, keeps only the calls of its last complete run (dev videos were run several
times while tuning), counts the answered ones (an answer replayed from the cache counts: that run needed it), and
divides by the video minutes.
Token Factory's published price per token (evidence/tokenfactory_models.json) converts tokens to its own unit,
"points", which is reported as such and never converted to dollars.

Usage: python -m eval.e14_tokens --projects projects/_dev [--split dev]
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from accesscast.config import REPO_ROOT
from eval.common import EVIDENCE, Experiment, run_experiment

# prompt id → the version it serves; evidence and scene judgments are shared by all five
VERSION_OF = {
    "evidence": "shared",
    "scene_judge": "shared",
    "write_ad": "description_en",
    "repair_ad": "description_en",
    "easy": "easy_read",
    "repair_easy": "easy_read",
    "translate_subs": "subtitles_hi_it",
    "repair_subs": "subtitles_hi_it",
    "voiceover": "voiceover_hi_it",
    "ad_translate": "description_hi_it",
}
FINAL_STAGES = ("voiceover_it", "subtitles_it", "captions_easy", "tts")


def last_run_start(root: Path) -> str | None:
    """Timestamp at which the last complete pipeline run of this project began (its ingest event), or None if
    that run did not finish every final stage. Dev videos were run several times while tuning; only the last run
    counts, so the result is the tokens one finished run needs."""
    ev = root / "logs" / "events.jsonl"
    if not ev.exists():
        return None
    events = [json.loads(line) for line in ev.read_text().splitlines() if line.strip()]
    starts = [e["ts"] for e in events if e.get("stage") == "ingest" and e.get("event") in ("start", "cached")]
    if not starts:
        return None
    t0 = starts[-1]
    done = {e["stage"] for e in events if e.get("event") == "done" and e["ts"] >= t0}
    return t0 if all(s in done for s in FINAL_STAGES) else None


def tf_price() -> tuple[float, float] | None:
    f = EVIDENCE / "tokenfactory_models.json"
    if not f.exists():
        return None
    for m in json.loads(f.read_text())["models"]:
        if m.get("id") == "Gemma-4-31B-IT":
            p = m["pricing"]
            return float(p["prompt"]), float(p["completion"])
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--projects", default="projects/_dev")
    ap.add_argument("--split", default="dev", choices=["dev"])
    args = ap.parse_args()
    base = (REPO_ROOT / args.projects).resolve()
    exp = Experiment(
        "e14_cost",
        args.split,
        config={
            "mode": "tokens (D-021: no droplet, Gemma 4 31B on AMD Token Factory)",
            "projects_dir": str(base.relative_to(REPO_ROOT)),
            "counted": "answered calls of each video's last complete run (cache replays included: that run needed them; failed calls excluded)",
            "finished_if_done": list(FINAL_STAGES),
        },
    )

    def body(e: Experiment) -> None:
        tot_in = tot_out = 0
        minutes = 0.0
        by_version: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        providers: set[str] = set()
        served: set[str] = set()
        for root in sorted(p for p in base.iterdir() if (p / "project.json").exists()):
            info = json.loads((root / "project.json").read_text())
            calls_f = root / "logs" / "llm_calls.jsonl"
            t0 = last_run_start(root)
            if t0 is None or not calls_f.exists():
                e.results.append(
                    {"video": info["source_name"], "counted": False, "reason": "last run not finished"}
                )
                continue
            vin = vout = n = 0
            for line in calls_f.read_text().splitlines():
                c: dict[str, Any] = json.loads(line)
                if c.get("status") != "ok" or c.get("ts", "") < t0:
                    continue
                n += 1
                vin += int(c.get("tokens_in") or 0)
                vout += int(c.get("tokens_out") or 0)
                v = VERSION_OF.get(c["prompt_id"].split("@")[0], "other")
                by_version[v][0] += int(c.get("tokens_in") or 0)
                by_version[v][1] += int(c.get("tokens_out") or 0)
                providers.add(str(c.get("provider")))
                served.add(str(c.get("served_model_id")))
            mins = info["duration_ms"] / 60000
            minutes += mins
            tot_in, tot_out = tot_in + vin, tot_out + vout
            e.results.append(
                {
                    "video": info["source_name"],
                    "counted": True,
                    "minutes": round(mins, 3),
                    "calls": n,
                    "tokens_in": vin,
                    "tokens_out": vout,
                }
            )
        price = tf_price()
        e.summary = {
            "videos_counted": sum(1 for r in e.results if r["counted"]),
            "videos_total": len(e.results),
            "video_minutes": round(minutes, 2),
            "tokens_in": tot_in,
            "tokens_out": tot_out,
            "tokens_per_finished_minute": round((tot_in + tot_out) / minutes) if minutes else None,
            "tokens_per_finished_minute_by_version": {
                k: round((a + b) / minutes) for k, (a, b) in sorted(by_version.items())
            }
            if minutes
            else {},
            "providers": sorted(providers),
            "served_model_ids": sorted(served),
        }
        if price and minutes:
            e.summary["tokenfactory_points_per_finished_minute"] = round(
                (tot_in * price[0] + tot_out * price[1]) / minutes, 8
            )
            e.summary["tokenfactory_price_per_token"] = {"prompt": price[0], "completion": price[1]}
        e.checks["some_finished_videos"] = bool(minutes)
        e.checks["one_provider"] = providers == {"tokenfactory"}
        e.checks["one_served_model"] = len(served) == 1

    return run_experiment(exp, body)


if __name__ == "__main__":
    raise SystemExit(main())
