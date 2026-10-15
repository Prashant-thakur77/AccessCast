"""ffmpeg/ffprobe helpers. Every call checks the exit code and keeps the stderr tail for the error."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from accesscast.errors import MediaError, MissingDependencyError


def _bin(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise MissingDependencyError(f"{name} not found on PATH")
    return path


def run_ffmpeg(args: list[str], *, timeout: float = 1800) -> str:
    cmd = [_bin("ffmpeg"), "-hide_banner", "-nostdin", "-y", *args]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as e:
        raise MediaError(f"ffmpeg timed out after {timeout}s") from e
    if p.returncode != 0:
        tail = "\n".join(p.stderr.strip().splitlines()[-12:])
        raise MediaError(f"ffmpeg failed ({p.returncode}): {tail}")
    return p.stderr


def ffprobe_json(path: Path) -> dict[str, Any]:
    cmd = [
        _bin("ffprobe"),
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    p = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if p.returncode != 0:
        raise MediaError(f"ffprobe could not read {path.name}: {p.stderr.strip()[:300]}")
    data: dict[str, Any] = json.loads(p.stdout)
    return data


@dataclass(frozen=True)
class Probe:
    duration_ms: int
    fps: float
    width: int
    height: int
    has_video: bool
    has_audio: bool
    audio_rate: int | None


def probe(path: Path) -> Probe:
    d = ffprobe_json(path)
    v = next((s for s in d.get("streams", []) if s.get("codec_type") == "video"), None)
    a = next((s for s in d.get("streams", []) if s.get("codec_type") == "audio"), None)
    dur = float(d.get("format", {}).get("duration") or (v or a or {}).get("duration") or 0)
    fps = 0.0
    if v is not None:
        num, _, den = str(v.get("avg_frame_rate", "0/1")).partition("/")
        try:
            fps = float(num) / float(den or 1) if float(den or 1) else 0.0
        except ValueError:
            fps = 0.0
    return Probe(
        duration_ms=round(dur * 1000),
        fps=round(fps, 3),
        width=int(v.get("width", 0)) if v else 0,
        height=int(v.get("height", 0)) if v else 0,
        has_video=v is not None,
        has_audio=a is not None,
        audio_rate=int(a["sample_rate"]) if a and a.get("sample_rate") else None,
    )


def ffmpeg_version() -> str:
    p = subprocess.run([_bin("ffmpeg"), "-version"], capture_output=True, text=True, check=False)
    m = re.search(r"ffmpeg version (\S+)", p.stdout)
    return m.group(1) if m else "unknown"


@dataclass(frozen=True)
class Loudness:
    integrated_lufs: float
    true_peak_dbtp: float
    lra: float


def measure_loudness(path: Path) -> Loudness:
    """EBU R 128 measurement with true peak (ffmpeg ebur128=peak=true)."""
    err = run_ffmpeg(["-i", str(path), "-map", "0:a:0", "-af", "ebur128=peak=true", "-f", "null", "-"])
    summary = err[err.rfind("Summary:") :]
    i = re.search(r"I:\s+(-?[\d.]+|-inf) LUFS", summary)
    tp = re.search(r"Peak:\s+(-?[\d.]+|-inf) dBFS", summary)
    lra = re.search(r"LRA:\s+(-?[\d.]+) LU", summary)
    if not i or not tp:
        raise MediaError("could not parse ebur128 summary")

    def f(x: str) -> float:
        return float("-inf") if x == "-inf" else float(x)

    return Loudness(f(i.group(1)), f(tp.group(1)), float(lra.group(1)) if lra else 0.0)
