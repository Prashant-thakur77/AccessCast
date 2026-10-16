"""Prompt files: src/accesscast/llm/prompts/<id>.md with YAML front matter (PLAN §14.4)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from accesscast.errors import ConfigError
from accesscast.project import sha256_text

PROMPT_DIR = Path(__file__).parent / "prompts"


@dataclass(frozen=True)
class Prompt:
    id: str
    version: int
    model: str
    temperature: float
    max_tokens: int
    schema: dict[str, Any]
    system: str
    sha256: str

    @property
    def ref(self) -> str:
        return f"{self.id}@{self.version}"


@lru_cache(maxsize=64)
def load_prompt(prompt_id: str) -> Prompt:
    path = PROMPT_DIR / f"{prompt_id}.md"
    if not path.exists():
        raise ConfigError(f"missing prompt file {path.name}")
    raw = path.read_text(encoding="utf-8")
    if not raw.startswith("---\n"):
        raise ConfigError(f"prompt {prompt_id} has no front matter")
    _, fm, body = raw.split("---\n", 2)
    meta = yaml.safe_load(fm)
    shape = meta.get("schema")
    # The declared output shape goes to the model with the instructions: without it Gemma named the evidence
    # fact key "fact", "visible_fact" or "text" from call to call (dev run, docs/incidents.md 2026-10-16).
    system = body.strip() + (
        "\n\nOutput shape (use exactly these keys; types are descriptive):\n"
        + json.dumps(shape, ensure_ascii=False)
        if shape
        else ""
    )
    try:
        return Prompt(
            id=str(meta["id"]),
            version=int(meta["version"]),
            model=str(meta["model"]),
            temperature=float(meta["temperature"]),
            max_tokens=int(meta["max_tokens"]),
            schema=dict(meta.get("schema") or {}),
            system=system,
            sha256=sha256_text(
                raw + "\n" + system
            ),  # what is sent, so a change in the shape text changes the cache key
        )
    except (KeyError, TypeError, ValueError) as e:
        raise ConfigError(f"prompt {prompt_id} front matter invalid: {e}") from e


def all_prompt_hashes() -> dict[str, str]:
    return {p.stem: sha256_text(p.read_text(encoding="utf-8")) for p in sorted(PROMPT_DIR.glob("*.md"))}
