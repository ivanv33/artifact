# artifact

A CLI for running *artifacts* — self-describing, git-native directories that package an LLM recipe with every run of it and its promoted outputs.

See `docs/artifact-dd.md` for the full design document. This README is a fast-start.

## The idea

One directory is one unit of knowledge work:

```
1-github-report/
├── ARTIFACT.md            # the recipe: YAML frontmatter + prompt body
├── runs/                  # append-only — one subdirectory per run (gitignored)
│   └── 2026-04-19T14-23-01-0700/
│       ├── manifest.json  # provenance: sha256s, params, model, labels
│       ├── in/            # staged input files
│       ├── params.json    # resolved param values
│       └── out/           # outputs produced by this run
└── outs/                  # promoted runs — mutable, label-addressed (git-tracked)
    └── alice/
        ├── manifest.json
        ├── in/
        ├── params.json
        └── out/
```

Five invariants:

1. `ARTIFACT.md` is the only required file — a fresh artifact is one file.
2. `runs/` is append-only; nothing inside a run is ever modified.
3. `outs/<label>/` is a **full copy** of a run directory, not a symlink — portable across filesystems and commits.
4. Every run has a `manifest.json` recording every hash, param, and model that produced it.
5. Outputs live in runs first, labels second.

## Install

From PyPI (`artf` is the distribution name):

```bash
uv tool install artf       # or: uvx artf <subcommand> for a one-shot run
```

For local development:

```bash
git clone https://github.com/ivanv33/artifact
cd artifact
uv sync
```

Either install exposes two console scripts — `artf` and `artifact` — pointing to the same entry point. Use whichever you prefer; examples below use `artifact`.

Put your LLM provider key in a `.env` at the repo root (or any parent directory of where you invoke `artifact`):

```
GOOGLE_API_KEY=...        # for google_genai:... models
ANTHROPIC_API_KEY=...     # for anthropic:... models
```

For Claude subscription auth (no API key), declare `executor: claude_cli` in your `ARTIFACT.md` instead of `executor: deepagent`. The CLI shells out to your local `claude` binary and uses your Pro/Max session. Requires:
- `claude` on `$PATH` (`npm i -g @anthropic-ai/claude-code`)
- An authenticated session (`claude /login`)
- A real TTY (won't work backgrounded)

See `docs/claude-cli-executor-dd.md` for details.

The CLI auto-loads `.env` from the nearest parent directory (like `docker compose` or `aider`). Shell-exported env vars still win, so CI/Docker-injected secrets are never overridden.

## ARTIFACT.md

YAML frontmatter + markdown body. Example:

```yaml
---
kind: transform                     # only `transform` in v0.2
executor: deepagent                 # `deepagent` or `claude_cli`
model: anthropic:claude-sonnet-4-6  # any langchain provider:model string (required for deepagent; optional bare name for claude_cli)

inputs:
  - name: events.json
    desc: GitHub events export.
  - name: mission.md
    desc: Target org's mission statement.

params:
  - name: user
    type: string
    required: true
    desc: GitHub username the report is about.
  - name: focus
    type: string
    required: false
    default: general
    desc: Optional focus area.

outputs:
  - name: report.md
    desc: Narrative activity report.
  - name: stats.json
    desc: Structured counts/aggregates.
---

You are producing a GitHub activity report for {{ params.user }}.

Read in/events.json and in/mission.md. Write out/report.md and out/stats.json.
If {{ params.focus }} is set, emphasize that focus.
```

Template variables available in the body:
- `{{ params.<name> }}` — the resolved param value.
- `{{ inputs.<name> }}` — the absolute path to the staged input in `runs/<id>/in/<name>`.

## Commands

```bash
# Execute one run
artifact run <artifact-dir>
    [--input NAME=PATH]...     # repeat for each declared input
    [--param NAME=VALUE]...    # repeat for each param you set
    [--model PROVIDER:NAME]    # override ARTIFACT.md's model for this run
    [--promote-as LABEL]       # also copy the run to outs/<LABEL>/

# Promote an existing run to a label after the fact
artifact promote <artifact-dir> <run-id> --as <label>

# List runs (newest first) with timestamp, promoted labels, and params
artifact runs <artifact-dir>

# Show ARTIFACT.md frontmatter and current outs/ labels
artifact show <artifact-dir>
```

Each command exits with a non-zero code and prints `error: <msg>` to stderr on expected failures (bad params, missing inputs, malformed frontmatter, missing declared outputs).

## Example

```bash
# Run the report for Alice, promoting the result to outs/alice/
artifact run 1-github-report/ \
  --input events.json=/path/to/alice-events.json \
  --input mission.md=/path/to/growth-mission.md \
  --param user=alice \
  --promote-as alice
```

Outcome:
- `1-github-report/runs/<timestamp>/` contains `in/`, `out/`, `params.json`, `manifest.json`.
- `1-github-report/outs/alice/` is a full copy of that run.
- Both `manifest.json` files list `"promoted_to": ["alice"]`.
- The run dir's timestamp name matches its manifest's `timestamp` field — deterministic lookup.

## Git conventions

- `ARTIFACT.md`, `outs/` — committed. `outs/` is the published state of the artifact, with provenance.
- `runs/` — ignored by default. Add `runs/*` to `.gitignore` at the artifact-containing repo root (see this repo's `.gitignore`).

## Testing

```bash
uv run pytest                    # 80 unit tests, no network, < 1 second
uv run pytest -m integration     # opt-in: live calls; needs GOOGLE_API_KEY and/or `claude` on PATH
```

Integration tests skip cleanly when their prerequisites are missing — the Gemini tests need `GOOGLE_API_KEY`, the `executor: claude_cli` tests need an authenticated `claude` CLI.

## What's not in v0.2

Deliberately deferred to a future version (per the design doc):

- `kind: run` (orchestration artifacts that wire other artifacts together)
- Non-LLM executors (`executor: python` etc.)
- Input schema validation beyond a prose description
- Cross-artifact dependencies
- MCP server exposure
- Retention policies for old runs
- Cost/approval metadata

See `docs/artifact-dd.md` §Open questions for the roadmap.
