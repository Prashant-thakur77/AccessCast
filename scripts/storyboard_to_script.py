"""Write docs/demo-script.md from docs/demo/storyboard.json, so the public script always matches the video.
Numbers stay `<pending: claim_id>` placeholders here; `scripts/claims_build.py --fill` fills them from the registry.
Usage: python scripts/storyboard_to_script.py && python scripts/claims_build.py --fill
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MOTION = {
    "p_upload": "The problem, over stock footage of a family watching TV (Pexels): how much video is uploaded",
    "p_blind": "The problem: people who are blind (stock footage of a blind man reading Braille; the picture fades to black)",
    "p_deaf": "The problem: people with disabling hearing loss (stock footage of people signing)",
    "p_read": "The problem: adults who read at the lowest levels (stock footage of an older man reading his phone)",
    "p_cost": "Why most video is left out: the time and price of doing it by hand (stock footage of a video editor at night)",
    "split": "3D animation: one video card splits into five, each labelled with its audience",
    "pipeline": "How it works at a glance: seven steps light up in turn (Gemma steps marked AMD, the check marked code)",
    "amd": "Counters from our own call logs: Gemma requests answered by AMD Token Factory, tokens, videos; tokens and estimated cost per finished minute",
    "gate": "Animation: Gemma's real answer is stopped at the code-check gate for dropping a number, its repair passes to the viewer (both texts from the recorded attack test)",
    "res_neg": "Bars: easy-read captions that kept every negation, Gemma alone against AccessCast as published",
    "laws": "Three law dates: EU, India, US",
    "close": "Closing line over stock footage of a family watching TV, with the links and footage credits",
}
RECORDING = {
    "hook_closed.mp4": 'Black screen, "Close your eyes." The NASA clip\'s own sound only.',
    "hook_ad.mp4": 'Black screen, "The same video, with AccessCast." The extended description version\'s sound (machine draft, labelled).',
    "hook_open.mp4": '"Open your eyes." The extended render itself: Hubble Ultra Deep Field, each description line as text, "picture held" while it is read.',
    "ver_hi.mp4": "The NASA clip's Hindi version: its own Hindi voice and subtitles (machine draft, labelled)",
    "ver_it.mp4": "The NASA clip's Italian version: its own Italian voice and subtitles (machine draft, labelled)",
    "home.webm": "The live site's home page",
    "five_ways.webm": 'The live site\'s "Same clip, five ways" page on the Sintel trailer (labelled draft)',
    "how.webm": 'The live site\'s "How it works" page on the NASA clip, one step at a time',
    "decisions_drawer.webm": "The review app: frames Gemma saw, checks, repair history, keyboard approval",
    "studio.webm": "AccessCast Studio: a video dropped in, every stage listed as it runs",
    "try.webm": 'The live site\'s proof page: a caption typed in "Try your own caption", then the three live versions and the checks',
    "proof.webm": 'The live site\'s proof page: "Run the attack" pressed live, then each try and the tally',
}


def placeholders(text: str) -> str:
    return re.sub(r"\{claim:([\w.\-]+)\}", r"<pending: \1>", text)


def main() -> int:
    sb = json.loads((ROOT / "docs" / "demo" / "storyboard.json").read_text())
    rows = []
    for sc in sb["scenes"]:
        if sc["kind"] == "motion":
            pic = MOTION.get(sc["scene"], sc["scene"])
        elif sc["kind"] == "card":
            pic = "Card: " + " / ".join(placeholders(x) for x in sc["lines"])
        else:
            pic = RECORDING.get(sc["recording"], sc["recording"])
            if sc.get("mark"):
                pic += f" (step `{sc['mark']}`)"
        words = placeholders(sc.get("narration", "")) or "(the clip's own sound, no narration)"
        rows.append(f"| {pic.replace('|', '/')} | {words.replace('|', '/')} |")
    out = [
        "# Demo video script",
        "",
        "Generated from `docs/demo/storyboard.json` by `scripts/storyboard_to_script.py`; the video is built from the same "
        "file by `scripts/make_demo_video.py`. Every number is filled from `evidence/public-claims.json`. No W3C video "
        "appears: the footage is NASA (Life in the Universe, the eclipse animation), the Blender Foundation's Sintel "
        "trailer (CC BY 3.0) and our own pages. Narration is synthetic speech (Kokoro, voice af_heart), and the video "
        "has burned-in captions.",
        "",
        "| Picture | Words (read aloud) |",
        "|---|---|",
        *rows,
        "",
        "## How it is made",
        "- Motion scenes: `docs/demo/motion/index.html`, rendered frame by frame with a transparent background "
        "(`scripts/render_motion.mjs`) and composited over real footage.",
        "- Opening: `scripts/make_hook_scenes.py`, from the NASA clip's draft render and its extended timeline.",
        "- Screen recordings: `scripts/record_demo.mjs` against the live site (https://accesscast.vercel.app), with a "
        "time mark at each step so narration lines up with the picture.",
        "- Editing: scenes crossfade; each narration line keeps only a short pause; a soft tone made with "
        "ffmpeg (no music, so no licence) sits under the narration and fades out where a video's own sound plays.",
        "- Export: H.264, AAC, two-pass loudness to −16 LUFS.",
        "",
    ]
    (ROOT / "docs" / "demo-script.md").write_text("\n".join(out), encoding="utf-8")
    print("docs/demo-script.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
