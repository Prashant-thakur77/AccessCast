"""S5 visual evidence (PLAN §9 S5): frames per scene → Gemma lists what is visible (temperature 0) →
code checks the list. Failures re-ask once, then the scene is `evidence_failed` and its gaps go to review.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from accesscast import constants as C
from accesscast.confidence import reject_model_confidence
from accesscast.errors import LlmOutputError, ModelEndpointError
from accesscast.llm.client import LlmClient, LlmRequest
from accesscast.media.ingest import extract_frame
from accesscast.schemas import (
    Character,
    Gap,
    ModelRef,
    OnScreenText,
    Scene,
    SceneEvidence,
    VisibleFact,
    Word,
)
from accesscast.verify import nlp


def frame_times(scene: Scene, gaps: Sequence[Gap], video: Path | None) -> list[int]:
    """Anchors at 0.05/0.35/0.65/0.95 of the scene, + up to 2 high-change frames, + each gap start."""
    a, b = scene.start_ms, scene.end_ms
    length = b - a
    times = [a + round(f * length) for f in C.EVIDENCE_ANCHORS]
    min_sep = max(500, round(0.08 * length))
    if video is not None and length > 2000:
        # sample 12 frames, pick the 2 with the largest change from their predecessor
        probes = [a + round(length * (i + 0.5) / 12) for i in range(12)]
        try:
            imgs = [_tiny(video, t) for t in probes]
            diffs = [0.0] + [float(np.abs(imgs[i] - imgs[i - 1]).mean()) for i in range(1, len(imgs))]
            for i in np.argsort(diffs)[::-1]:
                t = probes[int(i)]
                if diffs[int(i)] > 0 and all(abs(t - x) >= min_sep for x in times):
                    times.append(t)
                if len(times) >= len(C.EVIDENCE_ANCHORS) + C.EVIDENCE_HIGH_CHANGE_FRAMES:
                    break
        except Exception:
            pass  # high-change frames are optional; anchors are enough
    for g in gaps:
        if g.scene_id == scene.scene_id and a <= g.start_ms < b:
            t = min(b - 1, g.start_ms + 100)
            if all(abs(t - x) >= 250 for x in times):
                times.append(t)
    # 16 = vLLM --limit-mm-per-prompt; smaller local servers can set ACCESSCAST_MAX_IMAGES (integration runs only)
    return sorted(times)[: int(os.environ.get("ACCESSCAST_MAX_IMAGES", "16"))]


def _tiny(video: Path, t_ms: int) -> np.ndarray:
    tmp = Path(str(video) + f".tiny{t_ms}.jpg")
    extract_frame(video, t_ms, tmp, px=64)
    try:
        return np.asarray(Image.open(tmp).convert("L").resize((32, 18)), dtype=np.float32)
    finally:
        tmp.unlink(missing_ok=True)


def ocr_frame(path: Path, langs: str = "eng+hin+ita") -> list[tuple[str, float]]:
    """Tesseract lines with mean confidence. Returns [] if tesseract is not installed (doctor reports it)."""
    exe = shutil.which("tesseract")
    if exe is None:
        return []
    p = subprocess.run([exe, str(path), "-", "-l", langs, "tsv"], capture_output=True, text=True, check=False)
    if p.returncode != 0:
        p = subprocess.run([exe, str(path), "-", "tsv"], capture_output=True, text=True, check=False)
    lines: dict[tuple[str, str, str], list[tuple[str, float]]] = {}
    for row in p.stdout.splitlines()[1:]:
        cols = row.split("\t")
        if len(cols) < 12 or not cols[11].strip():
            continue
        try:
            conf = float(cols[10])
        except ValueError:
            continue
        lines.setdefault((cols[2], cols[3], cols[4]), []).append((cols[11].strip(), conf))
    out = []
    for words in lines.values():
        text = " ".join(w for w, _ in words)
        out.append((text, sum(c for _, c in words) / len(words)))
    return out


def check_evidence(
    raw: dict[str, Any], scene: Scene, n_frames: int, transcript: str, ocr_text: str
) -> tuple[SceneEvidence, list[str], list[str]]:
    """Validate and clean a model evidence object. Returns (evidence, errors, warnings)."""
    errors: list[str] = []
    warnings: list[str] = []
    reject_model_confidence(raw)
    facts: list[VisibleFact] = []
    for i, f in enumerate(raw.get("visible_facts") or []):
        try:
            frames = [int(x) for x in f.get("frames") or []]
            vf = VisibleFact(
                fid=str(f.get("fid") or f"F{i + 1:03d}"),
                frames=frames,
                text=str(f["text"]).strip(),
                priority=int(f.get("priority", 4)),
                important=bool(f.get("important", False)),
            )
        except (KeyError, TypeError, ValueError) as e:
            errors.append(f"fact {i}: malformed ({e})")
            continue
        if any(x < 0 or x >= n_frames for x in vf.frames):
            errors.append(f"{vf.fid}: frame index out of range")
        if len(nlp.sentences(vf.text)) != 1:
            errors.append(f"{vf.fid}: not exactly one sentence")
        if not 1 <= vf.priority <= 5:
            vf = vf.model_copy(update={"priority": 4})
        facts.append(vf)
    limit = C.max_facts((scene.end_ms - scene.start_ms) / 1000)
    if len(facts) > limit:
        errors.append(f"{len(facts)} facts > {limit}")
    if not facts:
        errors.append("no visible facts")
    chars: list[Character] = []
    allowed_text = (transcript + " " + ocr_text).lower()
    for c in raw.get("characters") or []:
        try:
            ch = Character(
                cid=str(c["cid"]),
                appearance=str(c.get("appearance", "")),
                name=c.get("name"),
                name_source=c.get("name_source"),
            )
        except (KeyError, TypeError) as e:
            errors.append(f"character malformed ({e})")
            continue
        if ch.name:
            ok_src = ch.name_source in C.NAME_SOURCES_ALLOWED
            ok_txt = all(part.lower() in allowed_text for part in ch.name.split())
            if not (ok_src and ok_txt):
                warnings.append(
                    f"{ch.cid}: name {ch.name!r} removed (source={ch.name_source}, in transcript/OCR={ok_txt})"
                )
                ch = ch.model_copy(update={"name": None, "name_source": None})
        chars.append(ch)
    ost: list[OnScreenText] = []
    for raw_t in raw.get("on_screen_text") or []:
        try:
            ost.append(
                OnScreenText(
                    text=str(raw_t["text"]), frame=int(raw_t.get("frame", 0)), kind=str(raw_t.get("kind", "other"))
                )
            )
        except (KeyError, TypeError, ValueError):
            warnings.append("on-screen text item malformed; dropped")
    ev = SceneEvidence(
        scene_id=scene.scene_id,
        frames=[],
        setting=str(raw.get("setting", "")),
        characters=chars,
        visible_facts=facts,
        on_screen_text=ost,
        inferences=[str(x) for x in raw.get("inferences") or []],
        uncertainties=[str(x) for x in raw.get("uncertainties") or []],
        warnings=warnings,
    )
    return ev, errors, warnings


def merge_ocr(ev: SceneEvidence, ocr_lines: list[tuple[int, str, float]]) -> SceneEvidence:
    """Mark model text that OCR also found; add high-confidence OCR text the model missed (EV001)."""

    def norm(s: str) -> str:
        return re.sub(r"[^\w]+", " ", s.lower()).strip()

    ocr_norm = [(f, norm(t), t, c) for f, t, c in ocr_lines]
    ost = []
    for t in ev.on_screen_text:
        nt = norm(t.text)
        agrees = bool(nt) and any(nt in o or o in nt for _, o, _, _ in ocr_norm if len(o) >= 3)
        ost.append(t.model_copy(update={"ocr_agrees": agrees}))
    warnings = list(ev.warnings)
    have = " ".join(norm(t.text) for t in ost)
    for f, o, line, c in ocr_norm:
        if c >= 80 and len(o.split()) >= 2 and o not in have:
            ost.append(OnScreenText(text=line, frame=f, kind="other", ocr_agrees=True, source="ocr"))
            warnings.append(f"EV001 OCR_TEXT_MISSED_BY_GEMMA: {line[:40]!r}")
            have += " " + o
    return ev.model_copy(update={"on_screen_text": ost, "warnings": warnings})


def gather_evidence(
    client: LlmClient,
    scene: Scene,
    scene_index: int,
    gaps: Sequence[Gap],
    words: Sequence[Word],
    cast: list[Character],
    video: Path,
    out_dir: Path,
    *,
    use_ocr: bool,
) -> SceneEvidence:
    times = frame_times(scene, gaps, video)
    paths = [extract_frame(video, t, out_dir / f"f{i:02d}.jpg") for i, t in enumerate(times)]
    transcript = " ".join(w.w for w in words if scene.start_ms <= w.start_ms < scene.end_ms)
    ocr_lines: list[tuple[int, str, float]] = []
    if use_ocr:
        for i, p in enumerate(paths):
            ocr_lines += [(i, t, c) for t, c in ocr_frame(p)]
    ocr_text = " ".join(t for _, t, _ in ocr_lines)
    payload = {
        "scene_index": scene_index,
        "frame_times_ms": times,
        "dialogue": transcript,
        "cast": [{"cid": c.cid, "appearance": c.appearance, "name": c.name} for c in cast],
        "max_facts": C.max_facts((scene.end_ms - scene.start_ms) / 1000),
    }
    last_err = ""
    for attempt in range(2):
        try:
            resp = client.call(
                LlmRequest(
                    "evidence", payload, seed=0, images=paths, label=f"evidence:{scene.scene_id}:{attempt}"
                )
            )
            ev, errors, _ = check_evidence(resp.obj, scene, len(paths), transcript, ocr_text)
        except (LlmOutputError, ModelEndpointError) as e:
            last_err = str(e)
            continue
        except Exception as e:  # malformed shape (e.g. facts as strings): re-ask once, then evidence_failed
            last_err = f"malformed evidence: {type(e).__name__}: {str(e)[:120]}"
            continue
        if errors:
            last_err = "; ".join(errors)
            payload = {**payload, "_previous_problems": errors}
            continue
        ev = merge_ocr(ev, ocr_lines)
        return ev.model_copy(
            update={
                "frames": [p.name for p in paths],
                "frame_ms": times,
                "model": ModelRef(
                    name="google/gemma-4-31B-it",
                    endpoint=resp.provider,
                    temperature=resp.temperature,
                    seed=0,
                    prompt_id=resp.prompt.ref,
                    prompt_sha=resp.prompt.sha256,
                    served_model_id=resp.served_model_id,
                ),
            }
        )
    return SceneEvidence(
        scene_id=scene.scene_id,
        frames=[p.name for p in paths],
        frame_ms=times,
        status="evidence_failed",
        warnings=[f"evidence failed after 2 tries: {last_err[:200]}"],
    )
