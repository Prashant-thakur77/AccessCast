from accesscast.schemas import Slot
from accesscast.verify.rules_ad import ad004_overlaps_speech
from tests.unit.conftest import make_item


def test_ad004_overlaps_speech_passes(ctx):
    assert [
        f
        for f in ad004_overlaps_speech(make_item("The woman presses Tab on a laptop."), ctx)
        if f.rule == "AD004"
    ] == []


def test_ad004_overlaps_speech_fails(ctx):
    found = ad004_overlaps_speech(
        make_item(
            "The woman presses Tab on a laptop and then " + "types more text " * 8,
            slot=Slot(start_ms=2100, end_ms=20000),
            budget=None,
        ),
        ctx,
    )
    assert found and found[0].rule == "AD004"
    assert found[0].observed and found[0].threshold
