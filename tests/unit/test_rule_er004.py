from accesscast.schemas import ItemKind, Slot
from accesscast.verify.rules_text import er004_number_changed
from tests.unit.conftest import make_item


def _item(**kw):
    base = dict(
        kind=ItemKind.EASY,
        lang="en",
        budget=None,
        anchor_ms=0,
        slot=Slot(start_ms=0, end_ms=3000),
        source_text="Press the button 3 times within 10 seconds.",
    )
    base.update(kw)
    return make_item(base.pop("draft"), **base)


def test_er004_number_changed_passes(ctx):
    ctx.lang = "en"
    assert [
        f
        for f in er004_number_changed(_item(draft="Press the button 3 times in 10 seconds."), ctx)
        if f.rule == "ER004"
    ] == []


def test_er004_number_changed_fails(ctx):
    ctx.lang = "en"
    found = er004_number_changed(_item(draft="Press the button a few times quickly."), ctx)
    assert found and found[0].rule == "ER004"
