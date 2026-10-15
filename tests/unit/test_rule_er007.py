from accesscast.schemas import ItemKind, Slot  # noqa: F401
from accesscast.verify.rules_text import er007_abbreviation
from tests.unit.conftest import make_item


def _item(**kw):
    base = dict(kind=ItemKind.EASY, lang="en", budget=None, anchor_ms=0, slot=Slot(start_ms=0, end_ms=3000))
    base.update(kw)
    return make_item(base.pop("draft"), **base)


def test_er007_abbreviation_passes(ctx):
    ctx.lang = "en"
    assert [f for f in er007_abbreviation(_item(draft="Use a key, for example Tab."), ctx) if f.rule == "ER007"] == []


def test_er007_abbreviation_fails(ctx):
    ctx.lang = "en"
    found = er007_abbreviation(_item(draft="Use a key, e.g. Tab."), ctx)
    assert found and found[0].rule == "ER007"
