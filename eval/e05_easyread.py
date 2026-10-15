"""E5: are easy-read captions easier to read without changing the meaning? (PLAN §15.3, eval/PREREGISTRATION.md)

The one change: the rewrite method.
  gemma_alone  Gemma 4 31B, the same `easy` prompt, no checks: attempt 0 as written, for every cue
  accesscast   the same attempt 0, then our easy-read checks and up to 3 Gemma repairs; a cue that still fails
               goes to a person, so this arm publishes only the cues that pass
Both arms share one attempt-0 draft per cue. Reference: the unsimplified caption text.

E5 is LED BY A PERSON: this script exports a blind rating sheet (30 cues, both arms' rewrites, shuffled, arm
hidden) with the columns "easier_to_read (1-5)" and "same_meaning (yes/no)". The key is written separately and
is git-ignored. The automatic numbers here are secondary and OVERLAP WITH OUR OWN RULES (reading rate, sentence
length, numbers, negations), so they partly measure what the checks enforce; every report says so.
Automatic metrics: share of cues at or under 130 words per minute (k/N), mean words per sentence, Flesch reading
ease (English, textstat), numbers kept, negations kept (both implemented here, independent of verify/), and
BERTScore F1 against the original caption.

Data: --split test = W3C's human caption cues (after the freeze; never used for tuning); --split dev = our SDH
cues on the dev clips. `--simpitiki N` adds an Italian check on N SIMPITIKI pairs (CC-BY-4.0): Gemma's easy
rewrite against the person-made simplification, by sentence length, Gulpease, numbers (digits only), negations
and LaBSE similarity to the original. SIMPITIKI pairs are single edits, not full easy-read rewrites.

Usage: python -m eval.e05_easyread --split dev|test [--videos ids] [--simpitiki 60] [--dry-run [--real-metrics]]
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import statistics
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from accesscast import constants as C
from accesscast.config import REPO_ROOT, Settings, load_settings
from accesscast.schemas import Item, ItemStatus
from eval.common import Experiment, run_experiment
from eval.e04_translation import (
    EVAL_WORK,
    Metrics,
    dry_run_env,
    gemma_client,
    one_served_model,
    read_vtt_cues,
    sdh_items,
    write_outputs,
)

WPM_MAX = (
    130  # PLAN §10.3 / constants.EASY_WPM_MAX (DCMP Captioning Key); restated here so the eval is independent
)
SHEET_N = 30
ARMS = ("gemma_alone", "accesscast")

# ------------------------------------------------------------------ independent text measures (no verify/ code)
_EN_UNITS = (
    "zero",
    "",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
    "twenty",
)
_EN_NUM_WORDS = {w: str(i) for i, w in enumerate(_EN_UNITS) if w}
_EN_NUM_WORDS |= {
    "thirty": "30",
    "forty": "40",
    "fifty": "50",
    "sixty": "60",
    "seventy": "70",
    "eighty": "80",
    "ninety": "90",
    "hundred": "100",
    "thousand": "1000",
    "million": "1000000",
}
# "one" is left out on purpose: it is far more often a pronoun ("no one", "the one") than a number.
_NEG = {
    "en": {"not", "no", "never", "none", "nobody", "nothing", "nowhere", "neither", "nor", "cannot"},
    "it": {"non", "mai", "nessuno", "nessuna", "niente", "nulla", "né", "neanche", "nemmeno", "neppure"},
}


def words(text: str) -> list[str]:
    return re.findall(r"[^\W_]+(?:['’][^\W_]+)*", text.lower())


def sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?…])\s+|\n+", text.strip())
    return [p for p in parts if words(p)]


def words_per_sentence(text: str) -> float | None:
    s = sentences(text)
    return None if not s else sum(len(words(x)) for x in s) / len(s)


def wpm(text: str, dur_ms: int) -> float:
    return len(words(text)) / max(dur_ms, 1) * 60_000


def numbers(text: str, lang: str = "en") -> Counter[str]:
    """Numbers as normalised strings: digits (thousands separators dropped), and English number words → digits.
    Italian: digits only."""
    out: Counter[str] = Counter()
    low = text.lower()
    for m in re.findall(r"\d+(?:[.,]\d+)*", low):
        t = m.replace(",", "") if re.fullmatch(r"\d{1,3}(?:,\d{3})+", m) else m.replace(",", ".")
        out[t.rstrip("0").rstrip(".") if "." in t else t] += 1
    if lang == "en":
        for w in re.findall(r"[a-z]+", low):
            if w in _EN_NUM_WORDS:
                out[_EN_NUM_WORDS[w]] += 1
    return out


def negation_count(text: str, lang: str = "en") -> int:
    toks = words(text)
    n = sum(1 for t in toks if t in _NEG.get(lang, set()))
    if lang == "en":
        n += sum(1 for t in toks if t.endswith("n't") or t.endswith("n’t"))
    return n


def numbers_kept(src: str, out: str, lang: str = "en") -> bool:
    """Every number in the source appears in the rewrite (at least as often)."""
    return not (numbers(src, lang) - numbers(out, lang))


def negations_kept(src: str, out: str, lang: str = "en") -> bool:
    """Same number of negations as the source (a dropped or added 'not' can flip the meaning)."""
    return negation_count(src, lang) == negation_count(out, lang)


def gulpease(text: str) -> float | None:
    """Gulpease index (Lucisano & Piemontese 1988): 89 + (300 × sentences − 10 × letters) / words."""
    w = words(text)
    if not w:
        return None
    letters = sum(1 for c in text if c.isalpha())
    return 89 + (300 * max(1, len(sentences(text))) - 10 * letters) / len(w)


def flesch_en(text: str) -> float | None:
    import textstat

    return float(textstat.flesch_reading_ease(text)) if words(text) else None


def _mean(xs: Sequence[float | None]) -> float | None:
    v = [x for x in xs if x is not None]
    return statistics.fmean(v) if v else None


def describe(rows: Sequence[dict[str, Any]], key: str) -> dict[str, Any]:
    v = [r[key] for r in rows if r.get(key) is not None]
    if not v:
        return {"n": 0}
    return {
        "n": len(v),
        "mean": statistics.fmean(v),
        "median": statistics.median(v),
        "min": min(v),
        "max": max(v),
    }


def arm_block(rows: Sequence[dict[str, Any]], text_key: str) -> dict[str, Any]:
    """Automatic measures over the given cues (k/N next to every share)."""
    n = len(rows)
    ok = [r for r in rows if r[text_key].strip()]
    m: list[dict[str, Any]] = [
        {
            "wpm": wpm(r[text_key], r["dur_ms"]),
            "wps": words_per_sentence(r[text_key]),
            "flesch": flesch_en(r[text_key]),
            "num": numbers_kept(r["source"], r[text_key]),
            "neg": negations_kept(r["source"], r[text_key]),
            "bert": r.get(f"bertscore_{text_key}"),
        }
        for r in ok
    ]
    return {
        "cues": n,
        "empty": n - len(ok),
        "at_or_under_130_wpm": {"k": sum(1 for x in m if x["wpm"] <= WPM_MAX), "n": len(m)},
        "words_per_sentence": describe(m, "wps"),
        "flesch_reading_ease_en": describe(m, "flesch"),
        "numbers_kept": {"k": sum(1 for x in m if x["num"]), "n": len(m)},
        "negations_kept": {"k": sum(1 for x in m if x["neg"]), "n": len(m)},
        "bertscore_f1_vs_source": describe(m, "bert"),
    }


def blind_sheet(
    rows: Sequence[dict[str, Any]], n: int, seed: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Pick n cues that have text in both arms; one row per (cue, arm), shuffled. Returns (sheet, key)."""
    rng = random.Random(seed)
    eligible = [r for r in rows if r["gemma_alone"].strip() and r["accesscast"].strip()]
    picked = rng.sample(eligible, min(n, len(eligible)))
    pairs = [(r, a) for r in picked for a in ARMS]
    rng.shuffle(pairs)
    sheet, key = [], []
    for k, (r, a) in enumerate(pairs):
        sheet.append(
            {
                "row": k,
                "original": r["source"],
                "rewrite": r[a].replace("\n", " "),
                "easier_to_read (1-5)": "",
                "same_meaning (yes/no)": "",
            }
        )
        key.append(
            {"row": k, "arm": a, "video": r["video"], "cue": r["cue"], "accesscast_published": r["published"]}
        )
    return sheet, key


# ------------------------------------------------------------------ data
def cue_sets(settings: Settings, split: str, only: list[str], provider: str) -> list[tuple[str, list[Item]]]:
    from eval.e01_verifier_ab import video_list

    out = []
    for v in video_list(split, only):
        if split == "test":
            cap = Path(v["captions"])
            if not cap.exists():
                raise FileNotFoundError(
                    f"{v['id']}: W3C captions missing (run eval/datasets/fetch_w3c_wai.py)"
                )
            out.append((v["id"], sdh_items(read_vtt_cues(cap))))
        else:
            out.append((v["id"], dev_sdh(settings, Path(v["video"]), provider)))
    return out


def dev_sdh(settings: Settings, video: Path, provider: str) -> list[Item]:
    from accesscast.captions.segment import segment_sdh
    from accesscast.pipeline import ANALYSIS, open_run, stage_ingest, verify_context
    from accesscast.project import read_model
    from accesscast.schemas import ProjectInfo

    proj = stage_ingest(settings, video)
    base = open_run(settings, proj, provider=provider, strict=True)
    if not proj.p("analysis", "gaps.json").exists():
        for _n, fn in ANALYSIS:
            fn(base)
    ctx = verify_context(proj, "en")
    info = read_model(proj.p("project.json"), ProjectInfo)
    return [
        i for i in segment_sdh(ctx.words, ctx.sounds, ctx.fps, info.duration_ms) if "sound_tag" not in i.flags
    ]


def labels_dir(settings: Settings, split: str) -> Path:
    if settings.worker_mode == "fake":
        return EVAL_WORK / "_smoke_labels"  # canned outputs are never rated
    # W3C-derived text is never committed (CLAUDE.md rule 8): the test sheet stays in git-ignored data/.
    return REPO_ROOT / ("data/labels" if split == "test" else "eval/labels")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["dev", "test"], default="dev")
    ap.add_argument("--videos", default="")
    ap.add_argument("--provider", default="local")
    ap.add_argument(
        "--simpitiki", type=int, default=0, help="also run the Italian check on N SIMPITIKI pairs"
    )
    ap.add_argument("--allow-cpu", action="store_true")
    ap.add_argument(
        "--dry-run", action="store_true", help="fake mode, fixture clip, 3 SIMPITIKI pairs, _smoke"
    )
    ap.add_argument("--real-metrics", action="store_true")
    args = ap.parse_args()
    dry_run_env(args.dry_run)
    settings = load_settings()
    stand_in = settings.worker_mode == "fake" and not args.real_metrics
    only = ["fixture20"] if args.dry_run else [x for x in args.videos.split(",") if x]
    split = "dev" if args.dry_run else args.split
    exp = Experiment(
        "e05_easyread",
        split,
        config={
            "question": "Are easy-read captions easier to read without changing the meaning?",
            "one_change": "rewrite method",
            "arms": {
                "gemma_alone": "Gemma 4 31B, same easy prompt, no checks (attempt 0 as written)",
                "accesscast": "same attempt 0 + easy-read checks + up to 3 Gemma repairs; failures go to a person",
            },
            "reference": "the unsimplified caption text",
            "data": "W3C human caption cues (never used for tuning)"
            if split == "test"
            else "dev clips, our SDH cues",
            "lead_metric": "blind human rating sheet (30 cues, both arms, arm hidden)",
            "automatic_metrics_note": "secondary; they overlap with our own easy-read rules",
            "wpm_max": WPM_MAX,
            "provider": args.provider,
            "strict_provider": True,
            "worker_mode": settings.worker_mode,
            "metrics_stand_in": stand_in,
            "dry_run": args.dry_run,
            "simpitiki_pairs": args.simpitiki or None,
        },
    )

    def body(e: Experiment) -> None:
        from accesscast.verify.base import VerifyContext
        from accesscast.write.text_versions import TextOptions, make_easy

        metrics = Metrics(
            e.experiment,
            stand_in=stand_in,
            require_rocm=settings.worker_mode == "real" and not args.allow_cpu,
        )
        client, tail = gemma_client(settings, e.experiment, args.provider)
        opts = TextOptions(run_label=f"e05:{split}", project_seed=settings.project_seed, repair=True)
        rows: list[dict[str, Any]] = []
        for vid, sdh in cue_sets(settings, split, only, args.provider):
            src = {i.id: i for i in sdh}
            for it in make_easy(client, sdh, VerifyContext(lang="en"), opts):
                s = src[it.source_ids[0]]
                rows.append(
                    {
                        "video": vid,
                        "cue": it.id,
                        "source": s.text.replace("\n", " "),
                        "dur_ms": it.slot.end_ms - it.slot.start_ms,
                        "gemma_alone": it.draft.replace("\n", " "),
                        "accesscast": it.text.replace("\n", " "),
                        "published": it.status == ItemStatus.PENDING and not it.violations,
                        "repairs": it.repair.attempts,
                        "rules_failed": sorted({f.rule for f in it.violations}),
                    }
                )
        if not rows:
            raise RuntimeError("no caption cues to rewrite")
        scored = [r for r in rows if r["gemma_alone"].strip()] + [r for r in rows if r["accesscast"].strip()]
        n_a = sum(1 for r in rows if r["gemma_alone"].strip())
        bs = metrics(
            "bertscore",
            {
                "cands": [r["gemma_alone"] for r in scored[:n_a]] + [r["accesscast"] for r in scored[n_a:]],
                "refs": [r["source"] for r in scored],
                "lang": "en",
            },
        )["F1"]
        for r, f in zip(scored[:n_a], bs[:n_a], strict=True):
            r["bertscore_gemma_alone"] = f
        for r, f in zip(scored[n_a:], bs[n_a:], strict=True):
            r["bertscore_accesscast"] = f
        pub = [r for r in rows if r["published"]]
        e.summary["arms"] = {
            "source": arm_block([{**r, "bertscore_source": None} for r in rows], "source"),
            "gemma_alone": arm_block(rows, "gemma_alone"),
            "accesscast_published": arm_block(pub, "accesscast"),
            "gemma_alone_on_the_same_cues": arm_block(pub, "gemma_alone"),
        }
        e.summary["accesscast_routing"] = {
            "published": len(pub),
            "sent_to_person": len(rows) - len(pub),
            "of": len(rows),
        }
        e.summary["note"] = (
            "LED BY THE BLIND HUMAN RATING. The automatic numbers are secondary and overlap with our "
            "own easy-read rules."
        )
        keep_text = split != "test"
        e.results = [
            r if keep_text else {k: v for k, v in r.items() if k not in ("source", ARMS[0], ARMS[1])}
            for r in rows
        ]
        e.summary["outputs"] = write_outputs(e.experiment, f"easy_{split}", rows)
        sheet, key = blind_sheet(rows, SHEET_N, settings.project_seed)
        d = labels_dir(settings, split)
        d.mkdir(parents=True, exist_ok=True)
        sheet_p, key_p = d / f"e05_{split}_blind_sheet.csv", d / f"e05_{split}_blind_key.json"
        with sheet_p.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(sheet[0]) if sheet else ["row"])
            w.writeheader()
            w.writerows(sheet)
        key_p.write_text(json.dumps(key, indent=0, ensure_ascii=False))
        e.summary["rating_sheet"] = {
            "sheet": str(sheet_p.relative_to(REPO_ROOT)),
            "cues": len(sheet) // 2,
            "rows": len(sheet),
            "key": str(key_p.relative_to(REPO_ROOT)),
            "key_committed": False,
            "status": "waiting for a person to rate",
        }
        if args.simpitiki or args.dry_run:
            e.summary["simpitiki"] = simpitiki_check(
                client, metrics, 3 if args.dry_run else args.simpitiki, settings.project_seed, e.experiment
            )
        e.summary["served_model_id"] = one_served_model(tail)
        e.summary["metric_models"] = metrics.meta
        e.checks["every_cue_rewritten_or_counted"] = all("gemma_alone" in r for r in rows)
        e.checks["rating_sheet_written"] = len(sheet) == 2 * min(
            SHEET_N, sum(1 for r in rows if r["gemma_alone"].strip() and r["accesscast"].strip())
        )
        e.checks["strict_provider"] = True

    return run_experiment(exp, body)


def simpitiki_check(client: Any, metrics: Metrics, n: int, seed: int, exp_name: str) -> dict[str, Any]:
    """Italian: Gemma's `easy` rewrite (lang it, no checks) vs the person-made SIMPITIKI simplification."""
    from accesscast.errors import LlmOutputError, ModelEndpointError
    from accesscast.llm.client import LlmRequest
    from accesscast.seeds import derive_seed
    from eval.datasets.fetch_simpitiki import load_pairs

    pairs, seen = [], set()
    for p in load_pairs():
        if p.before not in seen:
            seen.add(p.before)
            pairs.append(p)
    pairs = random.Random(seed).sample(pairs, min(n, len(pairs)))
    rows: list[dict[str, Any]] = []
    for k, p in enumerate(pairs):
        wmax = max(3, len(words(p.before)))
        try:
            r = client.call(
                LlmRequest(
                    "easy",
                    {
                        "lang": "it",
                        "seconds": round(wmax * 60 / C.EASY_WPM_MAX, 2),
                        "words_max": wmax,
                        "cues": [{"id": "c1", "text": p.before}],
                    },
                    seed=derive_seed(seed, f"e05:simpitiki:{k}"),
                    label=f"e05_simpitiki:{k}",
                )
            )
            got = [x for x in r.obj.get("items") or [] if isinstance(x, dict)]
            text, err = (str(got[0].get("text", "")) if got else ""), None
        except (LlmOutputError, ModelEndpointError) as ex:
            text, err = "", str(ex)[:200]
        rows.append(
            {
                "k": k,
                "origin": p.origin,
                "type": p.type_id,
                "before": p.before,
                "gemma": text,
                "human": p.after,
                "error": err,
            }
        )
    ok = [r for r in rows if r["gemma"].strip()]
    lab = (
        metrics(
            "labse",
            {"a": [r["gemma"] for r in ok] + [r["human"] for r in ok], "b": [r["before"] for r in ok] * 2},
        )["cosine"]
        if ok
        else []
    )

    def block(key: str, sims: Sequence[float]) -> dict[str, Any]:
        m = [{"wps": words_per_sentence(r[key]), "gulp": gulpease(r[key])} for r in ok]
        return {
            "n": len(ok),
            "words_per_sentence": describe(m, "wps"),
            "gulpease": describe(m, "gulp"),
            "numbers_kept_digits": {
                "k": sum(1 for r in ok if numbers_kept(r["before"], r[key], "it")),
                "n": len(ok),
            },
            "negations_kept": {
                "k": sum(1 for r in ok if negations_kept(r["before"], r[key], "it")),
                "n": len(ok),
            },
            "labse_vs_original": describe([{"s": s} for s in sims], "s"),
        }

    return {
        "pairs": len(rows),
        "failed_calls": len(rows) - len(ok),
        "source": block("before", [1.0] * len(ok)),
        "gemma_easy_it": block("gemma", lab[: len(ok)]),
        "human_simplification": block("human", lab[len(ok) :]),
        "outputs": write_outputs(exp_name, "simpitiki_it", rows),
        "note": "SIMPITIKI pairs are single human edits, not full easy-read rewrites; Gemma alone, no checks",
    }


if __name__ == "__main__":
    raise SystemExit(main())
