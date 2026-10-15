from accesscast.schemas import Slot  # noqa: F401
from accesscast.verify.rules_ad import ad011_sound
from tests.unit.conftest import make_item


def test_ad011_sound_passes(ctx):
    assert [
        f
        for f in ad011_sound(make_item("A dog opens its mouth wide.", fact_ids=["F002"]), ctx)
        if f.rule == "AD011"
    ] == []


def test_ad011_sound_fails(ctx):
    found = ad011_sound(make_item("A dog barks loudly.", fact_ids=["F002"]), ctx)
    assert found and found[0].rule == "AD011"
    assert found[0].observed and found[0].threshold
