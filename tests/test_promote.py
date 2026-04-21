import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest

from artifact.promote import PromoteError, promote
from artifact.runner import run

FIXTURES = Path(__file__).parent / "fixtures"

NOW_1 = datetime(2026, 4, 19, 14, 23, 1, tzinfo=timezone.utc)
NOW_2 = datetime(2026, 4, 19, 14, 23, 2, tzinfo=timezone.utc)


class _FakeExecutor:
    def __init__(self, outputs: list[str]) -> None:
        self.outputs = outputs

    def __call__(self, *, spec, run_dir, templated_body):
        out = run_dir / "out"
        out.mkdir(exist_ok=True)
        for name in self.outputs:
            (out / name).write_text("content")


def _make_run(
    tmp_path: Path,
    fixture: str,
    outputs: list[str],
    *,
    now: datetime | None = None,
    **kwargs,
) -> Path:
    src = FIXTURES / fixture
    dst = tmp_path / fixture
    if not dst.exists():
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns("runs", "outs"))
    return run(dst, executor=_FakeExecutor(outputs), now=now, **kwargs)


def test_promote_copies_full_run_directory(tmp_path):
    run_dir = _make_run(tmp_path, "trivial", ["hello.md"], now=NOW_1, params={}, inputs={})
    artifact_dir = run_dir.parent.parent

    out_path = promote(artifact_dir, run_dir.name, label="alice")

    assert out_path == artifact_dir / "outs" / "alice"
    assert (out_path / "manifest.json").is_file()
    assert (out_path / "out" / "hello.md").read_text() == "content"
    assert (out_path / "in").is_dir()
    assert (out_path / "params.json").is_file()


def test_promote_is_a_copy_not_a_symlink(tmp_path):
    run_dir = _make_run(tmp_path, "trivial", ["hello.md"], now=NOW_1, params={}, inputs={})
    artifact_dir = run_dir.parent.parent

    out_path = promote(artifact_dir, run_dir.name, label="v1")

    assert not out_path.is_symlink()
    for p in out_path.rglob("*"):
        assert not p.is_symlink(), f"{p} is a symlink"


def test_promote_updates_manifest_in_both_locations(tmp_path):
    run_dir = _make_run(tmp_path, "trivial", ["hello.md"], now=NOW_1, params={}, inputs={})
    artifact_dir = run_dir.parent.parent

    promote(artifact_dir, run_dir.name, label="alice")

    run_manifest = json.loads((run_dir / "manifest.json").read_text())
    out_manifest = json.loads((artifact_dir / "outs" / "alice" / "manifest.json").read_text())
    assert "alice" in run_manifest["promoted_to"]
    assert "alice" in out_manifest["promoted_to"]


def test_promote_overwrites_existing_label(tmp_path):
    r1 = _make_run(tmp_path, "trivial", ["hello.md"], now=NOW_1, params={}, inputs={})
    artifact_dir = r1.parent.parent
    promote(artifact_dir, r1.name, label="latest")

    r2 = _make_run(tmp_path, "trivial", ["hello.md"], now=NOW_2, params={}, inputs={})
    assert r2.parent == r1.parent
    assert r1.name != r2.name

    promote(artifact_dir, r2.name, label="latest")

    out_manifest = json.loads((artifact_dir / "outs" / "latest" / "manifest.json").read_text())
    assert out_manifest["run_id"] == r2.name


def test_promote_rejects_missing_run(tmp_path):
    src = FIXTURES / "trivial"
    dst = tmp_path / "trivial"
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("runs", "outs"))
    with pytest.raises(PromoteError, match="run not found"):
        promote(dst, "does-not-exist", label="x")
