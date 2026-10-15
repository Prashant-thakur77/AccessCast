import pytest
from eval.e07_similarity import cider_d, pair_lines, timing_agreement


def test_timing_agreement_counts_human_cues_within_window():
    assert timing_agreement([1000, 10_000, 20_000], [3500, 13_001, 19_000]) == (2, 3)
    assert timing_agreement([1000], [4000]) == (1, 1)  # exactly 3 s is inside
    assert timing_agreement([1000], []) == (0, 1)
    assert timing_agreement([], [1000]) == (0, 0)


def test_pair_lines_joins_nearby_lines_and_leaves_gaps_empty():
    human = [(1000, "A man waves."), (20_000, "A door closes.")]
    ours = [(2500, "He  waves."), (500, "A man stands."), (9000, "Far away.")]
    assert pair_lines(human, ours) == [
        (0, "A man waves.", "A man stands. He waves."),
        (1, "A door closes.", ""),
    ]


REFS = [
    ["a man types on a laptop"],
    ["a woman reads a book on a sofa"],
    ["two people talk in an office"],
    ["a dog runs on the beach"],
]


def test_cider_d_exact_match_beats_paraphrase_and_unrelated():
    exact = cider_d(["a man types on a laptop", *[r[0] for r in REFS[1:]]], REFS)[0]
    para = cider_d(["a man is typing on his laptop", *[r[0] for r in REFS[1:]]], REFS)[0]
    other = cider_d(["the sky is blue", *[r[0] for r in REFS[1:]]], REFS)[0]
    assert exact > para > other == 0.0


def test_cider_d_basic_properties():
    assert cider_d([], []) == []
    assert cider_d(["", "x"], [["a b"], ["c d"]])[0] == 0.0
    s = cider_d(["a man types on a laptop"] * 4, REFS)
    assert all(x >= 0 for x in s)
    with pytest.raises(ValueError):
        cider_d(["a"], [])


def test_cider_d_length_penalty_lowers_padded_candidates():
    base = [r[0] for r in REFS]
    padded = ["a man types on a laptop " + "very " * 10, *base[1:]]
    assert cider_d(padded, REFS)[0] < cider_d(base, REFS)[0]
