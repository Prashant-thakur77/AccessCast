"""Per-project event log (logs/events.jsonl) and the worker progress-line protocol."""

from __future__ import annotations

import json
import sys
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from accesscast.constants import EVENT_PREFIX

_lock = threading.Lock()


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class EventLog:
    """Append-only JSONL log: {"stage","ts","event",...}. Never holds secrets or image bytes."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, stage: str, event: str, **fields: Any) -> dict[str, Any]:
        rec: dict[str, Any] = {"stage": stage, "ts": now_iso(), "event": event, **fields}
        line = json.dumps(rec, ensure_ascii=False, sort_keys=True, default=str)
        with _lock, self.path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        return rec

    def read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [json.loads(x) for x in self.path.read_text(encoding="utf-8").splitlines() if x.strip()]


def worker_event(event: str, **fields: Any) -> None:
    """Workers print progress on stderr as `@@AC_EVENT@@ {json}`; the core parses these lines."""
    sys.stderr.write(f"{EVENT_PREFIX} {json.dumps({'event': event, **fields}, sort_keys=True)}\n")
    sys.stderr.flush()


def parse_worker_line(line: str) -> dict[str, Any] | None:
    if not line.startswith(EVENT_PREFIX):
        return None
    try:
        obj = json.loads(line[len(EVENT_PREFIX):].strip())
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None
