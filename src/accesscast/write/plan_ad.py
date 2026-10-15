"""S6 plan the description (deterministic; PLAN §9 S6)."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field

from accesscast import constants as C
from accesscast.schemas import Budget, Gap, SceneEvidence, VadSegment, VisibleFact, Word


@dataclass(frozen=True)
class Calibration:
    voice: str
    wps_voice: float
    intercept_s: float = 0.0
    measured: bool = False


@dataclass
class PlannedLine:
    item_id: str
    gap: Gap | None
    scene_id: str
    anchor_ms: int
    slot_start_ms: int
    slot_end_ms: int
    budget: Budget
    facts: list[VisibleFact]
    extended: bool = False
    gap_index: int = -1
    on_screen_text: list[str] = field(default_factory=list)


def words_budget(available_ms: int, cal: Calibration, rate: float = 1.0) -> int:
    """words_max = clamp(floor((available_s − intercept) × wps) − 1, 2, 40) (PLAN §9 S7)."""
    avail_s = (available_ms - C.AD_PAD_BEFORE_MS - C.AD_PAD_AFTER_MS) / 1000 - cal.intercept_s
    n = math.floor(avail_s * cal.wps_voice * rate) - 1
    return max(C.AD_WORDS_MIN, min(C.AD_WORDS_MAX, C.AD_MAX_WORDS_PER_LINE, n))


def _event_window(f: VisibleFact, ev: SceneEvidence) -> tuple[int, int]:
    times = [ev.frame_ms[i] for i in f.frames if 0 <= i < len(ev.frame_ms)] or ev.frame_ms[:1] or [0]
    return min(times) - C.AD_EVENT_BEFORE_MS, max(times) + C.AD_EVENT_AFTER_MS


def _speech_segment_ends(words: Sequence[Word], vad: Sequence[VadSegment]) -> list[int]:
    ends = sorted({s.end_ms for s in vad})
    if not ends and words:
        segs: dict[int, int] = {}
        for w in words:
            segs[w.seg] = max(segs.get(w.seg, 0), w.end_ms)
        ends = sorted(segs.values())
    return ends


def plan_description(
    gaps: Sequence[Gap],
    evidence: dict[str, SceneEvidence],
    words: Sequence[Word],
    vad: Sequence[VadSegment],
    cal: Calibration,
    lang: str = "en",
    detail: str = "standard",
) -> list[PlannedLine]:
    level = C.DETAIL_LEVELS[detail]
    cutoff = int(level["max_priority"])
    rate = float(level["rate"])
    used: set[str] = set()
    plans: list[PlannedLine] = []
    all_facts: list[tuple[SceneEvidence, VisibleFact]] = [
        (ev, f)
        for ev in evidence.values()
        if ev.status == "ok"
        for f in ev.visible_facts
        if f.priority <= cutoff
    ]
    for gi, g in enumerate(gaps):
        eligible: list[tuple[int, VisibleFact, SceneEvidence]] = []
        for ev, f in all_facts:
            key = f"{ev.scene_id}:{f.fid}"
            if key in used:
                continue
            lo, hi = _event_window(f, ev)
            if g.start_ms + C.AD_PAD_BEFORE_MS <= hi and g.end_ms >= lo:
                anchor = max(g.start_ms, lo)
                if g.end_ms - anchor >= C.MIN_GAP_MS:
                    eligible.append((anchor, f, ev))
        if not eligible:
            continue  # "Do not try to fill every pause" (DCMP)
        eligible.sort(key=lambda x: (x[1].priority, x[0]))
        anchor = max(a for a, _, _ in eligible[:1])
        ev0 = eligible[0][2]
        chosen = [f for a, f, ev in eligible if ev.scene_id == ev0.scene_id and a <= anchor + 500][:3]
        wm = words_budget(g.end_ms - anchor, cal, rate)
        if (
            math.floor(
                ((g.end_ms - anchor - C.AD_PAD_BEFORE_MS - C.AD_PAD_AFTER_MS) / 1000 - cal.intercept_s)
                * cal.wps_voice
                * rate
            )
            - 1
            < C.AD_MIN_USEFUL_WORDS
        ):
            continue  # too short to say anything useful; important facts become extended candidates
        for f in chosen:
            used.add(f"{ev0.scene_id}:{f.fid}")
        plans.append(
            PlannedLine(
                item_id="",
                gap=g,
                scene_id=ev0.scene_id,
                anchor_ms=anchor,
                slot_start_ms=g.start_ms,
                slot_end_ms=g.end_ms,
                budget=Budget(
                    words_max=wm, seconds_max=round((g.end_ms - anchor) / 1000, 2), wps_voice=cal.wps_voice
                ),
                facts=chosen,
                gap_index=gi,
                on_screen_text=[t.text for t in ev0.on_screen_text],
            )
        )
    # Important facts that found no gap → extended-description candidates, inserted at the speech
    # boundary (start of video, start or end of a speech segment, never inside a word) nearest the event.
    bounds = sorted(
        {0, *(s.start_ms for s in vad), *(s.end_ms for s in vad), *_speech_segment_ends(words, vad)}
    )
    for ev, f in all_facts:
        if not f.important or f"{ev.scene_id}:{f.fid}" in used:
            continue
        lo, hi = _event_window(f, ev)
        event_start = lo + C.AD_EVENT_BEFORE_MS
        ok = [b for b in bounds if lo <= b <= hi and not any(w.start_ms < b < w.end_ms for w in words)]
        if ok:
            at = min(ok, key=lambda b: (abs(b - event_start), b))
        else:
            after = [b for b in bounds if b >= lo]
            at = after[0] if after else lo  # AD005 will send it to a person
        wm = max(C.AD_WORDS_MIN, min(C.AD_MAX_WORDS_PER_LINE, len(f.text.split()) + 2))
        used.add(f"{ev.scene_id}:{f.fid}")
        plans.append(
            PlannedLine(
                item_id="",
                gap=None,
                scene_id=ev.scene_id,
                anchor_ms=at,
                slot_start_ms=at,
                slot_end_ms=at,
                budget=Budget(
                    words_max=wm, seconds_max=round(wm / cal.wps_voice + 0.6, 2), wps_voice=cal.wps_voice
                ),
                facts=[f],
                extended=True,
                on_screen_text=[t.text for t in ev.on_screen_text],
            )
        )
    plans.sort(key=lambda p: (p.anchor_ms, p.extended))
    for i, p in enumerate(plans):
        p.item_id = f"ad.{lang}.{i + 1:04d}"
    return plans
