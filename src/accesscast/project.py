"""Project folders (projects/<sha12>/), atomic file writes, hashing and the stage cache."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from accesscast.events import EventLog

M = TypeVar("M", bound=BaseModel)

SUBDIRS = ("media", "analysis", "evidence", "items", "review", "tts", "render", "render/tracks", "reports", "logs")


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while block := fh.read(chunk):
            h.update(block)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Temp file in the same folder, fsync, rename (CLAUDE.md §6)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def atomic_write_text(path: Path, text: str) -> None:
    atomic_write_bytes(path, text.encode("utf-8"))


def write_json(path: Path, obj: Any) -> None:
    if isinstance(obj, BaseModel):
        obj = obj.model_dump(mode="json", by_alias=True)
    atomic_write_text(path, json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=False) + "\n")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_model(path: Path, model: type[M]) -> M:
    return model.model_validate(read_json(path))


def write_jsonl(path: Path, rows: Iterable[BaseModel | dict[str, Any]]) -> None:
    lines = []
    for r in rows:
        d = r.model_dump(mode="json") if isinstance(r, BaseModel) else r
        lines.append(json.dumps(d, ensure_ascii=False))
    atomic_write_text(path, "\n".join(lines) + ("\n" if lines else ""))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def cache_key(
    stage: str,
    stage_version: str,
    config: dict[str, Any],
    input_hashes: Iterable[str],
    *,
    model_manifest: dict[str, Any] | None = None,
    seed: int | None = None,
    prompt_sha: str | None = None,
    sampling: dict[str, Any] | None = None,
    served_model_id: str | None = None,
) -> str:
    """CLAUDE.md §6: no paths, ids or timings; seed/prompt/sampling/model id included so repeats never hit cache."""
    payload = {
        "stage": stage,
        "v": stage_version,
        "config": config,
        "inputs": sorted(input_hashes),
        "models": model_manifest or {},
        "seed": seed,
        "prompt_sha": prompt_sha,
        "sampling": sampling or {},
        "served_model_id": served_model_id,
    }
    return sha256_text(canonical_json(payload))


class Project:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.events = EventLog(root / "logs" / "events.jsonl")

    @classmethod
    def create(cls, projects_dir: Path, sha12: str) -> Project:
        root = projects_dir / sha12
        for d in SUBDIRS:
            (root / d).mkdir(parents=True, exist_ok=True)
        return cls(root)

    @classmethod
    def open(cls, projects_dir: Path, sha12: str) -> Project:
        root = projects_dir / sha12
        if not (root / "project.json").exists():
            from accesscast.errors import UsageError

            raise UsageError(f"no project {sha12} under {projects_dir}")
        return cls(root)

    # paths --------------------------------------------------------------
    def p(self, *parts: str) -> Path:
        return self.root.joinpath(*parts)

    @property
    def sha12(self) -> str:
        return self.root.name

    # stage cache ---------------------------------------------------------
    def _cache_file(self) -> Path:
        return self.p("logs", "stage_cache.json")

    def cache_get(self, stage: str) -> str | None:
        f = self._cache_file()
        if not f.exists():
            return None
        data: dict[str, str] = read_json(f)
        return data.get(stage)

    def cache_put(self, stage: str, key: str) -> None:
        f = self._cache_file()
        data: dict[str, str] = read_json(f) if f.exists() else {}
        data[stage] = key
        write_json(f, data)

    def cache_invalidate(self, *stages: str) -> None:
        f = self._cache_file()
        if not f.exists():
            return
        data: dict[str, str] = read_json(f)
        for s in stages:
            data.pop(s, None)
        write_json(f, data)
