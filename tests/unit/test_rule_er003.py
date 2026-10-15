from accesscast.schemas import ItemKind, Slot  # noqa: F401
from accesscast.verify.rules_text import er003_more_than_one_idea
from tests.unit.conftest import make_item


def _item(**kw):
    base = dict(kind=ItemKind.EASY, lang="en", budget=None, anchor_ms=0, slot=Slot(start_ms=0, end_ms=3000))
    base.update(kw)
    return make_item(base.pop("draft"), **base)


def test_er003_more_than_one_idea_passes(ctx):
    ctx.lang = "en"
    assert [f for f in er003_more_than_one_idea(_item(draft="Press the button."), ctx) if f.rule == "ER003"] == []


def test_er003_more_than_one_idea_fails(ctx):
    ctx.lang = "en"
    found = er003_more_than_one_idea(_item(draft="She presses the button and the machine starts."), ctx)
    assert found and found[0].rule == "ER003"
