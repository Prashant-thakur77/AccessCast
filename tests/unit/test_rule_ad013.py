from accesscast.schemas import OnScreenText
from accesscast.verify.rules_ad import ad013_onscreen_not_read
from tests.unit.conftest import make_evidence, make_item


def test_ad013_passes(ctx):
    item = make_item("On screen: Keyboard Compatibility.")
    assert ad013_onscreen_not_read(item, ctx) == []


def test_ad013_warns(ctx):
    ctx.evidence["SC001"] = make_evidence(
        on_screen_text=[OnScreenText(text="How people use the web", frame=0, kind="title", ocr_agrees=True)]
    )
    found = ad013_onscreen_not_read(make_item("The woman presses Tab on a laptop."), ctx)
    assert found and found[0].rule == "AD013" and found[0].severity == "warning"
