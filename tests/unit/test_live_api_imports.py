"""The live API on Vercel ships a pruned bundle (scripts/build_vercel_api.sh): no Pillow, no soundfile, no torch.
Importing it, and the code the picture API calls, must not need them (an import failure there is a 500 for every
visitor; it happened once, docs/incidents.md 2026-10-18)."""

import subprocess
import sys

BLOCKED = ("PIL", "soundfile", "torch", "torchaudio", "cv2")

CODE = f"""
import sys
for m in {BLOCKED!r}:
    sys.modules[m] = None  # any import of these now fails, as in the bundle
from accesscast.proof.api import create_app
from accesscast.write.evidence import evidence_from_frames, check_evidence
from accesscast.write.write_ad import verify_and_repair, write_drafts
create_app()
print("ok")
"""


def test_the_live_api_imports_without_pillow_soundfile_or_torch() -> None:
    r = subprocess.run([sys.executable, "-c", CODE], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0 and r.stdout.strip().endswith("ok"), r.stderr[-1500:]
