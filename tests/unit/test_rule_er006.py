from accesscast.schemas import ItemKind, Slot
from accesscast.verify.rules_text import er006_name_or_term_lost
from tests.unit.conftest import make_item


def _item(**kw):
    base = dict(
        kind=ItemKind.EASY,
        lang="en",
        budget=None,
        anchor_ms=0,
        slot=Slot(start_ms=0, end_ms=3000),
        source_text="Maria will help you.",
    )
    base.update(kw)
    return make_item(base.pop("draft"), **base)


def test_er006_name_or_term_lost_passes(ctx):
    ctx.lang = "en"
    assert [
        f for f in er006_name_or_term_lost(_item(draft="Maria helps you."), ctx) if f.rule == "ER006"
    ] == []


def test_er006_name_or_term_lost_fails(ctx):
    ctx.lang = "en"
    found = er006_name_or_term_lost(_item(draft="Someone helps you."), ctx)
    assert found and found[0].rule == "ER006"
