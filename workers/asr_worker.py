"""ASR worker (PLAN §9 S2): Silero VAD + Whisper word timestamps + optional wav2vec2 CTC forced alignment.

Actions:
  transcribe  {audio, lang, model?, align?, batch_size?} → {words, vad, raw_words, timing}
  vad         {audio} → {segments}

Chunks are cut at the lowest-energy 20 ms frame within ±2 s of each 30 s mark so no word is split.
Batch size is pinned (default 1) and recorded: AudioSight found batching shifted aligned timestamps.
Word probabilities are not extracted from Whisper here (recorded as null → 1.0); ASR uncertainty comes from
the independent Gemma E4B cross-check (S2b).
"""

from __future__ import annotations

import re
from typing import Any

import numpy as np
import soundfile as sf
from common import device, event, main, stage_timer

SR = 16_000
_cache: dict[str, Any] = {}
ALIGN_MODELS = {"en": "WAV2VEC2_ASR_BASE_960H"}  # torchaudio bundle (fairseq weights, MIT)


def load_audio(path: str) -> np.ndarray:
    a, sr = sf.read(path, dtype="float32", always_2d=False)
    if a.ndim > 1:
        a = a.mean(axis=1)
    if sr != SR:
        raise ValueError(f"expected {SR} Hz audio, got {sr}")
    return a


def cut_points(audio: np.ndarray, chunk_s: float = 30.0, search_s: float = 2.0) -> list[int]:
    n = len(audio)
    frame = int(0.02 * SR)
    cuts = [0]
    t = chunk_s
    while t * SR < n - SR:
        lo, hi = int((t - search_s) * SR), min(n, int((t + search_s) * SR))
        seg = audio[lo:hi]
        k = max(1, len(seg) // frame)
        rms = np.sqrt(np.mean(seg[: k * frame].reshape(k, frame) ** 2, axis=1))
        cut = lo + int(np.argmin(rms)) * frame
        cuts.append(cut)
        t = cut / SR + chunk_s
    cuts.append(n)
    return cuts


def vad(p: dict[str, Any], require_rocm: bool) -> dict[str, Any]:
    from silero_vad import get_speech_timestamps, load_silero_vad

    audio = load_audio(p["audio"])
    import torch

    model = _cache.setdefault("vad", load_silero_vad())
    ts = get_speech_timestamps(torch.from_numpy(audio), model, sampling_rate=SR, return_seconds=False)
    return {"model": "silero-vad", "segments": [{"start_ms": round(t["start"] * 1000 / SR),
                                                  "end_ms": round(t["end"] * 1000 / SR)} for t in ts]}


def _whisper(model_id: str, dev: str) -> Any:
    key = f"whisper:{model_id}:{dev}"
    if key not in _cache:
        import torch
        from transformers import pipeline

        _cache[key] = pipeline("automatic-speech-recognition", model=model_id, device=0 if dev == "cuda" else -1,
                               torch_dtype=torch.float16 if dev == "cuda" else torch.float32)
    return _cache[key]


def _norm_en(w: str) -> str:
    return re.sub(r"[^A-Z']", "", w.upper())


def align_chunk(audio: np.ndarray, words: list[dict[str, Any]], offset_s: float, dev: str) -> int:
    """Re-time words in place with wav2vec2 CTC forced alignment. Returns the number of words aligned."""
    import torch
    import torchaudio
    import torchaudio.functional as F

    if "aligner" not in _cache:
        bundle = getattr(torchaudio.pipelines, ALIGN_MODELS["en"])
        _cache["aligner"] = (bundle.get_model().to(dev).eval(), bundle.get_labels(), bundle.sample_rate)
    model, labels, sr = _cache["aligner"]
    if sr != SR:
        raise ValueError("aligner sample rate mismatch")
    idx = {c: i for i, c in enumerate(labels)}
    keep = [(k, _norm_en(w["w"])) for k, w in enumerate(words)]
    keep = [(k, t) for k, t in keep if t and all(c in idx for c in t)]
    if not keep:
        return 0
    transcript = "|".join(t for _, t in keep)
    targets = torch.tensor([[idx[c] for c in transcript]], dtype=torch.int32, device=dev)
    with torch.inference_mode():
        emission, _ = model(torch.from_numpy(audio).unsqueeze(0).to(dev))
        emission = torch.log_softmax(emission, dim=-1)
    if emission.shape[1] < targets.shape[1]:
        return 0
    aligned, scores = F.forced_align(emission, targets, blank=0)
    spans = F.merge_tokens(aligned[0], scores[0].exp())
    ratio = audio.shape[0] / emission.shape[1] / SR
    # group token spans into words, separated by the '|' token
    sep = idx["|"]
    cur: list[Any] = []
    groups: list[list[Any]] = []
    for s in spans:
        if s.token == sep:
            if cur:
                groups.append(cur)
            cur = []
        else:
            cur.append(s)
    if cur:
        groups.append(cur)
    if len(groups) != len(keep):
        return 0
    for (k, _), g in zip(keep, groups, strict=True):
        words[k]["start_ms"] = round((offset_s + g[0].start * ratio) * 1000)
        words[k]["end_ms"] = round((offset_s + g[-1].end * ratio) * 1000)
        words[k]["aligned"] = True
    return len(keep)


def transcribe(p: dict[str, Any], require_rocm: bool) -> dict[str, Any]:
    dev = device(require_rocm)
    lang = p.get("lang", "en")
    model_id = p.get("model", "openai/whisper-large-v3")
    bs = int(p.get("batch_size", 1))
    audio = load_audio(p["audio"])
    timing: dict[str, Any] = {}
    with stage_timer("vad", timing):
        v = vad(p, require_rocm)
    asr = _whisper(model_id, dev)
    cuts = cut_points(audio)
    raw: list[dict[str, Any]] = []
    final: list[dict[str, Any]] = []
    aligned_n = 0
    with stage_timer("whisper", timing):
        for ci in range(len(cuts) - 1):
            a, b = cuts[ci], cuts[ci + 1]
            chunk = audio[a:b]
            out = asr({"raw": chunk, "sampling_rate": SR}, return_timestamps="word", batch_size=bs,
                      generate_kwargs={"language": lang, "task": "transcribe"})
            off = a / SR
            words = []
            for c in out.get("chunks") or []:
                ts = c.get("timestamp") or (None, None)
                if ts[0] is None or not c["text"].strip():
                    continue
                end = ts[1] if ts[1] is not None else ts[0] + 0.2
                words.append({"w": c["text"].strip(), "start_ms": round((off + ts[0]) * 1000),
                              "end_ms": round((off + end) * 1000), "seg": ci})
            raw.extend(dict(w) for w in words)
            if p.get("align", True) and lang in ALIGN_MODELS and words:
                aligned_n += align_chunk(chunk, words, off, dev)
            final.extend(words)
            event("progress", chunk=ci + 1, chunks=len(cuts) - 1)
    for lst in (raw, final):
        for k, w in enumerate(lst):
            w.pop("aligned", None)
            w.update({"i": k, "prob": 1.0, "speaker": None})
    words_all = final
    return {
        "words": {"lang": lang, "model": model_id, "aligned": aligned_n > 0, "words": words_all},
        "raw_words": {"lang": lang, "model": model_id, "aligned": False, "words": raw},
        "vad": v, "timing": timing, "device": dev, "batch_size": bs, "aligned_words": aligned_n,
        "chunks": [[round(cuts[i] / SR, 3), round(cuts[i + 1] / SR, 3)] for i in range(len(cuts) - 1)],
    }


if __name__ == "__main__":
    raise SystemExit(main({"transcribe": transcribe, "vad": vad}))
