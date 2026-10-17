"""Estimate the Gemma cost of one finished minute in dollars: measured tokens (E14) × a published list price.

An estimate, labelled as such wherever it is used: the token counts are measured (evidence/e14_cost.json, dev set,
all five versions); the price is a cited list price for Gemma 4 31B (evidence/cited_claims.json), not what AMD Token
Factory charges (it bills in points) and not money we paid. Usage: python scripts/cost_estimate.py
"""

from __future__ import annotations

import json

from eval.common import EVIDENCE, Experiment, run_experiment


def main() -> int:
    e14 = json.loads((EVIDENCE / "e14_cost.json").read_text())["summary"]
    cited = {c["claim_id"]: c for c in json.loads((EVIDENCE / "cited_claims.json").read_text())["verified"]}
    p_in = float(cited["cited.price.gemma4_31b_input_per_m"]["value"])
    p_out = float(cited["cited.price.gemma4_31b_output_per_m"]["value"])
    exp = Experiment(
        "cost_estimate",
        "dev",
        config={
            "tokens_from": "evidence/e14_cost.json",
            "price_from": ["cited.price.gemma4_31b_input_per_m", "cited.price.gemma4_31b_output_per_m"],
            "kind": "estimate at a published list price",
        },
    )

    def body(e: Experiment) -> None:
        mins = float(e14["video_minutes"])
        usd = (e14["tokens_in"] * p_in + e14["tokens_out"] * p_out) / 1e6 / mins
        e.summary = {
            "usd_per_finished_minute_gemma": round(usd, 5),
            "usd_per_hour_of_video_gemma": round(usd * 60, 3),
            "tokens_in_per_minute": round(e14["tokens_in"] / mins),
            "tokens_out_per_minute": round(e14["tokens_out"] / mins),
        }
        e.checks["inputs_present"] = mins > 0

    return run_experiment(exp, body)


if __name__ == "__main__":
    raise SystemExit(main())
