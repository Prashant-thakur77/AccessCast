from accesscast.schemas import Slot  # noqa: F401
from accesscast.verify.rules_ad import ad010_unsupported_claim
from tests.unit.conftest import make_item


def test_ad010_unsupported_claim_passes(ctx):
    assert [
        f
        for f in ad010_unsupported_claim(make_item("The woman presses Tab on a laptop."), ctx)
        if f.rule == "AD010"
    ] == []


def test_ad010_unsupported_claim_fails(ctx):
    found = ad010_unsupported_claim(make_item("A web developer presses Tab because she tests the site."), ctx)
    assert found and found[0].rule == "AD010"
    assert found[0].observed and found[0].threshold
