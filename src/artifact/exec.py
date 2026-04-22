"""Executor protocol, the deepagents-backed default, and the dispatcher.

``deepagent_executor`` and ``claude_cli_executor`` (in ``claude_cli.py``) are
thin adapters over their respective backends. Both are exercised via the
``Executor`` protocol with fakes in ``tests/test_runner.py`` and
``tests/test_claude_cli.py``. ``get_executor(spec)`` maps ``spec.executor`` to
the right callable and is the single point of dispatch at run time.
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

    def __call__(
        self, *, spec: Spec, run_dir: Path, templated_body: str
    ) -> dict | None:
        """Execute the artifact, writing outputs under ``run_dir/out/``.

        Args:
            spec: The parsed artifact spec.
            run_dir: The run directory (with ``in/`` and ``out/`` already created).
            templated_body: The artifact body after ``render()`` substitution.

        Returns:
            An optional mapping of extra fields to merge into ``manifest.json``.
            Return ``None`` (or equivalently ``{}``) when the executor has
            nothing to record beyond what the runner already captures.
        """
        ...


def noop_executor(
    *, spec: Spec, run_dir: Path, templated_body: str
) -> None:
    """No-op executor used only for scaffolding."""
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


def get_executor(spec: Spec) -> Executor:
    """Return the executor callable for ``spec.executor``.

    Spec validation already restricts ``spec.executor`` to the allowed set, so
    this function is total for any ``Spec`` produced by ``parse_spec``.
    """
    if spec.executor == "claude_cli":
        from artifact.claude_cli import claude_cli_executor
        return claude_cli_executor
    if spec.executor == "deepagent":
        return deepagent_executor
    raise ValueError(f"unknown executor {spec.executor!r}")
