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


def test_ad011_sound_word_printed_on_screen_is_visible_text(ctx):
    from accesscast.schemas import OnScreenText
    from tests.unit.conftest import make_evidence

    ctx.evidence = {
        "SC001": make_evidence(on_screen_text=[OnScreenText(text="Display Sound Privacy", frame=0)])
    }
    item = make_item("A settings menu shows Display, Sound and Privacy.", fact_ids=["F002"])
    assert ad011_sound(item, ctx) == []
    # an invented sound is still caught even when the screen shows the word "Sound"
    assert ad011_sound(make_item("A dog barks loudly.", fact_ids=["F002"]), ctx)
