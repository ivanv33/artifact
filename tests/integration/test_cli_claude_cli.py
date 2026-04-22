"""End-to-end: ``artifact run`` with ``executor: claude_cli`` hits the real ``claude`` CLI.

Opt-in via ``pytest -m integration``. Skipped when ``claude`` is not on PATH.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from artifact.cli import main

FIXTURES = Path(__file__).parent / "fixtures"

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _require_claude_cli():
    if shutil.which("claude") is None:
        pytest.skip(
            "`claude` CLI not found on PATH; skipping live claude_cli integration test"
        )


def test_claude_cli_executor_writes_haiku_and_provenance(tmp_path, capsys):
    art = tmp_path / "trivial-claude-cli"
    shutil.copytree(
        FIXTURES / "trivial-claude-cli",
        art,
        ignore=shutil.ignore_patterns("runs", "outs"),
    )

    rc = main(["run", str(art), "--param", "topic=rain"])
    assert rc == 0, f"main() returned {rc}; stderr: {capsys.readouterr().err}"

    runs = sorted((art / "runs").iterdir())
    assert len(runs) == 1, f"expected one run directory, got {runs}"
    run_dir = runs[0]

    haiku = run_dir / "out" / "haiku.md"
    assert haiku.is_file(), f"expected declared output at {haiku}"
    assert len(haiku.read_text().strip()) > 10, "haiku is suspiciously empty"

    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert manifest["executor"] == "claude_cli"
    assert manifest["model"] is None
    assert manifest["model_declared"] is None
    assert manifest["model_overridden"] is False
    assert "claude_cli" in manifest
    block = manifest["claude_cli"]
    assert isinstance(block.get("session_id"), str)
    assert len(block["session_id"]) > 0


def test_claude_cli_executor_reads_staged_input(tmp_path, capsys):
    art = tmp_path / "claude-cli-with-input"
    shutil.copytree(
        FIXTURES / "claude-cli-with-input",
        art,
        ignore=shutil.ignore_patterns("runs", "outs"),
    )
    topic_src = tmp_path / "topic.txt"
    topic_src.write_text("thunder\n")

    rc = main(
        ["run", str(art), "--input", f"topic.txt={topic_src}"],
    )
    assert rc == 0, f"main() returned {rc}; stderr: {capsys.readouterr().err}"

    runs = sorted((art / "runs").iterdir())
    assert len(runs) == 1, f"expected one run directory, got {runs}"
    run_dir = runs[0]

    staged = run_dir / "in" / "topic.txt"
    assert staged.is_file(), f"expected staged input at {staged}"
    assert staged.read_text() == "thunder\n"

    haiku = run_dir / "out" / "haiku.md"
    assert haiku.is_file(), f"expected declared output at {haiku}"
    assert len(haiku.read_text().strip()) > 10, "haiku is suspiciously empty"

    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert manifest["executor"] == "claude_cli"
    assert len(manifest["inputs"]) == 1
    rec = manifest["inputs"][0]
    assert rec["name"] == "topic.txt"
    assert rec["source"] == str(topic_src)
    assert len(rec["sha256"]) == 64
    assert manifest["claude_cli"]["session_id"]
