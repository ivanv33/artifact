# DD: `artifact create`

*Addendum to `artifact-dd.md` — adds one subcommand and one shipped example artifact.*

## Problem

Two failure modes today:

1. **Hand-written `ARTIFACT.md` files ship malformed.** YAML is unforgiving (a missing `desc:`, a stray tab, an unquoted `:` in a value), and the parser rejects them at run time, *after* the user has already shaped the rest of the directory in their head. The recipe should be valid by construction.
2. **Agents have no clean way to scaffold one.** A Claude Code session that wants to spin up a new artifact has to either remember the full frontmatter shape and emit it via `Write` (error-prone, drifts from the parser) or be taught a multi-step ritual. A single CLI call that produces a parseable file is the right surface.

The original DD said "a user can create an artifact with `mkdir` and an editor." That's still true. `create` adds a faster, parser-correct path for the people and agents that want one — without changing the underlying primitive.

## Change

One new subcommand:

```
artifact create <dir>
    [--model PROVIDER:NAME]    # set (or override) the declared model
    [--example NAME]           # start from a shipped example artifact instead of the stub
    [--body-file PATH]         # replace the body with the contents of PATH (use - for stdin)
    [--force]                  # overwrite an existing ARTIFACT.md
```

Plus implicit stdin: when stdin is piped (`isatty(0) == False`), its contents replace the body, equivalent to `--body-file -`. When both implicit stdin and `--body-file` are set, `--body-file` wins.

The directory is created if it does not exist. If `<dir>/ARTIFACT.md` already exists, the command exits 1 with `error: <dir>/ARTIFACT.md exists; pass --force to overwrite` unless `--force` is given. No `runs/`, `outs/`, or `.gitignore` is created — those are managed elsewhere (the runner creates `runs/` lazily; `.gitignore` is the surrounding repo's concern).

Stdout: the path of the written artifact directory (the argument `<dir>`, made absolute). Matches `artifact run`'s convention of printing the thing you pass to the next command — `artifact run "$(artifact create foo)"` is the intended pipeline shape.

### Two modes

**Default (no `--example`):** emit a minimal stub. Required fields filled with sensible defaults; `inputs/params/outputs` present as empty lists with comments explaining what to add; body is a placeholder paragraph instructing the agent/user to describe the task. The result parses immediately. Supports the agent path (B+E from "Problem"): an agent runs `artifact create my-thing`, then edits the file or pipes a body.

**With `--example NAME`:** copy a shipped, fully-functional artifact from `<package>/examples/<NAME>/` into `<dir>`. Inherits the example's frontmatter and body verbatim. `--model` overrides the declared model; `--body-file`/stdin overrides the body. Other fields (inputs, params, outputs) are inherited unchanged — the user edits the file afterward to specialize.

## The default stub

Generated for `artifact create my-thing` with no flags:

```yaml
---
# kind: shape of the artifact. v0.2 supports: transform
kind: transform
# executor: how the body is run. v0.2 supports: deepagent
executor: deepagent
# model: provider:name string handed to the executor.
# Override per-run with `artifact run --model PROVIDER:NAME`.
model: anthropic:claude-sonnet-4-6

# inputs: declared input files this artifact consumes.
# Each entry is { name: <basename>, desc: <prose> }.
# The runner stages each input under runs/<id>/in/<name>; reference
# them in the body as {{ inputs.<name> }} (resolves to an absolute path).
inputs: []

# params: declared scalar knobs.
# Each entry is { name, type, required, default?, desc }.
# type is one of: string | int | float | bool.
# Reference in the body as {{ params.<name> }}.
params: []

# outputs: declared output files this artifact must produce in out/.
# Missing outputs fail the run; undeclared extras are warned but allowed.
# Each entry is { name: <basename>, desc: <prose> }.
outputs: []
---

TODO: describe the task. The deep agent reads this as its system prompt.
Reference declared params with `{{ params.<name> }}` and declared inputs
with `{{ inputs.<name> }}` (resolves to an absolute path on disk).
```

Notes on the comments:

- **Allowed-value comments are computed**, not hardcoded. The strings `transform`, `deepagent`, and `string | int | float | bool` are interpolated from the parser's authoritative sets at render time (see "Sync with the parser" below). When the parser gains a new kind/executor, the stub's comments update automatically.
- **Default model** is `anthropic:claude-sonnet-4-6` — matches the worked examples in the DD. Overridable via `--model`.
- The body is intentionally one short paragraph. Agents who pipe a body via stdin replace it cleanly; humans who edit it have a one-line cue, not a wall to delete.

## The hero example: `competitor-brief`

Committed at `examples/competitor-brief/` in the repo. The DIKW digit prefix is intentionally dropped from shipped-with-the-package examples — the prefix is a convention for the *user's* artifact hierarchy, not for pedagogical material that lives outside it.

A real, runnable artifact — not a template string. Single source of truth: `parse_spec` parses it, `artifact run` runs it, and `artifact create --example competitor-brief` copies it. The `--example` flag value matches the directory name verbatim.

Why a competitor brief: it's recognizable knowledge work everyone has done by hand, and it naturally exercises every primitive — file inputs, multiple params, websearch + fetch tools, multiple outputs, and the "label per target" promotion pattern.

Sketch (final wording produced during implementation):

```yaml
---
kind: transform
executor: deepagent
model: anthropic:claude-sonnet-4-6

inputs:
  - name: seed.md
    desc: |
      Seed material — the target's own About/Pricing page text, a press
      release, or any short document that anchors the brief in primary source.
      Plain markdown.

params:
  - name: target
    type: string
    required: true
    desc: Name of the company being briefed (e.g. "OpenAI").
  - name: focus
    type: string
    required: false
    default: general
    desc: |
      Aspect to emphasize: "general", "pricing", "hiring", "engineering",
      "go-to-market", etc. Free-form.

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

Start from {{ inputs.seed.md }} as primary source. Use the websearch and
fetch tools to confirm and extend: company background, products, pricing
posture, recent announcements, and anything relevant to the focus area
"{{ params.focus }}".

Write:
- out/brief.md — narrative brief, one H2 per theme. Cite every claim
  with an inline link to the source.
- out/facts.json — structured fact sheet matching the schema in the
  output description above. Use null for fields you cannot confirm.
```

Intended workflow that the README/tutorial walks through:

```bash
artifact create research --example competitor-brief
# edit research/ARTIFACT.md if you want to change anything
artifact run research/ \
  --input seed.md=./openai-about.md \
  --param target=OpenAI \
  --promote-as openai
```

Result: `research/outs/openai/` is a complete, committed brief with full provenance — exactly the thing the artifact primitive exists to make first-class.

## Body input

Order of precedence, highest wins:

1. `--body-file PATH` (where `PATH = -` means read stdin).
2. Implicit stdin (when `isatty(0) == False`).
3. The body baked into the chosen mode (stub placeholder or example body).

Notes:

- Interactive users (`artifact create foo` typed into a terminal) hit case 3 — stdin is a TTY, no implicit consumption, no hang.
- Agents that pipe (`echo "..." | artifact create foo`) hit case 2 — clean, no flag needed.
- Heredocs (`artifact create foo <<'EOF' ... EOF`) hit case 2.
- Reading from a real file (`artifact create foo < prompt.md`) hits case 2 via redirection — no separate flag for "read from file."
- `--body-file -` is the explicit form of case 2, useful in scripts where the author wants the intent visible.

The body is inserted verbatim after the closing `---\n`. No trailing newline is appended if the body already ends with one; one is appended if it does not (so the file always ends in `\n`).

## Sync with the parser

The risk: `create` hardcodes "transform | deepagent | string | int | float | bool" in its comments; the parser later grows a new kind/executor; comments lie.

Fix in two parts:

**1. Promote the parser's allowed-value sets to public constants.**

In `src/artifact/spec.py`, rename the leading-underscore sets to public names (or, equivalently, lift them to a tiny `src/artifact/constants.py` and import from `spec.py` for backward compatibility within the package — same effect, slightly cleaner separation):

```python
ALLOWED_KINDS = {"transform"}
ALLOWED_EXECUTORS = {"deepagent"}
ALLOWED_PARAM_TYPES = {"string", "int", "float", "bool"}
```

`parse_spec` keeps using them for validation, unchanged. The `create` module imports them and interpolates into its rendered comments. New value added to the parser → next render of the stub picks it up automatically.

**2. Round-trip test as the tripwire.**

Two unit tests guard the invariants:

```python
def test_default_stub_parses(tmp_path):
    create(tmp_path / "x")
    spec = parse_spec(tmp_path / "x" / "ARTIFACT.md")
    # Sanity: required fields populated, lists empty.
    assert spec.kind in ALLOWED_KINDS
    assert spec.executor in ALLOWED_EXECUTORS
    assert spec.inputs == [] and spec.params == [] and spec.outputs == []

def test_stub_comments_list_every_allowed_value(tmp_path):
    create(tmp_path / "x")
    text = (tmp_path / "x" / "ARTIFACT.md").read_text()
    for v in ALLOWED_KINDS | ALLOWED_EXECUTORS | ALLOWED_PARAM_TYPES:
        assert v in text, f"{v} missing from generated comments"
```

The hero example does not need its own sync test because it IS a real artifact — the existing test suite already parses it via `parse_spec` (and an integration test optionally runs it).

## Wiring

New file: `src/artifact/create.py`. One public function:

```python
def create(
    dest: Path,
    *,
    model: str | None = None,
    example: str | None = None,
    body: str | None = None,
    force: bool = False,
) -> Path:
    """Write a new ARTIFACT.md under `dest`. Returns the written path."""
```

Pure stdlib (`pathlib`, `shutil`, plus the parser's constants). No I/O on stdin or argv — that lives in `cli.py`.

Changes elsewhere:

1. **`src/artifact/cli.py`**: add `create` subparser with the four flags above. Read implicit stdin via `sys.stdin.isatty()` + `sys.stdin.read()`. Validate `--model ""` the same way `run` does. When `--body-file` is given, it is the body source — implicit stdin is ignored without warning, and `--body-file -` resolves explicitly to stdin (the two equivalent ways to say "use stdin"). When `--body-file` is absent and stdin is piped, stdin is the body source.
2. **`src/artifact/spec.py`**: rename `_ALLOWED_KINDS`/`_ALLOWED_EXECUTORS`/`_ALLOWED_PARAM_TYPES` to public names. Update internal references.
3. **`examples/competitor-brief/ARTIFACT.md`**: new file, the hero. Committed.
4. **`examples/` shipped with the package**: update `pyproject.toml` to include `examples/**` as package data so `artifact create --example competitor-brief` can find it after `pip install`/`uv pip install`. Resolve via `importlib.resources`.

`README.md`: add a "Quick start" snippet using `artifact create … --example competitor-brief` as the lead example.

## Errors

| Condition | Exit | Stderr |
|---|---|---|
| `<dir>/ARTIFACT.md` exists, no `--force` | 1 | `error: <path> exists; pass --force to overwrite` |
| `--model ""` | 1 | `error: --model requires a non-empty string` |
| `--example NAME` where NAME is not shipped | 1 | `error: unknown example <NAME>; available: <list>` |
| `--body-file PATH` where PATH does not exist (and is not `-`) | 1 | `error: --body-file: <path> not found` |
| `<dir>` cannot be created (permission, etc.) | 1 | `error: <oserror message>` |

All errors print before any file is written. No partial state.

## Testing

Unit tests in `tests/test_create.py` (no network, fast):

- Default stub is created, parses, has empty inputs/params/outputs.
- Stub comments contain every value from the parser's allowed-value sets (the sync tripwire).
- `--model X` produces a stub whose `spec.model == X`.
- `--example competitor-brief` copies the hero verbatim; `parse_spec` succeeds; `--model X` overrides the declared model; `--body-file F` replaces the body.
- Implicit stdin: feed a bytes string to a fake stdin → body equals that string.
- `--body-file -` with stdin: body equals stdin.
- `--body-file PATH`: body equals file contents.
- Precedence: `--body-file PATH` beats piped stdin.
- Error cases from the table above each have a test asserting exit code, stderr text, and that no file was written.

No new integration test. `create` does not call out to LLMs, the network, or any executor.

## Non-goals

- **Multiple shipped examples beyond the hero.** v0.2 ships `2-competitor-brief` only. Adding more (a paper summarizer, a weekly digest, etc.) is a follow-up — easy to do once the `--example` machinery exists, but not part of this DD.
- **Project-level scaffolding.** `create` produces one artifact directory, not a parent repo with `.gitignore`, README, `pyproject.toml`, etc. The artifact is one directory; surrounding repo concerns are out of scope.
- **Interactive wizard.** No prompts, no TUI. Flags + stdin only; the surface is identical for humans, scripts, and agents.
- **Per-shape flags** (`--input-name X`, `--param-name Y`, `--output-name Z`). An earlier draft included these to let callers set declared shape from the CLI without editing the file. Dropping them: with `--example` available for "start from something concrete" and the stub default for "start from minimum, edit afterward," shape flags don't pay rent. Adding inputs/params/outputs is a one-line YAML edit; agents do that with `Edit` in two seconds. The validation idea attached to those flags (rejecting paths in `--input-name`) is retired with them.
- **`artifact template` as a separate command.** Considered. Folded into `create`'s default behavior: the stub *is* the template. The generated file's comments are its documentation.
- **Mutating an existing artifact.** `create --force` overwrites; it does not merge. There is no `artifact add-input` or `artifact set-model`. The file is small enough that editing it directly is faster than memorizing a CLI for it.

## Open questions

Not blocking; surfaced so they're not forgotten.

- **Multiple examples.** When a second example is added, do we want a flat namespace (`--example weekly-digest`) or hierarchical (`--example digest/weekly`)? Trivial for two; matters at five. Defer until we have three.
- **Listing examples.** `artifact create --list-examples`? `artifact examples`? Current answer: defer; until there are >2, the README is the catalog.
- **Default model.** Hardcoded to `anthropic:claude-sonnet-4-6`. Could read `ARTIFACT_DEFAULT_MODEL` from the env. Not in v0.2 — one config knob is one config knob.
- **DIKW prefix on `<dir>`.** The DD describes the `N-name/` convention but doesn't enforce it. `create` does not validate or auto-add the prefix. Could warn when `<dir>` is missing one (`hint: artifacts conventionally use a DIKW digit prefix; got "research"`); deferred — warnings users learn to ignore are worse than none, and the convention is informal.
- **Should `create --example` snapshot the example's git SHA into the new artifact?** Provenance for "this was forked from `competitor-brief@<sha>`." Useful for "did this user start from the latest hero or a stale one?" Probably yes, eventually; out of scope for v0.2.
