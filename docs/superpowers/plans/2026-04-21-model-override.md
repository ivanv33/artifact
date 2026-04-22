# `--model` Override Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `--model` CLI flag to `artifact run` that overrides the model declared in `ARTIFACT.md` for a single run, with manifest provenance recording both declared and effective model.

**Architecture:** `runner.run` gains a `model: str | None` kwarg. When set, the runner produces an overridden `Spec` via `dataclasses.replace(spec, model=model)` and hands *that* spec to the executor — no `Executor` protocol change. The manifest keeps `model` (sharpened semantics: effective model used) and gains `model_declared` (verbatim from `ARTIFACT.md`) and `model_overridden: bool`. CLI validates empty strings before calling the runner.

**Tech Stack:** Python 3.11+, argparse, `dataclasses.replace`, pytest. No new dependencies.

**Source of truth:** `docs/model-override-dd.md` in this worktree.

---

## File Structure

No new production files. No new test files.

**Modified:**
- `src/artifact/runner.py` — add `model` param to `run()`; thread overridden spec to executor; extend `_write_manifest` with `model_declared` / `model_overridden`.
- `src/artifact/cli.py` — add `--model` to `run` subparser; validate non-empty; pass through to `run_artifact`.
- `tests/test_runner.py` — append override-aware tests.
- `tests/test_cli.py` — append CLI-flag tests.

`src/artifact/spec.py` is untouched — `Spec` is already `frozen=True`, so `dataclasses.replace` works out of the box. `src/artifact/exec.py` is untouched — `deepagent_executor` already reads `spec.model`, so it automatically picks up the override.

---

## Task 1: Runner threads `model=` override to executor

Add the `model` kwarg to `runner.run` and, when set, dispatch to the executor with a spec whose `model` has been replaced. Manifest is NOT touched in this task — existing manifest tests must keep passing.

**Files:**
- Modify: `src/artifact/runner.py` (imports + `run()` signature + `run()` body around the executor call)
- Modify: `tests/test_runner.py` (append two tests)

### Step 1.1: Write the failing test for override-present

- [ ] Append to `tests/test_runner.py`:

```python
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
```

### Step 1.2: Run tests and confirm they fail

Run: `uv run pytest tests/test_runner.py::test_run_model_override_threads_to_executor tests/test_runner.py::test_run_no_model_override_preserves_declared -v`

Expected: `test_run_model_override_threads_to_executor` FAILS with `TypeError: run() got an unexpected keyword argument 'model'`. The second test PASSES already (it doesn't exercise the new kwarg).

### Step 1.3: Implement the override in `runner.run`

- [ ] In `src/artifact/runner.py`, add `dataclasses` to the imports. The current import block (lines 7–19) ends with `from artifact.timestamp import make_run_id`. Add `import dataclasses` alphabetically near the top:

```python
from __future__ import annotations

import dataclasses
import hashlib
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

from artifact.exec import Executor, noop_executor
from artifact.spec import Spec, parse_spec
from artifact.template import render
from artifact.timestamp import make_run_id
```

- [ ] Extend the `run()` signature to accept `model`. Replace the current signature (lines 26–33):

```python
def run(
    artifact_dir: str | Path,
    *,
    params: dict[str, str],
    inputs: dict[str, str],
    executor: Executor | None = None,
    now: datetime | None = None,
    model: str | None = None,
) -> Path:
```

- [ ] Update the `run()` docstring's `Args:` block to mention `model`. Insert after the `executor:` line and before `now:`:

```
        model: Optional override for ``spec.model``. When set, the executor
            receives a spec whose ``model`` has been replaced with this value;
            the parsed spec's declared model is preserved for the manifest.
```

- [ ] Thread the override into the executor call. Locate the executor dispatch (currently line 78):

```python
    (executor or noop_executor)(spec=spec, run_dir=run_dir, templated_body=templated_body)
```

Replace it with:

```python
    spec_for_exec = (
        dataclasses.replace(spec, model=model) if model is not None else spec
    )
    (executor or noop_executor)(
        spec=spec_for_exec, run_dir=run_dir, templated_body=templated_body
    )
```

### Step 1.4: Run the new tests and confirm they pass

Run: `uv run pytest tests/test_runner.py::test_run_model_override_threads_to_executor tests/test_runner.py::test_run_no_model_override_preserves_declared -v`

Expected: both PASS.

### Step 1.5: Run the full test suite to catch regressions

Run: `uv run pytest -v`

Expected: all previously-passing tests still pass. Nothing in the manifest has changed yet.

### Step 1.6: Commit

```bash
git add src/artifact/runner.py tests/test_runner.py
git commit -m "feat(runner): thread --model override to executor via dataclasses.replace"
```

---

## Task 2: Manifest records `model_declared` and `model_overridden`

Sharpen `model` in the manifest to always mean *effective* model, add `model_declared` (verbatim from the parsed spec) and `model_overridden: bool`. This task updates `_write_manifest` and backfills the existing manifest test to assert the new fields in their unset-override shape.

**Files:**
- Modify: `src/artifact/runner.py` (`run()` call to `_write_manifest`, and `_write_manifest` body)
- Modify: `tests/test_runner.py` (extend existing `test_run_writes_manifest`, add one new test)

### Step 2.1: Write the failing test for manifest-with-override

- [ ] Append to `tests/test_runner.py`:

```python
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
```

### Step 2.2: Extend the existing no-override manifest test

- [ ] In `tests/test_runner.py`, locate `test_run_writes_manifest` (around line 51). Add these assertions at the end of the function, after `assert manifest["inputs"] == []`:

```python
    assert manifest["model_declared"] == "anthropic:claude-sonnet-4-6"
    assert manifest["model_overridden"] is False
```

### Step 2.3: Run the two tests and confirm they fail

Run: `uv run pytest tests/test_runner.py::test_run_writes_manifest tests/test_runner.py::test_run_manifest_records_override -v`

Expected: `test_run_manifest_records_override` FAILS with `KeyError: 'model_declared'` (or similar). `test_run_writes_manifest` FAILS on the new `model_declared` assertion.

### Step 2.4: Implement the manifest changes

- [ ] In `src/artifact/runner.py`, update the `_write_manifest` call site inside `run()`. The current block (lines 82–89):

```python
    _write_manifest(
        run_dir=run_dir,
        spec=spec,
        artifact_dir=artifact_dir,
        resolved_params=resolved_params,
        input_records=input_records,
        now=now,
    )
```

Replace with:

```python
    _write_manifest(
        run_dir=run_dir,
        spec=spec,
        artifact_dir=artifact_dir,
        resolved_params=resolved_params,
        input_records=input_records,
        now=now,
        model_override=model,
    )
```

- [ ] Update `_write_manifest`'s signature and body. Replace the whole function (lines 169–193) with:

```python
def _write_manifest(
    *,
    run_dir: Path,
    spec: Spec,
    artifact_dir: Path,
    resolved_params: dict[str, object],
    input_records: list[dict],
    now: datetime,
    model_override: str | None,
) -> None:
    """Write ``manifest.json`` capturing full run provenance.

    Args:
        run_dir: Run directory receiving ``manifest.json``.
        spec: The parsed spec. ``spec.model`` is the declared model.
        artifact_dir: Artifact root (for the ``artifact`` field).
        resolved_params: Effective params after default merging.
        input_records: Per-input manifest records (name/sha256/source).
        now: Timestamp for the ``timestamp`` field.
        model_override: Value passed to ``run(..., model=...)``; ``None`` when
            unset. When set, ``model`` (effective) differs from
            ``model_declared``.
    """
    effective_model = model_override if model_override is not None else spec.model
    manifest = {
        "artifact": artifact_dir.name,
        "run_id": run_dir.name,
        "timestamp": now.isoformat(timespec="seconds"),
        "artifact_md_sha256": spec.artifact_sha256,
        "executor": spec.executor,
        "model": effective_model,
        "model_declared": spec.model,
        "model_overridden": model_override is not None,
        "inputs": input_records,
        "params": resolved_params,
        "outputs": [o.name for o in spec.outputs],
        "promoted_to": [],
    }
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
```

### Step 2.5: Run the two targeted tests and confirm they pass

Run: `uv run pytest tests/test_runner.py::test_run_writes_manifest tests/test_runner.py::test_run_manifest_records_override -v`

Expected: both PASS.

### Step 2.6: Run the full suite

Run: `uv run pytest -v`

Expected: all tests pass. If any promote/introspect test inspects the manifest shape strictly, it should still pass — we only added keys; `model` remains present with the same meaning when no override is given.

### Step 2.7: Commit

```bash
git add src/artifact/runner.py tests/test_runner.py
git commit -m "feat(runner): record model_declared and model_overridden in manifest"
```

---

## Task 3: CLI `--model` flag

Wire `--model` into the `run` subparser. Reject empty string before any run directory is created. Thread the validated string into `run_artifact(...)`.

**Files:**
- Modify: `src/artifact/cli.py` (`build_parser` — add argument; `main` — validate + pass through)
- Modify: `tests/test_cli.py` (append three tests)

### Step 3.1: Write the failing tests

- [ ] Append to `tests/test_cli.py`:

```python
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
```

### Step 3.2: Run the tests and confirm they fail

Run: `uv run pytest tests/test_cli.py::test_run_cli_passes_model_override_to_runner tests/test_cli.py::test_run_cli_rejects_empty_model tests/test_cli.py::test_run_cli_without_model_preserves_declared -v`

Expected: the override and empty-string tests FAIL with `argparse` errors like `unrecognized arguments: --model claude_code:haiku`. The third test PASSES already.

### Step 3.3: Add `--model` to the `run` subparser

- [ ] In `src/artifact/cli.py`, locate the block that adds `--promote-as` to the `run` subparser (currently lines 53–59):

```python
    run.add_argument(
        "--promote-as",
        dest="promote_as",
        default=None,
        metavar="LABEL",
        help="Also promote the newly-created run under outs/<LABEL>/.",
    )
```

Insert immediately *before* it:

```python
    run.add_argument(
        "--model",
        dest="model",
        default=None,
        metavar="PROVIDER:NAME",
        help="Override ARTIFACT.md's model for this run. Opaque to artifact.",
    )
```

### Step 3.4: Validate and pass through in `main`

- [ ] In `src/artifact/cli.py`, locate the `run` branch of `main` (currently starts around line 122):

```python
    if args.cmd == "run":
        params = _split_kv(args.param, "--param")
        inputs = _split_kv(args.input, "--input")
        try:
            run_dir = run_artifact(
                args.artifact_dir,
                params=params,
                inputs=inputs,
                executor=executor or deepagent_executor,
            )
            if args.promote_as:
                promote_run(args.artifact_dir, run_dir.name, label=args.promote_as)
        except (ValueError, OSError) as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        print(run_dir)
        return 0
```

Replace with:

```python
    if args.cmd == "run":
        if args.model is not None and args.model == "":
            print("error: --model requires a non-empty string", file=sys.stderr)
            return 1
        params = _split_kv(args.param, "--param")
        inputs = _split_kv(args.input, "--input")
        try:
            run_dir = run_artifact(
                args.artifact_dir,
                params=params,
                inputs=inputs,
                executor=executor or deepagent_executor,
                model=args.model,
            )
            if args.promote_as:
                promote_run(args.artifact_dir, run_dir.name, label=args.promote_as)
        except (ValueError, OSError) as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        print(run_dir)
        return 0
```

Note: the empty-string check runs *before* `_split_kv` and *before* any runner call, so no `runs/<id>/` directory is created on rejection.

### Step 3.5: Run the three tests and confirm they pass

Run: `uv run pytest tests/test_cli.py::test_run_cli_passes_model_override_to_runner tests/test_cli.py::test_run_cli_rejects_empty_model tests/test_cli.py::test_run_cli_without_model_preserves_declared -v`

Expected: all three PASS.

### Step 3.6: Run the full test suite

Run: `uv run pytest -v`

Expected: all tests pass, including the new ones from Tasks 1, 2, and 3.

### Step 3.7: Smoke-test the CLI help text

Run: `uv run artifact run --help`

Expected: output includes `--model PROVIDER:NAME` with the help string "Override ARTIFACT.md's model for this run. Opaque to artifact."

### Step 3.8: Commit

```bash
git add src/artifact/cli.py tests/test_cli.py
git commit -m "feat(cli): add --model override flag to artifact run"
```

---

## Self-Review Checklist

**Spec coverage** (cross-check against `docs/model-override-dd.md`):
- [x] `--model STR` on `artifact run` — Task 3
- [x] Empty-string rejection with exact error message and exit 1 before runner invocation — Task 3 (Step 3.4)
- [x] `runner.run(...)` gains `model: str | None = None` — Task 1
- [x] `dataclasses.replace(spec, model=model)` threaded into executor — Task 1 (Step 1.3)
- [x] No `Executor` protocol change — verified: `exec.py` untouched
- [x] `_write_manifest` takes original spec + override string — Task 2 (Step 2.4)
- [x] Manifest gains `model_declared`, `model_overridden`; `model` becomes effective — Task 2
- [x] Three DD-specified tests: override present / override absent / empty string — Task 1 (override present + absent), Task 2 (manifest with/without override), Task 3 (empty string)

**Placeholder scan:** no "TBD", "TODO", "similar to", "add error handling" — all steps contain executable code or exact commands.

**Type consistency:**
- `model: str | None = None` — consistent across `runner.run` signature, `_write_manifest` parameter (`model_override: str | None`), and `cli.py` (`args.model` from argparse with `default=None`).
- `model_overridden: bool` — written as `model_override is not None` in the manifest, asserted as `is True` / `is False` in tests.
- `effective_model` / `spec.model` — no naming drift.

**Out of scope (per DD non-goals, explicitly NOT in this plan):**
- No promotion-time `--model` override.
- No `ARTIFACT_MODEL` env var.
- No per-param or per-step routing.
- No new executor; `exec.py` is not modified.
- No LangSmith wiring.
- No integration test (DD: "The override changes a string, not dispatch behavior.").
