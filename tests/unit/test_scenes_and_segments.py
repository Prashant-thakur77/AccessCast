from accesscast.analysis.scenes import decide_boundary, dialogue_bridges
from accesscast.captions.segment import segment_sdh
from tests.unit.conftest import make_words


def test_boundary_decisions():
    assert decide_boundary(0.95, False).merge is True
    assert decide_boundary(0.85, True).reason == "VISUALLY_SIMILAR_DIALOGUE_CONTINUES"
    assert decide_boundary(0.30, False).merge is False
    assert decide_boundary(0.60, False).merge is None


def test_dialogue_bridge():
    w = make_words([("a", 0, 900), ("b", 1500, 1800)])
    assert dialogue_bridges(w, 1000)
    assert not dialogue_bridges(make_words([("a", 0, 500), ("b", 3000, 3300)]), 1000)


def test_sdh_cues_respect_layout_and_sync():
    words = make_words(
        [
            (w, 100 + i * 300, 350 + i * 300)
            for i, w in enumerate(
                [
                    "this",
                    "is",
                    "a",
                    "fairly",
                    "long",
                    "sentence",
                    "that",
                    "should",
                    "be",
                    "split",
                    "into",
                    "readable",
                    "caption",
                    "lines",
                    "for",
                    "viewers.",
                ]
            )
        ]
    )
    cues = segment_sdh(words, [], 30.0, 10_000)
    for c in cues:
        assert all(len(line) <= 42 for line in c.text.split("\n"))
        assert len(c.text.split("\n")) <= 2
    assert cues[0].slot.start_ms == words[0].start_ms
