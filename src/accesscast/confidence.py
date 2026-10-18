"""Confidence computed in code from measured signals (PLAN §11.2). Never asked of the model.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from accesscast import constants as C
from accesscast.errors import LlmOutputError

FORBIDDEN_MODEL_KEYS = frozenset({"confidence", "confidence_score", "conf", "certainty", "probability"})


def reject_model_confidence(obj: Mapping[str, Any]) -> None:
    """Fail closed if a model output tries to report its own confidence, at any depth."""
    stack: list[Any] = [obj]
    while stack:
        cur = stack.pop()
        if isinstance(cur, Mapping):
            bad = FORBIDDEN_MODEL_KEYS & {str(k).lower() for k in cur}
            if bad:
                raise LlmOutputError(f"model output contains a confidence field: {sorted(bad)}")
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)


def clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


def compute(
    *,
    grounding: float,
    slack_ms: float | None,
    asr_probs: Sequence[float],
    asr_disagreement: bool,
    ocr_disagrees: bool,
    repairs_used: int,
    warnings_count: int,
) -> tuple[float, dict[str, float]]:
    """confidence = clip01(grounding × slack × asr × ocr − 0.10·repairs − 0.05·warnings)."""
    slack = 1.0 if slack_ms is None else clip01(slack_ms / C.CONF_SLACK_FULL_MS)
    asr = (sum(asr_probs) / len(asr_probs)) if asr_probs else 1.0
    if asr_disagreement:
        asr *= C.CONF_ASR_DISAGREE_FACTOR
    ocr = C.CONF_OCR_DISAGREE_FACTOR if ocr_disagrees else 1.0
    rep = -C.CONF_REPAIR_PENALTY * repairs_used
    warn = -C.CONF_WARNING_PENALTY * warnings_count
    value = clip01(grounding * slack * asr * ocr + rep + warn)
    terms = {
        "grounding": round(grounding, 4),
        "slack": round(slack, 4),
        "asr": round(asr, 4),
        "ocr": round(ocr, 4),
        "repairs": round(rep, 4),
        "warnings": round(warn, 4),
    }
    return round(value, 4), terms
