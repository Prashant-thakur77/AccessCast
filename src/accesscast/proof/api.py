"""Proof API for /proof "Run the attack" (PLAN §13.5).

- /api/attack accepts only the fixed attack cases bundled in proof/cases/<case>/ (no free-form prompts).
- /api/try takes one short caption from a visitor (length-capped, timed as if spoken) and runs the easy-read and
  subtitle writers on it, with our checks, exactly as the pipeline does. Separate, smaller rate limit.
- Runs N tries (default 10) against the live Gemma endpoint — Token Factory first if configured, else the droplet —
  each with a fresh seed; reports per try what Gemma wrote, whether the case's oracle says it failed (the same
  independent oracle E11 uses), which rules blocked it, and whether anything reached the viewer.
- /api/describe takes one still picture from a visitor: Gemma 4 31B lists what is visible, the planner gives one
  line for an 8-second silent pause, Gemma writes it, and our description rules check it, with repairs, exactly as
  the pipeline does. The picture lives in a temporary file for the length of the request and is never stored.
- Holds the key server-side; the browser never sees it. Rate-limited per IP. Never fakes a run: if no endpoint
  answers, it returns 503 and the page shows the last recorded run with its date.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import threading
import time
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from accesscast import constants as C
from accesscast.config import load_settings
from accesscast.events import now_iso
from accesscast.llm.client import LlmClient
from accesscast.project import read_json
from accesscast.schemas import Gap, Gaps, ItemStatus, Scene, SceneEvidence, Scenes, Sounds, Vad, Word, Words
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


_DATA_URL = re.compile(r"^data:(image/[a-z+]+);base64,([A-Za-z0-9+/=\s]+)$")
_MAGIC = {"image/jpeg": b"\xff\xd8\xff", "image/png": b"\x89PNG", "image/webp": b"RIFF"}


def decode_image(data_url: str) -> tuple[str, bytes]:
    """A visitor's picture as (media type, bytes). Only a base64 data URL of a JPEG, PNG or WebP within the size
    limit, whose bytes really start like that type, is accepted (fail closed: nothing is sent to Gemma)."""
    import base64
    import binascii

    m = _DATA_URL.match(data_url.strip()) if data_url else None
    if not m or m.group(1) not in C.DESCRIBE_TYPES:
        raise HTTPException(422, "Send one JPEG, PNG or WebP picture.")
    if len(m.group(2)) > C.DESCRIBE_MAX_BYTES * 4 // 3 + 4:
        raise HTTPException(413, "That picture is too large. The page shrinks pictures before sending them.")
    try:
        raw = base64.b64decode(m.group(2), validate=False)
    except (binascii.Error, ValueError) as e:
        raise HTTPException(422, "That picture could not be read.") from e
    if not raw or len(raw) > C.DESCRIBE_MAX_BYTES or not raw.startswith(_MAGIC[m.group(1)]):
        raise HTTPException(422, "That picture could not be read.")
    return m.group(1), raw


def plain_problem(detail: str) -> str:
    """The reason the picture got no list of facts, in words a visitor can act on (the raw text stays in
    `evidence_detail`)."""
    d = detail.lower()
    if any(
        k in d
        for k in ("timed out", "timeout", "marked down", "http 5", "failed after retries", "no available")
    ):
        return "AMD Token Factory did not answer in time. Nothing was written. Please try again in a minute."
    if "malformed" in d or "json" in d or "invalid" in d:
        return "Gemma's answer about the picture could not be used. Nothing was written from it."
    return "Gemma could not list what is in the picture. Nothing was written from it."


def picture_context(ev: SceneEvidence) -> tuple[VerifyContext, Gap]:
    """The verify context for one still picture: one scene, one silent pause of DESCRIBE_PAUSE_MS, no speech."""
    end = C.DESCRIBE_PAUSE_MS
    gap = Gap(gap_id="G001", start_ms=0, end_ms=end, len_ms=end, scene_id=ev.scene_id)
    allowed = {p for c in ev.characters if c.name for p in c.name.split()}
    ctx = VerifyContext(
        lang="en",
        words=[],
        vad=[],
        gaps={gap.gap_id: gap},
        scenes=Scenes(scenes=[Scene(scene_id=ev.scene_id, start_ms=0, end_ms=end, shots=["SH001"])]),
        evidence={ev.scene_id: ev},
        sounds=[],
        guard_ms=C.GUARD_MS,
        allowed_names=frozenset(allowed),
    )
    return ctx, gap


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
        """A visitor's own caption: Gemma writes easy-read and each language live; our checks run on every answer
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

    @app.post("/api/describe")
    async def describe(request: Request) -> dict[str, Any]:
        """A visitor's own picture: Gemma lists what is visible, then writes one description line for a silent pause;
        our description rules check it and Gemma repairs what fails, as in the pipeline. Shows the facts, Gemma's first
        line, what blocked it, and what would be published. The picture is never stored."""
        import tempfile

        _allow("describe:" + _ip(request), C.DESCRIBE_PER_HOUR)
        try:
            body = await request.json()
        except ValueError as e:
            raise HTTPException(400, 'send JSON: {"image": "data:image/jpeg;base64,..."}') from e
        mime, raw = decode_image(str((body or {}).get("image", "")))
        from accesscast.write.evidence import evidence_from_frames

        settings = load_settings()
        provider = "tokenfactory" if settings.tf_api_key and settings.tf_base_url else "local"
        t0 = time.monotonic()
        # the function stops at 120 s: the picture call may retry once; writing gets what is left (see below)
        client = LlmClient(settings, provider=provider, strict_provider=True, timeout_s=38, max_retries=1)
        # the English description voice, as in the attack cases
        cal = Calibration(**read_json(CASES / "A1_no_pause" / "case.json")["calibration"])
        scene = Scene(scene_id="SC001", start_ms=0, end_ms=C.DESCRIBE_PAUSE_MS, shots=["SH001"])
        run_id = secrets.token_hex(4)
        # each phase runs with a hard time budget: a slow endpoint, a retry or a re-ask cannot carry the request past
        # the function's limit; when a budget runs out the visitor gets the plain answer and nothing is published
        pool = ThreadPoolExecutor(max_workers=1)
        tmp = tempfile.mkdtemp()
        path = Path(tmp) / ("f00" + {"image/jpeg": ".jpg", "image/png": ".png"}.get(mime, ".webp"))
        path.write_bytes(raw)
        try:
            ev = pool.submit(
                evidence_from_frames, client, scene, 0, [path], [C.DESCRIBE_PAUSE_MS // 2]
            ).result(timeout=C.DESCRIBE_EVIDENCE_BUDGET_S)
        except FutureTimeout:
            ev = SceneEvidence(
                scene_id=scene.scene_id,
                frames=[],
                frame_ms=[],
                status="evidence_failed",
                warnings=["timed out: no answer within the picture budget"],
            )
        except Exception as e:
            raise HTTPException(
                503, f"Gemma endpoint not reachable ({type(e).__name__}). Nothing was run."
            ) from e
        finally:
            shutil.rmtree(tmp, ignore_errors=True)  # the picture is deleted as soon as Gemma has looked at it
        facts = [{"fid": f.fid, "text": f.text} for f in (ev.visible_facts if ev.status == "ok" else [])]
        lines: list[dict[str, Any]] = []
        left = C.DESCRIBE_DEADLINE_S - (time.monotonic() - t0)
        note = None
        if ev.status == "ok" and facts and left < C.DESCRIBE_MIN_WRITE_S:
            note = "Gemma took too long to look at the picture, so no line was written in time: it goes to a person."
        elif ev.status == "ok" and facts:
            ctx, gap = picture_context(ev)
            ctx.wps_voice = cal.wps_voice
            plans = plan_description([gap], ctx.evidence, [], [], cal)[:1]  # one line: the time limit
            # one write and as many repairs as fit: a slow endpoint gets fewer, longer calls, not many short ones
            per_call = max(15.0, min(30.0, left / 2))
            writer = LlmClient(
                settings, provider=provider, strict_provider=True, timeout_s=per_call, max_retries=0
            )
            opts = WriteOptions(
                run_label=f"describe:{run_id}",
                project_seed=settings.project_seed,
                max_repairs=max(0, min(C.DESCRIBE_MAX_REPAIRS, int(left // per_call) - 1)),
            )

            def write_and_check() -> list[Any]:
                return verify_and_repair(
                    writer, plans, write_drafts(writer, plans, ctx.evidence, ctx, opts), ctx, opts
                )

            items: list[Any] = []
            try:
                items = pool.submit(write_and_check).result(timeout=max(1.0, left - 3))
            except FutureTimeout:
                note = "Gemma did not finish the line in time, so it goes to a person. Nothing is published."
            except Exception as e:
                raise HTTPException(503, f"Gemma endpoint not reachable ({type(e).__name__}).") from e
            for item, plan in zip(items, plans, strict=False):
                first = item.repair.history[0] if item.repair.history else None
                published = item.status == ItemStatus.PENDING and not item.violations
                lines.append(
                    {
                        "gemma_wrote": first.text if first else item.draft,
                        "blocked_by": first.rules if first and first.rules else [],
                        "published": item.text if published else None,
                        "to_person": not published,
                        "repairs": item.repair.attempts,
                        "budget_words": plan.budget.words_max,
                        "findings": [{"rule": f.rule, "observed": f.observed} for f in item.violations][:6],
                    }
                )
        pool.shutdown(wait=False)  # a call still running finishes in the background; its answer is not used
        return {
            "facts": facts,
            "evidence_ok": ev.status == "ok",
            "evidence_problem": None
            if ev.status == "ok"
            else plain_problem((ev.warnings or ["no answer"])[0]),
            "evidence_detail": None if ev.status == "ok" else (ev.warnings or ["no answer"])[0][:200],
            "lines": lines,
            "note": note,
            "pause_ms": C.DESCRIBE_PAUSE_MS,
            "endpoint_label": "Gemma 4 31B on AMD Token Factory"
            if client.provider == "tokenfactory"
            else client.provider,
            "recorded_at": now_iso(),
        }

    return app


def _ip(request: Request) -> str:
    return request.headers.get("x-forwarded-for", request.client.host if request.client else "?").split(",")[
        0
    ]


app = create_app()
_ = json
