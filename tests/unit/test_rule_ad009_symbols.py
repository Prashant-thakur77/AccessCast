from accesscast.verify.rules_ad import ad009_invented_name
from tests.unit.conftest import make_item


def test_key_names_and_symbols_are_not_names(ctx):
    for text in ("We see the screen showing Ctrl + C.", "She presses Ctrl and C."):
        assert ad009_invented_name(make_item(text), ctx) == [] or \
            all(f.observed not in ("name '+'", "name 'C.'") for f in ad009_invented_name(make_item(text), ctx))


def test_real_invented_name_still_fires(ctx):
    found = ad009_invented_name(make_item("Sarah presses Ctrl + C."), ctx)
    assert found and "Sarah" in found[0].observed
