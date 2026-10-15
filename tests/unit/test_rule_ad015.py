from accesscast.schemas import Slot  # noqa: F401
from accesscast.verify.rules_ad import ad015_not_present_tense
from tests.unit.conftest import make_item


def test_ad015_not_present_tense_passes(ctx):
    assert [
        f
        for f in ad015_not_present_tense(make_item("The woman presses Tab on a laptop."), ctx)
        if f.rule == "AD015"
    ] == []


def test_ad015_not_present_tense_fails(ctx):
    found = ad015_not_present_tense(make_item("The woman pressed Tab on a laptop."), ctx)
    assert found and found[0].rule == "AD015"
    assert found[0].observed and found[0].threshold
