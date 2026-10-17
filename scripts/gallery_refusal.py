"""The refusal gallery: ask for a PUBLIC render of a project whose lines no person has approved, and record that
the gate refused it (exit code and message), next to the labelled DRAFT render the same project is allowed.

Usage: ACCESSCAST_PROJECTS_DIR=projects/_site python scripts/gallery_refusal.py dac08bcd9d7a
→ evidence/gallery/refused_public_render.json
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from eval.common import Experiment, run_experiment  # noqa: E402


def main() -> int:
    sha12 = sys.argv[1] if len(sys.argv) > 1 else "dac08bcd9d7a"
    projects = Path(os.environ.get("ACCESSCAST_PROJECTS_DIR", ROOT / "projects"))
    exp = Experiment(
        "gallery/refused_public_render", "none", config={"project": sha12, "projects_dir": str(projects)}
    )

    def body(e: Experiment) -> None:
        cmd = ["uv", "run", "accesscast", "render", "-p", sha12, "--mode", "public"]
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=ROOT,
            env={**os.environ, "ACCESSCAST_PROJECTS_DIR": str(projects)},
        )
        msg = [ln for ln in (r.stdout + r.stderr).splitlines() if "refused" in ln or "error" in ln.lower()]
        draft = json.loads((projects / sha12 / "reports" / "render.json").read_text())
        e.results = [
            {
                "request": "public render",
                "command": " ".join(cmd[2:]),
                "exit_code": r.returncode,
                "message": msg[-1] if msg else "",
            },
            {
                "request": "draft render (labelled UNREVIEWED DRAFT)",
                "mode": draft.get("mode"),
                "versions": sorted((draft.get("versions") or {}).keys()),
            },
        ]
        e.summary = {
            "public_render_refused": r.returncode != 0,
            "refusal_message": msg[-1] if msg else "",
            "exit_code": r.returncode,
        }
        e.checks["public_render_refused"] = r.returncode == 7 and bool(msg)

    return run_experiment(exp, body)


if __name__ == "__main__":
    raise SystemExit(main())
