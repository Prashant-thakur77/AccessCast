"""export-site: copy reviewed projects into a static site the player reads (PLAN §13, §19.5).

Refuses: drafts (unless --allow-drafts, which keeps their watermark), and ANY project whose source hash is in
a W3C test-set manifest (W3C-derived outputs are never published without written permission).
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from accesscast.config import REPO_ROOT, Settings
from accesscast.errors import UsageError
from accesscast.project import read_json, write_json

STATIC = Path(__file__).parent / "static"
MANIFESTS = REPO_ROOT / "eval" / "datasets" / "manifests"


def w3c_hashes() -> set[str]:
    out: set[str] = set()
    for f in MANIFESTS.glob("w3c*.json"):
        data = json.loads(f.read_text(encoding="utf-8"))
        for row in data.get("files", []):
            if row.get("sha256"):
                out.add(str(row["sha256"]))
    return out


def export_site(settings: Settings, projects: Sequence[str], out: Path, *, allow_drafts: bool = False) -> int:
    out.mkdir(parents=True, exist_ok=True)
    # static player files
    for f in STATIC.rglob("*"):
        if f.is_file():
            dst = out / f.relative_to(STATIC)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(f, dst)
    roots = [settings.projects_dir / p for p in projects] if projects else sorted(
        d for d in settings.projects_dir.iterdir() if (d / "reports" / "index.json").exists())
    banned = w3c_hashes()
    catalog: list[dict[str, Any]] = []
    for root in roots:
        info = read_json(root / "project.json")
        if info["sha256"] in banned:
            raise PermissionError(f"{root.name} is a W3C test-set video; its outputs are never published")
        idx_p = root / "reports" / "index.json"
        if not idx_p.exists():
            raise UsageError(f"{root.name}: no reports/index.json (render and package first)")
        idx = read_json(idx_p)
        if not idx.get("human_reviewed") and not allow_drafts:
            raise PermissionError(f"{root.name} is not reviewed by a person; refusing to publish a draft")
        dst = out / "p" / root.name
        if dst.exists():
            shutil.rmtree(dst)
        (dst / "render" / "tracks").mkdir(parents=True)
        for v in idx["versions"].values():
            shutil.copyfile(root / v["file"], dst / v["file"])
            for t in v["tracks"]:
                shutil.copyfile(root / t["file"], dst / t["file"])
            if v.get("source_to_output"):
                rows = [json.loads(x) for x in (root / v["source_to_output"]).read_text().splitlines() if x.strip()]
                write_json(dst / (v["source_to_output"].replace(".jsonl", ".json")), rows)
                v["source_to_output"] = v["source_to_output"].replace(".jsonl", ".json")
        dec = read_json(root / "reports" / "decisions.json")
        for item in dec["items"]:
            for fr in item.get("frames", []):
                src = root / fr
                if src.exists():
                    (dst / fr).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(src, dst / fr)
        write_json(dst / "index.json", idx)
        write_json(dst / "decisions.json", dec)
        rep = read_json(root / "reports" / "report.json")
        write_json(dst / "report.json", rep)
        catalog.append({"sha12": root.name, "title": idx.get("title"), "duration_ms": idx["duration_ms"],
                        "human_reviewed": idx.get("human_reviewed"), "synthetic_test_data": idx.get("synthetic_test_data"),
                        "reviewed_at": idx.get("reviewed_at")})
    (out / "data").mkdir(exist_ok=True)
    write_json(out / "data" / "catalog.json", {"projects": catalog})
    return len(catalog)
