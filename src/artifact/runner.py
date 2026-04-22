"""Orchestrate one run of an artifact.

The runner sequences: parse → resolve params → resolve inputs → create run dir
→ stage inputs → template body → dispatch executor → verify outputs → write manifest.
"""

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


class RunnerError(ValueError):
    """Raised for any user-facing run failure (bad params, missing inputs, etc.)."""


def run(
    artifact_dir: str | Path,
    *,
    params: dict[str, str],
    inputs: dict[str, str],
    executor: Executor | None = None,
    now: datetime | None = None,
    model: str | None = None,
) -> Path:
    """Execute one run of an artifact.

    Args:
        artifact_dir: Path to the artifact directory containing ``ARTIFACT.md``.
        params: Explicit param values, by name.
        inputs: Explicit input file paths, by declared input name. Each source
            file is copied to runs/<id>/in/<name>, SHA-256'd, and its absolute
            staged path made available to the template as {{ inputs.<name> }}.
        executor: Callable satisfying ``Executor``. Defaults to ``noop_executor``.
        model: Optional override for ``spec.model``. When set, the executor
            receives a spec whose ``model`` has been replaced with this value;
            the parsed spec's declared model is preserved for the manifest.
        now: Override for the run's timestamp (used for ``run_id`` and manifest
            timestamp). Defaults to wall clock; tests pass a fixed datetime for
            deterministic run IDs.

    Returns:
        The path of the newly created run directory under ``runs/``.

    Raises:
        RunnerError: If params or inputs are invalid.
        SpecError: If the artifact's ``ARTIFACT.md`` is malformed.
    """
    artifact_dir = Path(artifact_dir).resolve()
    spec = parse_spec(artifact_dir / "ARTIFACT.md")

    resolved_params = _resolve_params(spec, params)
    input_plan = _resolve_inputs(spec, inputs)

    if now is None:
        now = datetime.now().astimezone()
    run_id = make_run_id(now=now)
    run_dir = artifact_dir / "runs" / run_id
    (run_dir / "in").mkdir(parents=True, exist_ok=False)
    (run_dir / "out").mkdir(parents=True, exist_ok=False)

    input_records = _stage_inputs(input_plan, run_dir)

    (run_dir / "params.json").write_text(
        json.dumps(resolved_params, indent=2, sort_keys=True) + "\n"
    )

    input_paths = {
        rec["name"]: str((run_dir / "in" / rec["name"]).resolve()) for rec in input_records
    }
    templated_body = render(spec.body, params=resolved_params, inputs=input_paths)

    spec_for_exec = (
        dataclasses.replace(spec, model=model) if model is not None else spec
    )
    manifest_extra = (executor or noop_executor)(
        spec=spec_for_exec, run_dir=run_dir, templated_body=templated_body
    )

    _verify_outputs(spec, run_dir)

    _write_manifest(
        run_dir=run_dir,
        spec=spec,
        artifact_dir=artifact_dir,
        resolved_params=resolved_params,
        input_records=input_records,
        now=now,
        model_override=model,
        manifest_extra=manifest_extra,
    )

    return run_dir


def _resolve_params(spec: Spec, supplied: dict[str, str]) -> dict[str, object]:
    """Merge supplied params with declared defaults; raise on unknown or missing required."""
    declared = {p.name: p for p in spec.params}
    unknown = set(supplied) - set(declared)
    if unknown:
        raise RunnerError(f"unknown param(s): {sorted(unknown)}")

    resolved: dict[str, object] = {}
    for name, p in declared.items():
        if name in supplied:
            resolved[name] = supplied[name]
        elif p.required and p.default is None:
            raise RunnerError(f"required param missing: {name}")
        else:
            resolved[name] = p.default
    return resolved


def _resolve_inputs(spec: Spec, supplied: dict[str, str]) -> dict[str, Path]:
    """Validate that supplied inputs match declared ones and all source files exist."""
    declared = {i.name for i in spec.inputs}
    unknown = set(supplied) - declared
    if unknown:
        raise RunnerError(f"unknown input(s): {sorted(unknown)}")
    missing = declared - set(supplied)
    if missing:
        raise RunnerError(f"input(s) not supplied: {sorted(missing)}")

    plan: dict[str, Path] = {}
    for name, raw in supplied.items():
        p = Path(raw).resolve()
        if not p.is_file():
            raise RunnerError(f"input {name!r}: file not found at {p}")
        plan[name] = p
    return plan


def _verify_outputs(spec: Spec, run_dir: Path) -> None:
    """Enforce that every declared output exists; warn on extras.

    Args:
        spec: The parsed spec whose ``outputs`` list is the authority.
        run_dir: The run directory whose ``out/`` is being inspected.

    Raises:
        RunnerError: If a declared output is missing from ``run_dir/out/``.
    """
    out_dir = run_dir / "out"
    declared = {o.name for o in spec.outputs}
    present = {p.name for p in out_dir.iterdir()} if out_dir.is_dir() else set()

    missing = declared - present
    if missing:
        raise RunnerError(f"declared output missing in out/: {sorted(missing)}")

    extra = present - declared
    if extra:
        print(
            f"warning: undeclared output file(s) in {out_dir}: {sorted(extra)}",
            file=sys.stderr,
        )


def _stage_inputs(plan: dict[str, Path], run_dir: Path) -> list[dict]:
    """Copy each input into ``run_dir/in/<name>`` and return per-input manifest records."""
    records: list[dict] = []
    for name, source in plan.items():
        dest = run_dir / "in" / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        sha = hashlib.sha256(dest.read_bytes()).hexdigest()
        records.append({"name": name, "sha256": sha, "source": str(source)})
    return records


def _write_manifest(
    *,
    run_dir: Path,
    spec: Spec,
    artifact_dir: Path,
    resolved_params: dict[str, object],
    input_records: list[dict],
    now: datetime,
    model_override: str | None,
    manifest_extra: dict | None = None,
) -> None:
    """Write ``manifest.json`` capturing full run provenance."""
    effective_model = model_override if model_override is not None else spec.model
    manifest: dict = {
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
    if manifest_extra:
        manifest.update(manifest_extra)
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
