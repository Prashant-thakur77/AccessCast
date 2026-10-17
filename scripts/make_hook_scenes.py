"""The demo's opening, built only from a real project's files (no recording, no hand-made output):

  hook_closed.mp4  black screen + the source video's own sound ("close your eyes")
  hook_ad.mp4      black screen + the extended description version's sound (machine draft, labelled)
  hook_open.mp4    the extended version itself, picture and sound, with each description line shown as text and a
                   "picture held" badge exactly while the render holds the frame (from source_to_output)

Usage: python scripts/make_hook_scenes.py [project_dir]   (default projects/_site/dac08bcd9d7a). Writes data/demo/.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "demo"
FB = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
F = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
CLOSED_S = 18.6  # source: up to "...in this image alone." (the first spoken sentences)
AD_S = 16.0  # extended output: both opening description lines, then the same first sentence
OPEN_S = 8.5  # extended output: the two held descriptions with the picture


def ff(*args: str) -> None:
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *args], check=True)


def card_text(lines: list[tuple[str, str, int, int, str]]) -> str:
    out = []
    for i, (font, text, y, size, color) in enumerate(lines):
        tf = OUT / f"hook_txt_{i}.txt"
        tf.write_text(text, encoding="utf-8")
        out.append(
            f"drawtext=fontfile={font}:textfile='{tf}':x=(w-text_w)/2:y={y}:fontsize={size}:fontcolor={color}"
        )
    return ",".join(out)


def vtt_cues(p: Path) -> list[tuple[float, float, str]]:
    cues = []
    blocks = p.read_text(encoding="utf-8").split("\n\n")
    for b in blocks:
        m = re.search(r"(\d\d):(\d\d):(\d\d)\.(\d\d\d) --> (\d\d):(\d\d):(\d\d)\.(\d\d\d)\n(.+)", b, re.S)
        if not m:
            continue
        g = [int(x) for x in m.groups()[:8]]
        a = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000
        z = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000
        cues.append((a, z, m.group(9).strip().replace("[UNREVIEWED DRAFT] ", "")))
    return cues


def main() -> int:
    proj = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "projects" / "_site" / "dac08bcd9d7a"
    src = proj / "media" / "source.mp4"
    ext = proj / "render" / "blind_ext.en.mp4"
    tl = proj / "render" / "source_to_output.blind_ext.en.jsonl"
    rows = [json.loads(x) for x in tl.read_text().splitlines() if x.strip()]
    OUT.mkdir(parents=True, exist_ok=True)

    vf = card_text(
        [
            (FB, "Close your eyes.", 420, 84, "white"),
            (F, "A NASA video, as a blind viewer hears it.", 560, 46, "0xc9d3ea"),
        ]
    )
    ff(
        "-f",
        "lavfi",
        "-i",
        f"color=c=black:s=1920x1080:r=30:d={CLOSED_S}",
        "-t",
        str(CLOSED_S),
        "-i",
        str(src),
        "-map",
        "0:v",
        "-map",
        "1:a",
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-ar",
        "48000",
        "-ac",
        "2",
        "-shortest",
        str(OUT / "hook_closed.mp4"),
    )

    vf = card_text(
        [
            (FB, "The same video, with AccessCast.", 420, 72, "white"),
            (
                F,
                "Description written by Gemma 4 31B on AMD and checked in code (machine draft, before review).",
                560,
                34,
                "0xffc857",
            ),
        ]
    )
    ff(
        "-f",
        "lavfi",
        "-i",
        f"color=c=black:s=1920x1080:r=30:d={AD_S}",
        "-t",
        str(AD_S),
        "-i",
        str(ext),
        "-map",
        "0:v",
        "-map",
        "1:a",
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-ar",
        "48000",
        "-ac",
        "2",
        "-shortest",
        str(OUT / "hook_ad.mp4"),
    )

    # Open your eyes: the render itself, its description lines as text, and the holds as a badge.
    draws = ["scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2"]
    for i, (a, z, text) in enumerate(
        c for c in vtt_cues(proj / "render" / "tracks" / "desc.en.blind_ext.en.vtt") if c[0] < OPEN_S
    ):
        tf = OUT / f"hook_desc_{i}.txt"
        tf.write_text(text, encoding="utf-8")
        draws.append(
            f"drawtext=fontfile={FB}:textfile='{tf}':x=(w-text_w)/2:y=h-150:fontsize=48:fontcolor=0xffd23f:"
            f"box=1:boxcolor=black@0.8:boxborderw=18:enable='between(t,{a:.3f},{z:.3f})'"
        )
    for r in rows:
        if r.get("type") == "insertion" and r["output_start_ms"] / 1000 < OPEN_S:
            a, z = r["output_start_ms"] / 1000, r["output_end_ms"] / 1000
            draws.append(
                f"drawtext=fontfile={FB}:text='PICTURE HELD FOR THE DESCRIPTION':x=60:y=150:fontsize=40:fontcolor=0x1b1e4b:"
                f"box=1:boxcolor=0xffd23f:boxborderw=16:enable='between(t,{a:.3f},{z:.3f})'"
            )
    tf = OUT / "hook_open_title.txt"
    tf.write_text("Open your eyes.", encoding="utf-8")
    draws.append(
        f"drawtext=fontfile={FB}:textfile='{tf}':x=w-text_w-60:y=60:fontsize=56:fontcolor=white:"
        "box=1:boxcolor=black@0.6:boxborderw=14"
    )
    ff(
        "-t",
        str(OPEN_S),
        "-i",
        str(ext),
        "-vf",
        ",".join(draws) + ",fps=30",
        "-c:v",
        "libx264",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-ar",
        "48000",
        "-ac",
        "2",
        str(OUT / "hook_open.mp4"),
    )
    for n in ("hook_closed", "hook_ad", "hook_open"):
        print(OUT / f"{n}.mp4")
    return 0


if __name__ == "__main__":
    sys.exit(main())
