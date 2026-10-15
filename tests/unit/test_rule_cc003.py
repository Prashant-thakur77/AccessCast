from accesscast.schemas import ItemKind, Slot  # noqa: F401
from accesscast.verify.rules_text import cc003_lines
from tests.unit.conftest import make_item


def _item(**kw):
    base = dict(kind=ItemKind.SDH, lang="en", budget=None, anchor_ms=0, slot=Slot(start_ms=0, end_ms=3000))
    base.update(kw)
    return make_item(base.pop("draft"), **base)


def test_cc003_lines_passes(ctx):
    ctx.lang = "en"
    assert [f for f in cc003_lines(_item(draft="Press\nthe key."), ctx) if f.rule == "CC003"] == []


def test_cc003_lines_fails(ctx):
    ctx.lang = "en"
    found = cc003_lines(_item(draft="Press\nthe\nkey."), ctx)
    assert found and found[0].rule == "CC003"
