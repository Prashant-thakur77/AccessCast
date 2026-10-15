from accesscast.schemas import ItemKind, Slot  # noqa: F401
from accesscast.verify.rules_text import cc004_duration
from tests.unit.conftest import make_item


def _item(**kw):
    base = dict(kind=ItemKind.SDH, lang="en", budget=None, anchor_ms=0, slot=Slot(start_ms=0, end_ms=3000))
    base.update(kw)
    return make_item(base.pop("draft"), **base)


def test_cc004_duration_passes(ctx):
    ctx.lang = "en"
    assert [f for f in cc004_duration(_item(draft="Press the key."), ctx) if f.rule == "CC004"] == []


def test_cc004_duration_fails(ctx):
    ctx.lang = "en"
    found = cc004_duration(_item(draft="Press the key.", slot=Slot(start_ms=0, end_ms=500)), ctx)
    assert found and found[0].rule == "CC004"
