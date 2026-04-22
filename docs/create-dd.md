# DD: `artifact template` + `artifact create`

*Addendum to `artifact-dd.md` — adds two parameter-free subcommands that compose via a Unix pipe.*

## Problem

Two failure modes today:

1. **Hand-written `ARTIFACT.md` files ship malformed.** YAML is unforgiving (a missing `desc:`, a stray tab, an unquoted `:` in a value), and the parser rejects them at `run` time, *after* the user has already shaped the rest of the directory in their head. The recipe should be valid by construction — or at minimum, invalid ones should be rejected before a directory is written, not hours later when the first run fires.
2. **Agents have no clean way to scaffold one.** A Claude Code session that wants to spin up a new artifact has to either remember the full frontmatter shape and emit it via `Write` (error-prone, drifts from the parser) or be taught a multi-step ritual. A single pipeable CLI is the right surface.

Secondary failure mode, specific to the `inputs`/`outputs` declarations:

3. **`name:` is easy to misuse as a path.** The declared name is a bare filename (used as `runs/<id>/in/<name>`), but nothing in the parser today enforces that. A user or agent can write `name: /abs/path/mission.md` or `name: ../mission.md` and the parser accepts it; the error surfaces downstream in ways that don't point to the mistake. This is exactly the "caller passed a path thinking they were providing the file path" confusion we want to head off.

The original DD said "a user can create an artifact with `mkdir` and an editor." That's still true. These commands add a parser-correct path for the people and agents that want one, and they harden `parse_spec` against the path-in-name foot-gun that affects both.

## Change

Two new subcommands. **Neither takes any flags.** The only argument anywhere is `create`'s positional `<dir>`.

```
artifact template                      # emit a reference ARTIFACT.md to stdout
artifact create <dir>                  # read ARTIFACT.md from stdin, validate, write
```

Intended usage:

```bash
# One-liner: default reference into a new dir.
artifact template | artifact create 1-my-thing

# Edit-then-create: customize before writing.
artifact template > /tmp/ARTIFACT.md
$EDITOR /tmp/ARTIFACT.md
artifact create 1-my-thing < /tmp/ARTIFACT.md

# Agent path: skip template entirely, just pipe the content.
cat <<'EOF' | artifact create 1-my-thing
---
kind: transform
executor: deepagent
model: anthropic:claude-sonnet-4-6
---
body here
EOF
```

Design consequences of the no-flags rule:

- **No `--model`.** Model is one line of YAML; change it by editing the piped content (or via `sed`/`yq` in the pipeline).
- **No `--example`.** Until a second shipped example exists, `template`'s output *is* the example.
- **No `--body-file`.** Body is part of stdin content; no precedence table.
- **No `--force`.** `create` refuses to overwrite (see Errors).

Each command does exactly one thing. `template` reads nothing and touches no filesystem; `create` has one input source (stdin) and one output shape (a dir with two files).

## What `template` emits

The full reference artifact — frontmatter + body — as a single UTF-8 stream to stdout. Exit 0, no stderr, no side effects.

Content is a **competitor brief** — the DD's §Example 4 extended with an optional `focus` param and a `seed.md` input, chosen to exercise every declaration shape in one compact artifact (a declared input, one required + one optional param, two outputs in different formats). The `kind`, `executor`, and param `type` comment strings are interpolated at render time from the parser's authoritative constants (see Parser sync) so they can't drift.

```yaml
---
# ARTIFACT.md — recipe + provenance container.
# Convention: prefix the parent directory with a DIKW digit
# (0- raw, 1- info, 2- knowledge, 3- wisdom). Not enforced.
# Full reference: docs/artifact-dd.md

kind: transform                        # one of: transform
executor: deepagent                    # one of: claude_cli | deepagent
model: anthropic:claude-sonnet-4-6     # provider:name under executor: deepagent; bare Claude model under executor: claude_cli (optional there)

inputs:
  - name: seed.md
    desc: |
      Seed material — the target's own About/Pricing page text, a press
      release, or any short document that anchors the brief in primary
      source. Plain markdown. `name:` must be a bare filename.

params:
  - name: target
    type: string                       # one of: bool | float | int | string
    required: true
    desc: Name of the company being briefed (e.g. "OpenAI").
  - name: focus
    type: string
    required: false
    default: general
    desc: |
      Aspect to emphasize: "general", "pricing", "hiring",
      "engineering", "go-to-market", etc. Free-form.

outputs:
  - name: brief.md
    desc: |
      Two-page narrative brief on {{ params.target }}, one H2 per theme.
      Cite primary sources by URL in inline links.
  - name: facts.json
    desc: |
      Structured fact sheet:
      {
        "founded": <int year | null>,
        "hq": <string | null>,
        "headcount_estimate": <int | null>,
        "funding_total_usd": <int | null>,
        "primary_products": [<string>...],
        "sources": [<url>...]
      }
---

You are producing a competitor brief for {{ params.target }}.

Start from {{ inputs.seed.md }} as primary source. Use the websearch
and fetch tools to confirm and extend: company background, products,
pricing posture, recent announcements, and anything relevant to the
focus area "{{ params.focus }}".

Write:
- out/brief.md — narrative brief, one H2 per theme. Cite every claim
  with an inline link to the source.
- out/facts.json — structured fact sheet matching the schema in the
  output description above. Use null for fields you cannot confirm.
```

Rationale for a functional reference (not a blank stub):

- **Every `desc:` is concrete prose.** A user editing "Seed material — the target's own About/Pricing page text…" into their own description writes better prose than a user filling in `desc: TODO`.
- **Editing a working example is cheaper than filling blanks.** The blank-page problem applies to agents too. Given a full artifact, an agent rewriting it for a different task removes what it doesn't need and adapts what it does; given a stub, it has to invent the shape.
- **`template | create` smoke-tests the full pipeline** on a fresh install: emit → pipe → parse → write → (optionally) `run`. If any link breaks, the one-liner surfaces it.

Trade-off accepted: the default pipeline (`artifact template | artifact create foo`) writes an opinionated artifact the user will edit. That's fine — delete is cheaper than invent, and an agent/user who wants something else pipes their own content through `create`.

## How `create` works

`artifact create <dir>` is a pure stdin→filesystem adapter:

1. **Guard against the empty/TTY cases.** If `sys.stdin.isatty()`, exit 1 with a one-line hint pointing at the pipe idiom. If stdin is piped but reads zero bytes, exit 1 with `error: stdin is empty`.
2. **Read stdin to a string.** UTF-8, no size limit (an ARTIFACT.md is kilobytes, not megabytes).
3. **Validate via the parser.** Call `parse_spec_from_str(content, synthetic_path)` — a new sibling of `parse_spec` that skips the file read (see Wiring). If validation fails, exit 1 with the parser's own message, no files written. This is the critical property: `create` never writes an invalid ARTIFACT.md.
4. **Guard the target directory.** `<dir>` is created if it does not exist. If `<dir>` exists and contains any entry → exit 1 with `error: <dir> is not empty`. No overwriting, no merge, no `--force`.
5. **Write two files atomically enough.** `<dir>/ARTIFACT.md` gets the exact stdin content (trailing newline added if missing). `<dir>/.gitignore` gets one line: `runs/*`. Both are committed to disk before the command returns. If writing `ARTIFACT.md` fails mid-write, `<dir>` is left as-is (we don't pretend to offer crash-safe atomicity for a two-file write; `git status` will show the mess). Explicit non-feature.
6. **Print the directory path and exit 0.** Same stdout convention as `artifact run` (prints the thing you pass to the next command).

`create` does not write `runs/`, `outs/`, or `src/` — the runner creates `runs/` lazily, `outs/` is born from `promote`, and `src/` is a future-executor concern. `create` writes exactly two files.

## Parser sync + the bare-filename rule

Two validation hardenings land as part of this DD, both inside `spec.py` so `create` and `run` benefit equally.

### 1. Shared allowed-value constants

`spec.py` currently holds `_ALLOWED_KINDS`, `_ALLOWED_EXECUTORS`, and `_ALLOWED_PARAM_TYPES` as module-private. Promote to public names:

```python
# src/artifact/spec.py
ALLOWED_KINDS = {"transform"}
ALLOWED_EXECUTORS = {"deepagent", "claude_cli"}
ALLOWED_PARAM_TYPES = {"string", "int", "float", "bool"}
```

`parse_spec` keeps using them unchanged. `template` imports them and interpolates their contents into the YAML comments it renders. When the set grows (as it did when `claude_cli` landed), `template`'s output updates automatically. No manual sync.

The `model:` field's comment is **not** driven purely from the constants: its validity rule is conditional on `executor` (`provider:name` under `deepagent`, bare name or omitted under `claude_cli`). The template's emitted `model:` line picks the `executor: deepagent` form because that's the default the reference uses; the YAML comment names the conditional rule in prose. A user who flips the template to `executor: claude_cli` edits the model line to suit, and `parse_spec` catches mistakes.

### 2. Bare-filename validation on `inputs[].name` and `outputs[].name`

New rule in `parse_spec`: for every entry in `inputs` and `outputs`, the `name` field must be a bare filename. Reject any name containing `/`, equal to `.` or `..`, or with a path separator of any kind. The exact check:

```python
def _require_bare_filename(name: str, kind: str, path: Path) -> None:
    if "/" in name or name in (".", "..") or Path(name).name != name:
        raise SpecError(
            f"{path}: {kind} name must be a bare filename, got {name!r}"
        )
```

Invoked from `_parse_input` and `_parse_output`. Not applied to `param.name` — params are identifiers, not filenames; they live in `params.json` keys and `{{ params.<name> }}` references. A separate identifier-validity rule for params is out of scope here (open question below).

This catches the "I wrote `name: /abs/mission.md` thinking I was providing the file path" mistake at parse time. The error message points at the right field. Both `create` (via its in-memory `parse_spec` call) and `run` get the fix for free.

### 3. Round-trip tripwire

Two unit tests guard the sync invariants:

```python
def test_template_output_parses():
    text = render_template()                        # no filesystem, pure str
    spec = parse_spec_from_str(text, Path("<template>"))
    assert spec.kind in ALLOWED_KINDS
    assert spec.executor in ALLOWED_EXECUTORS
    assert len(spec.inputs) >= 1
    assert len(spec.params) >= 1
    assert len(spec.outputs) >= 1

def test_template_comments_list_every_allowed_value():
    text = render_template()
    for v in ALLOWED_KINDS | ALLOWED_EXECUTORS | ALLOWED_PARAM_TYPES:
        assert v in text, f"{v} missing from generated comments"
```

First test catches "template drifted to invalid YAML"; second catches "parser grew; template didn't."

## Wiring

- **New module `src/artifact/create.py`.** Two public functions:
  ```python
  def render_template() -> str: ...
  def create(dest: Path, *, content: str) -> Path: ...
  ```
  `render_template` returns the reference ARTIFACT.md as a string, with YAML comments interpolated from `ALLOWED_*`. `create` validates `content` via the parser and writes the two files. Pure stdlib (`pathlib`). No stdin/argv handling in this module — that's `cli.py`'s job.
- **`src/artifact/spec.py`.**
  - Rename `_ALLOWED_KINDS` / `_ALLOWED_EXECUTORS` / `_ALLOWED_PARAM_TYPES` to public names. No in-tree consumer uses the private names.
  - Add `_require_bare_filename` and call it from `_parse_input` and `_parse_output`.
  - Add `parse_spec_from_str(content: str, path: Path) -> Spec` — the logic `parse_spec` already uses after reading bytes, factored out. `parse_spec` becomes a thin "read bytes + call `parse_spec_from_str`" wrapper. `create` calls `parse_spec_from_str` directly; no tempfile round-trip.
- **`src/artifact/cli.py`.** Two new subparsers:
  - `template` — no args, no flags. Calls `render_template()` and prints to stdout.
  - `create` — one positional `dir`. Reads `sys.stdin`. TTY / empty-stdin guards before parsing. Calls `create(Path(dir), content=content)`. Prints the returned path on success.
- **`tests/test_create.py`.** New file. Tests listed below.
- **`tests/test_cli.py`** (if it exists; otherwise in-line in `test_cli.py`'s sibling): add CLI-level tests for the TTY guard and the empty-stdin guard.

Nothing in `runner.py`, `promote.py`, `exec.py`, `template.py`, or `introspect.py` changes.

## Errors

| Condition | Exit | Stderr |
|---|---|---|
| `artifact create <dir>` invoked with stdin as a TTY | 1 | `error: create reads ARTIFACT.md from stdin; try: artifact template \| artifact create <dir>` |
| Stdin readable but empty | 1 | `error: stdin is empty` |
| Stdin content fails `parse_spec` (any `SpecError`) | 1 | `error: <SpecError message>` (verbatim) |
| `<dir>` exists and is non-empty | 1 | `error: <dir> is not empty` |
| `<dir>` cannot be created (permissions, etc.) | 1 | `error: <OSError message>` |

All errors are raised *before* any file is written. No partial state.

## Testing

Unit, no network, no LLM calls:

**`template`:**
- Output parses cleanly via `parse_spec_from_str`.
- Output declares at least one input, one param, one output (smoke — protects against "template accidentally became empty").
- Output contains every value in `ALLOWED_KINDS`, `ALLOWED_EXECUTORS`, `ALLOWED_PARAM_TYPES` as substrings (drift tripwire).
- Rendering is deterministic (same call produces identical bytes).

**`create`:**
- Piping `template`'s output to `create <tmp>/x` produces `<tmp>/x/ARTIFACT.md` (equal to the piped content) and `<tmp>/x/.gitignore` (exactly `runs/*\n`).
- Invalid input (stdin contains malformed YAML, missing `kind`, unknown `executor`, etc.) → exit 1 with the parser's error message, no files written.
- Non-empty target dir → exit 1, specific error message, no files written.
- TTY stdin → exit 1 with the hint message, no files written.
- Empty stdin → exit 1, no files written.

**Bare-filename validation:**
- `parse_spec` rejects `inputs[].name = "../x.md"`, `"/abs/x.md"`, `"sub/x.md"`, `"."`, `".."` with `SpecError` whose message names the offending field.
- Same for `outputs[].name`.
- `params[].name` unaffected (only inputs/outputs).

**End-to-end pipeline:**
- `artifact template | artifact create <tmp>/x` exits 0; `parse_spec(<tmp>/x/ARTIFACT.md)` succeeds.

No integration test. Nothing here calls out to LLMs or the network.

## Non-goals

- **Flags of any kind.** Covered above. If a future need arises, it lands as a separate flag-bearing subcommand rather than accreting onto these two.
- **Multiple shipped examples / `--example NAME`.** `template` emits exactly one reference artifact in v0.2. Adding more becomes relevant only once a second genuinely distinct example is worth shipping; at that point the shape is `artifact template NAME` (positional) or a new `artifact templates list` command.
- **Mutating an existing artifact.** `create` refuses non-empty directories. There is no `artifact add-input` or `artifact set-model`. Edit the YAML.
- **Identifier validation on `params[].name`.** Out of scope for this DD. Tracked in Open questions.
- **Ancestor `.gitignore` detection.** `create` always writes `runs/*` locally. Redundant when the artifact lives inside a repo with `runs/*` already ignored, correct when standalone. Not worth the complexity to detect and skip.
- **Project-level scaffolding.** `create` produces one artifact directory — not a parent repo, not `pyproject.toml`, not a README.

## Open questions

Not blocking; surfaced so they're not forgotten.

- **Identifier validity for `params[].name`.** Today any string passes. A future rule — `[A-Za-z_][A-Za-z0-9_]*`, say — would match what `{{ params.<name> }}` can safely resolve. Out of scope here; the filename case is the one that stung.
- **Listing / choosing examples.** When a second example ships, `template` gains a positional arg (`artifact template competitor-brief`) with the current content becoming the default. A separate `artifact templates` subcommand to list is also possible. Defer until there's a second.
- **Default model knob.** Hardcoded to `anthropic:claude-sonnet-4-6` in the emitted template. Environment-variable override (`ARTIFACT_DEFAULT_MODEL`) is the obvious next knob. Not in v0.2; users can `sed` the pipe.
- **DIKW prefix on `<dir>`.** The DD describes the `N-name/` convention but doesn't enforce it. `create` does not validate or auto-add the prefix; a warning ("hint: artifacts conventionally use a DIKW digit prefix") was considered and dropped — warnings users learn to ignore are worse than none.
- **Provenance for "I started from template@<sha>".** Snapshotting the git SHA of `template`'s source into the created artifact would let you tell whether a user scaffolded from the latest or a stale version. Useful eventually; out of scope for v0.2.
