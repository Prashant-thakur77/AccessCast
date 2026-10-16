"""S0 ingest and probe (PLAN §9 S0)."""

from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np
import soundfile as sf

from accesscast import constants as C
from accesscast.errors import MediaError
from accesscast.media.ffmpeg import Probe, probe, run_ffmpeg
from accesscast.project import sha256_file


def source_hash(path: Path) -> str:
    if not path.exists():
        raise MediaError(f"input not found: {path}")
    return sha256_file(path)


def ingest(src: Path, media_dir: Path) -> Probe:
    pr = probe(src)
    if not pr.has_video or not pr.has_audio:
        raise MediaError(
            f"{src.name}: needs both a video and an audio stream (video={pr.has_video}, audio={pr.has_audio})"
        )
    media_dir.mkdir(parents=True, exist_ok=True)
    dst = media_dir / "source.mp4"
    if not dst.exists():
        shutil.copyfile(src, dst)
    run_ffmpeg(
        [
            "-i",
            str(dst),
            "-map",
            "0:a:0",
            "-ac",
            "2",
            "-ar",
            str(C.MASTER_SAMPLE_RATE),
            "-c:a",
            "pcm_f32le",
            str(media_dir / "master48k.wav"),
        ]
    )
    run_ffmpeg(
        [
            "-i",
            str(dst),
            "-map",
            "0:a:0",
            "-ac",
            "1",
            "-ar",
            str(C.ASR_SAMPLE_RATE),
            "-c:a",
            "pcm_s16le",
            str(media_dir / "asr16k.wav"),
        ]
    )
    run_ffmpeg(
        [
            "-i",
            str(dst),
            "-map",
            "0:v:0",
            "-vf",
            f"scale=-2:{C.PROXY_HEIGHT},fps=30",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "28",
            "-g",
            "15",
            "-an",
            str(media_dir / "proxy480.mp4"),
        ]
    )
    return pr


def extract_frame(video: Path, t_ms: int, out: Path, px: int = C.EVIDENCE_FRAME_PX) -> Path:
    """Frame at t_ms; near the end of a stream ffmpeg can decode nothing, so step back up to 1 s (the same rule as
    scene frames), then fail closed."""
    out.parent.mkdir(parents=True, exist_ok=True)
    last = ""
    for back in (0, 200, 500, 1000):
        try:
            run_ffmpeg(
                [
                    "-ss",
                    f"{max(0, t_ms - back) / 1000:.3f}",
                    "-i",
                    str(video),
                    "-frames:v",
                    "1",
                    "-vf",
                    # full range for JPEG: ffmpeg 8's mjpeg refuses limited-range (TV) frames (NASA dev clip, 16 Oct)
                    f"scale='min({px},iw)':-2:out_range=full,format=yuvj420p",
                    "-q:v",
                    "3",
                    str(out),
                ]
            )
        except MediaError as e:  # nothing decodable here: step back
            last = str(e)[:120]
            continue
        if out.exists() and out.stat().st_size > 0:
            return out
    raise MediaError(f"frame at {t_ms} ms not extracted {last}".strip())


def load_mono16k(path: Path) -> tuple[np.ndarray, int]:
    data, sr = sf.read(str(path), dtype="float32", always_2d=False)
    if data.ndim > 1:
        data = data.mean(axis=1)
    return data, int(sr)


def rms_window(audio: np.ndarray, sr: int, start_ms: int, end_ms: int) -> float:
    a, b = int(start_ms * sr / 1000), int(end_ms * sr / 1000)
    seg = audio[a:b]
    return float(np.sqrt(np.mean(seg**2))) if seg.size else 0.0
