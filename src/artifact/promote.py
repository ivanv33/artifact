"""Promote a run to a label.

Promotion = copy ``runs/<id>/`` in its entirety to ``outs/<label>/`` (never a
symlink, per design doc invariant 3) and record the label on both manifests'
``promoted_to`` list.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path


class PromoteError(ValueError):
    """Raised when promotion fails (missing run, filesystem error, etc.)."""


def promote(artifact_dir: str | Path, run_id: str, *, label: str) -> Path:
    """Copy ``runs/<run_id>/`` to ``outs/<label>/`` and update both manifests.

    Any existing ``outs/<label>/`` is removed and replaced.

    Args:
        artifact_dir: Path to the artifact directory.
        run_id: Basename of the run to promote (must exist in ``runs/``).
        label: The label name to create under ``outs/``.

    Returns:
        The path to the new ``outs/<label>/`` directory.

    Raises:
        PromoteError: If the run is missing.
    """
    artifact_dir = Path(artifact_dir).resolve()
    run_dir = artifact_dir / "runs" / run_id
    if not run_dir.is_dir():
        raise PromoteError(f"run not found: {run_dir}")

    outs_dir = artifact_dir / "outs"
    target = outs_dir / label
    if target.exists():
        shutil.rmtree(target)
    outs_dir.mkdir(exist_ok=True)
    shutil.copytree(run_dir, target, symlinks=False)

    _append_label(run_dir / "manifest.json", label)
    _append_label(target / "manifest.json", label)

    return target


def _append_label(manifest_path: Path, label: str) -> None:
    """Append ``label`` to ``promoted_to`` in the manifest at ``manifest_path`` (idempotent)."""
    data = json.loads(manifest_path.read_text())
    promoted = list(data.get("promoted_to", []))
    if label not in promoted:
        promoted.append(label)
    data["promoted_to"] = promoted
    manifest_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
