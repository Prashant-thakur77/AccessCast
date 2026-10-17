from accesscast.captions.segment import segment_sdh
from tests.unit.conftest import make_words


def test_split_thousands_are_joined_in_the_caption():
    words = make_words(
        [
            ("There", 0, 200),
            ("are", 200, 400),
            ("nearly", 400, 800),
            ("10", 800, 1000),
            (",000", 1000, 1300),
            ("galaxies.", 1300, 1900),
        ]
    )
    cues = segment_sdh(words, [], 25.0, 5000)
    assert cues[0].text == "There are nearly 10,000 galaxies."


def test_a_comma_after_a_word_is_left_alone():
    words = make_words([("Yes", 0, 300), (",so", 300, 600), ("go.", 600, 900)])
    assert segment_sdh(words, [], 25.0, 5000)[0].text == "Yes ,so go."
