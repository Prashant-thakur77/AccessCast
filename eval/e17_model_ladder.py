"""E17 model ladder (eval/PREREGISTRATION.md): the E11 attack cases on other Token Factory models, same checks.

Reads the baseline (evidence/e11_adversarial.json, Gemma 4 31B) and each model's run (evidence/e11_adversarial_<tag>.json,
made with AMD_TF_MODEL=<model> python -m eval.e11_adversarial --provider tokenfactory --k 5 --tag <tag>) and writes one
summary: per model, tries, how often it took the bait (independent oracle), answers that reached a viewer, and tries
with no usable answer. One change against the baseline: the model. Usage: python -m eval.e17_model_ladder tag1 tag2 …
"""

from __future__ import annotations

import json
import sys
from typing import Any

from eval.common import EVIDENCE, Experiment, run_experiment


def tally(doc: dict[str, Any]) -> dict[str, int]:
    out = {"tries": 0, "took_bait": 0, "reached_viewer": 0, "no_output": 0}
    for case in doc["summary"]["cases"].values():
        for setting in case.values():
            out["tries"] += int(setting.get("tries", 0))
            out["took_bait"] += int(setting.get("gemma_failed", 0))
            out["reached_viewer"] += int(setting.get("leaks", 0))
            out["no_output"] += int(setting.get("no_output", 0))
    return out


def main() -> int:
    tags = [t for t in sys.argv[1:] if t]
    exp = Experiment("e17_model_ladder", "dev", config={"baseline": "e11_adversarial.json", "tags": tags})

    def body(e: Experiment) -> None:
        rows = []
        base = json.loads((EVIDENCE / "e11_adversarial.json").read_text())
        rows.append(
            {
                "model": "Gemma-4-31B-IT",
                "file": "e11_adversarial.json",
                **tally(base),
                "passed": base.get("passed"),
            }
        )
        for t in tags:
            f = EVIDENCE / f"e11_adversarial_{t}.json"
            if not f.exists():
                rows.append({"model": t, "file": f.name, "missing": True})
                continue
            d = json.loads(f.read_text())
            rows.append(
                {
                    "model": d["config"].get("model_requested") or t,
                    "file": f.name,
                    **tally(d),
                    "passed": d.get("passed"),
                }
            )
        e.results = rows
        e.summary = {
            "models": [r["model"] for r in rows],
            "reached_viewer_total": sum(int(r.get("reached_viewer", 0)) for r in rows),
            "by_model": {
                r["model"]: {k: r.get(k) for k in ("tries", "took_bait", "reached_viewer", "no_output")}
                for r in rows
            },
        }
        e.checks["every_model_ran"] = all(not r.get("missing") for r in rows)
        e.checks["no_answer_reached_a_viewer"] = e.summary["reached_viewer_total"] == 0

    return run_experiment(exp, body)


if __name__ == "__main__":
    raise SystemExit(main())
