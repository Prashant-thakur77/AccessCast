# Structure (required files, secret scan, licence rows, size limits) follows Rivet's cli/submission_command.py
# (https://github.com/damishafe/Rivet), MIT License, Copyright (c) 2026 Enoch Idowu. Rewritten for AccessCast.
"""make submission-check: everything in PLAN §18.6. Exit 0 only if every check passes."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import urllib.request

from accesscast.claims import check as claims_check
from accesscast.config import REPO_ROOT
from accesscast.project import sha256_file

MUST_HAVE_EVIDENCE = {  # PLAN §5 → evidence files (two-digit eNN_)
    1: ["e01_verifier_ab.json"], 2: ["e02_ladder_V0.json", "e03_model_size_*.json"],
    3: ["test_freeze.json", "test_runs.jsonl"], 4: ["public-claims.json"], 6: ["e13_serving_*.json", "e14_cost.json",
    "doctor.json"], 7: ["e11_adversarial.json"], 8: ["e08_soak.json", "e09_determinism.json", "e10_offline.json"],
    10: ["uptime.json"],
}
SECRET_RES = [re.compile(p) for p in (r"rc-[A-Za-z0-9_\-]{16,}", r"hf_[A-Za-z0-9]{24,}", r"gh[opsu]_[A-Za-z0-9]{30,}",
                                      r"sk-[A-Za-z0-9]{20,}", r"AKIA[0-9A-Z]{16}", r"-----BEGIN [A-Z ]*PRIVATE KEY-----")]
MEDIA_EXT = (".mp4", ".mov", ".mkv", ".webm", ".wav", ".mp3", ".m4a", ".flac")
LIVE_URL = "https://accesscast.vercel.app/"


def tracked() -> list[str]:
    return subprocess.run(["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True, check=True).stdout.split()


def main() -> int:
    fails: list[str] = []
    oks: list[str] = []

    def chk(ok: bool, msg: str) -> None:
        (oks if ok else fails).append(msg)

    files = tracked()
    # 1. claims (strict: no <pending:> placeholders anywhere public)
    cr = claims_check(REPO_ROOT, strict_placeholders=True)
    chk(cr.ok, f"claims-check strict ({len(cr.pending)} placeholders)")
    first = (REPO_ROOT / "README.md").read_text(encoding="utf-8").splitlines()[0]
    chk("<pending" not in first and bool(re.search(r"\d", first)), "README line 1 is the filled headline")
    # 2. must-have evidence files
    ev = REPO_ROOT / "evidence"
    for k, pats in MUST_HAVE_EVIDENCE.items():
        missing = [p for p in pats if not list(ev.glob(p))]
        chk(not missing, f"must-have #{k} evidence {missing or 'present'}")
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    chk("## What didn't work" in readme and "<pending: negative.results>" not in readme, "must-have #5 negative results")
    # 3. no W3C-derived media in git or site
    man = REPO_ROOT / "eval" / "datasets" / "manifests" / "w3c_wai.json"
    w3c = {r["sha256"] for r in json.loads(man.read_text())["files"]} if man.exists() else set()
    bad = [f for f in files if f.endswith(MEDIA_EXT) and (REPO_ROOT / f).exists() and sha256_file(REPO_ROOT / f) in w3c]
    bad += [f for f in files if "perspectives_" in f and f.endswith(MEDIA_EXT)]
    site_media = [p for p in (REPO_ROOT / "site").rglob("*") if p.suffix in MEDIA_EXT]
    bad += [str(p) for p in site_media if sha256_file(p) in w3c]
    chk(not bad, f"no W3C-derived media in git or site/ {bad[:3]}")
    # 4. media we may commit: fixtures, site player media of our own projects, adversarial clips are not tracked
    allowed = ("tests/fixtures/", "site/p/")
    stray = [f for f in files if f.endswith(MEDIA_EXT) and not f.startswith(allowed)]
    chk(not stray, f"no other media committed {stray[:3]}")
    big = [f for f in files if (REPO_ROOT / f).exists() and (REPO_ROOT / f).stat().st_size > 50 * 2**20]
    chk(not big, f"no tracked file > 50 MB {big[:3]}")
    # 5. secrets
    leaks = []
    for f in files:
        p = REPO_ROOT / f
        if f == ".env" or (p.suffix in MEDIA_EXT) or not p.is_file() or p.stat().st_size > 5 * 2**20:
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if any(r.search(text) for r in SECRET_RES):
            leaks.append(f)
    chk(not leaks, f"no secrets in tracked files {leaks[:3]}")
    chk(".env" not in files, ".env is not tracked")
    # 6. licences: every model/voice named in code or project.json files is in MODEL_LICENSES.md
    lic = (REPO_ROOT / "MODEL_LICENSES.md").read_text(encoding="utf-8")
    names = {"google/gemma-4-31B-it", "google/gemma-4-E4B-it", "Kokoro-82M", "whisper-large-v3", "Silero VAD",
             "WAV2VEC2_ASR_BASE_960H", "en_core_web_sm"}
    for pj in (REPO_ROOT / "projects").glob("*/project.json"):
        for m in json.loads(pj.read_text()).get("models", []):
            names.add(m["name"])
    missing_lic = sorted(n for n in names if n not in lic)
    chk(not missing_lic, f"MODEL_LICENSES.md lists every model {missing_lic}")
    # 7. site + live URL
    chk((REPO_ROOT / "site" / "index.html").exists(), "site/ is built")
    try:
        code = urllib.request.urlopen(LIVE_URL, timeout=20).status
    except Exception as e:
        code = str(e)
    chk(code == 200, f"live URL {LIVE_URL} returns {code}")
    # 8. submission assets
    chk((REPO_ROOT / "docs" / "deck" / "deck.pdf").exists(), "deck PDF exists")
    chk(any((REPO_ROOT / "docs").glob("cover.*")), "cover image exists")
    lab = REPO_ROOT / "docs" / "lablab.md"
    chk((lab.exists() and "youtu" in lab.read_text(encoding="utf-8").lower()) or (lab.exists() and "video" in
        lab.read_text(encoding="utf-8").lower() and "http" in lab.read_text(encoding="utf-8")), "lablab text with demo video link")
    for m in oks:
        print(f"ok   {m}")
    for m in fails:
        print(f"FAIL {m}")
    print(f"\n{len(oks)} passed, {len(fails)} failed")
    return 0 if not fails else 7


if __name__ == "__main__":
    sys.exit(main())
