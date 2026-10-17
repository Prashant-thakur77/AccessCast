"""Easy-read (ER001–ER011), caption/subtitle (CC001–CC010) and voice-over (VO001–VO004) rules.

PLAN §10.3–§10.5. CC011 (burned-in contrast) runs in rules_render because it needs the frame.
"""

from __future__ import annotations

import re

from accesscast import constants as C
from accesscast.schemas import Item, ItemKind
from accesscast.verify import lexicons as L
from accesscast.verify import nlp
from accesscast.verify.base import Finding, Rule, Severity, VerifyContext, fmt_s


def _dur_s(item: Item) -> float:
    return max(0.001, (item.slot.end_ms - item.slot.start_ms) / 1000)


def _lines(text: str) -> list[str]:
    return text.split("\n")


# ---------------------------------------------------------------- all text kinds
def gen001_empty_or_failed(item: Item, ctx: VerifyContext) -> list[Finding]:
    """Fail closed: empty text, a failed generation or a misaligned translation is never publishable."""
    if not item.text.strip():
        return [
            Finding(
                "GEN001",
                "error",
                "empty text",
                "a line to show or speak",
                "There is no text for this line. A person must write it.",
                "write",
                repairable=False,
            )
        ]
    bad = [f for f in item.flags if f.startswith(("generation_error:", "misaligned:"))]
    if bad:
        return [
            Finding(
                "GEN001",
                "error",
                bad[0][:80],
                "generated and aligned",
                "The model output for this line failed. A person must check it.",
                "write",
                repairable=False,
            )
        ]
    return []


# ---------------------------------------------------------------- easy-read
def er001_too_fast(item: Item, ctx: VerifyContext) -> list[Finding]:
    if item.needs_pause:
        return []
    words = nlp.word_count(item.text)
    wpm = words / _dur_s(item) * 60
    if wpm > C.EASY_WPM_MAX:
        return [
            Finding(
                "ER001",
                "error",
                f"{wpm:.0f} words per minute",
                f"≤ {C.EASY_WPM_MAX}",
                "Too fast to read. Use fewer words.",
                "easy",
            )
        ]
    return []


def er002_sentence_too_long(item: Item, ctx: VerifyContext) -> list[Finding]:
    for s in nlp.sentences(item.text):
        n = nlp.word_count(s)
        if n > C.EASY_SENTENCE_WORDS_MAX:
            return [
                Finding(
                    "ER002",
                    "error",
                    f"{n} words in a sentence",
                    f"≤ {C.EASY_SENTENCE_WORDS_MAX}",
                    "A sentence is too long. Split it.",
                    "easy",
                )
            ]
    return []


_COORD = {"en": ("and", "but", "or", "so"), "it": ("e", "ma", "o", "quindi"), "hi": ("और", "लेकिन", "या")}


def er003_more_than_one_idea(item: Item, ctx: VerifyContext) -> list[Finding]:
    for s in nlp.sentences(item.text):
        toks = nlp.lower_tokens(s)
        if ctx.lang == "en":
            doc_verbs = [
                t for t in nlp._doc_en(s) if t.pos_ in ("VERB", "AUX") and "Fin" in t.morph.get("VerbForm")
            ]
            if len(doc_verbs) >= 2 and any(c in toks for c in _COORD["en"]):
                return [
                    Finding(
                        "ER003",
                        "warning",
                        f"{len(doc_verbs)} main verbs joined",
                        "1 idea per sentence",
                        "This sentence may hold two ideas.",
                        "easy",
                    )
                ]
        elif sum(1 for c in _COORD.get(ctx.lang, ()) if c in toks) >= 1 and len(toks) > 8:
            return [
                Finding(
                    "ER003",
                    "warning",
                    "clauses joined",
                    "1 idea per sentence",
                    "This sentence may hold two ideas.",
                    "easy",
                )
            ]
    return []


def er004_number_changed(item: Item, ctx: VerifyContext) -> list[Finding]:
    src = item.source_text or ""
    a, b = (
        nlp.numbers(src, ctx.lang if item.kind == ItemKind.EASY else "en"),
        nlp.numbers(item.text, ctx.lang),
    )
    if a != b:
        return [
            Finding(
                "ER004",
                "error",
                f"numbers {b}",
                f"same as source {a}",
                "A number was changed or lost.",
                "easy",
            )
        ]
    return []


def er005_negation_flipped(item: Item, ctx: VerifyContext) -> list[Finding]:
    src = item.source_text or ""
    a = nlp.negation_count(src, "en" if item.kind != ItemKind.EASY else ctx.lang)
    b = nlp.negation_count(item.text, ctx.lang)
    if a != b:
        return [
            Finding(
                "ER005",
                "error",
                f"{b} negations",
                f"{a} as in the source",
                "A 'not' or 'never' was lost or added. The meaning may have flipped.",
                "easy",
            )
        ]
    return []


def er006_name_or_term_lost(item: Item, ctx: VerifyContext) -> list[Finding]:
    src = item.source_text or ""
    low = item.text.lower()
    keep = [n for n in nlp.proper_nouns(src, "en" if ctx.lang == "en" else ctx.lang) if n.lower() not in low]
    keep += [g for g in ctx.glossary if g.lower() in src.lower() and g.lower() not in low]
    if keep:
        return [
            Finding(
                "ER006",
                "error",
                f"missing '{keep[0]}'",
                "every name and key term kept",
                "A name or key term was dropped.",
                "easy",
            )
        ]
    return []


def er007_abbreviation(item: Item, ctx: VerifyContext) -> list[Finding]:
    low = item.text.lower()
    hits = [a for a in L.ABBREVIATIONS if a in low]
    acr = [t for t in nlp.tokens(item.text) if len(t) >= 2 and t.isupper() and t.isalpha() and t != "I"]
    if hits or acr:
        return [
            Finding(
                "ER007",
                "error",
                f"'{(hits or acr)[0]}'",
                "no abbreviations",
                "Write the words out in full.",
                "easy",
            )
        ]
    return []


def er008_hard_word(item: Item, ctx: VerifyContext) -> list[Finding]:
    if ctx.lang not in ("en", "it"):
        return []
    from wordfreq import zipf_frequency

    hard = [
        t
        for t in nlp.lower_tokens(item.text)
        if t.isalpha() and len(t) > 3 and zipf_frequency(t, ctx.lang) < C.EASY_ZIPF_HARD
    ]
    if hard:
        return [
            Finding(
                "ER008",
                "warning",
                f"'{hard[0]}'",
                f"Zipf ≥ {C.EASY_ZIPF_HARD}",
                "This word may be hard. Use a common word or explain it.",
                "easy",
            )
        ]
    return []


def er009_readability(item: Item, ctx: VerifyContext) -> list[Finding]:
    if ctx.lang == "hi" or nlp.word_count(item.text) < 8:
        return []
    import textstat

    if ctx.lang == "en":
        score = float(textstat.flesch_reading_ease(item.text))
        if score < C.EASY_FLESCH_MIN_EN:
            return [
                Finding(
                    "ER009",
                    "warning",
                    f"Flesch {score:.0f}",
                    f"≥ {C.EASY_FLESCH_MIN_EN}",
                    "The text may be hard to read.",
                    "easy",
                )
            ]
    else:
        textstat.set_lang("it")
        score = float(textstat.gulpease_index(item.text))
        textstat.set_lang("en")
        if score < C.EASY_GULPEASE_MIN_IT:
            return [
                Finding(
                    "ER009",
                    "warning",
                    f"Gulpease {score:.0f}",
                    f"≥ {C.EASY_GULPEASE_MIN_IT}",
                    "The text may be hard to read.",
                    "easy",
                )
            ]
    return []


def er010_layout(item: Item, ctx: VerifyContext) -> list[Finding]:
    return cc002_chars_per_line(item, ctx) + cc003_lines(item, ctx)


# ---------------------------------------------------------------- captions and subtitles
def cc001_cps(item: Item, ctx: VerifyContext) -> list[Finding]:
    kind = "sdh" if item.kind == ItemKind.SDH else "subtitle"
    limit = C.CPS_MAX.get((ctx.lang, kind))
    if limit is None:
        return []
    chars = len(item.text.replace("\n", " "))
    cps = chars / _dur_s(item)
    if cps > limit:
        sev: Severity = "warning" if item.kind == ItemKind.SDH else "error"
        return [
            Finding(
                "CC001",
                sev,
                f"{cps:.1f} characters per second",
                f"≤ {limit}",
                "Too fast to read.",
                "captions",
                repairable=item.kind != ItemKind.SDH,
            )
        ]
    return []


def cc002_chars_per_line(item: Item, ctx: VerifyContext) -> list[Finding]:
    longest = max((len(x) for x in _lines(item.text)), default=0)
    if longest > C.CHARS_PER_LINE_MAX:
        return [
            Finding(
                "CC002",
                "error",
                f"{longest} characters in a line",
                f"≤ {C.CHARS_PER_LINE_MAX}",
                "A caption line is too long.",
                "captions",
            )
        ]
    return []


def cc003_lines(item: Item, ctx: VerifyContext) -> list[Finding]:
    n = len(_lines(item.text))
    if n > C.LINES_MAX:
        return [
            Finding("CC003", "error", f"{n} lines", f"≤ {C.LINES_MAX}", "Too many caption lines.", "captions")
        ]
    return []


def cc004_duration(item: Item, ctx: VerifyContext) -> list[Finding]:
    d = item.slot.end_ms - item.slot.start_ms
    lo = round(C.CUE_MIN_FRAMES / ctx.fps * 1000)
    hi = round(C.CUE_MAX_S * 1000)
    if d < lo or d > hi:
        return [
            Finding(
                "CC004",
                "error",
                fmt_s(d),
                f"{fmt_s(lo)}–{fmt_s(hi)}",
                "The caption is on screen too briefly or too long.",
                "captions",
                repairable=False,
            )
        ]
    return []


def cc005_sync(item: Item, ctx: VerifyContext) -> list[Finding]:
    if item.kind != ItemKind.SDH or not item.source_ids:
        return []
    first = next((w for w in ctx.words if f"w{w.i}" == item.source_ids[0]), None)
    if first is None:
        return []
    off = abs(item.slot.start_ms - first.start_ms)
    if off > C.CUE_SYNC_MS:
        return [
            Finding(
                "CC005",
                "error",
                f"{off} ms from its first word",
                f"≤ {C.CUE_SYNC_MS} ms",
                "The caption starts out of sync with the speech.",
                "captions",
                repairable=False,
            )
        ]
    return []


def _norm_words(text: str) -> list[str]:
    return [
        re.sub(r"[^\w']", "", t.lower()) for t in nlp.tokens(re.sub(r"\[[^\]]*\]|^[A-Z0-9 ]+:", "", text))
    ]


def cc006_not_verbatim(item: Item, ctx: VerifyContext) -> list[Finding]:
    if item.kind != ItemKind.SDH or ctx.is_reviewer_edit or item.source == "manual" or not item.source_ids:
        return []
    ids = set(item.source_ids)
    aligned = " ".join(w.w for w in ctx.words if f"w{w.i}" in ids)
    if _norm_words(aligned) != _norm_words(item.text):
        return [
            Finding(
                "CC006",
                "error",
                "words differ from the speech",
                "verbatim",
                "Captions must match what is said.",
                "captions",
                repairable=False,
            )
        ]
    return []


def cc007_segment_misaligned(item: Item, ctx: VerifyContext) -> list[Finding]:
    return [
        Finding(
            "CC007",
            "error",
            f,
            "ids and snippets match the source batch",
            "The translation is not matched to the right caption.",
            "translate",
        )
        for f in item.flags
        if f.startswith("misaligned:")
    ]


def cc008_untranslated(item: Item, ctx: VerifyContext) -> list[Finding]:
    if item.kind not in (ItemKind.SUBTITLE, ItemKind.VOICEOVER) or ctx.lang == "en":
        return []
    text = item.text.strip()
    src = (item.source_text or "").strip()
    if src and nlp.normalise(text).lower() == nlp.normalise(src).lower():
        return [
            Finding(
                "CC008",
                "error",
                "same as the English",
                "translated",
                "This line was not translated.",
                "translate",
            )
        ]
    if ctx.lang == "hi":
        frac = 1 - nlp.devanagari_fraction(text)
        if frac > C.UNTRANSLATED_ENGLISH_FRACTION:
            return [
                Finding(
                    "CC008",
                    "error",
                    f"{frac:.0%} Latin letters",
                    "mostly Devanagari",
                    "This line is mostly not in Hindi.",
                    "translate",
                )
            ]
        return []
    from wordfreq import zipf_frequency

    toks = [t for t in nlp.lower_tokens(text) if t.isalpha() and len(t) > 2]
    if toks:
        en = sum(1 for t in toks if zipf_frequency(t, "en") > zipf_frequency(t, ctx.lang) + 1.0) / len(toks)
        if en > C.UNTRANSLATED_ENGLISH_FRACTION:
            return [
                Finding(
                    "CC008",
                    "error",
                    f"{en:.0%} English words",
                    f"≤ {C.UNTRANSLATED_ENGLISH_FRACTION:.0%}",
                    "This line is mostly still in English.",
                    "translate",
                )
            ]
    return []


def cc009_number_or_name_changed(item: Item, ctx: VerifyContext) -> list[Finding]:
    if item.kind not in (ItemKind.SUBTITLE, ItemKind.VOICEOVER, ItemKind.AD_TRANSLATION):
        return []
    src = item.source_text or ""
    a, b = nlp.numbers(src, "en"), nlp.numbers(item.text, ctx.lang)
    if a != b:
        return [
            Finding(
                "CC009",
                "error",
                f"numbers {b}",
                f"same as source {a}",
                "A number changed in translation.",
                "translate",
            )
        ]
    if ctx.lang in ("it", "es", "fr", "pt"):  # Latin script: names are kept as written
        lost = [n for n in nlp.kept_names(src) if n.lower() not in item.text.lower()]
        if lost:
            return [
                Finding(
                    "CC009",
                    "error",
                    f"name '{lost[0]}' missing",
                    "every name kept",
                    "A name was lost in translation.",
                    "translate",
                )
            ]
    return []


def cc010_missing_glyph(item: Item, ctx: VerifyContext) -> list[Finding]:
    if ctx.font_glyphs is None:
        return []
    missing = sorted({c for c in item.text if not c.isspace() and c not in ctx.font_glyphs})
    if missing:
        return [
            Finding(
                "CC010",
                "error",
                f"cannot draw {''.join(missing[:5])!r}",
                "every character drawable",
                "The caption font cannot draw some characters.",
                "render",
                repairable=False,
            )
        ]
    return []


# ---------------------------------------------------------------- voice-over
def vo001_slot_overflow(item: Item, ctx: VerifyContext) -> list[Finding]:
    slot = item.slot.end_ms - item.slot.start_ms
    dur = (
        ctx.tts_duration_ms
        if ctx.tts_duration_ms is not None
        else (
            item.tts.duration_ms
            if item.tts
            else round(nlp.word_count(item.text) / max(ctx.wps_voice, 0.1) * 1000)
        )
    )
    if dur > slot * C.VO_TEMPO_MAX:
        return [
            Finding(
                "VO001",
                "error",
                f"{fmt_s(dur)} of speech",
                f"≤ {fmt_s(slot * C.VO_TEMPO_MAX)} (slot × {C.VO_TEMPO_MAX})",
                "The voice-over is too long for its slot. Shorten it.",
                "voiceover",
            )
        ]
    return []


def vo002_untranslated(item: Item, ctx: VerifyContext) -> list[Finding]:
    return [
        Finding("VO002", f.severity, f.observed, f.threshold, f.message, "voiceover")
        for f in cc008_untranslated(item, ctx)
    ]


def vo003_number_or_name(item: Item, ctx: VerifyContext) -> list[Finding]:
    return [
        Finding("VO003", f.severity, f.observed, f.threshold, f.message, "voiceover")
        for f in cc009_number_or_name_changed(item, ctx)
    ]


def vo004_too_short(item: Item, ctx: VerifyContext) -> list[Finding]:
    if item.tts is None and ctx.tts_duration_ms is None:
        return []
    dur = ctx.tts_duration_ms if ctx.tts_duration_ms is not None else item.tts.duration_ms  # type: ignore[union-attr]
    slot = item.slot.end_ms - item.slot.start_ms
    if dur < slot * C.VO_TOO_SHORT_FRACTION:
        return [
            Finding(
                "VO004",
                "warning",
                f"{fmt_s(dur)} in a {fmt_s(slot)} slot",
                f"≥ {C.VO_TOO_SHORT_FRACTION:.0%}",
                "The voice-over is much shorter than the speech. Content may be missing.",
                "voiceover",
            )
        ]
    return []


EASY_RULES: tuple[Rule, ...] = (
    gen001_empty_or_failed,
    er001_too_fast,
    er002_sentence_too_long,
    er003_more_than_one_idea,
    er004_number_changed,
    er005_negation_flipped,
    er006_name_or_term_lost,
    er007_abbreviation,
    er008_hard_word,
    er009_readability,
    er010_layout,
)
SDH_RULES: tuple[Rule, ...] = (
    gen001_empty_or_failed,
    cc001_cps,
    cc002_chars_per_line,
    cc003_lines,
    cc004_duration,
    cc005_sync,
    cc006_not_verbatim,
    cc010_missing_glyph,
)
SUBTITLE_RULES: tuple[Rule, ...] = (
    gen001_empty_or_failed,
    cc001_cps,
    cc002_chars_per_line,
    cc003_lines,
    cc004_duration,
    cc007_segment_misaligned,
    cc008_untranslated,
    cc009_number_or_name_changed,
    cc010_missing_glyph,
)
VOICEOVER_RULES: tuple[Rule, ...] = (
    gen001_empty_or_failed,
    vo001_slot_overflow,
    vo002_untranslated,
    vo003_number_or_name,
    vo004_too_short,
    cc007_segment_misaligned,
)
