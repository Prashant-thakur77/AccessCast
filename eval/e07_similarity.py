"""E7: how close is our description to W3C's human description? (PLAN §15.3, eval/PREREGISTRATION.md)

The one change: the description method. Three systems, each compared with W3C's human description track
(<id>_desc.en.vtt) on the test set (after the freeze; never used for tuning):
  accesscast   E1 arm C, seed 0: same plan, checks + up to 3 Gemma repairs, failures withheld (no human review)
  gemma_alone  E1 arm A, seed 0: same plan, attempt 0 as written, no checks
  naive        a per-gap captioner: Gemma describes the middle frame of each pause with the `naive_caption`
               prompt (no evidence, no plan, no checks)
Lines for accesscast and gemma_alone come from evidence/e01_verifier_ab.json when it covers the video under the
same freeze; otherwise they are generated exactly as E1 does (same run label, seeds and prompts).

Pairing: each human description cue is paired with the system's lines that START within ±3 s of the cue's start
(joined in time order). Unpaired cues get no similarity score; they show up in timing agreement instead.
Metrics per system:
  timing agreement  human cues with one of our line starts within ±3 s (k/N)
  BERTScore F1      microsoft/deberta-xlarge-mnli, paired cues only
  CIDEr-D           our own implementation of Vedantam et al. (2015), simple lowercase word tokenizer, document
                    frequencies from the human cues in this run; NOT comparable with published CIDEr numbers
  judge 1–5         a non-Gemma Token Factory model (prompt e07_judge, in the spirit of LLM-AD-eval), paired cues
Every timing and score is reported with n, mean, median, min and max. No significance language.

Usage: python -m eval.e07_similarity --judge-model <Token Factory model id> [--videos ids] [--dry-run]
"""

from __future__ import annotations

import argparse
import math
import re
import statistics
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from accesscast import constants as C
from accesscast.config import Settings, load_settings
from accesscast.errors import ConfigError, LlmOutputError, ModelEndpointError
from accesscast.llm.client import LlmClient, LlmRequest
from accesscast.seeds import derive_seed
from eval.common import Experiment, run_experiment
from eval.e04_translation import LogTail, Metrics, dry_run_env, one_served_model, write_outputs
from eval.e06_questions import DRY_HUMAN, answerer, answerer_served_id, e1_lines, human_description

WINDOW_MS = 3000  # PLAN §15.3: ±3 s, the same window as E1's coverage
SYSTEMS = ("accesscast", "gemma_alone", "naive")


# ------------------------------------------------------------------ pure helpers
def timing_agreement(
    human_starts: Sequence[int], our_starts: Sequence[int], window_ms: int = WINDOW_MS
) -> tuple[int, int]:
    """(k, N): human cue starts with at least one of our line starts within ±window_ms."""
    k = sum(1 for h in human_starts if any(abs(o - h) <= window_ms for o in our_starts))
    return k, len(human_starts)


def pair_lines(
    human: Sequence[tuple[int, str]], ours: Sequence[tuple[int, str]], window_ms: int = WINDOW_MS
) -> list[tuple[int, str, str]]:
    """(human index, human text, our lines starting within ±window_ms joined in time order; '' if none)."""
    out = []
    for k, (h, text) in enumerate(human):
        near = [t for s, t in sorted(ours) if abs(s - h) <= window_ms and t.strip()]
        out.append((k, text, " ".join(" ".join(x.split()) for x in near)))
    return out


def tokens(text: str) -> list[str]:
    return re.findall(r"[^\W_]+(?:['’][^\W_]+)*", text.lower())


def _ngrams(toks: Sequence[str], n: int) -> Counter[tuple[str, ...]]:
    return Counter(tuple(toks[i : i + n]) for i in range(len(toks) - n + 1))


def cider_d(
    cands: Sequence[str], refs: Sequence[Sequence[str]], n: int = 4, sigma: float = 6.0
) -> list[float]:
    """CIDEr-D per candidate (Vedantam, Zitnick, Parikh, CVPR 2015), implemented from the paper's description:
    tf-idf n-gram vectors (n = 1..4) with document frequencies over the reference sets, clipped candidate
    weights, a Gaussian length penalty (sigma 6), averaged over n and references, times 10."""
    if len(cands) != len(refs):
        raise ValueError("one reference set per candidate")
    if not cands:
        return []
    ref_toks = [[tokens(r) for r in rs] for rs in refs]
    df: Counter[tuple[str, ...]] = Counter()
    for rs in ref_toks:
        df.update({g for r in rs for k in range(1, n + 1) for g in _ngrams(r, k)})
    log_n = math.log(float(len(refs)))

    def vec(toks: list[str]) -> tuple[list[dict[tuple[str, ...], float]], list[float]]:
        vs, norms = [], []
        for k in range(1, n + 1):
            v = {g: tf * (log_n - math.log(max(1.0, df[g]))) for g, tf in _ngrams(toks, k).items()}
            vs.append(v)
            norms.append(math.sqrt(sum(x * x for x in v.values())))
        return vs, norms

    out = []
    for cand, rs in zip(cands, ref_toks, strict=True):
        ct = tokens(cand)
        cv, cn = vec(ct)
        total = 0.0
        for r in rs:
            rv, rn = vec(r)
            delta = len(ct) - len(r)
            per_n = []
            for k in range(n):
                val = sum(min(w, rv[k].get(g, 0.0)) * rv[k].get(g, 0.0) for g, w in cv[k].items())
                if cn[k] != 0 and rn[k] != 0:
                    val /= cn[k] * rn[k]
                per_n.append(val * math.exp(-(delta**2) / (2 * sigma**2)))
            total += sum(per_n) / n
        out.append(10.0 * total / max(1, len(rs)))
    return out


def describe(xs: Sequence[float]) -> dict[str, Any]:
    if not xs:
        return {"n": 0}
    return {
        "n": len(xs),
        "mean": statistics.fmean(xs),
        "median": statistics.median(xs),
        "min": min(xs),
        "max": max(xs),
    }


# ------------------------------------------------------------------ the naive captioner baseline
def naive_lines(
    settings: Settings, v: dict[str, Any], split: str, provider: str
) -> tuple[list[tuple[int, str]], int, str | None]:
    """Gemma describes the middle frame of each pause (prompt naive_caption): no evidence, no plan, no checks.
    Returns (lines, failed calls, served model id); a failed call publishes nothing for that pause."""
    from accesscast.media.ingest import extract_frame
    from accesscast.pipeline import ANALYSIS, open_run, stage_ingest, verify_context
    from accesscast.tts.engine import VOICES, load_calibration
    from accesscast.write.plan_ad import words_budget

    proj = stage_ingest(settings, Path(v["video"]))
    label = f"e07:naive:{split}"
    run = open_run(settings, proj, provider=provider, strict=True, run_label=label)
    if not proj.p("analysis", "gaps.json").exists():
        for _n, fn in ANALYSIS:
            fn(run)
    ctx = verify_context(proj, "en")
    cal = load_calibration(VOICES["en"])
    tail = LogTail(proj.p("logs", "llm_calls.jsonl"))
    lines, failed = [], 0
    for g in sorted(ctx.gaps.values(), key=lambda g: g.start_ms):
        mid = (g.start_ms + g.end_ms) // 2
        frame = extract_frame(
            proj.p("media", "proxy480.mp4"), mid, proj.p("eval", "e07", "naive", f"{g.gap_id}.jpg")
        )
        try:
            r = run.client.call(
                LlmRequest(
                    "naive_caption",
                    {"words_max": words_budget(g.len_ms, cal)},
                    seed=derive_seed(settings.project_seed, f"{label}:{g.gap_id}"),
                    images=[frame],
                    label=f"naive_caption:{g.gap_id}",
                )
            )
            text = str(r.obj.get("text", "")).strip()
        except (LlmOutputError, ModelEndpointError):
            text = ""
        if text:
            lines.append((g.start_ms + C.AD_PAD_BEFORE_MS, text))
        else:
            failed += 1
    return lines, failed, one_served_model(tail)


def judge(client: LlmClient, reference: str, candidate: str, seed: int) -> tuple[int | None, str | None]:
    try:
        r = client.call(
            LlmRequest(
                "e07_judge", {"reference": reference, "candidate": candidate}, seed=seed, label="e07_judge"
            )
        )
    except (LlmOutputError, ModelEndpointError) as ex:
        return None, f"{type(ex).__name__}: {str(ex)[:200]}"
    s = r.obj.get("score")
    if isinstance(s, str) and s.strip().isdigit():
        s = int(s)
    if not isinstance(s, int) or isinstance(s, bool) or not 1 <= s <= 5:
        return None, f"bad score {s!r}"
    return s, None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--judge-model", default="", help="Token Factory model id; must not be a Gemma model")
    ap.add_argument("--videos", default="")
    ap.add_argument("--provider", default="local")
    ap.add_argument("--allow-cpu", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--real-metrics", action="store_true")
    args = ap.parse_args()
    dry_run_env(args.dry_run)
    settings = load_settings()
    split = "dev" if args.dry_run else "test"
    model = args.judge_model or ("fake-judge" if args.dry_run else "")
    stand_in = settings.worker_mode == "fake" and not args.real_metrics
    exp = Experiment(
        "e07_similarity",
        split,
        config={
            "question": "How close is our description to W3C's human description?",
            "one_change": "description method",
            "systems": {
                "accesscast": "E1 arm C, seed 0 (checks + Gemma repair, no human review)",
                "gemma_alone": "E1 arm A, seed 0 (same plan, no checks)",
                "naive": "Gemma describes the middle frame of each pause (naive_caption; no evidence/plan/checks)",
            },
            "reference": "W3C human description track (<id>_desc.en.vtt)",
            "window_ms": WINDOW_MS,
            "pairing": "human cue ↔ our lines starting within ±3 s; unpaired cues are not similarity-scored",
            "cider": "CIDEr-D, own implementation, simple tokenizer; not comparable with published CIDEr",
            "bertscore": "microsoft/deberta-xlarge-mnli F1, not rescaled",
            "judge_model_requested": model,
            "judge_provider": "tokenfactory",
            "provider": args.provider,
            "strict_provider": True,
            "worker_mode": settings.worker_mode,
            "metrics_stand_in": stand_in,
            "dry_run": args.dry_run,
        },
    )

    def body(e: Experiment) -> None:
        from eval.e01_verifier_ab import video_list

        if not model:
            raise ConfigError("--judge-model is required (a non-Gemma model listed by Token Factory)")
        metrics = Metrics(
            e.experiment,
            stand_in=stand_in,
            require_rocm=settings.worker_mode == "real" and not args.allow_cpu,
        )
        jclient, jtail = answerer(settings, e.experiment, model)
        vids = (
            video_list("dev", ["fixture20"])
            if args.dry_run
            else video_list("test", [x for x in args.videos.split(",") if x])
        )
        if not vids:
            raise RuntimeError("no videos")
        pairs: list[dict[str, Any]] = []
        e.summary["timing_agreement"] = {s: {"k": 0, "n": 0} for s in SYSTEMS}
        e.summary["lines"] = {s: 0 for s in SYSTEMS}
        naive_failed = 0
        gemma_ids: set[str] = set()
        for v in vids:
            human = DRY_HUMAN if args.dry_run else human_description(v)
            e1 = e1_lines(settings, v, split, args.provider, e.freeze_tag)
            naive, nf, served = naive_lines(settings, v, split, args.provider)
            naive_failed += nf
            gemma_ids |= {served} if served else set()
            for sname, lines in (("accesscast", e1["C"]), ("gemma_alone", e1["A"]), ("naive", naive)):
                k, n = timing_agreement([h for h, _ in human], [s for s, _ in lines])
                ta = e.summary["timing_agreement"][sname]
                ta["k"], ta["n"] = ta["k"] + k, ta["n"] + n
                e.summary["lines"][sname] += len(lines)
                for hi, htext, cand in pair_lines(human, lines):
                    pairs.append(
                        {
                            "video": v["id"],
                            "system": sname,
                            "human_index": hi,
                            "reference": htext,
                            "candidate": cand,
                            "paired": bool(cand),
                        }
                    )
        paired = [p for p in pairs if p["paired"]]
        if paired:
            f1 = metrics(
                "bertscore",
                {
                    "cands": [p["candidate"] for p in paired],
                    "refs": [p["reference"] for p in paired],
                    "lang": "en",
                },
            )["F1"]
            for p, f in zip(paired, f1, strict=True):
                p["bertscore_f1"] = f
        for sname in SYSTEMS:
            ps = [p for p in paired if p["system"] == sname]
            for p, c in zip(
                ps, cider_d([p["candidate"] for p in ps], [[p["reference"]] for p in ps]), strict=True
            ):
                p["cider_d"] = c
        for p in paired:
            p["judge_score"], p["judge_error"] = judge(
                jclient,
                p["reference"],
                p["candidate"],
                derive_seed(settings.project_seed, f"e07:{p['video']}:{p['system']}:{p['human_index']}"),
            )
        e.summary["systems"] = {}
        for sname in SYSTEMS:
            ps = [p for p in paired if p["system"] == sname]
            allp = [p for p in pairs if p["system"] == sname]
            e.summary["systems"][sname] = {
                "human_cues_paired": {"k": len(ps), "n": len(allp)},
                "bertscore_f1": describe([p["bertscore_f1"] for p in ps]),
                "cider_d": describe([p["cider_d"] for p in ps]),
                "judge_1_to_5": describe(
                    [float(p["judge_score"]) for p in ps if p["judge_score"] is not None]
                ),
                "judge_errors": sum(1 for p in ps if p["judge_error"]),
            }
        e.summary["naive_failed_calls"] = naive_failed
        keep_text = split != "test"
        e.results = [
            p if keep_text else {k: v for k, v in p.items() if k not in ("reference", "candidate")}
            for p in pairs
        ]
        e.summary["outputs"] = write_outputs(e.experiment, f"pairs_{split}", pairs)
        e.summary["judge_served_model_id"] = answerer_served_id(jtail)
        e.summary["metric_models"] = metrics.meta
        e.summary["note"] = (
            "Similarity to one human describer's track, on paired cues only; timing agreement "
            "shows how many human cues were paired. CIDEr-D here is our own implementation."
        )
        if len(gemma_ids) > 1:
            raise ModelEndpointError(f"naive captions served by more than one model id: {sorted(gemma_ids)}")
        e.summary["naive_served_model_id"] = next(iter(gemma_ids), None)
        e.checks["every_paired_cue_judged"] = all(p["judge_error"] is None for p in paired)
        e.checks["strict_provider"] = True

    return run_experiment(exp, body)


if __name__ == "__main__":
    raise SystemExit(main())
