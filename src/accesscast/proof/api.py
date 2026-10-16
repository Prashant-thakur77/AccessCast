"""Proof API for /proof "Run the attack" (PLAN §13.5).

- Accepts only the fixed attack cases bundled in proof/cases/<case>/ (no free-form prompts).
- Runs N tries (default 10) against the live Gemma endpoint — Token Factory first if configured, else the droplet —
  each with a fresh seed; reports per try what Gemma wrote, whether the case's oracle says it failed (the same
  independent oracle E11 uses), which rules blocked it, and whether anything reached the viewer.
- Holds the key server-side; the browser never sees it. Rate-limited per IP. Never fakes a run: if no endpoint
  answers, it returns 503 and the page shows the last recorded run with its date.
"""

from __future__ import annotations

import json
import os
import secrets
import threading
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from accesscast import constants as C
from accesscast.config import load_settings
from accesscast.events import now_iso
from accesscast.llm.client import LlmClient
from accesscast.project import read_json
from accesscast.schemas import Gaps, ItemStatus, SceneEvidence, Scenes, Sounds, Vad, Words
from accesscast.verify.base import VerifyContext
from accesscast.write.plan_ad import Calibration, plan_description
from accesscast.write.write_ad import WriteOptions, verify_and_repair, write_drafts

CASES = Path(__file__).parent / "cases"
RATE_PER_HOUR = int(os.environ.get("ACCESSCAST_PROOF_RATE_PER_HOUR", "6"))
_hits: dict[str, deque[float]] = defaultdict(deque)
_lock = threading.Lock()


def load_case(case: str) -> tuple[VerifyContext, dict[str, Any], Calibration]:
    d = CASES / case
    if not d.is_dir() or not case.replace("_", "").isalnum():
        raise HTTPException(404, "unknown case")
    meta = read_json(d / "case.json")
    ev = {e["scene_id"]: SceneEvidence.model_validate(e) for e in read_json(d / "evidence.json")}
    gaps = Gaps.model_validate(read_json(d / "gaps.json"))
    allowed = {p for e in ev.values() for c in e.characters if c.name for p in c.name.split()}
    ctx = VerifyContext(
        lang="en",
        words=Words.model_validate(read_json(d / "words.json")).words,
        vad=Vad.model_validate(read_json(d / "vad.json")).segments,
        gaps={g.gap_id: g for g in gaps.gaps},
        scenes=Scenes.model_validate(read_json(d / "scenes.json")),
        evidence=ev,
        sounds=Sounds.model_validate(read_json(d / "sounds.json")).events,
        guard_ms=gaps.guard_ms,
        allowed_names=frozenset(allowed),
    )
    cal = Calibration(**meta["calibration"])
    ctx.wps_voice = cal.wps_voice
    return ctx, meta, cal


def oracle(meta: dict[str, Any], text: str) -> bool:
    from importlib import import_module

    try:  # same independent oracle as E11 when the eval package is present
        return bool(import_module("eval.e11_adversarial").oracle(meta, text))
    except ModuleNotFoundError:
        low = f" {text.lower()} "
        o = meta["oracle"]
        return o["type"] == "contains" and any(p in low for p in o["any"])


def create_app() -> FastAPI:
    app = FastAPI(title="AccessCast proof API", docs_url=None, redoc_url=None)
    origins = [
        o for o in os.environ.get("ACCESSCAST_PROOF_ORIGINS", "https://accesscast.vercel.app").split(",") if o
    ]
    app.add_middleware(
        CORSMiddleware, allow_origins=origins, allow_methods=["POST", "GET"], allow_headers=["*"]
    )

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {
            "ok": True,
            "cases": sorted(p.name for p in CASES.iterdir() if p.is_dir()) if CASES.exists() else [],
        }

    @app.post("/api/attack")
    def attack(request: Request, case: str | None = None, n: int = 10) -> dict[str, Any]:
        ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "?").split(
            ","
        )[0]
        now = time.time()
        with _lock:
            q = _hits[ip]
            while q and now - q[0] > 3600:
                q.popleft()
            if len(q) >= RATE_PER_HOUR:
                raise HTTPException(429, "Too many runs from this address. Try again in an hour.")
            q.append(now)
        n = max(1, min(int(n), 10))
        default_case = os.environ.get("ACCESSCAST_PROOF_CASE") or next(
            iter(sorted(p.name for p in CASES.iterdir())), ""
        )
        ctx, meta, cal = load_case(case or default_case)
        settings = load_settings()
        provider = "tokenfactory" if settings.tf_api_key and settings.tf_base_url else "local"
        client = LlmClient(settings, provider=provider, strict_provider=True)
        plans = plan_description(list(ctx.gaps.values()), ctx.evidence, ctx.words, ctx.vad, cal)
        plans = [p for p in plans if not p.extended][:1]
        if not plans:
            raise HTTPException(500, "case has no planned line")
        tries = []
        run_id = secrets.token_hex(4)
        for k in range(n):
            label = f"proof:{run_id}:{k}"
            opts = WriteOptions(
                run_label=label,
                project_seed=settings.project_seed,
                temperature=C.TEMP_STRESS if meta.get("proof_temperature") == "stress" else None,
                concurrency=1,
            )
            try:
                drafts = write_drafts(client, plans, ctx.evidence, ctx, opts)
                item = verify_and_repair(client, plans, drafts, ctx, opts)[0]
            except Exception as e:
                raise HTTPException(
                    503,
                    f"Gemma endpoint not reachable ({type(e).__name__}); showing the last "
                    "recorded run instead",
                ) from e
            published = item.status == ItemStatus.PENDING and not item.violations
            first = item.repair.history[0] if item.repair.history else None
            tries.append(
                {
                    "try": k + 1,
                    "text": item.draft,
                    "failed": oracle(meta, item.draft),
                    "blocked_by": first.rules if first else [],
                    "final": item.text if published else None,
                    "reached_viewer": bool(published and oracle(meta, item.text)),
                    "repairs": item.repair.attempts,
                    "stop_reason": item.repair.stop_reason,
                }
            )
        served = client.provider
        return {
            "case": case or default_case,
            "baits": meta.get("baits"),
            "endpoint": served,
            "model": settings.local_model if served == "local" else "Gemma-4-31B-IT (Token Factory)",
            "temperature": "stress (1.0)" if meta.get("proof_temperature") == "stress" else "production",
            "recorded_at": now_iso(),
            "tries": tries,
            "tally": {
                "n": n,
                "gemma_failed": sum(t["failed"] for t in tries),
                "blocked": sum(t["failed"] and not t["reached_viewer"] for t in tries),
                "reached_viewer": sum(t["reached_viewer"] for t in tries),
            },
        }

    return app


app = create_app()
_ = json
