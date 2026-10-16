from accesscast.analysis.speakers import assign_speakers
from tests.unit.conftest import make_words


def test_words_take_the_most_overlapping_turn_and_untouched_words_stay_unlabelled():
    words = make_words([("hello", 0, 400), ("there", 450, 900), ("yes", 1500, 1800), ("hm", 5000, 5100)])
    turns = [
        {"start_ms": 0, "end_ms": 1000, "speaker": "S1"},
        {"start_ms": 800, "end_ms": 2000, "speaker": "S2"},
    ]
    out = assign_speakers(words, turns)
    assert [w.speaker for w in out] == ["S1", "S1", "S2", None]
