"""Shared pytest config for the artifact test suite.

Loaded once per session. Sources ``.env`` at the repo root (if present) so
integration tests that need ``GOOGLE_API_KEY`` can find it.
"""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv


def _repo_root() -> Path:
    """Return the repository root (where ``pyproject.toml`` lives)."""
    here = Path(__file__).resolve()
    for parent in (here, *here.parents):
        if (parent / "pyproject.toml").is_file():
            return parent
    return here.parent


load_dotenv(_repo_root() / ".env")
