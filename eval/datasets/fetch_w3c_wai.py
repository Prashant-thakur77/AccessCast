"""Fetch the test set: 10 W3C WAI "Web Accessibility Perspectives" videos + W3C's human tracks.

TEST SET — NEVER USED FOR TUNING (CLAUDE.md rule 4). Media are fetched into data/w3c/ (git-ignored) and are
never committed, published or excerpted (rule 8). Only the SHA-256 manifest is committed.
W3C's terms ask that each video's page is linked and whole videos are used; we process whole videos only.

Videos are embedded from YouTube on W3C's pages (no direct MP4 download is offered), so they are fetched with
yt-dlp for private evaluation (decision D-006). Tracks come from github.com/w3c/wai-website at a pinned commit.
Tracks per video (W3C naming): <id>.en.vtt captions (original) · <id>_desc.en.vtt description text (original
timeline) · <id>_ad.en.vtt captions (described version) · <id>_ad_desc.en.vtt description (described version).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import urllib.request

from accesscast.config import REPO_ROOT
from accesscast.events import now_iso
from accesscast.project import sha256_file

WAI_COMMIT = "9112159662b8b9b4d0052d9d0f8703aa580448a4"
RAW = f"https://raw.githubusercontent.com/w3c/wai-website/{WAI_COMMIT}/wai-videos/perspectives/en"
OUT = REPO_ROOT / "data" / "w3c"
MANIFEST = REPO_ROOT / "eval" / "datasets" / "manifests" / "w3c_wai.json"
VIDEOS = {  # video-id: (youtube id, described-version youtube id, page)
    "perspectives_keyboard": ("93UgG72os8M", "1rBwxGMT9ZM", "keyboard"),
    "perspectives_captions": ("iWO5N3n1DXU", "4qIordU8vT8", "captions"),
    "perspectives_contrast": ("Hui87z2Vx8o", "a9kNUv6N8Rk", "contrast"),
    "perspectives_controls": ("CzfKB3PuuIY", "65G_twR47OQ", "controls"),
    "perspectives_customizable": ("rbiI65Jcz5s", "L4WLeVc5l5k", "customizable"),
    "perspectives_layout": ("tfkzj5VC9P8", "w-2nFEUBELo", "layout"),
    "perspectives_notifications": ("E1fEv4Vpexg", "jtteu0ilDXk", "notifications"),
    "perspectives_text-to-speech": ("8Rn5pXCdZWU", "F3A1VffiOH4", "speech"),
    "perspectives_understandable": ("BYRxF2yInfA", "MNlT1Qy3pvQ", "understandable"),
    "perspectives_speech-recognition": ("7RHG_XiQ0ck", "21yWr7evHTs", "voice"),
}
TRACKS = ("", "_desc", "_ad", "_ad_desc")


def main(fetch_video: bool = True) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for vid, (yt, yt_ad, page) in VIDEOS.items():
        d = OUT / vid
        d.mkdir(exist_ok=True)
        for t in TRACKS:
            dst = d / f"{vid}{t}.en.vtt"
            if not dst.exists():
                urllib.request.urlretrieve(f"{RAW}/{vid}{t}.en.vtt", dst)
            rows.append(
                {
                    "video_id": vid,
                    "file": f"data/w3c/{vid}/{dst.name}",
                    "sha256": sha256_file(dst),
                    "kind": "track",
                }
            )
        mp4 = d / f"{vid}.mp4"
        if fetch_video and not mp4.exists():
            ytdlp = shutil.which("yt-dlp")
            if ytdlp is None:
                print("yt-dlp not found: `uv tool install yt-dlp`", file=sys.stderr)
                return 4
            subprocess.run(
                [
                    ytdlp,
                    "-q",
                    "-f",
                    "bv*[height<=720][ext=mp4]+ba[ext=m4a]/b[ext=mp4]",
                    "--merge-output-format",
                    "mp4",
                    "-o",
                    str(mp4),
                    f"https://www.youtube.com/watch?v={yt}",
                ],
                check=True,
            )
        if mp4.exists():
            rows.append(
                {
                    "video_id": vid,
                    "file": f"data/w3c/{vid}/{mp4.name}",
                    "sha256": sha256_file(mp4),
                    "kind": "video",
                    "youtube_id": yt,
                    "youtube_id_described": yt_ad,
                    "page": f"https://www.w3.org/WAI/perspective-videos/{page}/",
                }
            )
    MANIFEST.write_text(
        json.dumps(
            {
                "dataset": "W3C WAI Web Accessibility Perspectives (test set, never used for tuning)",
                "wai_website_commit": WAI_COMMIT,
                "fetched_at": now_iso(),
                "terms": "https://www.w3.org/WAI/about/using-wai-material/",
                "files": rows,
            },
            indent=1,
        )
        + "\n"
    )
    print(
        f"{sum(r['kind'] == 'video' for r in rows)} videos, {sum(r['kind'] == 'track' for r in rows)} tracks → {MANIFEST}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(fetch_video="--tracks-only" not in sys.argv))
