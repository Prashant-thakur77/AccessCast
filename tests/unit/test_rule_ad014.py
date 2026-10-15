from accesscast.schemas import Slot  # noqa: F401
from accesscast.verify.rules_ad import ad014_commentary
from tests.unit.conftest import make_item


def test_ad014_commentary_passes(ctx):
    assert [
        f for f in ad014_commentary(make_item("The woman presses Tab on a laptop."), ctx) if f.rule == "AD014"
    ] == []


def test_ad014_commentary_fails(ctx):
    found = ad014_commentary(make_item("We see the woman press Tab on a laptop."), ctx)
    assert found and found[0].rule == "AD014"
    assert found[0].observed and found[0].threshold
