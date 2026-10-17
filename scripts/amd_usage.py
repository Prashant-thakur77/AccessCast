"""How much of AccessCast's model work ran on AMD: every Gemma call our code logged (logs/llm_calls.jsonl in each
project and evaluation), counted once (projects copied for drafts or experiments repeat their logs, so a call is
identified by time, label, seed and prompt hash).

Counts only what our logs show: requests Token Factory answered (attempts ≥ 1; a cache hit sent nothing), their
tokens as the server reported them, the videos and minutes of video those requests worked on, and the calls that
got no answer after every retry. Calls made by the public site's live attack run in the Vercel function and are not
in these logs, so the totals are a floor.

Usage: python scripts/amd_usage.py   → evidence/amd_usage.json
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from eval.common import Experiment, run_experiment  # noqa: E402

SHA12 = re.compile(r"^[0-9a-f]{12}$")


def project_of(log: Path) -> Path | None:
    for parent in log.parents:
        if SHA12.match(parent.name) and (parent / "project.json").exists():
            return parent
    return None


def main() -> int:
    exp = Experiment(
        "amd_usage",
        "none",
        config={
            "question": "How much of the model work ran on AMD Token Factory?",
            "source": "projects/**/llm_calls.jsonl (git-ignored logs; each file's call count is in results)",
            "dedupe_key": ["ts", "label", "seed", "prompt_sha"],
            "excludes": "the public site's live attack (logged server-side, not here); fake-mode calls",
        },
    )

    def body(e: Experiment) -> None:
        seen: set[tuple[object, ...]] = set()
        status: Counter[str] = Counter()
        tokens = Counter[str]()
        served: Counter[str] = Counter()
        videos: dict[str, int] = {}
        groups: dict[str, str] = {}
        days: Counter[str] = Counter()
        for log in sorted((ROOT / "projects").glob("**/llm_calls.jsonl")):
            n_new = 0
            proj = project_of(log)
            for line in log.read_text(encoding="utf-8").splitlines():
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if r.get("provider") != "tokenfactory":
                    continue
                key = (r.get("ts"), r.get("label"), r.get("seed"), r.get("prompt_sha"))
                if key in seen:
                    continue
                seen.add(key)
                n_new += 1
                answered = r.get("status") == "ok" and int(r.get("attempts") or 0) >= 1
                if answered:
                    status["answered"] += 1
                    tokens["in"] += int(r.get("tokens_in") or 0)
                    tokens["out"] += int(r.get("tokens_out") or 0)
                    served[str(r.get("served_model_id"))] += 1
                    days[str(r.get("ts", ""))[:10]] += 1
                    if proj is not None:
                        pj = json.loads((proj / "project.json").read_text())
                        videos[proj.name] = int(pj.get("duration_ms") or 0)
                        name = str(pj.get("source_name", ""))
                        groups[proj.name] = (
                            "w3c_test"
                            if name.startswith("perspectives_")
                            else "attack_clips"
                            if re.match(r"^A\d_", name)
                            else "dev_clips"
                        )
                elif r.get("status") == "ok":
                    status["cache_hit_no_request"] += 1
                elif r.get("status") == "endpoint_error":
                    status["no_answer_after_retries"] += 1
                else:
                    status[f"answered_but_{r.get('status')}"] += 1
            e.results.append({"log": str(log.relative_to(ROOT)), "new_tokenfactory_calls": n_new})
        total = tokens["in"] + tokens["out"]
        e.summary = {
            "requests_answered": status["answered"],
            "tokens_in": tokens["in"],
            "tokens_out": tokens["out"],
            "tokens_total": total,
            "served_model_ids": dict(served),
            "videos": len(videos),
            "video_minutes": round(sum(videos.values()) / 60000, 1),
            "video_groups": dict(Counter(groups.values())),
            "no_answer_after_retries": status["no_answer_after_retries"],
            "answered_but_unusable": sum(v for k, v in status.items() if k.startswith("answered_but_")),
            "cache_hits_no_request": status["cache_hit_no_request"],
            "days": dict(sorted(days.items())),
        }
        e.checks["one_served_model"] = len(served) == 1
        e.checks["some_requests"] = status["answered"] > 0

    return run_experiment(exp, body)


if __name__ == "__main__":
    raise SystemExit(main())
