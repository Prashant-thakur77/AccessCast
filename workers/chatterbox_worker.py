"""Chatterbox Multilingual TTS worker (MIT; ResembleAI). Runs in workers/chatterbox/.venv (its own torch pins).

Same request/response contract as tts_worker.synth. Chatterbox adds an imperceptible watermark (Perth) to every
clip; the player and MODEL_LICENSES.md disclose it. A "forcing EOS token" warning from its alignment analyzer is
recorded per line as `eos_forced`, because it can mean the line was cut short (checked by VO004 and by a person).
"""

from __future__ import annotations

import hashlib
import io
import logging
from typing import Any

import soundfile as sf

from common import device, event, main, stage_timer

_model: Any = None
LANGS = {"hi", "it", "en"}


class _EosCatcher(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.hit = False

    def emit(self, record: logging.LogRecord) -> None:
        if "forcing EOS" in record.getMessage():
            self.hit = True


def synth(p: dict[str, Any], require_rocm: bool) -> dict[str, Any]:
    global _model
    import torch
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS

    dev = device(require_rocm)
    if _model is None:
        _model = ChatterboxMultilingualTTS.from_pretrained(device=dev)
    timings: dict[str, Any] = {}
    out = []
    t_audio = 0.0
    catcher = _EosCatcher()
    logging.getLogger("chatterbox").addHandler(catcher)
    with stage_timer("tts", timings):
        for i, line in enumerate(p["lines"]):
            if line["lang"] not in LANGS:
                raise ValueError(f"unsupported TTS language {line['lang']!r} (no fallback)")
            seed = int(hashlib.sha256(f"{line['voice']}:{line.get('speed', 1.0)}:{line['text']}".encode()).hexdigest()[:8], 16)
            torch.manual_seed(seed)
            catcher.hit = False
            wav = _model.generate(line["text"], language_id=line["lang"])
            audio = wav.squeeze().cpu().numpy()
            buf = io.BytesIO()
            sf.write(buf, audio, _model.sr, format="WAV", subtype="PCM_16")
            with open(line["out"], "wb") as fh:
                fh.write(buf.getvalue())
            dur = len(audio) / _model.sr
            t_audio += dur
            out.append({"id": line["id"], "duration_ms": round(dur * 1000), "path": line["out"], "eos_forced": catcher.hit})
            event("progress", done=i + 1, total=len(p["lines"]))
    wall = timings["tts"]["wall_s"]
    return {"items": out, "engine": "chatterbox-multilingual", "device": dev, "timing": timings,
            "rtf": round(wall / t_audio, 4) if t_audio else None, "watermark": "perth (imperceptible)"}


if __name__ == "__main__":
    raise SystemExit(main({"synth": synth}))
