"""Counts the README quotes about the project itself, read from the code and the repo (never typed by hand): check
rules per family, pipeline stages, viewer versions, languages, prompts, experiments run, incidents, charts, pages.

Usage: python scripts/repo_stats.py   → evidence/repo_stats.json
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from eval.common import Experiment, run_experiment  # noqa: E402

FAMILIES = {
    "AD": "description",
    "ER": "easy-read",
    "CC": "captions and subtitles",
    "VO": "voice-over",
    "RN": "render",
}
PLANNED = [f"e{n:02d}" for n in range(1, 19)]  # E1–E18 in PLAN.md and eval/PREREGISTRATION.md


def main() -> int:
    exp = Experiment("repo_stats", "none", config={"source": "code, docs/rules.md, evidence/, docs/"})

    def body(e: Experiment) -> None:
        from accesscast import constants as C
        from accesscast.render_stage import AUDIENCE_VERSIONS
        from accesscast.review.studio import STAGE_WORDS

        rules_md = (ROOT / "docs" / "rules.md").read_text(encoding="utf-8")
        ids = sorted(set(re.findall(r"^\| ([A-Z]{2}\d{3})\b", rules_md, flags=re.M)))
        per_family = {fam: sum(1 for i in ids if i.startswith(fam)) for fam in FAMILIES}
        ran = sorted({p.name[:3] for p in (ROOT / "evidence").glob("e[0-9][0-9]_*.json")})
        incidents = len(re.findall(r"^## 20\d\d-", (ROOT / "docs" / "incidents.md").read_text(), flags=re.M))
        py_lines = sum(
            len(p.read_text(encoding="utf-8").splitlines())
            for p in (ROOT / "src" / "accesscast").rglob("*.py")
        )
        pages = sorted(p.name for p in (ROOT / "src/accesscast/player/static").glob("*.html"))
        e.results = [{"rule_ids": ids, "experiments_with_evidence": ran, "pages": pages}]
        e.summary = {
            "rules_total": len(ids),
            "rules_by_family": per_family,
            "pipeline_stages": len(STAGE_WORDS),
            "viewer_versions": len(AUDIENCE_VERSIONS),
            "languages_total": len(C.LANGS),
            "translation_languages": len(C.TRANSLATION_LANGS),
            "prompts": len(list((ROOT / "src/accesscast/llm/prompts").glob("*.md"))),
            "experiments_planned": len(PLANNED),
            "experiments_run": len([x for x in ran if x in PLANNED]),
            "incidents": incidents,
            "charts": len(list((ROOT / "docs" / "charts").glob("*.png"))),
            "site_pages": len(pages),
            "python_lines_src": py_lines,
        }
        e.checks["rules_found"] = len(ids) > 0
        e.checks["stages_found"] = len(STAGE_WORDS) > 0

    return run_experiment(exp, body)


if __name__ == "__main__":
    raise SystemExit(main())
