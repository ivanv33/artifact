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


def test_create_writes_artifact_and_gitignore(tmp_path):
    from artifact.create import create, render_template

    content = render_template()
    dest = tmp_path / "1-shortlist"
    returned = create(dest, content=content)

    assert returned == dest
    assert (dest / "ARTIFACT.md").read_text(encoding="utf-8") == content
    assert (dest / ".gitignore").read_text(encoding="utf-8") == "runs/*\n"


def test_create_appends_trailing_newline_when_missing(tmp_path):
    from artifact.create import create, render_template

    content = render_template().rstrip("\n")
    dest = tmp_path / "2-shortlist"
    create(dest, content=content)

    written = (dest / "ARTIFACT.md").read_text(encoding="utf-8")
    assert written.endswith("\n")
    assert written == content + "\n"


def test_create_creates_parent_dir_when_absent(tmp_path):
    from artifact.create import create, render_template

    dest = tmp_path / "nested" / "3-shortlist"
    assert not dest.exists()
    create(dest, content=render_template())
    assert (dest / "ARTIFACT.md").is_file()


def test_create_rejects_invalid_content(tmp_path):
    from artifact.create import create
    from artifact.spec import SpecError

    bad = "no frontmatter at all"
    dest = tmp_path / "x"
    with pytest.raises(SpecError):
        create(dest, content=bad)
    # Critical property: no files written when validation fails.
    assert not dest.exists() or list(dest.iterdir()) == []


def test_create_rejects_non_empty_dir(tmp_path):
    from artifact.create import create, render_template

    dest = tmp_path / "occupied"
    dest.mkdir()
    (dest / "already-here").write_text("hello")

    with pytest.raises(FileExistsError, match="is not empty"):
        create(dest, content=render_template())
    # Existing file untouched.
    assert (dest / "already-here").read_text(encoding="utf-8") == "hello"
    assert not (dest / "ARTIFACT.md").exists()


def test_create_accepts_empty_existing_dir(tmp_path):
    from artifact.create import create, render_template

    dest = tmp_path / "empty"
    dest.mkdir()
    create(dest, content=render_template())
    assert (dest / "ARTIFACT.md").is_file()


def test_create_rejects_bare_filename_violation(tmp_path):
    # A piped ARTIFACT.md that uses a path-like input name must fail
    # validation — same rule as parse_spec, reached via create().
    from artifact.create import create
    from artifact.spec import SpecError

    bad = (
        "---\nkind: transform\nexecutor: deepagent\nmodel: x\n"
        "inputs:\n  - name: '../mission.md'\n    desc: d\n"
        "outputs:\n  - name: o.md\n    desc: d\n---\nbody\n"
    )
    dest = tmp_path / "x"
    with pytest.raises(SpecError, match="bare filename"):
        create(dest, content=bad)
    assert not dest.exists() or list(dest.iterdir()) == []
