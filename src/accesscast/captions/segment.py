"""SDH caption segmentation, rules only (PLAN §9 S10): ≤42 chars/line, ≤2 lines, break at punctuation and
clause boundaries, 40 frames–6 s, cue start = first word's aligned start, [sound] tags, speaker labels.
"""

from __future__ import annotations

from collections.abc import Sequence

from accesscast import constants as C
from accesscast.schemas import Item, ItemKind, Slot, SoundEvent, Word

_BREAK_AFTER = (",", ";", ":", ".", "?", "!")
_CLAUSE_WORDS = {"and", "but", "or", "so", "because", "which", "that", "when", "while", "if", "then"}


def _wrap(words: list[str]) -> list[str]:
    """Balanced two-line wrap within CHARS_PER_LINE_MAX, or [] if it cannot fit in two lines."""
    text = " ".join(words)
    if len(text) <= C.CHARS_PER_LINE_MAX:
        return [text]
    best: tuple[int, list[str]] | None = None
    for k in range(1, len(words)):
        a, b = " ".join(words[:k]), " ".join(words[k:])
        if len(a) <= C.CHARS_PER_LINE_MAX and len(b) <= C.CHARS_PER_LINE_MAX:
            score = abs(len(a) - len(b)) - (8 if words[k - 1].endswith(_BREAK_AFTER) else 0)
            if best is None or score < best[0]:
                best = (score, [a, b])
    return best[1] if best else []


def segment_sdh(
    words: Sequence[Word], sounds: Sequence[SoundEvent], fps: float, duration_ms: int
) -> list[Item]:
    cues: list[list[Word]] = []
    cur: list[Word] = []
    max_ms = int(C.CUE_MAX_S * 1000)
    for w in sorted(words, key=lambda x: x.start_ms):
        if cur:
            new_seg = w.seg != cur[-1].seg or w.speaker != cur[-1].speaker
            too_long = w.end_ms - cur[0].start_ms > max_ms
            no_fit = not _wrap([x.w for x in cur] + [w.w])
            sentence_end = cur[-1].w.endswith((".", "?", "!")) and len(cur) >= 3
            pause = w.start_ms - cur[-1].end_ms > 700
            if new_seg or too_long or no_fit or sentence_end or pause:
                cues.append(cur)
                cur = []
        cur.append(w)
    if cur:
        cues.append(cur)

    min_ms = round(C.CUE_MIN_FRAMES / max(fps, 1.0) * 1000)
    items: list[Item] = []
    prev_speaker: str | None = None
    for ci, cue in enumerate(cues):
        start = cue[0].start_ms
        end = cue[-1].end_ms
        nxt = cues[ci + 1][0].start_ms if ci + 1 < len(cues) else duration_ms
        # Extend short or fast cues into following silence (never past the next cue or 6 s).
        chars = len(" ".join(x.w for x in cue))
        want = max(min_ms, round(chars / C.CPS_MAX[("en", "sdh")] * 1000))
        if end - start < want:
            end = min(nxt - 1, start + max_ms, start + want)
        lines = _wrap([x.w for x in cue]) or [" ".join(x.w for x in cue)]
        speaker = cue[0].speaker
        if speaker and prev_speaker and speaker != prev_speaker:
            lines[0] = f"- {lines[0]}"
        prev_speaker = speaker or prev_speaker
        items.append(
            Item(
                id=f"sdh.en.{len(items) + 1:04d}",
                kind=ItemKind.SDH,
                lang="en",
                audiences=["deaf"],
                anchor_ms=start,
                slot=Slot(start_ms=start, end_ms=end),
                draft="\n".join(lines),
                source_ids=[f"w{x.i}" for x in cue],
                source_text=" ".join(x.w for x in cue),
            )
        )
    # Non-speech sound tags as their own cues.
    for e in sounds:
        if e.label in ("silence", "other", "music_with_lyrics"):
            continue
        overlaps = any(min(e.end_ms, i.slot.end_ms) - max(e.start_ms, i.slot.start_ms) > 0 for i in items)
        if overlaps:
            continue
        end = min(e.end_ms, e.start_ms + max_ms)
        if end - e.start_ms < min_ms:
            end = min(duration_ms, e.start_ms + min_ms)
        items.append(
            Item(
                id="",
                kind=ItemKind.SDH,
                lang="en",
                audiences=["deaf"],
                anchor_ms=e.start_ms,
                slot=Slot(start_ms=e.start_ms, end_ms=end),
                draft=f"[{e.label.replace('_', ' ')}]",
                flags=["sound_tag"],
            )
        )
    items.sort(key=lambda i: i.anchor_ms)
    return [i.model_copy(update={"id": f"sdh.en.{k + 1:04d}"}) for k, i in enumerate(items)]
