"""Append one uptime sample for the live site (and the proof API if configured) to evidence/uptime.json."""

from __future__ import annotations

import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

URLS = ["https://accesscast.vercel.app/", "https://accesscast.vercel.app/data/catalog.json"]
OUT = Path(__file__).resolve().parents[1] / "evidence" / "uptime.json"


def probe(url: str) -> dict[str, object]:
    t0 = time.perf_counter()
    try:
        code = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "accesscast-uptime"}),
                                      timeout=20).status
    except Exception as e:
        code = f"{type(e).__name__}"
    return {"url": url, "status": code, "ms": round((time.perf_counter() - t0) * 1000)}


def main() -> None:
    doc = json.loads(OUT.read_text()) if OUT.exists() else {"schema": "accesscast/uptime/v1", "samples": []}
    doc["samples"].append({"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "checks": [probe(u) for u in URLS]})
    doc["samples"] = doc["samples"][-2000:]
    ok = sum(all(c["status"] == 200 for c in s["checks"]) for s in doc["samples"])
    doc["summary"] = {"samples": len(doc["samples"]), "all_ok": ok, "first": doc["samples"][0]["ts"],
                      "last": doc["samples"][-1]["ts"]}
    OUT.write_text(json.dumps(doc, indent=1) + "\n")


if __name__ == "__main__":
    main()
