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
        ["run", str(art), "--model", "claude_code:haiku"],
        executor=capturing_executor,
    )
    assert rc == 0
    assert seen["model"] == "claude_code:haiku"


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
