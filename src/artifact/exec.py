"""Executor protocol.

An ``Executor`` is any callable that takes a ``Spec``, a run directory, and a
templated prompt body, and produces output files under ``run_dir/out/``.
The real deepagent-backed implementation arrives in Stage 5; this initial
version only defines the protocol plus a no-op used for scaffolding.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from artifact.spec import Spec


class Executor(Protocol):
    """Callable protocol for running a templated artifact body."""

    def __call__(self, *, spec: Spec, run_dir: Path, templated_body: str) -> None:
        """Execute the artifact, writing outputs under ``run_dir/out/``.

        Args:
            spec: The parsed artifact spec.
            run_dir: The run directory (with ``in/`` and ``out/`` already created).
            templated_body: The artifact body after ``render()`` substitution.
        """
        ...


def noop_executor(*, spec: Spec, run_dir: Path, templated_body: str) -> None:
    """No-op executor used only for scaffolding.

    Args:
        spec: Unused.
        run_dir: Unused.
        templated_body: Unused.
    """
    return None
