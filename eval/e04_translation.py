"""E4: is Gemma 4 31B a good translator for Hindi and Italian? (PLAN §15.3, eval/PREREGISTRATION.md)

The one change: the translator. Gemma 4 31B through our own path (`translate_batch`, the alignment-safe batch
translation the subtitles use, prompt `translate_subs`) against a baseline per language:
  hi  ai4bharat/indictrans2-en-indic-1B (MIT, gated; no AI4Bharat model called "Indic-Translate" exists on
      Hugging Face as of 16 Oct 2026, see MODEL_LICENSES.md)
  it  Helsinki-NLP/opus-mt-en-it (Apache-2.0)
Data: FLORES+ devtest (all sentences by default; `--limit` for smoke runs). Metrics: COMET (wmt22-comet-da) and
chrF++, each with a paired bootstrap 95% interval of the difference (Gemma − baseline). A segment Gemma never
aligns is scored as an empty translation and counted (fail closed: it would never be shown untranslated).
With `--split test` (after the freeze) it also translates W3C's human caption cues and reports, per system, how
many subtitle cues pass our rules CC001 (reading speed) and CC009 (numbers and names kept), on attempt 0.

FLORES+ text and every translation stay in data/ (git-ignored): the evidence file holds ids, scores and the
SHA-256 of the output files only. W3C-derived subtitles are never written to evidence/ either.

This file also holds small helpers shared by E5–E7 (metrics worker calls, the Gemma client, VTT cues, outputs).

Usage: python -m eval.e04_translation [--langs hi,it] [--limit N] [--split test] [--dry-run [--real-metrics]]
"""

from __future__ import annotations

import argparse
import json
import os
import re
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from accesscast import constants as C
from accesscast.config import REPO_ROOT, Settings, load_settings
from accesscast.errors import ModelEndpointError
from accesscast.llm.client import LlmClient, LlmRequest, LlmResponse
from accesscast.llm.fake import FakeModel
from accesscast.llm.promptlib import load_prompt
from accesscast.project import atomic_write_text, sha256_file
from accesscast.schemas import Item, ItemKind, Slot
from accesscast.verify.base import VerifyContext
from accesscast.workers_client import run_worker
from eval.common import Experiment, run_experiment

EVAL_WORK = REPO_ROOT / "projects" / "_eval"  # git-ignored scratch (worker request files, LLM call logs)
OUTPUTS = REPO_ROOT / "data" / "eval_outputs"  # git-ignored: texts we may not commit (FLORES+, W3C-derived)
LANG_NAME = {"hi": "Hindi", "it": "Italian", "es": "Spanish", "fr": "French", "pt": "Portuguese"}
# IndicTrans2's remote model code imports transformers.onnx (removed in transformers 5), so the Hindi baseline runs
# in its own worker env pinned to transformers 4 (workers/indic/pyproject.toml); same worker file, same protocol.
INDIC_PYTHON = Path(os.environ.get("ACCESSCAST_INDIC_PYTHON", REPO_ROOT / "workers/indic/.venv/bin/python"))
BASELINE_NAME = {
    "hi": "IndicTrans2 en-indic 1B",
    "it": "Opus-MT en-it",
    "es": "Opus-MT en-es",
    "fr": "Opus-MT en-fr",
    "pt": "Opus-MT tc-big en-pt",
}
FLORES_LANG = {"hi": "hin_Deva", "it": "ita_Latn", "es": "spa_Latn", "fr": "fra_Latn", "pt": "por_Latn"}
# Dry-run sentences (wiring check only; written for this file, never scored as evidence).
DRY_SENTENCES = [
    "Press the Tab key to move to the next link.",
    "The video has captions in 3 languages.",
    "She does not use a mouse.",
]


# ------------------------------------------------------------------ shared helpers (E4–E7)
def dry_run_env(dry: bool) -> None:
    """--dry-run: fake worker mode, so the LLM is the canned fake and the evidence goes to evidence/_smoke/."""
    if dry:
        os.environ["ACCESSCAST_WORKER_MODE"] = "fake"


class Metrics:
    """Calls workers/metrics_worker.py through the worker protocol. `stand_in` = fake-mode wiring check."""

    def __init__(self, exp_name: str, *, stand_in: bool, require_rocm: bool) -> None:
        self.workdir = EVAL_WORK / exp_name / "worker"
        self.stand_in = stand_in
        self.require_rocm = require_rocm
        self.meta: dict[str, Any] = {}

    def __call__(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        res = run_worker(
            "metrics",
            action,
            {**payload, "stand_in": self.stand_in},
            self.workdir,
            require_rocm=self.require_rocm,
            timeout_s=6 * 3600,
            python=INDIC_PYTHON
            if action == "translate_baseline" and payload.get("lang") == "hi" and not self.stand_in
            else None,
        )
        key = f"{action}:{payload['lang']}" if "lang" in payload else action
        self.meta[key] = {
            k: res[k]
            for k in (
                "model",
                "revision",
                "hash",
                "signature",
                "device",
                "versions",
                "generation",
                "metric",
                "stand_in",
            )
            if k in res
        }
        return res


class LogTail:
    """Reads the LLM call log written after this point: served model ids and call counts for this run."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.offset = path.stat().st_size if path.exists() else 0

    def records(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        with self.path.open("rb") as fh:
            fh.seek(self.offset)
            return [json.loads(x) for x in fh.read().decode("utf-8").splitlines() if x.strip()]

    def served(self) -> list[str]:
        return sorted({str(r.get("served_model_id")) for r in self.records() if r.get("served_model_id")})

    def endpoint_errors(self) -> int:
        """Calls the endpoint never answered (outage, rate limit). translate_batch drops a segment it cannot get,
        which is right in the pipeline but would score an outage as a bad translation, so a quality run with any
        of these does not pass: re-run it (successful answers come back from the opt-in cache)."""
        return sum(1 for r in self.records() if r.get("status") == "endpoint_error")


def gemma_client(settings: Settings, exp_name: str, provider: str) -> tuple[LlmClient, LogTail]:
    log = EVAL_WORK / exp_name / "llm_calls.jsonl"
    fake = FakeModel(None) if settings.worker_mode == "fake" else None
    client = LlmClient(settings, provider=provider, strict_provider=True, log_path=log, fake_handler=fake)
    return client, LogTail(log)


def one_served_model(tail: LogTail) -> str | None:
    """Strict provider: every call in this run must have been served by the same model id."""
    ids = tail.served()
    if len(ids) > 1:
        raise ModelEndpointError(f"more than one served model id in one run: {ids}")
    return ids[0] if ids else None


@dataclass(frozen=True)
class Cue:
    start_ms: int
    end_ms: int
    text: str


def _ts(s: str) -> int:
    parts = s.strip().split(":")
    sec = float(parts[-1])
    mins = int(parts[-2]) if len(parts) >= 2 else 0
    hours = int(parts[-3]) if len(parts) >= 3 else 0
    return round((hours * 3600 + mins * 60 + sec) * 1000)


def read_vtt_cues(path: Path) -> list[Cue]:
    """WebVTT cues with text (voice/markup tags removed, lines joined with a space)."""
    cues: list[Cue] = []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    i = 0
    while i < len(lines):
        m = re.match(r"\s*([\d:.]+)\s+-->\s+([\d:.]+)", lines[i])
        if not m:
            i += 1
            continue
        text: list[str] = []
        i += 1
        while i < len(lines) and lines[i].strip():
            text.append(re.sub(r"<[^>]+>", "", lines[i]).strip())
            i += 1
        t = " ".join(x for x in text if x)
        if t:
            cues.append(Cue(_ts(m.group(1)), _ts(m.group(2)), t))
    return sorted(cues, key=lambda c: c.start_ms)


def sdh_items(cues: Sequence[Cue]) -> list[Item]:
    """Caption cues as SDH items (the input our easy-read and subtitle writers take)."""
    return [
        Item(
            id=f"sdh.en.{k + 1:04d}",
            kind=ItemKind.SDH,
            lang="en",
            audiences=["sdh"],
            anchor_ms=c.start_ms,
            slot=Slot(start_ms=c.start_ms, end_ms=max(c.end_ms, c.start_ms + 1)),
            draft=c.text,
        )
        for k, c in enumerate(cues)
    ]


def write_outputs(exp_name: str, name: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Texts go to data/eval_outputs/ (git-ignored); the evidence file records the path and SHA-256."""
    p = OUTPUTS / exp_name / f"{name}.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(p, "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    return {
        "file": str(p.relative_to(REPO_ROOT)),
        "sha256": sha256_file(p),
        "rows": len(rows),
        "committed": False,
    }


def paired_bootstrap(
    a: Sequence[float], b: Sequence[float], n_boot: int = 1000, seed: int = C.PROJECT_SEED_DEFAULT
) -> dict[str, float]:
    """Mean(b) − mean(a) over paired items, with a percentile 95% interval (items resampled with replacement)."""
    xa, xb = np.asarray(a, float), np.asarray(b, float)
    if xa.shape != xb.shape or xa.size == 0:
        raise ValueError(f"paired bootstrap needs two equal, non-empty lists ({xa.size} vs {xb.size})")
    d = xb - xa
    idx = np.random.default_rng(seed).integers(0, d.size, size=(n_boot, d.size))
    boots = d[idx].mean(axis=1)
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return {
        "diff": float(d.mean()),
        "ci95_lo": float(lo),
        "ci95_hi": float(hi),
        "n": int(d.size),
        "n_boot": n_boot,
    }


def winner(diff: float, lo: float, hi: float, a: str, b: str) -> dict[str, Any]:
    """Which system has the higher point estimate of (b − a); says whether the interval includes no change."""
    name = b if diff > 0 else a if diff < 0 else "tie"
    return {"higher": name, "interval_includes_zero": bool(lo <= 0 <= hi)}


# ------------------------------------------------------------------ E4
class FixedTranslations(LlmClient):
    """Feeds a baseline's translations through the same make_subtitles code as Gemma (same cue timing, same
    rules). Answers only `translate_subs`; anything else fails closed."""

    def __init__(self, settings: Settings, table: dict[str, str], model: str) -> None:
        super().__init__(settings, provider="fake_off", strict_provider=True)
        self.table, self.model = table, model

    def call(self, req: LlmRequest, *, provider: str | None = None) -> LlmResponse:
        if req.prompt_id != "translate_subs":
            raise ModelEndpointError(f"baseline client cannot answer {req.prompt_id}")
        items = [
            {"id": s["id"], "snippet": s["text"][:10], "translation": self.table.get(s["text"], "")}
            for s in req.payload["segments"]
        ]
        obj = {"items": items}
        return LlmResponse(
            obj,
            json.dumps(obj, ensure_ascii=False),
            "baseline",
            self.model,
            load_prompt(req.prompt_id),
            req.seed,
            0.0,
            0,
            0,
            0.0,
            1,
        )


def flores_segments(sents: Sequence[str], lang: str) -> list[dict[str, Any]]:
    """FLORES sentences are not subtitles: chars_max = 3 × the English length so the length limit never binds."""
    cps = C.CPS_MAX[(lang, "subtitle")]
    return [
        {"id": i, "text": s, "chars_max": 3 * len(s), "seconds": round(3 * len(s) / cps, 1)}
        for i, s in enumerate(sents)
    ]


def gemma_translate(
    client: LlmClient, segs: list[dict[str, Any]], lang: str, opts: Any, chunk: int, concurrency: int
) -> dict[int, str]:
    from accesscast.write.text_versions import translate_batch

    chunks = [segs[i : i + chunk] for i in range(0, len(segs), chunk)]
    out: dict[int, str] = {}
    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as ex:
        for part in ex.map(lambda c: translate_batch(client, c, lang, opts), chunks):
            out.update(part)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--split",
        choices=["none", "test"],
        default="none",
        help="test = also run the in-domain W3C check (needs the prompt freeze)",
    )
    ap.add_argument("--langs", default="hi,it")
    ap.add_argument("--tag", default="", help="evidence name suffix, e.g. es_fr → e04_translation_es_fr.json")
    ap.add_argument("--limit", type=int, default=0, help="first N FLORES+ sentences (0 = all)")
    ap.add_argument("--chunk", type=int, default=16, help="sentences per translate_batch call")
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--n-boot", type=int, default=1000)
    ap.add_argument("--provider", default="local")
    ap.add_argument("--videos", default="", help="test split: comma-separated W3C video ids (default all)")
    ap.add_argument("--allow-cpu", action="store_true", help="let metric models run on CPU (recorded)")
    ap.add_argument("--dry-run", action="store_true", help="fake mode, 3 sentences, evidence/_smoke/")
    ap.add_argument("--real-metrics", action="store_true", help="with --dry-run: run the real metric models")
    args = ap.parse_args()
    dry_run_env(args.dry_run)
    settings = load_settings()
    langs = [x for x in args.langs.split(",") if x]
    stand_in = settings.worker_mode == "fake" and not args.real_metrics
    exp = Experiment(
        "e04_translation" + (f"_{args.tag}" if args.tag else ""),
        args.split,
        config={
            "question": "Is Gemma 4 31B a good translator for Hindi and Italian?",
            "one_change": "translator",
            "systems": {
                "gemma": "Gemma 4 31B via translate_batch (prompt translate_subs, attempt 0, no repair)",
                **{f"baseline_{lang}": BASELINE_NAME[lang] for lang in langs},
            },
            "data": "FLORES+ devtest"
            if not args.dry_run
            else "dry run: 3 built-in sentences (wiring check only)",
            "limit": args.limit or None,
            "chunk": args.chunk,
            "provider": args.provider,
            "strict_provider": True,
            "worker_mode": settings.worker_mode,
            "metrics_stand_in": stand_in,
            "n_boot": args.n_boot,
            "bootstrap": "paired, items resampled with replacement, percentile 95% interval",
            "comet": "Unbabel/wmt22-comet-da",
            "chrf": "sacrebleu chrF++ (word order 2)",
            "missing_segments": "scored as an empty translation",
            "in_domain": "W3C human caption cues → CC001/CC009 pass rate, attempt 0"
            if args.split == "test"
            else None,
        },
    )

    def body(e: Experiment) -> None:
        from accesscast.write.text_versions import TextOptions

        metrics = Metrics(
            e.experiment,
            stand_in=stand_in,
            require_rocm=settings.worker_mode == "real" and not args.allow_cpu,
        )
        client, tail = gemma_client(settings, e.experiment, args.provider)
        opts = TextOptions(run_label=f"e04:{args.split}", project_seed=settings.project_seed, repair=False)
        if args.dry_run:
            flores = {"eng_Latn": DRY_SENTENCES, **{FLORES_LANG[x]: DRY_SENTENCES for x in langs}}
        else:
            from eval.datasets.fetch_flores import load_split

            flores = load_split("devtest")
        src_all = flores["eng_Latn"][: args.limit or None]
        e.summary["languages"] = {}
        for lang in langs:
            ref = flores[FLORES_LANG[lang]][: len(src_all)]
            done = gemma_translate(
                client, flores_segments(src_all, lang), lang, opts, args.chunk, args.concurrency
            )
            gem = [done.get(i, "") for i in range(len(src_all))]
            base = metrics("translate_baseline", {"lang": lang, "texts": src_all})["translations"]
            sysname = f"baseline_{lang}"
            com = metrics("comet", {"src": src_all * 2, "mt": gem + base, "ref": ref * 2})
            n = len(src_all)
            cg, cb = com["segments"][:n], com["segments"][n:]
            chf = metrics(
                "chrf",
                {
                    "ref": ref,
                    "systems": {"gemma": gem, sysname: base},
                    "pairs": [[sysname, "gemma"]],
                    "n_boot": args.n_boot,
                    "seed": settings.project_seed,
                },
            )
            cboot = paired_bootstrap(cb, cg, args.n_boot, settings.project_seed)
            pair = chf["pairs"][0] if chf.get("pairs") else None
            for i in range(n):
                e.results.append(
                    {
                        "lang": lang,
                        "flores_index": i,
                        "gemma_aligned": i in done,
                        "comet_gemma": cg[i],
                        "comet_baseline": cb[i],
                        "chrf_gemma": chf["systems"]["gemma"].get("sentences", [None] * n)[i],
                        "chrf_baseline": chf["systems"][sysname].get("sentences", [None] * n)[i],
                    }
                )
            outputs = write_outputs(
                e.experiment,
                f"flores_{lang}",
                [{"i": i, "gemma": gem[i], "baseline": base[i]} for i in range(n)],
            )
            res: dict[str, Any] = {
                "n": n,
                "gemma_never_aligned": n - len(done),
                "comet": {
                    "gemma": float(np.mean(cg)),
                    sysname: float(np.mean(cb)),
                    "gemma_minus_baseline": cboot,
                    **winner(cboot["diff"], cboot["ci95_lo"], cboot["ci95_hi"], sysname, "gemma"),
                },
                "chrf": {
                    "gemma": chf["systems"]["gemma"]["corpus"],
                    sysname: chf["systems"][sysname]["corpus"],
                },
                "baseline": BASELINE_NAME[lang],
                "outputs": outputs,
            }
            if pair:
                res["chrf"]["gemma_minus_baseline"] = {
                    "diff": pair["diff_b_minus_a"],
                    "ci95_lo": pair["ci95"][0],
                    "ci95_hi": pair["ci95"][1],
                    "n": n,
                    "n_boot": pair["n_boot"],
                }
                res["chrf"].update(
                    winner(pair["diff_b_minus_a"], pair["ci95"][0], pair["ci95"][1], sysname, "gemma")
                )
            e.summary["languages"][lang] = res
            if args.split == "test":
                res["in_domain"] = in_domain(
                    settings,
                    client,
                    lang,
                    base_translator(metrics, lang),
                    opts,
                    [x for x in args.videos.split(",") if x],
                    e.experiment,
                )
        e.summary["served_model_id"] = one_served_model(tail)
        e.summary["endpoint_errors"] = tail.endpoint_errors()
        e.summary["cache_hits"] = sum(
            1 for r in tail.records() if r.get("status") == "ok" and r.get("attempts") == 0
        )
        e.config["llm_cache"] = bool(os.environ.get("ACCESSCAST_LLM_CACHE"))
        e.checks["no_endpoint_errors"] = e.summary["endpoint_errors"] == 0
        e.summary["metric_models"] = metrics.meta
        e.summary["statements"] = statements(e.summary["languages"], dry=args.dry_run)
        e.summary["negative_results"] = [s for s, neg in e.summary["statements"] if neg]
        e.summary["statements"] = [s for s, _ in e.summary["statements"]]
        e.checks["all_languages_scored"] = set(e.summary["languages"]) == set(langs)
        e.checks["every_segment_scored"] = len(e.results) == len(langs) * len(src_all) and all(
            isinstance(r["comet_gemma"], float) and isinstance(r["comet_baseline"], float) for r in e.results
        )
        e.checks["strict_provider"] = True
        e.config["dry_run"] = args.dry_run

    return run_experiment(exp, body)


def statements(langs: dict[str, Any], *, dry: bool) -> list[tuple[str, bool]]:
    """Plain sentences built from the numbers (no hand-written results). (text, is_negative_result)."""
    out = []
    for lang, r in langs.items():
        for metric, label in (("comet", "COMET"), ("chrf", "chrF++")):
            m = r.get(metric, {})
            if "higher" not in m:
                continue
            who = (
                "Gemma 4 31B"
                if m["higher"] == "gemma"
                else r["baseline"]
                if m["higher"] != "tie"
                else "neither"
            )
            data = "dry-run sentences (not a result)" if dry else f"FLORES+ devtest ({r['n']} sentences)"
            s = f"{LANG_NAME[lang]}, {label}: {who} scored higher on {data}"
            if m["interval_includes_zero"]:
                s += "; the 95% interval of the difference includes no change"
            out.append((s + ".", m["higher"] not in ("gemma", "tie")))
    return out


def base_translator(metrics: Metrics, lang: str) -> Any:
    def tr(texts: list[str]) -> dict[str, str]:
        uniq = sorted(set(texts))
        got = metrics("translate_baseline", {"lang": lang, "texts": uniq})["translations"]
        return dict(zip(uniq, got, strict=True))

    return tr


def in_domain(
    settings: Settings, client: LlmClient, lang: str, base_tr: Any, opts: Any, only: list[str], exp_name: str
) -> dict[str, Any]:
    """Test split only (Experiment already checked the freeze): W3C caption cues → subtitles → CC001/CC009."""
    from accesscast.write.text_versions import make_subtitles
    from eval.e01_verifier_ab import video_list

    out: dict[str, Any] = {
        "gemma": {"cues": 0, "cc001_pass": 0, "cc009_pass": 0},
        "baseline": {"cues": 0, "cc001_pass": 0, "cc009_pass": 0},
        "videos": [],
    }
    rows = []
    for v in video_list("test", only):
        if not v["captions"] or not Path(v["captions"]).exists():
            raise FileNotFoundError(f"{v['id']}: W3C captions missing (run eval/datasets/fetch_w3c_wai.py)")
        sdh = sdh_items(read_vtt_cues(Path(v["captions"])))
        ctx = VerifyContext(lang="en")
        table = base_tr([i.source_text or i.text.replace("\n", " ") for i in sdh])
        systems = {
            "gemma": make_subtitles(client, sdh, lang, ctx, opts),
            "baseline": make_subtitles(
                FixedTranslations(settings, table, BASELINE_NAME[lang]), sdh, lang, ctx, opts
            ),
        }
        for name, items in systems.items():
            for it in items:
                rules = {f.rule for f in it.violations}
                out[name]["cues"] += 1
                out[name]["cc001_pass"] += int("CC001" not in rules)
                out[name]["cc009_pass"] += int("CC009" not in rules)
                rows.append(
                    {
                        "video": v["id"],
                        "system": name,
                        "id": it.id,
                        "text": it.draft,
                        "violations": sorted(rules),
                    }
                )
        out["videos"].append(v["id"])
    out["outputs"] = write_outputs(exp_name, f"w3c_subtitles_{lang}", rows)  # W3C-derived: never committed
    out["note"] = "attempt 0 for both systems (no repair); same cue timing code and rules for both"
    return out


if __name__ == "__main__":
    raise SystemExit(main())
