from accesscast.render_stage import timeline_items
from tests.unit.conftest import make_item


def test_source_timeline_keeps_only_lines_voiced_without_a_pause():
    std = make_item("A narrow alleyway.")
    ext = make_item("A bald man raises a long blade above his head.", extended=True)
    assert timeline_items([std, ext], extended_timeline=False) == [std]


def test_extended_timeline_keeps_every_line():
    std = make_item("A narrow alleyway.")
    ext = make_item("A bald man raises a long blade above his head.", extended=True)
    assert timeline_items([std, ext], extended_timeline=True) == [std, ext]


def test_project_versions_leave_out_stages_that_never_ran():
    from accesscast.render_stage import project_versions
    from accesscast.schemas import ItemKind

    said = make_item("Hello.", id="sdh.en.0001", kind=ItemKind.SDH, lang="en", audiences=["deaf"])
    sub_it = make_item("Ciao.", id="subs.it.0001", kind=ItemKind.SUBTITLE, lang="it", audiences=["it"])
    have = project_versions({"sdh.en.0001": said, "subs.it.0001": sub_it})
    assert "it" in have and "es" not in have and "fr" not in have and "blind.hi" not in have
    sub_es = make_item("Hola.", id="subs.es.0001", kind=ItemKind.SUBTITLE, lang="es", audiences=["es"])
    assert "es" in project_versions({"sdh.en.0001": said, "subs.it.0001": sub_it, "subs.es.0001": sub_es})


def test_a_video_without_speech_has_no_easy_read_or_language_versions_to_wait_for():
    from accesscast.render_stage import project_versions
    from accesscast.schemas import ItemKind

    ad = make_item(
        "A small grey moon circles the Earth.",
        id="ad.en.0001",
        kind=ItemKind.AD,
        lang="en",
        audiences=["blind"],
    )
    music = make_item("[music]", id="sdh.en.0001", kind=ItemKind.SDH, lang="en", audiences=["deaf"])
    music = music.model_copy(update={"flags": ["sound_tag"]})
    have = project_versions({"ad.en.0001": ad, "sdh.en.0001": music})
    assert "blind.en" in have and "deaf.en" in have
    assert not {"easy.en", "hi", "it", "es", "fr", "pt"} & set(have)
    # with speech, the caption-derived versions are expected again (and block review if their lines are missing)
    said = make_item("Hello.", id="sdh.en.0002", kind=ItemKind.SDH, lang="en", audiences=["deaf"])
    assert {"easy.en", "hi", "it"} <= set(project_versions({"ad.en.0001": ad, "sdh.en.0002": said}))
