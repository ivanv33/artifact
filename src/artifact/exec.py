"""Executor protocol + the deepagents-backed default.

``deepagent_executor`` is a thin adapter over the ``deepagents`` library. It is
deliberately not unit-tested — its behavior is covered by the manual
verification step. All of our code reaching through the executor seam is
tested via the ``Executor`` protocol with fakes in ``tests/test_runner.py``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend

from artifact.spec import Spec

_USER_KICKOFF = (
    "Execute the recipe in your system prompt. "
    "Read inputs from in/ and write outputs to out/ using the declared output names."
)


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


def deepagent_executor(*, spec: Spec, run_dir: Path, templated_body: str) -> None:
    """Execute an artifact using a deep agent backed by ``FilesystemBackend``.

    The agent's working directory is ``run_dir``, so relative reads hit
    ``in/`` and writes land in ``out/``.

    Args:
        spec: The parsed spec. Only ``spec.model`` is used here.
        run_dir: The run directory for the agent's filesystem backend.
        templated_body: The system prompt after template substitution.
    """
    backend = FilesystemBackend(root_dir=str(run_dir), virtual_mode=True)
    agent = create_deep_agent(
        model=spec.model,
        system_prompt=templated_body,
        backend=backend,
    )
    agent.invoke({"messages": [{"role": "user", "content": _USER_KICKOFF}]})
