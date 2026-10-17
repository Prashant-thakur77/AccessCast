from accesscast.captions.vtt import ts, write_vtt
from tests.unit.conftest import make_item


def test_held_line_uses_its_output_window(tmp_path):
    held = make_item("A square image of a star-filled black void.", extended=True)
    p = tmp_path / "d.vtt"
    write_vtt(p, [held], remap=lambda ms: ms + 5000, end_of=lambda it: 9999, span_of=lambda it: (100, 3133))
    assert "00:00:00.100 --> 00:00:03.133" in p.read_text()


def test_line_without_span_is_remapped(tmp_path):
    std = make_item("The planets exit the frame.")
    p = tmp_path / "d.vtt"
    write_vtt(
        p, [std], remap=lambda ms: ms + 1000, end_of=lambda it: it.anchor_ms + 2000, span_of=lambda it: None
    )
    assert f"{ts(std.anchor_ms + 1000)} --> {ts(std.anchor_ms + 3000)}" in p.read_text()
