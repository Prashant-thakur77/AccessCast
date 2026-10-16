from accesscast.analysis.sound_labels import label_from_audioset


def test_most_likely_mapped_class_wins():
    assert label_from_audioset([("Music", 0.6), ("Applause", 0.3)]) == "music"
    assert label_from_audioset([("Applause", 0.7), ("Music", 0.2)]) == "applause"


def test_speech_and_singing_fail_closed_even_when_less_likely():
    assert label_from_audioset([("Music", 0.8), ("Singing", 0.2)]) == "music_with_lyrics"
    assert label_from_audioset([("Music", 0.8), ("Speech", 0.2), ("Singing", 0.3)]) == "unknown"


def test_below_threshold_or_unmapped_is_other():
    assert label_from_audioset([("Music", 0.05)]) == "other"
    assert label_from_audioset([("Wind", 0.9)]) == "other"
