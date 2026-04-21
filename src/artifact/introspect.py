"""Read-only inspection of an artifact directory: list runs and show spec + labels."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from artifact.spec import parse_spec


@dataclass(frozen=True)
class RunRow:
    """One row summarizing a run for the ``artifact runs`` listing.

    Attributes:
        run_id: Basename of the run directory.
        timestamp: ISO-8601 timestamp string from the run's manifest.
        params: The resolved param values for that run.
        promoted_to: Labels under ``outs/`` pointing at this run.
    """

    run_id: str
    timestamp: str
    params: dict
    promoted_to: list[str]


def list_runs(artifact_dir: str | Path) -> list[RunRow]:
    """List runs of an artifact, newest-first.

    Args:
        artifact_dir: Path to the artifact directory.

    Returns:
        A list of ``RunRow`` sorted newest-first. Empty if ``runs/`` is absent.
    """
    artifact_dir = Path(artifact_dir).resolve()
    runs_dir = artifact_dir / "runs"
    if not runs_dir.is_dir():
        return []

    rows: list[RunRow] = []
    for entry in runs_dir.iterdir():
        if not entry.is_dir():
            continue
        manifest_path = entry / "manifest.json"
        if not manifest_path.is_file():
            continue
        m = json.loads(manifest_path.read_text())
        rows.append(
            RunRow(
                run_id=m.get("run_id", entry.name),
                timestamp=m.get("timestamp", ""),
                params=dict(m.get("params", {})),
                promoted_to=list(m.get("promoted_to", [])),
            )
        )
    rows.sort(key=lambda r: r.run_id, reverse=True)
    return rows


def show(artifact_dir: str | Path) -> str:
    """Render a human-readable summary of an artifact and its current labels.

    Args:
        artifact_dir: Path to the artifact directory.

    Returns:
        Multi-line text ending with a trailing newline.

    Raises:
        SpecError: If the artifact's ``ARTIFACT.md`` is malformed.
    """
    artifact_dir = Path(artifact_dir).resolve()
    spec = parse_spec(artifact_dir / "ARTIFACT.md")

    outs = artifact_dir / "outs"
    labels = sorted(p.name for p in outs.iterdir() if p.is_dir()) if outs.is_dir() else []

    lines = [
        f"artifact: {artifact_dir.name}",
        f"kind: {spec.kind}",
        f"executor: {spec.executor}",
        f"model: {spec.model}",
        f"inputs: {[i.name for i in spec.inputs]}",
        f"params: {[p.name for p in spec.params]}",
        f"outputs: {[o.name for o in spec.outputs]}",
        "labels:",
    ]
    lines.extend(f"  - {label}" for label in labels)
    return "\n".join(lines) + "\n"
