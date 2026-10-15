"""TTS calibration (PLAN §14.5): 60 fixed sentences of 5–25 words per language → duration = a + b × words."""

from __future__ import annotations

import random
from typing import Any

from accesscast.config import REPO_ROOT
from accesscast.project import write_json
from accesscast.tts.engine import CAL_DIR
from accesscast.workers_client import run_worker

_WORDS = {
    "en": ["the", "person", "opens", "a", "laptop", "on", "the", "desk", "near", "a", "window", "while", "a", "title", "appears", "and", "text", "on", "screen", "shows", "the", "next", "step", "in", "a", "short", "lesson", "about", "using", "the", "keyboard", "with", "two", "hands", "and", "a", "small", "mouse", "beside", "a", "cup", "of", "coffee", "in", "a", "bright", "office", "room"],
    "it": ["la", "persona", "apre", "un", "portatile", "sulla", "scrivania", "vicino", "a", "una", "finestra", "mentre", "appare", "un", "titolo", "e", "il", "testo", "sullo", "schermo", "mostra", "il", "passo", "successivo", "di", "una", "breve", "lezione", "sulla", "tastiera", "con", "due", "mani", "e", "un", "piccolo", "mouse", "accanto", "a", "una", "tazza", "di", "caffè", "in", "un", "ufficio", "luminoso"],
    "hi": ["व्यक्ति", "खिड़की", "के", "पास", "मेज़", "पर", "लैपटॉप", "खोलता", "है", "जबकि", "एक", "शीर्षक", "दिखाई", "देता", "है", "और", "स्क्रीन", "पर", "लिखा", "पाठ", "कीबोर्ड", "के", "उपयोग", "के", "बारे", "में", "एक", "छोटे", "पाठ", "का", "अगला", "कदम", "दिखाता", "है", "और", "पास", "में", "एक", "छोटा", "माउस", "और", "कॉफ़ी", "का", "कप", "रखा", "है"],
}


def sentences(lang: str, n: int = 60, seed: int = 7) -> list[str]:
    """Fixed, reproducible sentences of 5–25 words drawn from a per-language word list."""
    rng = random.Random(f"{seed}:{lang}")
    words = _WORDS[lang]
    out = []
    for i in range(n):
        k = 5 + (i * 20) // max(1, n - 1)
        start = rng.randrange(0, max(1, len(words) - k))
        s = " ".join(words[start : start + k])
        out.append(s[0].upper() + s[1:] + ("." if lang != "hi" else "।"))
    return out


def calibrate(voice: str, lang: str, *, require_rocm: bool = False, speed: float = 1.0) -> dict[str, Any]:
    res = run_worker("tts", "calibrate", {"voice": voice, "lang": lang, "speed": speed,
                                          "sentences": sentences(lang)}, REPO_ROOT / "projects" / "_calibration",
                     None, require_rocm=require_rocm)
    CAL_DIR.mkdir(parents=True, exist_ok=True)
    write_json(CAL_DIR / f"calibration.{voice}.json", res)
    return res
