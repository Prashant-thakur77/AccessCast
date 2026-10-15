"""Settings from the environment (.env is read if present; keys are never logged)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from accesscast.constants import GPU_HOURLY_COST_USD, PROJECT_SEED_DEFAULT
from accesscast.errors import ConfigError

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover
        return
    env = REPO_ROOT / ".env"
    if env.exists():
        load_dotenv(env, override=False)


@dataclass(frozen=True)
class Settings:
    worker_mode: Literal["real", "fake"] = "real"
    local_base_url: str = "http://127.0.0.1:8000/v1"
    local_audio_base_url: str = "http://127.0.0.1:8001/v1"
    local_model: str = "gemma-4-31b"
    local_audio_model: str = "gemma-4-e4b"
    tf_base_url: str = ""
    tf_api_key: str = field(default="", repr=False)
    tf_max_concurrency: int = 8
    tf_rpm: int = 30
    hf_token_set: bool = False
    gpu_hourly_cost_usd: float = GPU_HOURLY_COST_USD
    review_policy: Literal["manual", "prototype-auto"] = "manual"
    project_seed: int = PROJECT_SEED_DEFAULT
    projects_dir: Path = REPO_ROOT / "projects"

    def redacted(self) -> dict[str, object]:
        return {
            "worker_mode": self.worker_mode,
            "local_base_url": self.local_base_url,
            "local_audio_base_url": self.local_audio_base_url,
            "local_model": self.local_model,
            "local_audio_model": self.local_audio_model,
            "tf_base_url": self.tf_base_url or None,
            "tf_api_key": "<set>" if self.tf_api_key else None,
            "hf_token": "<set>" if self.hf_token_set else None,
            "review_policy": self.review_policy,
            "project_seed": self.project_seed,
        }


def load_settings(**overrides: object) -> Settings:
    _load_dotenv()
    mode = os.environ.get("ACCESSCAST_WORKER_MODE", "real")
    if mode not in ("real", "fake"):
        raise ConfigError(f"ACCESSCAST_WORKER_MODE must be real or fake, got {mode!r}")
    policy = os.environ.get("ACCESSCAST_REVIEW_POLICY", "manual")
    if policy not in ("manual", "prototype-auto"):
        raise ConfigError(f"ACCESSCAST_REVIEW_POLICY must be manual or prototype-auto, got {policy!r}")
    try:
        seed = int(os.environ.get("ACCESSCAST_PROJECT_SEED", PROJECT_SEED_DEFAULT))
        cost = float(os.environ.get("GPU_HOURLY_COST_USD", GPU_HOURLY_COST_USD))
        tf_conc = int(os.environ.get("AMD_TF_MAX_CONCURRENCY", 8))
        tf_rpm = int(os.environ.get("AMD_TF_RPM", 30))
    except ValueError as e:
        raise ConfigError(f"bad numeric setting: {e}") from e
    projects = os.environ.get("ACCESSCAST_PROJECTS_DIR")
    s = Settings(
        worker_mode=mode,  # type: ignore[arg-type]
        local_base_url=os.environ.get("ACCESSCAST_LOCAL_BASE_URL", Settings.local_base_url),
        local_audio_base_url=os.environ.get("ACCESSCAST_LOCAL_AUDIO_BASE_URL", Settings.local_audio_base_url),
        local_model=os.environ.get("ACCESSCAST_LOCAL_MODEL", Settings.local_model),
        local_audio_model=os.environ.get("ACCESSCAST_LOCAL_AUDIO_MODEL", Settings.local_audio_model),
        tf_base_url=os.environ.get("AMD_TF_BASE_URL", ""),
        tf_api_key=os.environ.get("AMD_TF_API_KEY", ""),
        tf_max_concurrency=tf_conc,
        tf_rpm=tf_rpm,
        hf_token_set=bool(os.environ.get("HF_TOKEN")),
        gpu_hourly_cost_usd=cost,
        review_policy=policy,  # type: ignore[arg-type]
        project_seed=seed,
        projects_dir=Path(projects).resolve() if projects else REPO_ROOT / "projects",
    )
    if overrides:
        from dataclasses import replace

        s = replace(s, **overrides)  # type: ignore[arg-type]
    return s
