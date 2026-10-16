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
        "e14.tokens_per_minute",
        "e14_cost.json",
        "/summary/tokens_per_finished_minute",
        "Gemma tokens per finished minute of video, all five versions (dev set)",
        "tokens",
        fmt=lambda x: f"{float(x):,.0f}",
    ),
    Spec(
        "e13.failed",
        "e13_serving_tokenfactory.json",
        "/summary/failed",
        "Gemma requests to AMD Token Factory that failed during the speed test",
        "requests",
    ),
    Spec(
        "e13.requests",
        "e13_serving_tokenfactory.json",
        "/summary/requests",
        "Gemma requests sent to AMD Token Factory during the speed test",
        "requests",
    ),
    Spec(
        "e13.best_tokens_per_s",
        "e13_serving_tokenfactory.json",
        "/summary/best/tokens_per_s",
        "generated tokens per second seen by our client, Gemma 4 31B on AMD Token Factory, best concurrency",
        "tokens/s",
        fmt=lambda x: f"{float(x):,.0f}",
    ),
    Spec(
        "e13.best_p95_s",
        "e13_serving_tokenfactory.json",
        "/summary/best/p95_s",
        "client-side p95 latency of a Gemma request on AMD Token Factory at that concurrency",
        "s",
        fmt=secs,
    ),
    Spec(
        "e1.pub_a",
        "e01_verifier_ab.json",
        "/summary/pooled/A/lines_published",
        "lines published, arm A",
        "lines",
        split="test",
    ),
    Spec(
        "e1.pub_b",
        "e01_verifier_ab.json",
        "/summary/pooled/B/lines_published",
        "lines published, arm B",
        "lines",
        split="test",
    ),
    Spec(
        "e1.pub_c",
        "e01_verifier_ab.json",
        "/summary/pooled/C/lines_published",
        "lines published, arm C",
        "lines",
        split="test",
    ),
    Spec(
        "e1.sent_b",
        "e01_verifier_ab.json",
        "/summary/pooled/B/sent_to_person",
        "lines sent to a person in arm B",
        "lines",
        split="test",
    ),
    Spec(
        "e1.cov_a",
        "e01_verifier_ab.json",
        "/summary/coverage_share/A",
        "share of human description positions covered, arm A",
        fmt=pct,
        split="test",
    ),
    Spec(
        "e1.cov_c",
        "e01_verifier_ab.json",
        "/summary/coverage_share/C",
        "share of human description positions covered, arm C",
        fmt=pct,
        split="test",
    ),
    Spec(
        "e09.summary",
        "e09_determinism.json",
        "/summary/all_artefacts_identical",
        "whether every artefact was byte-identical across runs",
        fmt=lambda x: (
            "every artefact byte-identical across 5 fresh runs"
            if x
            else "not every artefact was byte-identical (details in the evidence file)"
        ),
    ),
    Spec(
        "e16.player_passed",
        "e16_ui_a11y.json",
        "/summary/player/passed",
        "player accessibility tests passed (Playwright + axe-core)",
        "tests",
        split="none",
    ),
    Spec(
        "e16.player_total",
        "e16_ui_a11y.json",
        "/summary/player/total",
        "player accessibility tests run",
        "tests",
        split="none",
    ),
    Spec(
        "e16.review_passed",
        "e16_ui_a11y.json",
        "/summary/review/passed",
        "review-app accessibility tests passed (Playwright + axe-core)",
        "tests",
        split="none",
    ),
    Spec(
        "e16.review_total",
        "e16_ui_a11y.json",
        "/summary/review/total",
        "review-app accessibility tests run",
        "tests",
        split="none",
    ),
    Spec(
        "e15.wer_en_turbo",
        "e15_asr.json",
        "/summary/accuracy/openai~1whisper-large-v3-turbo/en/wer",
        "English word error rate, Whisper large-v3-turbo, FLEURS (dev)",
        fmt=lambda x: f"{float(x) * 100:.1f}%",
    ),
    Spec(
        "e15.wer_en_large",
        "e15_asr.json",
        "/summary/accuracy/openai~1whisper-large-v3/en/wer",
        "English word error rate, Whisper large-v3, FLEURS (dev)",
        fmt=lambda x: f"{float(x) * 100:.1f}%",
    ),
    Spec(
        "e15.wer_hi_turbo",
        "e15_asr.json",
        "/summary/accuracy/openai~1whisper-large-v3-turbo/hi/wer",
        "Hindi word error rate, Whisper large-v3-turbo, FLEURS (dev)",
        fmt=lambda x: f"{float(x) * 100:.1f}%",
    ),
    Spec(
        "e15.wer_it_turbo",
        "e15_asr.json",
        "/summary/accuracy/openai~1whisper-large-v3-turbo/it/wer",
        "Italian word error rate, Whisper large-v3-turbo, FLEURS (dev)",
        fmt=lambda x: f"{float(x) * 100:.1f}%",
    ),
    Spec(
        "e15.n_per_lang",
        "e15_asr.json",
        "/summary/accuracy/openai~1whisper-large-v3-turbo/en/n",
        "FLEURS clips per language",
        "clips",
    ),
    Spec(
        "e15.boundary_aligned_median",
        "e15_asr.json",
        "/summary/boundary_error/openai~1whisper-large-v3-turbo/aligned/median_ms",
        "median word-boundary error after forced alignment (synthetic dev clips)",
        "ms",
        fmt=lambda x: f"{float(x):.0f} ms",
    ),
    Spec(
        "e15.boundary_aligned_p95",
        "e15_asr.json",
        "/summary/boundary_error/openai~1whisper-large-v3-turbo/aligned/p95_ms",
        "95th-percentile word-boundary error after forced alignment",
        "ms",
        fmt=lambda x: f"{float(x):.0f} ms",
    ),
    Spec(
        "e15.boundary_raw_p95",
        "e15_asr.json",
        "/summary/boundary_error/openai~1whisper-large-v3-turbo/raw/p95_ms",
        "95th-percentile word-boundary error of raw Whisper timestamps",
        "ms",
        fmt=lambda x: f"{float(x):.0f} ms",
    ),
    Spec(
        "e15.boundary_n",
        "e15_asr.json",
        "/summary/boundary_error/openai~1whisper-large-v3-turbo/aligned/n",
        "word boundaries measured",
        "words",
    ),
    Spec(
        "e15.guard_ms",
        "e15_asr.json",
        "/summary/decision/guard_ms",
        "guard band around speech, from the measured p95 word-boundary error",
        "ms",
    ),
]


def e11_specs() -> list[Spec]:
    f = EV / "e11_adversarial.json"
    if not f.exists():
        return []
    out = []
    for case, st in json.loads(f.read_text())["summary"].get("cases", {}).items():
        for setting in st:
            for key in ("tries", "gemma_failed", "blocked", "leaks"):
                out.append(
                    Spec(
                        f"e11.{case}.{setting}.{key}",
                        "e11_adversarial.json",
                        f"/summary/cases/{case}/{setting}/{key}",
                        f"E11 {case} ({setting}): {key}",
                        "tries",
                    )
                )
    return out


def e11_table() -> str | None:
    f = EV / "e11_adversarial.json"
    if not f.exists():
        return None
    cases = json.loads(f.read_text())["summary"].get("cases", {})
    lines = [
        "| Case | Gemma failed (production) | Blocked | Reached the viewer | Gemma failed (stress) |",
        "|---|---|---|---|---|",
    ]
    for c in cases:
        lines.append(
            f"| {c} | <pending: e11.{c}.production.gemma_failed> of <pending: e11.{c}.production.tries> | "
            f"<pending: e11.{c}.production.blocked> | <pending: e11.{c}.production.leaks> | "
            f"<pending: e11.{c}.stress.gemma_failed> of <pending: e11.{c}.stress.tries> |"
        )
    return "\n".join(lines)


def e13_failed_sentence() -> str | None:
    if not (EV / "e13_serving_tokenfactory.json").exists():
        return None
    return "<pending: e13.failed> of <pending: e13.requests> requests failed (client-side, dev requests replayed)."


def results_more() -> str | None:
    """Plain-words lines for every experiment that has run, regenerated on each build (markers keep the block)."""
    rows = []
    if (EV / "e15_asr.json").exists():
        rows.append(
            "- **Speech recognition (E15, dev set).** We chose Whisper large-v3-turbo: its English word error rate was "
            "<pending: e15.wer_en_turbo> on <pending: e15.n_per_lang> FLEURS clips, against <pending: e15.wer_en_large> "
            "for the larger large-v3 (Hindi <pending: e15.wer_hi_turbo>, Italian <pending: e15.wer_it_turbo>). After "
            "forced alignment, word boundaries were off by <pending: e15.boundary_aligned_median> at the median and "
            "<pending: e15.boundary_aligned_p95> at the 95th percentile (raw Whisper: <pending: e15.boundary_raw_p95>), "
            "on <pending: e15.boundary_n> word boundaries of our synthetic clips, so description keeps "
            "<pending: e15.guard_ms> ms clear of speech. Large-v3 could not produce word timings within our "
            "computer's memory, so it was not a candidate."
        )
    if (EV / "e16_ui_a11y.json").exists():
        rows.append(
            "- **Accessibility (E16).** Automatic tests with keyboard-only runs and axe-core scans pass: player "
            "<pending: e16.player_passed> of <pending: e16.player_total>, review app and Studio "
            "<pending: e16.review_passed> of <pending: e16.review_total>. No blind tester has used it yet."
        )
    return "\n".join(rows) if rows else None


SECTIONS: dict[str, Callable[[], str | None]] = {
    "e11.table": e11_table,
    "e13.failed_sentence": e13_failed_sentence,
    "results.more": results_more,
}
REGENERATED = ("results.more",)  # kept between markers and rebuilt every time, as experiments land


def register() -> dict[str, Any]:
    reg_p = EV / "public-claims.json"
    reg = json.loads(reg_p.read_text())
    by_id = {c["claim_id"]: c for c in reg["claims"]}
    for s in [*SPECS, *e11_specs()]:
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
        for (
            sec,
            gen,
        ) in SECTIONS.items():  # expand generated sections first; their cells are claim placeholders
            start, end = f"<!-- {sec}:start -->", f"<!-- {sec}:end -->"
            if sec in REGENERATED and start in text and end in text:
                block = gen()
                if block:
                    a, b = text.index(start) + len(start), text.index(end)
                    text = text[:a] + "\n" + block + "\n" + text[b:]
                continue
            block = gen() if f"<pending: {sec}>" in text else None
            if block:
                wrapped = f"{start}\n{block}\n{end}" if sec in REGENERATED else block
                text = text.replace(f"<pending: {sec}>", wrapped)

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
