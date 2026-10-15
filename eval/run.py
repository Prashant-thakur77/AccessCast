"""`make eNN` dispatcher. Arguments after the id are passed through (e.g. EXTRA="--split test")."""

from __future__ import annotations

import os
import runpy
import sys

MODULES = {
    "e01": "eval.e01_verifier_ab", "e02": "eval.e02_ladder", "e03": "eval.e01_verifier_ab",
    "e04": "eval.e04_translation", "e05": "eval.e05_easyread", "e06": "eval.e06_questions",
    "e07": "eval.e07_similarity", "e08": "eval.e08_soak", "e09": "eval.e09_determinism", "e10": "eval.e10_offline",
    "e11": "eval.e11_adversarial", "e12": "eval.e12_person_time", "e13": "eval.e13_serving", "e14": "eval.e14_cost",
    "e15": "eval.e15_asr", "e16": "eval.e16_ui_a11y",
}

if __name__ == "__main__":
    exp = sys.argv[1]
    extra = os.environ.get("EXTRA", "").split()
    if exp == "e03":  # E3 = E1's measure with another served model (set ACCESSCAST_LOCAL_MODEL first)
        extra = ["--experiment-name", f"e03_model_size_{os.environ.get('ACCESSCAST_LOCAL_MODEL', 'model')}", *extra]
    sys.argv = [MODULES[exp], *sys.argv[2:], *extra]
    runpy.run_module(MODULES[exp], run_name="__main__")
