from accesscast.schemas import Slot  # noqa: F401
from accesscast.verify.rules_ad import ad007_word_budget
from tests.unit.conftest import make_item


def test_ad007_word_budget_passes(ctx):
    assert [
        f
        for f in ad007_word_budget(make_item("The woman presses Tab on a laptop."), ctx)
        if f.rule == "AD007"
    ] == []


def test_ad007_word_budget_fails(ctx):
    found = ad007_word_budget(
        make_item("The woman with short grey hair presses the Tab key on a laptop again and again."), ctx
    )
    assert found and found[0].rule == "AD007"
    assert found[0].observed and found[0].threshold
