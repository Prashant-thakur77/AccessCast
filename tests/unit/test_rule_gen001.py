from accesscast.schemas import ItemKind, Slot
from accesscast.verify.rules_text import gen001_empty_or_failed
from tests.unit.conftest import make_item


def _vo(text: str, **kw):
    return make_item(text, kind=ItemKind.VOICEOVER, lang="it", budget=None, anchor_ms=0,
                     slot=Slot(start_ms=0, end_ms=3000), **kw)


def test_gen001_passes(ctx):
    assert gen001_empty_or_failed(_vo("Premete il tasto."), ctx) == []


def test_gen001_blocks_empty_and_failed(ctx):
    assert gen001_empty_or_failed(_vo(""), ctx)[0].rule == "GEN001"
    assert gen001_empty_or_failed(_vo("Ciao.", flags=["misaligned:missing"]), ctx)[0].rule == "GEN001"
