"""Core side of the worker protocol (CLAUDE.md §6, PLAN §6.3).

One-shot mode: write request.json atomically, run `workers/.venv/bin/python workers/<role>_worker.py
<request> <response>`, stream `@@AC_EVENT@@` lines from stderr into the event log, read response.json.
The core process never imports torch.
"""

from __future__ import annotations

import json
import os
import subprocess
import uuid
from pathlib import Path
from typing import Any

from accesscast import constants as C
from accesscast.config import REPO_ROOT
from accesscast.errors import ExitCode, MissingDependencyError, OutOfMemoryError, ValidationFailed
from accesscast.events import EventLog, parse_worker_line
from accesscast.project import atomic_write_text, read_json

WORKERS_DIR = REPO_ROOT / "workers"


def worker_python() -> Path:
    py = Path(os.environ.get("ACCESSCAST_WORKER_PYTHON", WORKERS_DIR / ".venv" / "bin" / "python"))
    return py


def workers_available() -> bool:
    return worker_python().exists()


def run_worker(
    role: str,
    action: str,
    payload: dict[str, Any],
    workdir: Path,
    events: EventLog | None = None,
    *,
    require_rocm: bool = False,
    timeout_s: float = 3600,
) -> dict[str, Any]:
    py = worker_python()
    if not py.exists():
        raise MissingDependencyError(f"worker environment missing ({py}); run `make setup`")
    script = WORKERS_DIR / f"{role}_worker.py"
    rid = uuid.uuid4().hex[:12]
    workdir.mkdir(parents=True, exist_ok=True)
    req_p = workdir / f"{role}.{action}.{rid}.request.json"
    resp_p = workdir / f"{role}.{action}.{rid}.response.json"
    req = {
        "schema": C.SCHEMA_WORKER_REQUEST,
        "request_id": rid,
        "action": action,
        "require_rocm": require_rocm,
        "payload": payload,
    }
    atomic_write_text(req_p, json.dumps(req, ensure_ascii=False))
    env = {**os.environ, "PYTHONNOUSERSITE": "1"}
    # -E ignores PYTHONPATH; in offline mode the guard's sitecustomize hook must load, so keep PYTHONPATH then.
    flags = ["-s"] if os.environ.get("ACCESSCAST_OFFLINE") == "1" else ["-E", "-s"]
    proc = subprocess.Popen(
        [str(py), *flags, str(script), str(req_p), str(resp_p)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        cwd=str(WORKERS_DIR),
    )
    tail: list[str] = []
    assert proc.stderr is not None
    for line in proc.stderr:
        ev = parse_worker_line(line.rstrip("\n"))
        if ev is not None and events is not None:
            events.emit(f"worker:{role}", str(ev.pop("event", "progress")), **ev)
        elif ev is None:
            tail = (tail + [line.rstrip()])[-15:]
    rc = proc.wait(timeout=timeout_s)
    req_p.unlink(missing_ok=True)
    if rc == ExitCode.OUT_OF_MEMORY:
        raise OutOfMemoryError(f"{role} worker ran out of memory")
    if rc != 0 or not resp_p.exists():
        raise ValidationFailed(
            f"{role} worker {action} failed (exit {rc}): " + " | ".join(tail[-5:]),
            code=ExitCode(rc) if rc in ExitCode._value2member_map_ else None,
        )
    resp: dict[str, Any] = read_json(resp_p)
    resp_p.unlink(missing_ok=True)
    if resp.get("schema") != C.SCHEMA_WORKER_RESPONSE or resp.get("request_id") != rid:
        raise ValidationFailed(f"{role} worker returned a mismatched response")
    if resp.get("status") != "ok":
        raise ValidationFailed(f"{role} worker error: {resp.get('error')}")
    result: dict[str, Any] = resp["result"]
    return result
