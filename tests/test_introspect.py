import itertools
import shutil
from pathlib import Path

import artifact.runner as runner_module
from artifact.introspect import list_runs, show
from artifact.promote import promote
from artifact.runner import run

FIXTURES = Path(__file__).parent / "fixtures"


class _FakeExecutor:
    def __init__(self, outputs: list[str]) -> None:
        self.outputs = outputs

    def __call__(self, *, spec, run_dir, templated_body):
        out = run_dir / "out"
        out.mkdir(exist_ok=True)
        for name in self.outputs:
            (out / name).write_text("x")


def _counter_run_ids(monkeypatch):
    counter = itertools.count(1)
    monkeypatch.setattr(
        runner_module, "make_run_id",
        lambda *, now=None: f"2026-04-19T14-23-0{next(counter)}-0700",
    )


def test_list_runs_empty(tmp_path):
    src = FIXTURES / "trivial"
    dst = tmp_path / "trivial"
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("runs", "outs"))
    assert list_runs(dst) == []


def test_list_runs_newest_first(tmp_path, monkeypatch):
    _counter_run_ids(monkeypatch)
    src = FIXTURES / "with-params"
    dst = tmp_path / "with-params"
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("runs", "outs"))

    run(dst, params={"user": "a"}, inputs={}, executor=_FakeExecutor(["report.md"]))
    run(dst, params={"user": "b"}, inputs={}, executor=_FakeExecutor(["report.md"]))

    rows = list_runs(dst)
    assert len(rows) == 2
    assert rows[0].run_id > rows[1].run_id  # newest first
    assert rows[0].params["user"] == "b"
    assert rows[1].params["user"] == "a"


def test_list_runs_shows_promoted_labels(tmp_path, monkeypatch):
    _counter_run_ids(monkeypatch)
    src = FIXTURES / "trivial"
    dst = tmp_path / "trivial"
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("runs", "outs"))

    rd = run(dst, params={}, inputs={}, executor=_FakeExecutor(["hello.md"]))
    promote(dst, rd.name, label="alice")

    rows = list_runs(dst)
    assert rows[0].promoted_to == ["alice"]


def test_show_prints_frontmatter_and_labels(tmp_path, monkeypatch):
    _counter_run_ids(monkeypatch)
    src = FIXTURES / "with-params"
    dst = tmp_path / "with-params"
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("runs", "outs"))

    rd = run(dst, params={"user": "a"}, inputs={}, executor=_FakeExecutor(["report.md"]))
    promote(dst, rd.name, label="alice")

    text = show(dst)
    assert "kind: transform" in text
    assert "executor: deepagent" in text
    assert "model: anthropic:claude-sonnet-4-6" in text
    assert "labels:" in text
    assert "- alice" in text
