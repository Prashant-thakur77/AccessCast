"""Tiny static server with HTTP Range support (video seeking needs it; http.server lacks it). Localhost only."""

from __future__ import annotations

import http.server
import os
import re
import socketserver
from functools import partial
from pathlib import Path


class RangeHandler(http.server.SimpleHTTPRequestHandler):
    def send_head(self):  # type: ignore[no-untyped-def]
        rng = self.headers.get("Range")
        path = self.translate_path(self.path)
        if not rng or not os.path.isfile(path):
            return super().send_head()
        m = re.match(r"bytes=(\d*)-(\d*)", rng)
        size = os.path.getsize(path)
        if not m:
            self.send_error(416)
            return None
        start = int(m.group(1)) if m.group(1) else max(0, size - int(m.group(2) or 0))
        end = int(m.group(2)) if m.group(1) and m.group(2) else size - 1
        if start >= size:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{size}")
            self.end_headers()
            return None
        end = min(end, size - 1)
        f = open(path, "rb")  # noqa: SIM115 (closed by copyfile caller)
        f.seek(start)
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(end - start + 1))
        self.end_headers()
        self._remaining: int | None = end - start + 1
        return f

    def copyfile(self, source, outputfile):  # type: ignore[no-untyped-def]
        remaining = getattr(self, "_remaining", None)
        if remaining is None:
            return super().copyfile(source, outputfile)
        while remaining > 0:
            chunk = source.read(min(65536, remaining))
            if not chunk:
                break
            outputfile.write(chunk)
            remaining -= len(chunk)
        self._remaining = None
        return None

    def end_headers(self) -> None:
        if not self.headers.get("Range"):
            self.send_header("Accept-Ranges", "bytes")
        super().end_headers()


def serve(directory: Path, port: int, host: str = "127.0.0.1") -> None:
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer((host, port), partial(RangeHandler, directory=str(directory))) as httpd:
        httpd.serve_forever()
