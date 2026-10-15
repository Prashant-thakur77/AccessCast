from accesscast.schemas import ItemKind, Slot  # noqa: F401
from accesscast.verify.rules_text import cc001_cps
from tests.unit.conftest import make_item


def _item(**kw):
    base = dict(kind=ItemKind.SUBTITLE, lang="it", budget=None, anchor_ms=0, slot=Slot(start_ms=0, end_ms=3000), source_text='Press the key.')
    base.update(kw)
    return make_item(base.pop("draft"), **base)


def test_cc001_cps_passes(ctx):
    ctx.lang = "it"
    assert [f for f in cc001_cps(_item(draft="Premi il tasto."), ctx) if f.rule == "CC001"] == []


def test_cc001_cps_fails(ctx):
    ctx.lang = "it"
    found = cc001_cps(_item(draft="Premi il tasto rosso sul lato sinistro della tastiera adesso per favore."), ctx)
    assert found and found[0].rule == "CC001"
