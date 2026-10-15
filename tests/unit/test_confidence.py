import pytest

from accesscast.confidence import compute, reject_model_confidence
from accesscast.errors import LlmOutputError


def test_confidence_formula():
    v, terms = compute(
        grounding=1.0,
        slack_ms=300,
        asr_probs=[1.0],
        asr_disagreement=False,
        ocr_disagrees=False,
        repairs_used=1,
        warnings_count=0,
    )
    assert v == pytest.approx(0.4) and terms["slack"] == 0.5


def test_model_may_not_report_confidence():
    with pytest.raises(LlmOutputError):
        reject_model_confidence({"items": [{"text": "x", "confidence": 0.9}]})
    reject_model_confidence({"items": [{"text": "x"}]})
