"""make freeze-prompts: tag test-freeze-<n> and write evidence/test_freeze.json (PLAN §14.4)."""

from __future__ import annotations

import json
import subprocess
import sys

from accesscast.config import REPO_ROOT
from accesscast.events import now_iso
from eval.common import FREEZE, frozen_hashes, git


def main() -> int:
    if git("status", "--porcelain"):
        print("refusing to freeze: commit your changes first (the freeze must point at a commit)", file=sys.stderr)
        return 2
    tags = [t for t in git("tag", "--list", "test-freeze-*").split() if t]
    n = max((int(t.rsplit("-", 1)[1]) for t in tags), default=0) + 1
    tag = f"test-freeze-{n}"
    doc = {"tag": tag, "commit": git("rev-parse", "HEAD"), "frozen_at": now_iso(), "files": frozen_hashes()}
    FREEZE.write_text(json.dumps(doc, indent=1) + "\n")
    subprocess.run(["git", "add", str(FREEZE.relative_to(REPO_ROOT))], cwd=REPO_ROOT, check=True)
    subprocess.run(["git", "commit", "-qm", f"Freeze prompts, constants, lexicons and confidence: {tag}"], cwd=REPO_ROOT,
                   check=True)
    subprocess.run(["git", "tag", tag], cwd=REPO_ROOT, check=True)
    print(f"{tag}: {len(doc['files'])} files frozen")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
