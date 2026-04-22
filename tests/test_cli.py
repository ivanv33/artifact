import pytest

from artifact.cli import build_parser, main


def test_help_does_not_crash(capsys):
    try:
        main(["--help"])
    except SystemExit as e:
        assert e.code == 0
    out = capsys.readouterr().out
    assert "artifact" in out


def test_run_subcommand_parses():
    parser = build_parser()
    args = parser.parse_args(["run", "some/dir"])
    assert args.cmd == "run"
    assert args.artifact_dir == "some/dir"


from pathlib import Path


def test_run_cli_creates_run_dir_via_injected_executor(tmp_path):
    import shutil

    from artifact.cli import main

    fixtures = Path(__file__).parent / "fixtures"
    art = tmp_path / "trivial"
    shutil.copytree(fixtures / "trivial", art, ignore=shutil.ignore_patterns("runs", "outs"))

    def stub_executor(*, spec, run_dir, templated_body):
        # produce the declared output so the Stage-5 verification step
        # (added later) stays green when re-running historical tests.
        (run_dir / "out" / "hello.md").write_text("hi")

    rc = main(["run", str(art)], executor=stub_executor)
    assert rc == 0
    runs = list((art / "runs").iterdir())
    assert len(runs) == 1
    assert (runs[0] / "manifest.json").is_file()


def test_run_cli_reports_missing_dir_cleanly(tmp_path, capsys):
    from artifact.cli import main

    rc = main(["run", str(tmp_path / "does-not-exist")])
    assert rc == 1
    err = capsys.readouterr().err
    assert err.startswith("error: ")
    # The error should NOT contain a Python traceback.
    assert "Traceback" not in err


def test_show_cli_reports_missing_dir_cleanly(tmp_path, capsys):
    from artifact.cli import main

    rc = main(["show", str(tmp_path / "does-not-exist")])
    assert rc == 1
    err = capsys.readouterr().err
    assert err.startswith("error: ")
    assert "Traceback" not in err


def test_run_with_promote_as(tmp_path):
    import shutil

    from artifact import cli

    fixtures = Path(__file__).parent / "fixtures"
    art = tmp_path / "trivial"
    shutil.copytree(fixtures / "trivial", art, ignore=shutil.ignore_patterns("runs", "outs"))

    def stub_executor(*, spec, run_dir, templated_body):
        (run_dir / "out" / "hello.md").write_text("hi")

    rc = cli.main(["run", str(art), "--promote-as", "alice"], executor=stub_executor)
    assert rc == 0
    assert (art / "outs" / "alice" / "out" / "hello.md").is_file()


def test_run_cli_passes_model_override_to_runner(tmp_path):
    import shutil

    from artifact.cli import main

    fixtures = Path(__file__).parent / "fixtures"
    art = tmp_path / "trivial"
    shutil.copytree(fixtures / "trivial", art, ignore=shutil.ignore_patterns("runs", "outs"))

    seen: dict = {}

    def capturing_executor(*, spec, run_dir, templated_body):
        seen["model"] = spec.model
        (run_dir / "out" / "hello.md").write_text("hi")

    rc = main(
        ["run", str(art), "--model", "anthropic:claude-haiku-4-5"],
        executor=capturing_executor,
    )
    assert rc == 0
    assert seen["model"] == "anthropic:claude-haiku-4-5"


def test_run_cli_rejects_empty_model(tmp_path, capsys):
    import shutil

    from artifact.cli import main

    fixtures = Path(__file__).parent / "fixtures"
    art = tmp_path / "trivial"
    shutil.copytree(fixtures / "trivial", art, ignore=shutil.ignore_patterns("runs", "outs"))

    def should_not_run(*, spec, run_dir, templated_body):
        raise AssertionError("executor must not be invoked when --model is empty")

    rc = main(["run", str(art), "--model", ""], executor=should_not_run)
    assert rc == 1
    err = capsys.readouterr().err
    assert "error: --model requires a non-empty string" in err
    assert not (art / "runs").exists() or list((art / "runs").iterdir()) == []


def test_run_cli_without_model_preserves_declared(tmp_path):
    import shutil

    from artifact.cli import main

    fixtures = Path(__file__).parent / "fixtures"
    art = tmp_path / "trivial"
    shutil.copytree(fixtures / "trivial", art, ignore=shutil.ignore_patterns("runs", "outs"))

    seen: dict = {}

    def capturing_executor(*, spec, run_dir, templated_body):
        seen["model"] = spec.model
        (run_dir / "out" / "hello.md").write_text("hi")

    rc = main(["run", str(art)], executor=capturing_executor)
    assert rc == 0
    # The `trivial` fixture declares a model in its frontmatter; assert the
    # executor saw it verbatim (no override in play).
    from artifact.spec import parse_spec
    declared = parse_spec(art / "ARTIFACT.md").model
    assert seen["model"] == declared


def test_run_cli_rejects_colon_override_under_claude_cli(tmp_path, capsys):
    import shutil

    from artifact.cli import main

    art = tmp_path / "claude-cli-artifact"
    art.mkdir()
    (art / "ARTIFACT.md").write_text(
        "---\nkind: transform\nexecutor: claude_cli\n"
        "outputs:\n  - name: o\n    desc: d\n---\nbody"
    )

    def should_not_run(*, spec, run_dir, templated_body):
        raise AssertionError("executor must not be invoked when override is invalid")

    rc = main(
        ["run", str(art), "--model", "anthropic:foo"],
        executor=should_not_run,
    )
    assert rc == 1
    err = capsys.readouterr().err
    assert "bare Claude model name" in err


def test_template_subcommand_prints_reference_to_stdout(capsys):
    from artifact.cli import main

    rc = main(["template"])
    assert rc == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    # Frontmatter delimiters present; body is non-empty.
    assert captured.out.startswith("---\n")
    assert "\nkind: transform" in captured.out
    assert "requirements.md" in captured.out


def test_template_subcommand_is_idempotent(capsys):
    from artifact.cli import main

    rc1 = main(["template"])
    first = capsys.readouterr().out
    rc2 = main(["template"])
    second = capsys.readouterr().out
    assert rc1 == 0 and rc2 == 0
    assert first == second


def test_template_subcommand_rejects_flags(capsys):
    from artifact.cli import main

    # argparse exits with SystemExit(2) for unknown flags.
    with pytest.raises(SystemExit) as excinfo:
        main(["template", "--model", "x"])
    assert excinfo.value.code == 2


class _FakeStdin:
    """Minimal stdin double: fixed content + controllable isatty()."""

    def __init__(self, content: str, *, isatty: bool) -> None:
        self._content = content
        self._isatty = isatty

    def isatty(self) -> bool:
        return self._isatty

    def read(self) -> str:
        if self._isatty:
            raise AssertionError("read() should not be called when isatty()")
        return self._content


def test_create_cli_rejects_tty_stdin(tmp_path, capsys):
    from artifact.cli import main

    rc = main(["create", str(tmp_path / "x")], stdin=_FakeStdin("", isatty=True))
    assert rc == 1
    err = capsys.readouterr().err
    assert err.startswith("error: create reads ARTIFACT.md from stdin;")
    assert "artifact template | artifact create" in err
    assert not (tmp_path / "x").exists()


def test_create_cli_rejects_empty_stdin(tmp_path, capsys):
    from artifact.cli import main

    rc = main(["create", str(tmp_path / "x")], stdin=_FakeStdin("", isatty=False))
    assert rc == 1
    assert "error: stdin is empty" in capsys.readouterr().err
    assert not (tmp_path / "x").exists()


def test_create_cli_writes_files_on_valid_stdin(tmp_path, capsys):
    from artifact.cli import main
    from artifact.create import render_template

    content = render_template()
    dest = tmp_path / "1-shortlist"
    rc = main(["create", str(dest)], stdin=_FakeStdin(content, isatty=False))
    assert rc == 0
    out = capsys.readouterr().out.strip()
    # stdout is the destination path (as passed, not resolved).
    assert out == str(dest)
    assert (dest / "ARTIFACT.md").read_text(encoding="utf-8") == content
    assert (dest / ".gitignore").read_text(encoding="utf-8") == "runs/*\n"


def test_create_cli_surfaces_spec_errors(tmp_path, capsys):
    from artifact.cli import main

    rc = main(
        ["create", str(tmp_path / "bad")],
        stdin=_FakeStdin("not an artifact", isatty=False),
    )
    assert rc == 1
    err = capsys.readouterr().err
    assert err.startswith("error: ")
    assert "Traceback" not in err
    assert not (tmp_path / "bad").exists()


def test_create_cli_refuses_non_empty_dir(tmp_path, capsys):
    from artifact.cli import main
    from artifact.create import render_template

    dest = tmp_path / "occupied"
    dest.mkdir()
    (dest / "already").write_text("x")

    rc = main(
        ["create", str(dest)],
        stdin=_FakeStdin(render_template(), isatty=False),
    )
    assert rc == 1
    err = capsys.readouterr().err
    assert "is not empty" in err
    assert (dest / "already").read_text(encoding="utf-8") == "x"
    assert not (dest / "ARTIFACT.md").exists()


def test_template_create_pipeline_end_to_end(tmp_path, capsys):
    """The headline one-liner: template output piped into create writes a
    dir whose ARTIFACT.md parses cleanly via parse_spec."""
    from artifact.cli import main
    from artifact.spec import parse_spec

    # Phase 1: run `template`, capture stdout.
    rc = main(["template"])
    assert rc == 0
    template_out = capsys.readouterr().out

    # Phase 2: feed it into `create` via the injected stdin.
    dest = tmp_path / "1-end-to-end"
    rc = main(["create", str(dest)], stdin=_FakeStdin(template_out, isatty=False))
    assert rc == 0

    spec = parse_spec(dest / "ARTIFACT.md")
    assert spec.kind == "transform"
    assert spec.inputs and spec.params and spec.outputs
