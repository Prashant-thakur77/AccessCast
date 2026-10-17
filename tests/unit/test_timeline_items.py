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

    sub_it = make_item("Ciao.", id="subs.it.0001", kind=ItemKind.SUBTITLE, lang="it", audiences=["it"])
    have = project_versions({"subs.it.0001": sub_it})
    assert "it" in have and "es" not in have and "fr" not in have and "blind.hi" not in have
    sub_es = make_item("Hola.", id="subs.es.0001", kind=ItemKind.SUBTITLE, lang="es", audiences=["es"])
    assert "es" in project_versions({"subs.it.0001": sub_it, "subs.es.0001": sub_es})
