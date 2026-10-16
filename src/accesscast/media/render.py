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
    video: Path, audio: Path, rows: Sequence[dict[str, Any]], out: Path, *, watermark: bool, fps: float = 30.0
) -> None:
    """Per source segment: trim by frame number + setpts; per insertion: hold the last frame (tpad clone) for a whole
    number of frames. A hold at t=0 clones the first frame at the start of the first segment. Cuts and holds are
    counted in frames so the picture stays on the audio timeline (E9 found 3 frames of drift with time-based trims
    and a 0.04 s head clip; docs/incidents.md 2026-10-17)."""
    parts: list[str] = []
    labels: list[str] = []
    k = 0
    i = 0
    rows = list(rows)
    lead = 0  # frames to hold before the first source segment (insertions at t=0)

    def frames(ms: float) -> int:
        return round(ms * fps / 1000)

    while i < len(rows):
        r = rows[i]
        if r["type"] == "source":
            a, b = frames(r["source_start_ms"]), frames(r["source_end_ms"])
            pad = 0
            j = i + 1
            while j < len(rows) and rows[j]["type"] == "insertion":
                pad += frames(rows[j]["output_end_ms"] - rows[j]["output_start_ms"])
                j += 1
            chain = f"[0:v]trim=start_frame={a}:end_frame={b},setpts=PTS-STARTPTS"
            # one tpad with both options: a second tpad in the same chain drops its padding (ffmpeg 8, tested)
            opts = ([f"start_mode=clone:start={lead}"] if lead else []) + (
                [f"stop_mode=clone:stop={pad}"] if pad else []
            )
            if opts:
                chain += ",tpad=" + ":".join(opts)
            lead = 0
            parts.append(f"{chain}[v{k}]")
            labels.append(f"[v{k}]")
            k += 1
            i = j
        else:  # insertion before any source: held at the start of the first segment
            lead += frames(r["output_end_ms"] - r["output_start_ms"])
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
