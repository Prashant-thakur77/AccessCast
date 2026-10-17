"""Assemble the demo video from docs/demo/storyboard.json: title cards, screen recordings, narration, captions.

Narration is Kokoro af_heart (disclosed in the video description as synthetic speech) unless a recorded human
narration file is given per scene. Every on-screen and spoken number must come from public-claims.json: the
storyboard refers to claims by id (`{claim:e1.fit_c}`) and this script fills them from the registry; it refuses
to render while any referenced claim is missing. Captions are burned in (≤ 42 characters per line, 2 lines).
Run with the workers env for TTS:  cd workers && uv run python ../scripts/make_demo_video.py
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import textwrap
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "demo"
FONT_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def claims() -> dict[str, str]:
    reg = json.loads((ROOT / "evidence" / "public-claims.json").read_text())
    return {c["claim_id"]: (c.get("display") or [str(c["value"])])[0] for c in reg["claims"]}


def fill(text: str, reg: dict[str, str]) -> str:
    missing = [m for m in re.findall(r"\{claim:([\w.\-]+)\}", text) if m not in reg]
    if missing:
        raise SystemExit(f"refusing to render: claims not registered yet: {missing}")
    return re.sub(r"\{claim:([\w.\-]+)\}", lambda m: reg[m.group(1)], text)


def tts(text: str, path: Path) -> float:
    from kokoro import KPipeline

    pipe = KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M")
    audio = np.concatenate([r.audio.numpy() for r in pipe(text, voice="af_heart", speed=1.0)])
    sf.write(path, audio, 24000)
    return len(audio) / 24000


def esc(t: str) -> str:
    return (
        t.replace("\\", "\\\\").replace(":", "\\:").replace("'", "’").replace(",", "\\,").replace("%", "\\%")
    )


def main() -> int:
    sb = json.loads((ROOT / "docs" / "demo" / "storyboard.json").read_text())
    reg = claims()
    OUT.mkdir(parents=True, exist_ok=True)
    parts = []
    for k, sc in enumerate(sb["scenes"]):
        narr = fill(sc.get("narration", ""), reg)
        wav = OUT / f"n{k:02d}.wav"
        dur = tts(narr, wav) + 0.6 if narr else float(sc.get("seconds", 3))
        dur = max(dur, float(sc.get("min_seconds", 0)))
        mp4 = OUT / f"s{k:02d}.mp4"
        if sc["kind"] == "card":
            lines = [esc(fill(x, reg)) for x in sc["lines"]]
            draws = [
                f"drawtext=fontfile={FONT_B}:text='{t}':x=(w-text_w)/2:y={360 + 110 * i}:fontsize={sc.get('size', 64)}:fontcolor=white"
                for i, t in enumerate(lines)
            ]
            vin = ["-f", "lavfi", "-i", f"color=c=0x0f1b33:s=1920x1080:r=30:d={dur:.2f}"]
            vf = ",".join(draws) or "null"
        else:
            src = OUT / sc["recording"]
            vin = ["-ss", str(sc.get("start", 0)), "-t", f"{dur:.2f}", "-i", str(src)]
            vf = "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30"
        # burned-in captions of the narration, chunked to ≤ 42 chars × 2 lines across the scene
        chunks = textwrap.wrap(narr, 84) if narr else []
        caps = []
        for i, ch in enumerate(chunks):
            a, b = dur * i / len(chunks), dur * (i + 1) / len(chunks)
            lines = textwrap.wrap(ch, 42)[:2]
            for j, line in enumerate(lines):  # one drawtext per line: this ffmpeg draws a newline as a glyph
                tf = OUT / f"cap{k:02d}_{i:02d}_{j}.txt"
                tf.write_text(line, encoding="utf-8")
                y = f"h-{230 - 64 * j if len(lines) == 2 else 170}"
                caps.append(
                    f"drawtext=fontfile={FONT}:textfile='{tf}':x=(w-text_w)/2:y={y}:fontsize=46:fontcolor=white:"
                    f"box=1:boxcolor=black@0.75:boxborderw=12:enable='between(t,{a:.2f},{b:.2f})'"
                )
        vf = ",".join([vf, *caps]) if caps else vf
        ain = ["-i", str(wav)] if narr else ["-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo:d={dur:.2f}"]
        amap = "1:a:0"
        if sc.get("keep_audio"):  # the recording's own sound (e.g. the eyes-closed before/after), no narration
            ain, amap = [], "0:a:0"
        subprocess.run(
            [
                "ffmpeg",
                "-loglevel",
                "error",
                "-y",
                *vin,
                *ain,
                "-map",
                "0:v:0",
                "-map",
                amap,
                "-vf",
                vf,
                "-t",
                f"{dur:.2f}",
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
                str(mp4),
            ],
            check=True,
        )
        parts.append(mp4)
    lst = OUT / "parts.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts))
    raw = OUT / "demo_raw.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(lst),
            "-c",
            "copy",
            str(raw),
        ],
        check=True,
    )
    final = OUT / "accesscast_demo.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(raw),
            "-c:v",
            "copy",
            "-af",
            "loudnorm=I=-16:TP=-1.5:LRA=11",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            str(final),
        ],
        check=True,
    )
    print(f"demo → {final}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
