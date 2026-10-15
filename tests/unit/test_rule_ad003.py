from accesscast.schemas import Slot  # noqa: F401
from accesscast.verify.rules_ad import ad003_anchor_near_word
from tests.unit.conftest import make_item


def test_ad003_anchor_near_word_passes(ctx):
    assert [
        f
        for f in ad003_anchor_near_word(make_item("The woman presses Tab on a laptop."), ctx)
        if f.rule == "AD003"
    ] == []


def test_ad003_anchor_near_word_fails(ctx):
    found = ad003_anchor_near_word(make_item("The woman presses Tab on a laptop.", anchor_ms=1950), ctx)
    assert found and found[0].rule == "AD003"
    assert found[0].observed and found[0].threshold
