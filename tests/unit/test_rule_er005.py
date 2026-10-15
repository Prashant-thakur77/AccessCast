from accesscast.schemas import ItemKind, Slot  # noqa: F401
from accesscast.verify.rules_text import er005_negation_flipped
from tests.unit.conftest import make_item


def _item(**kw):
    base = dict(kind=ItemKind.EASY, lang="en", budget=None, anchor_ms=0, slot=Slot(start_ms=0, end_ms=3000), source_text='Do not unplug the device while it is updating.')
    base.update(kw)
    return make_item(base.pop("draft"), **base)


def test_er005_negation_flipped_passes(ctx):
    ctx.lang = "en"
    assert [f for f in er005_negation_flipped(_item(draft="Do not unplug the device during the update."), ctx) if f.rule == "ER005"] == []


def test_er005_negation_flipped_fails(ctx):
    ctx.lang = "en"
    found = er005_negation_flipped(_item(draft="Unplug the device during the update."), ctx)
    assert found and found[0].rule == "ER005"
