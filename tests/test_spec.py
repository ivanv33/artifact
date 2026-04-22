from pathlib import Path

import pytest

from artifact.spec import Spec, SpecError, parse_spec

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_trivial():
    spec = parse_spec(FIXTURES / "trivial" / "ARTIFACT.md")
    assert spec.kind == "transform"
    assert spec.executor == "deepagent"
    assert spec.model == "anthropic:claude-sonnet-4-6"
    assert spec.inputs == []
    assert spec.params == []
    assert [o.name for o in spec.outputs] == ["hello.md"]
    assert "out/hello.md" in spec.body


def test_parse_with_params():
    spec = parse_spec(FIXTURES / "with-params" / "ARTIFACT.md")
    assert [p.name for p in spec.params] == ["user", "focus"]
    user = spec.params[0]
    assert user.required is True
    assert user.default is None
    focus = spec.params[1]
    assert focus.required is False
    assert focus.default == "general"


def test_parse_with_inputs():
    spec = parse_spec(FIXTURES / "with-inputs" / "ARTIFACT.md")
    assert [i.name for i in spec.inputs] == ["events.json"]


def test_missing_frontmatter_raises(tmp_path):
    p = tmp_path / "ARTIFACT.md"
    p.write_text("no frontmatter here")
    with pytest.raises(SpecError, match="frontmatter"):
        parse_spec(p)


def test_unknown_kind_raises(tmp_path):
    p = tmp_path / "ARTIFACT.md"
    p.write_text("---\nkind: run\nexecutor: deepagent\nmodel: x\n---\nbody")
    with pytest.raises(SpecError, match="kind"):
        parse_spec(p)


def test_unknown_executor_raises(tmp_path):
    p = tmp_path / "ARTIFACT.md"
    p.write_text("---\nkind: transform\nexecutor: python\nmodel: x\n---\nbody")
    with pytest.raises(SpecError, match="executor"):
        parse_spec(p)


def test_missing_model_raises(tmp_path):
    p = tmp_path / "ARTIFACT.md"
    p.write_text("---\nkind: transform\nexecutor: deepagent\n---\nbody")
    with pytest.raises(SpecError, match="model"):
        parse_spec(p)


def test_required_param_without_default_is_required(tmp_path):
    p = tmp_path / "ARTIFACT.md"
    p.write_text(
        "---\nkind: transform\nexecutor: deepagent\nmodel: x\n"
        "params:\n  - name: foo\n    type: string\n    required: true\n    desc: f\n"
        "outputs:\n  - name: o\n    desc: d\n---\nbody"
    )
    spec = parse_spec(p)
    assert spec.params[0].required is True
    assert spec.params[0].default is None


def test_artifact_sha256_is_computed():
    spec = parse_spec(FIXTURES / "trivial" / "ARTIFACT.md")
    assert len(spec.artifact_sha256) == 64
    assert all(c in "0123456789abcdef" for c in spec.artifact_sha256)


def test_executor_claude_cli_accepted(tmp_path):
    p = tmp_path / "ARTIFACT.md"
    p.write_text(
        "---\nkind: transform\nexecutor: claude_cli\nmodel: claude-sonnet-4-6\n"
        "outputs:\n  - name: o\n    desc: d\n---\nbody"
    )
    spec = parse_spec(p)
    assert spec.executor == "claude_cli"
