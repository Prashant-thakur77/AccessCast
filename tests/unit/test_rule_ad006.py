from accesscast.verify.rules_ad import ad006_non_monotonic
from tests.unit.conftest import make_item


def test_ad006_passes(ctx):
    a = make_item("The woman presses Tab.", id="ad.en.0001", anchor_ms=2100)
    b = make_item("A dog opens its mouth.", id="ad.en.0002", anchor_ms=6000)
    ctx.other_items = [a, b]
    assert ad006_non_monotonic(a, ctx) == []


def test_ad006_fails_on_overlap(ctx):
    a = make_item("The woman presses Tab on a laptop in the office.", id="ad.en.0001", anchor_ms=2100)
    b = make_item("A dog opens its mouth.", id="ad.en.0002", anchor_ms=2600)
    ctx.other_items = [a, b]
    found = ad006_non_monotonic(a, ctx)
    assert found and found[0].rule == "AD006"
