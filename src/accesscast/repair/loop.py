# The verifier → feedback → revise loop follows the shape of ProteinLoop's
# sim/proteinloop_sim/gemma_repair.py (https://github.com/Anarpego/ProteinLoop),
# MIT License, Copyright (c) 2026 Anibal Perez. Rewritten for AccessCast items; prompt text is our own.
"""Repair loop (PLAN §11.1): verify → feedback → Gemma revises (≤3) → never promote a failure."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from accesscast import constants as C
from accesscast.verify.base import Finding, VerificationResult

# Stop reasons (logged per item)
SAFE_INITIAL = "safe_initial_proposal"
SAFE_REVISION = "safe_model_revision"
LIMIT_REACHED = "repair_limit_reached"
GENERATION_FAILED = "revision_generation_failed"
NON_REPAIRABLE = "non_repairable"


@dataclass
class Attempt:
    attempt: int
    text: str
    rules: list[str]


@dataclass
class RepairOutcome:
    text: str
    ok: bool
    stop_reason: str
    attempts: int
    history: list[Attempt] = field(default_factory=list)
    final_result: VerificationResult | None = None
    fact_ids: list[str] = field(default_factory=list)


Verify = Callable[[str, list[str]], VerificationResult]
Revise = Callable[[int, str, list[Finding]], tuple[str, list[str]]]


def feedback_violations(result: VerificationResult) -> list[dict[str, str]]:
    return [
        {"rule": f.rule, "observed": f.observed, "threshold": f.threshold, "message": f.message}
        for f in result.violations
    ]


def run_repair_loop(
    draft: str,
    fact_ids: list[str],
    verify: Verify,
    revise: Revise,
    *,
    max_attempts: int = C.REPAIR_MAX_ATTEMPTS,
    enabled: bool = True,
) -> RepairOutcome:
    """`verify(text, fact_ids)` runs the rules; `revise(k, text, violations)` asks Gemma for attempt k.

    With `enabled=False` (E1 arm B) a failing draft is not repaired; it goes to a person.
    """
    text, facts = draft, list(fact_ids)
    res = verify(text, facts)
    history = [Attempt(0, text, res.rules)]
    if res.ok:
        return RepairOutcome(text, True, SAFE_INITIAL, 0, history, res, facts)
    if not enabled:
        return RepairOutcome(text, False, LIMIT_REACHED, 0, history, res, facts)
    if not res.all_repairable:
        return RepairOutcome(text, False, NON_REPAIRABLE, 0, history, res, facts)
    for k in range(1, max_attempts + 1):
        try:
            new_text, new_facts = revise(k, text, res.violations)
        except Exception:
            return RepairOutcome(text, False, GENERATION_FAILED, k, history, res, facts)
        text, facts = new_text, new_facts or facts
        res = verify(text, facts)
        history.append(Attempt(k, text, res.rules))
        if res.ok:
            return RepairOutcome(text, True, SAFE_REVISION, k, history, res, facts)
        if not res.all_repairable:
            return RepairOutcome(text, False, NON_REPAIRABLE, k, history, res, facts)
    return RepairOutcome(text, False, LIMIT_REACHED, max_attempts, history, res, facts)
