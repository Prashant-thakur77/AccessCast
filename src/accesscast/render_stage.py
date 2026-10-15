"""S13 gate + S14 render per audience + S15 package (PLAN §9 S13–S15, §12.5).

Two modes:
- public: the gate must pass (nothing pending / needs_revision) and every description and easy-read line
  must be approved by a person; output is stamped human_reviewed=true.
- draft: renders only approved/auto_approved items, watermarks "UNREVIEWED DRAFT" on screen and in the
  first description cue, stamps human_reviewed=false. export-site refuses drafts.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from accesscast import constants as C
from accesscast.captions.vtt import PUBLISHABLE, write_vtt
from accesscast.errors import ValidationFailed
from accesscast.events import now_iso
from accesscast.media import mix as M
from accesscast.media.render import mux_standard, render_extended
from accesscast.media.timeline import remap_ms
from accesscast.pipeline import Run, verify_context
from accesscast.project import read_json, sha256_file, write_json, write_jsonl
from accesscast.review import gate
from accesscast.review.store import ReviewStore
from accesscast.schemas import Item, ItemKind
from accesscast.verify import rules_render as R
from accesscast.verify.base import Finding

TRACK_LABELS = {
    "sdh.en": ("captions", "en", "English (deaf and hard of hearing)"),
    "easy.en": ("subtitles", "en", "English (easy-read)"),
    "subs.hi": ("subtitles", "hi", "हिन्दी"),
    "subs.it": ("subtitles", "it", "Italiano"),
    "desc.en": ("descriptions", "en", "Description (English)"),
    "desc.hi": ("descriptions", "hi", "Description (हिन्दी)"),
    "desc.it": ("descriptions", "it", "Description (Italiano)"),
}

AUDIENCE_VERSIONS: dict[str, dict[str, Any]] = {
    "blind.en": {"label": "I can't see the screen", "tracks": ["desc.en", "sdh.en"]},
    "blind_ext.en": {"label": "I can't see the screen (extended)", "tracks": ["desc.en", "sdh.en"], "extended": True},
    "deaf.en": {"label": "I can't hear", "tracks": ["sdh.en"]},
    "easy.en": {"label": "Simpler words, please", "tracks": ["easy.en"]},
    "hi": {"label": "हिन्दी", "tracks": ["subs.hi"]},
    "it": {"label": "Italiano", "tracks": ["subs.it"]},
    "blind.hi": {"label": "हिन्दी + description", "tracks": ["desc.hi", "subs.hi"]},
    "blind.it": {"label": "Italiano + description", "tracks": ["desc.it", "subs.it"]},
}


def _clip_end(it: Item) -> int:
    dur = it.tts.duration_ms if it.tts else 2000
    return it.anchor_ms + C.AD_PAD_BEFORE_MS + dur


def _publishable(it: Item, mode: str) -> bool:
    return it.status in PUBLISHABLE


def _remapper(rows: list[dict[str, Any]]) -> Callable[[int], int]:
    return lambda ms: remap_ms(rows, ms)


def run_gate(run: Run, versions: Sequence[str]) -> gate.GateResult:
    store = ReviewStore(run.project.root)
    res = gate.evaluate(store.merged(), versions, store.state_sha256())
    gate.write_validation(run.project.root, res)
    run.project.events.emit("gate", "done", ok=res.ok, blocking=len(res.blocking), human_reviewed=res.human_reviewed)
    return res


def render_all(run: Run, *, mode: str = "draft", versions: Sequence[str] | None = None,
               target_lufs: float = C.LUFS_WEB) -> dict[str, Any]:
    if mode not in ("draft", "public"):
        raise ValueError("mode must be draft or public")
    proj = run.project
    info = run.info
    store = ReviewStore(proj.root)
    items = store.merged()
    wanted = list(versions or AUDIENCE_VERSIONS)
    # Only render versions whose items exist (hi/it description needs approved English lines first).
    present = {f"{i.kind.value}.{i.lang}" for i in items.values()}
    if "ad_translation.hi" not in present:
        wanted = [v for v in wanted if v != "blind.hi"]
    if "ad_translation.it" not in present:
        wanted = [v for v in wanted if v != "blind.it"]
    res = run_gate(run, wanted)
    public = mode == "public"
    if public:
        gate.check_fresh(proj.root, store)  # raises PermissionError on refusal
        if not res.human_reviewed:
            raise PermissionError("public render needs every description and easy-read line approved by a person")
    watermark = not (public and res.human_reviewed)
    rdir = proj.p("render")
    tdir = proj.p("render", "tracks")
    tmp = proj.p("render", "tmp")
    for d in (rdir, tdir, tmp):
        d.mkdir(parents=True, exist_ok=True)

    def sel(kind: ItemKind, lang: str, *, extended: bool | None = None) -> list[Item]:
        out = [i for i in items.values() if i.kind == kind and i.lang == lang and _publishable(i, mode)]
        if extended is not None:
            out = [i for i in out if i.extended == extended]
        return sorted(out, key=lambda i: i.anchor_ms)

    note = "UNREVIEWED DRAFT: machine-made, not yet approved by a person." if watermark else \
        "Reviewed by a person. Description voiced by synthetic speech."
    # ---------------------------------------------------------------- tracks (source timeline)
    track_files: dict[str, Path] = {}
    track_items: dict[str, list[Item]] = {
        "sdh.en": sel(ItemKind.SDH, "en"), "easy.en": sel(ItemKind.EASY, "en"),
        "subs.hi": sel(ItemKind.SUBTITLE, "hi"), "subs.it": sel(ItemKind.SUBTITLE, "it"),
        "desc.en": sel(ItemKind.AD, "en"), "desc.hi": sel(ItemKind.AD_TRANSLATION, "hi"),
        "desc.it": sel(ItemKind.AD_TRANSLATION, "it"),
    }
    for name, its in track_items.items():
        p = tdir / f"{name}.vtt"
        if watermark and name.startswith("desc") and its:
            its = [its[0].model_copy(update={"final": f"[UNREVIEWED DRAFT] {its[0].text}"}), *its[1:]]
        write_vtt(p, its, end_of=_clip_end if name.startswith("desc") else None, header_note=note)
        track_files[name] = p

    master = proj.p("media", "master48k.wav")
    video = proj.p("media", "source.mp4")
    words = verify_context(proj).words
    speech = [(w.start_ms, w.end_ms) for w in words]
    results: dict[str, Any] = {}
    for v in wanted:
        spec = AUDIENCE_VERSIONS[v]
        findings: list[Finding] = []
        out = rdir / f"{v}.mp4"
        mixed = tmp / f"{v}.mix.wav"
        normed = tmp / f"{v}.norm.wav"
        stem = rdir / f"{v}.desc_stem.wav"
        rendered_ids: list[str] = []
        approved_ids: list[str] = []
        expected_ms = info.duration_ms
        rows: list[dict[str, Any]] | None = None
        lang = v.split(".")[-1] if "." in v else v
        vo: list[Item] = sel(ItemKind.VOICEOVER, lang) if lang in ("hi", "it") else []
        ad: list[Item] = []
        if v in ("blind.en", "blind_ext.en"):
            ad = sel(ItemKind.AD, "en")
        elif v in ("blind.hi", "blind.it"):
            ad = sel(ItemKind.AD_TRANSLATION, lang)
        std_ad = [i for i in ad if not i.extended]
        ext_ad = [i for i in ad if i.extended] if spec.get("extended") else []
        vo_clips = [M.Clip(i.id, proj.p("tts", f"{i.tts.sha256}.wav"), i.anchor_ms, C.VO_DIP_DB) for i in vo if i.tts]
        ad_clips = [M.Clip(i.id, proj.p("tts", f"{i.tts.sha256}.wav"), i.anchor_ms + C.AD_PAD_BEFORE_MS) for i in std_ad if i.tts]
        ext_clips = [M.Clip(i.id, proj.p("tts", f"{i.tts.sha256}.wav"), i.anchor_ms) for i in ext_ad if i.tts]
        rendered_ids = [c.item_id for c in [*vo_clips, *ad_clips, *ext_clips]]
        approved_ids = [i.id for i in [*vo, *std_ad, *ext_ad]]
        if ext_clips:
            rows = M.mix_extended(master, ext_clips, [*vo_clips, *ad_clips], mixed, stem, tmp)
            expected_ms = int(str(rows[-1]["output_end_ms"]))
            write_jsonl(rdir / f"source_to_output.{v}.jsonl", rows)
        else:
            M.mix_standard(master, [*vo_clips, *ad_clips], mixed, stem, tmp)
        loud = M.loudnorm_2pass(mixed, normed, target_lufs)
        if rows is not None:
            render_extended(video, normed, rows, out, watermark=watermark)
            for name in spec["tracks"]:  # remap tracks onto the extended timeline
                src_items = track_items[name]
                write_vtt(tdir / f"{name}.{v}.vtt", src_items, remap=_remapper(rows),
                          end_of=_clip_end if name.startswith("desc") else None, header_note=note)
        else:
            mux_standard(video, normed, out, watermark=watermark)
        findings += R.rn001_duration(out, expected_ms)
        findings += R.rn002_items_match(rendered_ids, approved_ids)
        lf, measured = R.rn003_loudness(out, target_lufs)
        findings += lf
        findings += R.rn005_av_sync(out)
        for name in spec["tracks"]:
            findings += R.rn006_vtt_valid(tdir / (f"{name}.{v}.vtt" if rows is not None else f"{name}.vtt"))
        findings += R.rn007_human_reviewed(res.human_reviewed, public)
        if ad_clips and rows is None:
            findings += R.rn008_no_overlap(stem, speech)
        errors = [f for f in findings if f.severity == "error"]
        if errors:
            out.rename(rdir / f"{v}.REFUSED.mp4")  # never left where the player would pick it up
        results[v] = {
            "ok": not errors, "file": f"render/{v}.mp4" if not errors else None,
            "sha256": sha256_file(rdir / f"{v}.mp4") if not errors else None,
            "duration_ms": expected_ms, "extended": rows is not None,
            "checks": [{"rule": f.rule, "severity": f.severity, "observed": f.observed, "threshold": f.threshold,
                        "passed": False} for f in findings],
            "loudness": {"integrated_lufs": measured.integrated_lufs, "true_peak_dbtp": measured.true_peak_dbtp,
                         "target_lufs": target_lufs},
            "items": rendered_ids, "tracks": spec["tracks"],
        }
        run.project.events.emit("render", "version", version=v, ok=not errors, findings=len(findings))
    shutil.rmtree(tmp, ignore_errors=True)
    summary = {"mode": mode, "watermark": watermark, "human_reviewed": res.human_reviewed and public,
               "review_state_sha256": res.state_sha256, "versions": results, "rendered_at": now_iso()}
    write_json(proj.p("reports", "render.json"), summary)
    if not all(r["ok"] for r in results.values()):
        failed = [k for k, r in results.items() if not r["ok"]]
        run.project.events.emit("render", "refused", versions=failed)
    store.mark_exported(res.state_sha256)
    return summary


def package(run: Run) -> dict[str, Any]:
    """S15: report.json, decisions.json, benchmark.json, cost.json and index.json for the player."""
    from accesscast.reports import build_reports

    return build_reports(run)


def ensure_ok(summary: dict[str, Any]) -> None:
    bad = [k for k, r in summary["versions"].items() if not r["ok"]]
    if bad:
        raise ValidationFailed(f"render checks failed for {bad}")


__all__ = ["AUDIENCE_VERSIONS", "TRACK_LABELS", "ensure_ok", "package", "read_json", "render_all", "run_gate"]
