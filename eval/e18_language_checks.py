"""E18: how each language's subtitles and voice-over fare against our checks, across the site's draft projects (dev).

For every project and language: lines made, lines that passed every check on their own (ready for a person), lines held
for a person (a check still fails after repair), and which rules held them. Nothing here is a quality score of the
translation itself (E4 is); it measures how often the checks let a line through, per language.

Usage: ACCESSCAST_PROJECTS_DIR=projects/_site python -m eval.e18_language_checks cbf141ec3213 dac08bcd9d7a
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path

from accesscast import constants as C
from accesscast.config import REPO_ROOT
from eval.common import Experiment, run_experiment

HELD = {"needs_revision"}
PASSED = {"pending", "approved", "auto_approved"}


def main() -> int:
    ids = [a for a in sys.argv[1:] if a]
    root = Path(os.environ.get("ACCESSCAST_PROJECTS_DIR", REPO_ROOT / "projects"))
    exp = Experiment(
        "e18_language_checks", "dev", config={"projects": ids, "languages": list(C.TRANSLATION_LANGS)}
    )

    def body(e: Experiment) -> None:
        by_lang: dict[str, dict[str, object]] = {}
        for lang in C.TRANSLATION_LANGS:
            made = passed = held = 0
            rules: Counter[str] = Counter()
            for pid in ids:
                for kind in ("subs", "vo"):
                    f = root / pid / "items" / f"{kind}.{lang}.jsonl"
                    if not f.exists():
                        continue
                    for line in f.read_text(encoding="utf-8").splitlines():
                        if not line.strip():
                            continue
                        it = json.loads(line)
                        made += 1
                        if it.get("status") in HELD or it.get("violations"):
                            held += 1
                            rules.update(v["rule"] for v in it.get("violations") or [])
                        elif it.get("status") in PASSED:
                            passed += 1
                    e.results.append({"project": pid, "lang": lang, "kind": kind, "file": f.name})
            by_lang[lang] = {
                "lines": made,
                "passed": passed,
                "held_for_a_person": held,
                "held_by_rule": dict(rules.most_common()),
            }
        e.summary = {"by_language": by_lang, "projects": len(ids)}
        e.checks["every_language_has_lines"] = all(int(v["lines"]) > 0 for v in by_lang.values())  # type: ignore[call-overload]

    return run_experiment(exp, body)


if __name__ == "__main__":
    raise SystemExit(main())
