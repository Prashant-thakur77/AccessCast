"""OpenAI-compatible chat client for Gemma (PLAN §14.3).

Providers: `local` (vLLM through the SSH tunnel or on the droplet), `local_audio` (E4B), `tokenfactory`,
and `fake` (canned, deterministic outputs for fake worker mode). Never falls back between providers when
strict; never logs keys or image/audio bytes.
"""

from __future__ import annotations

import base64
import hashlib
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
        timeout_s: float | None = None,
        max_retries: int | None = None,
    ) -> None:
        """`timeout_s` / `max_retries` override the pipeline's patient defaults for callers with a hard deadline
        (the live site's function stops at 120 s): a slow call then fails closed sooner, it never passes."""
        self.settings = settings
        self.max_retries = C.LLM_MAX_RETRIES if max_retries is None else max_retries
        self.provider = "fake" if settings.worker_mode == "fake" and provider != "fake_off" else provider
        self.strict = strict_provider
        self.log_path = log_path
        self.fake_handler = fake_handler
        self._http = httpx.Client(timeout=C.LLM_TIMEOUT_S if timeout_s is None else timeout_s)
        self._down_until: dict[str, float] = {}
        self._limiters: dict[str, RateLimiter] = {
            "local": RateLimiter(64, 0),
            "local_audio": RateLimiter(32, 0),
            "tokenfactory": RateLimiter(settings.tf_max_concurrency, settings.tf_rpm),
            "aistudio": RateLimiter(4, settings.gai_rpm),
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
            return s.tf_base_url, s.tf_model, {"Authorization": f"Bearer {s.tf_api_key}"}
        if provider == "aistudio":  # backup only, never mixed with another provider inside one experiment
            if not s.gai_api_key:
                raise ModelEndpointError("Google AI Studio not configured (GEMINI_API_KEY)")
            return s.gai_base_url, s.gai_model, {"Authorization": f"Bearer {s.gai_api_key}"}
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

    def _messages(self, prompt: Prompt, req: LlmRequest, fold_system: bool = False) -> list[dict[str, Any]]:
        user: list[dict[str, Any]] = []
        if (
            fold_system
        ):  # Gemma on Google AI Studio takes no system role: the same text goes first in the user turn
            user.append({"type": "text", "text": prompt.system})
        for img in req.images:
            user.append(self._image_part(img))
        if req.audio is not None:
            user.append(self._audio_part(req.audio))
        user.append({"type": "text", "text": canonical_json(req.payload)})
        if fold_system:
            return [{"role": "user", "content": user}]
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
        error = ""
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
        except ModelEndpointError as e:
            status = "endpoint_error"
            error = str(e)[:200]  # why: rate limit, outage or timeout (never a key; messages carry no headers)
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
                    **({"error": error} if error else {}),
                }
            )

    def _http_call(
        self, prov: str, prompt: Prompt, req: LlmRequest, temp: float, lim: RateLimiter
    ) -> tuple[str, str, int, int, int]:
        base, model, headers = self._endpoint(prov)
        body: dict[str, Any] = {
            "model": model,
            "messages": self._messages(prompt, req, fold_system=prov == "aistudio"),
            "temperature": temp,
            "max_tokens": prompt.max_tokens,
            "response_format": {"type": "json_object"},
        }
        if prov == "aistudio":  # no JSON mode for Gemma there: the reply is parsed and checked as always
            del body["response_format"]
        if req.seed is not None:
            body["seed"] = req.seed
        rec = os.environ.get("ACCESSCAST_RECORD_REPLAY")
        if (
            rec and not req.images and req.audio is None
        ):  # E13 replay set: text-only requests, never image bytes
            Path(rec).mkdir(parents=True, exist_ok=True)
            with self._log_lock, (Path(rec) / f"{prompt.id}.jsonl").open("a", encoding="utf-8") as fh:
                fh.write(
                    json.dumps({k: v for k, v in body.items() if k != "model"}, ensure_ascii=False) + "\n"
                )
        if prov != "tokenfactory":  # Token Factory silently drops chat_template_kwargs (SayAgain's finding)
            body["chat_template_kwargs"] = {"enable_thinking": False}
        cache = self._cache_path(prov, body)
        if cache is not None and cache.exists():
            hit = json.loads(cache.read_text(encoding="utf-8"))
            if not self.strict or hit["served"].split("/")[-1].lower() == model.split("/")[-1].lower():
                return (
                    hit["text"],
                    hit["served"],
                    hit["tokens_in"],
                    hit["tokens_out"],
                    0,
                )  # 0 attempts = cache hit
        last: Exception | None = None
        down = self._down_until.get(prov, 0.0)
        if (
            time.monotonic() < down
        ):  # circuit open: fail closed at once instead of waiting out every retry again
            raise ModelEndpointError(
                f"{prov} marked down after a call failed every retry; not asking again until "
                f"{down - time.monotonic():.0f} s from now"
            )
        for attempt in range(1, self.max_retries + 2):
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
            served = str(data.get("model", ""))
            if self.strict and served.split("/")[-1].lower() != model.split("/")[-1].lower():
                # --strict-provider: never accept an answer from a different model than the one requested
                raise ModelEndpointError(
                    f"{prov} answered with model {served!r}, expected {model!r} (strict)"
                )
            out = (
                text,
                served or model,
                int(usage.get("prompt_tokens", 0)),
                int(usage.get("completion_tokens", 0)),
                attempt,
            )
            if cache is not None:
                cache.parent.mkdir(parents=True, exist_ok=True)
                tmp = cache.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
                tmp.write_text(
                    json.dumps(
                        {"text": out[0], "served": out[1], "tokens_in": out[2], "tokens_out": out[3]},
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                tmp.replace(cache)
            return out
        self._down_until[prov] = time.monotonic() + C.LLM_CIRCUIT_OPEN_S
        raise ModelEndpointError(f"{prov} failed after retries: {last}")

    @staticmethod
    def _cache_path(prov: str, body: dict[str, Any]) -> Path | None:
        """Opt-in (ACCESSCAST_LLM_CACHE=<dir>): successful answers keyed by the SHA-256 of the exact request body
        (model, prompt text, images, temperature, seed, max tokens) and provider, so a re-run after an endpoint
        outage repeats only the calls that failed. Never set for E9, E11 or E13, which measure repeated calls."""
        root = os.environ.get("ACCESSCAST_LLM_CACHE")
        if not root:
            return None
        key = hashlib.sha256((prov + "\n" + canonical_json(body)).encode("utf-8")).hexdigest()
        return Path(root) / key[:2] / f"{key}.json"

    def _backoff(self, attempt: int, retry_after: str | None) -> None:
        if attempt > self.max_retries:
            return
        delay = min(C.LLM_BACKOFF_MAX_S, 2.0**attempt) + random.uniform(0, 0.5)
        if retry_after:
            try:
                delay = min(C.LLM_BACKOFF_MAX_S, float(retry_after))
            except ValueError:
                pass
        time.sleep(delay)

    def _log(self, rec: dict[str, Any]) -> None:
        if self.log_path is None:
            return
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self._log_lock, self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
