"""S14 audio mixing (PLAN §9 S14).

Ducking uses a deterministic gain envelope computed from the known clip times (not sidechaincompress,
whose dip depends on level). The envelope and the mix are computed in numpy at 48 kHz; loudness is then
normalised with ffmpeg's two-pass `loudnorm` with I always set explicitly (ffmpeg's default is −24).
The description stem is written separately so E1 can measure overlap from the rendered stem.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf

from accesscast import constants as C
from accesscast.errors import MediaError
from accesscast.media.ffmpeg import run_ffmpeg
from accesscast.media.timeline import Insertion, build_timeline, ms_to_samples

SR = C.MASTER_SAMPLE_RATE


@dataclass(frozen=True)
class Clip:
    item_id: str
    wav: Path
    start_ms: int  # where the voice starts on the timeline it is placed on
    duck_db: float = C.DUCK_DB


def load_48k(path: Path, tmp_dir: Path) -> np.ndarray:
    """Load any wav as 48 kHz stereo float32 (resampled by ffmpeg when needed)."""
    info = sf.info(str(path))
    if info.samplerate != SR or info.channels != 2:
        out = tmp_dir / f"{path.stem}.48k.wav"
        if not out.exists():
            run_ffmpeg(["-i", str(path), "-ar", str(SR), "-ac", "2", "-c:a", "pcm_f32le", str(out)])
        path = out
    data, _ = sf.read(str(path), dtype="float32", always_2d=True)
    return np.asarray(data, dtype=np.float32)


def gain_envelope(
    n: int, spans: Sequence[tuple[int, int, float]], ramp_ms: int = C.DUCK_RAMP_MS
) -> np.ndarray:
    """Linear gain per sample: 1.0, dipping to 10^(−dB/20) over each [start, end] with ramps outside it."""
    env = np.ones(n, dtype=np.float32)
    ramp = ms_to_samples(ramp_ms)
    for s_ms, e_ms, db in spans:
        lo = 10 ** (-db / 20)
        s, e = ms_to_samples(s_ms), ms_to_samples(e_ms)
        seg = np.ones(n, dtype=np.float32)
        a0, a1 = max(0, s - ramp), max(0, s)
        if a1 > a0:
            seg[a0:a1] = np.linspace(1.0, lo, a1 - a0, dtype=np.float32)
        seg[max(0, s) : min(n, e)] = lo
        b0, b1 = min(n, e), min(n, e + ramp)
        if b1 > b0:
            seg[b0:b1] = np.linspace(lo, 1.0, b1 - b0, dtype=np.float32)
        env = np.minimum(env, seg)
    return env


def place(stem: np.ndarray, clip: np.ndarray, start_sample: int) -> None:
    a = max(0, start_sample)
    b = min(len(stem), a + len(clip))
    if b > a:
        stem[a:b] += clip[: b - a]


def loudnorm_2pass(src: Path, dst: Path, target_lufs: float) -> dict[str, float]:
    """Two-pass loudnorm: measure, then apply with measured_* and linear=true (I set explicitly)."""
    flt = f"loudnorm=I={target_lufs}:TP={C.TRUE_PEAK_MAX - 0.5}:LRA=11"
    err = run_ffmpeg(["-i", str(src), "-af", f"{flt}:print_format=json", "-f", "null", "-"])
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", err, re.S)
    if not m:
        raise MediaError("loudnorm pass 1 produced no measurement")
    meas = json.loads(m.group(0))
    second = (
        f"{flt}:measured_I={meas['input_i']}:measured_TP={meas['input_tp']}:measured_LRA={meas['input_lra']}"
        f":measured_thresh={meas['input_thresh']}:offset={meas['target_offset']}:linear=true"
    )
    run_ffmpeg(["-i", str(src), "-af", second, "-ar", str(SR), "-c:a", "pcm_f32le", str(dst)])
    return {
        k: float(v)
        for k, v in meas.items()
        if k.startswith(("input_", "target_")) and v not in ("-inf", "inf")
    }


def mix_standard(
    master: Path,
    clips: Sequence[Clip],
    out_mix: Path,
    out_stem: Path,
    tmp_dir: Path,
    extra_spans: Sequence[tuple[int, int, float]] = (),
    stem_ids: set[str] | None = None,
) -> dict[str, object]:
    """Original dipped under each clip, clips placed at their start; writes the mix and the stem.

    The stem holds only the clips in `stem_ids` (the description lines) when given, so RN008 and E1 measure
    description, never a dubbed voice-over."""
    tmp_dir.mkdir(parents=True, exist_ok=True)
    orig, sr = sf.read(str(master), dtype="float32", always_2d=True)
    if sr != SR:
        raise MediaError(f"master must be {SR} Hz, got {sr}")
    if orig.shape[1] == 1:
        orig = np.repeat(orig, 2, axis=1)
    stem = np.zeros_like(orig)
    voices = np.zeros_like(orig)
    spans: list[tuple[int, int, float]] = list(extra_spans)
    for c in clips:
        audio = load_48k(c.wav, tmp_dir)
        place(voices, audio, ms_to_samples(c.start_ms))
        if stem_ids is None or c.item_id in stem_ids:
            place(stem, audio, ms_to_samples(c.start_ms))
        spans.append((c.start_ms, c.start_ms + round(len(audio) * 1000 / SR), c.duck_db))
    env = gain_envelope(len(orig), spans)
    mixed = orig * env[:, None] + voices
    peak = float(np.max(np.abs(mixed))) if mixed.size else 0.0
    if peak > 0.99:
        mixed *= 0.99 / peak
    sf.write(str(out_mix), mixed, SR, subtype="PCM_24")
    sf.write(str(out_stem), stem, SR, subtype="PCM_24")
    sf.write(str(out_stem.with_suffix(".bed.wav")), orig * env[:, None], SR, subtype="PCM_24")  # for RN004
    return {"clips": len(clips), "duck_spans": len(spans), "spans": [(a, b) for a, b, _ in spans]}


def mix_extended(
    master: Path,
    insertions: Sequence[Clip],
    standard: Sequence[Clip],
    out_mix: Path,
    out_stem: Path,
    tmp_dir: Path,
    fps: float | None = None,
) -> list[dict[str, object]]:
    """Expanded timeline: the source pauses (silence) at each insertion point while the clip plays.

    Returns the source_to_output rows (AudioSight timeline format). Standard clips are remapped. With `fps`, every
    cut point and every hold is snapped to the source's frame grid (cut to the nearest frame, hold rounded up to
    whole frames), because the video can only cut and hold whole frames: off-grid times let the picture drift from
    the description audio by up to a frame per hold (E9: 120 ms on one dev clip, refused by RN001).
    """
    tmp_dir.mkdir(parents=True, exist_ok=True)
    orig, _ = sf.read(str(master), dtype="float32", always_2d=True)
    if orig.shape[1] == 1:
        orig = np.repeat(orig, 2, axis=1)
    pre, post = ms_to_samples(C.EXT_PAD_MS), ms_to_samples(C.EXT_PAD_MS)
    loaded = {c.item_id: load_48k(c.wav, tmp_dir) for c in [*insertions, *standard]}
    ins = []
    for c in insertions:
        at, speech = min(len(orig), ms_to_samples(c.start_ms)), len(loaded[c.item_id])
        tail = post
        if fps:
            frame = SR / fps
            at = min(len(orig), round(round(at / frame) * frame))
            total = pre + speech + post
            tail = post + math.ceil(math.ceil(total / frame) * frame) - total
        ins.append(Insertion(c.item_id, at, speech, pre, tail))
    rows = build_timeline(len(orig), ins)
    total = int(rows[-1]["output_end_sample"]) if rows else len(orig)
    out = np.zeros((total, 2), dtype=np.float32)
    stem = np.zeros_like(out)
    fade = ms_to_samples(C.EXT_FADE_MS)
    for r in rows:
        if r["type"] == "source":
            seg = orig[int(r["source_start_sample"]) : int(r["source_end_sample"])].copy()
            if len(seg) > 2 * fade:  # 10 ms fades at every cut
                seg[:fade] *= np.linspace(0, 1, fade, dtype=np.float32)[:, None]
                seg[-fade:] *= np.linspace(1, 0, fade, dtype=np.float32)[:, None]
            out[int(r["output_start_sample"]) : int(r["output_start_sample"]) + len(seg)] = seg
        else:
            clip = loaded[str(r["narration_id"])]
            place(stem, clip, int(r["output_start_sample"]) + pre)
    from accesscast.media.timeline import remap_ms

    spans = []
    for c in standard:
        start = remap_ms(rows, c.start_ms)
        clip = loaded[c.item_id]
        place(stem, clip, ms_to_samples(start))
        spans.append((start, start + round(len(clip) * 1000 / SR), c.duck_db))
    env = gain_envelope(len(out), spans)
    mixed = out * env[:, None] + stem
    peak = float(np.max(np.abs(mixed))) if mixed.size else 0.0
    if peak > 0.99:
        mixed *= 0.99 / peak
    sf.write(str(out_mix), mixed, SR, subtype="PCM_24")
    sf.write(str(out_stem), stem, SR, subtype="PCM_24")
    return rows
