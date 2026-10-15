"""accesscast doctor (PLAN §14.8). Never prints keys; reports whether they are set."""

from __future__ import annotations

import shutil
import subprocess
from typing import Any

import httpx

from accesscast.config import REPO_ROOT, Settings
from accesscast.events import now_iso
from accesscast.workers_client import run_worker, worker_python


def _check(name: str, ok: bool, detail: str, required: bool = True) -> dict[str, Any]:
    return {"name": name, "ok": ok, "detail": detail, "required": required}


def _bin(name: str, args: list[str]) -> dict[str, Any]:
    exe = shutil.which(name)
    if exe is None:
        return _check(name, False, "not on PATH")
    p = subprocess.run([exe, *args], capture_output=True, text=True, check=False)
    first = (p.stdout or p.stderr).strip().splitlines()[:1]
    return _check(name, p.returncode == 0, first[0][:80] if first else "")


def _endpoint(name: str, base: str, want: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
    try:
        r = httpx.get(f"{base.rstrip('/')}/models", headers=headers or {}, timeout=8)
        r.raise_for_status()
        ids = [m["id"] for m in r.json().get("data", [])]
        return _check(name, any(want.lower() in i.lower() for i in ids), f"models: {', '.join(ids)[:120]}")
    except Exception as e:
        return _check(name, False, f"unreachable ({type(e).__name__})")


def run_doctor(s: Settings, *, deep: bool = False) -> dict[str, Any]:
    checks = [
        _bin("ffmpeg", ["-version"]), _bin("ffprobe", ["-version"]),
        _bin("tesseract", ["--version"]), _bin("espeak-ng", ["--version"]),
        _check("worker env", worker_python().exists(), str(worker_python().relative_to(REPO_ROOT))
               if worker_python().is_relative_to(REPO_ROOT) else str(worker_python())),
        _check("HF_TOKEN", s.hf_token_set, "set" if s.hf_token_set else "not set", required=False),
        _check("AMD_TF_API_KEY", bool(s.tf_api_key), "set" if s.tf_api_key else "not set", required=False),
    ]
    tess = shutil.which("tesseract")
    if tess:
        p = subprocess.run([tess, "--list-langs"], capture_output=True, text=True, check=False)
        langs = set(p.stdout.split())
        need = {"eng", "hin", "ita"}
        checks.append(_check("tesseract languages", need <= langs, f"have {sorted(langs & need)}, need {sorted(need)}"))
    du = shutil.disk_usage(REPO_ROOT)
    checks.append(_check("disk free", du.free > 20 * 2**30, f"{du.free / 2**30:.0f} GiB free"))
    if s.worker_mode == "real":
        checks.append(_endpoint("gemma-4-31b endpoint", s.local_base_url, s.local_model))
        checks.append(_endpoint("gemma-4-e4b endpoint", s.local_audio_base_url, s.local_audio_model))
        if s.tf_api_key and s.tf_base_url:
            checks.append({**_endpoint("token factory", s.tf_base_url, "gemma",
                                       {"Authorization": f"Bearer {s.tf_api_key}"}), "required": False})
    deep_results: dict[str, Any] = {}
    if deep and worker_python().exists():
        for role, action, payload in (("tts", "calibrate", {"voice": "af_heart", "lang": "en",
                                                            "sentences": ["A short test sentence for the voice."] * 3}),):
            try:
                deep_results[role] = run_worker(role, action, payload, REPO_ROOT / "projects" / "_doctor", None)
                checks.append(_check(f"{role} worker loads", True, f"device {deep_results[role].get('device')}"))
            except Exception as e:
                checks.append(_check(f"{role} worker loads", False, f"{type(e).__name__}: {str(e)[:100]}"))
        try:
            p = subprocess.run([str(worker_python()), "-c", "import torch,json;print(json.dumps({'torch':torch.__version__,"
                                "'hip':getattr(torch.version,'hip',None),'cuda':torch.cuda.is_available(),"
                                "'device':torch.cuda.get_device_name(0) if torch.cuda.is_available() else None}))"],
                               capture_output=True, text=True, check=False, timeout=120)
            import json

            deep_results["torch"] = json.loads(p.stdout.strip().splitlines()[-1])
            t = deep_results["torch"]
            checks.append(_check("ROCm device", bool(t.get("hip")) and bool(t.get("cuda")),
                                 f"torch {t.get('torch')} hip={t.get('hip')} device={t.get('device')}",
                                 required=s.worker_mode == "real"))
        except Exception as e:
            checks.append(_check("ROCm device", False, f"probe failed: {type(e).__name__}", required=s.worker_mode == "real"))
    ok = all(c["ok"] for c in checks if c["required"])
    return {"schema": "accesscast/doctor/v1", "generated_at": now_iso(), "ok": ok, "worker_mode": s.worker_mode,
            "settings": s.redacted(), "checks": checks, "deep": deep_results}
