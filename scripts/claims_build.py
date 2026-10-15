"""Register claims from evidence files, then fill `<pending: id>` placeholders in public files from the registry.

Never type a number by hand: every value is read from an evidence file at a JSON pointer (or comes from a verified
`cited` fact in evidence/cited_claims.json), hashed, and written to evidence/public-claims.json. Placeholders whose
evidence does not exist yet are left in place, so submission-check keeps failing until the experiment runs.

Usage: python scripts/claims_build.py [--fill]
"""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from accesscast.claims import PUBLIC_FILES, resolve_pointer
from accesscast.config import REPO_ROOT
from accesscast.project import sha256_file

EV = REPO_ROOT / "evidence"


@dataclass
class Spec:
    claim_id: str
    path: str
    pointer: str
    text: str  # plain-words sentence; {v} is the display value
    unit: str = ""
    fmt: Callable[[Any], str] = str
    split: str = "dev"


def pct(x: Any) -> str:
    return f"{float(x) * 100:.0f}%"


def money(x: Any) -> str:
    return f"${float(x):.4f}" if float(x) < 0.1 else f"${float(x):.2f}"


def secs(x: Any) -> str:
    return f"{float(x):.1f} s"


SPECS: list[Spec] = [
    # E1 (test split, headline)
    Spec(
        "e1.lines_planned",
        "e01_verifier_ab.json",
        "/summary/pooled/A/lines_planned",
        "description lines planned",
        "lines",
        split="test",
    ),
    Spec(
        "e1.fit_a",
        "e01_verifier_ab.json",
        "/summary/pooled/A/lines_fit",
        "lines that fit, Gemma 4 alone (arm A)",
        "lines",
        split="test",
    ),
    Spec(
        "e1.fit_b",
        "e01_verifier_ab.json",
        "/summary/pooled/B/lines_fit",
        "lines that fit, + checks (arm B)",
        "lines",
        split="test",
    ),
    Spec(
        "e1.fit_c",
        "e01_verifier_ab.json",
        "/summary/pooled/C/lines_fit",
        "lines that fit, + checks and Gemma repair (arm C)",
        "lines",
        split="test",
    ),
    Spec(
        "e1.sent_c",
        "e01_verifier_ab.json",
        "/summary/pooled/C/sent_to_person",
        "lines sent to a person in arm C",
        "lines",
        split="test",
    ),
    Spec(
        "e1.ci_lo",
        "e01_verifier_ab.json",
        "/summary/c_minus_a_share/ci95_lo",
        "lower end of the 95% interval for (C−A)/L",
        fmt=pct,
        split="test",
    ),
    Spec(
        "e1.ci_hi",
        "e01_verifier_ab.json",
        "/summary/c_minus_a_share/ci95_hi",
        "upper end of the 95% interval for (C−A)/L",
        fmt=pct,
        split="test",
    ),
    # E11
    Spec(
        "e11.total_leaks",
        "e11_adversarial.json",
        "/summary/total_leaks",
        "attack outputs that reached the viewer",
        "lines",
    ),
    # E13 / E14 / E8 / E9 / E10 / E15 / E16
    Spec(
        "e13.best_tokens_per_s",
        "e13_serving_prefix_on.json",
        "/summary/best/tokens_per_s",
        "generated tokens per second at the best concurrency",
        "tokens/s",
        fmt=lambda x: f"{float(x):,.0f}",
    ),
    Spec(
        "e13.best_p95_s",
        "e13_serving_prefix_on.json",
        "/summary/best/p95_s",
        "p95 latency of a description request at that concurrency",
        "s",
        fmt=secs,
    ),
    Spec(
        "e13.usd_per_1000_lines",
        "e13_serving_prefix_on.json",
        "/summary/best/usd_per_1000_lines",
        "GPU cost per 1,000 description lines",
        "USD",
        fmt=money,
    ),
    Spec(
        "e14.bundle_usd_per_minute",
        "e14_cost.json",
        "/summary/batch/bundle_usd_per_finished_minute",
        "GPU cost per finished minute, all five versions",
        "USD",
        fmt=money,
    ),
    Spec(
        "e14.users_per_gpu",
        "e14_cost.json",
        "/summary/users_per_gpu",
        "simultaneous video jobs per MI300X at ≤ 1× real time",
        "jobs",
    ),
    Spec(
        "e08.hours",
        "e08_soak.json",
        "/summary/hours_run",
        "hours of continuous soak",
        "h",
        fmt=lambda x: f"{float(x):.1f}",
    ),
    Spec("e08.failed_jobs", "e08_soak.json", "/summary/jobs/failed", "failed jobs during the soak", "jobs"),
    Spec(
        "e10.python_blocked",
        "e10_offline.json",
        "/summary/python_blocked_attempts",
        "network attempts blocked in Python during the offline run",
        "attempts",
    ),
    Spec(
        "e10.host_packets",
        "e10_offline.json",
        "/summary/host_outbound_packets",
        "outbound packets counted on the host during the offline run",
        "packets",
    ),
    Spec("e16.player_passed", "e16_ui_a11y.json", "/summary/player/passed", "player accessibility tests passed (Playwright + axe-core)", "tests", split="none"),
    Spec("e16.player_total", "e16_ui_a11y.json", "/summary/player/total", "player accessibility tests run", "tests", split="none"),
    Spec("e16.review_passed", "e16_ui_a11y.json", "/summary/review/passed", "review-app accessibility tests passed (Playwright + axe-core)", "tests", split="none"),
    Spec("e16.review_total", "e16_ui_a11y.json", "/summary/review/total", "review-app accessibility tests run", "tests", split="none"),
    Spec(
        "e15.guard_ms",
        "e15_asr.json",
        "/summary/decision/guard_ms",
        "guard band around speech, from the measured p95 word-boundary error",
        "ms",
    ),
]


def register() -> dict[str, Any]:
    reg_p = EV / "public-claims.json"
    reg = json.loads(reg_p.read_text())
    by_id = {c["claim_id"]: c for c in reg["claims"]}
    for s in SPECS:
        f = EV / s.path
        if not f.exists():
            continue
        doc = json.loads(f.read_text())
        try:
            val = resolve_pointer(doc, s.pointer)
        except (KeyError, IndexError, ValueError):
            continue
        if val is None:
            continue
        by_id[s.claim_id] = {
            "claim_id": s.claim_id,
            "text": s.text,
            "value": val,
            "unit": s.unit,
            "status": "measured",
            "split": doc.get("split", s.split),
            "evidence": [{"path": f"evidence/{s.path}", "sha256": sha256_file(f), "pointer": s.pointer}],
            "public_files": [],
            "display": [s.fmt(val)],
        }
    cited = EV / "cited_claims.json"
    if cited.exists():
        for c in json.loads(cited.read_text()).get("verified", []):
            by_id[c["claim_id"]] = {**c, "evidence": [], "public_files": c.get("public_files", [])}
    reg["claims"] = sorted(by_id.values(), key=lambda c: c["claim_id"])
    reg_p.write_text(json.dumps(reg, indent=1, ensure_ascii=False) + "\n")
    return {c["claim_id"]: c for c in reg["claims"]}


def fill(claims: dict[str, Any]) -> int:
    n = 0
    for rel in PUBLIC_FILES:
        p = REPO_ROOT / rel
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8")

        def sub(m: re.Match[str], rel: str = rel) -> str:
            nonlocal n
            c = claims.get(m.group(1))
            if c and c.get("display"):
                n += 1
                if rel not in c["public_files"]:
                    c["public_files"].append(rel)
                return str(c["display"][0])
            return m.group(0)

        new = re.sub(r"<pending:\s*([\w.\-]+)\s*>", sub, text)
        if new != text:
            p.write_text(new, encoding="utf-8")
    reg_p = EV / "public-claims.json"
    reg = json.loads(reg_p.read_text())
    reg["claims"] = sorted(claims.values(), key=lambda c: c["claim_id"])
    reg_p.write_text(json.dumps(reg, indent=1, ensure_ascii=False) + "\n")
    return n


if __name__ == "__main__":
    claims = register()
    print(f"{len(claims)} claims registered")
    if "--fill" in sys.argv:
        print(f"{fill(claims)} placeholders filled")
    _ = Path
