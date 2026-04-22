# `artifact template` + `artifact create` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship two parameter-free subcommands — `artifact template` (emits a reference `ARTIFACT.md` to stdout) and `artifact create <dir>` (reads `ARTIFACT.md` from stdin, validates, writes the two-file scaffold) — composable via `artifact template | artifact create <dir>`.

**Architecture:** Parser-first, bottom-up, in `src/artifact/`. `spec.py` gains a str-based entry point and bare-filename validation. A new `src/artifact/create.py` hosts two pure functions (`render_template`, `create`). `cli.py` gets two thin subparsers that call them. Each stage is a vertical slice that ships with tests and commits on its own.

**Tech Stack:** Python 3.11+ (stdlib `argparse`, `pathlib`, `sys`), `PyYAML`, `pytest`, `uv` for builds. No new runtime deps.

---

## Context for the implementing engineer

You are working inside the `feat/artifact-cli-v0.3` branch of the `artifact` repo. Before you start:

- Read `docs/create-dd.md` — the design doc this plan implements. Treat it as the source of truth when the plan is silent.
- Read `docs/artifact-dd.md` — the parent design doc for the `artifact` tool.
- Read `src/artifact/spec.py` end-to-end (~215 lines). It is the only file you will modify in core parsing. Its only job is "path in, `Spec` out, or raise `SpecError`." Keep it that way.
- Read `src/artifact/cli.py` — note the argparse layout and the "no business logic" rule in its docstring.
- Skim `tests/test_spec.py` and `tests/test_cli.py` — your new tests should follow their style (plain `pytest`, `tmp_path`, no mocks, no monkeypatching of module attributes).

**Project conventions (obey these):**

- `src/artifact/` is a uv-built package (`pyproject.toml` → `[tool.uv.build-backend]`). Don't add `__init__.py` content; imports are flat (`from artifact.spec import parse_spec`).
- Dataclasses are frozen. Use type hints everywhere. `from __future__ import annotations` at the top of every module.
- One-line module docstrings on public modules; Google-style docstrings on public functions (see existing `spec.py` / `template.py`).
- Errors are caller-readable: `raise SpecError(f"{path}: <what>: <got>")`. Never a bare `ValueError`.
- Tests live in `tests/` (mirror file names: `src/artifact/create.py` → `tests/test_create.py`). Integration tests (network/LLM) go in `tests/integration/` — there are none in this plan.
- `uv sync` before first run; `uv run pytest` to run the suite. Do not invoke bare `pytest`; the project relies on `uv`'s lockfile.

**Separation of concerns (Occam's razor):**

- `spec.py` does not know what stdin is. It takes a `str` + `Path` and returns a `Spec` or raises.
- `create.py` does not know what argv is. It takes a `Path` + keyword `content: str` and returns a `Path` or raises.
- `cli.py` does not build YAML, does not read files itself, does not format `SpecError` messages. It marshals stdin/argv into keyword args and prints the result.

Every test should exercise the smallest layer that owns the behavior. Don't reach through `cli.main` to test validation logic that belongs to `spec.py`.

**Commit cadence:** One commit per stage, at the end, after the full stage's tests are green. Do not batch stages into one commit; do not commit mid-stage. Message convention from `git log --oneline`: lowercase imperative, no type prefix required, scope-then-what (`parser: expose ALLOWED_* constants`). Match what's already in `git log`.

---

## File Structure

Files you will **create**:

- `src/artifact/create.py` — two public functions: `render_template() -> str` and `create(dest: Path, *, content: str) -> Path`. Pure stdlib, no I/O coupling beyond what each function needs.
- `tests/test_create.py` — all tests for both public functions + the template/parser round-trip tripwires.

Files you will **modify**:

- `src/artifact/spec.py` — rename three module-private constants to public; add `_require_bare_filename` helper; wire it into `_parse_input` and `_parse_output`; extract `parse_spec_from_str` from `parse_spec`. That's it. No other changes.
- `src/artifact/cli.py` — two new subparsers (`template`, `create`) with their dispatch branches. Thin.
- `tests/test_spec.py` — add cases for `parse_spec_from_str` and the bare-filename rule.
- `tests/test_cli.py` — add CLI-level tests for the `template` / `create` subcommands (TTY guard, empty-stdin guard, success, error surfaces).

Files you will **not touch**: `runner.py`, `promote.py`, `exec.py`, `template.py`, `introspect.py`, `claude_cli.py`, `errors.py`, `timestamp.py`, `__init__.py`, `pyproject.toml`. If you feel the urge to edit any of these, stop and re-read the DD.

---

## Stage 1: Parser refactor — expose constants and factor `parse_spec_from_str`

**Why this stage exists:** Stages 3 and 5 need (a) public allowed-value constants to interpolate into the template, and (b) a string-based parser entry point so `create` can validate piped content without a tempfile. Ship both as a pure refactor with zero behavior change, verified by the existing test suite.

**Files:**

- Modify: `src/artifact/spec.py` (constants + function split)
- Test: `tests/test_spec.py` (add two new tests; all existing tests must still pass)

- [ ] **Step 1.1: Write a failing test for the public constants**

Add to `tests/test_spec.py` (append at the bottom):

```python
def test_allowed_value_constants_are_public():
    from artifact.spec import ALLOWED_KINDS, ALLOWED_EXECUTORS, ALLOWED_PARAM_TYPES
    assert "transform" in ALLOWED_KINDS
    assert "deepagent" in ALLOWED_EXECUTORS
    assert "claude_cli" in ALLOWED_EXECUTORS
    assert {"string", "int", "float", "bool"} <= ALLOWED_PARAM_TYPES
```

- [ ] **Step 1.2: Run the test; verify it fails**

Run: `uv run pytest tests/test_spec.py::test_allowed_value_constants_are_public -v`
Expected: `FAIL — ImportError: cannot import name 'ALLOWED_KINDS'`.

- [ ] **Step 1.3: Write a failing test for `parse_spec_from_str`**

Add to `tests/test_spec.py`:

```python
def test_parse_spec_from_str_parses_inline_content():
    from pathlib import Path
    from artifact.spec import parse_spec_from_str

    content = (
        "---\n"
        "kind: transform\n"
        "executor: deepagent\n"
        "model: anthropic:claude-sonnet-4-6\n"
        "outputs:\n"
        "  - name: o.md\n"
        "    desc: d\n"
        "---\n"
        "body\n"
    )
    spec = parse_spec_from_str(content, Path("<inline>"))
    assert spec.kind == "transform"
    assert spec.executor == "deepagent"
    assert spec.model == "anthropic:claude-sonnet-4-6"
    assert spec.path == Path("<inline>")
    assert [o.name for o in spec.outputs] == ["o.md"]


def test_parse_spec_from_str_reports_path_in_error():
    from pathlib import Path
    from artifact.spec import SpecError, parse_spec_from_str

    with pytest.raises(SpecError, match="<synth>"):
        parse_spec_from_str("no frontmatter at all", Path("<synth>"))
```

- [ ] **Step 1.4: Run tests; verify both fail**

Run: `uv run pytest tests/test_spec.py -v -k "from_str or allowed_value_constants"`
Expected: 3 failures (all `ImportError` or `AttributeError`).

- [ ] **Step 1.5: Edit `src/artifact/spec.py` — rename constants to public names**

At the module top, change:

```python
_ALLOWED_KINDS = {"transform"}
_ALLOWED_EXECUTORS = {"deepagent", "claude_cli"}
_ALLOWED_PARAM_TYPES = {"string", "int", "float", "bool"}
```

to:

```python
ALLOWED_KINDS = {"transform"}
ALLOWED_EXECUTORS = {"deepagent", "claude_cli"}
ALLOWED_PARAM_TYPES = {"string", "int", "float", "bool"}
```

Then update the three in-module references (inside `parse_spec` and `_parse_param`) to the new names. Use `grep` to find them; there are exactly three sites. Do **not** keep `_ALLOWED_*` aliases — the DD explicitly says no in-tree consumer uses the private names.

- [ ] **Step 1.6: Edit `src/artifact/spec.py` — extract `parse_spec_from_str`**

Refactor `parse_spec` into two functions. The current body of `parse_spec` splits into:

1. `parse_spec` (thin): reads bytes, decodes, calls `parse_spec_from_str`.
2. `parse_spec_from_str` (does the work): regex match, YAML load, field validation, build `Spec`.

Target shape:

```python
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

    sha = hashlib.sha256(content.encode("utf-8")).hexdigest()

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
```

**Correctness note:** `parse_spec` previously hashed `raw` (file bytes). After this refactor `parse_spec_from_str` hashes the encoded UTF-8 content. For files these are byte-identical (you read bytes and decoded them); the SHA is stable. Do **not** pass the original `raw` around — keeping one hash site is the point.

- [ ] **Step 1.7: Run the full test suite; verify everything passes**

Run: `uv run pytest -v`
Expected: all existing tests PASS, plus the three new ones PASS. No `_ALLOWED_*` references remain (`uv run python -c "from artifact.spec import _ALLOWED_KINDS"` should fail with `ImportError`).

If any existing test in `test_spec.py` fails, you likely missed a rename site. Search `src/artifact/spec.py` for `_ALLOWED_`.

- [ ] **Step 1.8: Commit**

```bash
git add src/artifact/spec.py tests/test_spec.py
git commit -m "parser: expose ALLOWED_* and factor parse_spec_from_str"
```

---

## Stage 2: Parser — bare-filename validation on `inputs[].name` and `outputs[].name`

**Why this stage exists:** Closes the path-in-name foot-gun (`name: /abs/mission.md`, `name: ../x.md`) at parse time, pointing at the offending field. Applies to `inputs` and `outputs` only; `params[].name` is out of scope (see DD Open questions).

**Files:**

- Modify: `src/artifact/spec.py` (add helper + two call sites)
- Test: `tests/test_spec.py`

- [ ] **Step 2.1: Write failing tests covering every rejection case plus the pass-through case**

Add to `tests/test_spec.py`:

```python
import pytest


@pytest.mark.parametrize(
    "bad_name",
    ["../x.md", "/abs/x.md", "sub/x.md", ".", "..", "a/b/c"],
)
def test_input_name_must_be_bare_filename(tmp_path, bad_name):
    from artifact.spec import SpecError, parse_spec

    p = tmp_path / "ARTIFACT.md"
    p.write_text(
        "---\nkind: transform\nexecutor: deepagent\nmodel: x\n"
        f"inputs:\n  - name: {bad_name!r}\n    desc: d\n"
        "outputs:\n  - name: o.md\n    desc: d\n---\nbody"
    )
    with pytest.raises(SpecError, match="input name must be a bare filename"):
        parse_spec(p)


@pytest.mark.parametrize(
    "bad_name",
    ["../x.md", "/abs/x.md", "sub/x.md", ".", "..", "a/b/c"],
)
def test_output_name_must_be_bare_filename(tmp_path, bad_name):
    from artifact.spec import SpecError, parse_spec

    p = tmp_path / "ARTIFACT.md"
    p.write_text(
        "---\nkind: transform\nexecutor: deepagent\nmodel: x\n"
        f"outputs:\n  - name: {bad_name!r}\n    desc: d\n---\nbody"
    )
    with pytest.raises(SpecError, match="output name must be a bare filename"):
        parse_spec(p)


def test_param_name_with_slash_is_not_validated_by_filename_rule(tmp_path):
    # Params are identifiers, not filenames. The bare-filename rule must
    # not apply here. (A separate identifier rule is deferred.)
    from artifact.spec import parse_spec

    p = tmp_path / "ARTIFACT.md"
    p.write_text(
        "---\nkind: transform\nexecutor: deepagent\nmodel: x\n"
        "params:\n  - name: a/b\n    type: string\n    required: false\n    desc: d\n"
        "outputs:\n  - name: o.md\n    desc: d\n---\nbody"
    )
    spec = parse_spec(p)
    assert spec.params[0].name == "a/b"
```

Note: `{bad_name!r}` wraps the name in single quotes in the generated YAML, so `/abs/x.md` becomes `'/abs/x.md'` (valid YAML string). Without that, YAML treats `/abs/x.md` as a bare scalar — which also parses fine, but relying on `!r` keeps the test readable even for edge values like `".."`.

- [ ] **Step 2.2: Run the tests; verify they fail**

Run: `uv run pytest tests/test_spec.py -v -k "bare_filename or param_name_with_slash"`
Expected: 12 `test_input_*` + 12 `test_output_*` parametrized failures — all fail because there's no validation yet and the parser accepts the bad names. `test_param_name_with_slash_is_not_validated_by_filename_rule` should PASS already (no rule exists). That's fine; keep the test as a regression guard.

- [ ] **Step 2.3: Add `_require_bare_filename` and wire it into input/output parsers**

Add below `_require_str` in `src/artifact/spec.py`:

```python
def _require_bare_filename(name: str, kind: str, path: Path) -> None:
    """Reject ``name`` if it contains a path separator or is ``.`` / ``..``.

    ``kind`` is "input" or "output" for the error message.
    """
    if "/" in name or name in (".", "..") or Path(name).name != name:
        raise SpecError(
            f"{path}: {kind} name must be a bare filename, got {name!r}"
        )
```

Update `_parse_input`:

```python
def _parse_input(raw: object, path: Path) -> Input:
    """Parse one entry from the frontmatter ``inputs`` list."""
    if not isinstance(raw, dict):
        raise SpecError(f"{path}: input entries must be mappings")
    name = _require_str(raw, "name", path)
    _require_bare_filename(name, "input", path)
    return Input(name=name, desc=raw.get("desc", ""))
```

Update `_parse_output`:

```python
def _parse_output(raw: object, path: Path) -> Output:
    """Parse one entry from the frontmatter ``outputs`` list."""
    if not isinstance(raw, dict):
        raise SpecError(f"{path}: output entries must be mappings")
    name = _require_str(raw, "name", path)
    _require_bare_filename(name, "output", path)
    return Output(name=name, desc=raw.get("desc", ""))
```

Leave `_parse_param` alone.

- [ ] **Step 2.4: Run the tests; verify they pass**

Run: `uv run pytest tests/test_spec.py -v`
Expected: full file green, including the 24 new parametrized cases and all prior tests.

- [ ] **Step 2.5: Commit**

```bash
git add src/artifact/spec.py tests/test_spec.py
git commit -m "parser: reject non-bare filenames in inputs and outputs"
```

---

## Stage 3: `render_template()` — the reference `ARTIFACT.md` as a string

**Why this stage exists:** The rest of the feature rides on the template being (a) valid by construction and (b) kept in sync with `ALLOWED_*`. Land it as a pure function returning a string, with round-trip tripwires.

**Files:**

- Create: `src/artifact/create.py` (this stage adds only `render_template`; `create()` comes in Stage 5)
- Create: `tests/test_create.py` (first file in this module's suite)

- [ ] **Step 3.1: Write the failing tests for `render_template`**

Create `tests/test_create.py`:

```python
"""Tests for render_template and create (src/artifact/create.py)."""

from __future__ import annotations

from pathlib import Path

import pytest

from artifact.create import render_template
from artifact.spec import (
    ALLOWED_EXECUTORS,
    ALLOWED_KINDS,
    ALLOWED_PARAM_TYPES,
    parse_spec_from_str,
)


def test_render_template_is_valid_spec():
    text = render_template()
    spec = parse_spec_from_str(text, Path("<template>"))
    assert spec.kind in ALLOWED_KINDS
    assert spec.executor in ALLOWED_EXECUTORS
    assert len(spec.inputs) >= 1
    assert len(spec.params) >= 1
    assert len(spec.outputs) >= 1


def test_render_template_is_deterministic():
    assert render_template() == render_template()


def test_render_template_returns_str_with_frontmatter_and_body():
    text = render_template()
    assert text.startswith("---\n")
    # Closing frontmatter delimiter is followed by a blank line then the body.
    assert "\n---\n" in text
    # Body is non-trivial.
    assert len(text.split("\n---\n", 2)[2].strip()) > 0


def test_render_template_lists_every_allowed_value_in_comments():
    """Drift tripwire: if the parser grows a new allowed value, the template
    must surface it somewhere in the rendered text (typically the `# one of:`
    comment next to the relevant field).
    """
    text = render_template()
    missing = [
        v
        for v in (ALLOWED_KINDS | ALLOWED_EXECUTORS | ALLOWED_PARAM_TYPES)
        if v not in text
    ]
    assert missing == [], f"template missing allowed values: {missing}"


@pytest.mark.parametrize(
    "needle",
    [
        "requirements.md",    # declared input name
        "max_budget_usd",     # a required param
        "picks.md",           # a declared output
        "candidates.json",    # another declared output
        "wildcards.md",       # third declared output
    ],
)
def test_render_template_contains_reference_names(needle):
    assert needle in render_template()
```

- [ ] **Step 3.2: Run; verify they fail**

Run: `uv run pytest tests/test_create.py -v`
Expected: `ImportError` — `src/artifact/create.py` does not exist yet.

- [ ] **Step 3.3: Create `src/artifact/create.py` with `render_template`**

```python
"""Emit a reference ``ARTIFACT.md`` and scaffold a new artifact directory.

This module has two public functions. They are deliberately I/O-minimal
and have no CLI coupling — ``cli.py`` is responsible for stdin/argv.

- ``render_template`` returns the reference artifact as a string. YAML
  comments listing allowed values are interpolated from the authoritative
  ``spec.ALLOWED_*`` constants so the template cannot drift from the parser.
- ``create`` (added in a later stage) takes a destination path and content
  string, validates the content via the parser, and writes
  ``<dest>/ARTIFACT.md`` plus ``<dest>/.gitignore``.
"""

from __future__ import annotations

from artifact.spec import ALLOWED_EXECUTORS, ALLOWED_KINDS, ALLOWED_PARAM_TYPES


def _render_allowed(values: set[str]) -> str:
    """Render an ``ALLOWED_*`` set as ``a | b | c`` (sorted, stable)."""
    return " | ".join(sorted(values))


def render_template() -> str:
    """Return the reference ``ARTIFACT.md`` (frontmatter + body) as a string.

    The comment strings next to ``kind``, ``executor``, and each param's
    ``type`` are interpolated from ``spec.ALLOWED_*`` so they cannot
    silently drift when the parser grows a new accepted value.

    Returns:
        The full artifact text, terminated by a newline.
    """
    kinds = _render_allowed(ALLOWED_KINDS)
    executors = _render_allowed(ALLOWED_EXECUTORS)
    param_types = _render_allowed(ALLOWED_PARAM_TYPES)

    return f"""\
---
# ARTIFACT.md — recipe + provenance container.
# Convention: prefix the parent directory with a DIKW digit
# (0- raw, 1- info, 2- knowledge, 3- wisdom). Not enforced.
# Full reference: docs/artifact-dd.md

kind: transform                        # one of: {kinds}
executor: deepagent                    # one of: {executors}
model: anthropic:claude-sonnet-4-6     # provider:name under executor: deepagent; bare Claude model under executor: claude_cli (optional there)

inputs:
  - name: requirements.md
    desc: |
      Free-form brief describing what you want in a car and why.
      Who drives it, climate, commute, what you'll carry, deal-breakers,
      nice-to-haves, any brand lean or scar tissue ("my last Jetta ate
      two transmissions"). A paragraph is plenty.
      `name:` must be a bare filename.

params:
  - name: max_budget_usd
    type: float                        # one of: {param_types}
    required: true
    desc: Upper bound on what you'll spend out the door (not monthly payment).
  - name: stretch_budget_usd
    type: float
    required: false
    default: null
    desc: |
      Used only for wildcards. If set, the agent may propose picks priced
      up to this amount and explain what the extra money unlocks. Unset =
      no stretch wildcards.
  - name: shortlist_size
    type: int
    required: false
    default: 5
    desc: How many model recommendations to include in the core shortlist.
  - name: wildcard_count
    type: int
    required: false
    default: 3
    desc: |
      How many "outside your requirements" picks to include. Zero disables
      the wildcards section.
  - name: reliability_weight
    type: float
    required: false
    default: 0.7
    desc: |
      0.0 = weight features/fun/looks equally with reliability.
      1.0 = rank reliability above all else.
      Used to shape picks, not to hard-filter.
  - name: include_used
    type: bool
    required: false
    default: true
    desc: |
      true = consider model years going back ~8 years when they fit budget.
      false = limit to new or near-new (within 2 model years).

outputs:
  - name: picks.md
    desc: |
      Prose memo. One H2 per recommended {{year-range, make, model, trim}}
      with: why it fits the requirements, 3-5 things owners consistently
      say (good and bad) with source URLs, expected price band, and
      common issues to watch for at this age/mileage.
  - name: candidates.json
    desc: |
      Structured list of picks:
      [{{
        "rank": <int>,
        "make": <string>,
        "model": <string>,
        "year_range": <string e.g. "2020-2022">,
        "trim_hints": [<string>...],
        "price_usd_range": [<int>, <int>],
        "fit_score": <float 0..1>,
        "why_fits": <string — one sentence>,
        "what_owners_say": [{{"claim": <string>, "source": <url>}}, ...],
        "common_issues": [<string>...],
        "sources": [<url>...]
      }}, ...]
  - name: wildcards.md
    desc: |
      Picks deliberately outside the stated requirements, with a paragraph
      each explaining why the caller should reconsider. Three flavors, one
      of each when applicable: stretch-budget, segment-adjacent,
      older-premium-for-same-dollars.
---

# Body style: refer to agent capabilities as verbs ("search the web",
# "fetch the page"), not specific tool identifiers. Keeps the recipe
# portable across executors; the agent picks the right tool at run time.

You are recommending which cars the author of {{{{ inputs.requirements.md }}}}
should SHORTLIST — the research that happens before they touch a listing
site. You are not finding them a specific vehicle to buy. You are naming
the models, year ranges, and trims worth considering, and explaining why.

Your evidence must come from people who actually own these cars, not from
manufacturer marketing or SEO-bait "top 10" listicles. Prefer:

- Owner communities and model-specific forums for lived experience.
- Independent reliability and recall data (government recall databases,
  consumer-reported complaint aggregators).
- Real-world transaction price ranges, not MSRP or live listings.

Search the web for owner discussions, reliability reports, and recall
histories for each candidate. Fetch specific pages when you need the
exact claim or number to quote. For every factual claim in your outputs,
include an inline URL you actually visited. For every pick, cite at
least two independent owner-community sources. If you can't meet that
bar, say so in the memo rather than padding with weaker sources.

Produce three files:

**`out/picks.md`** — the core memo. {{{{ params.shortlist_size }}}} H2
sections, one per recommended model. Each section opens with a specific
pick (year range + make + model + trim guidance), explains in one
paragraph why it fits the caller's requirements, lists 3-5 bullets of
what owners consistently report (good and bad) with inline source URLs,
names the expected price band, and calls out 1-2 things to watch for
when inspecting a specific listing at that age/mileage.

**`out/candidates.json`** — the same picks in the structured schema
described in the output declaration above. Every `source` must be a real
URL you used.

**`out/wildcards.md`** — {{{{ params.wildcard_count }}}} picks OUTSIDE the
stated requirements. Aim for one of each flavor when applicable:
stretch-budget (only if {{{{ params.stretch_budget_usd }}}} is set — what
does the extra money unlock), segment-adjacent (wagon instead of SUV,
say), and older-premium-for-same-dollars (older model year of a
higher-class vehicle; call out ownership-cost trade-offs honestly).

Weighting: {{{{ params.reliability_weight }}}} near 1.0 ranks reliability
above features; near 0.5 is balanced; below 0.3 means the caller is
buying for joy. {{{{ params.include_used }}}} = false limits picks to new
or within two model years; true widens the net back ~8 years when the
price fits.

Be specific. "Toyota RAV4" is not a pick; "2020-2022 RAV4 XLE or above
(skip LE — cloth seats, no blind-spot monitor)" is a pick.
"""
```

**F-string escaping note:** Python f-strings require `{` and `}` in the literal output to be doubled. Every `{{ inputs.X }}` / `{{ params.X }}` placeholder in the rendered body must be written as `{{{{ inputs.X }}}}` / `{{{{ params.X }}}}` in the f-string source. The JSON example braces (`[{...}, ...]`) and the f-string-internal `year-range, make, model, trim` brace pair are doubled too. Re-check escapes before running tests — if a test asserts `{{ inputs.requirements.md }}` appears in output and it doesn't, you've likely under-escaped.

- [ ] **Step 3.4: Run the tests; verify they pass**

Run: `uv run pytest tests/test_create.py -v`
Expected: all 9 tests PASS (`test_render_template_is_valid_spec`, `test_render_template_is_deterministic`, `test_render_template_returns_str_with_frontmatter_and_body`, `test_render_template_lists_every_allowed_value_in_comments`, 5 × `test_render_template_contains_reference_names`).

If `test_render_template_is_valid_spec` fails with a YAML error, your f-string escaping is wrong — print `render_template()` and diff the frontmatter against `docs/create-dd.md`. If the "allowed values" tripwire fails, check that `_render_allowed` outputs the raw values (no quotes, no brackets).

- [ ] **Step 3.5: Commit**

```bash
git add src/artifact/create.py tests/test_create.py
git commit -m "create: add render_template() with parser-synced allowed-value comments"
```

---

## Stage 4: `artifact template` CLI subcommand

**Why this stage exists:** First user-visible vertical slice. After this stage, running `artifact template` prints the reference to stdout; `artifact template | wc -l` works; the command is idempotent and does not touch disk.

**Files:**

- Modify: `src/artifact/cli.py` (add subparser + dispatch branch)
- Modify: `tests/test_cli.py` (add CLI-level tests)

- [ ] **Step 4.1: Write failing CLI tests for `template`**

Append to `tests/test_cli.py`:

```python
def test_template_subcommand_prints_reference_to_stdout(capsys):
    from artifact.cli import main

    rc = main(["template"])
    assert rc == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    # Frontmatter delimiters present; body is non-empty.
    assert captured.out.startswith("---\n")
    assert "\nkind: transform" in captured.out
    assert "requirements.md" in captured.out


def test_template_subcommand_is_idempotent(capsys):
    from artifact.cli import main

    rc1 = main(["template"])
    first = capsys.readouterr().out
    rc2 = main(["template"])
    second = capsys.readouterr().out
    assert rc1 == 0 and rc2 == 0
    assert first == second


def test_template_subcommand_rejects_flags(capsys):
    from artifact.cli import main

    # argparse exits with SystemExit(2) for unknown flags.
    with pytest.raises(SystemExit) as excinfo:
        main(["template", "--model", "x"])
    assert excinfo.value.code == 2
```

If `pytest` is not already imported at the top of `tests/test_cli.py`, add `import pytest`.

- [ ] **Step 4.2: Run; verify they fail**

Run: `uv run pytest tests/test_cli.py -v -k template`
Expected: argparse rejects the unknown `template` subcommand; all 3 fail (`SystemExit(2)` from argparse, message "invalid choice: 'template'").

- [ ] **Step 4.3: Wire `template` into `src/artifact/cli.py`**

In `build_parser`, after the existing `show_cmd` block, add:

```python
    sub.add_parser(
        "template",
        help="Emit a reference ARTIFACT.md to stdout.",
    )
```

No arguments, no flags. The DD is explicit: no flags on these subcommands.

In `main`, add a new dispatch branch after the existing `if args.cmd == "show":` block and before `return 2`:

```python
    if args.cmd == "template":
        from artifact.create import render_template

        sys.stdout.write(render_template())
        return 0
```

Using `sys.stdout.write` (not `print`) avoids an extra trailing newline — `render_template` already ends in `\n`.

- [ ] **Step 4.4: Run; verify all three new tests pass, and nothing else broke**

Run: `uv run pytest -v`
Expected: full suite green, including 3 new `template` tests.

- [ ] **Step 4.5: Smoke-test from a real shell**

Run (manual, not pytest):

```bash
uv run artifact template | head -5
```

Expected first five lines:

```
---
# ARTIFACT.md — recipe + provenance container.
# Convention: prefix the parent directory with a DIKW digit
# (0- raw, 1- info, 2- knowledge, 3- wisdom). Not enforced.
# Full reference: docs/artifact-dd.md
```

This is an eyes-on check; no test harness asserts it. If the first line isn't `---` something is wrong.

- [ ] **Step 4.6: Commit**

```bash
git add src/artifact/cli.py tests/test_cli.py
git commit -m "cli: add `artifact template` subcommand"
```

---

## Stage 5: `create()` — stdin-content → dir adapter (pure function)

**Why this stage exists:** The `create` command's business logic, isolated from argv/stdin. It takes a destination `Path` and keyword `content: str`, validates the content via `parse_spec_from_str`, writes two files, returns the destination. All error surfaces live here; `cli.py` just reports them.

**Files:**

- Modify: `src/artifact/create.py` (add `create` function)
- Modify: `tests/test_create.py` (add tests for `create`)

- [ ] **Step 5.1: Write failing tests for `create` — the happy path and every error branch**

Append to `tests/test_create.py`:

```python
def test_create_writes_artifact_and_gitignore(tmp_path):
    from artifact.create import create, render_template

    content = render_template()
    dest = tmp_path / "1-shortlist"
    returned = create(dest, content=content)

    assert returned == dest
    assert (dest / "ARTIFACT.md").read_text(encoding="utf-8") == content
    assert (dest / ".gitignore").read_text(encoding="utf-8") == "runs/*\n"


def test_create_appends_trailing_newline_when_missing(tmp_path):
    from artifact.create import create, render_template

    content = render_template().rstrip("\n")
    dest = tmp_path / "2-shortlist"
    create(dest, content=content)

    written = (dest / "ARTIFACT.md").read_text(encoding="utf-8")
    assert written.endswith("\n")
    assert written == content + "\n"


def test_create_creates_parent_dir_when_absent(tmp_path):
    from artifact.create import create, render_template

    dest = tmp_path / "nested" / "3-shortlist"
    assert not dest.exists()
    create(dest, content=render_template())
    assert (dest / "ARTIFACT.md").is_file()


def test_create_rejects_invalid_content(tmp_path):
    from artifact.create import create
    from artifact.spec import SpecError

    bad = "no frontmatter at all"
    dest = tmp_path / "x"
    with pytest.raises(SpecError):
        create(dest, content=bad)
    # Critical property: no files written when validation fails.
    assert not dest.exists() or list(dest.iterdir()) == []


def test_create_rejects_non_empty_dir(tmp_path):
    from artifact.create import create, render_template

    dest = tmp_path / "occupied"
    dest.mkdir()
    (dest / "already-here").write_text("hello")

    with pytest.raises(FileExistsError, match="is not empty"):
        create(dest, content=render_template())
    # Existing file untouched.
    assert (dest / "already-here").read_text(encoding="utf-8") == "hello"
    assert not (dest / "ARTIFACT.md").exists()


def test_create_accepts_empty_existing_dir(tmp_path):
    from artifact.create import create, render_template

    dest = tmp_path / "empty"
    dest.mkdir()
    create(dest, content=render_template())
    assert (dest / "ARTIFACT.md").is_file()


def test_create_rejects_bare_filename_violation(tmp_path):
    # A piped ARTIFACT.md that uses a path-like input name must fail
    # validation — same rule as parse_spec, reached via create().
    from artifact.create import create
    from artifact.spec import SpecError

    bad = (
        "---\nkind: transform\nexecutor: deepagent\nmodel: x\n"
        "inputs:\n  - name: '../mission.md'\n    desc: d\n"
        "outputs:\n  - name: o.md\n    desc: d\n---\nbody\n"
    )
    dest = tmp_path / "x"
    with pytest.raises(SpecError, match="bare filename"):
        create(dest, content=bad)
    assert not dest.exists() or list(dest.iterdir()) == []
```

- [ ] **Step 5.2: Run; verify they fail**

Run: `uv run pytest tests/test_create.py -v -k create`
Expected: all 7 new tests fail with `ImportError: cannot import name 'create'`.

- [ ] **Step 5.3: Implement `create` in `src/artifact/create.py`**

Append to `src/artifact/create.py` (after `render_template`), and add the required stdlib imports at the top of the file:

```python
from pathlib import Path

from artifact.spec import parse_spec_from_str
```

Then the function:

```python
def create(dest: Path, *, content: str) -> Path:
    """Validate ``content`` and scaffold an artifact directory at ``dest``.

    Writes exactly two files: ``<dest>/ARTIFACT.md`` (the piped content,
    with a trailing newline appended if missing) and ``<dest>/.gitignore``
    containing ``runs/*\\n``.

    Args:
        dest: Destination directory. Created with parents if it does not
            exist. Must be empty if it does exist.
        content: Full ``ARTIFACT.md`` text. Must parse cleanly via
            ``parse_spec_from_str`` — if not, raises before any file is
            written.

    Returns:
        ``dest`` (resolved to an absolute path on return).

    Raises:
        SpecError: If ``content`` fails parser validation. No files written.
        FileExistsError: If ``dest`` exists and is not empty. No files written.
        OSError: If the directory cannot be created (permissions, etc.).
            No files written.
    """
    parse_spec_from_str(content, dest / "ARTIFACT.md")

    if dest.exists():
        if any(dest.iterdir()):
            raise FileExistsError(f"{dest} is not empty")
    else:
        dest.mkdir(parents=True)

    artifact_text = content if content.endswith("\n") else content + "\n"
    (dest / "ARTIFACT.md").write_text(artifact_text, encoding="utf-8")
    (dest / ".gitignore").write_text("runs/*\n", encoding="utf-8")
    return dest
```

**Ordering matters:** validate first, *then* create the directory, *then* write. If validation fails, the target directory is never created — the "no partial state on invalid input" invariant from the DD's Errors table. The non-empty check runs before any write too; the "already-here" file in the test proves we don't clobber.

**Why `FileExistsError` (not `SpecError`):** `SpecError` is for artifact-content validation. "Target dir is not empty" is a filesystem-state error, not a content error. `cli.py` (next stage) catches both `SpecError` and `OSError` (which `FileExistsError` subclasses) and prints each verbatim.

**Return-value note:** Return `dest` as passed, not `dest.resolve()`. On macOS, `tmp_path` involves a `/var` → `/private/var` symlink that would make `returned == dest` fail in tests. Any path canonicalization (if needed) belongs in `cli.py`, which prints the returned value directly.

- [ ] **Step 5.4: Run; verify all tests pass**

Run: `uv run pytest tests/test_create.py -v`
Expected: 16 PASS (9 from Stage 3 + 7 from this stage).

- [ ] **Step 5.5: Commit**

```bash
git add src/artifact/create.py tests/test_create.py
git commit -m "create: add create(dest, *, content) pure-function scaffolder"
```

---

## Stage 6: `artifact create <dir>` CLI + end-to-end pipeline

**Why this stage exists:** Final vertical slice. Wires the `create` function to stdin + argv, adds the two guards that cannot be expressed below the CLI (TTY detection, empty-stdin detection), and locks in the `artifact template | artifact create <dir>` round-trip with an end-to-end test.

**Files:**

- Modify: `src/artifact/cli.py` (subparser + dispatch branch + TTY/empty guards)
- Modify: `tests/test_cli.py` (CLI-level tests for `create`, including E2E)

- [ ] **Step 6.1: Write failing CLI tests for `create` — guards, errors, happy path, E2E**

Append to `tests/test_cli.py`:

```python
import io


class _FakeStdin:
    """Minimal stdin double: fixed content + controllable isatty()."""

    def __init__(self, content: str, *, isatty: bool) -> None:
        self._content = content
        self._isatty = isatty

    def isatty(self) -> bool:
        return self._isatty

    def read(self) -> str:
        if self._isatty:
            raise AssertionError("read() should not be called when isatty()")
        return self._content


def test_create_cli_rejects_tty_stdin(tmp_path, capsys):
    from artifact.cli import main

    rc = main(["create", str(tmp_path / "x")], stdin=_FakeStdin("", isatty=True))
    assert rc == 1
    err = capsys.readouterr().err
    assert err.startswith("error: create reads ARTIFACT.md from stdin;")
    assert "artifact template | artifact create" in err
    assert not (tmp_path / "x").exists()


def test_create_cli_rejects_empty_stdin(tmp_path, capsys):
    from artifact.cli import main

    rc = main(["create", str(tmp_path / "x")], stdin=_FakeStdin("", isatty=False))
    assert rc == 1
    assert "error: stdin is empty" in capsys.readouterr().err
    assert not (tmp_path / "x").exists()


def test_create_cli_writes_files_on_valid_stdin(tmp_path, capsys):
    from artifact.cli import main
    from artifact.create import render_template

    content = render_template()
    dest = tmp_path / "1-shortlist"
    rc = main(["create", str(dest)], stdin=_FakeStdin(content, isatty=False))
    assert rc == 0
    out = capsys.readouterr().out.strip()
    # stdout is the resolved destination path.
    assert out == str(dest)
    assert (dest / "ARTIFACT.md").read_text(encoding="utf-8") == content
    assert (dest / ".gitignore").read_text(encoding="utf-8") == "runs/*\n"


def test_create_cli_surfaces_spec_errors(tmp_path, capsys):
    from artifact.cli import main

    rc = main(
        ["create", str(tmp_path / "bad")],
        stdin=_FakeStdin("not an artifact", isatty=False),
    )
    assert rc == 1
    err = capsys.readouterr().err
    assert err.startswith("error: ")
    assert "Traceback" not in err
    assert not (tmp_path / "bad").exists()


def test_create_cli_refuses_non_empty_dir(tmp_path, capsys):
    from artifact.cli import main
    from artifact.create import render_template

    dest = tmp_path / "occupied"
    dest.mkdir()
    (dest / "already").write_text("x")

    rc = main(
        ["create", str(dest)],
        stdin=_FakeStdin(render_template(), isatty=False),
    )
    assert rc == 1
    err = capsys.readouterr().err
    assert "is not empty" in err
    assert (dest / "already").read_text(encoding="utf-8") == "x"
    assert not (dest / "ARTIFACT.md").exists()


def test_template_create_pipeline_end_to_end(tmp_path, capsys):
    """The headline one-liner: template output piped into create writes a
    dir whose ARTIFACT.md parses cleanly via parse_spec."""
    from artifact.cli import main
    from artifact.spec import parse_spec

    # Phase 1: run `template`, capture stdout.
    rc = main(["template"])
    assert rc == 0
    template_out = capsys.readouterr().out

    # Phase 2: feed it into `create` via the injected stdin.
    dest = tmp_path / "1-end-to-end"
    rc = main(["create", str(dest)], stdin=_FakeStdin(template_out, isatty=False))
    assert rc == 0

    spec = parse_spec(dest / "ARTIFACT.md")
    assert spec.kind == "transform"
    assert spec.inputs and spec.params and spec.outputs
```

**Testing-seam note:** `main` takes an injected `stdin` parameter defaulting to `sys.stdin` (wired in Step 6.3). Tests pass a small `_FakeStdin` fake instead of monkeypatching `sys.stdin` — matches the existing `executor=` injection seam and follows the project's "prefer fakes over monkeypatching module attributes" convention. `io.StringIO` was rejected because its `isatty()` always returns `False` (so you can't test the TTY branch with a StringIO alone). A tiny fake with a controllable flag is cleaner than wrapping one.

- [ ] **Step 6.2: Run; verify the new tests fail**

Run: `uv run pytest tests/test_cli.py -v -k "create or pipeline"`
Expected: all 6 fail — argparse rejects `create` (not yet a subcommand), some with `SystemExit(2)`.

- [ ] **Step 6.3: Wire `create` into `src/artifact/cli.py`**

First, widen `main`'s signature to accept an injected stdin. Change the existing signature:

```python
def main(argv: list[str] | None = None, *, executor: Executor | None = None) -> int:
```

to:

```python
def main(
    argv: list[str] | None = None,
    *,
    executor: Executor | None = None,
    stdin: "typing.TextIO | None" = None,
) -> int:
```

Add `import typing` at the top of the file (or use `from typing import TextIO` and drop the string quote). Then inside `main`, resolve the stdin source once:

```python
    stdin = stdin if stdin is not None else sys.stdin
```

Update the docstring's Args section to include the new parameter:

```
        stdin: Optional stdin source for ``create``. ``None`` means
            ``sys.stdin``. Public injection seam for tests.
```

In `build_parser`, after the new `template` subparser (from Stage 4), add:

```python
    create_cmd = sub.add_parser(
        "create",
        help="Read ARTIFACT.md from stdin and scaffold <dir>.",
    )
    create_cmd.add_argument(
        "dir",
        help="Destination directory. Will be created if absent; must be empty if present.",
    )
```

In `main`, after the `if args.cmd == "template":` branch, add:

```python
    if args.cmd == "create":
        from pathlib import Path

        from artifact.create import create as create_artifact
        from artifact.spec import SpecError

        if stdin.isatty():
            print(
                "error: create reads ARTIFACT.md from stdin; "
                "try: artifact template | artifact create <dir>",
                file=sys.stderr,
            )
            return 1
        content = stdin.read()
        if not content:
            print("error: stdin is empty", file=sys.stderr)
            return 1

        try:
            out = create_artifact(Path(args.dir), content=content)
        except (SpecError, OSError) as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        print(out)
        return 0
```

**Why catch `OSError` (not just `FileExistsError`):** `FileExistsError` is a subclass of `OSError`. Catching the parent also handles permission errors (`PermissionError`) and other path-creation failures the DD's Errors table lists. Same surface as the existing `run` branch — keep the CLI's error shape uniform.

- [ ] **Step 6.4: Run the full suite; verify everything passes**

Run: `uv run pytest -v`
Expected: every test passes, including the 6 new CLI tests. No regressions in `test_spec.py`, `test_runner.py`, `test_promote.py`, etc.

- [ ] **Step 6.5: Real-shell smoke test of the full pipeline**

Run (manual):

```bash
TMP=$(mktemp -d) && uv run artifact template | uv run artifact create "$TMP/1-shortlist" && ls "$TMP/1-shortlist"
```

Expected output ends with two filenames:

```
/.../tmpXXXX/1-shortlist
ARTIFACT.md
.gitignore
```

Follow-up check:

```bash
uv run artifact show "$TMP/1-shortlist"
```

Expected: prints the parsed frontmatter without error (proves `show` can re-parse what `create` wrote).

Cleanup: `rm -rf "$TMP"`.

- [ ] **Step 6.6: Commit**

```bash
git add src/artifact/cli.py tests/test_cli.py
git commit -m "cli: add `artifact create <dir>` with stdin guards and E2E"
```

---

## Post-implementation checklist

Before handing off or opening a PR:

- [ ] `uv run pytest -v` is fully green and no tests are skipped (unless they were already marked `integration`).
- [ ] `git log --oneline origin/feat/artifact-cli-v0.3..HEAD` shows six commits, one per stage, in the order above.
- [ ] `git diff origin/feat/artifact-cli-v0.3..HEAD -- src/` has changes only in `spec.py`, `cli.py`, and the new `create.py`. Anything else is a bug.
- [ ] `uv run artifact template | uv run artifact create /tmp/smoke-$(date +%s)` round-trips without error.
- [ ] `uv run artifact --help` lists `template` and `create` in its subcommand list. (argparse does this automatically; confirm visually.)
- [ ] `uv run python -c "from artifact.spec import _ALLOWED_KINDS"` raises `ImportError` (proves no stale private alias slipped back in).
- [ ] No `.venv`, `__pycache__/`, `*.pyc`, or editor temp files are staged.

## Non-goals (do not implement)

From the DD — mentioned here so no one wastes a half-hour building them:

- No `--model`, `--example`, `--body-file`, or `--force` flags on either subcommand.
- No `--force` on `create`; non-empty dirs always error.
- No identifier validation on `params[].name` (deferred; the filename rule is the one that stung).
- No ancestor-`.gitignore` detection; `create` always writes `runs/*` locally.
- No `scripts/`, `runs/`, or `outs/` directory creation — those belong to the runner/promote flows.
- No editing of `runner.py`, `promote.py`, `exec.py`, `template.py`, `introspect.py`, `claude_cli.py`.
- No `pyproject.toml` changes (no new deps).

If mid-implementation you think you need one of the above, stop and reread the relevant DD section before deviating.
