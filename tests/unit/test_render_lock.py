"""One render per project at a time: a second render is refused in plain words instead of racing the first one's
working files (incident 2026-10-18: a review-app render crashed while a command-line render of the same project ran)."""

from __future__ import annotations

from pathlib import Path

import pytest

from accesscast.render_stage import RenderBusy, _render_lock


def test_a_second_render_of_the_same_project_is_refused(tmp_path: Path) -> None:
    with _render_lock(tmp_path), pytest.raises(RenderBusy, match="another render"), _render_lock(tmp_path):
        pass


def test_the_lock_is_released_after_a_render_even_when_it_fails(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError), _render_lock(tmp_path):
        raise RuntimeError("render broke")
    with _render_lock(tmp_path):  # free again
        pass


def test_a_busy_render_is_a_refusal_so_the_app_answers_409_not_500() -> None:
    assert issubclass(RenderBusy, PermissionError)
