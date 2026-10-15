# Idea from Rivet's rivet/telemetry/network_guard.py (https://github.com/damishafe/Rivet), MIT License,
# Copyright (c) 2026 Enoch Idowu. Rewritten: Rivet patched only connect/create_connection; this guard also
# covers connect_ex, sendto (UDP) and getaddrinfo (DNS), allows only literal loopback addresses, and counts
# every blocked attempt.
"""Python-level offline guard (PLAN §14.6). Install in the core process and, via sitecustomize, in workers."""

from __future__ import annotations

import ipaddress
import json
import os
import socket
import threading
from pathlib import Path
from typing import Any

_LOCK = threading.Lock()
BLOCKED: list[dict[str, str]] = []
_INSTALLED = False
OFFLINE_ENV = {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "HF_DATASETS_OFFLINE": "1",
               "VLLM_NO_USAGE_STATS": "1", "DO_NOT_TRACK": "1"}


def _is_loopback(host: Any) -> bool:
    if isinstance(host, tuple):
        host = host[0]
    if host is None:
        return False
    if isinstance(host, bytes):
        host = host.decode(errors="ignore")
    if isinstance(host, str) and host.startswith("/"):
        return True  # Unix socket path
    try:
        return ipaddress.ip_address(str(host).split("%")[0]).is_loopback
    except ValueError:
        return str(host) == "localhost"


def _record(kind: str, target: Any) -> None:
    with _LOCK:
        BLOCKED.append({"call": kind, "target": str(target)[:120]})
    log = os.environ.get("ACCESSCAST_GUARD_LOG")
    if log:
        with open(log, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"pid": os.getpid(), "call": kind, "target": str(target)[:120]}) + "\n")


class NetworkBlocked(OSError):
    pass


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    orig_connect = socket.socket.connect
    orig_connect_ex = socket.socket.connect_ex
    orig_sendto = socket.socket.sendto
    orig_gai = socket.getaddrinfo
    orig_cc = socket.create_connection

    def connect(self: socket.socket, address: Any) -> Any:
        if self.family == getattr(socket, "AF_UNIX", -1) or _is_loopback(address):
            return orig_connect(self, address)
        _record("connect", address)
        raise NetworkBlocked(f"offline guard blocked connect to {address}")

    def connect_ex(self: socket.socket, address: Any) -> Any:
        if self.family == getattr(socket, "AF_UNIX", -1) or _is_loopback(address):
            return orig_connect_ex(self, address)
        _record("connect_ex", address)
        return 111  # ECONNREFUSED

    def sendto(self: socket.socket, data: Any, *args: Any) -> Any:
        address = args[-1] if args else None
        if _is_loopback(address):
            return orig_sendto(self, data, *args)
        _record("sendto", address)
        raise NetworkBlocked(f"offline guard blocked sendto {address}")

    def getaddrinfo(host: Any, *args: Any, **kw: Any) -> Any:
        if _is_loopback(host):
            return orig_gai(host, *args, **kw)
        _record("getaddrinfo", host)
        raise socket.gaierror(f"offline guard blocked DNS lookup of {host}")

    def create_connection(address: Any, *args: Any, **kw: Any) -> Any:
        if _is_loopback(address):
            return orig_cc(address, *args, **kw)
        _record("create_connection", address)
        raise NetworkBlocked(f"offline guard blocked connection to {address}")

    socket.socket.connect = connect  # type: ignore[method-assign]
    socket.socket.connect_ex = connect_ex  # type: ignore[method-assign]
    socket.socket.sendto = sendto  # type: ignore[method-assign,assignment]
    socket.getaddrinfo = getaddrinfo
    socket.create_connection = create_connection  # type: ignore[assignment]
    os.environ.update(OFFLINE_ENV)
    _INSTALLED = True


def blocked_count(log: Path | None = None) -> int:
    n = len(BLOCKED)
    if log is not None and log.exists():
        n += sum(1 for line in log.read_text().splitlines() if line.strip())
    return n
