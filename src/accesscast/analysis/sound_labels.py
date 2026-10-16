"""Map AudioSet class scores (AST, run in a worker) to AccessCast's closed sound vocabulary (D-021)."""

from __future__ import annotations

from collections.abc import Sequence

from accesscast import constants as C


def label_from_audioset(scores: Sequence[tuple[str, float]], min_p: float = C.SOUND_AST_MIN_P) -> str:
    """Fail closed first: any speech-like class above min_p → "unknown" (treated as speech), then any singing →
    "music_with_lyrics" (treated as dialogue); otherwise the most likely mapped class; nothing mapped → "other"."""
    hits = [(C.AUDIOSET_TO_VOCAB.get(name), p) for name, p in scores if p >= min_p]
    labels = [v for v, _ in sorted(hits, key=lambda x: -x[1]) if v]
    for first in ("unknown", "music_with_lyrics"):
        if first in labels:
            return first
    return labels[0] if labels else "other"
