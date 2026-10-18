"""TTS worker: Kokoro-82M (Apache-2.0). Actions: synth (batch of lines → wav files), calibrate.

Kokoro language codes and the hi/it voices (h/hf_alpha, i/if_sara) are listed below.
"""

from __future__ import annotations

import time
from typing import Any

import numpy as np
import soundfile as sf

from common import device, event, main, stage_timer

KOKORO_LANG = {"en": "a", "hi": "h", "it": "i", "es": "e", "fr": "f", "pt": "p"}
SR = 24_000
_pipes: dict[str, Any] = {}


def _pipe(lang: str, dev: str) -> Any:
    from kokoro import KPipeline

    if lang not in KOKORO_LANG:
        raise ValueError(f"unsupported TTS language {lang!r} (no fallback to English)")
    if lang not in _pipes:
        _pipes[lang] = KPipeline(lang_code=KOKORO_LANG[lang], repo_id="hexgrad/Kokoro-82M", device=dev)
    return _pipes[lang]


def _synth_one(pipe: Any, text: str, voice: str, speed: float) -> np.ndarray:
    # Kokoro's vocoder draws random noise; seed from the line itself so the same text, voice and speed always
    # give the same clip (E9 found 1780 vs 1789 ms for one line across fresh processes before this).
    import hashlib

    import torch

    torch.manual_seed(int(hashlib.sha256(f"{voice}:{speed}:{text}".encode()).hexdigest()[:8], 16))
    chunks = [r.audio.numpy() for r in pipe(text, voice=voice, speed=speed) if r.audio is not None]
    if not chunks:
        raise RuntimeError("TTS produced no audio")
    audio = np.concatenate(chunks).astype(np.float32)
    # trim leading/trailing near-silence so measured duration is the spoken duration
    idx = np.flatnonzero(np.abs(audio) > 0.003)
    if idx.size:
        audio = audio[max(0, idx[0] - 240) : idx[-1] + 240]
    return audio


def synth(p: dict[str, Any], require_rocm: bool) -> dict[str, Any]:
    dev = device(require_rocm)
    timings: dict[str, Any] = {}
    out = []
    t_audio = 0.0
    with stage_timer("tts", timings):
        for i, line in enumerate(p["lines"]):
            pipe = _pipe(line["lang"], dev)
            audio = _synth_one(pipe, line["text"], line["voice"], float(line.get("speed", 1.0)))
            sf.write(line["out"], audio, SR, subtype="PCM_16")
            dur = len(audio) / SR
            t_audio += dur
            out.append({"id": line["id"], "duration_ms": round(dur * 1000), "path": line["out"]})
            event("progress", done=i + 1, total=len(p["lines"]))
    wall = timings["tts"]["wall_s"]
    return {
        "items": out,
        "engine": "kokoro-82m",
        "device": dev,
        "timing": timings,
        "rtf": round(wall / t_audio, 4) if t_audio else None,
    }


def calibrate(p: dict[str, Any], require_rocm: bool) -> dict[str, Any]:
    """Fit duration_s = a + b × words over fixed sentences; wps_voice = 1/b (PLAN §14.5)."""
    dev = device(require_rocm)
    pipe = _pipe(p["lang"], dev)
    xs, ys = [], []
    t0 = time.perf_counter()
    for s in p["sentences"]:
        audio = _synth_one(pipe, s, p["voice"], float(p.get("speed", 1.0)))
        xs.append(len(s.split()))
        ys.append(len(audio) / SR)
    b, a = np.polyfit(np.array(xs, float), np.array(ys, float), 1)
    resid = np.array(ys) - (a + b * np.array(xs))
    return {
        "voice": p["voice"],
        "lang": p["lang"],
        "speed": p.get("speed", 1.0),
        "n": len(xs),
        "intercept_s": round(float(a), 4),
        "s_per_word": round(float(b), 4),
        "wps_voice": round(1 / float(b), 4),
        "resid_p95_s": round(float(np.percentile(np.abs(resid), 95)), 4),
        "device": dev,
        "wall_s": round(time.perf_counter() - t0, 2),
    }


if __name__ == "__main__":
    raise SystemExit(main({"synth": synth, "calibrate": calibrate}))
