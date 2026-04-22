"""Unit tests for the pure resolver helper in ``artifact.exec``.

We do NOT test ``deepagent_executor`` here; per ``exec.py``'s module
docstring, the executor itself is covered by manual verification. The
resolver is pure string-and-factory plumbing, so it gets unit tests.
"""

from __future__ import annotations

import pytest

from artifact.exec import _resolve_chat_model


class _FakeChatModel:
    """Stand-in for ``ChatClaudeCode`` that records its constructor kwargs."""

    def __init__(self, *, model: str) -> None:
        self.model = model


def _fake_factory(*, model: str) -> _FakeChatModel:
    return _FakeChatModel(model=model)


def test_resolve_passes_non_claude_code_strings_through_unchanged():
    assert _resolve_chat_model("anthropic:claude-sonnet-4-6") == "anthropic:claude-sonnet-4-6"
    assert _resolve_chat_model("google_genai:gemini-2.5-flash-lite") == "google_genai:gemini-2.5-flash-lite"
    assert _resolve_chat_model("openai:gpt-4o-mini") == "openai:gpt-4o-mini"


def test_resolve_claude_code_prefix_calls_factory_with_tail():
    result = _resolve_chat_model(
        "claude_code:haiku", claude_code_factory=_fake_factory
    )
    assert isinstance(result, _FakeChatModel)
    assert result.model == "haiku"


def test_resolve_claude_code_with_empty_tail_raises():
    with pytest.raises(ValueError, match="claude_code:"):
        _resolve_chat_model("claude_code:", claude_code_factory=_fake_factory)


def test_resolve_does_not_match_substring():
    # Defensive: only the exact ``claude_code:`` prefix should trigger the
    # factory. A model named ``something-claude_code:foo`` (unlikely but
    # possible) must pass through.
    s = "anthropic:claude_code:something"
    assert _resolve_chat_model(s, claude_code_factory=_fake_factory) == s
