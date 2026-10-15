from accesscast.verify.rules_ad import ad016_wrong_language
from tests.unit.conftest import make_item


def test_ad016_hindi_passes(ctx):
    ctx.lang = "hi"
    assert ad016_wrong_language(make_item("महिला लैपटॉप पर टैब दबाती है।", lang="hi"), ctx) == []


def test_ad016_hindi_fails_on_english(ctx):
    ctx.lang = "hi"
    found = ad016_wrong_language(make_item("The woman presses Tab.", lang="hi"), ctx)
    assert found and found[0].rule == "AD016"
