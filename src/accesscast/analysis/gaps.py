"""S4 gap map: a pure function of words.json, vad.json and sounds.json (PLAN §9 S4).

Speech = union of word spans and VAD speech, each padded by guard_ms. `music_with_lyrics` sound events
also count as speech ("treat lyrics like dialogue", Netflix AD guide). Gaps = everything else that is at
least min_gap_ms long, clipped to [0, duration].
"""

from __future__ import annotations

from collections.abc import Sequence

from accesscast.schemas import Gap, Gaps, GapUnder, Scene, SoundEvent, VadSegment, Word


def merge_spans(spans: Sequence[tuple[int, int]]) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for a, b in sorted(spans):
        if b <= a:
            continue
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def gate_words_by_vad(
    words: Sequence[Word], vad: Sequence[VadSegment], pad_ms: int
) -> tuple[list[Word], list[Word]]:
    """Drop ASR words that overlap no VAD speech segment (padded by pad_ms): Whisper writes text over music
    ("Thank you. Transcription by ESO.") where Silero hears no speech. Returns (kept, dropped)."""
    kept: list[Word] = []
    dropped: list[Word] = []
    for w in words:
        hit = any(w.start_ms < s.end_ms + pad_ms and w.end_ms > s.start_ms - pad_ms for s in vad)
        (kept if hit else dropped).append(w)
    return [w.model_copy(update={"i": k}) for k, w in enumerate(kept)], dropped


def speech_spans(
    words: Sequence[Word], vad: Sequence[VadSegment], sounds: Sequence[SoundEvent], guard_ms: int
) -> list[tuple[int, int]]:
    spans = [(w.start_ms - guard_ms, w.end_ms + guard_ms) for w in words]
    spans += [(s.start_ms - guard_ms, s.end_ms + guard_ms) for s in vad]
    spans += [
        (e.start_ms - guard_ms, e.end_ms + guard_ms)
        for e in sounds
        if e.label in ("music_with_lyrics", "unknown")
    ]  # lyrics are dialogue; unknown fails closed
    return merge_spans(spans)


def _under(start: int, end: int, sounds: Sequence[SoundEvent]) -> GapUnder:
    """Label covering most of the gap: silence → silence, music → music_no_lyrics, else non_speech_sound."""
    cover: dict[str, int] = {}
    for e in sounds:
        ov = min(end, e.end_ms) - max(start, e.start_ms)
        if ov > 0:
            cover[e.label] = cover.get(e.label, 0) + ov
    if not cover:
        return "silence"
    label = max(sorted(cover), key=lambda k: cover[k])
    if label == "silence":
        return "silence"
    if label == "music":
        return "music_no_lyrics"
    return "non_speech_sound"


def _scene_for(mid: int, scenes: Sequence[Scene]) -> str | None:
    for s in scenes:
        if s.start_ms <= mid < s.end_ms:
            return s.scene_id
    return scenes[-1].scene_id if scenes and mid >= scenes[-1].end_ms else None


def build_gaps(
    words: Sequence[Word],
    vad: Sequence[VadSegment],
    sounds: Sequence[SoundEvent],
    scenes: Sequence[Scene],
    duration_ms: int,
    guard_ms: int,
    min_gap_ms: int,
) -> Gaps:
    speech = speech_spans(words, vad, sounds, guard_ms)
    free: list[tuple[int, int]] = []
    cursor = 0
    for a, b in speech:
        a, b = max(0, a), min(duration_ms, b)
        if a > cursor:
            free.append((cursor, a))
        cursor = max(cursor, b)
    if cursor < duration_ms:
        free.append((cursor, duration_ms))

    ordered = sorted(words, key=lambda w: (w.start_ms, w.end_ms))
    gaps: list[Gap] = []
    for start, end in free:
        if end - start < min_gap_ms:
            continue
        prev_i = max((w.i for w in ordered if w.end_ms <= start + guard_ms), default=None)
        next_i = min((w.i for w in ordered if w.start_ms >= end - guard_ms), default=None)
        gaps.append(
            Gap(
                gap_id=f"G{len(gaps) + 1:04d}",
                start_ms=start,
                end_ms=end,
                len_ms=end - start,
                scene_id=_scene_for((start + end) // 2, scenes),
                prev_word_i=prev_i,
                next_word_i=next_i,
                under=_under(start, end, sounds),
            )
        )
    return Gaps(guard_ms=guard_ms, min_gap_ms=min_gap_ms, gaps=gaps)
