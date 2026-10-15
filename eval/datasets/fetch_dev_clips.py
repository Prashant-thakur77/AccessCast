"""Fetch the development set (tuning allowed). Media go to data/dev/ (git-ignored); the manifest is committed.

Licences: NASA media are generally not copyrighted in the US (credit NASA; no logos; no implied endorsement);
Prelinger Archives films are public domain (archive.org licenseurl = publicdomain); Blender open movies are
CC BY 3.0 (credit lines below). Dev clips may be trimmed (only W3C test videos must be used whole).
"""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.request

from accesscast.config import REPO_ROOT
from accesscast.events import now_iso
from accesscast.project import sha256_file

OUT = REPO_ROOT / "data" / "dev"
MANIFEST = REPO_ROOT / "eval" / "datasets" / "manifests" / "dev_clips.json"
NASA = "https://images-assets.nasa.gov/video/{id}/{id}~medium.mp4"
CLIPS = [  # (clip id, url, max seconds or None, source, licence, credit)
    *[(f"nasa_{i}", NASA.format(id=i), 180, "NASA", "NASA media usage guidelines (generally not copyrighted in the US)",
       "Courtesy NASA") for i in (
        "GSFC_20170614_Eclipse_m12534_Plane", "GSFC_20140408_LRO_m11514_Eclipse", "GSFC_20131121_ISON_m11384_Comet",
        "GSFC_20171115_m12776_LifeInTheUniverse", "GSFC_20180417_Worldview_m12928_Tutorial",
        "GSFC_20130918_AACS_m11356_Food")],
    *[(f"prelinger_{i}", f"https://archive.org/download/{i}/{i}_512kb.mp4", 180, "Prelinger Archives",
       "Public domain", "Prelinger Archives, archive.org") for i in ("Televisi1970", "Operator1949_2", "WhenYouA1948")],
    ("blender_sintel_trailer", "https://download.blender.org/durian/trailer/sintel_trailer-480p.mp4", None, "Blender",
     "CC BY 3.0", "© copyright Blender Foundation | www.sintel.org"),
    ("blender_bbb_excerpt", "https://download.blender.org/peach/bigbuckbunny_movies/BigBuckBunny_320x180.mp4.zip", 120,
     "Blender", "CC BY 3.0", "(c) copyright 2008, Blender Foundation / www.bigbuckbunny.org"),
]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for cid, url, max_s, source, lic, credit in CLIPS:
        dst = OUT / f"{cid}.mp4"
        if not dst.exists():
            raw = OUT / f"{cid}.download.mp4"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "AccessCast-dataset-fetch/0.1 (+github.com/Prashant-thakur77/AccessCast)"})
                with urllib.request.urlopen(req, timeout=300) as r, raw.open("wb") as fh:
                    fh.write(r.read())
                if url.endswith(".zip"):
                    import zipfile

                    with zipfile.ZipFile(raw) as z:
                        name = next(n for n in z.namelist() if n.lower().endswith((".mp4", ".m4v", ".mov")))
                        data = z.read(name)
                    raw.write_bytes(data)
            except Exception as e:  # keep going; the manifest records what failed
                print(f"{cid}: download failed ({e})", file=sys.stderr)
                rows.append({"clip": cid, "url": url, "error": str(e)[:200]})
                continue
            args = ["ffmpeg", "-loglevel", "error", "-y", "-i", str(raw)]
            if max_s:
                args += ["-t", str(max_s)]
            args += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-c:a", "aac", "-b:a", "128k",
                     "-movflags", "+faststart", str(dst)]
            subprocess.run(args, check=True)
            raw.unlink()
        rows.append({"clip": cid, "url": url, "trimmed_to_s": max_s, "source": source, "licence": lic,
                     "credit": credit, "file": f"data/dev/{dst.name}", "sha256": sha256_file(dst)})
    MANIFEST.write_text(json.dumps({"dataset": "AccessCast development set (tuning allowed)", "fetched_at": now_iso(),
                                    "clips": rows}, indent=1) + "\n")
    print(f"{sum('sha256' in r for r in rows)} dev clips → {MANIFEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
