from accesscast.schemas import Slot  # noqa: F401
from accesscast.verify.rules_ad import ad012_not_grounded
from tests.unit.conftest import make_item


def test_ad012_not_grounded_passes(ctx):
    assert [
        f
        for f in ad012_not_grounded(make_item("The woman presses Tab on a laptop."), ctx)
        if f.rule == "AD012"
    ] == []


def test_ad012_not_grounded_fails(ctx):
    found = ad012_not_grounded(make_item("A pilot flies a helicopter over mountains."), ctx)
    assert found and found[0].rule == "AD012"
    assert found[0].observed and found[0].threshold
