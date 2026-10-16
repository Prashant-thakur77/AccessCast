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
    """words_max = clamp(floor((available_s − intercept − margin) × wps) − 1, 2, 40) (PLAN §9 S7; margin dev-tuned)."""
    avail_s = (
        (available_ms - C.AD_PAD_BEFORE_MS - C.AD_PAD_AFTER_MS) / 1000
        - cal.intercept_s
        - C.AD_BUDGET_MARGIN_S
    )
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
        # A long pause holds several lines, in time order, in disjoint slots: each line runs from its anchor to the
        # next line's anchor (or the pause end). One line per pause pushed the rest of a long musical intro to
        # extended description seconds later (dev run, docs/incidents.md 2026-10-16).
        cursor = g.start_ms
        while True:
            eligible: list[tuple[int, VisibleFact, SceneEvidence]] = []
            for ev, f in all_facts:
                if f"{ev.scene_id}:{f.fid}" in used:
                    continue
                lo, hi = _event_window(f, ev)
                if cursor + C.AD_PAD_BEFORE_MS <= hi and g.end_ms >= lo:
                    anchor = max(cursor, lo)
                    if g.end_ms - anchor >= C.MIN_GAP_MS:
                        eligible.append((anchor, f, ev))
            if not eligible:
                break  # "Do not try to fill every pause" (DCMP)
            first = min(a for a, _, _ in eligible)
            near = [x for x in eligible if x[0] <= first + C.AD_LINE_HORIZON_MS]
            near.sort(key=lambda x: (x[1].priority, x[0]))
            anchor, _, ev0 = near[0]
            chosen = [f for a, f, ev in eligible if ev.scene_id == ev0.scene_id and abs(a - anchor) <= 500][
                :3
            ]
            anchor = max(a for a, f, _ in eligible if f in chosen)  # never before any grouped fact's window
            later = [a for a, f, _ in eligible if f not in chosen and a >= anchor + C.MIN_GAP_MS]
            slot_end = min([g.end_ms, *later])
            usable = (
                math.floor(
                    (
                        (slot_end - anchor - C.AD_PAD_BEFORE_MS - C.AD_PAD_AFTER_MS) / 1000
                        - cal.intercept_s
                        - C.AD_BUDGET_MARGIN_S
                    )
                    * cal.wps_voice
                    * rate
                )
                - 1
            )
            if usable < C.AD_MIN_USEFUL_WORDS:
                if slot_end >= g.end_ms:
                    break  # too short to say anything useful; important facts become extended candidates
                cursor = slot_end
                continue
            for f in chosen:
                used.add(f"{ev0.scene_id}:{f.fid}")
            wm = words_budget(slot_end - anchor, cal, rate)
            plans.append(
                PlannedLine(
                    item_id="",
                    gap=g,
                    scene_id=ev0.scene_id,
                    anchor_ms=anchor,
                    slot_start_ms=anchor if anchor > g.start_ms else g.start_ms,
                    slot_end_ms=slot_end,
                    budget=Budget(
                        words_max=wm,
                        seconds_max=round((slot_end - anchor) / 1000, 2),
                        wps_voice=cal.wps_voice,
                    ),
                    facts=chosen,
                    gap_index=gi,
                    on_screen_text=[t.text for t in ev0.on_screen_text],
                )
            )
            cursor = slot_end
            if cursor >= g.end_ms:
                break
    # Pauses in scenes whose evidence failed go to a person (PLAN §9 S5): a line with no facts, never sent to Gemma.
    failed = {sid for sid, ev in evidence.items() if ev.status != "ok"}
    for gi, g in enumerate(gaps):
        if g.scene_id in failed and not any(p.gap is g for p in plans):
            wm = words_budget(g.end_ms - g.start_ms, cal, rate)
            if wm >= C.AD_MIN_USEFUL_WORDS:
                plans.append(
                    PlannedLine(
                        item_id="",
                        gap=g,
                        scene_id=g.scene_id or "",
                        anchor_ms=g.start_ms,
                        slot_start_ms=g.start_ms,
                        slot_end_ms=g.end_ms,
                        budget=Budget(
                            words_max=wm, seconds_max=round(g.len_ms / 1000, 2), wps_voice=cal.wps_voice
                        ),
                        facts=[],
                        gap_index=gi,
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
        # Inside a pause (no words, VAD speech, lyrics or unknown sound there) the video may hold right at the
        # event, or where a planned line's slot ends, as long as no planned line is speaking at that moment.
        slots = [(p.slot_start_ms, p.slot_end_ms) for p in plans if not p.extended]
        in_pause = [
            b
            for b in (
                event_start,
                *(a for a, _ in slots),
                *(e for _, e in slots),
                *(g.start_ms for g in gaps),
            )
            if lo <= b <= hi
            and any(g.start_ms <= b <= g.end_ms for g in gaps)
            and not any(a < b < e for a, e in slots)
        ]
        ok = sorted(set(ok) | set(in_pause))
        # No segment boundary near the event: use a breath between two words inside the event window
        # (the video holds there, so nothing is talked over) instead of a boundary seconds later (AD005).
        brk = [
            a.end_ms
            for a, b in zip(words, words[1:], strict=False)
            if b.start_ms - a.end_ms >= C.AD_EXT_MIN_BREAK_MS and lo <= a.end_ms <= hi
        ]
        if ok:
            at = min(ok, key=lambda b: (abs(b - event_start), b))
        elif brk:
            at = min(brk, key=lambda b: (abs(b - event_start), b))
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
