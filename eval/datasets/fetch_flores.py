"""Fetch FLORES+ devtest for E4: eng_Latn, hin_Deva, ita_Latn, spa_Latn, fra_Latn (openlanguagedata/flores_plus, CC BY-SA 4.0, gated).

The data goes to data/flores/ (git-ignored) and is never committed (CLAUDE.md rule 8). Only the SHA-256 manifest
eval/datasets/manifests/flores_plus.json is committed, so every E4 result is tied to exact files.

Needs HF_TOKEN in .env for an account that accepted the dataset's terms on its Hugging Face page.
Exit codes: 0 ok, 4 no token or no access, 5 network/endpoint error, 7 the files are not what we expect.

Usage: python -m eval.datasets.fetch_flores [--split devtest]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import httpx

from accesscast.config import REPO_ROOT, load_settings
from accesscast.events import now_iso
from accesscast.project import atomic_write_text, sha256_file

REPO = "openlanguagedata/flores_plus"
REVISION = "e707e62e762a9e2faca3933aa315f4665cc3cd8f"  # dataset commit, read from the HF API on 16 Oct 2026
LANGS = ("eng_Latn", "hin_Deva", "ita_Latn", "spa_Latn", "fra_Latn")
OUT = REPO_ROOT / "data" / "flores"
MANIFEST = REPO_ROOT / "eval" / "datasets" / "manifests" / "flores_plus.json"
PAGE = f"https://huggingface.co/datasets/{REPO}"


def url(split: str, lang: str) -> str:
    return f"https://huggingface.co/datasets/{REPO}/resolve/{REVISION}/{split}/{lang}.jsonl"


def read_rows(path: Path) -> list[dict[str, object]]:
    rows = []
    for k, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            raise ValueError(f"{path.name}:{k + 1}: not JSON ({e})") from e
        if not isinstance(obj, dict) or "id" not in obj or not str(obj.get("text", "")).strip():
            raise ValueError(f"{path.name}:{k + 1}: missing id or text")
        rows.append(obj)
    return rows


def load_split(split: str = "devtest") -> dict[str, list[str]]:
    """lang → sentences in id order, checked against the committed manifest. Used by E4."""
    if not MANIFEST.exists():
        raise FileNotFoundError("no FLORES+ manifest: run `python -m eval.datasets.fetch_flores` first")
    man = json.loads(MANIFEST.read_text())
    out: dict[str, list[str]] = {}
    for f in man["files"]:
        if f["split"] != split:
            continue
        p = REPO_ROOT / f["file"]
        if not p.exists():
            raise FileNotFoundError(f"{f['file']} missing: run `python -m eval.datasets.fetch_flores`")
        if sha256_file(p) != f["sha256"]:
            raise ValueError(f"{f['file']} does not match the manifest SHA-256")
        rows = sorted(read_rows(p), key=lambda r: int(str(r["id"])))
        out[f["lang"]] = [str(r["text"]).strip() for r in rows]
    if set(out) != set(LANGS):
        raise ValueError(f"manifest lists {sorted(out)}, expected {list(LANGS)}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="devtest", choices=["devtest", "dev"])
    args = ap.parse_args()
    load_settings()  # reads .env into the environment; the token itself is never printed or logged
    token = os.environ.get("HF_TOKEN", "")
    if not token:
        print(
            f"HF_TOKEN is not set. FLORES+ is gated: accept its terms at {PAGE} and put HF_TOKEN in .env.",
            file=sys.stderr,
        )
        return 4
    d = OUT / args.split
    d.mkdir(parents=True, exist_ok=True)
    files = []
    with httpx.Client(
        timeout=120, follow_redirects=True, headers={"Authorization": f"Bearer {token}"}
    ) as http:
        for lang in LANGS:
            dst = d / f"{lang}.jsonl"
            try:
                r = http.get(url(args.split, lang))
            except httpx.HTTPError as e:
                print(f"network error fetching {lang}: {type(e).__name__}", file=sys.stderr)
                return 5
            if r.status_code in (401, 403):
                print(
                    f"HTTP {r.status_code} for {lang}: this token's account has no access. Accept the terms at "
                    f"{PAGE} with the same account.",
                    file=sys.stderr,
                )
                return 4
            if r.status_code != 200:
                print(f"HTTP {r.status_code} fetching {lang}", file=sys.stderr)
                return 5
            atomic_write_text(dst, r.text)
            rows = read_rows(dst)
            files.append(
                {
                    "split": args.split,
                    "lang": lang,
                    "file": str(dst.relative_to(REPO_ROOT)),
                    "sha256": sha256_file(dst),
                    "sentences": len(rows),
                    "ids": [min(int(str(x["id"])) for x in rows), max(int(str(x["id"])) for x in rows)],
                }
            )
    counts = {f["lang"]: f["sentences"] for f in files}
    if len(set(counts.values())) != 1:
        print(f"sentence counts differ across languages: {counts}", file=sys.stderr)
        return 7
    id_sets = [{int(str(x["id"])) for x in read_rows(REPO_ROOT / str(f["file"]))} for f in files]
    if any(s != id_sets[0] for s in id_sets):
        print("sentence ids differ across languages", file=sys.stderr)
        return 7
    old = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {"files": []}
    keep = [f for f in old.get("files", []) if f.get("split") != args.split]
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(
        MANIFEST,
        json.dumps(
            {
                "dataset": REPO,
                "revision": REVISION,
                "licence": "CC BY-SA 4.0 (gated)",
                "page": PAGE,
                "fetched_at": now_iso(),
                "committed": False,
                "note": "data stays in data/flores/ (git-ignored)",
                "files": keep + files,
            },
            indent=1,
        )
        + "\n",
    )
    print(f"FLORES+ {args.split}: {counts} → {MANIFEST.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
