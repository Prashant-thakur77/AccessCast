from accesscast.schemas import Slot  # noqa: F401
from accesscast.verify.rules_ad import ad009_invented_name
from tests.unit.conftest import make_item


def test_ad009_invented_name_passes(ctx):
    assert [
        f
        for f in ad009_invented_name(make_item("The woman presses Tab on a laptop."), ctx)
        if f.rule == "AD009"
    ] == []


def test_ad009_invented_name_fails(ctx):
    found = ad009_invented_name(make_item("Sarah presses Tab on a laptop."), ctx)
    assert found and found[0].rule == "AD009"
    assert found[0].observed and found[0].threshold
