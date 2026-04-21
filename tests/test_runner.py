import json
import shutil
from pathlib import Path

import pytest

from artifact.exec import Executor
from artifact.runner import RunnerError, run

FIXTURES = Path(__file__).parent / "fixtures"


def _copy_fixture(name: str, dest: Path) -> Path:
    src = FIXTURES / name
    target = dest / name
    shutil.copytree(src, target)
    return target


class RecordingExecutor:
    """An Executor that records inputs and writes declared outputs as empty files."""

    def __init__(self, outputs_to_write: list[str] | None = None) -> None:
        self.calls: list[dict] = []
        self.outputs_to_write = outputs_to_write or []

    def __call__(self, *, spec, run_dir: Path, templated_body: str) -> None:
        self.calls.append(
            {"spec": spec, "run_dir": run_dir, "templated_body": templated_body}
        )
        out_dir = run_dir / "out"
        out_dir.mkdir(exist_ok=True)
        for name in self.outputs_to_write:
            (out_dir / name).write_text("")


def test_run_creates_run_directory(tmp_path):
    art = _copy_fixture("trivial", tmp_path)
    executor = RecordingExecutor(outputs_to_write=["hello.md"])

    run_dir = run(art, params={}, inputs={}, executor=executor)

    assert run_dir.parent == art / "runs"
    assert run_dir.exists()
    assert (run_dir / "in").is_dir()
    assert (run_dir / "out").is_dir()
    assert (run_dir / "params.json").is_file()
    assert (run_dir / "manifest.json").is_file()


def test_run_writes_manifest(tmp_path):
    art = _copy_fixture("with-params", tmp_path)
    executor = RecordingExecutor(outputs_to_write=["report.md"])

    run_dir = run(
        art, params={"user": "alice"}, inputs={}, executor=executor
    )

    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert manifest["artifact"] == "with-params"
    assert manifest["run_id"] == run_dir.name
    assert manifest["executor"] == "deepagent"
    assert manifest["model"] == "anthropic:claude-sonnet-4-6"
    assert manifest["params"] == {"user": "alice", "focus": "general"}
    assert manifest["outputs"] == ["report.md"]
    assert manifest["promoted_to"] == []
    assert len(manifest["artifact_md_sha256"]) == 64
    assert manifest["inputs"] == []


def test_run_templates_params_in_body(tmp_path):
    art = _copy_fixture("with-params", tmp_path)
    executor = RecordingExecutor(outputs_to_write=["report.md"])

    run(art, params={"user": "alice", "focus": "security"}, inputs={}, executor=executor)

    assert len(executor.calls) == 1
    body = executor.calls[0]["templated_body"]
    assert "{{ params.user }}" not in body
    assert "alice" in body
    assert "security" in body


def test_run_applies_param_defaults(tmp_path):
    art = _copy_fixture("with-params", tmp_path)
    executor = RecordingExecutor(outputs_to_write=["report.md"])

    run_dir = run(art, params={"user": "alice"}, inputs={}, executor=executor)

    params = json.loads((run_dir / "params.json").read_text())
    assert params == {"user": "alice", "focus": "general"}


def test_run_rejects_missing_required_param(tmp_path):
    art = _copy_fixture("with-params", tmp_path)
    executor = RecordingExecutor()

    with pytest.raises(RunnerError, match="user"):
        run(art, params={}, inputs={}, executor=executor)


def test_run_rejects_unknown_param(tmp_path):
    art = _copy_fixture("with-params", tmp_path)
    executor = RecordingExecutor()

    with pytest.raises(RunnerError, match="unknown param"):
        run(art, params={"user": "a", "nope": "x"}, inputs={}, executor=executor)
