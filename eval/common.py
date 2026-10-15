"""Shared evaluation plumbing (CLAUDE.md §7).

- `Experiment` always writes evidence/eNN_<name>.json, including when its checks fail (passed=false, exit 7).
- Test-split runs refuse unless the frozen files match evidence/test_freeze.json, and are logged in
  evidence/test_runs.jsonl.
"""

from __future__ import annotations

import json
import platform
import subprocess
import sys
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from accesscast.config import REPO_ROOT
from accesscast.events import now_iso
from accesscast.project import atomic_write_text, sha256_file

EVIDENCE = REPO_ROOT / "evidence"
FREEZE = EVIDENCE / "test_freeze.json"
TEST_RUNS = EVIDENCE / "test_runs.jsonl"
FROZEN_GLOBS = ("src/accesscast/llm/prompts/*.md", "src/accesscast/constants.py",
                "src/accesscast/confidence.py", "src/accesscast/verify/lexicons/*.py")


def git(*args: str) -> str:
    p = subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=False)
    return p.stdout.strip()


def frozen_hashes() -> dict[str, str]:
    out = {}
    for g in FROZEN_GLOBS:
        for f in sorted(REPO_ROOT.glob(g)):
            out[str(f.relative_to(REPO_ROOT))] = sha256_file(f)
    return out


def check_freeze() -> dict[str, Any]:
    """Test-set runs only after `make freeze-prompts`, and only while the frozen files are unchanged."""
    if not FREEZE.exists():
        raise SystemExit("refusing a test-set run: no evidence/test_freeze.json (run `make freeze-prompts` first)")
    frozen = json.loads(FREEZE.read_text())
    now = frozen_hashes()
    changed = sorted(k for k in set(now) | set(frozen["files"]) if now.get(k) != frozen["files"].get(k))
    if changed:
        raise SystemExit(f"refusing a test-set run: frozen files changed since {frozen['tag']}: {changed[:5]}")
    return frozen


def environment() -> dict[str, Any]:
    env: dict[str, Any] = {"python": platform.python_version(), "host": platform.node(), "platform": platform.platform()}
    try:
        p = subprocess.run(["amd-smi", "static", "--asic", "--json"], capture_output=True, text=True, timeout=20, check=False)
        if p.returncode == 0:
            env["amd_smi_static"] = json.loads(p.stdout)
            env["gpu"] = "AMD Instinct MI300X" if "MI300X" in p.stdout else "AMD GPU"
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
        env["gpu"] = None
    lock = REPO_ROOT / "deploy" / "versions.lock"
    if lock.exists():
        env["versions_lock"] = dict(line.split("=", 1) for line in lock.read_text().splitlines()
                                    if "=" in line and not line.startswith("#"))
    return env


@dataclass
class Experiment:
    experiment: str  # e.g. "e01_verifier_ab"
    split: str  # dev | test | none
    config: dict[str, Any] = field(default_factory=dict)
    results: list[dict[str, Any]] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    checks: dict[str, bool] = field(default_factory=dict)
    started_at: str = field(default_factory=now_iso)
    freeze_tag: str | None = None

    def __post_init__(self) -> None:
        if self.split == "test":
            self.freeze_tag = check_freeze()["tag"]

    def path(self) -> Path:
        return EVIDENCE / f"{self.experiment}.json"

    def write(self, error: str | None = None) -> bool:
        passed = bool(self.checks) and all(self.checks.values()) and error is None
        doc = {
            "schema": "accesscast/evidence/v1", "experiment": self.experiment, "split": self.split,
            "passed": passed, "git_commit": git("rev-parse", "HEAD"), "git_dirty": bool(git("status", "--porcelain")),
            "freeze_tag": self.freeze_tag, "started_at": self.started_at, "finished_at": now_iso(),
            "environment": environment(), "config": self.config, "checks": self.checks,
            "results": self.results, "summary": self.summary, "error": error,
        }
        EVIDENCE.mkdir(exist_ok=True)
        atomic_write_text(self.path(), json.dumps(doc, indent=1, ensure_ascii=False, default=str) + "\n")
        if self.split == "test":
            with TEST_RUNS.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"ts": now_iso(), "experiment": self.experiment, "freeze_tag": self.freeze_tag,
                                     "git_commit": doc["git_commit"], "passed": passed}) + "\n")
        return passed


def run_experiment(exp: Experiment, body: Callable[[Experiment], None]) -> int:
    """Run `body`; always write the evidence file; exit 0 if every check passed, else 7."""
    err = None
    try:
        body(exp)
    except SystemExit:
        raise
    except BaseException as e:  # the evidence file is written even on a crash
        err = f"{type(e).__name__}: {e}\n{traceback.format_exc()[-1500:]}"
    passed = exp.write(err)
    print(f"{exp.experiment}: passed={passed} → {exp.path().relative_to(REPO_ROOT)}")
    if err:
        print(err, file=sys.stderr)
    return 0 if passed else 7
