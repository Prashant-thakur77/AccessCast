from accesscast.schemas import ItemKind, Slot
from accesscast.verify.rules_text import er010_layout
from tests.unit.conftest import make_item


def _item(**kw):
    base = dict(kind=ItemKind.EASY, lang="en", budget=None, anchor_ms=0, slot=Slot(start_ms=0, end_ms=3000))
    base.update(kw)
    return make_item(base.pop("draft"), **base)


def test_er010_layout_passes(ctx):
    ctx.lang = "en"
    assert [f for f in er010_layout(_item(draft="Press the key."), ctx) if f.rule == "CC002"] == []


def test_er010_layout_fails(ctx):
    ctx.lang = "en"
    found = er010_layout(_item(draft="Press the key on the left side of the keyboard now please."), ctx)
    assert found and found[0].rule == "CC002"
