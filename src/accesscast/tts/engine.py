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

ENGINE_REV = "kokoro-82m@v1.0+seeded"  # seed per line (E9); bumps the TTS cache key
VOICES = {"en": "af_heart", "hi": "hf_alpha", "it": "if_sara"}  # Kokoro voice ids (Katha's map, MIT)
VOICEOVER_VOICES = {"hi": "hm_omega", "it": "im_nicola"}  # distinct from the description voice
CAL_DIR = REPO_ROOT / "src" / "accesscast" / "tts" / "calibration"


def load_calibration(voice: str, speed: float = 1.0) -> Calibration:
    f = CAL_DIR / f"calibration.{voice}.json"
    if f.exists():
        d = json.loads(f.read_text())
        return Calibration(
            voice=voice, wps_voice=float(d["wps_voice"]), intercept_s=float(d["intercept_s"]), measured=True
        )
    return Calibration(voice=voice, wps_voice=2.6, intercept_s=0.0, measured=False)


def tts_key(text: str, voice: str, speed: float) -> str:
    return sha256_text(
        canonical_json({"text": text, "voice": voice, "speed": round(speed, 3), "engine": ENGINE_REV})
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
        if voice is None:
            raise ValueError(f"no TTS voice for language {it.lang!r} (no fallback to English)")
        key = tts_key(it.text, voice, speed)
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
                }
            )
    engine = "kokoro-82m"
    if todo:
        if workers_available():
            run_worker("tts", "synth", {"lines": todo}, tts_dir / "req", events, require_rocm=require_rocm)
        else:
            engine = "placeholder"
            for t in todo:
                _placeholder(
                    Path(str(t["out"])), nlp.word_count(str(t["text"])), load_calibration(str(t["voice"])).wps_voice
                )
                Path(str(t["out"]) + ".placeholder").write_text("placeholder tone; no TTS worker installed\n")
    result = []
    for it in items:
        key, voice, out = keyed[it.id]
        info = sf.info(str(out))
        is_ph = Path(str(out) + ".placeholder").exists()
        flags = [*it.flags, "placeholder_tts"] if is_ph and "placeholder_tts" not in it.flags else it.flags
        result.append(
            it.model_copy(
                update={
                    "tts": TtsInfo(
                        voice=voice,
                        speed=speed,
                        sha256=key,
                        duration_ms=round(info.duration * 1000),
                        engine="placeholder" if is_ph else engine,
                    ),
                    "flags": flags,
                }
            )
        )
    return result
