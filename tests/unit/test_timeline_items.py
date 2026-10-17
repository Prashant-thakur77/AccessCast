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
