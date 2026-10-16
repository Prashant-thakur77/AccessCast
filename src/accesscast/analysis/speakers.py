"""Speaker labels for words, from diarization turns (anonymous S1, S2, …; never names)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from accesscast.schemas import Word


def assign_speakers(words: Sequence[Word], turns: Sequence[dict[str, Any]]) -> list[Word]:
    """Each word takes the speaker whose turn overlaps it most; a word no turn touches keeps speaker None
    (the captions then mark no change there rather than guess)."""
    out = []
    for w in words:
        best, best_ov = None, 0
        for t in turns:
            ov = min(w.end_ms, int(t["end_ms"])) - max(w.start_ms, int(t["start_ms"]))
            if ov > best_ov:
                best, best_ov = str(t["speaker"]), ov
        out.append(w.model_copy(update={"speaker": best}))
    return out
