from accesscast.schemas import ItemKind, Slot
from accesscast.verify.rules_text import er001_too_fast
from tests.unit.conftest import make_item


def _item(**kw):
    base = dict(kind=ItemKind.EASY, lang="en", budget=None, anchor_ms=0, slot=Slot(start_ms=0, end_ms=3000))
    base.update(kw)
    return make_item(base.pop("draft"), **base)


def test_er001_too_fast_passes(ctx):
    ctx.lang = "en"
    assert [
        f for f in er001_too_fast(_item(draft="Press the button 3 times."), ctx) if f.rule == "ER001"
    ] == []


def test_er001_too_fast_fails(ctx):
    ctx.lang = "en"
    found = er001_too_fast(
        _item(
            draft="Press the red button three times quickly and then wait for the light to turn green before you go on."
        ),
        ctx,
    )
    assert found and found[0].rule == "ER001"
