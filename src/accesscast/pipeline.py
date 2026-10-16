"""Stage orchestration (PLAN §9). Every stage reads files and writes files under projects/<sha12>/."""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from accesscast import constants as C
from accesscast.config import REPO_ROOT, Settings
from accesscast.errors import MissingDependencyError, UsageError
from accesscast.events import now_iso
from accesscast.llm.client import LlmClient, LlmRequest
from accesscast.llm.fake import FakeModel
from accesscast.project import (
    Project,
    read_json,
    read_jsonl,
    read_model,
    sha256_file,
    write_json,
    write_jsonl,
)
from accesscast.schemas import (
    AsrChunkCheck,
    AsrCrosscheck,
    Character,
    Gaps,
    Item,
    ItemKind,
    ItemStatus,
    ProjectInfo,
    SceneEvidence,
    Scenes,
    Shots,
    SoundEvent,
    Sounds,
    ToolVersion,
    Vad,
    Words,
)
from accesscast.verify.base import VerifyContext

FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "fixture20"
STAGES = (
    "ingest",
    "shots",
    "asr",
    "asr_crosscheck",
    "sounds",
    "gaps",
    "evidence",
    "describe",
    "tts",
    "captions",
    "voiceover",
    "review_init",
    "gate",
    "render",
    "package",
)


@dataclass
class Run:
    project: Project
    settings: Settings
    client: LlmClient
    run_label: str = "run0"
    canned_dir: Path | None = None
    require_rocm: bool = False
    asr_model: str = field(default_factory=lambda: os.environ.get("ACCESSCAST_ASR_MODEL", C.ASR_MODEL))
    # E15 decides large-v3 vs large-v3-turbo on the dev set; the override exists for CPU integration runs
    timings: dict[str, float] = field(default_factory=dict)

    @property
    def info(self) -> ProjectInfo:
        return read_model(self.project.p("project.json"), ProjectInfo)

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        ev = self.project.events
        ev.emit(name, "start")
        t0 = time.perf_counter()
        try:
            yield
        except Exception as e:
            ev.emit(
                name,
                "error",
                error=f"{type(e).__name__}: {str(e)[:300]}",
                wall_s=round(time.perf_counter() - t0, 3),
            )
            raise
        wall = round(time.perf_counter() - t0, 3)
        self.timings[name] = wall
        ev.emit(name, "done", wall_s=wall)


def fixture_canned_for(sha: str) -> Path | None:
    src = FIXTURE_DIR / "source.mp4"
    if src.exists() and sha256_file(src) == sha:
        return FIXTURE_DIR / "canned"
    return None


def make_client(
    settings: Settings,
    project: Project,
    canned: Path | None,
    *,
    provider: str = "local",
    strict: bool = False,
) -> LlmClient:
    fake = FakeModel(canned) if settings.worker_mode == "fake" else None
    return LlmClient(
        settings,
        provider=provider,
        strict_provider=strict,
        log_path=project.p("logs", "llm_calls.jsonl"),
        fake_handler=fake,
    )


# ===================================================================== S0
def stage_ingest(settings: Settings, src: Path) -> Project:
    from accesscast.media.ffmpeg import ffmpeg_version
    from accesscast.media.ingest import ingest, source_hash

    sha = source_hash(src)
    proj = Project.create(settings.projects_dir, sha[:12])
    if proj.p("project.json").exists() and proj.p("media", "proxy480.mp4").exists():
        proj.events.emit("ingest", "cached")
        return proj
    proj.events.emit("ingest", "start", source=src.name)
    pr = ingest(src, proj.p("media"))
    canned = fixture_canned_for(sha)
    info = ProjectInfo(
        sha256=sha,
        sha12=sha[:12],
        source_name=src.name,
        duration_ms=pr.duration_ms,
        fps=pr.fps or 30.0,
        width=pr.width,
        height=pr.height,
        has_audio=pr.has_audio,
        created_at=now_iso(),
        worker_mode=settings.worker_mode,
        project_seed=settings.project_seed,
        settings={
            "guard_ms": C.GUARD_MS,
            "min_gap_ms": C.MIN_GAP_MS,
            "detail": "standard",
            "fixture": canned is not None,
            "synthetic_test_data": settings.worker_mode == "fake",
        },
        tools=[ToolVersion(name="ffmpeg", version=ffmpeg_version(), licence="LGPL-2.1+/GPL (system binary)")],
    )
    write_json(proj.p("project.json"), info)
    proj.events.emit("ingest", "done", duration_ms=pr.duration_ms)
    return proj


def open_run(
    settings: Settings,
    proj: Project,
    *,
    run_label: str = "run0",
    provider: str = "local",
    strict: bool = False,
    require_rocm: bool = False,
) -> Run:
    info = read_model(proj.p("project.json"), ProjectInfo)
    canned = fixture_canned_for(info.sha256)
    client = make_client(settings, proj, canned, provider=provider, strict=strict)
    return Run(proj, settings, client, run_label=run_label, canned_dir=canned, require_rocm=require_rocm)


# ===================================================================== S1–S4
def stage_shots(run: Run) -> None:
    from accesscast.analysis.scenes import build_scenes

    proj = run.project
    info = run.info
    with run.stage("shots"):
        if run.canned_dir is not None and (run.canned_dir / "shots.json").exists():
            shots = Shots.model_validate(read_json(run.canned_dir / "shots.json"))
        elif run.settings.worker_mode == "fake":
            shots = Shots.model_validate({"detector": "fake-single", "shots": [{"shot_id": "SH001", "start_ms": 0, "end_ms": info.duration_ms}]})
        else:
            shots = _detect_shots(proj.p("media", "proxy480.mp4"), info.duration_ms)
        write_json(proj.p("analysis", "shots.json"), shots)

    def judge(cut_ms: int, idx: int) -> tuple[bool, str]:
        from accesscast.media.ingest import extract_frame

        frames = [
            extract_frame(
                proj.p("media", "proxy480.mp4"), t, proj.p("analysis", "judge", f"{cut_ms}_{k}.jpg")
            )
            for k, t in enumerate(
                [cut_ms - 3000, cut_ms - 1500, cut_ms - 200, cut_ms + 200, cut_ms + 1500, cut_ms + 3000]
            )
        ]
        words = _words(proj).words
        dia = " ".join(w.w for w in words if cut_ms - 6000 <= w.start_ms <= cut_ms + 6000)
        r = run.client.call(
            LlmRequest(
                "scene_judge",
                {"images_before": 3, "images_after": 3, "dialogue": dia},
                seed=0,
                images=frames,
                label=f"scene_judge:{cut_ms}",
            )
        )
        same = r.obj.get("same_scene")
        if not isinstance(same, bool):
            raise ValueError("scene_judge: same_scene not a bool")
        return same, str(r.obj.get("reason", ""))

    with run.stage("scenes"):
        words = _words(proj).words if proj.p("analysis", "words.json").exists() else []
        video = None if run.settings.worker_mode == "fake" else proj.p("media", "proxy480.mp4")
        scenes = build_scenes(shots.shots, words, video, judge if video else None, info.duration_ms)
        write_json(proj.p("analysis", "scenes.json"), scenes)


def _detect_shots(proxy: Path, duration_ms: int) -> Shots:
    try:
        from scenedetect import AdaptiveDetector, detect
    except ImportError as e:
        raise MissingDependencyError("PySceneDetect not installed (uv sync --extra analysis)") from e
    found = detect(str(proxy), AdaptiveDetector())
    shots = [
        {
            "shot_id": f"SH{i + 1:03d}",
            "start_ms": round(a.get_seconds() * 1000),
            "end_ms": round(b.get_seconds() * 1000),
        }
        for i, (a, b) in enumerate(found)
    ]
    if not shots:
        shots = [{"shot_id": "SH001", "start_ms": 0, "end_ms": duration_ms}]
    return Shots.model_validate({"detector": "pyscenedetect.AdaptiveDetector", "shots": shots})


def _words(proj: Project) -> Words:
    return read_model(proj.p("analysis", "words.json"), Words)


def stage_asr(run: Run) -> None:
    from accesscast.workers_client import run_worker

    proj = run.project
    with run.stage("asr"):
        if run.canned_dir is not None:
            words = Words.model_validate(read_json(run.canned_dir / "words.json"))
            vad = Vad.model_validate(read_json(run.canned_dir / "vad.json"))
        elif run.settings.worker_mode == "fake":
            words = Words(lang="en", model="fake", words=[])
            vad = Vad(model="fake", segments=[])
        else:
            res = run_worker(
                "asr",
                "transcribe",
                {"audio": str(proj.p("media", "asr16k.wav")), "lang": "en", "align": True, "model": run.asr_model},
                proj.p("logs", "worker"),
                proj.events,
                require_rocm=run.require_rocm,
            )
            words = Words.model_validate(res["words"])
            vad = Vad.model_validate(res["vad"])
            write_json(proj.p("analysis", "words_raw.json"), Words.model_validate(res["raw_words"]))
            write_json(proj.p("analysis", "asr_meta.json"), {k: res[k] for k in ("timing", "device", "batch_size",
                                                                                 "aligned_words", "chunks")})
        write_json(proj.p("analysis", "words.json"), words)
        write_json(proj.p("analysis", "vad.json"), vad)


def stage_asr_crosscheck(run: Run) -> None:
    """S2b: Gemma 4 E4B transcribes each ≤30 s chunk; WER vs Whisper marks disagreement."""
    import jiwer

    from accesscast.media.ffmpeg import run_ffmpeg

    proj = run.project
    info = run.info
    words = _words(proj).words
    with run.stage("asr_crosscheck"):
        chunks: list[AsrChunkCheck] = []
        step = int(C.ASR_CHUNK_S * 1000)
        for k, a in enumerate(range(0, info.duration_ms, step)):
            b = min(info.duration_ms, a + step)
            ref = " ".join(w.w for w in words if a <= w.start_ms < b)
            clip = proj.p("analysis", "asr_chunks", f"c{k:03d}.wav")
            clip.parent.mkdir(parents=True, exist_ok=True)
            run_ffmpeg(
                [
                    "-ss",
                    f"{a / 1000:.3f}",
                    "-t",
                    f"{(b - a) / 1000:.3f}",
                    "-i",
                    str(proj.p("media", "asr16k.wav")),
                    "-c:a",
                    "pcm_s16le",
                    str(clip),
                ]
            )
            try:
                r = run.client.call(
                    LlmRequest(
                        "asr_crosscheck",
                        {"language": "English", "reference_text_fake_only": ref}
                        if run.settings.worker_mode == "fake"
                        else {"language": "English"},
                        seed=0,
                        audio=clip,
                        label=f"asr_crosscheck:{k}",
                    ),
                    provider="local_audio",
                )
                hyp = str(r.obj.get("text", ""))
                wer = (
                    float(jiwer.wer(ref.lower(), hyp.lower()))
                    if ref.strip()
                    else (0.0 if not hyp.strip() else 1.0)
                )
                chunks.append(
                    AsrChunkCheck(
                        chunk=k,
                        start_ms=a,
                        end_ms=b,
                        wer=round(wer, 4),
                        disagreement=wer > C.ASR_CROSSCHECK_WER,
                    )
                )
            except Exception as e:  # fail closed: an unchecked chunk counts as disagreement
                chunks.append(
                    AsrChunkCheck(
                        chunk=k,
                        start_ms=a,
                        end_ms=b,
                        wer=None,
                        disagreement=True,
                        error=f"{type(e).__name__}: {str(e)[:120]}",
                    )
                )
        write_json(
            proj.p("analysis", "asr_crosscheck.json"),
            AsrCrosscheck(model="google/gemma-4-E4B-it", threshold=C.ASR_CROSSCHECK_WER, chunks=chunks),
        )


def stage_sounds(run: Run) -> None:
    """S3: non-speech regions ≥1 s → ≤5 s windows → RMS gate → E4B closed-vocabulary labels."""
    from accesscast.analysis.gaps import speech_spans
    from accesscast.media.ffmpeg import run_ffmpeg
    from accesscast.media.ingest import load_mono16k, rms_window

    proj = run.project
    info = run.info
    words = _words(proj).words
    vad = read_model(proj.p("analysis", "vad.json"), Vad).segments
    audio, sr = load_mono16k(proj.p("media", "asr16k.wav"))
    with run.stage("sounds"):
        speech = speech_spans(words, vad, [], 0)
        free = []
        cur = 0
        for a, b in speech:
            if a - cur >= C.SOUND_MIN_REGION_S * 1000:
                free.append((cur, a))
            cur = max(cur, b)
        if info.duration_ms - cur >= C.SOUND_MIN_REGION_S * 1000:
            free.append((cur, info.duration_ms))
        events: list[SoundEvent] = []
        rejected: list[str] = []
        win = int(C.SOUND_WINDOW_MAX_S * 1000)
        for a, b in free:
            for s in range(a, b, win):
                e = min(b, s + win)
                if e - s < 500:
                    continue
                if rms_window(audio, sr, s, e) < C.SOUND_RMS_SILENCE:
                    events.append(SoundEvent(start_ms=s, end_ms=e, label="silence", source="energy_gate"))
                    continue
                clip = proj.p("analysis", "sound_windows", f"w{s:08d}.wav")
                clip.parent.mkdir(parents=True, exist_ok=True)
                run_ffmpeg(
                    [
                        "-ss",
                        f"{s / 1000:.3f}",
                        "-t",
                        f"{(e - s) / 1000:.3f}",
                        "-i",
                        str(proj.p("media", "asr16k.wav")),
                        "-c:a",
                        "pcm_s16le",
                        str(clip),
                    ]
                )
                try:
                    r = run.client.call(
                        LlmRequest("sounds", {"window_ms": [s, e]}, seed=0, audio=clip, label=f"sounds:{s}"),
                        provider="local_audio",
                    )
                    labels = [str(x) for x in r.obj.get("labels") or []]
                except Exception as ex:
                    labels = []
                    rejected.append(f"error@{s}: {type(ex).__name__}")
                ok = [x for x in labels if x in C.SOUND_VOCAB]
                rejected += [x for x in labels if x not in C.SOUND_VOCAB]
                events.append(
                    SoundEvent(start_ms=s, end_ms=e, label=ok[0] if ok else "other", source="model")
                )
        merged: list[SoundEvent] = []
        for ev in events:
            if merged and merged[-1].label == ev.label and ev.start_ms - merged[-1].end_ms <= 50:
                merged[-1] = merged[-1].model_copy(update={"end_ms": ev.end_ms})
            else:
                merged.append(ev)
        write_json(
            proj.p("analysis", "sounds.json"),
            Sounds(model="google/gemma-4-E4B-it", events=merged, rejected_labels=rejected),
        )


def stage_gaps(run: Run) -> None:
    from accesscast.analysis.gaps import build_gaps

    proj = run.project
    info = run.info
    with run.stage("gaps"):
        guard = int(info.settings.get("guard_ms", C.GUARD_MS))
        g = build_gaps(
            _words(proj).words,
            read_model(proj.p("analysis", "vad.json"), Vad).segments,
            read_model(proj.p("analysis", "sounds.json"), Sounds).events,
            read_model(proj.p("analysis", "scenes.json"), Scenes).scenes,
            info.duration_ms,
            guard,
            int(info.settings.get("min_gap_ms", C.MIN_GAP_MS)),
        )
        write_json(proj.p("analysis", "gaps.json"), g)


# ===================================================================== S5
def stage_evidence(run: Run) -> None:
    import shutil

    from accesscast.write.evidence import gather_evidence

    proj = run.project
    scenes = read_model(proj.p("analysis", "scenes.json"), Scenes).scenes
    gaps = read_model(proj.p("analysis", "gaps.json"), Gaps).gaps
    words = _words(proj).words
    with run.stage("evidence"):
        cast: list[Character] = []
        use_ocr = shutil.which("tesseract") is not None
        for i, sc in enumerate(scenes):
            ev = gather_evidence(
                run.client,
                sc,
                i,
                gaps,
                words,
                cast,
                proj.p("media", "proxy480.mp4"),
                proj.p("evidence", sc.scene_id),
                use_ocr=use_ocr,
            )
            if not use_ocr:
                ev = ev.model_copy(
                    update={"warnings": [*ev.warnings, "OCR not run (tesseract not installed)"]}
                )
            write_json(proj.p("evidence", sc.scene_id, "evidence.json"), ev)
            known = {c.cid for c in cast}
            cast += [c for c in ev.characters if c.cid not in known]


def load_evidence(proj: Project) -> dict[str, SceneEvidence]:
    out = {}
    for f in sorted(proj.p("evidence").glob("*/evidence.json")):
        ev = read_model(f, SceneEvidence)
        out[ev.scene_id] = ev
    return out


def verify_context(proj: Project, lang: str = "en") -> VerifyContext:
    info = read_model(proj.p("project.json"), ProjectInfo)
    words = _words(proj).words
    ev = load_evidence(proj)
    allowed: set[str] = set()
    for e in ev.values():
        for c in e.characters:
            if c.name:
                allowed |= set(c.name.split())
    gaps = read_model(proj.p("analysis", "gaps.json"), Gaps)
    return VerifyContext(
        lang=lang,
        words=words,
        vad=read_model(proj.p("analysis", "vad.json"), Vad).segments,
        gaps={g.gap_id: g for g in gaps.gaps},
        scenes=read_model(proj.p("analysis", "scenes.json"), Scenes),
        evidence=ev,
        sounds=read_model(proj.p("analysis", "sounds.json"), Sounds).events,
        guard_ms=gaps.guard_ms,
        allowed_names=frozenset(allowed),
        fps=info.fps or 30.0,
    )


def asr_disagreement_ids(proj: Project, items: list[Item]) -> set[str]:
    p = proj.p("analysis", "asr_crosscheck.json")
    if not p.exists():
        return set()
    bad = [(c.start_ms, c.end_ms) for c in read_model(p, AsrCrosscheck).chunks if c.disagreement]
    return {i.id for i in items if any(a <= i.anchor_ms < b for a, b in bad)}


# ===================================================================== S6–S8
def stage_describe(
    run: Run,
    *,
    checks: bool = True,
    repair: bool = True,
    temperature: float | None = None,
    lang: str = "en",
    detail: str = "standard",
    out_name: str = "ad.en",
) -> list[Item]:
    from accesscast.tts.engine import VOICES, load_calibration
    from accesscast.write.plan_ad import plan_description
    from accesscast.write.write_ad import WriteOptions, verify_and_repair, write_drafts

    proj = run.project
    ctx = verify_context(proj, lang)
    cal = load_calibration(VOICES[lang])
    ctx.wps_voice = cal.wps_voice
    with run.stage("plan"):
        plans = plan_description(list(ctx.gaps.values()), ctx.evidence, ctx.words, ctx.vad, cal, lang, detail)
    opts = WriteOptions(
        run_label=run.run_label,
        project_seed=run.settings.project_seed,
        checks=checks,
        repair=repair,
        temperature=temperature,
    )
    with run.stage("write"):
        drafts = write_drafts(run.client, plans, ctx.evidence, ctx, opts)
    with run.stage("verify_repair"):
        items = verify_and_repair(run.client, plans, drafts, ctx, opts)
        dis = asr_disagreement_ids(proj, items)
        if dis:
            items = [
                i.model_copy(update={"flags": [*i.flags, "asr_disagreement"]}) if i.id in dis else i
                for i in items
            ]
        write_jsonl(proj.p("items", f"{out_name}.jsonl"), items)
    return items


# ===================================================================== S9
def stage_tts(run: Run, name: str = "ad.en") -> list[Item]:
    from accesscast.tts.engine import synthesize
    from accesscast.verify import rules_ad
    from accesscast.verify.base import run_rules

    proj = run.project
    items = [Item.model_validate(r) for r in read_jsonl(proj.p("items", f"{name}.jsonl"))]
    lang = name.split(".")[1]
    with run.stage("tts"):
        todo = [i for i in items if i.text.strip()]
        voiced = {
            i.id: i for i in synthesize(todo, proj.p("tts"), proj.events, require_rocm=run.require_rocm)
        }
        ctx = verify_context(proj, lang)
        out = []
        for it in items:
            it = voiced.get(it.id, it)
            if it.tts is not None and not it.extended and it.status == ItemStatus.PENDING:
                # AD001/AD004/AD006 re-run on the MEASURED clip duration (PLAN §9 S9)
                ctx.tts_duration_ms = it.tts.duration_ms
                ctx.other_items = [voiced.get(o.id, o) for o in items if not o.extended]
                res = run_rules(
                    it,
                    ctx,
                    (
                        rules_ad.ad001_gap_overflow,
                        rules_ad.ad004_overlaps_speech,
                        rules_ad.ad006_non_monotonic,
                    ),
                )
                if not res.ok:
                    it = it.model_copy(
                        update={
                            "status": ItemStatus.NEEDS_REVISION,
                            "violations": [*it.violations, *[f.to_model() for f in res.violations]],
                            "flags": [*it.flags, "measured_overflow", "extended_candidate"],
                        }
                    )
            out.append(it)
        ctx.tts_duration_ms = None
        write_jsonl(proj.p("items", f"{name}.jsonl"), out)
    return out


# ===================================================================== S10, S11
def stage_captions(run: Run) -> None:
    from accesscast.captions.segment import segment_sdh
    from accesscast.verify.base import run_rules
    from accesscast.verify.rules_text import SDH_RULES
    from accesscast.write.text_versions import TextOptions, make_easy, make_subtitles
    from accesscast.write.write_ad import with_confidence

    proj = run.project
    info = run.info
    ctx = verify_context(proj, "en")
    words = ctx.words
    sounds = ctx.sounds
    with run.stage("captions_sdh"):
        sdh = segment_sdh(words, sounds, ctx.fps, info.duration_ms)
        dis = asr_disagreement_ids(proj, sdh)
        out = []
        for it in sdh:
            res = run_rules(it, ctx, SDH_RULES)
            it = it.model_copy(
                update={
                    "violations": [f.to_model() for f in res.violations],
                    "warnings": [f.to_model() for f in res.warnings],
                    "status": ItemStatus.PENDING if res.ok else ItemStatus.NEEDS_REVISION,
                    "flags": [*it.flags, *(["asr_disagreement"] if it.id in dis else [])],
                }
            )
            probs = [w.prob for w in words if f"w{w.i}" in it.source_ids]
            from accesscast import confidence as conf

            value, terms = conf.compute(
                grounding=1.0,
                slack_ms=None,
                asr_probs=probs,
                asr_disagreement=it.id in dis,
                ocr_disagrees=False,
                repairs_used=0,
                warnings_count=len(it.warnings),
            )
            out.append(it.model_copy(update={"confidence": value, "confidence_terms": terms}))
        write_jsonl(proj.p("items", "sdh.en.jsonl"), out)
        _ = with_confidence
    opts = TextOptions(run_label=run.run_label, project_seed=run.settings.project_seed)
    with run.stage("captions_easy"):
        write_jsonl(proj.p("items", "easy.en.jsonl"), make_easy(run.client, out, ctx, opts))
    for lang in ("hi", "it"):
        with run.stage(f"subtitles_{lang}"):
            write_jsonl(
                proj.p("items", f"subs.{lang}.jsonl"), make_subtitles(run.client, out, lang, ctx, opts)
            )


def stage_voiceover(run: Run) -> None:
    from accesscast.repair.loop import GENERATION_FAILED, LIMIT_REACHED, SAFE_INITIAL, SAFE_REVISION
    from accesscast.schemas import RepairInfo, RepairStep
    from accesscast.tts.engine import VOICEOVER_VOICES, load_calibration, synthesize
    from accesscast.verify.base import run_rules
    from accesscast.verify.rules_text import VOICEOVER_RULES
    from accesscast.write.text_versions import TextOptions, make_voiceover, shorten_voiceover

    proj = run.project
    sdh = [Item.model_validate(r) for r in read_jsonl(proj.p("items", "sdh.en.jsonl"))]
    ctx = verify_context(proj, "en")
    opts = TextOptions(run_label=run.run_label, project_seed=run.settings.project_seed)
    for lang in ("hi", "it"):
        with run.stage(f"voiceover_{lang}"):
            cal = load_calibration(VOICEOVER_VOICES[lang])
            lctx = VerifyContext(**{**ctx.__dict__, "lang": lang, "wps_voice": cal.wps_voice})
            out = []
            for it in make_voiceover(run.client, sdh, lang, cal.wps_voice, ctx, opts, run.info.duration_ms):
                history = [RepairStep(attempt=0, text=it.text, rules=[])]
                stop = SAFE_INITIAL
                for k in range(0, C.REPAIR_MAX_ATTEMPTS + 1):
                    if not it.text.strip():
                        res = run_rules(it, lctx, VOICEOVER_RULES)
                        stop = LIMIT_REACHED
                        break
                    it = synthesize(
                        [it],
                        proj.p("tts"),
                        proj.events,
                        voice_for=VOICEOVER_VOICES,
                        require_rocm=run.require_rocm,
                    )[0]
                    lctx.tts_duration_ms = it.tts.duration_ms if it.tts else None
                    res = run_rules(it, lctx, VOICEOVER_RULES)
                    history[-1] = RepairStep(attempt=k, text=it.text, rules=res.rules)
                    if res.ok:
                        stop = SAFE_INITIAL if k == 0 else SAFE_REVISION
                        break
                    if k == C.REPAIR_MAX_ATTEMPTS or not res.all_repairable:
                        stop = LIMIT_REACHED
                        break
                    try:
                        new = shorten_voiceover(
                            run.client, it, lang, cal.wps_voice, opts, k + 1, res.violations
                        )
                    except Exception:
                        stop = GENERATION_FAILED
                        break
                    if new == it.text:
                        stop = LIMIT_REACHED
                        break
                    it = it.model_copy(update={"final": new, "tts": None})
                    history.append(RepairStep(attempt=k + 1, text=new, rules=[]))
                lctx.tts_duration_ms = None
                out.append(
                    it.model_copy(
                        update={
                            "violations": [f.to_model() for f in res.violations],
                            "warnings": [f.to_model() for f in res.warnings],
                            "status": ItemStatus.PENDING if res.ok else ItemStatus.NEEDS_REVISION,
                            "repair": RepairInfo(
                                attempts=len(history) - 1, stop_reason=stop, history=history
                            ),
                        }
                    )
                )
            write_jsonl(proj.p("items", f"vo.{lang}.jsonl"), out)


def stage_ad_translate(run: Run) -> None:
    """S11 description in hi/it: only from APPROVED English lines (meaning approved by a person)."""
    from accesscast.review.store import ReviewStore
    from accesscast.tts.engine import VOICES, load_calibration, synthesize
    from accesscast.write.text_versions import TextOptions, make_ad_translations

    proj = run.project
    store = ReviewStore(proj.root)
    items = store.merged()
    approved = [
        i
        for i in items.values()
        if i.kind == ItemKind.AD and i.lang == "en" and i.status == ItemStatus.APPROVED
    ]
    approved.sort(key=lambda i: i.anchor_ms)
    ctx = verify_context(proj, "en")
    opts = TextOptions(run_label=run.run_label, project_seed=run.settings.project_seed)
    for lang in ("hi", "it"):
        with run.stage(f"ad_translate_{lang}"):
            cal = load_calibration(VOICES[lang])
            tr = make_ad_translations(run.client, approved, lang, cal.wps_voice, ctx, opts)
            todo = [i for i in tr if i.text.strip()]
            voiced = {
                i.id: i for i in synthesize(todo, proj.p("tts"), proj.events, require_rocm=run.require_rocm)
            }
            write_jsonl(proj.p("items", f"ad.{lang}.jsonl"), [voiced.get(i.id, i) for i in tr])
    store.init_from_items()


# ===================================================================== S12 routing
def stage_review_init(run: Run) -> dict[str, int]:
    """Seed review state and apply PLAN §11.3 routing (auto_approved only where allowed)."""
    import random

    from accesscast.review.store import ReviewStore

    proj = run.project
    store = ReviewStore(proj.root)
    store.init_from_items()
    items = store.merged()
    auto: list[str] = []
    rng = random.Random(run.settings.project_seed)
    for it in items.values():
        if it.status != ItemStatus.PENDING:
            continue
        if it.kind == ItemKind.SDH:
            if (
                not it.warnings
                and "asr_disagreement" not in it.flags
                and (it.confidence or 0) >= C.SDH_AUTO_APPROVE_CONFIDENCE
            ):
                auto.append(it.id)
        elif it.kind in (ItemKind.SUBTITLE, ItemKind.VOICEOVER):
            sampled = rng.random() < 0.2  # random spot-check sample goes to a person
            if not it.warnings and not sampled:
                auto.append(it.id)
    if auto:
        store.auto_approve(auto, "PLAN §11.3 routing: every rule passed")
    if run.settings.review_policy == "prototype-auto":
        # Drafts only: stamp human_reviewed=false and watermark (AudioSight's draft mode).
        rest = [i.id for i in store.merged().values() if i.status == ItemStatus.PENDING]
        store.auto_approve(rest, "prototype-auto draft policy (NOT reviewed by a person)")
    counts: dict[str, int] = {}
    for it in store.merged().values():
        counts[it.status.value] = counts.get(it.status.value, 0) + 1
    proj.events.emit("review_init", "done", counts=counts)
    return counts


StageFn = Callable[[Run], Any]
ANALYSIS: tuple[tuple[str, StageFn], ...] = (
    ("asr", stage_asr),
    ("shots", stage_shots),
    ("asr_crosscheck", stage_asr_crosscheck),
    ("sounds", stage_sounds),
    ("gaps", stage_gaps),
)


def run_all(
    settings: Settings,
    src: Path,
    *,
    provider: str = "local",
    strict: bool = False,
    require_rocm: bool = False,
    until: str | None = None,
) -> Run:
    if until is not None and until not in STAGES:
        raise UsageError(f"unknown stage {until!r}")
    proj = stage_ingest(settings, src)
    run = open_run(settings, proj, provider=provider, strict=strict, require_rocm=require_rocm)
    for _name, fn in ANALYSIS:
        fn(run)
    stage_evidence(run)
    stage_describe(run)
    stage_tts(run)
    stage_captions(run)
    stage_voiceover(run)
    stage_review_init(run)
    return run
