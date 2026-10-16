import httpx
import pytest

from accesscast.config import load_settings
from accesscast.errors import ModelEndpointError
from accesscast.llm.client import LlmClient, LlmRequest


def _client(model_reply: str, strict: bool) -> LlmClient:
    s = load_settings(worker_mode="real", local_base_url="http://test/v1", local_model="gemma-4-31b")
    c = LlmClient(s, provider="local", strict_provider=strict)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"model": model_reply, "choices": [{"message": {"content": '{"text": "ok"}'}}],
                                         "usage": {"prompt_tokens": 1, "completion_tokens": 1}})

    c._http = httpx.Client(transport=httpx.MockTransport(handler))
    return c


def test_strict_refuses_another_model():
    with pytest.raises(ModelEndpointError):
        _client("gemma-4-26b", strict=True).call(LlmRequest("repair_ad", {"x": 1}))


def test_strict_accepts_the_requested_model():
    r = _client("gemma-4-31b", strict=True).call(LlmRequest("repair_ad", {"x": 1}))
    assert r.served_model_id == "gemma-4-31b" and r.obj == {"text": "ok"}
