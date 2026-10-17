"""Assemble the demo video from docs/demo/storyboard.json: title cards, screen recordings, narration, captions.

Narration is Kokoro af_heart (disclosed in the video description as synthetic speech) unless a recorded human
narration file is given per scene. Every on-screen and spoken number must come from public-claims.json: the
storyboard refers to claims by id (`{claim:e1.fit_c}`) and this script fills them from the registry; it refuses
to render while any referenced claim is missing. Captions are burned in (≤ 42 characters per line, 2 lines).
Run with the workers env for TTS:  cd workers && uv run python ../scripts/make_demo_video.py
"""

from __future__ import annotations

import json
import math
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


NARRATION_SPEED = 1.13  # a little brisker than Kokoro's default: the whole video stays near five minutes
LEAD_S, TAIL_S = (
    0.15,
    0.35,
)  # silence kept before and after each narration line (scenes also crossfade, see XFADE_S)
XFADE_S = 0.4  # picture and sound crossfade between scenes, instead of hard cuts


def tts(text: str, path: Path) -> tuple[float, list[tuple[str, float]], float]:
    """Narration audio with its own leading and trailing silence trimmed to LEAD_S / TAIL_S. Returns its length,
    each spoken segment (text, seconds) for caption timing, and where the first segment starts."""
    from kokoro import KPipeline

    pipe = KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M")
    parts = [(r.graphemes, r.audio.numpy()) for r in pipe(text, voice="af_heart", speed=NARRATION_SPEED)]
    audio = np.concatenate([a for _, a in parts])
    loud = np.flatnonzero(np.abs(audio) > 0.02 * float(np.max(np.abs(audio)) or 1.0))
    a0, a1 = (int(loud[0]), int(loud[-1]) + 1) if loud.size else (0, len(audio))
    sr = 24000
    audio = np.concatenate([np.zeros(int(LEAD_S * sr)), audio[a0:a1], np.zeros(int(TAIL_S * sr))])
    sf.write(path, audio, sr)
    return len(audio) / sr, [(g, len(a) / sr) for g, a in parts], LEAD_S - a0 / sr


def caption_chunks(segments: list[tuple[str, float]], t0: float = 0.0) -> list[tuple[str, float, float]]:
    """Captions (≤ 2 lines of 42) timed to the segment that speaks them; a long segment is split by length."""
    out, t = [], t0
    for text, secs in segments:
        pieces = textwrap.wrap(text, 84) or [""]
        total = sum(len(x) for x in pieces) or 1
        for piece in pieces:
            d = secs * len(piece) / total
            if piece:
                out.append((piece, t, t + d))
            t += d
    return out


def esc(t: str) -> str:
    return (
        t.replace("\\", "\\\\").replace(":", "\\:").replace("'", "’").replace(",", "\\,").replace("%", "\\%")
    )


# Music (Kevin MacLeod, incompetech.com, CC BY 4.0; credited on the closing screen and in MODEL_LICENSES.md): a
# quiet piano piece under the problem and the eyes-closed opening, then an uplifting one from "This is AccessCast".
# Each is levelled to the same loudness, dips under the narration (sidechain), and drops out under the scenes that
# play a video's own sound.
MUSIC = (
    ROOT / "data" / "music" / "Touching_Moments_Four_-_Melody.mp3",
    ROOT / "data" / "music" / "Inspired.mp3",
)
MUSIC_GAIN = (
    1.6,
    0.28,
)  # measured short-term loudness about −28 and −13 LUFS: both brought to about −24 before mixing


def xfade_join(
    clips: list[tuple[Path, float]],
    out: Path,
    extra_fc: list[str] | None = None,
    audio_out: str | None = None,
    extra_inputs: list[Path] | None = None,
) -> float:
    """Crossfade clips in order (picture: xfade, sound: acrossfade, XFADE_S each) into `out`; returns its length."""
    inputs: list[str] = []
    for p, _ in clips:
        inputs += ["-i", str(p)]
    for p in extra_inputs or []:  # e.g. the music, after the clips: input index len(clips), len(clips) + 1, …
        inputs += ["-i", str(p)]
    fc = [
        f"[{k}:v]fps=30,settb=AVTB,format=yuv420p[v{k}i];[{k}:a]aformat=sample_rates=48000:channel_layouts=stereo[a{k}i]"
        for k in range(len(clips))
    ]
    prev_v, prev_a, length = "[v0i]", "[a0i]", clips[0][1]
    for k in range(1, len(clips)):
        off = length - XFADE_S
        fc.append(f"{prev_v}[v{k}i]xfade=transition=fade:duration={XFADE_S}:offset={off:.4f}[v{k}]")
        fc.append(f"{prev_a}[a{k}i]acrossfade=d={XFADE_S}:c1=tri:c2=tri[a{k}]")
        prev_v, prev_a = f"[v{k}]", f"[a{k}]"
        length = off + clips[k][1]
    amap = prev_a
    if extra_fc:  # e.g. the tone mixed under the joined sound
        fc += [x.replace("{AUDIO}", prev_a).replace("{LENGTH}", f"{length:.2f}") for x in extra_fc]
        amap = audio_out or prev_a
    script = out.with_suffix(".filter")
    script.write_text(";\n".join(fc))
    subprocess.run(
        [
            "ffmpeg",
            "-loglevel",
            "error",
            "-y",
            *inputs,
            "-filter_complex_script",
            str(script),
            "-map",
            prev_v,
            "-map",
            amap,
            "-c:v",
            "libx264",
            "-crf",
            "16",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "pcm_s16le" if out.suffix == ".mov" else "aac",
            "-ar",
            "48000",
            "-ac",
            "2",
            str(out),
        ],
        check=True,
    )
    return length


def assemble(parts: list[tuple[Path, float, bool, bool]], raw: Path, batch: int = 6) -> None:
    """Join the scenes with crossfades and mix the tone underneath. Joined in batches: one graph over every
    scene at once ran out of memory. Batch joins overlap by XFADE_S exactly like scene joins, so times add up."""
    starts, t = [], 0.0
    for _, d, _, _ in parts:
        starts.append(t)
        t += d - XFADE_S
    chunks = []
    for i in range(0, len(parts), batch):
        group = [(p, d) for p, d, _, _ in parts[i : i + batch]]
        out = OUT / f"chunk{i // batch:02d}.mov"
        chunks.append((out, xfade_join(group, out) if len(group) > 1 else group[0][1]))
        if len(group) == 1:
            subprocess.run(
                [
                    "ffmpeg",
                    "-loglevel",
                    "error",
                    "-y",
                    "-i",
                    str(group[0][0]),
                    "-c:v",
                    "copy",
                    "-c:a",
                    "pcm_s16le",
                    str(out),
                ],
                check=True,
            )
    mutes = [(starts[k], starts[k] + d) for k, (_, d, keep, _) in enumerate(parts) if keep]
    gain = (
        "*".join(f"(1-clip(min((t-({a:.2f}-0.8))/0.8\\,(({b:.2f}+0.8)-t)/0.8)\\,0\\,1))" for a, b in mutes)
        or "1"
    )
    switch = next((starts[k] for k, (_, _, _, sw) in enumerate(parts) if sw), t / 2)
    n = len(chunks)
    a_end = switch + 2.0
    pad = [
        f"[{n}:a]aformat=sample_rates=48000:channel_layouts=stereo,atrim=0:{a_end:.2f},volume={MUSIC_GAIN[0]},"
        f"afade=t=in:d=2,afade=t=out:st={a_end - 3:.2f}:d=3[ma]",
        f"[{n + 1}:a]aformat=sample_rates=48000:channel_layouts=stereo,atrim=0:{t - switch + 1.5:.2f},volume={MUSIC_GAIN[1]},"
        f"afade=t=in:d=3,afade=t=out:st={max(0.0, t - switch - 3):.2f}:d=4.5,adelay={int((switch - 1.5) * 1000)}:all=1[mb]",
        f"[ma][mb]amix=inputs=2:duration=longest:normalize=0,apad=whole_dur={{LENGTH}},atrim=0:{{LENGTH}},"
        f"volume='{gain}':eval=frame[music]",
        "{AUDIO}asplit=2[narr][key]",
        "[music][key]sidechaincompress=threshold=0.03:ratio=5:attack=30:release=600:makeup=1[ducked]",
        "[narr][ducked]amix=inputs=2:duration=first:normalize=0[aout]",
    ]
    xfade_join(chunks, raw, pad, "[aout]", list(MUSIC))


def main() -> int:
    sb = json.loads((ROOT / "docs" / "demo" / "storyboard.json").read_text())
    reg = claims()
    OUT.mkdir(parents=True, exist_ok=True)
    parts = []
    for k, sc in enumerate(sb["scenes"]):
        narr = fill(sc.get("narration", ""), reg)
        wav = OUT / f"n{k:02d}.wav"
        spoken, segments, t0 = tts(narr, wav) if narr else (0.0, [], 0.0)
        dur = (
            spoken + XFADE_S if narr else float(sc.get("seconds", 3))
        )  # the crossfade eats XFADE_S of each scene
        dur = max(dur, float(sc.get("min_seconds", 0)))
        dur = math.ceil(dur * 30) / 30  # whole frames: sound and picture stay in step across every crossfade
        mp4 = OUT / f"s{k:02d}.mp4"
        if sc["kind"] == "card":
            lines = [esc(fill(x, reg)) for x in sc["lines"]]
            draws = [
                f"drawtext=fontfile={FONT_B}:text='{t}':x=(w-text_w)/2:y={360 + 110 * i}:fontsize={sc.get('size', 64)}:fontcolor=white"
                for i, t in enumerate(lines)
            ]
            vin = ["-f", "lavfi", "-i", f"color=c=0x0f1b33:s=1920x1080:r=30:d={dur:.2f}"]
            vf = ",".join(draws) or "null"
        elif (
            sc["kind"] == "image"
        ):  # a chart from docs/charts, centred on the dark background above the captions
            img = ROOT / sc["image"]
            if not img.exists():
                raise SystemExit(f"scene {k}: {sc['image']} missing (run make charts)")
            vin = ["-loop", "1", "-framerate", "30", "-t", f"{dur:.2f}", "-i", str(img)]
            vf = "scale=1600:800:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:60:color=0x0f1b33,fps=30"
        elif sc["kind"] == "motion":
            # a rendered motion scene (render_motion.mjs, transparent PNGs) over real footage, dimmed, or a plain
            # background; full frame, with the narration captions on top (motion layouts keep the bottom clear)
            frames = OUT / "motion" / sc["scene"]
            if not any(frames.glob("*.png")):
                raise SystemExit(
                    f"scene {k}: no frames for motion scene {sc['scene']!r} (run render_motion.mjs)"
                )
            comp = OUT / f"m{k:02d}.mp4"
            if sc.get("bg"):
                bg = [
                    "-ss",
                    f"{float(sc.get('bg_start', 0)):.2f}",
                    "-t",
                    f"{dur:.2f}",
                    "-i",
                    str(ROOT / sc["bg"]),
                ]
                look = sc.get("bg_look", "eq=brightness=-0.36:saturation=0.6,gblur=sigma=9")
                bgf = f"[0:v]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps=30,{look},tpad=stop_mode=clone:stop_duration={dur:.2f}[bg]"
            else:
                bg = ["-f", "lavfi", "-i", f"color=c=0x0f1b33:s=1920x1080:r=30:d={dur:.2f}"]
                bgf = "[0:v]null[bg]"
            subprocess.run(
                [
                    "ffmpeg",
                    "-loglevel",
                    "error",
                    "-y",
                    *bg,
                    "-framerate",
                    "30",
                    "-i",
                    str(frames / "%05d.png"),
                    "-filter_complex",
                    f"{bgf};[1:v]tpad=stop_mode=clone:stop_duration={dur:.2f}[ov];[bg][ov]overlay=0:0,format=yuv420p",
                    "-t",
                    f"{dur:.2f}",
                    "-an",
                    "-c:v",
                    "libx264",
                    "-crf",
                    "16",
                    str(comp),
                ],
                check=True,
            )
            vin = ["-i", str(comp)]
            vf = "null"
        else:
            src = OUT / sc["recording"]
            start = float(sc.get("start", 0))
            if (
                "mark" in sc
            ):  # seconds into the recording, written by record_demo.mjs (<recording>.marks.json)
                marks = json.loads((OUT / f"{Path(sc['recording']).stem}.marks.json").read_text())
                if sc["mark"] not in marks:
                    raise SystemExit(f"scene {k}: no mark {sc['mark']!r} in {sc['recording']} (re-record it)")
                start = marks[sc["mark"]] + float(sc.get("offset", 0))
            # "footage": seconds of the recording this scene may use; past that (or past the recording's end) the
            # last frame is held while the narration finishes, never the next thing the recorder did
            take = min(dur, float(sc.get("footage", dur)))
            vin = ["-ss", f"{max(0.0, start):.2f}", "-t", f"{take:.2f}", "-i", str(src)]
            # full frame; the recordings leave their bottom clear (zoomed out where the page has captions of its own)
            box, pad_y = "1920:1080", "(oh-ih)/2"
            vf = (
                f"scale={box}:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:{pad_y}:color=0x0f1b33,fps=30,"
                f"tpad=stop_mode=clone:stop_duration={dur:.2f}"
            )
        # burned-in captions of the narration, chunked to ≤ 42 chars × 2 lines across the scene
        caps = []
        for i, (ch, a, b) in enumerate(caption_chunks(segments, max(0.0, t0))):
            lines = textwrap.wrap(ch, 42)[:2]
            for j, line in enumerate(lines):  # one drawtext per line: this ffmpeg draws a newline as a glyph
                tf = OUT / f"cap{k:02d}_{i:02d}_{j}.txt"
                tf.write_text(line, encoding="utf-8")
                y = (
                    f"{40 + 64 * j}"  # top, where the bottom of the screen shows what the narration is about
                    if sc.get("captions_at") == "top"
                    else f"h-{230 - 64 * j if len(lines) == 2 else 170}"
                )
                caps.append(
                    f"drawtext=fontfile={FONT}:textfile='{tf}':x=(w-text_w)/2:y={y}:fontsize=46:fontcolor=white:expansion=none:"
                    f"box=1:boxcolor=black@0.75:boxborderw=12:enable='between(t,{a:.2f},{b:.2f})'"
                )
        vf = ",".join([vf, *caps]) if caps else vf
        ain = ["-i", str(wav)] if narr else ["-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo:d={dur:.2f}"]
        amap = "1:a:0"
        af = f"apad=whole_dur={dur:.2f}"
        if sc.get(
            "keep_audio"
        ):  # the recording's own sound (e.g. the eyes-closed before/after), no narration; faded, never cut off
            ain, amap = [], "0:a:0"
            af = f"afade=t=in:d=0.3,afade=t=out:st={max(0.0, dur - 0.7):.2f}:d=0.7,apad=whole_dur={dur:.2f}"
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
                "-af",
                af,
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
        parts.append((mp4, dur, bool(sc.get("keep_audio")), bool(sc.get("music_switch"))))
    raw = OUT / "demo_raw.mp4"
    assemble(parts, raw)
    final = OUT / "accesscast_demo.mp4"
    # two-pass loudnorm (one pass is dynamic and lands short of the target), then a limiter under the ceiling
    meas = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-i",
            str(raw),
            "-af",
            "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stderr
    m = json.loads(meas[meas.rindex("{") : meas.rindex("}") + 1])
    norm = (
        f"loudnorm=I=-16:TP=-1.5:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
        f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true,"
        "alimiter=limit=0.79:level=false"  # 0.79 ≈ −2 dBFS: AAC adds intersample overshoot
    )
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
            norm,
            "-ar",
            "48000",
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
