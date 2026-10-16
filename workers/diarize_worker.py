"""Speaker diarization worker: pyannote.audio (MIT) with pyannote/speaker-diarization-community-1 (CC-BY-4.0,
gated: the HF token must have accepted its conditions). Runs in its own env (workers/diarize/.venv).

Action `diarize`: {"audio": wav path, "min_speakers"?, "max_speakers"?} → exclusive speaker turns (one speaker at a
time, the form captions need), speaker count and timing. Labels are anonymous (S1, S2, … in order of first
appearance); they are never names.
"""

from __future__ import annotations

import os
from typing import Any

from common import device, event, main, stage_timer

MODEL = "pyannote/speaker-diarization-community-1"
_pipe: dict[str, Any] = {}


def diarize(p: dict[str, Any], require_rocm: bool) -> dict[str, Any]:
    import soundfile as sf
    import torch
    from pyannote.audio import Pipeline

    dev = device(require_rocm)
    if "pipe" not in _pipe:
        token = os.environ.get("HF_TOKEN")
        if not token:
            raise RuntimeError("HF_TOKEN is not set; the diarization model is gated")
        pipe = Pipeline.from_pretrained(MODEL, token=token)
        if pipe is None:
            raise RuntimeError(f"could not load {MODEL} (licence not accepted for this token?)")
        pipe.to(torch.device(dev))
        _pipe["pipe"] = pipe
    audio, sr = sf.read(p["audio"], dtype="float32", always_2d=True)
    wave = torch.from_numpy(audio.T.copy())
    kw = {k: int(p[k]) for k in ("min_speakers", "max_speakers") if p.get(k)}
    timing: dict[str, Any] = {}
    with stage_timer("diarize", timing):
        out = _pipe["pipe"]({"waveform": wave, "sample_rate": sr}, **kw)
    ann = getattr(out, "exclusive_speaker_diarization", None) or getattr(out, "speaker_diarization", out)
    names: dict[str, str] = {}
    turns = []
    for seg, _track, label in ann.itertracks(yield_label=True):
        if label not in names:
            names[label] = f"S{len(names) + 1}"
        turns.append({"start_ms": round(seg.start * 1000), "end_ms": round(seg.end * 1000), "speaker": names[label]})
    event("progress", turns=len(turns))
    return {"model": MODEL, "turns": turns, "speakers": len(names), "device": dev, "timing": timing}


if __name__ == "__main__":
    raise SystemExit(main({"diarize": diarize}))
