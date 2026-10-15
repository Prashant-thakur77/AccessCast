"""FLEURS (google/fleurs, CC-BY-4.0) test split samples for E15: en_us, hi_in, it_it.

Downloads the test parquet (audio included) and writes the first N utterances as 16 kHz WAV + transcript into
data/fleurs/<lang>/ (git-ignored); the SHA-256 manifest is committed. Dev data for the ASR decision (E15).
"""

from __future__ import annotations

import io
import json
import sys
import urllib.request

import numpy as np
import soundfile as sf

from accesscast.config import REPO_ROOT
from accesscast.events import now_iso
from accesscast.project import sha256_file

LANGS = {"en": "en_us", "hi": "hi_in", "it": "it_it"}
OUT = REPO_ROOT / "data" / "fleurs"
MANIFEST = REPO_ROOT / "eval" / "datasets" / "manifests" / "fleurs.json"


def main(n: int = 100) -> int:
    import pyarrow.parquet as pq

    rows = []
    for lang, cfg in LANGS.items():
        d = OUT / lang
        d.mkdir(parents=True, exist_ok=True)
        url = f"https://huggingface.co/api/datasets/google/fleurs/parquet/{cfg}/test/0.parquet"
        req = urllib.request.Request(url, headers={"User-Agent": "AccessCast-dataset-fetch/0.1"})
        with urllib.request.urlopen(req, timeout=600) as r:
            table = pq.read_table(io.BytesIO(r.read()))
        data = table.slice(0, n).to_pylist()
        for k, row in enumerate(data):
            audio = row["audio"]
            wav = d / f"{lang}_{k:04d}.wav"
            if not wav.exists():
                arr, sr = sf.read(io.BytesIO(audio["bytes"]), dtype="float32")
                if sr != 16000:
                    raise SystemExit(f"unexpected sample rate {sr}")
                sf.write(wav, np.asarray(arr), 16000, subtype="PCM_16")
            rows.append(
                {
                    "lang": lang,
                    "file": f"data/fleurs/{lang}/{wav.name}",
                    "sha256": sha256_file(wav),
                    "transcription": row.get("transcription") or row.get("raw_transcription"),
                    "raw_transcription": row.get("raw_transcription"),
                }
            )
    MANIFEST.write_text(
        json.dumps(
            {
                "dataset": "google/fleurs test (CC-BY-4.0), first N per language",
                "fetched_at": now_iso(),
                "n_per_lang": n,
                "files": rows,
            },
            ensure_ascii=False,
            indent=1,
        )
        + "\n"
    )
    print(f"{len(rows)} utterances → {MANIFEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(int(sys.argv[1]) if len(sys.argv) > 1 else 100))
