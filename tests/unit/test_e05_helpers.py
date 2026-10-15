from eval.e05_easyread import (
    blind_sheet,
    gulpease,
    negation_count,
    negations_kept,
    numbers,
    numbers_kept,
    words_per_sentence,
    wpm,
)


def test_numbers_normalise_words_and_digits():
    assert numbers("Press it three times, then 20 more.") == numbers("Press it 3 times. Then twenty more.")
    assert numbers("It costs 1,200 dollars") == numbers("It costs 1200 dollars")


def test_numbers_kept_passes_and_fails():
    assert numbers_kept("Wait 5 seconds and press two keys.", "Wait 5 seconds. Press 2 keys.")
    assert not numbers_kept("Wait 5 seconds.", "Wait a few seconds.")
    assert not numbers_kept("Wait 15 seconds.", "Wait 5 seconds.")


def test_one_is_not_read_as_a_number():
    assert numbers("No one uses the mouse.") == numbers("Nobody uses the mouse.")


def test_negations_kept_passes_and_fails():
    assert negations_kept("She does not use a mouse.", "She doesn't use a mouse.")
    assert not negations_kept("She does not use a mouse.", "She uses a mouse.")
    assert not negations_kept("You can use it.", "You can never use it.")
    assert negation_count("Non è mai facile.", "it") == 2


def test_words_per_sentence_and_wpm():
    assert words_per_sentence("One two three. Four five!") == 2.5
    assert words_per_sentence("") is None
    assert wpm("one two three four", 2000) == 120


def test_gulpease_is_higher_for_shorter_words_and_sentences():
    easy = gulpease("Il gatto mangia. Il cane dorme.")
    hard = gulpease("L'amministrazione comunale predispone le opportune comunicazioni istituzionali.")
    assert easy is not None and hard is not None and easy > hard
    assert gulpease("") is None


def test_blind_sheet_hides_the_arm_and_pairs_cues():
    rows = [
        {
            "video": "v",
            "cue": f"c{i}",
            "source": f"s{i}",
            "gemma_alone": f"g{i}",
            "accesscast": f"a{i}",
            "published": True,
        }
        for i in range(40)
    ]
    sheet, key = blind_sheet(rows, 30, seed=5)
    assert len(sheet) == 60 and len(key) == 60
    assert all("arm" not in r for r in sheet)
    assert set(sheet[0]) == {"row", "original", "rewrite", "easier_to_read (1-5)", "same_meaning (yes/no)"}
    cues = {}
    for k in key:
        cues.setdefault(k["cue"], set()).add(k["arm"])
    assert len(cues) == 30 and all(v == {"gemma_alone", "accesscast"} for v in cues.values())
    assert blind_sheet(rows, 30, seed=5) == (sheet, key)
