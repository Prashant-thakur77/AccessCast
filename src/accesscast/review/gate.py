"""S13 render gate (PLAN §12.5). Server-side, never a browser confirm().

Refuses while any item in the requested versions is `pending` or `needs_revision`. Writes
reports/validation.json bound to the SHA-256 of review/state.json; render refuses a stale validation.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from accesscast.events import now_iso
from accesscast.project import atomic_write_text
from accesscast.review.store import ReviewStore
from accesscast.schemas import Item, ItemKind, ItemStatus

# Which item files each audience version needs.
VERSION_ITEMS: dict[str, tuple[tuple[ItemKind, str], ...]] = {
    "blind.en": ((ItemKind.AD, "en"),),
    "blind_ext.en": ((ItemKind.AD, "en"),),
    "deaf.en": ((ItemKind.SDH, "en"),),
    "easy.en": ((ItemKind.EASY, "en"),),
    "hi": ((ItemKind.SUBTITLE, "hi"), (ItemKind.VOICEOVER, "hi")),
    "it": ((ItemKind.SUBTITLE, "it"), (ItemKind.VOICEOVER, "it")),
    "es": ((ItemKind.SUBTITLE, "es"), (ItemKind.VOICEOVER, "es")),
    "fr": ((ItemKind.SUBTITLE, "fr"), (ItemKind.VOICEOVER, "fr")),
    "pt": ((ItemKind.SUBTITLE, "pt"), (ItemKind.VOICEOVER, "pt")),
    "blind.hi": ((ItemKind.VOICEOVER, "hi"), (ItemKind.AD_TRANSLATION, "hi")),
    "blind.it": ((ItemKind.VOICEOVER, "it"), (ItemKind.AD_TRANSLATION, "it")),
}
BLOCKING = frozenset({ItemStatus.PENDING, ItemStatus.NEEDS_REVISION})
PERSON_ONLY = frozenset({ItemKind.AD, ItemKind.AD_TRANSLATION, ItemKind.EASY})


@dataclass(frozen=True)
class GateResult:
    ok: bool
    blocking: list[str]
    state_sha256: str
    versions: list[str]
    human_reviewed: bool
    counts: dict[str, int]


def items_for(items: Mapping[str, Item], version: str) -> list[Item]:
    wanted = VERSION_ITEMS[version]
    return [i for i in items.values() if (i.kind, i.lang) in wanted]


def evaluate(items: Mapping[str, Item], versions: Iterable[str], state_sha256: str) -> GateResult:
    vs = list(versions)
    unknown = [v for v in vs if v not in VERSION_ITEMS]
    if unknown:
        raise ValueError(f"unknown versions {unknown}")
    selected: dict[str, Item] = {}
    empty: list[str] = []
    for v in vs:
        found = items_for(items, v)
        if not found:
            empty.append(f"no_items:{v}")  # a version with nothing in it means a stage failed: fail closed
        for it in found:
            selected[it.id] = it
    blocking = sorted(i.id for i in selected.values() if i.status in BLOCKING) + empty
    # A description or easy-read line counts as reviewed only if a person approved it (never auto).
    auto_on_person_only = sorted(
        i.id for i in selected.values() if i.kind in PERSON_ONLY and i.status == ItemStatus.AUTO_APPROVED
    )
    counts: dict[str, int] = {}
    for i in selected.values():
        counts[i.status.value] = counts.get(i.status.value, 0) + 1
    human = (
        not blocking
        and not auto_on_person_only
        and all(i.reviewer is not None for i in selected.values() if i.status == ItemStatus.APPROVED)
    )
    return GateResult(
        ok=not blocking,
        blocking=blocking,
        state_sha256=state_sha256,
        versions=vs,
        human_reviewed=human,
        counts=counts,
    )


def write_validation(root: Path, res: GateResult) -> Path:
    p = root / "reports" / "validation.json"
    doc: dict[str, Any] = {
        "schema_version": "accesscast/validation/v1",
        "generated_at": now_iso(),
        "ok": res.ok,
        "blocking": res.blocking,
        "review_state_sha256": res.state_sha256,
        "versions": res.versions,
        "human_reviewed": res.human_reviewed,
        "counts": res.counts,
    }
    atomic_write_text(p, json.dumps(doc, indent=1, sort_keys=True) + "\n")
    return p


def check_fresh(root: Path, store: ReviewStore) -> dict[str, Any]:
    """Render refuses a stale or failed validation."""
    p = root / "reports" / "validation.json"
    if not p.exists():
        raise PermissionError("no validation; run the gate first")
    doc: dict[str, Any] = json.loads(p.read_text(encoding="utf-8"))
    if not doc.get("ok"):
        raise PermissionError(f"gate refused: {len(doc.get('blocking', []))} item(s) still pending")
    if doc.get("review_state_sha256") != store.state_sha256():
        raise PermissionError("validation is stale: review state changed since the gate ran")
    return doc
