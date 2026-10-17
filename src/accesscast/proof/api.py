"""Proof API for /proof "Run the attack" (PLAN §13.5).

- /api/attack accepts only the fixed attack cases bundled in proof/cases/<case>/ (no free-form prompts).
- /api/try takes one short caption from a visitor (length-capped, timed as if spoken) and runs the easy-read and
  subtitle writers on it, with our checks, exactly as the pipeline does. Separate, smaller rate limit.
- Runs N tries (default 10) against the live Gemma endpoint — Token Factory first if configured, else the droplet —
  each with a fresh seed; reports per try what Gemma wrote, whether the case's oracle says it failed (the same
  independent oracle E11 uses), which rules blocked it, and whether anything reached the viewer.
- Holds the key server-side; the browser never sees it. Rate-limited per IP. Never fakes a run: if no endpoint
  answers, it returns 503 and the page shows the last recorded run with its date.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import threading
import time
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from accesscast import constants as C
from accesscast.config import load_settings
from accesscast.events import now_iso
from accesscast.llm.client import LlmClient
from accesscast.project import read_json
from accesscast.schemas import Gaps, ItemStatus, SceneEvidence, Scenes, Sounds, Vad, Word, Words
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


def _quoted_ok(text: str, phrase: str) -> bool:
    low = text.lower()
    if phrase not in low:
        return True
    framed = re.search(r"(on screen|reads|sullo schermo|स्क्रीन पर)\s*:", low)
    quoted = re.search(r"[\"“'][^\"”']*" + re.escape(phrase) + r"[^\"”']*[\"”']", low)
    return bool(framed or quoted)


def oracle(meta: dict[str, Any], text: str) -> bool:
    """True when the output shows the failure the case baits. The same independent text oracle as E11
    (eval/e11_adversarial.py), kept here so the deployed API does not need the eval package; it never imports
    our verifier rules."""
    o = meta["oracle"]
    low = f" {text.lower()} "
    if o["type"] == "contains":
        return any(p in low for p in o["any"])
    if o["type"] == "unquoted":
        return any(not _quoted_ok(text, p) for p in o["any"])
    if o["type"] == "missing":
        return any(not re.search(r"\b(" + alt + r")", low) for alt in o["all"])
    if o["type"] == "latin_fraction":
        letters = [c for c in text if c.isalpha()]
        return bool(letters) and sum(1 for c in letters if c.isascii()) / len(letters) > o["max"]
    return False  # "overlap" needs timing the proof API does not model: never claim a failure it cannot see


def _allow(key: str, per_hour: int) -> None:
    now = time.time()
    with _lock:
        q = _hits[key]
        while q and now - q[0] > 3600:
            q.popleft()
        if len(q) >= per_hour:
            raise HTTPException(429, "Too many runs from this address. Try again in an hour.")
        q.append(now)


def words_from_text(text: str) -> list[Word]:
    """A visitor's sentence as timed words, spoken at an ordinary pace (TRY_MS_PER_WORD), with a short pause after
    each sentence. Rejects empty, over-long or control-character input (fail closed: nothing is sent to Gemma)."""
    text = " ".join(text.split())
    if not text or len(text) > C.TRY_MAX_CHARS or any(ord(c) < 32 for c in text):
        raise HTTPException(422, f"Write one or two sentences, up to {C.TRY_MAX_CHARS} characters.")
    toks = text.split(" ")
    if len(toks) < 3 or len(toks) > C.TRY_MAX_WORDS:
        raise HTTPException(422, f"Write between 3 and {C.TRY_MAX_WORDS} words.")
    out, t = [], 500
    for i, w in enumerate(toks):
        out.append(Word(i=i, w=w, start_ms=t, end_ms=t + C.TRY_MS_PER_WORD - 40))
        t += C.TRY_MS_PER_WORD + (300 if w.endswith((".", "?", "!")) else 0)
    return out


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
        _allow(_ip(request), RATE_PER_HOUR)
        n = max(1, min(int(n), 10))
        default_case = os.environ.get("ACCESSCAST_PROOF_CASE") or next(
            iter(sorted(p.name for p in CASES.iterdir())), ""
        )
        ctx, meta, cal = load_case(case or default_case)
        settings = load_settings()
        provider = "tokenfactory" if settings.tf_api_key and settings.tf_base_url else "local"
        client = LlmClient(settings, provider=provider, strict_provider=True)
        kind = meta.get("kind", "ad")
        temp = C.TEMP_STRESS if meta.get("proof_temperature") == "stress" else None
        run_id = secrets.token_hex(4)
        if kind == "ad":
            plans = plan_description(list(ctx.gaps.values()), ctx.evidence, ctx.words, ctx.vad, cal)
            plans = [p for p in plans if not p.extended][:1]
            if not plans:
                raise HTTPException(500, "case has no planned line")
        else:
            from accesscast.captions.segment import segment_sdh

            sdh = segment_sdh(ctx.words, ctx.sounds, 25.0, 10**7)

        def one(k: int) -> dict[str, Any]:
            label = f"proof:{run_id}:{k}"
            if kind == "ad":
                opts = WriteOptions(
                    run_label=label, project_seed=settings.project_seed, temperature=temp, concurrency=1
                )
                drafts = write_drafts(client, plans, ctx.evidence, ctx, opts)
                item = verify_and_repair(client, plans, drafts, ctx, opts)[0]
            else:
                from accesscast.schemas import ItemKind
                from accesscast.write.text_versions import TextOptions, make_easy, make_subtitles

                topts = TextOptions(run_label=label, project_seed=settings.project_seed, temperature=temp)
                made = (
                    make_easy(client, sdh, ctx, topts)
                    if kind == "easy"
                    else make_subtitles(client, sdh, "hi", ctx, topts)
                )
                item = next(i for i in made if i.kind in (ItemKind.EASY, ItemKind.SUBTITLE))
            published = item.status == ItemStatus.PENDING and not item.violations
            first = item.repair.history[0] if item.repair.history else None
            draft = first.text if first else item.draft
            return {
                "try": k + 1,
                "endpoint": provider,
                "text": draft,
                "failed": oracle(meta, draft),
                "blocked_by": first.rules if first and first.rules else [],
                "final": item.text if published else None,
                "reached_viewer": bool(published and oracle(meta, item.text)),
                "repairs": item.repair.attempts,
                "stop_reason": item.repair.stop_reason,
            }

        try:
            with ThreadPoolExecutor(max_workers=min(n, 5)) as ex:
                tries = list(ex.map(one, range(n)))
        except Exception as e:
            raise HTTPException(
                503,
                f"Gemma endpoint not reachable ({type(e).__name__}); showing the last recorded run instead",
            ) from e
        served = client.provider
        return {
            "case": case or default_case,
            "baits": meta.get("baits"),
            "case_text": (f'The video says "{meta["said"]}" ' if meta.get("said") else "")
            + str(meta.get("baits", ""))[:1].upper()
            + str(meta.get("baits", ""))[1:]
            + ".",
            "endpoint": served,
            "model": settings.local_model if served == "local" else "Gemma-4-31B-IT (Token Factory)",
            "endpoint_label": "Gemma 4 31B on AMD Token Factory" if served == "tokenfactory" else served,
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

    @app.post("/api/try")
    async def try_text(request: Request, version: str = "easy") -> dict[str, Any]:
        """A visitor's own caption: Gemma writes easy-read, Hindi and Italian live; our checks run on every answer
        and repairs are asked for as in the pipeline. Shows Gemma's first answer, what blocked it, and what would
        be published. Nothing is stored."""
        if version not in ("easy", *C.TRANSLATION_LANGS):
            raise HTTPException(404, f"version must be easy or one of {', '.join(C.TRANSLATION_LANGS)}")
        _allow("try:" + _ip(request), C.TRY_PER_HOUR)
        try:
            body = await request.json()
        except ValueError as e:
            raise HTTPException(400, 'send JSON: {"text": "..."}') from e
        words = words_from_text(str((body or {}).get("text", "")))
        from accesscast.captions.segment import segment_sdh
        from accesscast.schemas import ItemKind
        from accesscast.write.text_versions import TextOptions, make_easy, make_subtitles

        settings = load_settings()
        provider = "tokenfactory" if settings.tf_api_key and settings.tf_base_url else "local"
        # the function stops at 120 s: one slow call fails closed (the line goes to a person) instead of timing out
        client = LlmClient(settings, provider=provider, strict_provider=True, timeout_s=45, max_retries=0)
        ctx = VerifyContext(lang="en", words=words)
        end = words[-1].end_ms + 1500
        sdh = segment_sdh(words, [], 25.0, end)
        run_id = secrets.token_hex(4)
        topts = TextOptions(run_label=f"try:{run_id}", project_seed=settings.project_seed)

        def one(version: str) -> dict[str, Any]:
            if version == "easy":
                made = make_easy(client, sdh, ctx, topts)
                kind = ItemKind.EASY
            else:
                made = make_subtitles(client, sdh, version, ctx, topts)
                kind = ItemKind.SUBTITLE
            cues = []
            for item in (i for i in made if i.kind == kind):
                first = item.repair.history[0] if item.repair.history else None
                published = item.status == ItemStatus.PENDING and not item.violations
                cues.append(
                    {
                        "gemma_wrote": first.text if first else item.draft,
                        "blocked_by": first.rules if first and first.rules else [],
                        "published": item.text if published else None,
                        "to_person": not published,
                        "repairs": item.repair.attempts,
                        "back_translation": item.back_translation,
                        "findings": [{"rule": f.rule, "observed": f.observed} for f in item.violations][:6],
                    }
                )
            return {"version": version, "cues": cues}

        try:  # one version per request: the page asks for all three at once, so each stays under the time limit
            result = one(version)
        except Exception as e:
            raise HTTPException(
                503, f"Gemma endpoint not reachable ({type(e).__name__}). Nothing was run."
            ) from e
        return {
            "input": " ".join(w.w for w in words),
            "captions": [i.text for i in sdh],
            "endpoint_label": "Gemma 4 31B on AMD Token Factory"
            if client.provider == "tokenfactory"
            else client.provider,
            "recorded_at": now_iso(),
            "version": result["version"],
            "cues": result["cues"],
        }

    return app


def _ip(request: Request) -> str:
    return request.headers.get("x-forwarded-for", request.client.host if request.client else "?").split(",")[
        0
    ]


app = create_app()
_ = json
