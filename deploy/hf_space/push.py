"""Push the proof API to a Hugging Face Space (Docker). Needs HF_TOKEN with write access to the Space.

Usage: uv run --with huggingface_hub python deploy/hf_space/push.py <owner>/<space-name>
Then set the Space secrets AMD_TF_API_KEY and AMD_TF_BASE_URL in its settings (this script sets them if
they are in the environment), and put the Space URL in site/data/proof_config.json as api_base.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parents[2]
repo = sys.argv[1]
api = HfApi(token=os.environ["HF_TOKEN"])
api.create_repo(repo, repo_type="space", space_sdk="docker", exist_ok=True)
with tempfile.TemporaryDirectory() as td:
    t = Path(td)
    shutil.copy(ROOT / "deploy" / "hf_space" / "Dockerfile", t / "Dockerfile")
    shutil.copy(ROOT / "deploy" / "hf_space" / "SPACE_README.md", t / "README.md")
    for f in ("pyproject.toml", "uv.lock"):
        shutil.copy(ROOT / f, t / f)
    shutil.copytree(ROOT / "src", t / "src", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    api.upload_folder(folder_path=str(t), repo_id=repo, repo_type="space", commit_message="AccessCast proof API")
for k in ("AMD_TF_API_KEY", "AMD_TF_BASE_URL", "AMD_TF_RPM"):
    if os.environ.get(k):
        api.add_space_secret(repo, k, os.environ[k])
print(f"pushed https://huggingface.co/spaces/{repo}")
