import pytest
from fastapi import HTTPException

from accesscast import constants as C
from accesscast.proof.api import words_from_text


def test_words_are_timed_at_a_speaking_pace_with_a_pause_after_a_sentence():
    ws = words_from_text("Do not press it. Wait here.")
    assert [w.w for w in ws] == ["Do", "not", "press", "it.", "Wait", "here."]
    assert ws[1].start_ms - ws[0].start_ms == C.TRY_MS_PER_WORD
    assert ws[4].start_ms - ws[3].start_ms == C.TRY_MS_PER_WORD + 300


@pytest.mark.parametrize("text", ["", "two words", "x" * (C.TRY_MAX_CHARS + 1), "bad\x00 control char here"])
def test_bad_input_is_refused_before_any_model_call(text):
    with pytest.raises(HTTPException) as e:
        words_from_text(text)
    assert e.value.status_code == 422
