from accesscast.schemas import ItemKind, Slot
from accesscast.verify.rules_text import cc008_untranslated
from tests.unit.conftest import make_item


def _item(**kw):
    base = dict(
        kind=ItemKind.SUBTITLE,
        lang="hi",
        budget=None,
        anchor_ms=0,
        slot=Slot(start_ms=0, end_ms=3000),
        source_text="Press the key.",
    )
    base.update(kw)
    return make_item(base.pop("draft"), **base)


def test_cc008_untranslated_passes(ctx):
    ctx.lang = "hi"
    assert [f for f in cc008_untranslated(_item(draft="कुंजी दबाएँ।"), ctx) if f.rule == "CC008"] == []


def test_cc008_untranslated_fails(ctx):
    ctx.lang = "hi"
    found = cc008_untranslated(_item(draft="Press the key."), ctx)
    assert found and found[0].rule == "CC008"
