"""OpenAI-compatible chat client for Gemma (PLAN §14.3).

Providers: `local` (vLLM through the SSH tunnel or on the droplet), `local_audio` (E4B), `tokenfactory`,
and `fake` (canned, deterministic outputs for fake worker mode). Never falls back between providers when
strict; never logs keys or image/audio bytes.
"""

from __future__ import annotations

import base64
import json
import os
import random
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from accesscast import constants as C
from accesscast.config import Settings
from accesscast.errors import LlmOutputError, ModelEndpointError
from accesscast.events import now_iso
from accesscast.llm.json_utils import extract_last_object
from accesscast.llm.promptlib import Prompt, load_prompt
from accesscast.project import canonical_json


@dataclass
class LlmRequest:
    prompt_id: str
    payload: dict[str, Any]
    seed: int | None = None
    temperature: float | None = None
    images: list[Path] = field(default_factory=list)
    audio: Path | None = None
    label: str = ""


@dataclass
class LlmResponse:
    obj: dict[str, Any]
    raw: str
    provider: str
    served_model_id: str
    prompt: Prompt
    seed: int | None
    temperature: float
    tokens_in: int
    tokens_out: int
    latency_s: float
    attempts: int


class RateLimiter:
    """Per-provider concurrency semaphore plus a sliding-window requests-per-minute limiter."""

    def __init__(self, concurrency: int, rpm: int) -> None:
        self.sem = threading.BoundedSemaphore(max(1, concurrency))
        self.rpm = rpm
        self.times: deque[float] = deque()
        self.lock = threading.Lock()

    def wait_turn(self) -> None:
        if self.rpm <= 0:
            return
        while True:
            with self.lock:
                now = time.monotonic()
                while self.times and now - self.times[0] > 60:
                    self.times.popleft()
                if len(self.times) < self.rpm:
                    self.times.append(now)
                    return
                wait = 60 - (now - self.times[0])
            time.sleep(max(wait, 0.05))


FakeHandler = Callable[[Prompt, LlmRequest], dict[str, Any]]


class LlmClient:
    def __init__(
        self,
        settings: Settings,
        *,
        provider: str = "local",
        strict_provider: bool = False,
        log_path: Path | None = None,
        fake_handler: FakeHandler | None = None,
    ) -> None:
        self.settings = settings
        self.provider = "fake" if settings.worker_mode == "fake" and provider != "fake_off" else provider
        self.strict = strict_provider
        self.log_path = log_path
        self.fake_handler = fake_handler
        self._http = httpx.Client(timeout=C.LLM_TIMEOUT_S)
        self._limiters: dict[str, RateLimiter] = {
            "local": RateLimiter(64, 0),
            "local_audio": RateLimiter(32, 0),
            "tokenfactory": RateLimiter(settings.tf_max_concurrency, settings.tf_rpm),
            "fake": RateLimiter(64, 0),
        }
        self._log_lock = threading.Lock()

    # ------------------------------------------------------------------ endpoints
    def _endpoint(self, provider: str) -> tuple[str, str, dict[str, str]]:
        s = self.settings
        if provider == "local":
            return s.local_base_url, s.local_model, {}
        if provider == "local_audio":
            return s.local_audio_base_url, s.local_audio_model, {}
        if provider == "tokenfactory":
            if not s.tf_base_url or not s.tf_api_key:
                raise ModelEndpointError("Token Factory not configured (AMD_TF_BASE_URL / AMD_TF_API_KEY)")
            return s.tf_base_url, "Gemma-4-31B-IT", {"Authorization": f"Bearer {s.tf_api_key}"}
        raise ModelEndpointError(f"unknown provider {provider!r}")

    def list_models(self, provider: str) -> list[str]:
        base, _, headers = self._endpoint(provider)
        r = self._http.get(f"{base.rstrip('/')}/models", headers=headers, timeout=15)
        r.raise_for_status()
        return [m["id"] for m in r.json().get("data", [])]

    # ------------------------------------------------------------------ messages
    @staticmethod
    def _image_part(path: Path) -> dict[str, Any]:
        b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        return {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}

    @staticmethod
    def _audio_part(path: Path) -> dict[str, Any]:
        b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        return {"type": "audio_url", "audio_url": {"url": f"data:audio/wav;base64,{b64}"}}

    def _messages(self, prompt: Prompt, req: LlmRequest) -> list[dict[str, Any]]:
        user: list[dict[str, Any]] = []
        for img in req.images:
            user.append(self._image_part(img))
        if req.audio is not None:
            user.append(self._audio_part(req.audio))
        user.append({"type": "text", "text": canonical_json(req.payload)})
        return [{"role": "system", "content": prompt.system}, {"role": "user", "content": user}]

    # ------------------------------------------------------------------ call
    def call(self, req: LlmRequest, *, provider: str | None = None) -> LlmResponse:
        prov = provider or self.provider
        if self.settings.worker_mode == "fake":
            prov = "fake"
        prompt = load_prompt(req.prompt_id)
        temp = prompt.temperature if req.temperature is None else req.temperature
        lim = self._limiters.get(prov, self._limiters["local"])
        t0 = time.perf_counter()
        status = "ok"
        raw = ""
        served = ""
        tin = tout = 0
        attempts = 0
        try:
            with lim.sem:
                if prov == "fake":
                    attempts = 1
                    if self.fake_handler is None:
                        raise ModelEndpointError("fake mode without a fake handler")
                    obj = self.fake_handler(prompt, req)
                    raw = json.dumps(obj, ensure_ascii=False)
                    served = "fake/canned"
                    tin, tout = len(canonical_json(req.payload)) // 4, len(raw) // 4
                else:
                    raw, served, tin, tout, attempts = self._http_call(prov, prompt, req, temp, lim)
                    try:
                        obj = extract_last_object(raw)
                    except LlmOutputError:
                        # one retry asking for valid JSON only (PLAN §14.3), then fail closed
                        retry = LlmRequest(
                            **{**req.__dict__, "payload": {**req.payload, "_note": "Return valid JSON only."}}
                        )
                        raw, served, tin2, tout2, a2 = self._http_call(prov, prompt, retry, temp, lim)
                        tin, tout, attempts = tin + tin2, tout + tout2, attempts + a2
                        obj = extract_last_object(raw)
            return LlmResponse(
                obj, raw, prov, served, prompt, req.seed, temp, tin, tout, time.perf_counter() - t0, attempts
            )
        except LlmOutputError:
            status = "bad_json"
            raise
        except ModelEndpointError:
            status = "endpoint_error"
            raise
        finally:
            self._log(
                {
                    "ts": now_iso(),
                    "provider": prov,
                    "served_model_id": served,
                    "prompt_id": prompt.ref,
                    "prompt_sha": prompt.sha256,
                    "temperature": temp,
                    "seed": req.seed,
                    "label": req.label,
                    "tokens_in": tin,
                    "tokens_out": tout,
                    "latency_s": round(time.perf_counter() - t0, 3),
                    "status": status,
                    "attempts": attempts,
                    "n_images": len(req.images),
                    "has_audio": req.audio is not None,
                    "output_head": raw[: C.LLM_LOG_TRUNCATE],
                }
            )

    def _http_call(
        self, prov: str, prompt: Prompt, req: LlmRequest, temp: float, lim: RateLimiter
    ) -> tuple[str, str, int, int, int]:
        base, model, headers = self._endpoint(prov)
        body: dict[str, Any] = {
            "model": model,
            "messages": self._messages(prompt, req),
            "temperature": temp,
            "max_tokens": prompt.max_tokens,
            "response_format": {"type": "json_object"},
        }
        if req.seed is not None:
            body["seed"] = req.seed
        rec = os.environ.get("ACCESSCAST_RECORD_REPLAY")
        if rec and not req.images and req.audio is None:  # E13 replay set: text-only requests, never image bytes
            Path(rec).mkdir(parents=True, exist_ok=True)
            with self._log_lock, (Path(rec) / f"{prompt.id}.jsonl").open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({k: v for k, v in body.items() if k != "model"}, ensure_ascii=False) + "\n")
        if prov != "tokenfactory":  # Token Factory silently drops chat_template_kwargs (SayAgain's finding)
            body["chat_template_kwargs"] = {"enable_thinking": False}
        last: Exception | None = None
        for attempt in range(1, C.LLM_MAX_RETRIES + 2):
            lim.wait_turn()
            try:
                r = self._http.post(f"{base.rstrip('/')}/chat/completions", json=body, headers=headers)
            except (httpx.TimeoutException, httpx.TransportError) as e:
                last = e
                self._backoff(attempt, None)
                continue
            if r.status_code in C.LLM_RETRY_STATUS:
                last = ModelEndpointError(f"HTTP {r.status_code}")
                self._backoff(attempt, r.headers.get("retry-after"))
                continue
            if r.status_code >= 400:
                raise ModelEndpointError(f"HTTP {r.status_code} from {prov}: {r.text[:200]}")
            data = r.json()
            try:
                text = data["choices"][0]["message"]["content"] or ""
            except (KeyError, IndexError, TypeError) as e:
                raise LlmOutputError(f"malformed response envelope: {e}") from e
            usage = data.get("usage") or {}
            return (
                text,
                str(data.get("model", model)),
                int(usage.get("prompt_tokens", 0)),
                int(usage.get("completion_tokens", 0)),
                attempt,
            )
        raise ModelEndpointError(f"{prov} failed after retries: {last}")

    @staticmethod
    def _backoff(attempt: int, retry_after: str | None) -> None:
        if attempt > C.LLM_MAX_RETRIES:
            return
        delay = min(60.0, 2.0**attempt) + random.uniform(0, 0.5)
        if retry_after:
            try:
                delay = min(60.0, float(retry_after))
            except ValueError:
                pass
        time.sleep(delay)

    def _log(self, rec: dict[str, Any]) -> None:
        if self.log_path is None:
            return
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self._log_lock, self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
