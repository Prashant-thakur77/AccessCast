# Scene-merge similarity (top-62% crop, 9x8 dHash, H/S histogram correlation, 0.45/0.55 weights,
# 0.82/0.92/0.45 decisions, 1,200 ms dialogue bridge) follows AudioSight's src/audiosight/clustering.py
# (https://github.com/austin1997/AudioSight), Apache License 2.0, Copyright 2026 AudioSight contributors.
# Re-written for AccessCast with PIL/numpy (no OpenCV in the core process). Changes: frames are read by
# ffmpeg at exact timestamps from the proxy; "previous word" uses end time; 0.92 is a named constant.
"""S1 scenes: merge shots into scenes with deterministic rules, Gemma only for undecided boundaries."""

from __future__ import annotations

import io
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from accesscast import constants as C
from accesscast.errors import MediaError
from accesscast.media.ffmpeg import run_ffmpeg
from accesscast.schemas import Scene, Scenes, Shot, Word


def grab_frame(video: Path, t_ms: int) -> Image.Image:
    """Frame at t_ms; near a stream end ffmpeg can decode nothing, so step back up to 1 s before giving up."""
    for back in (0, 200, 500, 1000):
        t = max(0, t_ms - back)
        out = Path(str(video) + f".{t}.tmp.png")
        try:
            run_ffmpeg(["-ss", f"{t / 1000:.3f}", "-i", str(video), "-frames:v", "1", str(out)])
            if out.exists() and out.stat().st_size > 0:
                return Image.open(io.BytesIO(out.read_bytes())).convert("RGB")
        finally:
            out.unlink(missing_ok=True)
    raise MediaError(f"no frame decodable near {t_ms} ms in {video.name}")


def _crop_top(img: Image.Image) -> Image.Image:
    w, h = img.size
    return img.crop((0, 0, w, max(1, round(h * C.SCENE_CROP_TOP_FRACTION))))


def dhash_bits(img: Image.Image) -> np.ndarray:
    g = np.asarray(_crop_top(img).convert("L").resize((9, 8), Image.Resampling.BILINEAR), dtype=np.int16)
    return (g[:, 1:] > g[:, :-1]).flatten()


def hs_hist(img: Image.Image) -> np.ndarray:
    hsv = np.asarray(_crop_top(img).convert("HSV"), dtype=np.int32)
    h = hsv[..., 0].flatten() * 32 // 256
    s = hsv[..., 1].flatten() * 32 // 256
    hist = np.bincount(h * 32 + s, minlength=32 * 32).astype(np.float64)
    return hist / max(hist.sum(), 1.0)


def similarity(a: Image.Image, b: Image.Image) -> float:
    d = 1.0 - float(np.count_nonzero(dhash_bits(a) != dhash_bits(b))) / 64.0
    ha, hb = hs_hist(a), hs_hist(b)
    ha_c, hb_c = ha - ha.mean(), hb - hb.mean()
    denom = float(np.sqrt((ha_c**2).sum() * (hb_c**2).sum()))
    corr = float((ha_c * hb_c).sum() / denom) if denom > 0 else 1.0
    return C.SCENE_W_DHASH * d + C.SCENE_W_HIST * (corr + 1.0) / 2.0


def dialogue_bridges(words: Sequence[Word], cut_ms: int) -> bool:
    """True if a word spans the cut, or the last word before and first word after are within 1,200 ms."""
    if any(w.start_ms < cut_ms < w.end_ms for w in words):
        return True
    before = [w for w in words if w.end_ms <= cut_ms]
    after = [w for w in words if w.start_ms >= cut_ms]
    if not before or not after:
        return False
    prev_end = max(w.end_ms for w in before)
    next_start = min(w.start_ms for w in after)
    return next_start - prev_end <= C.SCENE_DIALOGUE_BRIDGE_MS


@dataclass(frozen=True)
class BoundaryDecision:
    merge: bool | None  # None = needs semantic judgment
    reason: str
    sim: float


def decide_boundary(sim: float, bridge: bool) -> BoundaryDecision:
    if sim >= C.SCENE_MERGE_IDENTICAL:
        return BoundaryDecision(True, "NEAR_IDENTICAL_VISUALS", sim)
    if sim >= C.SCENE_MERGE_DIALOGUE and bridge:
        return BoundaryDecision(True, "VISUALLY_SIMILAR_DIALOGUE_CONTINUES", sim)
    if sim <= C.SCENE_SPLIT_BELOW and not bridge:
        return BoundaryDecision(False, "VISUALLY_DIFFERENT", sim)
    return BoundaryDecision(None, "REQUIRES_SEMANTIC_JUDGMENT", sim)


Judge = Callable[[int, int], tuple[bool, str]]  # (cut_ms, shot index) -> (same_scene, reason)


def build_scenes(
    shots: Sequence[Shot],
    words: Sequence[Word],
    video: Path | None,
    judge: Judge | None,
    duration_ms: int,
) -> Scenes:
    if not shots:
        shots = [Shot(shot_id="SH001", start_ms=0, end_ms=duration_ms)]
    groups: list[list[Shot]] = [[shots[0]]]
    reasons: list[tuple[str, float | None]] = [("START", None)]
    for prev, cur in zip(shots, shots[1:], strict=False):
        cut = cur.start_ms
        sim = 0.0
        unreadable = False
        if video is not None:
            try:
                a = grab_frame(video, max(prev.start_ms, cut - 300))
                b = grab_frame(video, min(cur.end_ms - 1, cut + 300))
                sim = similarity(a, b)
            except MediaError:
                unreadable = True  # fail closed: keep the cut (a split never mixes two settings in one evidence call)
        dec = decide_boundary(sim, dialogue_bridges(words, cut))
        if unreadable:
            dec = BoundaryDecision(False, "FRAME_UNREADABLE_SPLIT", 0.0)
        merge = dec.merge
        reason = dec.reason
        if merge is None:
            if judge is None:
                merge, reason = False, "VL_BOUNDARY_FALLBACK_SPLIT"
            else:
                try:
                    same, why = judge(cut, shots.index(cur))
                    merge, reason = same, f"SEMANTIC:{why[:60]}"
                except Exception:
                    merge, reason = False, "VL_BOUNDARY_FALLBACK_SPLIT"
        if merge:
            groups[-1].append(cur)
        else:
            groups.append([cur])
            reasons.append((reason, round(dec.sim, 4)))
    scenes = []
    for i, (g, (why, sim_v)) in enumerate(zip(groups, reasons, strict=True)):
        scenes.append(
            Scene(
                scene_id=f"SC{i + 1:03d}",
                start_ms=g[0].start_ms,
                end_ms=g[-1].end_ms,
                shots=[s.shot_id for s in g],
                boundary_reason=why,
                boundary_similarity=sim_v,
            )
        )
    return Scenes(scenes=_clamp(scenes))


def _clamp(scenes: list[Scene]) -> list[Scene]:
    """Split scenes longer than SCENE_MAX_S evenly (AudioSight clamps 6–45 s; short scenes are kept,
    because merging across a real cut would mix two settings in one evidence call)."""
    out: list[Scene] = []
    for s in scenes:
        length = s.end_ms - s.start_ms
        n = max(1, int(np.ceil(length / (C.SCENE_MAX_S * 1000))))
        step = length // n
        for k in range(n):
            a = s.start_ms + k * step
            b = s.end_ms if k == n - 1 else a + step
            out.append(
                Scene(
                    scene_id="",
                    start_ms=a,
                    end_ms=b,
                    shots=s.shots,
                    boundary_reason=s.boundary_reason if k == 0 else "MAX_LENGTH_SPLIT",
                    boundary_similarity=s.boundary_similarity if k == 0 else None,
                )
            )
    return [s.model_copy(update={"scene_id": f"SC{i + 1:03d}"}) for i, s in enumerate(out)]
