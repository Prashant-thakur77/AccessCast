from accesscast.verify.rules_ad import ad020_backtranslation_drift
from tests.unit.conftest import make_item


def test_ad020_passes(ctx):
    assert ad020_backtranslation_drift(make_item("x y", flags=["bt_cos=0.91"]), ctx) == []


def test_ad020_warns_never_blocks(ctx):
    found = ad020_backtranslation_drift(make_item("x y", flags=["bt_cos=0.40"]), ctx)
    assert found and found[0].severity == "warning"
