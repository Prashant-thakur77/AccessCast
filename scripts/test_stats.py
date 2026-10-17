"""How many unit tests we run and how much of the core code they reach: one pytest run with coverage, counted from
pytest's own JUnit XML and coverage.py's JSON report (nothing typed by hand).

Writes evidence/tests.json always, including when tests fail (passed=false). The browser tests (E16) are separate.

Usage: python scripts/test_stats.py   → evidence/tests.json
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from eval.common import Experiment, run_experiment  # noqa: E402


def _test_file(classname: str) -> str:
    """tests.unit.test_x.TestY → tests.unit.test_x (the module whose name starts with test_)."""
    parts = classname.split(".")
    for i, part in enumerate(parts):
        if part.startswith("test_"):
            return ".".join(parts[: i + 1])
    return classname


def main() -> int:
    exp = Experiment(
        "tests",
        "none",
        config={
            "question": "How many unit and golden tests run, and how much of src/accesscast do they execute?",
            "runner": "pytest -q -p no:cacheprovider --cov=accesscast --cov-branch",
            "coverage": "coverage.py line + branch, src/accesscast only (workers/ run in their own envs)",
        },
    )

    def body(e: Experiment) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            junit = Path(tmp) / "junit.xml"
            cov = Path(tmp) / "coverage.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "-q",
                    "-p",
                    "no:cacheprovider",
                    "--cov=accesscast",
                    "--cov-branch",
                    f"--cov-report=json:{cov}",
                    f"--junitxml={junit}",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            root = ET.parse(junit).getroot()
            found = root if root.tag == "testsuite" else root.find("testsuite")
            assert found is not None, "no testsuite in JUnit XML"
            suite = found
            total = int(suite.get("tests", 0))
            failed = int(suite.get("failures", 0)) + int(suite.get("errors", 0))
            skipped = int(suite.get("skipped", 0))
            files = {_test_file(c.get("classname", "")) for c in suite.iter("testcase")}
            totals = json.loads(cov.read_text())["totals"] if cov.exists() else {}
        e.results.append({"pytest_exit": proc.returncode, "tail": proc.stdout.strip().splitlines()[-1:]})
        e.summary = {
            "tests_total": total,
            "tests_passed": total - failed - skipped,
            "tests_failed": failed,
            "tests_skipped": skipped,
            "test_files": len(files),
            "line_coverage_pct": round(float(totals.get("percent_covered", 0.0)), 1),
            "statements": totals.get("num_statements"),
            "statements_covered": totals.get("covered_lines"),
        }
        e.checks["pytest_exit_0"] = proc.returncode == 0
        e.checks["no_failures"] = failed == 0
        e.checks["coverage_measured"] = bool(totals)

    return run_experiment(exp, body)


if __name__ == "__main__":
    raise SystemExit(main())
