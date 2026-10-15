from accesscast.schemas import ItemKind, Slot
from accesscast.verify.rules_text import cc002_chars_per_line
from tests.unit.conftest import make_item


def _item(**kw):
    base = dict(kind=ItemKind.SDH, lang="en", budget=None, anchor_ms=0, slot=Slot(start_ms=0, end_ms=3000))
    base.update(kw)
    return make_item(base.pop("draft"), **base)


def test_cc002_chars_per_line_passes(ctx):
    ctx.lang = "en"
    assert [f for f in cc002_chars_per_line(_item(draft="Press the key."), ctx) if f.rule == "CC002"] == []


def test_cc002_chars_per_line_fails(ctx):
    ctx.lang = "en"
    found = cc002_chars_per_line(
        _item(draft="Press the key on the left side of the keyboard now please."), ctx
    )
    assert found and found[0].rule == "CC002"
