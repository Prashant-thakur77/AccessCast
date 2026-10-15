"""Worker side of the protocol. Only files in workers/ import torch."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import traceback
from collections.abc import Callable
from contextlib import contextmanager
from typing import Any

REQ = "accesscast/worker-request/v1"
RESP = "accesscast/worker-response/v1"
EXIT_OOM = 6


def event(name: str, **fields: Any) -> None:
    sys.stderr.write("@@AC_EVENT@@ " + json.dumps({"event": name, **fields}, sort_keys=True) + "\n")
    sys.stderr.flush()


def atomic_write(path: str, obj: Any) -> None:
    d = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".resp.")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def device(require_rocm: bool) -> str:
    """--require-rocm: fail unless torch sees an AMD GPU through HIP (PolicyCut only checked CUDA)."""
    import torch

    if torch.cuda.is_available() and getattr(torch.version, "hip", None):
        return "cuda"
    if require_rocm:
        raise RuntimeError("require_rocm: no ROCm (HIP) GPU visible to torch; refusing CPU fallback")
    return "cpu"


@contextmanager
def stage_timer(name: str, record: dict[str, Any]):
    """Synchronized GPU timing (CLAUDE.md §6; shape from PolicyCut's stage_metrics, MIT)."""
    import torch

    gpu = torch.cuda.is_available()
    if gpu:
        torch.cuda.reset_peak_memory_stats()
        torch.cuda.synchronize()
    t0 = time.perf_counter()
    try:
        yield
    finally:
        if gpu:
            torch.cuda.synchronize()
        record[name] = {
            "wall_s": round(time.perf_counter() - t0, 4),
            "peak_vram_mb": round(torch.cuda.max_memory_allocated() / 2**20, 1) if gpu else None,
        }


def main(actions: dict[str, Callable[[dict[str, Any], bool], dict[str, Any]]]) -> int:
    req_path, resp_path = sys.argv[1], sys.argv[2]
    with open(req_path, encoding="utf-8") as fh:
        req = json.load(fh)
    rid = req.get("request_id")
    if req.get("schema") != REQ:
        atomic_write(resp_path, {"schema": RESP, "request_id": rid, "status": "error", "error": "bad schema"})
        return 2
    fn = actions.get(req.get("action", ""))
    if fn is None:
        atomic_write(
            resp_path,
            {
                "schema": RESP,
                "request_id": rid,
                "status": "error",
                "error": f"unknown action {req.get('action')}",
            },
        )
        return 2
    try:
        result = fn(req["payload"], bool(req.get("require_rocm")))
    except Exception as e:  # fail closed: the core sees status=error and blocks the items
        msg = f"{type(e).__name__}: {e}"
        oom = "out of memory" in msg.lower()
        sys.stderr.write(traceback.format_exc())
        atomic_write(resp_path, {"schema": RESP, "request_id": rid, "status": "error", "error": msg[:500]})
        return EXIT_OOM if oom else 7
    atomic_write(resp_path, {"schema": RESP, "request_id": rid, "status": "ok", "result": result})
    return 0
