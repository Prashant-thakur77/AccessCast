from pathlib import Path

import pytest
from eval.e04_translation import flores_segments, paired_bootstrap, read_vtt_cues, sdh_items, winner


def test_paired_bootstrap_identical_systems_give_zero():
    r = paired_bootstrap([0.5, 0.6, 0.7], [0.5, 0.6, 0.7], n_boot=200, seed=1)
    assert r["diff"] == 0.0 and r["ci95_lo"] == 0.0 and r["ci95_hi"] == 0.0 and r["n"] == 3


def test_paired_bootstrap_constant_shift_is_exact_and_ordered():
    a = [0.1, 0.4, 0.2, 0.9]
    b = [x + 0.25 for x in a]
    r = paired_bootstrap(a, b, n_boot=500, seed=7)
    assert r["diff"] == pytest.approx(0.25)
    assert r["ci95_lo"] == pytest.approx(0.25) and r["ci95_hi"] == pytest.approx(0.25)


def test_paired_bootstrap_is_seeded_and_interval_contains_point():
    a, b = [0.1, 0.5, 0.3, 0.8, 0.2], [0.3, 0.4, 0.6, 0.9, 0.2]
    r1, r2 = paired_bootstrap(a, b, 300, 3), paired_bootstrap(a, b, 300, 3)
    assert r1 == r2
    assert r1["ci95_lo"] <= r1["diff"] <= r1["ci95_hi"]


def test_paired_bootstrap_refuses_unpaired_input():
    with pytest.raises(ValueError):
        paired_bootstrap([0.1, 0.2], [0.1])
    with pytest.raises(ValueError):
        paired_bootstrap([], [])


def test_winner_names_the_higher_system_and_flags_zero():
    assert winner(0.02, 0.01, 0.03, "base", "gemma") == {"higher": "gemma", "interval_includes_zero": False}
    assert winner(-0.02, -0.05, 0.01, "base", "gemma") == {"higher": "base", "interval_includes_zero": True}
    assert winner(0.0, -0.01, 0.01, "base", "gemma")["higher"] == "tie"


def test_flores_segments_never_bind_the_length_limit():
    segs = flores_segments(["Hello there.", "A much longer sentence about keyboards."], "hi")
    assert [s["id"] for s in segs] == [0, 1]
    assert all(s["chars_max"] == 3 * len(s["text"]) for s in segs)


def test_read_vtt_cues_strips_tags_and_joins_lines(tmp_path: Path):
    p = tmp_path / "x.vtt"
    p.write_text(
        "WEBVTT\n\n1\n00:00:01.000 --> 00:00:02.500\n<v Ana>Hello</v>\nworld\n\n"
        "00:01:00.000 --> 00:01:01.000\n[music]\n",
        encoding="utf-8",
    )
    cues = read_vtt_cues(p)
    assert [(c.start_ms, c.end_ms, c.text) for c in cues] == [
        (1000, 2500, "Hello world"),
        (60000, 61000, "[music]"),
    ]
    items = sdh_items(cues)
    assert items[0].slot.start_ms == 1000 and items[0].text == "Hello world" and items[1].id == "sdh.en.0002"
