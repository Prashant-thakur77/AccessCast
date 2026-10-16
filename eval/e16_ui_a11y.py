"""E16: are our own pages accessible? Runs the Playwright + axe-core suites (player and review app) with a JSON
reporter and records pass/fail per test. Target: 0 axe violations and the keyboard-only end-to-end tests passing.
A screen-reader smoke test by a person is recorded separately in docs/ when it happens (never claimed before).
Usage: python -m eval.e16_ui_a11y [--site projects/_fixture_site] [--review-fixture <projects dir>]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from accesscast.config import REPO_ROOT
from eval.common import Experiment, run_experiment


def run_suite(config: str | None, env: dict[str, str]) -> dict[str, object]:
    cmd = ["npx", "playwright", "test", "--reporter=json"] + (["-c", config] if config else [])
    p = subprocess.run(
        cmd, cwd=REPO_ROOT, env={**os.environ, **env}, capture_output=True, text=True, timeout=1800
    )
    try:
        rep = json.loads(p.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "error": (p.stderr or p.stdout)[-800:]}
    tests = []

    def walk(suite: dict[str, object]) -> None:
        for spec in suite.get("specs", []):  # type: ignore[union-attr]
            for t in spec.get("tests", []):
                res = t.get("results", [{}])[-1]
                tests.append({"title": spec.get("title"), "status": res.get("status")})
        for s in suite.get("suites", []):  # type: ignore[union-attr]
            walk(s)

    for s in rep.get("suites", []):
        walk(s)
    return {
        "ok": p.returncode == 0,
        "tests": tests,
        "passed": sum(t["status"] == "passed" for t in tests),
        "total": len(tests),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default=str(REPO_ROOT / "projects" / "_fixture_site"))
    ap.add_argument("--review-fixture", default=str(REPO_ROOT / "projects" / "_fixture"))
    args = ap.parse_args()
    exp = Experiment(
        "e16_ui_a11y",
        "none",
        config={
            "site": os.path.relpath(args.site, REPO_ROOT),
            "tools": "Playwright + @axe-core/playwright (chromium)",
        },
    )

    def body(e: Experiment) -> None:
        if Path(args.site).resolve() == (REPO_ROOT / "projects" / "_fixture_site").resolve():
            # always test the current pages, never a stale build (own process: it switches to fake mode)
            subprocess.run(
                [sys.executable, "-c", "from accesscast.cli import demo_fixture; demo_fixture(serve=False)"],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
            )
        player = run_suite(None, {"ACCESSCAST_SITE_DIR": args.site})
        review = run_suite("playwright.review.config.ts", {"ACCESSCAST_REVIEW_FIXTURE": args.review_fixture})
        e.results = [{"suite": "player", **player}, {"suite": "review", **review}]
        e.summary = {
            "player": {k: player.get(k) for k in ("passed", "total")},
            "review": {k: review.get(k) for k in ("passed", "total")},
            "screen_reader_test_by_person": None,
        }
        e.checks["player_suite"] = bool(player["ok"])
        e.checks["review_suite"] = bool(review["ok"])

    return run_experiment(exp, body)


if __name__ == "__main__":
    raise SystemExit(main())
