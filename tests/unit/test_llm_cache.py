import httpx

from accesscast.config import load_settings
from accesscast.llm.client import LlmClient, LlmRequest


def _client(calls: list[int]) -> LlmClient:
    s = load_settings(worker_mode="real", local_base_url="http://test/v1", local_model="gemma-4-31b")
    c = LlmClient(s, provider="local", strict_provider=True)

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(
            200,
            json={
                "model": "gemma-4-31b",
                "choices": [{"message": {"content": '{"text": "ok"}'}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2},
            },
        )

    c._http = httpx.Client(transport=httpx.MockTransport(handler))
    return c


def test_cache_is_off_unless_asked(monkeypatch):
    monkeypatch.delenv("ACCESSCAST_LLM_CACHE", raising=False)
    calls: list[int] = []
    c = _client(calls)
    c.call(LlmRequest("repair_ad", {"x": 1}, seed=1))
    c.call(LlmRequest("repair_ad", {"x": 1}, seed=1))
    assert len(calls) == 2


def test_cache_replays_only_identical_requests(monkeypatch, tmp_path):
    monkeypatch.setenv("ACCESSCAST_LLM_CACHE", str(tmp_path))
    calls: list[int] = []
    c = _client(calls)
    a = c.call(LlmRequest("repair_ad", {"x": 1}, seed=1))
    b = c.call(LlmRequest("repair_ad", {"x": 1}, seed=1))
    assert len(calls) == 1 and b.obj == a.obj and b.attempts == 0 and b.tokens_in == 3
    c.call(LlmRequest("repair_ad", {"x": 1}, seed=2))  # another seed is another request
    c.call(LlmRequest("repair_ad", {"x": 2}, seed=1))
    assert len(calls) == 3


def test_circuit_opens_after_a_call_fails_every_retry(monkeypatch):
    import pytest

    from accesscast import constants as C
    from accesscast.errors import ModelEndpointError

    monkeypatch.setattr(C, "LLM_MAX_RETRIES", 1)
    monkeypatch.setattr(LlmClient, "_backoff", staticmethod(lambda attempt, retry_after: None))
    s = load_settings(worker_mode="real", local_base_url="http://test/v1", local_model="gemma-4-31b")
    c = LlmClient(s, provider="local", strict_provider=True)
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(503, json={"error": "no_available_workers"})

    c._http = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(ModelEndpointError):
        c.call(LlmRequest("repair_ad", {"x": 1}))
    n = len(calls)
    with pytest.raises(ModelEndpointError, match="marked down"):
        c.call(LlmRequest("repair_ad", {"x": 2}))
    assert len(calls) == n  # the second call never reached the endpoint
