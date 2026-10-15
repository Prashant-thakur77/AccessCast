from accesscast.schemas import Slot  # noqa: F401
from accesscast.verify.rules_ad import ad017_emotion_inferred
from tests.unit.conftest import make_item


def test_ad017_emotion_inferred_passes(ctx):
    assert [
        f
        for f in ad017_emotion_inferred(make_item("The woman presses Tab on a laptop."), ctx)
        if f.rule == "AD017"
    ] == []


def test_ad017_emotion_inferred_fails(ctx):
    found = ad017_emotion_inferred(make_item("The frustrated woman presses Tab on a laptop."), ctx)
    assert found and found[0].rule == "AD017"
    assert found[0].observed and found[0].threshold
