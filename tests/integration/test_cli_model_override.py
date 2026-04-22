"""End-to-end: `artifact run --model X` hits a real Gemini model and records the override.

Opt-in via ``pytest -m integration``. Skipped when ``GOOGLE_API_KEY`` is absent.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from artifact.cli import main

FIXTURES = Path(__file__).parent / "fixtures"

pytestmark = pytest.mark.integration

# Override and declared are the same model on purpose: one API key, minimum
# cost, minimum drift risk. The decisive wire-check is ``model_overridden is
# True`` — if ``--model`` were not threaded through, that field would be
# False even with identical strings.
OVERRIDE_MODEL = "google_genai:gemini-2.5-flash-lite"
DECLARED_MODEL = "google_genai:gemini-2.5-flash-lite"


@pytest.fixture(autouse=True)
def _require_google_api_key():
    if not os.environ.get("GOOGLE_API_KEY"):
        pytest.skip("GOOGLE_API_KEY not set; skipping live Gemini integration test")


def test_cli_model_override_runs_and_records_manifest(tmp_path, capsys):
    art = tmp_path / "trivial-gemini"
    shutil.copytree(
        FIXTURES / "trivial-gemini",
        art,
        ignore=shutil.ignore_patterns("runs", "outs"),
    )

    rc = main(
        [
            "run",
            str(art),
            "--param",
            "topic=rain",
            "--model",
            OVERRIDE_MODEL,
        ]
    )
    assert rc == 0, f"main() returned {rc}; stderr: {capsys.readouterr().err}"

    runs = sorted((art / "runs").iterdir())
    assert len(runs) == 1, f"expected exactly one run directory, got {runs}"
    run_dir = runs[0]

    haiku = run_dir / "out" / "haiku.md"
    assert haiku.is_file(), f"expected declared output at {haiku}"
    content = haiku.read_text().strip()
    assert len(content) > 10, f"haiku is suspiciously empty: {content!r}"

    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert manifest["model"] == OVERRIDE_MODEL
    assert manifest["model_declared"] == DECLARED_MODEL
    assert manifest["model_overridden"] is True
