"""S14 video assembly for each audience version."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from accesscast.media.ffmpeg import run_ffmpeg

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
WATERMARK = "UNREVIEWED DRAFT"


def _wm_filter() -> str:
    return (
        f"drawtext=fontfile={FONT}:text='{WATERMARK}':x=(w-text_w)/2:y=12:fontsize=h/18:"
        "fontcolor=white:box=1:boxcolor=0xb00020@0.85:boxborderw=8"
    )


def mux_standard(video: Path, audio: Path, out: Path, *, watermark: bool) -> None:
    args = ["-i", str(video), "-i", str(audio), "-map", "0:v:0", "-map", "1:a:0"]
    if watermark:
        args += [
            "-vf",
            _wm_filter(),
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
        ]
    else:
        args += ["-c:v", "copy"]
    args += ["-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-shortest", "-movflags", "+faststart", str(out)]
    run_ffmpeg(args)


def render_extended(
    video: Path, audio: Path, rows: Sequence[dict[str, Any]], out: Path, *, watermark: bool
) -> None:
    """Per source segment: trim + setpts; per insertion: tpad clone of the last frame of the previous segment.

    Insertions are attached to the end of the preceding source segment (or a 1-frame head if at t=0).
    """
    parts: list[str] = []
    labels: list[str] = []
    k = 0
    i = 0
    rows = list(rows)
    while i < len(rows):
        r = rows[i]
        if r["type"] == "source":
            a, b = r["source_start_ms"] / 1000, r["source_end_ms"] / 1000
            pad_ms = 0
            j = i + 1
            while j < len(rows) and rows[j]["type"] == "insertion":
                pad_ms += rows[j]["output_end_ms"] - rows[j]["output_start_ms"]
                j += 1
            chain = f"[0:v]trim=start={a:.3f}:end={b:.3f},setpts=PTS-STARTPTS"
            if pad_ms:
                chain += f",tpad=stop_mode=clone:stop_duration={pad_ms / 1000:.3f}"
            parts.append(f"{chain}[v{k}]")
            labels.append(f"[v{k}]")
            k += 1
            i = j
        else:  # insertion at t=0: freeze the first frame
            pad_ms = r["output_end_ms"] - r["output_start_ms"]
            parts.append(
                f"[0:v]trim=start=0:end=0.04,setpts=PTS-STARTPTS,tpad=stop_mode=clone:"
                f"stop_duration={pad_ms / 1000:.3f}[v{k}]"
            )
            labels.append(f"[v{k}]")
            k += 1
            i += 1
    concat = f"{''.join(labels)}concat=n={len(labels)}:v=1:a=0[vc]"
    tail = f";[vc]{_wm_filter()}[vout]" if watermark else ";[vc]null[vout]"
    graph = ";".join([*parts, concat]) + tail
    run_ffmpeg(
        [
            "-i",
            str(video),
            "-i",
            str(audio),
            "-filter_complex",
            graph,
            "-map",
            "[vout]",
            "-map",
            "1:a:0",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            "-r",
            "30",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-ar",
            "48000",
            "-movflags",
            "+faststart",
            str(out),
        ]
    )
