"""Summarise dev-set runs for prompt iteration (DEV ONLY: never point this at W3C projects)."""

from __future__ import annotations

import collections
import json

from accesscast.config import load_settings
from accesscast.project import read_json, read_jsonl

s = load_settings()
banned = set()
man = s.projects_dir.parent / "eval" / "datasets" / "manifests" / "w3c_wai.json"
if man.exists():
    banned = {r["sha256"] for r in json.loads(man.read_text())["files"]}
rules: collections.Counter[str] = collections.Counter()
for d in sorted(s.projects_dir.iterdir()):
    if not (d / "project.json").exists() or read_json(d / "project.json")["sha256"] in banned:
        continue
    items = read_jsonl(d / "items" / "ad.en.jsonl")
    st = collections.Counter(i["status"] for i in items)
    print(f"\n## {read_json(d / 'project.json')['source_name']} ({d.name}): {dict(st)}")
    for i in items[:12]:
        hist = i["repair"]["history"]
        for h in hist:
            rules.update(h["rules"])
        print(f"- {i['id']} [{i['status']}] {hist[0]['rules'] if hist else []} draft: {i['draft'][:110]!r}")
        if i.get("final"):
            print(f"    final: {i['final'][:110]!r}")
print("\nrules fired on drafts and repairs:", dict(rules.most_common()))
