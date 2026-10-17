"""Vercel Python function: the live "try your own caption" API (POST /api/try); same app as api/attack.py. Code and pruned dependencies are vendored by
scripts/build_vercel_api.sh; the Token Factory key comes from the project's environment settings."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "_vendor"))
os.environ.setdefault("ACCESSCAST_WORKER_MODE", "real")
os.environ.setdefault("ACCESSCAST_PROJECTS_DIR", "/tmp/accesscast-projects")
# textstat (readability check ER009) reads NLTK's cmudict; the function cannot download it (read-only disk)
os.environ.setdefault("NLTK_DATA", os.path.join(os.path.dirname(__file__), "_vendor", "nltk_data"))

from accesscast.proof.api import create_app  # noqa: E402

app = create_app()
