"""Build the 20-second fixture clip (ours, MIT): generated visuals + two Kokoro voices (Apache-2.0).

Run with the workers environment:  cd workers && uv run python ../scripts/make_fixture.py
Writes tests/fixtures/fixture20/{source.mp4, canned/*.json}. Word timings come from the synthesizer
(Kokoro token timestamps), so they are exact for this clip by construction (decision D-003).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tests" / "fixtures" / "fixture20"
CANNED = OUT / "canned"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
SR = 24_000
DUR = 20.0

LINES = [  # (start_s, voice, text, speaker)
    (1.2, "am_michael", "Welcome. Today I will show you two shortcuts.", "S1"),
    (7.6, "am_michael", "Press control and C to copy the text.", "S1"),
    (13.0, "af_bella", "Then press control and V to paste it.", "S2"),
    (16.2, "af_bella", "Do not unplug the laptop while it saves.", "S2"),
]
SCENES = [(0.0, 4.2), (4.2, 12.4), (12.4, 20.0)]


def synth() -> tuple[np.ndarray, list[dict[str, object]], list[dict[str, int]]]:
    from kokoro import KPipeline

    pipe = KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M")
    track = np.zeros(int(DUR * SR), dtype=np.float32)
    rng = np.random.default_rng(7)
    track += (rng.standard_normal(track.shape) * 0.0008).astype(np.float32)  # faint room tone
    words: list[dict[str, object]] = []
    vad: list[dict[str, int]] = []
    seg = 0
    for start, voice, text, spk in LINES:
        chunks = list(pipe(text, voice=voice, speed=1.0))
        audio = np.concatenate([c.audio.numpy() for c in chunks])
        a = int(start * SR)
        track[a : a + len(audio)] += audio
        offset = 0.0
        first = last = None
        for c in chunks:
            for tk in c.tokens:
                if tk.start_ts is None or not any(ch.isalnum() for ch in tk.text):
                    if words and tk.text.strip() and not any(ch.isalnum() for ch in tk.text):
                        words[-1]["w"] = (
                            str(words[-1]["w"]) + tk.text.strip()
                        )  # keep punctuation, like Whisper
                    continue
                ws, we = start + offset + tk.start_ts, start + offset + tk.end_ts
                words.append(
                    {
                        "i": len(words),
                        "w": tk.text,
                        "start_ms": round(ws * 1000),
                        "end_ms": round(we * 1000),
                        "prob": 1.0,
                        "seg": seg,
                        "speaker": spk,
                    }
                )
                first = ws if first is None else first
                last = we
            offset += len(c.audio) / SR
        vad.append({"start_ms": round((first or start) * 1000), "end_ms": round((last or start) * 1000)})
        seg += 1
    peak = float(np.max(np.abs(track)))
    if peak > 0.89:
        track *= 0.89 / peak
    return track, words, vad


def render_video(wav: Path, mp4: Path) -> None:
    def txt(t: str, x: str, y: str, size: int, color: str, en: str, bold: bool = False) -> str:
        f = FONT_B if bold else FONT
        return f"drawtext=fontfile={f}:text='{t}':x={x}:y={y}:fontsize={size}:fontcolor={color}:enable='{en}'"

    s2 = "between(t,4.2,12.4)"
    s3 = "between(t,12.4,20)"
    s23 = "gte(t,4.2)"
    vf = ",".join(
        [
            "drawbox=x=0:y=0:w=640:h=360:color=0x1b2a4a:t=fill:enable='lt(t,4.2)'",
            txt("Keyboard Shortcuts", "(w-text_w)/2", "130", 40, "white", "lt(t,4.2)", True),
            txt("Lesson 1", "(w-text_w)/2", "190", 24, "0xcfd8ff", "lt(t,4.2)"),
            f"drawbox=x=0:y=0:w=640:h=360:color=0xd9d4cc:t=fill:enable='{s2}'",
            f"drawbox=x=0:y=0:w=640:h=360:color=0xcfe3cf:t=fill:enable='{s3}'",
            f"drawbox=x=40:y=250:w=560:h=24:color=0x7a5230:t=fill:enable='{s23}'",  # desk
            f"drawbox=x=330:y=150:w=200:h=100:color=0x222222:t=fill:enable='{s23}'",  # laptop screen
            f"drawbox=x=310:y=246:w=240:h=8:color=0x555555:t=fill:enable='{s23}'",  # laptop base
            f"drawbox=x=150:y=120:w=50:h=50:color=0xe0b48a:t=fill:enable='{s23}'",  # head
            f"drawbox=x=146:y=110:w=58:h=18:color=0x9a9a9a:t=fill:enable='{s23}'",  # short grey hair
            f"drawbox=x=125:y=170:w=100:h=80:color=0x2f5fb3:t=fill:enable='{s23}'",  # blue cardigan
            f"drawbox=x=225:y=205:w=95:h=14:color=0x2f5fb3:t=fill:enable='{s23}'",  # arm to laptop
            txt("Ctrl + C", "385", "185", 28, "white", "between(t,5.0,12.4)", True),
            txt("Ctrl + V", "385", "185", 28, "white", s3, True),
            "drawbox=x=40:y=40:w=230:h=60:color=0xf6e27a:t=fill:enable='between(t,14.5,20)'",
            txt("Do not unplug", "52", "52", 20, "black", "between(t,14.5,20)"),
            txt("while saving", "52", "74", 20, "black", "between(t,14.5,20)"),
        ]
    )
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c=black:s=640x360:r=30:d={DUR}",
        "-i",
        str(wav),
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-preset",
        "veryslow",
        "-crf",
        "30",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "96k",
        "-ar",
        "48000",
        "-shortest",
        "-movflags",
        "+faststart",
        str(mp4),
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def main() -> int:
    CANNED.mkdir(parents=True, exist_ok=True)
    track, words, vad = synth()
    wav = OUT / "speech24k.wav"
    sf.write(wav, track, SR)
    render_video(wav, OUT / "source.mp4")
    wav.unlink()
    (CANNED / "words.json").write_text(
        json.dumps(
            {"lang": "en", "model": "kokoro-82m-synth-timestamps", "aligned": True, "words": words}, indent=1
        )
    )
    (CANNED / "vad.json").write_text(
        json.dumps({"model": "kokoro-82m-synth-timestamps", "segments": vad}, indent=1)
    )
    shots = [
        {"shot_id": f"SH{i + 1:03d}", "start_ms": round(a * 1000), "end_ms": round(b * 1000)}
        for i, (a, b) in enumerate(SCENES)
    ]
    (CANNED / "shots.json").write_text(json.dumps({"detector": "fixture", "shots": shots}, indent=1))
    print(f"wrote {OUT / 'source.mp4'} with {len(words)} words")
    return 0


if __name__ == "__main__":
    sys.exit(main())
