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
