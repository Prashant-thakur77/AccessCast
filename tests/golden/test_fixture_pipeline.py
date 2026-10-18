"""Golden: the whole pipeline in fake mode on our 20-second synthetic clip, end to end, in a fresh project folder.

Fake mode replaces the model calls with canned answers, so this tests our own code: every stage runs and writes its
lines, the draft render makes every version with valid tracks, nothing published carries an open violation, and a
public render is refused while no person has approved the lines. Skipped where FFmpeg is missing (as in CI)."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs FFmpeg"),
    # about two and a half minutes: CI runs the fast suite; this runs locally and in scripts/test_stats.py
    pytest.mark.skipif(os.environ.get("CI") == "true", reason="slow end-to-end run, local only"),
]


@pytest.fixture(scope="module")
def run(tmp_path_factory: pytest.TempPathFactory):  # type: ignore[no-untyped-def]
    mp = pytest.MonkeyPatch()
    mp.setenv("ACCESSCAST_WORKER_MODE", "fake")
    mp.setenv("ACCESSCAST_REVIEW_POLICY", "prototype-auto")
    mp.setenv("ACCESSCAST_PROJECTS_DIR", str(tmp_path_factory.mktemp("projects")))
    mp.delenv("ACCESSCAST_LLM_CACHE", raising=False)
    from accesscast.config import load_settings
    from accesscast.pipeline import FIXTURE_DIR, run_all

    r = run_all(load_settings(), FIXTURE_DIR / "source.mp4")
    yield r
    mp.undo()


def _items(r, name: str) -> list[dict]:  # type: ignore[no-untyped-def]
    p = r.project.p("items", f"{name}.jsonl")
    return (
        [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()] if p.exists() else []
    )


def test_every_stage_writes_lines_for_every_language(run) -> None:  # type: ignore[no-untyped-def]
    from accesscast import constants as C

    for name in ("ad.en", "sdh.en", "easy.en", *(f"subs.{lang}" for lang in C.TRANSLATION_LANGS)):
        assert _items(run, name), f"no lines in {name}"


def test_nothing_ready_for_review_carries_an_open_violation(run) -> None:  # type: ignore[no-untyped-def]
    from accesscast.review.store import ITEM_FILES

    for name in ITEM_FILES:
        for it in _items(run, name):
            if it["status"] in ("pending", "approved", "auto_approved"):
                assert not it.get("violations"), (name, it["id"], it.get("violations"))


def test_a_draft_render_makes_every_version_with_valid_tracks(run) -> None:  # type: ignore[no-untyped-def]
    from accesscast.render_stage import project_versions, render_all
    from accesscast.review.store import ReviewStore

    render_all(run, mode="draft")
    versions = project_versions(ReviewStore(run.project.root).merged())
    assert versions
    rdir: Path = run.project.p("render")
    for v in versions:
        assert (rdir / f"{v}.mp4").stat().st_size > 0, v
    for vtt in (rdir / "tracks").glob("*.vtt"):
        assert vtt.read_text(encoding="utf-8").startswith("WEBVTT"), vtt.name


def test_a_public_render_is_refused_until_a_person_approves(run) -> None:  # type: ignore[no-untyped-def]
    from accesscast.render_stage import render_all

    with pytest.raises(PermissionError):
        render_all(run, mode="public")
