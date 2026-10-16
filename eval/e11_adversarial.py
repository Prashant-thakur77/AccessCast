"""E11: does the guard catch the REAL model live, in the same run? (PLAN §17)

Each case runs K tries at the production temperature and K at temperature 1.0 (labelled stress), each with its
own seed (run_label e11:<case>:<temp>:<try>). Per try:
  gemma_failed  — the case's ORACLE (defined here, independent of AccessCast's rules) is true on Gemma's attempt 0
  reached_viewer — the oracle is true on the text that would be published (passed every check, after repair)
  blocked        — gemma_failed and not reached_viewer
Leaks must be 0. If Gemma never fails a case we say so ("the rule never had to fire").

Usage: python -m eval.e11_adversarial [--k 20] [--cases A2_name_bait,...] [--provider local]
"""

from __future__ import annotations

import argparse
import json
import re
from typing import Any

from accesscast import constants as C
from accesscast.config import REPO_ROOT, load_settings
from accesscast.pipeline import ANALYSIS, open_run, stage_evidence, stage_ingest, verify_context
from accesscast.schemas import Item, ItemKind, ItemStatus
from accesscast.tts.engine import VOICES, load_calibration
from accesscast.write.plan_ad import plan_description
from accesscast.write.text_versions import TextOptions, make_easy, make_subtitles
from accesscast.write.write_ad import WriteOptions, verify_and_repair, write_drafts
from eval.common import Experiment, run_experiment

ADV = REPO_ROOT / "data" / "adversarial"
spans_final: dict[int, tuple[int, int]] = {}  # per try: index → span of the published (repaired) text


def _quoted_ok(text: str, phrase: str) -> bool:
    """True if every occurrence of phrase sits inside an explicit quote or after an 'On screen:'-style frame."""
    low = text.lower()
    if phrase not in low:
        return True
    framed = re.search(r"(on screen|reads|sullo schermo|स्क्रीन पर)\s*:", low)
    quoted = re.search(r"[\"“'][^\"”']*" + re.escape(phrase) + r"[^\"”']*[\"”']", low)
    return bool(framed or quoted)


def oracle(
    spec: dict[str, Any],
    text: str,
    *,
    span: tuple[int, int] | None = None,
    speech: list[tuple[int, int]] | None = None,
) -> bool:
    """True when the output shows the failure the case baits. Independent of verify/ code."""
    o = spec["oracle"]
    low = f" {text.lower()} "
    if o["type"] == "contains":
        return any(p in low for p in o["any"])
    if o["type"] == "unquoted":
        return any(not _quoted_ok(text, p) for p in o["any"])
    if o["type"] == "missing":
        return any(not re.search(r"\b(" + alt + r")", low) for alt in o["all"])
    if o["type"] == "latin_fraction":
        letters = [c for c in text if c.isalpha()]
        return bool(letters) and sum(1 for c in letters if c.isascii()) / len(letters) > o["max"]
    if o["type"] == "overlap":
        if span is None or speech is None:
            return False
        return any(min(span[1], b) - max(span[0], a) > 50 for a, b in speech)
    raise ValueError(o["type"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=20)
    ap.add_argument("--cases", default="")
    ap.add_argument("--provider", default="local")
    args = ap.parse_args()
    settings = load_settings()
    cases = sorted(p.stem for p in ADV.glob("*.json"))
    if args.cases:
        cases = [c for c in cases if c in args.cases.split(",")]
    exp = Experiment(
        "e11_adversarial",
        "dev",
        config={
            "k": args.k,
            "temperatures": {"production": C.TEMP_WRITE, "stress": C.TEMP_STRESS},
            "cases": cases,
            "provider": args.provider,
            "strict_provider": True,
            "worker_mode": settings.worker_mode,
            "oracles": "eval/e11_adversarial.py (independent of verify/)",
        },
    )

    def body(e: Experiment) -> None:
        for case in cases:
            spec = json.loads((ADV / f"{case}.json").read_text())
            proj = stage_ingest(settings, ADV / f"{case}.mp4")
            base = open_run(settings, proj, provider=args.provider, strict=True)
            if not proj.p("analysis", "gaps.json").exists():
                for _n, fn in ANALYSIS:
                    fn(base)
            if not any(proj.p("evidence").glob("*/evidence.json")):
                stage_evidence(base)
            ctx = verify_context(proj, "en")
            speech_truth = [(w["start_ms"], w["end_ms"]) for w in spec.get("synth_words", [])]
            cal = load_calibration(VOICES["en"])
            ctx.wps_voice = cal.wps_voice
            kind = spec.get("kind", "ad")
            for temp_name, temp in (("production", None), ("stress", C.TEMP_STRESS)):
                stats = {"tries": 0, "gemma_failed": 0, "blocked": 0, "leaks": 0, "no_output": 0}
                for k in range(args.k):
                    label = f"e11:{case}:{temp_name}:{k}"
                    run = open_run(settings, proj, provider=args.provider, strict=True, run_label=label)
                    spans_final.clear()
                    rows = _one_try(run, ctx, cal, kind, temp, label, settings.project_seed)
                    for k_row, (draft, final, published, span) in enumerate(rows):
                        failed = oracle(spec, draft, span=span, speech=speech_truth)
                        final_span = spans_final.get(
                            k_row, span
                        )  # the published text's own length, not the draft's
                        leak = published and oracle(spec, final, span=final_span, speech=speech_truth)
                        stats["tries"] += 1
                        stats["gemma_failed"] += int(failed)
                        stats["leaks"] += int(leak)
                        stats["blocked"] += int(failed and not leak)
                        stats["no_output"] += int(not draft.strip())
                        e.results.append(
                            {
                                "case": case,
                                "setting": temp_name,
                                "try": k,
                                "draft": draft,
                                "final": final,
                                "published": published,
                                "gemma_failed": failed,
                                "reached_viewer": leak,
                            }
                        )
                e.summary.setdefault("cases", {}).setdefault(case, {})[temp_name] = stats
        cs = e.summary.get("cases", {})
        e.summary["total_leaks"] = sum(s[t]["leaks"] for s in cs.values() for t in s)
        prod = {c: s["production"]["gemma_failed"] / max(1, s["production"]["tries"]) for c, s in cs.items()}
        e.summary["highest_failure_case_production"] = max(prod, key=lambda c: prod[c]) if prod else None
        e.checks["no_leaks"] = e.summary["total_leaks"] == 0
        e.checks["ran_all_cases"] = len(cs) == len(cases)

    return run_experiment(exp, body)


def _one_try(
    run: Any, ctx: Any, cal: Any, kind: str, temp: float | None, label: str, seed: int
) -> list[tuple[str, str, bool, tuple[int, int] | None]]:
    """Returns (attempt-0 text, published-candidate text, published?, span) per line produced in this try."""
    if kind == "ad":
        plans = [p for p in plan_description(list(ctx.gaps.values()), ctx.evidence, ctx.words, ctx.vad, cal)]
        if not plans:
            return []
        opts = WriteOptions(run_label=label, project_seed=seed, temperature=temp)
        drafts = write_drafts(run.client, plans, ctx.evidence, ctx, opts)
        items = verify_and_repair(run.client, plans, drafts, ctx, opts)
        out = []
        for it in items:
            published = it.status == ItemStatus.PENDING and not it.violations
            start = it.anchor_ms + C.AD_PAD_BEFORE_MS
            span = (start, start + round(len(it.draft.split()) / cal.wps_voice * 1000))
            out.append((it.draft, it.text, published, span))
            spans_final[len(out) - 1] = (start, start + round(len(it.text.split()) / cal.wps_voice * 1000))
        return out
    from accesscast.captions.segment import segment_sdh

    sdh = segment_sdh(ctx.words, ctx.sounds, ctx.fps, 10**7)
    topts = TextOptions(run_label=label, project_seed=seed, temperature=temp)
    res: list[Item] = (
        make_easy(run.client, sdh, ctx, topts)
        if kind == "easy"
        else make_subtitles(run.client, sdh, "hi", ctx, topts)
    )
    return [
        (
            i.repair.history[0].text if i.repair.history else i.draft,
            i.text,
            i.status == ItemStatus.PENDING and not i.violations,
            None,
        )
        for i in res
        if i.kind in (ItemKind.EASY, ItemKind.SUBTITLE)
    ]


if __name__ == "__main__":
    raise SystemExit(main())
