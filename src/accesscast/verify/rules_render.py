"""Render checks RN001–RN008 (PLAN §10.6). A render that fails an error check is not published."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import numpy as np
import soundfile as sf

from accesscast import constants as C
from accesscast.media.ffmpeg import Loudness, ffprobe_json, measure_loudness, probe
from accesscast.verify.base import Finding, fmt_s


def rn001_duration(out: Path, expected_ms: int) -> list[Finding]:
    got = probe(out).duration_ms
    if abs(got - expected_ms) > C.RENDER_DURATION_TOL_MS + 40:  # +1 AAC frame of container slack
        return [Finding("RN001", "error", fmt_s(got), f"{fmt_s(expected_ms)} ± {C.RENDER_DURATION_TOL_MS} ms",
                        "The rendered video has the wrong length.", "render", repairable=False)]
    return []


def rn002_items_match(rendered_ids: Sequence[str], approved_ids: Sequence[str]) -> list[Finding]:
    missing = sorted(set(approved_ids) - set(rendered_ids))
    extra = sorted(set(rendered_ids) - set(approved_ids))
    if missing or extra:
        return [Finding("RN002", "error", f"missing {missing[:3]} extra {extra[:3]}", "exactly the approved items",
                        "The render does not match the approved lines.", "render", repairable=False)]
    return []


def rn003_loudness(out: Path, target_lufs: float) -> tuple[list[Finding], Loudness]:
    lo = measure_loudness(out)
    found = []
    if abs(lo.integrated_lufs - target_lufs) > C.LUFS_TOLERANCE:
        found.append(Finding("RN003", "error", f"{lo.integrated_lufs:.1f} LUFS", f"{target_lufs} ± {C.LUFS_TOLERANCE} LU",
                             "Loudness is off target.", "render", repairable=False))
    if lo.true_peak_dbtp > C.TRUE_PEAK_MAX:
        found.append(Finding("RN003", "error", f"true peak {lo.true_peak_dbtp:.1f} dBTP", f"≤ {C.TRUE_PEAK_MAX} dBTP",
                             "Audio peaks too high.", "render", repairable=False))
    return found, lo


def rn004_duck_depth(master: Path, mixed_no_desc: Path | None, spans: Sequence[tuple[int, int]]) -> list[Finding]:
    """Warning: measured dip of the original under description, from the pre-normalisation ducked bed."""
    if mixed_no_desc is None or not spans:
        return []
    a, sr = sf.read(str(master), dtype="float32", always_2d=True)
    b, _ = sf.read(str(mixed_no_desc), dtype="float32", always_2d=True)
    dips = []
    for s, e in spans:
        i, j = int(s * sr / 1000), int(e * sr / 1000)
        ra = float(np.sqrt(np.mean(a[i:j] ** 2)) + 1e-9)
        rb = float(np.sqrt(np.mean(b[i:j] ** 2)) + 1e-9)
        if ra > 1e-4:
            dips.append(20 * np.log10(ra / rb))
    if dips and (min(dips) < C.DUCK_DB_MIN - 0.5 or max(dips) > C.DUCK_DB_MAX + 0.5):
        return [Finding("RN004", "warning", f"dip {min(dips):.1f}–{max(dips):.1f} dB", f"{C.DUCK_DB_MIN}–{C.DUCK_DB_MAX} dB",
                        "The original sound is not dipped by the expected amount.", "render", repairable=False)]
    return []


def rn005_av_sync(out: Path) -> list[Finding]:
    d = ffprobe_json(out)
    starts = {s.get("codec_type"): float(s.get("start_time") or 0) for s in d.get("streams", [])}
    off = abs(starts.get("video", 0.0) - starts.get("audio", 0.0)) * 1000
    if off > C.AV_SYNC_TOL_MS:
        return [Finding("RN005", "error", f"{off:.0f} ms", f"≤ {C.AV_SYNC_TOL_MS} ms",
                        "Audio and video start out of sync.", "render", repairable=False)]
    return []


def rn006_vtt_valid(track: Path) -> list[Finding]:
    import webvtt

    try:
        cues = list(webvtt.read(str(track)))
    except Exception as e:
        return [Finding("RN006", "error", f"parse error {type(e).__name__}", "valid WebVTT",
                        "A caption track is broken.", "render", repairable=False)]
    last = -1.0
    for c in cues:
        if c.start_in_seconds < last:
            return [Finding("RN006", "error", f"cue {c.identifier} out of order", "monotonic cues",
                            "Caption cues are out of order.", "render", repairable=False)]
        last = c.start_in_seconds
    return []


def rn007_human_reviewed(human_reviewed: bool, public: bool) -> list[Finding]:
    if public and not human_reviewed:
        return [Finding("RN007", "error", "human_reviewed=false", "true for public export",
                        "Not every line was approved by a person.", "review", repairable=False)]
    return []


def rn008_no_overlap(stem: Path, speech: Sequence[tuple[int, int]], offset_map: object = None) -> list[Finding]:
    """Rendered description stem vs the original's speech spans: any overlap > 50 ms is an error."""
    a, sr = sf.read(str(stem), dtype="float32", always_2d=True)
    env = np.abs(a).max(axis=1)
    hop = sr // 100  # 10 ms
    active = np.array([env[i : i + hop].max() > 0.01 for i in range(0, len(env), hop)])
    worst = 0
    for s, e in speech:
        i, j = max(0, s // 10), min(len(active), e // 10)
        if j > i:
            worst = max(worst, int(active[i:j].sum()) * 10)
    if worst > C.RENDER_OVERLAP_TOL_MS:
        return [Finding("RN008", "error", f"{worst} ms of description over speech", f"≤ {C.RENDER_OVERLAP_TOL_MS} ms",
                        "A description line plays on top of dialogue.", "render", repairable=False)]
    return []
