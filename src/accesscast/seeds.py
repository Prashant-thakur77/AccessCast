# derive_seed follows Rivet's rivet/pipeline/seeds.py
# (https://github.com/damishafe/Rivet), MIT License, Copyright (c) 2026 Enoch Idowu.
"""Per-item seeds (CLAUDE.md §6)."""

from __future__ import annotations

import hashlib


def derive_seed(project_seed: int, label: str) -> int:
    """int(sha256(f"{project_seed}:{label}").hexdigest()[:8], 16)."""
    return int(hashlib.sha256(f"{project_seed}:{label}".encode()).hexdigest()[:8], 16)
