from accesscast.analysis.gaps import build_gaps
from accesscast.schemas import Scene, SoundEvent, VadSegment
from tests.unit.conftest import make_words

SCENES = [Scene(scene_id="SC001", start_ms=0, end_ms=20000, shots=["SH001"])]


def test_gap_between_words_and_at_ends():
    words = make_words([("a", 3000, 3500), ("b", 3600, 4000), ("c", 9000, 9500)])
    g = build_gaps(words, [], [], SCENES, 12000, guard_ms=120, min_gap_ms=1200)
    spans = [(x.start_ms, x.end_ms) for x in g.gaps]
    assert spans == [(0, 2880), (4120, 8880), (9620, 12000)]
    assert g.gaps[1].prev_word_i == 1 and g.gaps[1].next_word_i == 2


def test_overlapping_words_and_vad_only_speech():
    words = make_words([("a", 1000, 2000), ("b", 1500, 2500)])
    vad = [VadSegment(start_ms=5000, end_ms=6000)]
    g = build_gaps(words, vad, [], SCENES, 8000, guard_ms=100, min_gap_ms=1200)
    assert [(x.start_ms, x.end_ms) for x in g.gaps] == [(2600, 4900), (6100, 8000)]


def test_short_gaps_dropped_and_lyrics_count_as_speech():
    words = make_words([("a", 0, 1000), ("b", 1800, 2000)])
    lyrics = [SoundEvent(start_ms=2500, end_ms=6000, label="music_with_lyrics")]
    g = build_gaps(words, [], lyrics, SCENES, 7000, guard_ms=100, min_gap_ms=1200)
    assert [(x.start_ms, x.end_ms) for x in g.gaps] == []


def test_under_label_from_sounds():
    music = [SoundEvent(start_ms=0, end_ms=5000, label="music")]
    g = build_gaps([], [], music, SCENES, 5000, guard_ms=100, min_gap_ms=1200)
    assert g.gaps[0].under == "music_no_lyrics"
