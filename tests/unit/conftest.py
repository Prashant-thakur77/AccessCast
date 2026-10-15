from __future__ import annotations

from typing import Any

import pytest

from accesscast.schemas import (
    Budget,
    Character,
    Item,
    ItemKind,
    OnScreenText,
    SceneEvidence,
    Slot,
    VisibleFact,
    Word,
)
from accesscast.verify.base import VerifyContext


def make_words(spec: list[tuple[str, int, int]]) -> list[Word]:
    return [Word(i=i, w=w, start_ms=a, end_ms=b) for i, (w, a, b) in enumerate(spec)]


DIALOGUE = make_words(
    [
        ("I", 0, 200),
        ("am", 220, 400),
        ("opening", 420, 900),
        ("the", 920, 1000),
        ("settings", 1020, 1500),
        ("menu", 1520, 1900),
        ("Thanks", 9000, 9400),
        ("for", 9420, 9600),
        ("watching", 9620, 10100),
    ]
)


def make_evidence(**kw: Any) -> SceneEvidence:
    base: dict[str, Any] = dict(
        scene_id="SC001",
        frames=["f00.jpg", "f01.jpg", "f02.jpg", "f03.jpg"],
        frame_ms=[1000, 3000, 5000, 7000],
        setting="A small office with a desk by a window.",
        characters=[Character(cid="C0001", appearance="woman with short grey hair, blue cardigan")],
        visible_facts=[
            VisibleFact(fid="F001", frames=[1, 2], text="The woman presses the Tab key on a laptop."),
            VisibleFact(fid="F002", frames=[2], text="A dog opens its mouth wide."),
        ],
        on_screen_text=[OnScreenText(text="Keyboard Compatibility", frame=0, kind="title", ocr_agrees=True)],
    )
    base.update(kw)
    return SceneEvidence(**base)


def make_item(text: str, **kw: Any) -> Item:
    base: dict[str, Any] = dict(
        id="ad.en.0001",
        kind=ItemKind.AD,
        lang="en",
        audiences=["blind"],
        scene_id="SC001",
        gap_id="G0001",
        anchor_ms=2100,
        slot=Slot(start_ms=2100, end_ms=8800),
        budget=Budget(words_max=12, seconds_max=6.0, wps_voice=2.6),
        fact_ids=["F001"],
        draft=text,
    )
    base.update(kw)
    return Item(**base)


@pytest.fixture
def ctx() -> VerifyContext:
    ev = make_evidence()
    return VerifyContext(lang="en", words=list(DIALOGUE), evidence={"SC001": ev}, guard_ms=120, wps_voice=2.6)
