from accesscast.schemas import ItemKind, Slot  # noqa: F401
from accesscast.verify.rules_text import er002_sentence_too_long
from tests.unit.conftest import make_item


def _item(**kw):
    base = dict(kind=ItemKind.EASY, lang="en", budget=None, anchor_ms=0, slot=Slot(start_ms=0, end_ms=3000))
    base.update(kw)
    return make_item(base.pop("draft"), **base)


def test_er002_sentence_too_long_passes(ctx):
    ctx.lang = "en"
    assert [f for f in er002_sentence_too_long(_item(draft="Press the button 3 times."), ctx) if f.rule == "ER002"] == []


def test_er002_sentence_too_long_fails(ctx):
    ctx.lang = "en"
    found = er002_sentence_too_long(_item(draft="Press the big red button on the left side of the machine three times before you start it."), ctx)
    assert found and found[0].rule == "ER002"
