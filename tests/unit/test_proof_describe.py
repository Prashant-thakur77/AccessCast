"""POST /api/describe: a visitor's picture, Gemma's facts and one checked description line. The model is the canned
fake (no network); these tests check the API's own rules: what it accepts, that it fails closed, and its limits."""

import base64

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from accesscast import constants as C
from accesscast.llm import client as llm_client
from accesscast.llm.fake import FakeModel
from accesscast.proof import api

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64


def data_url(raw: bytes, mime: str = "image/jpeg") -> str:
    return f"data:{mime};base64," + base64.b64encode(raw).decode()


def test_a_small_jpeg_is_accepted() -> None:
    mime, raw = api.decode_image(data_url(JPEG))
    assert mime == "image/jpeg" and raw == JPEG


@pytest.mark.parametrize(
    ("url", "status"),
    [
        ("", 422),
        ("not a data url", 422),
        (data_url(b"GIF89a" + b"\x00" * 10, "image/gif"), 422),  # a type we do not take
        (data_url(b"\x00\x01\x02\x03" * 8), 422),  # says JPEG, is not one
        (data_url(JPEG + b"\x00" * (C.DESCRIBE_MAX_BYTES + 10)), 413),
    ],
)
def test_anything_else_is_refused_before_any_model_call(url: str, status: int) -> None:
    with pytest.raises(HTTPException) as e:
        api.decode_image(url)
    assert e.value.status_code == status


def test_the_picture_is_one_scene_with_one_silent_pause() -> None:
    from accesscast.schemas import SceneEvidence

    ev = SceneEvidence.model_validate(
        FakeModel(None)._evidence({}) | {"scene_id": "SC001", "frames": ["f00.jpg"], "frame_ms": [4000]}
    )
    ctx, gap = api.picture_context(ev)
    assert (gap.start_ms, gap.end_ms) == (0, C.DESCRIBE_PAUSE_MS)
    assert ctx.words == [] and list(ctx.evidence) == ["SC001"]


@pytest.fixture
def app_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ACCESSCAST_WORKER_MODE", "fake")
    monkeypatch.setenv("AMD_TF_API_KEY", "")
    api._hits.clear()
    return TestClient(api.create_app())


def test_a_picture_gets_facts_and_one_checked_line(
    app_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = llm_client.LlmClient
    monkeypatch.setattr(api, "LlmClient", lambda s, **kw: real(s, **kw, fake_handler=FakeModel(None)))
    r = app_client.post("/api/describe", json={"image": data_url(JPEG)})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["evidence_ok"] and body["facts"]
    assert len(body["lines"]) == 1  # one line for one picture, inside a word budget for the pause
    assert body["lines"][0]["budget_words"] > 0
    for line in body["lines"]:
        # published only if it passed every check; otherwise it goes to a person, never out by default
        assert (line["published"] is None) == line["to_person"]
        assert line["repairs"] <= C.DESCRIBE_MAX_REPAIRS


def test_no_answer_from_the_model_means_nothing_is_published(app_client: TestClient) -> None:
    # fake mode without a fake model: every call fails, so the evidence fails closed and no line is written
    r = app_client.post("/api/describe", json={"image": data_url(JPEG)})
    assert r.status_code == 200
    body = r.json()
    assert body["evidence_ok"] is False and body["facts"] == [] and body["lines"] == []
    assert body["evidence_problem"]


def test_each_address_has_an_hourly_limit(app_client: TestClient) -> None:
    for _ in range(C.DESCRIBE_PER_HOUR):
        assert app_client.post("/api/describe", json={"image": "bad"}).status_code == 422
    assert app_client.post("/api/describe", json={"image": data_url(JPEG)}).status_code == 429


def test_too_little_time_left_means_no_line_and_a_plain_reason(
    app_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = llm_client.LlmClient
    monkeypatch.setattr(api, "LlmClient", lambda s, **kw: real(s, **kw, fake_handler=FakeModel(None)))
    monkeypatch.setattr(C, "DESCRIBE_DEADLINE_S", 0)  # as if looking at the picture used up the time
    body = app_client.post("/api/describe", json={"image": data_url(JPEG)}).json()
    assert body["facts"] and body["lines"] == []
    assert "goes to a person" in body["note"]
