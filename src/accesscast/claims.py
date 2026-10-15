"""Claims registry check (PLAN §18.4).

1. Every claim validates; `measured`/`verified`/`memory_accounting`/`estimate` claims point into evidence
   files whose SHA-256 matches and whose value at the JSON pointer equals the claim value.
2. `cited` claims carry source_url, accessed date and the quoted text.
3. Every number in a public file is a claim value/display string or on the allow-list
   (evidence/number-allowlist.json: versions, standard thresholds), after removing code, links and ids.
4. `<pending: id>` placeholders are counted; with strict=True (submission-check) any placeholder fails.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from accesscast.project import sha256_file
from accesscast.schemas import ClaimsRegistry

PUBLIC_FILES = ("README.md", "JUDGES.md", "docs/deck/deck.md", "docs/lablab.md", "docs/demo-script.md")
_PENDING = re.compile(r"<pending:\s*([\w.\-]+)\s*>")
_NUM = re.compile(r"(?<![\w.\-/#§@])[-−]?\$?\d[\d,]*(?:\.\d+)?(?:\s?%|×|x\b)?")


@dataclass
class CheckResult:
    ok: bool = True
    messages: list[str] = field(default_factory=list)
    pending: list[str] = field(default_factory=list)

    def fail(self, msg: str) -> None:
        self.ok = False
        self.messages.append(f"FAIL {msg}")

    def info(self, msg: str) -> None:
        self.messages.append(f"ok   {msg}")


def resolve_pointer(doc: Any, pointer: str) -> Any:
    cur = doc
    if pointer in ("", "/"):
        return cur
    for raw in pointer.lstrip("/").split("/"):
        part = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(cur, list):
            cur = cur[int(part)]
        else:
            cur = cur[part]
    return cur


def _same(a: Any, b: Any) -> bool:
    if isinstance(a, int | float) and isinstance(b, int | float) and not isinstance(a, bool):
        return abs(float(a) - float(b)) <= 1e-9 * max(1.0, abs(float(a)))
    return bool(a == b)


def strip_non_prose(text: str) -> str:
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"`[^`]*`", " ", text)
    text = re.sub(r"\]\([^)]*\)", "]", text)  # markdown link targets
    text = re.sub(r"https?://\S+", " ", text)
    text = _PENDING.sub(" ", text)
    text = re.sub(r"\b[A-Za-z]+[-_.]?\d[\w.\-]*\b", " ", text)  # ids and names: e01, AD001, gemma-4-31B, v1, MI300X
    text = re.sub(r"§\s?\d[\d.]*", " ", text)
    text = re.sub(r"\b\d+(?:\.\d+)?B\b", " ", text)  # model sizes in names: 31B, 82M handled above
    text = re.sub(r"\b\d{1,2}\s(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s\d{4}\b", " ", text)  # dates
    return text


def _norm_num(tok: str) -> str:
    t = tok.replace("−", "-").replace("$", "").replace(",", "").replace("%", "").replace("×", "").strip()
    t = t[:-1] if t.endswith("x") else t
    try:
        f = float(t)
    except ValueError:
        return t
    return str(int(f)) if f == int(f) else repr(round(f, 6))


def check(root: Path, *, strict_placeholders: bool = False) -> CheckResult:
    res = CheckResult()
    reg_p = root / "evidence" / "public-claims.json"
    if not reg_p.exists():
        res.fail("evidence/public-claims.json missing")
        return res
    try:
        reg = ClaimsRegistry.model_validate(json.loads(reg_p.read_text(encoding="utf-8")))
    except Exception as e:
        res.fail(f"public-claims.json invalid: {e}")
        return res
    allowed: set[str] = set()
    ids: set[str] = set()
    for c in reg.claims:
        if c.claim_id in ids:
            res.fail(f"duplicate claim_id {c.claim_id}")
        ids.add(c.claim_id)
        if c.status == "cited":
            if not (c.source_url and c.accessed and c.quote):
                res.fail(f"{c.claim_id}: cited claims need source_url, accessed and quote")
        else:
            if not c.evidence:
                res.fail(f"{c.claim_id}: status {c.status} needs an evidence pointer")
            for ev in c.evidence:
                p = root / ev.path
                if not p.exists():
                    res.fail(f"{c.claim_id}: {ev.path} missing")
                    continue
                if sha256_file(p) != ev.sha256:
                    res.fail(f"{c.claim_id}: {ev.path} changed since the claim was registered (sha256 mismatch)")
                    continue
                try:
                    val = resolve_pointer(json.loads(p.read_text(encoding="utf-8")), ev.pointer)
                except (KeyError, IndexError, ValueError) as e:
                    res.fail(f"{c.claim_id}: pointer {ev.pointer} not found ({e})")
                    continue
                if not _same(val, c.value):
                    res.fail(f"{c.claim_id}: value {c.value!r} != evidence {val!r} at {ev.pointer}")
        if c.value is not None:
            allowed.add(_norm_num(str(c.value)))
        for d in c.display:
            for m in _NUM.finditer(d):
                allowed.add(_norm_num(m.group(0)))
    allow_p = root / "evidence" / "number-allowlist.json"
    if allow_p.exists():
        for row in json.loads(allow_p.read_text(encoding="utf-8")).get("numbers", []):
            allowed.add(_norm_num(str(row["value"])))
    for rel in PUBLIC_FILES:
        p = root / rel
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8")
        for m in _PENDING.finditer(text):
            res.pending.append(f"{rel}: {m.group(1)}")
            if m.group(1) not in ids and not m.group(1).startswith(("site.", "video.", "deck.", "results.", "amd.",
                                                                     "negative.")):
                res.messages.append(f"note {rel}: placeholder {m.group(1)} has no claim yet")
        prose = strip_non_prose(text)
        bad = sorted({m.group(0).strip() for m in _NUM.finditer(prose) if _norm_num(m.group(0)) not in allowed})
        if bad:
            res.fail(f"{rel}: unregistered numbers {bad[:12]}")
        else:
            res.info(f"{rel}: every number is registered")
    if res.pending:
        msg = f"{len(res.pending)} <pending:> placeholder(s) remain"
        if strict_placeholders:
            res.fail(msg)
        else:
            res.messages.append(f"note {msg} (allowed until submission-check)")
    res.info(f"{len(reg.claims)} claim(s) checked")
    return res
