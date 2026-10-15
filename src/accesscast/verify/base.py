"""Verifier contract (PLAN §10.1).

Rules are small pure functions `rule(item, ctx) -> list[Finding]`. No network, no model calls.
Any exception inside a rule becomes an error finding VERIFIER_CRASH on that item (fail closed).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Literal

from accesscast.schemas import (
    FindingModel,
    Gap,
    Item,
    SceneEvidence,
    Scenes,
    SoundEvent,
    VadSegment,
    Word,
)

Severity = Literal["error", "warning"]


@dataclass(frozen=True)
class Finding:
    rule: str
    severity: Severity
    observed: str
    threshold: str
    message: str
    owner_stage: str
    repairable: bool = True

    def to_model(self) -> FindingModel:
        return FindingModel(
            rule=self.rule,
            severity=self.severity,
            observed=self.observed,
            threshold=self.threshold,
            message=self.message,
            owner_stage=self.owner_stage,
            repairable=self.repairable,
        )


@dataclass(frozen=True)
class VerificationResult:
    ok: bool
    violations: list[Finding]
    warnings: list[Finding]

    @property
    def rules(self) -> list[str]:
        return [f.rule for f in self.violations]

    @property
    def all_repairable(self) -> bool:
        return all(f.repairable for f in self.violations)


@dataclass
class VerifyContext:
    """Everything a rule may read. Built once per project from the analysis files."""

    lang: str = "en"
    words: list[Word] = field(default_factory=list)
    vad: list[VadSegment] = field(default_factory=list)
    gaps: dict[str, Gap] = field(default_factory=dict)
    scenes: Scenes | None = None
    evidence: dict[str, SceneEvidence] = field(default_factory=dict)
    sounds: list[SoundEvent] = field(default_factory=list)
    guard_ms: int = 120
    allowed_names: frozenset[str] = frozenset()
    glossary: frozenset[str] = frozenset()
    other_items: Sequence[Item] = ()  # sibling items of the same kind/lang (for monotonic checks)
    approved_english: dict[str, str] = field(default_factory=dict)  # for ad_translation
    fps: float = 30.0
    font_glyphs: frozenset[str] | None = None
    tts_duration_ms: int | None = None  # measured clip duration, when known
    wps_voice: float = 2.6
    is_reviewer_edit: bool = False

    def speech_spans(self) -> list[tuple[int, int]]:
        """Padded speech spans (words ∪ VAD), merged and sorted."""
        spans = [(w.start_ms - self.guard_ms, w.end_ms + self.guard_ms) for w in self.words]
        spans += [(s.start_ms - self.guard_ms, s.end_ms + self.guard_ms) for s in self.vad]
        spans.sort()
        merged: list[tuple[int, int]] = []
        for a, b in spans:
            if merged and a <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], b))
            else:
                merged.append((a, b))
        return merged

    def dialogue_text(self, start_ms: int, end_ms: int) -> str:
        return " ".join(w.w for w in self.words if w.end_ms >= start_ms and w.start_ms <= end_ms)


Rule = Callable[[Item, VerifyContext], list[Finding]]


def crash_finding(rule_name: str, exc: BaseException) -> Finding:
    return Finding(
        rule="VERIFIER_CRASH",
        severity="error",
        observed=f"{rule_name}: {type(exc).__name__}",
        threshold="no exception",
        message="A check could not run, so this line is blocked until a person looks at it.",
        owner_stage="verify",
        repairable=False,
    )


def run_rules(item: Item, ctx: VerifyContext, rules: Sequence[Rule]) -> VerificationResult:
    violations: list[Finding] = []
    warnings: list[Finding] = []
    for rule in rules:
        try:
            found = rule(item, ctx)
        except Exception as exc:  # fail closed: any crash blocks the item
            found = [crash_finding(getattr(rule, "__name__", "rule"), exc)]
        for f in found:
            (violations if f.severity == "error" else warnings).append(f)
    return VerificationResult(ok=not violations, violations=violations, warnings=warnings)


def fmt_s(ms: float) -> str:
    return f"{ms / 1000:.2f} s"
