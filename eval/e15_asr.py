"""E15: which ASR, and how accurate are word boundaries? (decision on DEV data only: FLEURS + dev clips)

Part 1 — accuracy and speed on FLEURS en/hi/it: Whisper large-v3 vs large-v3-turbo (transformers, ROCm) vs
Gemma 4 E4B (audio input, no timestamps). WER/CER with jiwer after lower-casing and stripping punctuation;
real-time factor; whether word timestamps are available.
Part 2 — word-boundary error in ms (median, p95) of raw Whisper vs forced-aligned words, on clips whose true word
boundaries are known: our synthetic clips (fixture + adversarial), where the boundaries come from the
synthesizer (decision D-003: not a human hand label; said wherever this number is used).
Output: the chosen ASR, aligner on/off, and guard_ms = p95 boundary error of the chosen setup rounded up to 10 ms.
Usage: python -m eval.e15_asr [--models openai/whisper-large-v3,openai/whisper-large-v3-turbo] [--n 100] [--no-gemma]
"""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import unicodedata
from pathlib import Path
from typing import Any

import jiwer

from accesscast.config import REPO_ROOT, load_settings
from accesscast.errors import OutOfMemoryError
from accesscast.llm.client import LlmClient, LlmRequest
from accesscast.workers_client import run_worker
from eval.common import Experiment, run_experiment

LANG_NAMES = {"en": "English", "hi": "Hindi", "it": "Italian"}


def norm(t: str) -> str:
    t = unicodedata.normalize("NFC", t.lower())
    t = re.sub(r"[^\w\sऀ-ॿ']", " ", t)
    return " ".join(t.split())


def boundary_errors(truth: list[dict[str, Any]], hyp: list[dict[str, Any]]) -> list[int]:
    """Match words in order by normalized text (greedy), return |start| and |end| errors in ms."""
    errs: list[int] = []
    j = 0
    for t in truth:
        tw = norm(t["w"])
        for k in range(j, min(len(hyp), j + 4)):
            if norm(hyp[k]["w"]) == tw:
                errs += [abs(hyp[k]["start_ms"] - t["start_ms"]), abs(hyp[k]["end_ms"] - t["end_ms"])]
                j = k + 1
                break
    return errs


def p95(v: list[int]) -> float | None:
    return float(sorted(v)[max(0, math.ceil(0.95 * len(v)) - 1)]) if v else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="openai/whisper-large-v3,openai/whisper-large-v3-turbo")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--no-gemma", action="store_true")
    ap.add_argument("--no-rocm", action="store_true")
    args = ap.parse_args()
    settings = load_settings()
    man = json.loads((REPO_ROOT / "eval" / "datasets" / "manifests" / "fleurs.json").read_text())
    exp = Experiment(
        "e15_asr",
        "dev",
        config={
            "models": args.models,
            "n_per_lang": args.n,
            "gemma": not args.no_gemma,
            "boundary_truth": "synthesizer word boundaries (synthetic clips; D-003)",
            "wer_normalisation": "lower-case, punctuation stripped",
        },
    )

    def body(e: Experiment) -> None:
        work = REPO_ROOT / "projects" / "_e15"
        acc: dict[str, dict[str, Any]] = {}
        for model in args.models.split(","):
            for lang in ("en", "hi", "it"):
                rows = [r for r in man["files"] if r["lang"] == lang][: args.n]
                res = run_worker(
                    "asr",
                    "transcribe_many",
                    {
                        "files": [str(REPO_ROOT / r["file"]) for r in rows],
                        "model": model,
                        "lang": lang,
                        "align": False,
                        "word_timestamps": False,  # WER needs text only; word timing is part 2
                    },
                    work,
                    None,
                    require_rocm=not args.no_rocm,
                    timeout_s=14400,
                )
                refs = [norm(r["transcription"]) for r in rows]
                hyps = [norm(x["text"]) for x in res["items"]]
                wall = sum(x["wall_s"] for x in res["items"])
                audio = sum(x["audio_s"] for x in res["items"])
                acc.setdefault(model, {})[lang] = {
                    "n": len(rows),
                    "wer": round(jiwer.wer(refs, hyps), 4),
                    "cer": round(jiwer.cer(refs, hyps), 4),
                    "rtf": round(wall / audio, 4) if audio else None,
                    "timestamps": True,
                    "rtf_without_word_timestamps": True,
                }
        if not args.no_gemma:
            client = LlmClient(settings, provider="local_audio", strict_provider=True)
            for lang in ("en", "hi", "it"):
                rows = [r for r in man["files"] if r["lang"] == lang][: args.n]
                refs, hyps, wall = [], [], 0.0
                for r in rows:
                    resp = client.call(
                        LlmRequest(
                            "asr_crosscheck",
                            {"language": LANG_NAMES[lang]},
                            seed=0,
                            audio=REPO_ROOT / r["file"],
                            label=f"e15:{lang}",
                        ),
                        provider="local_audio",
                    )
                    refs.append(norm(r["transcription"]))
                    hyps.append(norm(str(resp.obj.get("text", ""))))
                    wall += resp.latency_s
                acc.setdefault("google/gemma-4-E4B-it", {})[lang] = {
                    "n": len(rows),
                    "wer": round(jiwer.wer(refs, hyps), 4),
                    "cer": round(jiwer.cer(refs, hyps), 4),
                    "latency_s_total": round(wall, 2),
                    "timestamps": False,
                }
        e.summary["accuracy"] = acc
        # Part 2: boundary error on synthetic clips with known word boundaries
        clips: list[tuple[Path, list[dict[str, Any]]]] = []
        fx = REPO_ROOT / "tests" / "fixtures" / "fixture20"
        clips.append((fx / "source.mp4", json.loads((fx / "canned" / "words.json").read_text())["words"]))
        for meta in sorted((REPO_ROOT / "data" / "adversarial").glob("*.json")):
            m = json.loads(meta.read_text())
            if m.get("synth_words"):
                clips.append((meta.with_suffix(".mp4"), m["synth_words"]))
        import subprocess

        bound: dict[str, dict[str, Any]] = {}
        for model in args.models.split(","):
            raw_e: list[int] = []
            al_e: list[int] = []
            files = []
            for mp4, _ in clips:
                wav = work / f"{mp4.stem}.16k.wav"
                work.mkdir(parents=True, exist_ok=True)
                subprocess.run(
                    [
                        "ffmpeg",
                        "-loglevel",
                        "error",
                        "-y",
                        "-i",
                        str(mp4),
                        "-ac",
                        "1",
                        "-ar",
                        "16000",
                        str(wav),
                    ],
                    check=True,
                )
                files.append(str(wav))
            req = {"files": files, "model": model, "lang": "en", "align": True}
            try:
                res = run_worker(
                    "asr", "transcribe_many", req, work, None, require_rocm=not args.no_rocm, timeout_s=7200
                )
            except OutOfMemoryError:
                if not args.no_rocm:
                    raise
                # Word timestamps of a large model do not fit limited accelerator memory: same request on the CPU,
                # recorded per model below (never silent).
                res = run_worker(
                    "asr",
                    "transcribe_many",
                    {**req, "device": "cpu"},
                    work,
                    None,
                    require_rocm=False,
                    timeout_s=14400,
                )
            for (_mp4, truth), item in zip(clips, res["items"], strict=True):
                raw_e += boundary_errors(truth, item["raw_words"])
                al_e += boundary_errors(truth, item["words"])
            bound[model] = {
                "device": res.get("device"),
                "raw": {
                    "n": len(raw_e),
                    "median_ms": statistics.median(raw_e) if raw_e else None,
                    "p95_ms": p95(raw_e),
                },
                "aligned": {
                    "n": len(al_e),
                    "median_ms": statistics.median(al_e) if al_e else None,
                    "p95_ms": p95(al_e),
                },
            }
        e.summary["boundary_error"] = bound
        # decision (dev only): lowest English WER among Whisper models; aligner on if it lowers p95 error
        whisper = {m: v for m, v in acc.items() if "whisper" in m}
        chosen = min(whisper, key=lambda m: whisper[m]["en"]["wer"]) if whisper else None
        if chosen:
            b = bound[chosen]
            align_on = (b["aligned"]["p95_ms"] or 1e9) < (b["raw"]["p95_ms"] or 1e9)
            p = b["aligned" if align_on else "raw"]["p95_ms"]
            e.summary["decision"] = {
                "asr_model": chosen,
                "aligner": align_on,
                "guard_ms": int(math.ceil((p or 120) / 10.0) * 10),
            }
        e.checks["decision_made"] = chosen is not None

    return run_experiment(exp, body)


if __name__ == "__main__":
    raise SystemExit(main())
