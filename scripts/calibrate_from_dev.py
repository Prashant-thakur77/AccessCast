"""Refit the English description voice's timing on real dev-set description lines (decision on DEV data only).

The first calibration used generated sentences of plain words and under-predicted real description lines (median
0.26 s short), so lines inside their word budget still overran their pause (AD001). This fits seconds = intercept +
s_per_word × words on every voiced dev line (text as voiced, Kokoro duration as measured) and writes the voice's
calibration file. Never run on test data.
Usage: python scripts/calibrate_from_dev.py [--projects projects/_dev] [--voice af_heart]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from accesscast.config import REPO_ROOT
from accesscast.tts.engine import CAL_DIR


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--projects", default="projects/_dev")
    ap.add_argument("--voice", default="af_heart")
    args = ap.parse_args()
    words, secs, n_videos = [], [], 0
    for f in sorted((REPO_ROOT / args.projects).glob("*/items/ad.en.jsonl")):
        if json.loads((f.parents[1] / "project.json").read_text()).get("worker_mode") != "real":
            continue
        n_videos += 1
        for line in f.read_text(encoding="utf-8").splitlines():
            it = json.loads(line)
            t, txt = it.get("tts"), it.get("final") or it.get("draft")
            if t and t.get("duration_ms") and txt and t.get("voice") == args.voice:
                words.append(len(txt.split()))
                secs.append(t["duration_ms"] / 1000)
    if len(words) < 30:
        raise SystemExit(f"only {len(words)} voiced dev lines; need at least 30")
    x, y = np.array(words, float), np.array(secs, float)
    a, b = np.linalg.lstsq(np.vstack([x, np.ones_like(x)]).T, y, rcond=None)[0]
    r = y - (a * x + b)
    out = {
        "voice": args.voice, "lang": "en", "speed": 1.0, "n": len(x), "videos": n_videos,
        "intercept_s": round(float(b), 4), "s_per_word": round(float(a), 4), "wps_voice": round(1 / float(a), 4),
        "resid_p50_s": round(float(np.percentile(r, 50)), 4), "resid_p95_s": round(float(np.percentile(r, 95)), 4),
        "source": f"dev description lines in {args.projects} (scripts/calibrate_from_dev.py)",
    }
    p = CAL_DIR / f"calibration.{args.voice}.json"
    p.write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out))
    _ = Path
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
