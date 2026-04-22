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


def test_executor_claude_cli_rejects_colon_model(tmp_path):
    p = tmp_path / "ARTIFACT.md"
    p.write_text(
        "---\nkind: transform\nexecutor: claude_cli\nmodel: anthropic:foo\n"
        "outputs:\n  - name: o\n    desc: d\n---\nbody"
    )
    with pytest.raises(SpecError, match="claude_cli"):
        parse_spec(p)


def test_executor_claude_cli_allows_missing_model(tmp_path):
    p = tmp_path / "ARTIFACT.md"
    p.write_text(
        "---\nkind: transform\nexecutor: claude_cli\n"
        "outputs:\n  - name: o\n    desc: d\n---\nbody"
    )
    spec = parse_spec(p)
    assert spec.model is None


def test_executor_deepagent_still_requires_model(tmp_path):
    p = tmp_path / "ARTIFACT.md"
    p.write_text(
        "---\nkind: transform\nexecutor: deepagent\n"
        "outputs:\n  - name: o\n    desc: d\n---\nbody"
    )
    with pytest.raises(SpecError, match="model"):
        parse_spec(p)


def test_allowed_value_constants_are_public():
    from artifact.spec import ALLOWED_KINDS, ALLOWED_EXECUTORS, ALLOWED_PARAM_TYPES
    assert "transform" in ALLOWED_KINDS
    assert "deepagent" in ALLOWED_EXECUTORS
    assert "claude_cli" in ALLOWED_EXECUTORS
    assert {"string", "int", "float", "bool"} <= ALLOWED_PARAM_TYPES


def test_parse_spec_from_str_parses_inline_content():
    from pathlib import Path
    from artifact.spec import parse_spec_from_str

    content = (
        "---\n"
        "kind: transform\n"
        "executor: deepagent\n"
        "model: anthropic:claude-sonnet-4-6\n"
        "outputs:\n"
        "  - name: o.md\n"
        "    desc: d\n"
        "---\n"
        "body\n"
    )
    spec = parse_spec_from_str(content, Path("<inline>"))
    assert spec.kind == "transform"
    assert spec.executor == "deepagent"
    assert spec.model == "anthropic:claude-sonnet-4-6"
    assert spec.path == Path("<inline>")
    assert [o.name for o in spec.outputs] == ["o.md"]


def test_parse_spec_from_str_reports_path_in_error():
    from pathlib import Path
    from artifact.spec import SpecError, parse_spec_from_str

    with pytest.raises(SpecError, match="<synth>"):
        parse_spec_from_str("no frontmatter at all", Path("<synth>"))


@pytest.mark.parametrize(
    "bad_name",
    ["../x.md", "/abs/x.md", "sub/x.md", ".", "..", "a/b/c"],
)
def test_input_name_must_be_bare_filename(tmp_path, bad_name):
    from artifact.spec import SpecError, parse_spec

    p = tmp_path / "ARTIFACT.md"
    p.write_text(
        "---\nkind: transform\nexecutor: deepagent\nmodel: x\n"
        f"inputs:\n  - name: {bad_name!r}\n    desc: d\n"
        "outputs:\n  - name: o.md\n    desc: d\n---\nbody"
    )
    with pytest.raises(SpecError, match="input name must be a bare filename"):
        parse_spec(p)


@pytest.mark.parametrize(
    "bad_name",
    ["../x.md", "/abs/x.md", "sub/x.md", ".", "..", "a/b/c"],
)
def test_output_name_must_be_bare_filename(tmp_path, bad_name):
    from artifact.spec import SpecError, parse_spec

    p = tmp_path / "ARTIFACT.md"
    p.write_text(
        "---\nkind: transform\nexecutor: deepagent\nmodel: x\n"
        f"outputs:\n  - name: {bad_name!r}\n    desc: d\n---\nbody"
    )
    with pytest.raises(SpecError, match="output name must be a bare filename"):
        parse_spec(p)


def test_param_name_with_slash_is_not_validated_by_filename_rule(tmp_path):
    # Params are identifiers, not filenames. The bare-filename rule must
    # not apply here. (A separate identifier rule is deferred.)
    from artifact.spec import parse_spec

    p = tmp_path / "ARTIFACT.md"
    p.write_text(
        "---\nkind: transform\nexecutor: deepagent\nmodel: x\n"
        "params:\n  - name: a/b\n    type: string\n    required: false\n    desc: d\n"
        "outputs:\n  - name: o.md\n    desc: d\n---\nbody"
    )
    spec = parse_spec(p)
    assert spec.params[0].name == "a/b"


@pytest.mark.parametrize(
    "section,line",
    [
        ("input", "inputs:\n  - name: x.md\n    desc: a\n  - name: x.md\n    desc: b\n"),
        ("output", "outputs:\n  - name: y.md\n    desc: a\n  - name: y.md\n    desc: b\n"),
        ("param", "params:\n  - name: z\n    type: int\n    required: false\n    desc: a\n  - name: z\n    type: int\n    required: false\n    desc: b\n"),
    ],
)
def test_duplicate_names_rejected(tmp_path, section, line):
    from artifact.spec import SpecError, parse_spec

    p = tmp_path / "ARTIFACT.md"
    p.write_text(
        "---\nkind: transform\nexecutor: deepagent\nmodel: x\n"
        + line
        + ("outputs:\n  - name: o.md\n    desc: d\n" if section != "output" else "")
        + "---\nbody"
    )
    with pytest.raises(SpecError, match=f"duplicate {section} name"):
        parse_spec(p)


def test_parse_spec_from_str_rejects_surrogate_content():
    # Stdin read with surrogateescape can smuggle non-UTF-8 bytes into
    # the Python string. Re-encoding those via .encode("utf-8") raises
    # UnicodeEncodeError. We surface that as a SpecError at parse time
    # instead of leaking a traceback.
    from pathlib import Path
    from artifact.spec import SpecError, parse_spec_from_str

    bad = (
        "---\nkind: transform\nexecutor: deepagent\nmodel: a:b\n"
        "outputs:\n  - name: o.md\n    desc: d\n---\nbody \udcff\udcfe\n"
    )
    with pytest.raises(SpecError, match="non-UTF-8"):
        parse_spec_from_str(bad, Path("<synth>"))
