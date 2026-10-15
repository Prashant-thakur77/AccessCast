from accesscast.schemas import ItemKind, Slot  # noqa: F401
from accesscast.verify.rules_text import cc009_number_or_name_changed
from tests.unit.conftest import make_item


def _item(**kw):
    base = dict(kind=ItemKind.SUBTITLE, lang="it", budget=None, anchor_ms=0, slot=Slot(start_ms=0, end_ms=3000), source_text='Press the key 3 times.')
    base.update(kw)
    return make_item(base.pop("draft"), **base)


def test_cc009_number_or_name_changed_passes(ctx):
    ctx.lang = "it"
    assert [f for f in cc009_number_or_name_changed(_item(draft="Premi il tasto 3 volte."), ctx) if f.rule == "CC009"] == []


def test_cc009_number_or_name_changed_fails(ctx):
    ctx.lang = "it"
    found = cc009_number_or_name_changed(_item(draft="Premi il tasto alcune volte."), ctx)
    assert found and found[0].rule == "CC009"
