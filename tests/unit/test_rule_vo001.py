from accesscast.schemas import ItemKind, Slot
from accesscast.verify.rules_text import vo001_slot_overflow
from tests.unit.conftest import make_item


def _item(**kw):
    base = dict(
        kind=ItemKind.VOICEOVER,
        lang="it",
        budget=None,
        anchor_ms=0,
        slot=Slot(start_ms=0, end_ms=3000),
        source_text="Press the key.",
    )
    base.update(kw)
    return make_item(base.pop("draft"), **base)


def test_vo001_slot_overflow_passes(ctx):
    ctx.lang = "it"
    assert [f for f in vo001_slot_overflow(_item(draft="Premi il tasto."), ctx) if f.rule == "VO001"] == []


def test_vo001_slot_overflow_fails(ctx):
    ctx.lang = "it"
    found = vo001_slot_overflow(
        _item(
            draft="Premi il tasto rosso sul lato sinistro della tastiera tre volte adesso e poi aspetta un momento."
        ),
        ctx,
    )
    assert found and found[0].rule == "VO001"
