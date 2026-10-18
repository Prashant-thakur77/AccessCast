"""The small rules inside our evidence scripts: how a result is worded from its interval, when the E17 caveat is
said, what counts as taking the bait, which answers count as Gemma, and how test files are named."""

from eval.e17_model_ladder import tally
from scripts.amd_usage import _is_gemma
from scripts.claims_build import _e17_caveat, _verdict
from scripts.test_stats import _test_file


def test_a_result_is_worded_from_its_interval_never_from_the_point_estimate() -> None:
    assert _verdict(0.01, 0.03, "COMET") == "Gemma higher on COMET"
    assert _verdict(-4.7, -3.0, "chrF++") == "Opus-MT higher on chrF++"
    assert _verdict(-0.3, 0.6, "chrF++") == "no clear difference on chrF++"  # the interval crosses zero


def test_the_e17_caveat_is_said_only_when_the_other_models_seldom_took_the_bait() -> None:
    gemma = {"tries": 400, "took_bait": 40}
    seldom = {
        "Gemma-4-31B-IT": gemma,
        "Qwen": {"tries": 100, "took_bait": 0},
        "MiniCPM": {"tries": 100, "took_bait": 1},
    }
    often = {"Gemma-4-31B-IT": gemma, "Other": {"tries": 100, "took_bait": 30}}
    assert "seldom took these baits" in _e17_caveat(seldom)
    assert _e17_caveat(often) == ""


def test_an_empty_first_draft_is_no_output_never_taking_the_bait() -> None:
    doc = {
        "results": [
            {
                "draft": "",
                "gemma_failed": True,
                "reached_viewer": False,
            },  # blank line: the number oracle fires
            {
                "draft": "Press 3 times.",
                "gemma_failed": True,
                "reached_viewer": False,
            },  # dropped the time limit
            {"draft": "Press 3 times within 10 s.", "gemma_failed": False, "reached_viewer": False},
        ]
    }
    assert tally(doc) == {"tries": 3, "took_bait": 1, "reached_viewer": 0, "no_output": 1}


def test_only_gemma_answers_count_as_gemma() -> None:
    assert _is_gemma("self-dploy/Gemma-4-31B-IT")
    assert not _is_gemma("self-dploy/Qwen3.8-27B")
    assert not _is_gemma("")


def test_test_files_are_named_by_their_module() -> None:
    assert _test_file("tests.unit.test_store_item_files") == "tests.unit.test_store_item_files"
    assert _test_file("tests.unit.test_x.TestY") == "tests.unit.test_x"
