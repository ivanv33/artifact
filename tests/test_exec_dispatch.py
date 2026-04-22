"""Unit tests for artifact.exec.get_executor.

The dispatcher is pure: it maps ``spec.executor`` to a callable. These tests
verify the mapping; they do not invoke either executor.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from artifact.exec import deepagent_executor, get_executor
from artifact.spec import Spec


def _spec(executor: str) -> Spec:
    return Spec(
        path=Path("/dev/null"),
        kind="transform",
        executor=executor,
        model=None,
        inputs=[],
        params=[],
        outputs=[],
        body="",
        artifact_sha256="0" * 64,
    )


def test_get_executor_returns_deepagent_for_deepagent_spec():
    assert get_executor(_spec("deepagent")) is deepagent_executor


def test_get_executor_returns_claude_cli_executor_for_claude_cli_spec():
    from artifact.claude_cli import claude_cli_executor
    assert get_executor(_spec("claude_cli")) is claude_cli_executor


def test_get_executor_raises_on_unknown_executor():
    with pytest.raises(ValueError, match="unknown executor"):
        get_executor(_spec("python"))
