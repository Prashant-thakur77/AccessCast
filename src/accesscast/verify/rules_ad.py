"""Description-line rules AD001–AD020 (PLAN §10.2). Each rule is a pure function of (item, ctx)."""

from __future__ import annotations

import re

from accesscast import constants as C
from accesscast.schemas import Item, ItemKind, SceneEvidence, VisibleFact
from accesscast.verify import lexicons as L
from accesscast.verify import nlp
from accesscast.verify.base import Finding, Rule, Severity, VerifyContext, fmt_s


def _text(item: Item) -> str:
    return item.text.strip()


def _lower(item: Item) -> str:
    return nlp.normalise(_text(item)).lower()


def estimated_duration_ms(item: Item, ctx: VerifyContext) -> int:
    """Measured clip duration if we have it; otherwise words / wps_voice (PLAN §9 S7)."""
    if ctx.tts_duration_ms is not None:
        return ctx.tts_duration_ms
    if item.tts is not None:
        return item.tts.duration_ms
    wps = item.budget.wps_voice if item.budget else ctx.wps_voice
    return round(nlp.word_count(_text(item)) / max(wps, 0.1) * 1000)


def _evidence(item: Item, ctx: VerifyContext) -> SceneEvidence | None:
    return ctx.evidence.get(item.scene_id or "")


def _facts(item: Item, ctx: VerifyContext) -> list[VisibleFact]:
    ev = _evidence(item, ctx)
    if ev is None:
        return []
    return [f for f in ev.visible_facts if f.fid in item.fact_ids]


def _has_phrase(text: str, phrase: str) -> bool:
    return re.search(r"(?<![\w])" + re.escape(phrase) + r"(?![\w])", text) is not None


def _quote_framed(text: str, lang: str) -> bool:
    low = text.lower()
    return any(fr in low for fr in L.QUOTE_FRAMES.get(lang, ())) or '"' in text or "“" in text


# ---------------------------------------------------------------- timing rules
def ad001_gap_overflow(item: Item, ctx: VerifyContext) -> list[Finding]:
    dur = estimated_duration_ms(item, ctx)
    need = dur + C.AD_PAD_BEFORE_MS + C.AD_PAD_AFTER_MS
    avail = item.slot.end_ms - max(item.anchor_ms, item.slot.start_ms)
    if item.anchor_ms < item.slot.start_ms:
        return [
            Finding(
                "AD001",
                "error",
                f"anchor {fmt_s(item.anchor_ms)}",
                f"≥ pause start {fmt_s(item.slot.start_ms)}",
                "The line starts before the pause begins.",
                "plan_ad",
                repairable=False,
            )
        ]
    if need > avail:
        measured = "measured" if (ctx.tts_duration_ms is not None or item.tts is not None) else "estimated"
        return [
            Finding(
                "AD001",
                "error",
                f"{fmt_s(need)} ({measured}, incl. pads)",
                f"≤ {fmt_s(avail)}",
                f"Spoken line is {fmt_s(need - avail)} longer than the pause.",
                "write_ad",
            )
        ]
    return []


def ad002_anchor_inside_word(item: Item, ctx: VerifyContext) -> list[Finding]:
    for w in ctx.words:
        if w.start_ms < item.anchor_ms < w.end_ms:
            return [
                Finding(
                    "AD002",
                    "error",
                    f"anchor {fmt_s(item.anchor_ms)} inside '{w.w}'",
                    f"outside {fmt_s(w.start_ms)}–{fmt_s(w.end_ms)}",
                    "The line would start in the middle of a spoken word.",
                    "plan_ad",
                    repairable=False,
                )
            ]
    return []


def ad003_anchor_near_word(item: Item, ctx: VerifyContext) -> list[Finding]:
    if not ctx.words:
        return []
    near = min(min(abs(item.anchor_ms - w.start_ms), abs(item.anchor_ms - w.end_ms)) for w in ctx.words)
    if near < C.AD_NEAR_WORD_MS:
        return [
            Finding(
                "AD003",
                "warning",
                f"{near} ms from a word edge",
                f"≥ {C.AD_NEAR_WORD_MS} ms",
                "The line starts very close to dialogue.",
                "plan_ad",
                repairable=False,
            )
        ]
    return []


def clip_span(item: Item, ctx: VerifyContext) -> tuple[int, int]:
    """The anchor is the start of the padded region; the voice starts AD_PAD_BEFORE_MS later (PLAN §9 S7)."""
    start = item.anchor_ms + C.AD_PAD_BEFORE_MS
    return start, start + estimated_duration_ms(item, ctx)


def ad004_overlaps_speech(item: Item, ctx: VerifyContext) -> list[Finding]:
    start, end = clip_span(item, ctx)
    for a, b in ctx.speech_spans():
        ov = min(end, b) - max(start, a)
        if ov > 0:
            return [
                Finding(
                    "AD004",
                    "error",
                    f"overlaps speech by {fmt_s(ov)}",
                    "0 s overlap",
                    "The spoken line would play on top of dialogue.",
                    "write_ad",
                )
            ]
    return []


def ad005_anchor_far_from_event(item: Item, ctx: VerifyContext) -> list[Finding]:
    ev = _evidence(item, ctx)
    if ev is None or not item.fact_ids:
        return []
    facts = _facts(item, ctx)
    missing = sorted(set(item.fact_ids) - {f.fid for f in facts})
    if missing:
        return [
            Finding(
                "AD005",
                "error",
                f"unknown fact ids {missing}",
                "fact ids from the scene evidence",
                "The line cites facts that do not exist.",
                "write_ad",
            )
        ]
    times = [ev.frame_ms[i] for f in facts for i in f.frames if 0 <= i < len(ev.frame_ms)]
    if not times:
        return []
    lo, hi = min(times) - C.AD_EVENT_BEFORE_MS, max(times) + C.AD_EVENT_AFTER_MS
    if not lo <= item.anchor_ms <= hi:
        return [
            Finding(
                "AD005",
                "error",
                f"anchor {fmt_s(item.anchor_ms)}",
                f"within {fmt_s(lo)}–{fmt_s(hi)}",
                "The line is too far from what it describes.",
                "plan_ad",
                repairable=False,
            )
        ]
    return []


def ad006_non_monotonic(item: Item, ctx: VerifyContext) -> list[Finding]:
    me_start, me_end = clip_span(item, ctx)
    for other in ctx.other_items:
        if other.id == item.id or other.kind != item.kind or other.lang != item.lang:
            continue
        o_start, o_end = clip_span(other, VerifyContext(wps_voice=ctx.wps_voice))
        if not other.extended:  # AD001 keeps every sibling inside its own slot
            o_end = min(o_end, other.slot.end_ms)
        if min(me_end, o_end) - max(me_start, o_start) > 0:
            return [
                Finding(
                    "AD006",
                    "error",
                    f"overlaps {other.id}",
                    "no overlap between description lines",
                    "Two description lines would play at the same time.",
                    "plan_ad",
                )
            ]
        if (other.id < item.id) != (other.anchor_ms < item.anchor_ms) or other.anchor_ms == item.anchor_ms:
            return [
                Finding(
                    "AD006",
                    "error",
                    f"order vs {other.id}",
                    "ids in time order",
                    "Description lines are out of time order.",
                    "plan_ad",
                    repairable=False,
                )
            ]
    return []


def ad007_word_budget(item: Item, ctx: VerifyContext) -> list[Finding]:
    if item.budget is None:
        return []
    n = nlp.word_count(_text(item))
    if n > item.budget.words_max:
        return [
            Finding(
                "AD007",
                "error",
                f"{n} words",
                f"≤ {item.budget.words_max} words",
                "Too many words for this pause. Shorten it.",
                "write_ad",
            )
        ]
    return []


# ---------------------------------------------------------------- content rules
def ad008_restates_dialogue(item: Item, ctx: VerifyContext) -> list[Finding]:
    dia = ctx.dialogue_text(item.anchor_ms - C.AD_RESTATE_WINDOW_MS, item.anchor_ms + C.AD_RESTATE_WINDOW_MS)
    if not dia:
        return []
    a = nlp.lemmas(_text(item), ctx.lang)
    b = nlp.lemmas(dia, ctx.lang)
    shared = nlp.ngrams(a, C.AD_RESTATE_NGRAM) & nlp.ngrams(b, C.AD_RESTATE_NGRAM)
    if shared:
        return [
            Finding(
                "AD008",
                "error",
                f"shares '{' '.join(sorted(shared)[0])}'",
                f"no shared {C.AD_RESTATE_NGRAM}-word phrase with dialogue (±10 s)",
                "Do not repeat what someone says.",
                "write_ad",
            )
        ]
    sw = nlp.STOPWORDS[ctx.lang]
    ta = {t for t in a if t not in sw}
    tb = {t for t in b if t not in sw}
    j = nlp.jaccard(ta, tb)
    if j > C.AD_RESTATE_JACCARD:
        return [
            Finding(
                "AD008",
                "error",
                f"word overlap {j:.2f}",
                f"≤ {C.AD_RESTATE_JACCARD}",
                "Do not repeat what someone says.",
                "write_ad",
            )
        ]
    return []


def ad009_invented_name(item: Item, ctx: VerifyContext) -> list[Finding]:
    allowed = {n.lower() for n in ctx.allowed_names}
    ev = _evidence(item, ctx)
    if ev is not None:
        for t in ev.on_screen_text:
            allowed |= {x.lower() for x in nlp.tokens(t.text)}
    # Capitalised words in the line's own facts are grounded (S5 already removed unsupported names).
    for f in _facts(item, ctx):
        allowed |= {x.lower() for x in nlp.tokens(f.text)}
    text = _text(item)
    # Text quoted from the screen may contain names; only check outside quotes.
    unquoted = re.sub(r"[\"“][^\"”]*[\"”]", " ", text)
    if ":" in unquoted and _quote_framed(unquoted, ctx.lang):
        unquoted = unquoted.split(":", 1)[0]
    bad = [n for n in nlp.proper_nouns(unquoted, ctx.lang) if n.lower() not in allowed]
    if bad:
        return [
            Finding(
                "AD009",
                "error",
                f"name {bad[0]!r}",
                f"names allowed: {', '.join(sorted(ctx.allowed_names)) or 'none'}",
                "Do not use a name nobody said or showed.",
                "write_ad",
            )
        ]
    return []


def ad010_unsupported_claim(item: Item, ctx: VerifyContext) -> list[Finding]:
    low = _lower(item)
    facts = " ".join(f.text.lower() for f in _facts(item, ctx))
    ev = _evidence(item, ctx)
    screen = " ".join(t.text.lower() for t in ev.on_screen_text) if ev else ""
    hits: list[str] = []
    for kind, phrases in L.CLAIMS[ctx.lang].items():
        for p in phrases:
            if (
                _has_phrase(low, p)
                and not _has_phrase(facts, p)
                and not (kind == "occupation" and p in screen)
            ):
                if kind == "certainty" and _quote_framed(_text(item), ctx.lang) and p in screen:
                    continue
                hits.append(f"{kind}: '{p}'")
    if hits:
        return [
            Finding(
                "AD010",
                "error",
                "; ".join(hits[:3]),
                "no motive, relationship, destination, "
                "occupation, off-screen or certainty claims not in the facts",
                "Describe only what is visible.",
                "write_ad",
            )
        ]
    return []


def ad011_sound(item: Item, ctx: VerifyContext) -> list[Finding]:
    low = _lower(item)
    if _quote_framed(_text(item), ctx.lang) and ":" in low:
        low = low.split(":", 1)[0]
    hits = [w for w in L.SOUND_WORDS[ctx.lang] if _has_phrase(low, w)]
    # A sound word printed on screen in this scene ("Display, Sound, Privacy" in a menu) is visible text, not a
    # claim about the audio (dev false positive on A7, docs/incidents.md 2026-10-17).
    ev = _evidence(item, ctx)
    shown = " ".join(t.text for t in ev.on_screen_text).lower() if ev is not None else ""
    hits = [w for w in hits if not _has_phrase(shown, w)]
    if hits:
        return [
            Finding(
                "AD011",
                "error",
                f"sound word '{hits[0]}'",
                "no sound or speech words",
                "Describe what can be seen, not heard.",
                "write_ad",
            )
        ]
    return []


def ad012_not_grounded(item: Item, ctx: VerifyContext) -> list[Finding]:
    nouns = nlp.content_nouns(_text(item), ctx.lang)
    if not nouns:
        return []
    ev = _evidence(item, ctx)
    support_text = " ".join(f.text for f in _facts(item, ctx))
    if ev is not None:
        support_text += " " + " ".join(t.text for t in ev.on_screen_text)
        support_text += " " + " ".join(c.appearance for c in ev.characters)
        support_text += " " + ev.setting
    support = set(nlp.lemmas(support_text, ctx.lang)) | {t.lower() for t in nlp.tokens(support_text)}
    unsupported = []
    for n in nouns:
        if n in support or n in L.GENERIC_NOUNS:
            continue
        if L.SYNONYMS.get(n, frozenset()) & support:
            continue
        unsupported.append(n)
    if not unsupported:
        return []
    frac = len(unsupported) / len(nouns)
    sev: Severity = "error" if frac > C.AD_GROUNDING_ERROR_FRACTION else "warning"
    return [
        Finding(
            "AD012",
            sev,
            f"{len(unsupported)} of {len(nouns)} nouns unsupported ({', '.join(unsupported[:3])})",
            "every noun in the facts, on-screen text or cast (error above 1/3)",
            "Use only what the listed facts say.",
            "write_ad",
        )
    ]


def grounding_share(item: Item, ctx: VerifyContext) -> float:
    """Share of content nouns supported (used by confidence.py)."""
    found = ad012_not_grounded(item, ctx)
    if not found:
        return 1.0
    m = re.match(r"(\d+) of (\d+)", found[0].observed)
    if not m:
        return 0.0
    bad, total = int(m.group(1)), int(m.group(2))
    return 1.0 - bad / total if total else 1.0


def ad013_onscreen_not_read(item: Item, ctx: VerifyContext) -> list[Finding]:
    ev = _evidence(item, ctx)
    if ev is None:
        return []
    siblings = [o for o in ctx.other_items if o.scene_id == item.scene_id] or [item]
    said = " ".join(o.text.lower() for o in siblings)
    for t in ev.on_screen_text:
        if (
            t.kind in ("title", "slide")
            and nlp.word_count(t.text) >= C.AD_ONSCREEN_MIN_WORDS
            and (t.ocr_agrees or t.source == "ocr")
        ):
            words = [w.lower() for w in nlp.tokens(t.text)]
            hit = sum(1 for w in words if w in said) / len(words)
            if hit < 0.5:
                return [
                    Finding(
                        "AD013",
                        "warning",
                        f"'{t.text[:40]}' not read",
                        "titles and slides read aloud",
                        "Important on-screen text is not read in this scene.",
                        "plan_ad",
                        repairable=False,
                    )
                ]
    return []


def ad014_commentary(item: Item, ctx: VerifyContext) -> list[Finding]:
    low = _lower(item)
    hits = [p for p in L.COMMENTARY[ctx.lang] if _has_phrase(low, p)]
    if hits:
        return [
            Finding(
                "AD014",
                "warning",
                f"'{hits[0]}'",
                "no commentary phrases",
                "Describe directly, without 'we see' or 'seems to'.",
                "write_ad",
            )
        ]
    return []


def ad015_not_present_tense(item: Item, ctx: VerifyContext) -> list[Finding]:
    if ctx.lang != "en":
        return []
    past = nlp.finite_past_verbs(_text(item))
    if past:
        return [
            Finding(
                "AD015",
                "warning",
                f"past tense '{past[0]}'",
                "present tense",
                "Use the present tense.",
                "write_ad",
            )
        ]
    return []


def ad016_wrong_language(item: Item, ctx: VerifyContext) -> list[Finding]:
    text = _text(item)
    if ctx.lang == "hi":
        frac = nlp.devanagari_fraction(text)
        if frac < C.AD_HINDI_DEVANAGARI_MIN:
            return [
                Finding(
                    "AD016",
                    "error",
                    f"{frac:.0%} Devanagari letters",
                    f"≥ {C.AD_HINDI_DEVANAGARI_MIN:.0%}",
                    "The line is not in Hindi.",
                    "write_ad",
                )
            ]
        return []
    if nlp.devanagari_fraction(text) > 0.1:
        return [
            Finding(
                "AD016",
                "error",
                "Devanagari letters in a Latin-script language",
                "Latin script only",
                f"The line is not in the target language ({ctx.lang}).",
                "write_ad",
            )
        ]
    if ctx.lang == "it" and item.kind == ItemKind.AD_TRANSLATION:
        src = ctx.approved_english.get(item.source_ids[0], "") if item.source_ids else ""
        if src and nlp.normalise(src).strip().lower() == _lower(item):
            return [
                Finding(
                    "AD016",
                    "error",
                    "same text as the English",
                    "translated",
                    "The line was not translated.",
                    "write_ad",
                )
            ]
    return []


def ad017_emotion_inferred(item: Item, ctx: VerifyContext) -> list[Finding]:
    low = _lower(item)
    facts = " ".join(f.text.lower() for f in _facts(item, ctx))
    emos = [e for e in L.EMOTIONS[ctx.lang] if _has_phrase(low, e) and not _has_phrase(facts, e)]
    if emos and not any(x in facts for x in L.VISIBLE_EXPRESSIONS):
        return [
            Finding(
                "AD017",
                "warning",
                f"emotion '{emos[0]}'",
                "visible expression in the facts",
                "Describe the visible expression, not the feeling.",
                "write_ad",
            )
        ]
    return []


def ad018_injection_echo(item: Item, ctx: VerifyContext) -> list[Finding]:
    ev = _evidence(item, ctx)
    if ev is None:
        return []
    low = _lower(item)
    for t in ev.on_screen_text:
        tl = t.text.lower()
        markers = [m for m in L.INJECTION_MARKERS if m in tl]
        if not markers:
            continue
        # Any 3-word run of the instruction text appearing in the line, outside a quote frame.
        toks = nlp.lower_tokens(tl)
        runs = {" ".join(toks[i : i + 3]) for i in range(len(toks) - 2)}
        echoed = [r for r in runs if r in low]
        if echoed and not _quote_framed(_text(item), ctx.lang):
            return [
                Finding(
                    "AD018",
                    "error",
                    f"repeats on-screen instruction '{sorted(echoed)[0]}'",
                    "on-screen text only inside 'On screen: …' framing",
                    "On-screen text that gives orders must be quoted, not obeyed.",
                    "write_ad",
                )
            ]
        if any(m in low for m in markers) and not _quote_framed(_text(item), ctx.lang):
            return [
                Finding(
                    "AD018",
                    "error",
                    f"instruction phrase '{markers[0]}'",
                    "quoted framing",
                    "On-screen text that gives orders must be quoted, not obeyed.",
                    "write_ad",
                )
            ]
    return []


def ad019_empty_or_filler(item: Item, ctx: VerifyContext) -> list[Finding]:
    low = _lower(item).strip(" .!")
    if not low or low in L.FILLER or nlp.word_count(low) < 2:
        return [
            Finding(
                "AD019",
                "error",
                f"'{_text(item)[:30]}'",
                "a real description",
                "The line is empty or says nothing.",
                "write_ad",
            )
        ]
    return []


def ad020_backtranslation_drift(item: Item, ctx: VerifyContext) -> list[Finding]:
    """Advisory (never blocks). Real LaBSE score is computed by the metrics worker and stored in flags."""
    for f in item.flags:
        if f.startswith("bt_cos="):
            cos = float(f.split("=", 1)[1])
            if cos < C.AD_BACKTRANSLATION_MIN_COS:
                return [
                    Finding(
                        "AD020",
                        "warning",
                        f"cosine {cos:.2f}",
                        f"≥ {C.AD_BACKTRANSLATION_MIN_COS}",
                        "The back-translation drifts from the approved English.",
                        "ad_translate",
                    )
                ]
    return []


AD_RULES: tuple[Rule, ...] = (
    ad001_gap_overflow,
    ad002_anchor_inside_word,
    ad003_anchor_near_word,
    ad004_overlaps_speech,
    ad005_anchor_far_from_event,
    ad006_non_monotonic,
    ad007_word_budget,
    ad008_restates_dialogue,
    ad009_invented_name,
    ad010_unsupported_claim,
    ad011_sound,
    ad012_not_grounded,
    ad013_onscreen_not_read,
    ad014_commentary,
    ad015_not_present_tense,
    ad016_wrong_language,
    ad017_emotion_inferred,
    ad018_injection_echo,
    ad019_empty_or_filler,
    ad020_backtranslation_drift,
)
