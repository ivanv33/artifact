"""Shared exception types.

Kept import-free of the rest of the package so any module can depend on it
without risking a circular import.
"""

from __future__ import annotations


class RunnerError(ValueError):
    """Raised for any user-facing run failure (bad params, missing inputs, etc.)."""
