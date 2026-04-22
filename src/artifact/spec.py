"""Parse and validate an ``ARTIFACT.md`` file into a typed ``Spec``.

The module's only responsibility is path-in, ``Spec``-out (or raise
``SpecError``). It knows nothing about runs, filesystems, or executors.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.DOTALL)

ALLOWED_KINDS = {"transform"}
ALLOWED_EXECUTORS = {"deepagent", "claude_cli"}
ALLOWED_PARAM_TYPES = {"string", "int", "float", "bool"}


class SpecError(ValueError):
    """Raised when an ``ARTIFACT.md`` fails to parse or validate."""


@dataclass(frozen=True)
class Input:
    """A declared input file the artifact consumes.

    Attributes:
        name: The filename the artifact refers to (e.g. ``events.json``).
        desc: Human-readable description of the input.
    """

    name: str
    desc: str


@dataclass(frozen=True)
class Param:
    """A declared scalar parameter.

    Attributes:
        name: Parameter name.
        type: One of ``string``, ``int``, ``float``, ``bool``.
        required: Whether the runner must refuse to run when not supplied.
        default: Default value used when not supplied. May be ``None``.
        desc: Human-readable description of the parameter.
    """

    name: str
    type: str
    required: bool
    default: object | None
    desc: str


@dataclass(frozen=True)
class Output:
    """A declared output file the artifact produces.

    Attributes:
        name: The filename the executor is expected to write under ``out/``.
        desc: Human-readable description of the output.
    """

    name: str
    desc: str


@dataclass(frozen=True)
class Spec:
    """A fully-parsed, validated ``ARTIFACT.md``.

    Attributes:
        path: Absolute path to the source ``ARTIFACT.md``.
        kind: Always ``"transform"`` in v0.2.
        executor: Always ``"deepagent"`` in v0.2.
        model: Model identifier. Under ``executor: deepagent`` this is a
            ``provider:name`` string (required). Under ``executor: claude_cli``
            it is a bare Claude model name (optional; when ``None`` the
            ``claude`` CLI uses its own default).
        inputs: Declared inputs in source order.
        params: Declared params in source order.
        outputs: Declared outputs in source order.
        body: The prose body after the YAML frontmatter.
        artifact_sha256: SHA-256 of the UTF-8-encoded ``ARTIFACT.md`` content,
            for provenance. Byte-identical to the file's raw bytes for any
            well-formed UTF-8 source file.
    """

    path: Path
    kind: str
    executor: str
    model: str | None
    inputs: list[Input]
    params: list[Param]
    outputs: list[Output]
    body: str
    artifact_sha256: str


def parse_spec(path: str | Path) -> Spec:
    """Parse and validate an ``ARTIFACT.md`` file.

    Args:
        path: Path to the ``ARTIFACT.md`` file.

    Returns:
        A validated ``Spec``.

    Raises:
        SpecError: On frontmatter/validation failure.
        OSError: If the file cannot be read.
    """
    path = Path(path)
    raw = path.read_bytes()
    return parse_spec_from_str(raw.decode("utf-8"), path)


def parse_spec_from_str(content: str, path: Path) -> Spec:
    """Parse and validate ``ARTIFACT.md`` content already in memory.

    Args:
        content: Full ``ARTIFACT.md`` text (frontmatter + body).
        path: Source path used in error messages and stored on the
            returned ``Spec``. Pass a synthetic path (e.g. ``Path("<stdin>")``)
            when the content did not come from a file.

    Returns:
        A validated ``Spec`` whose ``artifact_sha256`` is the SHA-256 of
        the UTF-8-encoded ``content``.

    Raises:
        SpecError: On frontmatter/validation failure.
    """
    m = _FRONTMATTER_RE.match(content)
    if not m:
        raise SpecError(f"{path}: missing YAML frontmatter delimited by '---'")

    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError as e:
        raise SpecError(f"{path}: invalid YAML frontmatter: {e}") from e
    if not isinstance(fm, dict):
        raise SpecError(f"{path}: frontmatter must be a YAML mapping")

    body = m.group(2)

    kind = _require_str(fm, "kind", path)
    if kind not in ALLOWED_KINDS:
        raise SpecError(f"{path}: kind must be one of {sorted(ALLOWED_KINDS)}, got {kind!r}")

    executor = _require_str(fm, "executor", path)
    if executor not in ALLOWED_EXECUTORS:
        raise SpecError(
            f"{path}: executor must be one of {sorted(ALLOWED_EXECUTORS)}, got {executor!r}"
        )

    if executor == "claude_cli":
        raw_model = fm.get("model")
        if raw_model is None:
            model = None
        elif not isinstance(raw_model, str) or not raw_model:
            raise SpecError(f"{path}: 'model' must be a non-empty string if provided")
        elif ":" in raw_model:
            raise SpecError(
                f"{path}: executor 'claude_cli' requires a bare Claude model "
                f"name (no provider prefix); got {raw_model!r}"
            )
        else:
            model = raw_model
    else:
        model = _require_str(fm, "model", path)

    inputs = [_parse_input(i, path) for i in fm.get("inputs") or []]
    params = [_parse_param(p, path) for p in fm.get("params") or []]
    outputs = [_parse_output(o, path) for o in fm.get("outputs") or []]

    _require_unique_names([i.name for i in inputs], "input", path)
    _require_unique_names([p.name for p in params], "param", path)
    _require_unique_names([o.name for o in outputs], "output", path)

    try:
        content_bytes = content.encode("utf-8")
    except UnicodeEncodeError as e:
        raise SpecError(f"{path}: content contains non-UTF-8 bytes: {e}") from e
    sha = hashlib.sha256(content_bytes).hexdigest()

    return Spec(
        path=path,
        kind=kind,
        executor=executor,
        model=model,
        inputs=inputs,
        params=params,
        outputs=outputs,
        body=body,
        artifact_sha256=sha,
    )


def _require_str(fm: dict, key: str, path: Path) -> str:
    """Return ``fm[key]`` if it is a non-empty string; else raise ``SpecError``."""
    v = fm.get(key)
    if not isinstance(v, str) or not v:
        raise SpecError(f"{path}: required field {key!r} missing or not a non-empty string")
    return v


def _require_unique_names(names: list[str], kind: str, path: Path) -> None:
    """Reject duplicate ``name`` entries within an inputs/params/outputs list.

    ``kind`` is "input", "param", or "output" for the error message.
    """
    seen: set[str] = set()
    for n in names:
        if n in seen:
            raise SpecError(f"{path}: duplicate {kind} name: {n!r}")
        seen.add(n)


def _require_bare_filename(name: str, kind: str, path: Path) -> None:
    """Reject ``name`` if it contains a path separator or is ``.`` / ``..``.

    ``kind`` is "input" or "output" for the error message.
    """
    if "/" in name or name in (".", "..") or Path(name).name != name:
        raise SpecError(
            f"{path}: {kind} name must be a bare filename, got {name!r}"
        )


def _parse_input(raw: object, path: Path) -> Input:
    """Parse one entry from the frontmatter ``inputs`` list."""
    if not isinstance(raw, dict):
        raise SpecError(f"{path}: input entries must be mappings")
    name = _require_str(raw, "name", path)
    _require_bare_filename(name, "input", path)
    return Input(name=name, desc=raw.get("desc", ""))


def _parse_param(raw: object, path: Path) -> Param:
    """Parse one entry from the frontmatter ``params`` list."""
    if not isinstance(raw, dict):
        raise SpecError(f"{path}: param entries must be mappings")
    name = _require_str(raw, "name", path)
    ptype = raw.get("type", "string")
    if ptype not in ALLOWED_PARAM_TYPES:
        raise SpecError(
            f"{path}: param {name!r} has type {ptype!r}; must be one of {sorted(ALLOWED_PARAM_TYPES)}"
        )
    required = bool(raw.get("required", False))
    default = raw.get("default")
    return Param(name=name, type=ptype, required=required, default=default, desc=raw.get("desc", ""))


def _parse_output(raw: object, path: Path) -> Output:
    """Parse one entry from the frontmatter ``outputs`` list."""
    if not isinstance(raw, dict):
        raise SpecError(f"{path}: output entries must be mappings")
    name = _require_str(raw, "name", path)
    _require_bare_filename(name, "output", path)
    return Output(name=name, desc=raw.get("desc", ""))
