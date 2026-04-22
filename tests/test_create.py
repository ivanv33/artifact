"""Tests for render_template and create (src/artifact/create.py)."""

from __future__ import annotations

from pathlib import Path

import pytest

from artifact.create import render_template
from artifact.spec import (
    ALLOWED_EXECUTORS,
    ALLOWED_KINDS,
    ALLOWED_PARAM_TYPES,
    parse_spec_from_str,
)


def test_render_template_is_valid_spec():
    text = render_template()
    spec = parse_spec_from_str(text, Path("<template>"))
    assert spec.kind in ALLOWED_KINDS
    assert spec.executor in ALLOWED_EXECUTORS
    assert len(spec.inputs) >= 1
    assert len(spec.params) >= 1
    assert len(spec.outputs) >= 1


def test_render_template_is_deterministic():
    assert render_template() == render_template()


def test_render_template_returns_str_with_frontmatter_and_body():
    text = render_template()
    assert text.startswith("---\n")
    # Split on the frontmatter-closing delimiter; body follows.
    _, sep, body = text.partition("\n---\n")
    assert sep == "\n---\n"
    assert body.strip()


def test_render_template_lists_every_allowed_value_in_comments():
    """Drift tripwire: if the parser grows a new allowed value, the template
    must surface it somewhere in the rendered text (typically the `# one of:`
    comment next to the relevant field).
    """
    text = render_template()
    missing = [
        v
        for v in (ALLOWED_KINDS | ALLOWED_EXECUTORS | ALLOWED_PARAM_TYPES)
        if v not in text
    ]
    assert missing == [], f"template missing allowed values: {missing}"


@pytest.mark.parametrize(
    "needle",
    [
        "requirements.md",    # declared input name
        "max_budget_usd",     # a required param
        "picks.md",           # a declared output
        "candidates.json",    # another declared output
        "wildcards.md",       # third declared output
    ],
)
def test_render_template_contains_reference_names(needle):
    assert needle in render_template()
