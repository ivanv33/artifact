"""Orchestrate one run of an artifact.

The runner sequences: parse → resolve params → create run dir → template body
→ dispatch executor → write manifest. Input staging and output verification
are added in later stages.
"""

from __future__ import annotations

import json
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
) -> Path:
    """Execute one run of an artifact.

    Args:
        artifact_dir: Path to the artifact directory containing ``ARTIFACT.md``.
        params: Explicit param values, by name.
        inputs: Explicit input file paths, by declared input name. Unused in
            Stage 3; staged in Stage 4.
        executor: Callable satisfying ``Executor``. Defaults to ``noop_executor``.

    Returns:
        The path of the newly created run directory under ``runs/``.

    Raises:
        RunnerError: If params or inputs are invalid.
        SpecError: If the artifact's ``ARTIFACT.md`` is malformed.
    """
    artifact_dir = Path(artifact_dir).resolve()
    spec = parse_spec(artifact_dir / "ARTIFACT.md")

    resolved_params = _resolve_params(spec, params)

    now = datetime.now().astimezone()
    run_id = make_run_id(now=now)
    run_dir = artifact_dir / "runs" / run_id
    (run_dir / "in").mkdir(parents=True, exist_ok=False)
    (run_dir / "out").mkdir(parents=True, exist_ok=False)

    (run_dir / "params.json").write_text(
        json.dumps(resolved_params, indent=2, sort_keys=True) + "\n"
    )

    templated_body = render(spec.body, params=resolved_params, inputs={})

    (executor or noop_executor)(spec=spec, run_dir=run_dir, templated_body=templated_body)

    _write_manifest(
        run_dir=run_dir,
        spec=spec,
        artifact_dir=artifact_dir,
        resolved_params=resolved_params,
        input_records=[],
        now=now,
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


def _write_manifest(
    *,
    run_dir: Path,
    spec: Spec,
    artifact_dir: Path,
    resolved_params: dict[str, object],
    input_records: list[dict],
    now: datetime,
) -> None:
    """Write ``manifest.json`` capturing full run provenance."""
    manifest = {
        "artifact": artifact_dir.name,
        "run_id": run_dir.name,
        "timestamp": now.isoformat(timespec="seconds"),
        "artifact_md_sha256": spec.artifact_sha256,
        "executor": spec.executor,
        "model": spec.model,
        "inputs": input_records,
        "params": resolved_params,
        "outputs": [o.name for o in spec.outputs],
        "promoted_to": [],
    }
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
