from accesscast.schemas import ItemKind, Slot
from accesscast.verify.rules_text import cc009_number_or_name_changed
from tests.unit.conftest import make_item


def _item(**kw):
    base = dict(
        kind=ItemKind.SUBTITLE,
        lang="it",
        budget=None,
        anchor_ms=0,
        slot=Slot(start_ms=0, end_ms=3000),
        source_text="Press the key 3 times.",
    )
    base.update(kw)
    return make_item(base.pop("draft"), **base)


def test_cc009_number_or_name_changed_passes(ctx):
    ctx.lang = "it"
    assert [
        f
        for f in cc009_number_or_name_changed(_item(draft="Premi il tasto 3 volte."), ctx)
        if f.rule == "CC009"
    ] == []


def test_cc009_number_or_name_changed_fails(ctx):
    ctx.lang = "it"
    found = cc009_number_or_name_changed(_item(draft="Premi il tasto alcune volte."), ctx)
    assert found and found[0].rule == "CC009"


def test_cc009_article_one_and_translated_places_are_not_flagged(ctx):
    # dev false positives: "a comet" → "una cometa"; Moon/Earth/June are translated, not names to keep
    ctx.lang = "it"
    for src, tr in [
        ("Today, we're going to cook a comet.", "Oggi cucineremo una cometa."),
        (
            "It's when the Earth, the Moon, and the Sun are in precise alignment.",
            "È quando Terra, Luna e Sole sono allineati.",
        ),
        ("It has been orbiting the moon since June 2009.", "Orbita intorno alla Luna da giugno 2009."),
    ]:
        assert cc009_number_or_name_changed(_item(draft=tr, source_text=src), ctx) == [], src


def test_cc009_a_person_or_organisation_name_must_stay(ctx):
    ctx.lang = "it"
    found = cc009_number_or_name_changed(
        _item(
            draft="È un veicolo spaziale che orbita intorno alla Luna.",
            source_text="It's a NASA spacecraft that's been orbiting the Moon.",
        ),
        ctx,
    )
    assert found and "NASA" in found[0].observed
