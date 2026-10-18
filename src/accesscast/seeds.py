"""Per-item seeds (CLAUDE.md §6)."""

from __future__ import annotations

import hashlib


def derive_seed(project_seed: int, label: str) -> int:
    """int(sha256(f"{project_seed}:{label}").hexdigest()[:8], 16)."""
    return int(hashlib.sha256(f"{project_seed}:{label}".encode()).hexdigest()[:8], 16)
