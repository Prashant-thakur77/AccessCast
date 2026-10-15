"""Data model (PLAN §8). Every file a stage writes validates against one of these models.

`accesscast schemas export` writes them as JSON Schema into docs/schemas/.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ------------------------------------------------------------------ analysis (§8.1)
class Word(Strict):
    i: int
    w: str
    start_ms: int
    end_ms: int
    prob: float = 1.0
    seg: int = 0
    speaker: str | None = None


class Words(Strict):
    lang: str
    model: str
    aligned: bool = False
    words: list[Word]


class VadSegment(Strict):
    start_ms: int
    end_ms: int


class Vad(Strict):
    model: str
    segments: list[VadSegment]


GapUnder = Literal["silence", "non_speech_sound", "music_no_lyrics"]


class Gap(Strict):
    gap_id: str
    start_ms: int
    end_ms: int
    len_ms: int
    scene_id: str | None = None
    prev_word_i: int | None = None
    next_word_i: int | None = None
    under: GapUnder = "silence"


class Gaps(Strict):
    guard_ms: int
    min_gap_ms: int
    gaps: list[Gap]


class Shot(Strict):
    shot_id: str
    start_ms: int
    end_ms: int


class Shots(Strict):
    detector: str
    shots: list[Shot]


class Scene(Strict):
    scene_id: str
    start_ms: int
    end_ms: int
    shots: list[str]
    boundary_reason: str = "START"
    boundary_similarity: float | None = None


class Scenes(Strict):
    scenes: list[Scene]


class SoundEvent(Strict):
    start_ms: int
    end_ms: int
    label: str
    source: Literal["model", "energy_gate"] = "model"


class Sounds(Strict):
    model: str
    events: list[SoundEvent]
    rejected_labels: list[str] = Field(default_factory=list)


class AsrChunkCheck(Strict):
    chunk: int
    start_ms: int
    end_ms: int
    wer: float | None
    disagreement: bool
    error: str | None = None


class AsrCrosscheck(Strict):
    model: str
    threshold: float
    chunks: list[AsrChunkCheck]


# ------------------------------------------------------------------ evidence (§8.2)
class ModelRef(Strict):
    name: str
    endpoint: str
    temperature: float
    seed: int | None = None
    prompt_id: str
    prompt_sha: str
    served_model_id: str | None = None


class Character(Strict):
    cid: str
    appearance: str
    name: str | None = None
    name_source: str | None = None


class VisibleFact(Strict):
    fid: str
    frames: list[int]
    text: str
    priority: int = 4  # 1 on-screen text … 5 finer detail (PLAN §9 S6)
    important: bool = False


class OnScreenText(Strict):
    text: str
    frame: int
    kind: str = "other"
    ocr_agrees: bool = False
    source: Literal["model", "ocr"] = "model"


class SceneEvidence(Strict):
    scene_id: str
    frames: list[str]
    frame_ms: list[int] = Field(default_factory=list)
    setting: str = ""
    characters: list[Character] = Field(default_factory=list)
    visible_facts: list[VisibleFact] = Field(default_factory=list)
    on_screen_text: list[OnScreenText] = Field(default_factory=list)
    inferences: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    status: Literal["ok", "evidence_failed"] = "ok"
    model: ModelRef | None = None


# ------------------------------------------------------------------ items (§8.3)
class ItemKind(StrEnum):
    AD = "ad"
    SDH = "sdh"
    EASY = "easy"
    SUBTITLE = "subtitle"
    VOICEOVER = "voiceover"
    AD_TRANSLATION = "ad_translation"


class ItemStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    AUTO_APPROVED = "auto_approved"
    REJECTED = "rejected"
    NEEDS_REVISION = "needs_revision"


class Slot(Strict):
    start_ms: int
    end_ms: int


class Budget(Strict):
    words_max: int
    seconds_max: float
    wps_voice: float


class FindingModel(Strict):
    rule: str
    severity: Literal["error", "warning"]
    observed: str
    threshold: str
    message: str
    owner_stage: str
    repairable: bool = True


class RepairStep(Strict):
    attempt: int
    text: str
    rules: list[str]


class RepairInfo(Strict):
    attempts: int = 0
    stop_reason: str = "safe_initial_proposal"
    history: list[RepairStep] = Field(default_factory=list)


class TtsInfo(Strict):
    voice: str
    speed: float = 1.0
    sha256: str
    duration_ms: int
    engine: str = "kokoro"


class Item(Strict):
    id: str
    kind: ItemKind
    lang: str
    audiences: list[str]
    scene_id: str | None = None
    gap_id: str | None = None
    anchor_ms: int
    slot: Slot
    budget: Budget | None = None
    fact_ids: list[str] = Field(default_factory=list)
    source_text: str | None = None  # for easy/subtitle/voiceover: the text it was derived from
    source_ids: list[str] = Field(default_factory=list)
    draft: str
    final: str | None = None
    status: ItemStatus = ItemStatus.PENDING
    source: Literal["auto", "manual"] = "auto"
    extended: bool = False
    needs_pause: bool = False
    flags: list[str] = Field(default_factory=list)
    violations: list[FindingModel] = Field(default_factory=list)
    warnings: list[FindingModel] = Field(default_factory=list)
    repair: RepairInfo = Field(default_factory=RepairInfo)
    tts: TtsInfo | None = None
    confidence: float | None = None
    confidence_terms: dict[str, float] = Field(default_factory=dict)
    model: ModelRef | None = None
    revision: int = 0
    reviewer: str | None = None
    reviewed_at: str | None = None
    reviewer_note: str = ""
    override_reason: str | None = None
    back_translation: str | None = None

    @property
    def text(self) -> str:
        return self.final if self.final is not None else self.draft


# ------------------------------------------------------------------ project
class ToolVersion(Strict):
    name: str
    version: str
    licence: str | None = None


class ProjectInfo(Strict):
    schema_version: str = "accesscast/project/v1"
    sha256: str
    sha12: str
    source_name: str
    duration_ms: int
    fps: float
    width: int
    height: int
    has_audio: bool
    created_at: str
    worker_mode: Literal["real", "fake"]
    project_seed: int
    settings: dict[str, Any] = Field(default_factory=dict)
    tools: list[ToolVersion] = Field(default_factory=list)
    models: list[ToolVersion] = Field(default_factory=list)


# ------------------------------------------------------------------ evidence files and claims
class EvidenceFile(BaseModel):
    model_config = ConfigDict(extra="allow")
    schema_: str = Field("accesscast/evidence/v1", alias="schema")
    experiment: str
    split: Literal["dev", "test", "none"]
    passed: bool
    git_commit: str
    freeze_tag: str | None = None
    started_at: str
    finished_at: str
    environment: dict[str, Any]
    config: dict[str, Any]
    results: list[dict[str, Any]]
    summary: dict[str, Any]


ClaimStatus = Literal["measured", "verified", "estimate", "list_price", "memory_accounting", "cited"]


class ClaimEvidence(Strict):
    path: str
    sha256: str
    pointer: str


class Claim(Strict):
    claim_id: str
    text: str
    value: float | int | str | None
    unit: str = ""
    status: ClaimStatus
    split: Literal["dev", "test", "none"] = "none"
    evidence: list[ClaimEvidence] = Field(default_factory=list)
    source_url: str | None = None
    accessed: str | None = None
    quote: str | None = None
    note: str | None = None  # e.g. "secondary source" or "mirror of EUR-Lex"; shown wherever the claim is used
    public_files: list[str] = Field(default_factory=list)
    display: list[str] = Field(default_factory=list)  # exact strings that may appear in public files


class ClaimsRegistry(Strict):
    schema_: str = Field("accesscast/public-claims/v1", alias="schema")
    claims: list[Claim] = Field(default_factory=list)
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


EXPORTED_MODELS: dict[str, type[BaseModel]] = {
    "words": Words,
    "vad": Vad,
    "gaps": Gaps,
    "shots": Shots,
    "scenes": Scenes,
    "sounds": Sounds,
    "asr_crosscheck": AsrCrosscheck,
    "scene_evidence": SceneEvidence,
    "item": Item,
    "project": ProjectInfo,
    "evidence_file": EvidenceFile,
    "claims_registry": ClaimsRegistry,
}
