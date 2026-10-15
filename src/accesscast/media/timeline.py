# Copyright 2026 AudioSight contributors
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in
# compliance with the License. You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software distributed under the License is
# distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and limitations under the License.
#
# Source: https://github.com/austin1997/AudioSight src/audiosight/timeline.py (commit 5c708f6).
# Modified by AccessCast contributors, 2026: sample rate is a module constant set to 48 kHz (AccessCast's
# master rate) instead of AudioSight's constant; added `remap_ms` helper. Logic otherwise unchanged.
"""Expanded timeline for extended description: insertions, source_to_output and output_to_source."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

SAMPLE_RATE = 48_000


@dataclass(frozen=True, slots=True)
class Insertion:
    narration_id: str
    anchor_sample: int
    speech_samples: int
    pre_samples: int
    post_samples: int

    @property
    def total_samples(self) -> int:
        return self.pre_samples + self.speech_samples + self.post_samples


def ms_to_samples(milliseconds: int) -> int:
    return round(milliseconds * SAMPLE_RATE / 1000)


def samples_to_ms(samples: int) -> int:
    return round(samples * 1000 / SAMPLE_RATE)


def build_timeline(source_samples: int, insertions: list[Insertion]) -> list[dict[str, Any]]:
    ordered = sorted(insertions, key=lambda item: (item.anchor_sample, item.narration_id))
    if any(item.anchor_sample < 0 or item.anchor_sample > source_samples for item in ordered):
        raise ValueError("Insertion anchor is outside the source timeline.")
    rows: list[dict[str, Any]] = []
    source_cursor = 0
    output_cursor = 0
    for item in ordered:
        if item.anchor_sample > source_cursor:
            length = item.anchor_sample - source_cursor
            rows.append(
                {
                    "type": "source",
                    "source_start_sample": source_cursor,
                    "source_end_sample": item.anchor_sample,
                    "output_start_sample": output_cursor,
                    "output_end_sample": output_cursor + length,
                    "source_start_ms": samples_to_ms(source_cursor),
                    "source_end_ms": samples_to_ms(item.anchor_sample),
                    "output_start_ms": samples_to_ms(output_cursor),
                    "output_end_ms": samples_to_ms(output_cursor + length),
                }
            )
            source_cursor = item.anchor_sample
            output_cursor += length
        end = output_cursor + item.total_samples
        rows.append(
            {
                "type": "insertion",
                "narration_id": item.narration_id,
                "source_anchor_sample": item.anchor_sample,
                "source_anchor_ms": samples_to_ms(item.anchor_sample),
                "output_start_sample": output_cursor,
                "output_end_sample": end,
                "output_start_ms": samples_to_ms(output_cursor),
                "output_end_ms": samples_to_ms(end),
                "speech_duration_samples": item.speech_samples,
                "speech_duration_ms": samples_to_ms(item.speech_samples),
                "padding_duration_samples": item.pre_samples + item.post_samples,
                "padding_duration_ms": samples_to_ms(item.pre_samples + item.post_samples),
            }
        )
        output_cursor = end
    if source_cursor < source_samples:
        length = source_samples - source_cursor
        rows.append(
            {
                "type": "source",
                "source_start_sample": source_cursor,
                "source_end_sample": source_samples,
                "output_start_sample": output_cursor,
                "output_end_sample": output_cursor + length,
                "source_start_ms": samples_to_ms(source_cursor),
                "source_end_ms": samples_to_ms(source_samples),
                "output_start_ms": samples_to_ms(output_cursor),
                "output_end_ms": samples_to_ms(output_cursor + length),
            }
        )
    return rows


def source_to_output(rows: list[dict[str, Any]], source_sample: int) -> int:
    for row in rows:
        if row["type"] != "source":
            continue
        if row["source_start_sample"] <= source_sample <= row["source_end_sample"]:
            return int(row["output_start_sample"]) + source_sample - int(row["source_start_sample"])
    anchors = [row for row in rows if row["type"] == "insertion"]
    if source_sample == 0 and anchors:
        return 0
    raise ValueError("Source sample is outside mapping.")


def output_to_source(rows: list[dict[str, Any]], output_sample: int) -> tuple[int, str | None]:
    for row in rows:
        if not (row["output_start_sample"] <= output_sample <= row["output_end_sample"]):
            continue
        if row["type"] == "source":
            return (
                row["source_start_sample"] + output_sample - row["output_start_sample"],
                None,
            )
        return row["source_anchor_sample"], str(row["narration_id"])
    raise ValueError("Output sample is outside mapping.")


def remap_ms(rows: list[dict[str, Any]], source_ms: int) -> int:
    """Map a source time in ms to the output timeline (AccessCast addition)."""
    src = min(max(0, ms_to_samples(source_ms)), int(rows[-1].get("source_end_sample", 0)) if rows else 0)
    return samples_to_ms(source_to_output(rows, src))
