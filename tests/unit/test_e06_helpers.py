import json
from pathlib import Path

import pytest
from eval.e04_translation import Cue
from eval.e06_questions import (
    earliest_accesscast_output,
    load_question_file,
    parse_ts,
    questions_fresh,
    record_lines,
    validate_questions,
)

from accesscast.errors import ConfigError

GOOD = {
    "video_id": "v1",
    "written_by": "A. Person",
    "written_at": "2026-10-17T09:30:00+05:30",
    "questions": [
        {"q": "What colour is the wall?", "options": ["Red", "Blue", "Green", "White"], "answer_index": 2}
    ],
}


def test_valid_question_file_has_no_problems():
    assert validate_questions(GOOD, "v1") == []


@pytest.mark.parametrize(
    "change, needle",
    [
        ({"written_by": ""}, "written_by"),
        ({"written_at": "2026-10-17T09:30:00"}, "time zone"),
        ({"video_id": "other"}, "video_id"),
        ({"questions": [{"q": "x", "options": ["a", "b", "c"], "answer_index": 0}]}, "4"),
        ({"questions": [{"q": "x", "options": ["a", "b", "c", "d"], "answer_index": 4}]}, "answer_index"),
        ({"questions": [{"q": "x", "options": ["a", "a", "c", "d"], "answer_index": 0}]}, "same"),
    ],
)
def test_bad_question_files_are_reported(change, needle):
    errs = validate_questions({**GOOD, **change}, "v1")
    assert errs and any(needle in e for e in errs)


def test_freshness_uses_the_earliest_relevant_output():
    runs = [
        {"ts": "2026-10-18T05:00:00Z", "experiment": "e01_verifier_ab"},
        {"ts": "2026-10-17T03:00:00Z", "experiment": "e15", "videos": ["v2"]},
    ]
    first = earliest_accesscast_output("v1", runs, None)
    assert first == parse_ts("2026-10-18T05:00:00Z")  # the v2-only run does not count for v1
    assert earliest_accesscast_output("v2", runs, None) == parse_ts("2026-10-17T03:00:00Z")
    assert earliest_accesscast_output("v1", runs, "2026-10-16T00:00:00Z") == parse_ts("2026-10-16T00:00:00Z")
    assert earliest_accesscast_output("v1", [], None) is None


def test_questions_must_be_strictly_earlier():
    first = parse_ts("2026-10-18T05:00:00Z")
    assert questions_fresh("2026-10-18T10:29:59+05:30", first)  # 04:59:59 UTC
    assert not questions_fresh("2026-10-18T10:30:00+05:30", first)  # same instant
    assert not questions_fresh("2026-10-19T00:00:00Z", first)
    assert questions_fresh("2026-10-19T00:00:00Z", None)


def test_load_question_file_refuses_late_questions(tmp_path: Path):
    (tmp_path / "v1.json").write_text(json.dumps(GOOD))
    runs = [{"ts": "2026-10-17T00:00:00Z"}]  # before the questions were written (03:00 UTC on the 17th)
    with pytest.raises(ConfigError, match="refusing E6"):
        load_question_file("v1", test_runs=runs, created_at=None, qdir=tmp_path)
    ok = load_question_file("v1", test_runs=[{"ts": "2026-10-18T00:00:00Z"}], created_at=None, qdir=tmp_path)
    assert ok["video_id"] == "v1"
    with pytest.raises(ConfigError, match="no question file"):
        load_question_file("v9", test_runs=[], created_at=None, qdir=tmp_path)


def test_record_lines_merge_in_time_order_with_one_label():
    dia = [Cue(0, 900, "Hello."), Cue(5000, 6000, "Bye.")]
    lines = record_lines(dia, [(2000, "A man  waves."), (7000, " ")])
    assert lines == [
        "[0:00] Speech: Hello.",
        "[0:02] Visual description: A man waves.",
        "[0:05] Speech: Bye.",
    ]
    assert record_lines(dia, None) == ["[0:00] Speech: Hello.", "[0:05] Speech: Bye."]
