"""JSON extraction from model output: the last balanced top-level object (handles code fences)."""

from __future__ import annotations

import json
from typing import Any

from accesscast.errors import LlmOutputError


def extract_last_object(text: str) -> dict[str, Any]:
    """Return the last balanced {...} that parses as a JSON object. Fail closed otherwise."""
    if not isinstance(text, str) or not text.strip():
        raise LlmOutputError("empty model output")
    candidates: list[str] = []
    depth = 0
    start = -1
    in_str = False
    esc = False
    for i, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth > 0:
            depth -= 1
            if depth == 0 and start >= 0:
                candidates.append(text[start : i + 1])
    for cand in reversed(candidates):
        try:
            obj = json.loads(cand)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj
    raise LlmOutputError("no JSON object found in model output")
