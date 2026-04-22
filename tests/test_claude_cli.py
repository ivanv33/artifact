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


import io

from artifact.claude_cli import _consume_stream


def test_consume_stream_forwards_assistant_text():
    buf = io.StringIO()
    lines = [
        '{"type":"assistant","message":{"content":[{"type":"text","text":"hello"}]}}\n',
        '{"type":"result","session_id":"s1","num_turns":1,"duration_ms":10,'
        '"total_cost_usd":0.01,"model":"haiku"}\n',
    ]
    r = _consume_stream(lines, stdout=buf)
    assert "hello" in buf.getvalue()
    assert r is not None
    assert r["session_id"] == "s1"


def test_consume_stream_renders_tool_use_summary():
    buf = io.StringIO()
    lines = [
        '{"type":"assistant","message":{"content":[{"type":"tool_use",'
        '"id":"t1","name":"Write","input":{"file_path":"out/haiku.md"}}]}}\n',
        '{"type":"result"}\n',
    ]
    _consume_stream(lines, stdout=buf)
    assert "[Write]" in buf.getvalue()


def test_consume_stream_returns_none_when_no_result_event():
    buf = io.StringIO()
    lines = [
        '{"type":"assistant","message":{"content":[{"type":"text","text":"a"}]}}\n',
    ]
    assert _consume_stream(lines, stdout=buf) is None


def test_consume_stream_tolerates_malformed_json(capsys):
    buf = io.StringIO()
    lines = [
        '{"type":"assistant","message":{"content":[{"type":"text","text":"a"}]}}\n',
        'not json\n',
        '{"type":"result"}\n',
    ]
    r = _consume_stream(lines, stdout=buf)
    assert "a" in buf.getvalue()
    assert r is not None
    err = capsys.readouterr().err
    assert "non-JSON" in err


def test_consume_stream_skips_unknown_and_rate_limit_events():
    buf = io.StringIO()
    lines = [
        '{"type":"future_event","data":"whatever"}\n',
        '{"type":"rate_limit_event","reset_at":"2026-05-01"}\n',
        '{"type":"system","subtype":"init"}\n',
        '{"type":"assistant","message":{"content":[{"type":"text","text":"x"}]}}\n',
        '{"type":"result"}\n',
    ]
    r = _consume_stream(lines, stdout=buf)
    assert buf.getvalue().strip() == "x"
    assert r is not None


import pytest

from artifact.claude_cli import claude_cli_executor
from artifact.runner import RunnerError


class _FakePopen:
    def __init__(self, *, stdout_text: str, stderr_text: str, returncode: int) -> None:
        self.stdout = io.StringIO(stdout_text)
        self.stderr = io.StringIO(stderr_text)
        self._rc = returncode
        self.returncode = returncode

    def wait(self) -> int:
        return self._rc


def _factory(*, stdout_text: str = "", stderr_text: str = "", returncode: int = 0):
    def _make(*args, **kwargs):
        return _FakePopen(
            stdout_text=stdout_text, stderr_text=stderr_text, returncode=returncode
        )
    return _make


def test_executor_success_returns_claude_cli_manifest_block(tmp_path):
    stream = (
        '{"type":"assistant","message":{"content":'
        '[{"type":"text","text":"done"}]}}\n'
        '{"type":"result","session_id":"sess-1","model":"haiku","num_turns":2,'
        '"duration_ms":5,"total_cost_usd":0.01}\n'
    )
    out = claude_cli_executor(
        spec=_fake_spec(),
        run_dir=tmp_path,
        templated_body="body",
        popen_factory=_factory(stdout_text=stream),
    )
    assert out == {
        "claude_cli": {
            "session_id": "sess-1",
            "model_used": "haiku",
            "num_turns": 2,
            "duration_ms": 5,
            "total_cost_usd": 0.01,
        }
    }


def test_executor_non_zero_exit_raises_runner_error(tmp_path):
    with pytest.raises(RunnerError, match=r"exit.*2"):
        claude_cli_executor(
            spec=_fake_spec(),
            run_dir=tmp_path,
            templated_body="body",
            popen_factory=_factory(
                stdout_text='{"type":"result"}\n',
                stderr_text="boom\n",
                returncode=2,
            ),
        )


def test_executor_missing_result_event_raises(tmp_path):
    stream = '{"type":"assistant","message":{"content":[{"type":"text","text":"x"}]}}\n'
    with pytest.raises(RunnerError, match="final result event"):
        claude_cli_executor(
            spec=_fake_spec(),
            run_dir=tmp_path,
            templated_body="body",
            popen_factory=_factory(stdout_text=stream),
        )


def test_executor_claude_not_on_path_raises_with_install_hint(tmp_path):
    def _boom(*args, **kwargs):
        raise FileNotFoundError(2, "No such file", "claude")

    with pytest.raises(RunnerError, match="claude CLI not found"):
        claude_cli_executor(
            spec=_fake_spec(),
            run_dir=tmp_path,
            templated_body="body",
            popen_factory=_boom,
        )


def test_executor_is_error_result_raises(tmp_path):
    stream = (
        '{"type":"result","is_error":true,"subtype":"error_max_turns",'
        '"result":"exceeded turn budget"}\n'
    )
    with pytest.raises(RunnerError, match="error_max_turns"):
        claude_cli_executor(
            spec=_fake_spec(),
            run_dir=tmp_path,
            templated_body="body",
            popen_factory=_factory(stdout_text=stream),
        )


def test_executor_omits_missing_result_fields_from_manifest(tmp_path):
    stream = (
        '{"type":"result","session_id":"sess-2","model":"haiku"}\n'
    )
    out = claude_cli_executor(
        spec=_fake_spec(),
        run_dir=tmp_path,
        templated_body="body",
        popen_factory=_factory(stdout_text=stream),
    )
    assert out == {
        "claude_cli": {"session_id": "sess-2", "model_used": "haiku"}
    }
