"""Unit tests for artifact.claude_cli.

Pattern: inject collaborators (``popen_factory``) via the public parameter seam
— never monkeypatch module attributes.
"""
from __future__ import annotations

from pathlib import Path

from artifact.claude_cli import _build_argv
from artifact.spec import Spec


def _fake_spec(*, executor: str = "claude_cli", model: str | None = "haiku") -> Spec:
    return Spec(
        path=Path("/dev/null"),
        kind="transform",
        executor=executor,
        model=model,
        inputs=[],
        params=[],
        outputs=[],
        body="",
        artifact_sha256="0" * 64,
    )


def test_build_argv_contains_stream_json_and_bypass_permissions():
    argv = _build_argv(spec=_fake_spec(), templated_body="body", kickoff="go")
    assert "claude" == argv[0]
    assert "-p" in argv
    assert argv[argv.index("-p") + 1] == "go"
    assert "--output-format" in argv
    assert argv[argv.index("--output-format") + 1] == "stream-json"
    assert "--permission-mode" in argv
    assert argv[argv.index("--permission-mode") + 1] == "bypassPermissions"
    assert "--verbose" in argv


def test_build_argv_includes_system_prompt_and_model_when_set():
    argv = _build_argv(
        spec=_fake_spec(model="claude-sonnet-4-6"),
        templated_body="the recipe",
        kickoff="go",
    )
    assert "--system-prompt" in argv
    assert argv[argv.index("--system-prompt") + 1] == "the recipe"
    assert "--model" in argv
    assert argv[argv.index("--model") + 1] == "claude-sonnet-4-6"


def test_build_argv_omits_model_flag_when_none():
    argv = _build_argv(
        spec=_fake_spec(model=None),
        templated_body="body",
        kickoff="go",
    )
    assert "--model" not in argv
