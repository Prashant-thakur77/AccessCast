"""Independent E1 measurement (PLAN §15.3 E1 step 3). Imports NO AccessCast verifier, analysis or timing code.

Speech reference 1 = human caption cue times on the original mix (W3C's captions for test videos).
Speech reference 2 = an energy detector on the original audio (not Silero, not our VAD), reported separately.
A description line "fits" if its rendered span — measured from the rendered description stem, which the mixer
writes separately — overlaps no reference speech span by more than 50 ms and ends before the next cue starts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf

TOL_MS = 50  # PLAN §15.3: overlap tolerance


@dataclass(frozen=True)
class Span:
    start_ms: int
    end_ms: int


def _ts(s: str) -> int:
    parts = s.strip().split(":")
    sec = float(parts[-1])
    mins = int(parts[-2]) if len(parts) >= 2 else 0
    hours = int(parts[-3]) if len(parts) >= 3 else 0
    return round((hours * 3600 + mins * 60 + sec) * 1000)


def read_vtt_spans(path: Path) -> list[Span]:
    """Minimal WebVTT cue-time reader (independent of webvtt-py and of our captions code)."""
    spans = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r"\s*([\d:.]+)\s+-->\s+([\d:.]+)", line)
        if m:
            spans.append(Span(_ts(m.group(1)), _ts(m.group(2))))
    return sorted(spans, key=lambda s: s.start_ms)


def energy_speech_spans(wav: Path, *, frame_ms: int = 20, min_ms: int = 200, gap_ms: int = 250) -> list[Span]:
    """Frames whose RMS is above max(−45 dBFS, median + 10 dB) count as sound; merge gaps < 250 ms."""
    a, sr = sf.read(str(wav), dtype="float32", always_2d=True)
    mono = a.mean(axis=1)
    hop = int(sr * frame_ms / 1000)
    n = len(mono) // hop
    if n == 0:
        return []
    rms = np.sqrt(np.mean(mono[: n * hop].reshape(n, hop) ** 2, axis=1) + 1e-12)
    db = 20 * np.log10(rms)
    thr = max(-45.0, float(np.median(db)) + 10.0)
    on = db > thr
    spans: list[Span] = []
    i = 0
    while i < n:
        if on[i]:
            j = i
            while j < n and on[j]:
                j += 1
            spans.append(Span(i * frame_ms, j * frame_ms))
            i = j
        else:
            i += 1
    merged: list[Span] = []
    for s in spans:
        if merged and s.start_ms - merged[-1].end_ms < gap_ms:
            merged[-1] = Span(merged[-1].start_ms, s.end_ms)
        else:
            merged.append(s)
    return [s for s in merged if s.end_ms - s.start_ms >= min_ms]


def stem_line_spans(
    stem: Path, expected: list[tuple[str, int, int]], *, thr: float = 0.003
) -> dict[str, Span]:
    """Measure each line's actual rendered span from the stem around where it was placed."""
    a, sr = sf.read(str(stem), dtype="float32", always_2d=True)
    env = np.abs(a).max(axis=1)
    out = {}
    for lid, s_ms, e_ms in expected:
        lo = max(0, int((s_ms - 200) * sr / 1000))
        hi = min(len(env), int((e_ms + 200) * sr / 1000))
        idx = np.flatnonzero(env[lo:hi] > thr)
        if idx.size:
            out[lid] = Span(round((lo + idx[0]) * 1000 / sr), round((lo + idx[-1]) * 1000 / sr))
    return out


def overlap_ms(a: Span, b: Span) -> int:
    return max(0, min(a.end_ms, b.end_ms) - max(a.start_ms, b.start_ms))


def fits(line: Span, cues: list[Span]) -> tuple[bool, int, str]:
    """(fits, worst overlap ms, reason)."""
    worst = max((overlap_ms(line, c) for c in cues), default=0)
    if worst > TOL_MS:
        return False, worst, "overlaps speech"
    nxt = [c for c in cues if c.start_ms >= line.start_ms - TOL_MS]
    if nxt and line.end_ms > nxt[0].start_ms + TOL_MS:
        return False, worst, "runs past the start of the next cue"
    return True, worst, "fits"


def coverage(lines: list[Span], human_positions: list[int], window_ms: int = 3000) -> tuple[int, int]:
    """How many human description positions have one of our lines starting within ±3 s."""
    hit = sum(1 for h in human_positions if any(abs(ln.start_ms - h) <= window_ms for ln in lines))
    return hit, len(human_positions)
