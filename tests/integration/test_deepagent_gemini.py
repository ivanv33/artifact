"""End-to-end integration test using a real (cheap) Gemini model.

Opt-in via ``pytest -m integration``. Skipped when ``GOOGLE_API_KEY`` is not
set in the environment or in ``.env``.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from artifact.exec import deepagent_executor
from artifact.runner import run

FIXTURES = Path(__file__).parent / "fixtures"


pytestmark = [pytest.mark.integration, pytest.mark.forked]


@pytest.fixture(autouse=True)
def _require_google_api_key():
    if not os.environ.get("GOOGLE_API_KEY"):
        pytest.skip("GOOGLE_API_KEY not set; skipping live Gemini integration test")


def test_deepagent_produces_declared_output(tmp_path):
    art = tmp_path / "trivial-gemini"
    shutil.copytree(
        FIXTURES / "trivial-gemini",
        art,
        ignore=shutil.ignore_patterns("runs", "outs"),
    )

    run_dir = run(
        art,
        params={"topic": "rain"},
        inputs={},
        executor=deepagent_executor,
    )

    haiku = run_dir / "out" / "haiku.md"
    assert haiku.is_file(), f"expected declared output at {haiku}"
    content = haiku.read_text().strip()
    assert len(content) > 10, f"haiku is suspiciously empty: {content!r}"
