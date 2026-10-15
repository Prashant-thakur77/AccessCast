from accesscast.schemas import ItemKind, Slot  # noqa: F401
from accesscast.verify.rules_text import er008_hard_word
from tests.unit.conftest import make_item


def _item(**kw):
    base = dict(kind=ItemKind.EASY, lang="en", budget=None, anchor_ms=0, slot=Slot(start_ms=0, end_ms=3000))
    base.update(kw)
    return make_item(base.pop("draft"), **base)


def test_er008_hard_word_passes(ctx):
    ctx.lang = "en"
    assert [f for f in er008_hard_word(_item(draft="Press the key."), ctx) if f.rule == "ER008"] == []


def test_er008_hard_word_fails(ctx):
    ctx.lang = "en"
    found = er008_hard_word(_item(draft="Press the idiosyncratic key."), ctx)
    assert found and found[0].rule == "ER008"
