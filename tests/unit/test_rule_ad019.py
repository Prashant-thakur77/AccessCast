from accesscast.schemas import Slot  # noqa: F401
from accesscast.verify.rules_ad import ad019_empty_or_filler
from tests.unit.conftest import make_item


def test_ad019_empty_or_filler_passes(ctx):
    assert [
        f
        for f in ad019_empty_or_filler(make_item("The woman presses Tab on a laptop."), ctx)
        if f.rule == "AD019"
    ] == []


def test_ad019_empty_or_filler_fails(ctx):
    found = ad019_empty_or_filler(make_item("Something happens."), ctx)
    assert found and found[0].rule == "AD019"
    assert found[0].observed and found[0].threshold
