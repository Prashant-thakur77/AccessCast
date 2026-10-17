"""Spanish and French subtitles: the number, name and untranslated checks, passing and failing."""

import pytest

from accesscast import constants as C
from accesscast.schemas import ItemKind, Slot
from accesscast.verify import nlp
from accesscast.verify.rules_text import SUBTITLE_RULES, cc008_untranslated, cc009_number_or_name_changed
from tests.unit.conftest import make_item


def _sub(lang: str, draft: str, source: str):
    return make_item(
        draft,
        id=f"subs.{lang}.0001",
        kind=ItemKind.SUBTITLE,
        lang=lang,
        audiences=[lang],
        budget=None,
        anchor_ms=0,
        slot=Slot(start_ms=0, end_ms=3500),
        source_text=source,
    )


@pytest.mark.parametrize(
    "lang,good,bad",
    [
        ("es", "Hay casi 10.000 galaxias.", "Hay casi mil galaxias."),
        ("fr", "Il y a près de 10 000 galaxies.", "Il y a près de mille galaxies."),
    ],
)
def test_numbers_kept_or_caught(ctx, lang, good, bad):
    ctx.lang = lang
    src = "There are nearly 10,000 galaxies."
    assert [f for f in cc009_number_or_name_changed(_sub(lang, good, src), ctx) if f.rule == "CC009"] == []
    assert [f.rule for f in cc009_number_or_name_changed(_sub(lang, bad, src), ctx)] == ["CC009"]


@pytest.mark.parametrize(
    "lang,good,bad",
    [
        ("es", "La Dra. Maria Lopez explica los resultados.", "La doctora explica los resultados."),
        ("fr", "La Dre Maria Lopez explique les résultats.", "La docteure explique les résultats."),
    ],
)
def test_names_kept_or_caught(ctx, lang, good, bad):
    ctx.lang = lang
    src = "Dr. Maria Lopez explains the results."
    assert cc009_number_or_name_changed(_sub(lang, good, src), ctx) == []
    assert [f.rule for f in cc009_number_or_name_changed(_sub(lang, bad, src), ctx)] == ["CC009"]


@pytest.mark.parametrize(
    "lang,good",
    [
        ("es", "No desconectes el portátil mientras guarda."),
        ("fr", "Ne débranchez pas l'ordinateur pendant l'enregistrement."),
    ],
)
def test_untranslated_caught(ctx, lang, good):
    ctx.lang = lang
    src = "Do not unplug the laptop while it saves."
    assert cc008_untranslated(_sub(lang, good, src), ctx) == []
    assert [f.rule for f in cc008_untranslated(_sub(lang, src, src), ctx)] == ["CC008"]


def test_every_subtitle_rule_runs_on_the_new_languages(ctx):
    for lang in ("es", "fr"):
        ctx.lang = lang
        item = _sub(lang, "Hola." if lang == "es" else "Bonjour.", "Hello.")
        for rule in SUBTITLE_RULES:
            rule(item, ctx)  # no KeyError or UnknownLanguageError: every table has the language


def test_new_languages_are_registered():
    assert {"es", "fr"} <= set(C.TRANSLATION_LANGS) and {"es", "fr"} <= set(C.LANGS)
    for lang in ("es", "fr"):
        assert (lang, "subtitle") in C.CPS_MAX
        assert nlp.negation_count("no nunca" if lang == "es" else "pas jamais", lang) == 2
