"""Fetch SIMPITIKI v2 (Italian simplification pairs, CC-BY-4.0) for E5's Italian check.

Tonelli, Palmero Aprosio and Saltori, "SIMPITIKI: a Simplification corpus for Italian", CLiC-it 2016,
https://github.com/dhfbk/simpitiki (Fondazione Bruno Kessler). Stored in data/simpitiki/ (git-ignored); only the
SHA-256 manifest is committed. Each pair is one human edit labelled with a simplification type, so a pair is
usually a small change, not a full easy-read rewrite; E5 says so when it reports this data.

Exit codes: 0 ok, 5 network error, 7 the file is not what we expect.
Usage: python -m eval.datasets.fetch_simpitiki
"""

from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import httpx

from accesscast.config import REPO_ROOT
from accesscast.events import now_iso
from accesscast.project import atomic_write_text, sha256_file

COMMIT = "13c119cb5e0377e7f4a41c384ecc24f6584c851f"  # dhfbk/simpitiki master on 16 Oct 2026
URL = f"https://raw.githubusercontent.com/dhfbk/simpitiki/{COMMIT}/corpus/simpitiki-v2.xml"
OUT = REPO_ROOT / "data" / "simpitiki" / "simpitiki-v2.xml"
MANIFEST = REPO_ROOT / "eval" / "datasets" / "manifests" / "simpitiki.json"
_TAG = re.compile(r"</?(ins|del)>")


@dataclass(frozen=True)
class Pair:
    before: str
    after: str
    type_id: str
    origin: str  # itwiki | tn (Municipality of Trento)


def parse(path: Path) -> list[Pair]:
    """Pairs with the <ins>/<del> edit marks removed (each side keeps its own text)."""
    root = ET.parse(path).getroot()
    out = []
    for s in root.iter("simplification"):
        b, a = s.find("before"), s.find("after")
        if b is None or a is None:
            continue
        before = " ".join(_TAG.sub("", "".join(b.itertext())).split())
        after = " ".join(_TAG.sub("", "".join(a.itertext())).split())
        if before and after:
            out.append(Pair(before, after, s.get("type", ""), s.get("origin", "")))
    return out


def load_pairs() -> list[Pair]:
    if not MANIFEST.exists() or not OUT.exists():
        raise FileNotFoundError("SIMPITIKI missing: run `python -m eval.datasets.fetch_simpitiki`")
    man = json.loads(MANIFEST.read_text())
    if sha256_file(OUT) != man["sha256"]:
        raise ValueError("data/simpitiki/simpitiki-v2.xml does not match the manifest SHA-256")
    return parse(OUT)


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    try:
        r = httpx.get(URL, timeout=120, follow_redirects=True)
    except httpx.HTTPError as e:
        print(f"network error: {type(e).__name__}", file=sys.stderr)
        return 5
    if r.status_code != 200:
        print(f"HTTP {r.status_code} fetching {URL}", file=sys.stderr)
        return 5
    atomic_write_text(OUT, r.text)
    try:
        pairs = parse(OUT)
    except ET.ParseError as e:
        print(f"not valid XML: {e}", file=sys.stderr)
        return 7
    if not pairs:
        print("no simplification pairs found", file=sys.stderr)
        return 7
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(
        MANIFEST,
        json.dumps(
            {
                "dataset": "SIMPITIKI v2",
                "source": URL,
                "commit": COMMIT,
                "licence": "CC-BY-4.0",
                "credit": "Tonelli, Palmero Aprosio, Saltori (FBK), CLiC-it 2016",
                "fetched_at": now_iso(),
                "file": str(OUT.relative_to(REPO_ROOT)),
                "sha256": sha256_file(OUT),
                "pairs": len(pairs),
                "committed": False,
            },
            indent=1,
        )
        + "\n",
    )
    print(f"SIMPITIKI v2: {len(pairs)} pairs → {MANIFEST.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
