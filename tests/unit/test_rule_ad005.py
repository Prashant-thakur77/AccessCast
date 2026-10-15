from accesscast.schemas import Slot  # noqa: F401
from accesscast.verify.rules_ad import ad005_anchor_far_from_event
from tests.unit.conftest import make_item


def test_ad005_anchor_far_from_event_passes(ctx):
    assert [
        f
        for f in ad005_anchor_far_from_event(make_item("The woman presses Tab on a laptop."), ctx)
        if f.rule == "AD005"
    ] == []


def test_ad005_anchor_far_from_event_fails(ctx):
    found = ad005_anchor_far_from_event(
        make_item("The woman presses Tab on a laptop.", fact_ids=["F999"]), ctx
    )
    assert found and found[0].rule == "AD005"
    assert found[0].observed and found[0].threshold
