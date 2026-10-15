"""Metrics worker for the quality experiments E4–E7 (PLAN §15.3). Only workers/ import torch.

Actions (payload → result):
  comet               {src, mt, ref}            → system_score + per-segment scores (Unbabel/wmt22-comet-da)
  chrf                {ref, systems{name: hyps}, pairs?, n_boot?, seed?}
                                                → corpus chrF++ per system, sentence chrF++, and a paired
                                                  bootstrap 95% interval of each pair's corpus-score difference
  bertscore           {cands, refs, lang}       → P/R/F1 per pair (bert-score, microsoft/deberta-xlarge-mnli)
  labse               {a, b}                    → cosine per pair (sentence-transformers/LaBSE)
  translate_baseline  {lang, texts}             → baseline MT output (hi: IndicTrans2 en-indic 1B, it: Opus-MT en-it)

Every model is loaded at a pinned Hugging Face revision where the loader allows it, and every result names the
model id, revision and library versions. `stand_in: true` (fake worker mode / --dry-run) skips every model and
returns cheap lexical stand-ins labelled `"stand_in": true`; those numbers are never evidence of anything.
Fail closed: a missing model, a gated model without access, or a length mismatch raises, and the core marks the
experiment failed.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from common import device, event, main, stage_timer

# Pinned revisions (Hugging Face commit SHAs, read from the model API on 16 Oct 2026).
COMET_MODEL = ("Unbabel/wmt22-comet-da", "2760a223ac957f30acfb18c8aa649b01cf1d75f2")
BERTSCORE_MODEL = (
    "microsoft/deberta-xlarge-mnli"  # bert-score cannot pin a revision; its hash string is recorded
)
LABSE_MODEL = ("sentence-transformers/LaBSE", "836121a0533e5664b21c7aacc5d22951f2b8b25b")
BASELINES = {
    "hi": ("ai4bharat/indictrans2-en-indic-1B", "89cd0007fd7b9e0693a2fd4404d187e07dac79fd"),
    "it": ("Helsinki-NLP/opus-mt-en-it", "be5a254d936f1a8c8da080406ca582a6615e6658"),
}
FLORES_CODE = {"hi": "hin_Deva", "it": "ita_Latn"}


def _versions(*pkgs: str) -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    for p in pkgs:
        try:
            out[p] = version(p)
        except PackageNotFoundError:
            out[p] = None
    return out


def _same_len(**lists: Sequence[Any]) -> int:
    lens = {k: len(v) for k, v in lists.items()}
    if len(set(lens.values())) != 1:
        raise ValueError(f"length mismatch: {lens}")
    n = next(iter(lens.values()))
    if n == 0:
        raise ValueError("nothing to score")
    return n


def _char_f1(a: str, b: str) -> float:
    """Stand-in only (fake mode): character-bigram F1. Never reported as a metric."""
    ga = {a[i : i + 2] for i in range(max(0, len(a) - 1))}
    gb = {b[i : i + 2] for i in range(max(0, len(b) - 1))}
    if not ga or not gb:
        return 0.0
    inter = len(ga & gb)
    return 0.0 if inter == 0 else 2 * inter / (len(ga) + len(gb))


# ------------------------------------------------------------------ COMET
def _patch_comet_for_transformers5() -> None:
    """unbabel-comet 2.2.7 unpacks a 3-tuple from XLM-R with return_dict=False; transformers 5 drops the None
    pooler from that tuple. Read the same tensors by name instead. Checked on 16 Oct 2026: identical scores
    (6 decimals) to unpatched COMET under transformers 4.57.6 on a 3-pair probe."""
    import transformers

    if int(transformers.__version__.split(".")[0]) < 5:
        return
    from comet.encoders.xlmr import XLMREncoder

    def forward(self: Any, input_ids: Any, attention_mask: Any, **kwargs: Any) -> dict[str, Any]:
        out = self.model(
            input_ids=input_ids, attention_mask=attention_mask, output_hidden_states=True, return_dict=True
        )
        return {
            "sentemb": out.last_hidden_state[:, 0, :],
            "wordemb": out.last_hidden_state,
            "all_layers": out.hidden_states,
            "attention_mask": attention_mask,
        }

    XLMREncoder.forward = forward


def comet(p: dict[str, Any], require_rocm: bool) -> dict[str, Any]:
    n = _same_len(src=p["src"], mt=p["mt"], ref=p["ref"])
    if p.get("stand_in"):
        segs = [_char_f1(m, r) for m, r in zip(p["mt"], p["ref"], strict=True)]
        return {
            "stand_in": True,
            "metric": "stand-in (char-bigram F1), NOT COMET",
            "system_score": sum(segs) / n,
            "segments": segs,
        }
    dev = device(require_rocm)
    from huggingface_hub import snapshot_download

    _patch_comet_for_transformers5()
    from comet import load_from_checkpoint

    repo, rev = p.get("model", COMET_MODEL[0]), p.get("revision", COMET_MODEL[1])
    path = snapshot_download(repo_id=repo, revision=rev)
    timings: dict[str, Any] = {}
    with stage_timer("comet", timings):
        model = load_from_checkpoint(os.path.join(path, "checkpoints", "model.ckpt"))
        data = [{"src": s, "mt": m, "ref": r} for s, m, r in zip(p["src"], p["mt"], p["ref"], strict=True)]
        out = model.predict(
            data, batch_size=int(p.get("batch_size", 32)), gpus=1 if dev == "cuda" else 0, progress_bar=False
        )
    segs = [float(x) for x in out.scores]
    if len(segs) != n:
        raise RuntimeError(f"COMET returned {len(segs)} scores for {n} segments")
    event("progress", done=n, total=n)
    return {
        "metric": "COMET",
        "model": repo,
        "revision": rev,
        "system_score": float(out.system_score),
        "segments": segs,
        "device": dev,
        "timing": timings,
        "versions": _versions("unbabel-comet", "transformers", "torch"),
    }


# ------------------------------------------------------------------ chrF++
def _bootstrap_indices(n_items: int, n_boot: int, seed: int) -> Any:
    import numpy as np

    rng = np.random.default_rng(seed)
    return rng.integers(0, n_items, size=(n_boot, n_items))


def chrf(p: dict[str, Any], require_rocm: bool) -> dict[str, Any]:
    """chrF++ (sacrebleu, char order 6, word order 2, beta 2). CPU only; `require_rocm` does not apply."""
    import numpy as np

    refs: list[str] = p["ref"]
    systems: dict[str, list[str]] = p["systems"]
    for name, hyps in systems.items():
        _same_len(**{name: hyps, "ref": refs})
    n = len(refs)
    if p.get("stand_in"):
        return {
            "stand_in": True,
            "metric": "stand-in (char-bigram F1), NOT chrF++",
            "systems": {
                k: {"corpus": 100 * sum(_char_f1(h, r) for h, r in zip(v, refs, strict=True)) / n}
                for k, v in systems.items()
            },
            "pairs": [],
        }
    from sacrebleu.metrics import CHRF

    metric = CHRF(word_order=2)
    stats = {
        k: np.array(metric._extract_corpus_statistics(v, [refs]), dtype=np.int64) for k, v in systems.items()
    }
    out_sys = {}
    for k, v in systems.items():
        corpus = metric.corpus_score(v, [refs])
        out_sys[k] = {
            "corpus": float(corpus.score),
            "sentences": [float(metric.sentence_score(h, [r]).score) for h, r in zip(v, refs, strict=True)],
        }
    pairs_out = []
    n_boot, seed = int(p.get("n_boot", 1000)), int(p.get("seed", 0))
    idx = _bootstrap_indices(n, n_boot, seed)
    for a, b in p.get("pairs", []):
        sa, sb = stats[a], stats[b]
        point = (
            metric._compute_score_from_stats(sb.sum(0).tolist()).score
            - metric._compute_score_from_stats(sa.sum(0).tolist()).score
        )
        diffs = np.array(
            [
                metric._compute_score_from_stats(sb[r].sum(0).tolist()).score
                - metric._compute_score_from_stats(sa[r].sum(0).tolist()).score
                for r in idx
            ]
        )
        lo, hi = np.percentile(diffs, [2.5, 97.5])
        pairs_out.append(
            {
                "a": a,
                "b": b,
                "diff_b_minus_a": float(point),
                "ci95": [float(lo), float(hi)],
                "n_boot": n_boot,
                "seed": seed,
            }
        )
    return {
        "metric": "chrF++",
        "signature": str(metric.get_signature()),
        "systems": out_sys,
        "pairs": pairs_out,
        "versions": _versions("sacrebleu"),
    }


# ------------------------------------------------------------------ BERTScore
def bertscore(p: dict[str, Any], require_rocm: bool) -> dict[str, Any]:
    n = _same_len(cands=p["cands"], refs=p["refs"])
    if p.get("stand_in"):
        f = [_char_f1(c, r) for c, r in zip(p["cands"], p["refs"], strict=True)]
        return {
            "stand_in": True,
            "metric": "stand-in (char-bigram F1), NOT BERTScore",
            "P": f,
            "R": f,
            "F1": f,
        }
    dev = device(require_rocm)
    from bert_score import BERTScorer

    model = p.get("model", BERTSCORE_MODEL)
    timings: dict[str, Any] = {}
    with stage_timer("bertscore", timings):
        scorer = BERTScorer(
            model_type=model, lang=p.get("lang", "en"), device=dev, rescale_with_baseline=False
        )
        # transformers 5 gives DeBERTa a ~1e30 model_max_length, which overflows the fast tokenizer. 512 is the
        # model's position limit. Checked on 16 Oct 2026: same F1 (6 decimals) as transformers 4.57.6.
        if scorer._tokenizer.model_max_length > 100_000:
            scorer._tokenizer.model_max_length = 512
        too_long = [
            i
            for i, t in enumerate([*p["cands"], *p["refs"]])
            if len(scorer._tokenizer.encode(t, add_special_tokens=True)) > 512
        ]
        if too_long:  # no silent truncation (CLAUDE.md rule 6)
            raise ValueError(f"{len(too_long)} texts exceed 512 tokens; split them before scoring")
        P, R, F = scorer.score(list(p["cands"]), list(p["refs"]), batch_size=int(p.get("batch_size", 16)))
    event("progress", done=n, total=n)
    return {
        "metric": "BERTScore",
        "model": model,
        "hash": scorer.hash,
        "rescaled": False,
        "P": [float(x) for x in P],
        "R": [float(x) for x in R],
        "F1": [float(x) for x in F],
        "device": dev,
        "timing": timings,
        "versions": _versions("bert-score", "transformers", "torch"),
    }


# ------------------------------------------------------------------ LaBSE
def labse(p: dict[str, Any], require_rocm: bool) -> dict[str, Any]:
    _same_len(a=p["a"], b=p["b"])
    if p.get("stand_in"):
        return {
            "stand_in": True,
            "metric": "stand-in (char-bigram F1), NOT LaBSE",
            "cosine": [_char_f1(x, y) for x, y in zip(p["a"], p["b"], strict=True)],
        }
    dev = device(require_rocm)
    from sentence_transformers import SentenceTransformer

    repo, rev = p.get("model", LABSE_MODEL[0]), p.get("revision", LABSE_MODEL[1])
    timings: dict[str, Any] = {}
    with stage_timer("labse", timings):
        m = SentenceTransformer(repo, revision=rev, device=dev)
        too_long = [
            t
            for t in [*p["a"], *p["b"]]
            if len(m.tokenizer.encode(t, add_special_tokens=True)) > m.max_seq_length
        ]
        if too_long:  # no silent truncation (CLAUDE.md rule 6)
            raise ValueError(f"{len(too_long)} texts exceed LaBSE's {m.max_seq_length} tokens")
        ea = m.encode(list(p["a"]), normalize_embeddings=True, batch_size=int(p.get("batch_size", 32)))
        eb = m.encode(list(p["b"]), normalize_embeddings=True, batch_size=int(p.get("batch_size", 32)))
    cos = [float((x * y).sum()) for x, y in zip(ea, eb, strict=True)]
    return {
        "metric": "LaBSE cosine",
        "model": repo,
        "revision": rev,
        "cosine": cos,
        "device": dev,
        "timing": timings,
        "versions": _versions("sentence-transformers", "transformers", "torch"),
    }


# ------------------------------------------------------------------ baseline translators
def _batches(xs: list[str], n: int) -> list[list[str]]:
    return [xs[i : i + n] for i in range(0, len(xs), n)]


def _indictrans2(
    texts: list[str], repo: str, rev: str, dev: str, p: dict[str, Any]
) -> tuple[list[str], dict[str, Any]]:
    """IndicTrans2's documented inference recipe (huggingface_interface/example.py): IndicProcessor pre/post
    processing, beam 5, max_length 256. The model is gated: HF_TOKEN must belong to an account with access."""
    import torch
    import transformers
    import transformers.tokenization_utils as tu
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    if not hasattr(tu, "PreTrainedTokenizerBase"):  # IndicTransToolkit 1.1.1's collator imports the v4 path
        tu.PreTrainedTokenizerBase = transformers.PreTrainedTokenizerBase
    from IndicTransToolkit.processor import IndicProcessor

    if not os.environ.get("HF_TOKEN"):
        raise PermissionError(f"{repo} is gated: set HF_TOKEN in .env for an account that accepted its terms")
    tok = AutoTokenizer.from_pretrained(repo, revision=rev, trust_remote_code=True)
    model = AutoModelForSeq2SeqLM.from_pretrained(repo, revision=rev, trust_remote_code=True).to(dev).eval()
    ip = IndicProcessor(inference=True)
    beams, max_len = int(p.get("num_beams", 5)), int(p.get("max_length", 256))
    out: list[str] = []
    for k, batch in enumerate(_batches(texts, int(p.get("batch_size", 16)))):
        pre = ip.preprocess_batch(batch, src_lang="eng_Latn", tgt_lang=FLORES_CODE["hi"])
        enc = tok(
            pre, truncation=False, padding="longest", return_tensors="pt", return_attention_mask=True
        ).to(dev)
        if enc["input_ids"].shape[1] > max_len:
            raise ValueError(f"batch {k}: source longer than {max_len} tokens (no silent truncation)")
        with torch.no_grad():
            gen = model.generate(
                **enc,
                use_cache=True,
                min_length=0,
                max_length=max_len,
                num_beams=beams,
                num_return_sequences=1,
            )
        dec = tok.batch_decode(gen, skip_special_tokens=True, clean_up_tokenization_spaces=True)
        out += ip.postprocess_batch(dec, lang=FLORES_CODE["hi"])
        event("progress", done=len(out), total=len(texts))
    return out, {
        "num_beams": beams,
        "max_length": max_len,
        "preprocessing": "IndicTransToolkit.IndicProcessor",
    }


def _marian(
    texts: list[str], repo: str, rev: str, dev: str, p: dict[str, Any]
) -> tuple[list[str], dict[str, Any]]:
    import torch
    from transformers import MarianMTModel, MarianTokenizer

    tok = MarianTokenizer.from_pretrained(repo, revision=rev)
    model = MarianMTModel.from_pretrained(repo, revision=rev).to(dev).eval()
    beams = int(p.get("num_beams", model.generation_config.num_beams or 1))
    max_new = int(p.get("max_new_tokens", 256))
    out: list[str] = []
    for k, batch in enumerate(_batches(texts, int(p.get("batch_size", 16)))):
        enc = tok(batch, return_tensors="pt", padding=True, truncation=False).to(dev)
        if enc["input_ids"].shape[1] > tok.model_max_length:
            raise ValueError(
                f"batch {k}: source longer than {tok.model_max_length} tokens (no silent truncation)"
            )
        with torch.no_grad():
            gen = model.generate(**enc, num_beams=beams, max_new_tokens=max_new)
        out += tok.batch_decode(gen, skip_special_tokens=True)
        event("progress", done=len(out), total=len(texts))
    return out, {"num_beams": beams, "max_new_tokens": max_new}


def translate_baseline(p: dict[str, Any], require_rocm: bool) -> dict[str, Any]:
    lang = p["lang"]
    if lang not in BASELINES:
        raise ValueError(f"no baseline translator for {lang!r} (no fallback)")
    texts: list[str] = list(p["texts"])
    if not texts:
        raise ValueError("nothing to translate")
    repo, rev = p.get("model", BASELINES[lang][0]), p.get("revision", BASELINES[lang][1])
    if p.get("stand_in"):
        return {
            "stand_in": True,
            "model": f"stand-in for {repo}",
            "translations": [f"[{lang}] {t}" for t in texts],
        }
    dev = device(require_rocm)
    timings: dict[str, Any] = {}
    with stage_timer("translate", timings):
        if repo.startswith("ai4bharat/indictrans2"):
            out, gen = _indictrans2(texts, repo, rev, dev, p)
        elif repo.startswith("Helsinki-NLP/opus-mt"):
            out, gen = _marian(texts, repo, rev, dev, p)
        else:
            raise ValueError(f"unsupported baseline model {repo!r}")
    if len(out) != len(texts) or any(not t.strip() for t in out):
        raise RuntimeError(f"{repo}: {sum(1 for t in out if not t.strip())} empty outputs of {len(texts)}")
    return {
        "model": repo,
        "revision": rev,
        "translations": out,
        "generation": gen,
        "device": dev,
        "timing": timings,
        "versions": _versions("transformers", "torch", "IndicTransToolkit", "sentencepiece"),
    }


if __name__ == "__main__":
    raise SystemExit(
        main(
            {
                "comet": comet,
                "chrf": chrf,
                "bertscore": bertscore,
                "labse": labse,
                "translate_baseline": translate_baseline,
            }
        )
    )
