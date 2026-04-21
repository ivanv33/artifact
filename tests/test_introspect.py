import shutil
from datetime import datetime, timezone
from pathlib import Path

from artifact.introspect import list_runs, show
from artifact.promote import promote
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
            (out / name).write_text("x")


def test_list_runs_empty(tmp_path):
    src = FIXTURES / "trivial"
    dst = tmp_path / "trivial"
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("runs", "outs"))
    assert list_runs(dst) == []


def test_list_runs_newest_first(tmp_path):
    src = FIXTURES / "with-params"
    dst = tmp_path / "with-params"
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("runs", "outs"))

    run(dst, params={"user": "a"}, inputs={}, executor=_FakeExecutor(["report.md"]), now=NOW_1)
    run(dst, params={"user": "b"}, inputs={}, executor=_FakeExecutor(["report.md"]), now=NOW_2)

    rows = list_runs(dst)
    assert len(rows) == 2
    assert rows[0].run_id > rows[1].run_id  # newest first
    assert rows[0].params["user"] == "b"
    assert rows[1].params["user"] == "a"


def test_list_runs_shows_promoted_labels(tmp_path):
    src = FIXTURES / "trivial"
    dst = tmp_path / "trivial"
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("runs", "outs"))

    rd = run(dst, params={}, inputs={}, executor=_FakeExecutor(["hello.md"]), now=NOW_1)
    promote(dst, rd.name, label="alice")

    rows = list_runs(dst)
    assert rows[0].promoted_to == ["alice"]


def test_show_prints_frontmatter_and_labels(tmp_path):
    src = FIXTURES / "with-params"
    dst = tmp_path / "with-params"
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("runs", "outs"))

    rd = run(dst, params={"user": "a"}, inputs={}, executor=_FakeExecutor(["report.md"]), now=NOW_1)
    promote(dst, rd.name, label="alice")

    text = show(dst)
    assert "kind: transform" in text
    assert "executor: deepagent" in text
    assert "model: anthropic:claude-sonnet-4-6" in text
    assert "labels:" in text
    assert "- alice" in text
