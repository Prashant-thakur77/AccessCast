from accesscast.schemas import Slot
from accesscast.verify.rules_ad import ad002_anchor_inside_word
from tests.unit.conftest import make_item


def test_ad002_anchor_inside_word_passes(ctx):
    assert [
        f
        for f in ad002_anchor_inside_word(make_item("The woman presses Tab on a laptop."), ctx)
        if f.rule == "AD002"
    ] == []


def test_ad002_anchor_inside_word_fails(ctx):
    found = ad002_anchor_inside_word(
        make_item("The woman presses Tab on a laptop.", anchor_ms=600, slot=Slot(start_ms=0, end_ms=8800)),
        ctx,
    )
    assert found and found[0].rule == "AD002"
    assert found[0].observed and found[0].threshold
