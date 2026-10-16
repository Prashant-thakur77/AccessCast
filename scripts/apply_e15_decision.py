"""Apply E15's dev-set decision to constants.py (ASR model, guard_ms). Run before `make freeze-prompts`."""

from __future__ import annotations

import json
import re

from accesscast.config import REPO_ROOT

ev = json.loads((REPO_ROOT / "evidence" / "e15_asr.json").read_text())
d = ev["summary"].get("decision")
if not ev.get("passed") or not d:
    raise SystemExit("E15 did not produce a decision; constants unchanged")
p = REPO_ROOT / "src" / "accesscast" / "constants.py"
s = p.read_text()
s = re.sub(
    r'^ASR_MODEL = "[^"]*"  #.*$',
    f'ASR_MODEL = "{d["asr_model"]}"  # E15 dev-set decision (evidence/e15_asr.json)',
    s,
    flags=re.M,
)
s = re.sub(
    r"^GUARD_MS = \d+  #.*$",
    f"GUARD_MS = {int(d['guard_ms'])}  # E15: p95 word-boundary error on dev clips, rounded up",
    s,
    flags=re.M,
)
p.write_text(s)
print(f"ASR_MODEL={d['asr_model']} GUARD_MS={d['guard_ms']} aligner={'on' if d['aligner'] else 'off'}")
if not d["aligner"]:
    print(
        "NOTE: E15 found the aligner did not help; set align=False in pipeline.stage_asr and say so in the README."
    )
