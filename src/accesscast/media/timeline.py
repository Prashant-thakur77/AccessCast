"""Expanded timeline for extended description (PLAN §9 S7).

The source plays in pieces; at each description anchor the output holds the picture for the description (with
padding before and after). The timeline is a list of rows, one per piece, each with source and output positions
in samples and in milliseconds, so any source time can be mapped to the output and back.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

SAMPLE_RATE = 48_000  # the render's master rate


@dataclass(frozen=True, slots=True)
class Insertion:
    """One held-picture description: where it goes in the source and how long it lasts."""

    narration_id: str
    anchor_sample: int
    speech_samples: int
    pre_samples: int
    post_samples: int

    @property
    def total_samples(self) -> int:
        return self.speech_samples + self.pre_samples + self.post_samples


def ms_to_samples(milliseconds: int) -> int:
    return round(milliseconds * SAMPLE_RATE / 1000)


def samples_to_ms(samples: int) -> int:
    return round(samples * 1000 / SAMPLE_RATE)


def _source_row(src_from: int, src_to: int, out_from: int) -> dict[str, Any]:
    out_to = out_from + (src_to - src_from)
    return {
        "type": "source",
        "source_start_sample": src_from,
        "source_end_sample": src_to,
        "output_start_sample": out_from,
        "output_end_sample": out_to,
        "source_start_ms": samples_to_ms(src_from),
        "source_end_ms": samples_to_ms(src_to),
        "output_start_ms": samples_to_ms(out_from),
        "output_end_ms": samples_to_ms(out_to),
    }


def _insertion_row(ins: Insertion, out_from: int) -> dict[str, Any]:
    out_to = out_from + ins.total_samples
    padding = ins.pre_samples + ins.post_samples
    return {
        "type": "insertion",
        "narration_id": ins.narration_id,
        "source_anchor_sample": ins.anchor_sample,
        "source_anchor_ms": samples_to_ms(ins.anchor_sample),
        "output_start_sample": out_from,
        "output_end_sample": out_to,
        "output_start_ms": samples_to_ms(out_from),
        "output_end_ms": samples_to_ms(out_to),
        "speech_duration_samples": ins.speech_samples,
        "speech_duration_ms": samples_to_ms(ins.speech_samples),
        "padding_duration_samples": padding,
        "padding_duration_ms": samples_to_ms(padding),
    }


def build_timeline(source_samples: int, insertions: list[Insertion]) -> list[dict[str, Any]]:
    """Rows in output order. Fails closed on an anchor outside the source."""
    bad = [i.narration_id for i in insertions if not 0 <= i.anchor_sample <= source_samples]
    if bad:
        raise ValueError(f"Insertion anchor is outside the source timeline: {', '.join(bad)}")
    rows: list[dict[str, Any]] = []
    played = 0  # source samples already placed
    out = 0  # output samples already placed
    for ins in sorted(insertions, key=lambda i: (i.anchor_sample, i.narration_id)):
        if ins.anchor_sample > played:
            rows.append(_source_row(played, ins.anchor_sample, out))
            out += ins.anchor_sample - played
            played = ins.anchor_sample
        rows.append(_insertion_row(ins, out))
        out += ins.total_samples
    if played < source_samples:
        rows.append(_source_row(played, source_samples, out))
    return rows


def source_to_output(rows: list[dict[str, Any]], source_sample: int) -> int:
    """Output sample where a source sample plays (the first matching piece, so a cut point maps before the hold)."""
    for r in rows:
        if r["type"] == "source" and r["source_start_sample"] <= source_sample <= r["source_end_sample"]:
            return int(r["output_start_sample"]) + source_sample - int(r["source_start_sample"])
    if source_sample == 0 and any(r["type"] == "insertion" for r in rows):
        return 0  # a description at the very start: the source begins after it, but time zero is still zero
    raise ValueError("Source sample is outside mapping.")


def output_to_source(rows: list[dict[str, Any]], output_sample: int) -> tuple[int, str | None]:
    """Source sample shown at an output sample, and the description id while the picture is held."""
    for r in rows:
        if r["output_start_sample"] <= output_sample <= r["output_end_sample"]:
            if r["type"] == "insertion":
                return int(r["source_anchor_sample"]), str(r["narration_id"])
            return int(r["source_start_sample"]) + output_sample - int(r["output_start_sample"]), None
    raise ValueError("Output sample is outside mapping.")


def remap_ms(rows: list[dict[str, Any]], source_ms: int) -> int:
    """A source time in ms on the output timeline (clamped to the source's length)."""
    end = int(rows[-1].get("source_end_sample", 0)) if rows else 0
    return samples_to_ms(source_to_output(rows, min(max(0, ms_to_samples(source_ms)), end)))
