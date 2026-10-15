"""Prompt files: src/accesscast/llm/prompts/<id>.md with YAML front matter (PLAN §14.4)."""

from __future__ import annotations

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
    try:
        return Prompt(
            id=str(meta["id"]),
            version=int(meta["version"]),
            model=str(meta["model"]),
            temperature=float(meta["temperature"]),
            max_tokens=int(meta["max_tokens"]),
            schema=dict(meta.get("schema") or {}),
            system=body.strip(),
            sha256=sha256_text(raw),
        )
    except (KeyError, TypeError, ValueError) as e:
        raise ConfigError(f"prompt {prompt_id} front matter invalid: {e}") from e


def all_prompt_hashes() -> dict[str, str]:
    return {p.stem: sha256_text(p.read_text(encoding="utf-8")) for p in sorted(PROMPT_DIR.glob("*.md"))}
