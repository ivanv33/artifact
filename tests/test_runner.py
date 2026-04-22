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
    shutil.copytree(src, target, ignore=shutil.ignore_patterns("runs", "outs"))
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
    assert manifest["model_declared"] == "anthropic:claude-sonnet-4-6"
    assert manifest["model_overridden"] is False


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


def test_run_stages_inputs(tmp_path):
    art = _copy_fixture("with-inputs", tmp_path)
    src_events = tmp_path / "source-events.json"
    src_events.write_text('[{"type":"Push"}]')

    executor = RecordingExecutor(outputs_to_write=["report.md"])
    run_dir = run(
        art,
        params={"user": "alice"},
        inputs={"events.json": str(src_events)},
        executor=executor,
    )

    staged = run_dir / "in" / "events.json"
    assert staged.is_file()
    assert staged.read_text() == '[{"type":"Push"}]'


def test_run_records_input_sha256(tmp_path):
    import hashlib
    import json as _json

    art = _copy_fixture("with-inputs", tmp_path)
    src_events = tmp_path / "events.json"
    data = b'[{"type":"Push"}]'
    src_events.write_bytes(data)
    expected = hashlib.sha256(data).hexdigest()

    executor = RecordingExecutor(outputs_to_write=["report.md"])
    run_dir = run(
        art, params={"user": "alice"}, inputs={"events.json": str(src_events)}, executor=executor
    )

    manifest = _json.loads((run_dir / "manifest.json").read_text())
    assert len(manifest["inputs"]) == 1
    rec = manifest["inputs"][0]
    assert rec["name"] == "events.json"
    assert rec["sha256"] == expected
    assert rec["source"] == str(src_events.resolve())


def test_run_templates_inputs_to_absolute_paths(tmp_path):
    art = _copy_fixture("with-inputs", tmp_path)
    src_events = tmp_path / "e.json"
    src_events.write_text("[]")

    executor = RecordingExecutor(outputs_to_write=["report.md"])
    run_dir = run(
        art, params={"user": "alice"}, inputs={"events.json": str(src_events)}, executor=executor
    )

    staged = (run_dir / "in" / "events.json").resolve()
    body = executor.calls[0]["templated_body"]
    assert str(staged) in body


def test_run_rejects_missing_input_declaration(tmp_path):
    art = _copy_fixture("with-inputs", tmp_path)
    executor = RecordingExecutor()
    with pytest.raises(RunnerError, match="events.json"):
        run(art, params={"user": "a"}, inputs={}, executor=executor)


def test_run_rejects_unknown_input(tmp_path):
    art = _copy_fixture("with-inputs", tmp_path)
    src = tmp_path / "e.json"
    src.write_text("[]")
    executor = RecordingExecutor()
    with pytest.raises(RunnerError, match="unknown input"):
        run(
            art,
            params={"user": "a"},
            inputs={"events.json": str(src), "extra.json": str(src)},
            executor=executor,
        )


def test_run_rejects_nonexistent_input_path(tmp_path):
    art = _copy_fixture("with-inputs", tmp_path)
    executor = RecordingExecutor()
    with pytest.raises(RunnerError, match="not found"):
        run(
            art,
            params={"user": "a"},
            inputs={"events.json": str(tmp_path / "missing.json")},
            executor=executor,
        )


def test_run_fails_if_declared_output_missing(tmp_path):
    art = _copy_fixture("trivial", tmp_path)
    executor = RecordingExecutor(outputs_to_write=[])  # writes nothing

    with pytest.raises(RunnerError, match="declared output missing"):
        run(art, params={}, inputs={}, executor=executor)


def test_run_warns_on_undeclared_output(tmp_path, capsys):
    art = _copy_fixture("trivial", tmp_path)

    class SurplusExecutor:
        def __call__(self, *, spec, run_dir, templated_body):
            out = run_dir / "out"
            out.mkdir(exist_ok=True)
            (out / "hello.md").write_text("hi")
            (out / "surprise.txt").write_text("extra")

    run(art, params={}, inputs={}, executor=SurplusExecutor())
    captured = capsys.readouterr()
    assert "surprise.txt" in captured.err
    assert "undeclared" in captured.err.lower()


def test_run_model_override_threads_to_executor(tmp_path):
    art = _copy_fixture("with-params", tmp_path)
    executor = RecordingExecutor(outputs_to_write=["report.md"])

    run(
        art,
        params={"user": "alice"},
        inputs={},
        executor=executor,
        model="claude_code:haiku",
    )

    assert len(executor.calls) == 1
    assert executor.calls[0]["spec"].model == "claude_code:haiku"


def test_run_no_model_override_preserves_declared(tmp_path):
    art = _copy_fixture("with-params", tmp_path)
    executor = RecordingExecutor(outputs_to_write=["report.md"])

    run(art, params={"user": "alice"}, inputs={}, executor=executor)

    assert len(executor.calls) == 1
    # The `with-params` fixture declares anthropic:claude-sonnet-4-6.
    assert executor.calls[0]["spec"].model == "anthropic:claude-sonnet-4-6"


def test_run_manifest_records_override(tmp_path):
    art = _copy_fixture("with-params", tmp_path)
    executor = RecordingExecutor(outputs_to_write=["report.md"])

    run_dir = run(
        art,
        params={"user": "alice"},
        inputs={},
        executor=executor,
        model="claude_code:haiku",
    )

    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert manifest["model"] == "claude_code:haiku"
    assert manifest["model_declared"] == "anthropic:claude-sonnet-4-6"
    assert manifest["model_overridden"] is True


def test_run_merges_executor_returned_dict_into_manifest(tmp_path):
    art = _copy_fixture("trivial", tmp_path)

    class MergingExecutor:
        def __call__(self, *, spec, run_dir, templated_body):
            (run_dir / "out" / "hello.md").write_text("hi")
            return {"claude_cli": {"session_id": "s1", "num_turns": 3}}

    run_dir = run(art, params={}, inputs={}, executor=MergingExecutor())
    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert manifest["claude_cli"] == {"session_id": "s1", "num_turns": 3}


def test_run_accepts_executor_returning_none(tmp_path):
    art = _copy_fixture("trivial", tmp_path)
    executor = RecordingExecutor(outputs_to_write=["hello.md"])

    run_dir = run(art, params={}, inputs={}, executor=executor)
    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert "claude_cli" not in manifest
