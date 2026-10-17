"""Every language a stage writes is loaded for review and render (Spanish, French and Portuguese were once left out:
the review store read a fixed list of files, so their lines never reached the gate or a render)."""

from accesscast import constants as C
from accesscast.review.store import ITEM_FILES
from accesscast.review.studio import ITEM_FILES as STUDIO_FILES


def test_every_translation_language_is_loaded() -> None:
    for lang in C.TRANSLATION_LANGS:
        assert f"subs.{lang}" in ITEM_FILES
        assert f"vo.{lang}" in ITEM_FILES
    for lang in C.AD_TRANSLATION_LANGS:
        assert f"ad.{lang}" in ITEM_FILES
    assert {"ad.en", "sdh.en", "easy.en"} <= set(ITEM_FILES)


def test_studio_shows_every_subtitle_language() -> None:
    for lang in C.TRANSLATION_LANGS:
        assert f"subs.{lang}" in STUDIO_FILES
