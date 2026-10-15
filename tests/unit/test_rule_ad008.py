from accesscast.schemas import Slot  # noqa: F401
from accesscast.verify.rules_ad import ad008_restates_dialogue
from tests.unit.conftest import make_item


def test_ad008_restates_dialogue_passes(ctx):
    assert [
        f
        for f in ad008_restates_dialogue(make_item("The woman presses Tab on a laptop."), ctx)
        if f.rule == "AD008"
    ] == []


def test_ad008_restates_dialogue_fails(ctx):
    found = ad008_restates_dialogue(make_item("She is opening the settings menu."), ctx)
    assert found and found[0].rule == "AD008"
    assert found[0].observed and found[0].threshold
