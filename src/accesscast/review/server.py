"""Review app server (PLAN §12): FastAPI JSON API + static keyboard-first UI. Binds to 127.0.0.1.

Endpoints (PLAN §12.4):
  GET    /api/projects
  GET    /api/projects/{id}/items                 items with review state merged, sorted by time
  GET    /api/projects/{id}/analysis              words, gaps, scenes, duration (for the timeline)
  PATCH  /api/projects/{id}/items/{item_id}       {expected_revision, status?, final?, reviewer_note?,
                                                   override_reason?, review_seconds?} → 409 on mismatch
  POST   /api/projects/{id}/items/{item_id}/verify {text} → live re-verify, no save
  POST   /api/projects/{id}/items/{item_id}/hear   {text} → TTS of the current text + re-measured fit
  POST   /api/projects/{id}/items                 manual line
  POST   /api/projects/{id}/review/complete       gate check for all versions
  POST   /api/projects/{id}/render                server-side gate; 409 while anything is pending
  GET    /media/{id}/...                          project media (source video, evidence frames, tts clips)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from accesscast.config import Settings
from accesscast.project import Project, read_json
from accesscast.review.store import ReviewStore, RevisionConflict
from accesscast.schemas import Budget, Item, ItemKind, ItemStatus, Slot

STATIC = Path(__file__).parent / "static"


class PatchBody(BaseModel):
    expected_revision: int
    status: str | None = None
    final: str | None = None
    reviewer_note: str | None = None
    override_reason: str | None = None
    review_seconds: float | None = None


class TextBody(BaseModel):
    text: str


class ManualBody(BaseModel):
    kind: str = "ad"
    lang: str = "en"
    anchor_ms: int
    end_ms: int
    text: str


def _measured(it: Item, text: str) -> int | None:
    """Use the measured clip duration only when it was synthesised from exactly this text."""
    return it.tts.duration_ms if it.tts is not None and text == it.text else None


def _reviewer(request: Request) -> str:
    return request.headers.get("x-reviewer", os.environ.get("ACCESSCAST_REVIEWER", "reviewer-1"))[:40]


def create_app(settings: Settings) -> FastAPI:
    app = FastAPI(title="AccessCast review", docs_url=None, redoc_url=None)

    def proj(pid: str) -> Project:
        if not pid.isalnum() or len(pid) != 12:
            raise HTTPException(404, "no such project")
        try:
            return Project.open(settings.projects_dir, pid)
        except Exception as e:
            raise HTTPException(404, "no such project") from e

    def item_json(it: Item, st: dict[str, Any]) -> dict[str, Any]:
        d = it.model_dump(mode="json")
        s = st.get(it.id, {})
        d["revision"] = int(s.get("revision", 0))
        d["review_seconds"] = float(s.get("review_seconds") or 0)
        d["text"] = it.text
        return d

    def verify_text(p: Project, it: Item, text: str, *, measured_ms: int | None = None) -> dict[str, Any]:
        from accesscast.pipeline import verify_context
        from accesscast.verify import rules_ad
        from accesscast.verify.base import run_rules
        from accesscast.verify.rules_text import EASY_RULES, SDH_RULES, SUBTITLE_RULES, VOICEOVER_RULES
        from accesscast.write.write_ad import ad_rules

        ctx = verify_context(p, it.lang)
        ctx.is_reviewer_edit = True
        ctx.tts_duration_ms = measured_ms
        store = ReviewStore(p.root)
        ctx.other_items = [o for o in store.merged().values() if o.kind == it.kind and o.lang == it.lang and not o.extended]
        cand = it.model_copy(update={"final": text, "tts": None if measured_ms is None else it.tts})
        rules = {ItemKind.AD: ad_rules(it.extended), ItemKind.AD_TRANSLATION: ad_rules(it.extended),
                 ItemKind.SDH: SDH_RULES, ItemKind.EASY: EASY_RULES, ItemKind.SUBTITLE: SUBTITLE_RULES,
                 ItemKind.VOICEOVER: VOICEOVER_RULES}[it.kind]
        res = run_rules(cand, ctx, rules)
        from accesscast.verify import nlp

        words = nlp.word_count(text)
        dur = measured_ms if measured_ms is not None else rules_ad.estimated_duration_ms(cand, ctx)
        avail = it.slot.end_ms - it.anchor_ms
        return {"ok": res.ok, "violations": [f.to_model().model_dump() for f in res.violations],
                "warnings": [f.to_model().model_dump() for f in res.warnings],
                "meter": {"words": words, "words_max": it.budget.words_max if it.budget else None,
                          "seconds": round(dur / 1000, 2),
                          "seconds_max": round(max(0, avail - 300) / 1000, 2) if it.kind == ItemKind.AD and not it.extended else None,
                          "measured": measured_ms is not None}}

    @app.get("/")
    def root() -> RedirectResponse:
        return RedirectResponse("/app/index.html")

    @app.get("/api/projects")
    def projects() -> list[dict[str, Any]]:
        out = []
        if settings.projects_dir.exists():
            for d in sorted(settings.projects_dir.iterdir()):
                if (d / "project.json").exists() and (d / "items").exists():
                    info = read_json(d / "project.json")
                    st = ReviewStore(d).state()["items"]
                    pending = sum(1 for v in st.values() if v.get("status") in ("pending", "needs_revision"))
                    out.append({"id": d.name, "title": info["source_name"], "duration_ms": info["duration_ms"],
                                "pending": pending, "items": len(st), "fake": info.get("worker_mode") == "fake"})
        return out

    @app.get("/api/projects/{pid}/items")
    def items(pid: str) -> dict[str, Any]:
        p = proj(pid)
        store = ReviewStore(p.root)
        st = store.state()
        merged = sorted(store.merged().values(), key=lambda i: (i.anchor_ms, i.id))
        return {"items": [item_json(i, st["items"]) for i in merged], "exports_stale": st.get("exports_stale", True),
                "state_sha256": store.state_sha256()}

    @app.get("/api/projects/{pid}/analysis")
    def analysis(pid: str) -> dict[str, Any]:
        p = proj(pid)
        info = read_json(p.p("project.json"))
        out: dict[str, Any] = {"duration_ms": info["duration_ms"], "fps": info["fps"], "title": info["source_name"],
                               "fake": info.get("worker_mode") == "fake"}
        for name in ("words", "gaps", "scenes"):
            f = p.p("analysis", f"{name}.json")
            out[name] = read_json(f) if f.exists() else None
        evidence = {}
        for f in sorted(p.p("evidence").glob("*/evidence.json")):
            ev = read_json(f)
            evidence[ev["scene_id"]] = {"frames": ev["frames"], "frame_ms": ev["frame_ms"],
                                        "facts": ev["visible_facts"], "on_screen_text": ev["on_screen_text"],
                                        "characters": ev["characters"], "status": ev["status"]}
        out["evidence"] = evidence
        return out

    @app.patch("/api/projects/{pid}/items/{item_id}")
    def patch(pid: str, item_id: str, body: PatchBody, request: Request) -> JSONResponse:
        p = proj(pid)
        store = ReviewStore(p.root)
        merged = store.merged()
        if item_id not in merged:
            raise HTTPException(404, "no such item")
        it = merged[item_id]
        changes = {k: v for k, v in body.model_dump().items() if k != "expected_revision" and v is not None}
        current = int(store.state()["items"].get(item_id, {}).get("revision", 0))
        if current != body.expected_revision:
            return JSONResponse({"error": "conflict", "detail": "Changed elsewhere; reloaded.",
                                 "current_revision": current}, status_code=409)
        if changes.get("status") == "approved":
            text = changes.get("final", it.text)
            check = verify_text(p, it, text, measured_ms=_measured(it, text))
            if not check["ok"] and not (changes.get("override_reason") or "").strip():
                return JSONResponse({"error": "has_errors", "detail": "This line still fails checks. Fix it, or "
                                     "tick override and write a reason.", "check": check}, status_code=422)
        try:
            cur = store.patch(item_id, body.expected_revision, changes, who=_reviewer(request),
                              reason=changes.get("override_reason") or "")
        except RevisionConflict as e:
            return JSONResponse({"error": "conflict", "detail": "Changed elsewhere; reloaded.",
                                 "current_revision": e.current}, status_code=409)
        except (ValueError, KeyError) as e:
            raise HTTPException(400, str(e)) from e
        return JSONResponse({"item_id": item_id, "revision": cur["revision"], "status": cur["status"],
                             "final": cur.get("final"), "state_sha256": store.state_sha256()})

    @app.post("/api/projects/{pid}/items/{item_id}/verify")
    def reverify(pid: str, item_id: str, body: TextBody) -> dict[str, Any]:
        p = proj(pid)
        merged = ReviewStore(p.root).merged()
        if item_id not in merged:
            raise HTTPException(404, "no such item")
        it = merged[item_id]
        return verify_text(p, it, body.text, measured_ms=_measured(it, body.text))

    @app.post("/api/projects/{pid}/items/{item_id}/hear")
    def hear(pid: str, item_id: str, body: TextBody) -> dict[str, Any]:
        from accesscast.tts.engine import VOICEOVER_VOICES, VOICES, synthesize

        p = proj(pid)
        merged = ReviewStore(p.root).merged()
        if item_id not in merged:
            raise HTTPException(404, "no such item")
        it = merged[item_id].model_copy(update={"final": body.text})
        voices = VOICEOVER_VOICES if it.kind == ItemKind.VOICEOVER else VOICES
        voiced = synthesize([it], p.p("tts"), p.events, voice_for=voices)[0]
        assert voiced.tts is not None
        check = verify_text(p, it, body.text, measured_ms=voiced.tts.duration_ms)
        return {"audio": f"/media/{pid}/tts/{voiced.tts.sha256}.wav", "duration_ms": voiced.tts.duration_ms,
                "start_ms": it.anchor_ms + (150 if it.kind in (ItemKind.AD, ItemKind.AD_TRANSLATION) else 0),
                "check": check}

    @app.post("/api/projects/{pid}/items")
    def manual(pid: str, body: ManualBody, request: Request) -> dict[str, Any]:
        p = proj(pid)
        store = ReviewStore(p.root)
        n = sum(1 for i in store.merged().values() if i.source == "manual") + 1
        kind = ItemKind(body.kind)
        it = Item(id=f"{kind.value}.{body.lang}.m{n:03d}", kind=kind, lang=body.lang, audiences=["blind"],
                  anchor_ms=body.anchor_ms, slot=Slot(start_ms=body.anchor_ms, end_ms=body.end_ms),
                  budget=Budget(words_max=40, seconds_max=(body.end_ms - body.anchor_ms) / 1000, wps_voice=2.6)
                  if kind == ItemKind.AD else None, draft=body.text, source="manual", status=ItemStatus.PENDING)
        store.add_manual(it, _reviewer(request))
        return {"item_id": it.id}

    @app.post("/api/projects/{pid}/review/complete")
    def complete(pid: str) -> JSONResponse:
        from accesscast.render_stage import AUDIENCE_VERSIONS
        from accesscast.review import gate

        p = proj(pid)
        store = ReviewStore(p.root)
        res = gate.evaluate(store.merged(), [v for v in AUDIENCE_VERSIONS if not v.startswith("blind.h")
                                             and not v.startswith("blind.i")], store.state_sha256())
        gate.write_validation(p.root, res)
        body = {"ok": res.ok, "blocking": res.blocking, "human_reviewed": res.human_reviewed, "counts": res.counts}
        return JSONResponse(body, status_code=200 if res.ok else 409)

    @app.post("/api/projects/{pid}/render")
    def render(pid: str) -> JSONResponse:
        from accesscast.pipeline import open_run
        from accesscast.render_stage import package, render_all

        p = proj(pid)
        try:
            run = open_run(settings, p)
            summary = render_all(run, mode="public")
            package(run)
        except PermissionError as e:
            return JSONResponse({"error": "refused", "detail": str(e)}, status_code=409)
        return JSONResponse({"ok": all(v["ok"] for v in summary["versions"].values()),
                             "versions": {k: v["ok"] for k, v in summary["versions"].items()}})

    @app.get("/media/{pid}/{path:path}")
    def media(pid: str, path: str) -> FileResponse:
        p = proj(pid)
        allowed = ("media/source.mp4", "media/proxy480.mp4", "evidence/", "tts/", "render/")
        if ".." in path or not path.startswith(allowed):
            raise HTTPException(404, "not found")
        f = p.p(*path.split("/"))
        if not f.is_file():
            raise HTTPException(404, "not found")
        return FileResponse(f)

    if STATIC.exists():
        app.mount("/app", StaticFiles(directory=STATIC, html=True), name="app")
    return app
