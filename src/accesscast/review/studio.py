"""AccessCast Studio: drop in a video, watch every stage run, then review it (local only, 127.0.0.1).

  POST /api/studio/jobs?name=<file name>   raw video bytes → starts `accesscast run` in a child process
  GET  /api/studio/jobs/current            the latest job: stages in plain words, Gemma calls, line counts

One job at a time (memory and the model endpoint are shared). The child process is the normal pipeline with the
strict provider check, so Studio runs are exactly the runs the CLI makes; nothing is published from here, and every
line still goes through the review gate.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from accesscast import constants as C
from accesscast.config import Settings
from accesscast.project import read_jsonl

# (event stage, plain words shown to the person); order is the order they run in
STAGE_WORDS: tuple[tuple[str, str], ...] = (
    ("ingest", "Reading the video"),
    ("asr", "Listening for every word and when it is said"),
    ("speakers", "Telling the voices apart"),
    ("shots", "Finding the cuts"),
    ("scenes", "Grouping shots into scenes"),
    ("asr_crosscheck", "Second listen to check the transcript"),
    ("sounds", "Labelling sounds between the words"),
    ("gaps", "Finding the pauses between dialogue"),
    ("evidence", "Gemma looks at each scene and lists what is visible"),
    ("plan", "Planning which pause each description goes in"),
    ("write", "Gemma writes the description"),
    ("verify_repair", "Code checks every line; Gemma repairs what fails"),
    ("tts", "Voicing the description"),
    ("captions_sdh", "Captions for deaf and hard-of-hearing viewers"),
    ("captions_easy", "Easy-read captions"),
    ("subtitles_hi", "Hindi subtitles"),
    ("subtitles_it", "Italian subtitles"),
    ("subtitles_es", "Spanish subtitles"),
    ("subtitles_fr", "French subtitles"),
    ("subtitles_pt", "Portuguese subtitles"),
    ("voiceover_hi", "Hindi voice-over"),
    ("voiceover_it", "Italian voice-over"),
    ("voiceover_es", "Spanish voice-over"),
    ("voiceover_fr", "French voice-over"),
    ("voiceover_pt", "Portuguese voice-over"),
    ("review_init", "Lines ready for a person to review"),
)
ITEM_FILES = {
    "ad.en": "Description",
    "sdh.en": "Captions",
    "easy.en": "Easy-read",
    "subs.hi": "Hindi subtitles",
    "subs.it": "Italian subtitles",
    "subs.es": "Spanish subtitles",
    "subs.fr": "French subtitles",
    "subs.pt": "Portuguese subtitles",
}


@dataclass
class Job:
    id: str
    name: str
    sha12: str
    video: Path
    log: Path
    proc: subprocess.Popen[bytes] | None  # None: a finished job read back from disk after a restart
    started: float = field(default_factory=time.time)
    exit_code: int | None = None
    finished: float | None = None


def stage_states(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Latest state of each stage from the events log: waiting, running, done, skipped or failed."""
    last: dict[str, dict[str, Any]] = {}
    skipped: dict[str, dict[str, Any]] = {}
    for e in events:
        st = e.get("stage")
        kind = e.get("event")
        if st is None or kind not in ("start", "done", "error", "skipped", "cached"):
            continue
        if kind == "start":
            skipped.pop(st, None)
        if kind == "skipped":
            skipped[st] = e
        # a stage that skipped still ends with "done": show it as not run, with the reason
        last[st] = skipped[st] if kind == "done" and st in skipped else e
    out = []
    for stage, words in STAGE_WORDS:
        ev: dict[str, Any] | None = last.get(stage)
        kind = ev.get("event") if ev else None
        state = {
            "start": "running",
            "done": "done",
            "cached": "done",
            "error": "failed",
            "skipped": "skipped",
        }.get(kind or "", "waiting")
        row: dict[str, Any] = {"stage": stage, "label": words, "state": state}
        if ev and "wall_s" in ev:
            row["seconds"] = ev["wall_s"]
        if ev and kind == "skipped":
            row["note"] = str(ev.get("reason", ""))[:120]
        if ev and kind == "error":
            row["note"] = str(ev.get("error", ""))[:160]
        out.append(row)
    return out


def add_studio(app: FastAPI, settings: Settings, provider: str) -> None:
    lock = threading.Lock()
    current: dict[str, Job] = {}
    root = settings.projects_dir / "_studio"
    saved = root / "last_job.json"  # the last job survives a server restart (finished jobs only)

    def save(j: Job) -> None:
        root.mkdir(parents=True, exist_ok=True)
        saved.write_text(
            json.dumps(
                {
                    "id": j.id,
                    "name": j.name,
                    "sha12": j.sha12,
                    "video": str(j.video),
                    "log": str(j.log),
                    "started": j.started,
                    "exit_code": j.exit_code,
                    "finished": j.finished,
                }
            )
        )

    def code_of(j: Job) -> int | None:
        if j.proc is not None and j.exit_code is None:
            c = j.proc.poll()
            if c is not None:
                j.exit_code, j.finished = c, time.time()
                save(j)
        return j.exit_code

    if saved.exists():
        try:
            d = json.loads(saved.read_text())
            if d.get("exit_code") is not None:
                current["job"] = Job(
                    id=d["id"],
                    name=d["name"],
                    sha12=d["sha12"],
                    video=Path(d["video"]),
                    log=Path(d["log"]),
                    proc=None,
                    started=d["started"],
                    exit_code=d["exit_code"],
                    finished=d.get("finished"),
                )
        except (ValueError, KeyError):
            pass

    def running() -> Job | None:
        j = current.get("job")
        return j if j is not None and j.proc is not None and code_of(j) is None else None

    @app.post("/api/studio/jobs")
    async def start(request: Request, name: str = "video.mp4") -> JSONResponse:
        if running() is not None:
            raise HTTPException(409, "a video is already being processed; wait for it to finish")
        safe = "".join(c for c in Path(name).name if c.isalnum() or c in "._- ")[:80] or "video.mp4"
        root.mkdir(parents=True, exist_ok=True)
        tmp = root / f"upload.{os.getpid()}.part"
        h = hashlib.sha256()
        size = 0
        with tmp.open("wb") as fh:
            async for chunk in request.stream():
                size += len(chunk)
                if size > C.STUDIO_MAX_BYTES:
                    fh.close()
                    tmp.unlink(missing_ok=True)
                    raise HTTPException(413, f"video larger than {C.STUDIO_MAX_BYTES // 1_000_000} MB")
                h.update(chunk)
                fh.write(chunk)
        if size == 0:
            tmp.unlink(missing_ok=True)
            raise HTTPException(400, "empty upload")
        sha = h.hexdigest()
        video = root / f"{sha[:12]}{Path(safe).suffix or '.mp4'}"
        tmp.replace(video)
        dur = _duration_s(video)
        if dur is None:
            video.unlink(missing_ok=True)
            raise HTTPException(422, "this file is not a video ffprobe can read")
        if dur > C.STUDIO_MAX_SECONDS:
            video.unlink(missing_ok=True)
            raise HTTPException(
                422, f"video is {dur:.0f} s long; Studio takes up to {C.STUDIO_MAX_SECONDS} s"
            )
        exe = Path(sys.executable).parent / "accesscast"
        log = root / f"{sha[:12]}.log"
        with lock:
            proc = subprocess.Popen(
                [str(exe), "run", str(video), "--provider", provider, "--strict-provider"],
                stdout=log.open("wb"),
                stderr=subprocess.STDOUT,
                env=os.environ.copy(),
            )
            current["job"] = Job(id=sha[:12], name=safe, sha12=sha[:12], video=video, log=log, proc=proc)
            save(current["job"])
        return JSONResponse({"id": sha[:12], "name": safe, "seconds": round(dur, 1)}, status_code=202)

    @app.get("/api/studio/jobs/current")
    def status() -> dict[str, Any]:
        j = current.get("job")
        if j is None:
            return {"job": None}
        p = settings.projects_dir / j.sha12
        events = read_jsonl(p / "logs" / "events.jsonl")
        calls = read_jsonl(p / "logs" / "llm_calls.jsonl")
        code = code_of(j)
        lines = {}
        for f, label in ITEM_FILES.items():
            items = read_jsonl(p / "items" / f"{f}.jsonl")
            if items:
                st: dict[str, int] = {}
                for it in items:
                    st[it.get("status", "?")] = st.get(it.get("status", "?"), 0) + 1
                lines[label] = {
                    "total": len(items),
                    "by_status": st,
                    "repaired": sum(1 for it in items if (it.get("repair") or {}).get("attempts")),
                }
        return {
            "job": {
                "id": j.id,
                "name": j.name,
                "project": j.sha12,
                "status": "running" if code is None else ("done" if code == 0 else "failed"),
                "exit_code": code,
                "elapsed_s": round((j.finished or time.time()) - j.started, 1),
                "provider": provider,
                "fake": settings.worker_mode == "fake",
                "stages": stage_states(events),
                "gemma": {
                    "answered": sum(1 for c in calls if c.get("status") == "ok"),
                    "failed": sum(1 for c in calls if c.get("status") != "ok"),
                },
                "lines": lines,
                "log_tail": _tail(j.log) if code not in (None, 0) else None,
            }
        }


def _duration_s(video: Path) -> float | None:
    p = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(video)],
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        return float(json.loads(p.stdout)["format"]["duration"])
    except (ValueError, KeyError, json.JSONDecodeError):
        return None


def _tail(f: Path, n: int = 1200) -> str:
    try:
        return f.read_bytes()[-n:].decode("utf-8", "replace")
    except OSError:
        return ""
