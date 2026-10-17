"""WebVTT tracks. Each track gets a distinct label (MDN: one track per kind+srclang+label)."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

from accesscast.project import atomic_write_text
from accesscast.schemas import Item, ItemStatus

PUBLISHABLE = (ItemStatus.APPROVED, ItemStatus.AUTO_APPROVED)


def ts(ms: int) -> str:
    ms = max(0, int(ms))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def write_vtt(
    path: Path,
    items: Sequence[Item],
    *,
    include: Callable[[Item], bool] | None = None,
    remap: Callable[[int], int] | None = None,
    end_of: Callable[[Item], int] | None = None,
    span_of: Callable[[Item], tuple[int, int] | None] | None = None,
    header_note: str = "",
) -> int:
    """`span_of` gives a cue's times directly on the output timeline (not remapped): on the extended timeline a
    line voiced while the picture holds is heard exactly in its hold window, which no source time maps to."""
    lines = ["WEBVTT", ""]
    if header_note:
        lines += ["NOTE", header_note, ""]
    n = 0
    last_end = -1
    for it in sorted(items, key=lambda i: i.anchor_ms):
        if include is not None and not include(it):
            continue
        span = span_of(it) if span_of else None
        if span is not None:
            a, b = span
        else:
            a = it.anchor_ms if it.kind.value in ("ad", "ad_translation") else it.slot.start_ms
            b = end_of(it) if end_of else it.slot.end_ms
            if remap:
                a, b = remap(a), remap(b)
        a = max(a, last_end)
        if b <= a:
            b = a + 500
        last_end = b
        n += 1
        lines += [it.id, f"{ts(a)} --> {ts(b)}", it.text.strip(), ""]
    atomic_write_text(path, "\n".join(lines))
    return n
