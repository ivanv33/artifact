"""Executor protocol + the deepagents-backed default + model resolver.

``deepagent_executor`` is a thin adapter over the ``deepagents`` library. It
is deliberately not unit-tested — its behavior is covered by the manual
verification step. All of our code reaching through the executor seam is
tested via the ``Executor`` protocol with fakes in ``tests/test_runner.py``.

``_resolve_chat_model`` is the one piece of executor-adjacent logic that
*is* unit-tested, in ``tests/test_exec.py``: it is pure
prefix-and-factory plumbing for the ``claude_code:`` adapter, with no
LLM call inside.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Protocol

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langchain_core.language_models import BaseChatModel

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


_CLAUDE_CODE_PREFIX = "claude_code:"


def _default_claude_code_factory(*, model: str) -> BaseChatModel:
    """Construct the real ``ChatClaudeCode``; isolated so tests can inject a fake."""
    from langchain_claude_code import ChatClaudeCode

    return ChatClaudeCode(model=model)


def _resolve_chat_model(
    model: str,
    *,
    claude_code_factory: Callable[..., BaseChatModel] = _default_claude_code_factory,
) -> str | BaseChatModel:
    """Translate a ``spec.model`` string into a chat model that ``deepagents`` can use.

    Strings without the ``claude_code:`` prefix are returned unchanged so that
    LangChain's ``init_chat_model`` continues to handle ``anthropic:``,
    ``google_genai:``, ``openai:``, and friends.

    Strings with the ``claude_code:`` prefix are split into prefix and tail;
    the tail is handed to ``claude_code_factory`` (default: real
    ``ChatClaudeCode``), and the resulting instance is returned. ``deepagents``
    accepts both strings and ``BaseChatModel`` instances, so the call site
    treats both return types identically.

    Raises:
        ValueError: When the prefix is present but the tail is empty
            (e.g., ``--model claude_code:`` slips past the CLI's empty-string
            check, which only catches empty *whole* strings).
    """
    if not model.startswith(_CLAUDE_CODE_PREFIX):
        return model
    tail = model[len(_CLAUDE_CODE_PREFIX):]
    if not tail:
        raise ValueError("claude_code: requires a model name after the prefix")
    return claude_code_factory(model=tail)


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
        model=_resolve_chat_model(spec.model),
        system_prompt=templated_body,
        backend=backend,
    )
    agent.invoke({"messages": [{"role": "user", "content": _USER_KICKOFF}]})
