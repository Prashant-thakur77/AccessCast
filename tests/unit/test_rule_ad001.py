from accesscast.schemas import Slot
from accesscast.verify.rules_ad import ad001_gap_overflow
from tests.unit.conftest import make_item


def test_ad001_gap_overflow_passes(ctx):
    assert [
        f
        for f in ad001_gap_overflow(make_item("The woman presses Tab on a laptop."), ctx)
        if f.rule == "AD001"
    ] == []


def test_ad001_gap_overflow_fails(ctx):
    found = ad001_gap_overflow(
        make_item(
            "The woman presses Tab on a laptop " + "and keeps typing " * 6,
            slot=Slot(start_ms=2100, end_ms=4000),
        ),
        ctx,
    )
    assert found and found[0].rule == "AD001"
    assert found[0].observed and found[0].threshold
