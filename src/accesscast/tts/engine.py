"""S9 text to speech via the TTS worker, with a content-addressed cache (PLAN §9 S9).

Cache key = SHA-256 of (text, voice, speed, engine revision): the speed multiplier is part of the key
(AudioSight left it out). If no worker environment exists (CI, fake mode without `make setup`), a
placeholder tone of the estimated duration is written and the item is flagged `placeholder_tts`.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import soundfile as sf

from accesscast.config import REPO_ROOT
from accesscast.events import EventLog
from accesscast.project import canonical_json, sha256_text
from accesscast.schemas import Item, TtsInfo
from accesscast.verify import nlp
from accesscast.workers_client import run_worker, workers_available
from accesscast.write.plan_ad import Calibration

ENGINE_REV = "kokoro-82m@v1.0+seeded"
CHATTERBOX_REV = "chatterbox-multilingual@v3+seeded"
CHATTERBOX_PY = REPO_ROOT / "workers" / "chatterbox" / ".venv" / "bin" / "python"


def engine_for(lang: str) -> str:
    """kokoro (default) or chatterbox for hi/it, chosen by ACCESSCAST_TTS_ENGINE_HI_IT after the voice check."""
    import os

    if lang in ("hi", "it") and os.environ.get("ACCESSCAST_TTS_ENGINE_HI_IT", "kokoro") == "chatterbox":
        return "chatterbox"
    return "kokoro"  # seed per line (E9); bumps the TTS cache key


VOICES = {
    "en": "af_heart",
    "hi": "hf_alpha",
    "it": "if_sara",
    "es": "ef_dora",
    "fr": "ff_siwis",
}  # Kokoro voice ids (Katha's map, MIT)
VOICEOVER_VOICES = {
    "hi": "hm_omega",
    "it": "im_nicola",
    "es": "em_alex",
    "fr": "ff_siwis",
}  # distinct from the description voice where Kokoro has one (French has a single voice)
CAL_DIR = REPO_ROOT / "src" / "accesscast" / "tts" / "calibration"


def load_calibration(voice: str, speed: float = 1.0) -> Calibration:
    f = CAL_DIR / f"calibration.{voice}.json"
    if f.exists():
        d = json.loads(f.read_text())
        return Calibration(
            voice=voice, wps_voice=float(d["wps_voice"]), intercept_s=float(d["intercept_s"]), measured=True
        )
    return Calibration(voice=voice, wps_voice=2.6, intercept_s=0.0, measured=False)


def tts_key(text: str, voice: str, speed: float, engine: str = "kokoro") -> str:
    rev = CHATTERBOX_REV if engine == "chatterbox" else ENGINE_REV
    return sha256_text(
        canonical_json({"text": text, "voice": voice, "speed": round(speed, 3), "engine": rev})
    )


def _placeholder(path: Path, words: int, wps: float) -> int:
    dur = max(0.4, words / max(wps, 0.1))
    sr = 24_000
    t = np.arange(int(dur * sr)) / sr
    tone = 0.08 * np.sin(2 * np.pi * 220 * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 3 * t))
    sf.write(path, tone.astype(np.float32), sr, subtype="PCM_16")
    return round(dur * 1000)


def synthesize(
    items: Sequence[Item],
    tts_dir: Path,
    events: EventLog | None,
    *,
    voice_for: dict[str, str] | None = None,
    require_rocm: bool = False,
    speed: float = 1.0,
) -> list[Item]:
    tts_dir.mkdir(parents=True, exist_ok=True)
    voice_for = voice_for or VOICES
    todo: list[dict[str, str | float]] = []
    keyed: dict[str, tuple[str, str, Path]] = {}
    for it in items:
        voice = voice_for.get(it.lang)
        if voice is not None and engine_for(it.lang) == "chatterbox":
            voice = (
                "chatterbox-default"  # Chatterbox uses its built-in reference voice, not a Kokoro voice id
            )
        if voice is None:
            raise ValueError(f"no TTS voice for language {it.lang!r} (no fallback to English)")
        key = tts_key(it.text, voice, speed, engine_for(it.lang))
        out = tts_dir / f"{key}.wav"
        keyed[it.id] = (key, voice, out)
        if not out.exists():
            todo.append(
                {
                    "id": it.id,
                    "text": it.text,
                    "lang": it.lang,
                    "voice": voice,
                    "speed": speed,
                    "out": str(out),
                    "engine": engine_for(it.lang),
                }
            )
    engine = "kokoro-82m"
    if todo:
        if workers_available():
            kok = [t for t in todo if t.get("engine") == "kokoro"]
            cbx = [t for t in todo if t.get("engine") == "chatterbox"]
            if kok:
                run_worker("tts", "synth", {"lines": kok}, tts_dir / "req", events, require_rocm=require_rocm)
            if cbx:
                res = run_worker(
                    "chatterbox",
                    "synth",
                    {"lines": cbx},
                    tts_dir / "req",
                    events,
                    require_rocm=require_rocm,
                    python=CHATTERBOX_PY,
                )
                for r in res["items"]:
                    if r.get("eos_forced"):
                        Path(str(r["path"]) + ".eos_forced").write_text("chatterbox forced end of sentence\n")
        else:
            engine = "placeholder"
            for t in todo:
                _placeholder(
                    Path(str(t["out"])),
                    nlp.word_count(str(t["text"])),
                    load_calibration(str(t["voice"])).wps_voice,
                )
                Path(str(t["out"]) + ".placeholder").write_text("placeholder tone; no TTS worker installed\n")
    result = []
    for it in items:
        key, voice, out = keyed[it.id]
        info = sf.info(str(out))
        is_ph = Path(str(out) + ".placeholder").exists()
        flags = (
            [*it.flags, "placeholder_tts"] if is_ph and "placeholder_tts" not in it.flags else list(it.flags)
        )
        if Path(str(out) + ".eos_forced").exists() and "tts_eos_forced" not in flags:
            flags.append("tts_eos_forced")  # may be cut short: shown to the reviewer
        result.append(
            it.model_copy(
                update={
                    "tts": TtsInfo(
                        voice=voice,
                        speed=speed,
                        sha256=key,
                        duration_ms=round(info.duration * 1000),
                        engine="placeholder"
                        if is_ph
                        else ("chatterbox-multilingual" if engine_for(it.lang) == "chatterbox" else engine),
                    ),
                    "flags": flags,
                }
            )
        )
    return result
