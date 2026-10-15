"""Bundle one adversarial case's analysis for the proof API: proof/cases/<case>/ (our synthetic clips only).

Usage: python scripts/bundle_proof_case.py <case> <projects_dir>/<sha12> [--stress]
Copies words, vad, gaps, scenes, sounds and evidence (no media), the case's oracle, and the voice calibration.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from accesscast.config import REPO_ROOT
from accesscast.project import read_json
from accesscast.tts.engine import VOICES, load_calibration

case, proj = sys.argv[1], Path(sys.argv[2])
out = REPO_ROOT / "src" / "accesscast" / "proof" / "cases" / case
out.mkdir(parents=True, exist_ok=True)
info = read_json(proj / "project.json")
man = REPO_ROOT / "eval" / "datasets" / "manifests" / "w3c_wai.json"
if man.exists() and info["sha256"] in {r["sha256"] for r in json.loads(man.read_text())["files"]}:
    raise SystemExit("refusing: W3C test-set material is never published")
for name in ("words", "vad", "gaps", "scenes", "sounds"):
    (out / f"{name}.json").write_text((proj / "analysis" / f"{name}.json").read_text())
ev = [read_json(f) for f in sorted((proj / "evidence").glob("*/evidence.json"))]
(out / "evidence.json").write_text(json.dumps(ev, indent=1))
meta = json.loads((REPO_ROOT / "data" / "adversarial" / f"{case}.json").read_text())
cal = load_calibration(VOICES["en"])
meta = {k: meta[k] for k in ("baits", "oracle", "rules")} | {
    "calibration": {
        "voice": cal.voice,
        "wps_voice": cal.wps_voice,
        "intercept_s": cal.intercept_s,
        "measured": cal.measured,
    },
    "proof_temperature": "stress" if "--stress" in sys.argv else "production",
    "source_sha256": info["sha256"],
}
(out / "case.json").write_text(json.dumps(meta, indent=1))
print(f"bundled {case} → {out}")
