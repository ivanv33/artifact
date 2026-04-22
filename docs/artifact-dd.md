# PRD: The Artifact Primitive

*Version 0.2 — single-artifact specification*

## Problem

Knowledge work produces outputs — reports, analyses, lists, recommendations — that have no durable home. The recipe that produced them lives in a chat session, a notebook, or someone's head. Three failure modes follow:

*Chat lock-in.* A multi-step AI chat produces a useful result. Changing step three requires redoing everything after it. The intermediate steps aren't addressable, so they can't be edited in isolation.

*Unreproducible outputs.* A markdown file in a repo is bytes without provenance. You can't tell what produced it, when, from what inputs, with what prompt.

*Unshareable work.* Sharing only an output gives consumers a fish. Sharing the chat transcript is unreadable. There's no unit that packages "the answer and how we got it" such that someone else can re-run or adapt it.

The artifact is the unit that fixes this. An artifact is a directory containing the algorithm, the inputs, the parameters, and every output ever produced. It's git-native, self-describing, and executable. Humans write some; Python produces others; LLMs produce others; they all share one shape.

## Goals

1. A single directory fully describes one unit of knowledge work: recipe + history + current state.
2. An artifact can be executed by a human with a CLI command.
3. Every run is captured immutably with full provenance.
4. Outputs that matter are explicitly promoted; outputs that don't disappear quietly.
5. Nothing about an artifact depends on its location in a larger repo or knowledge graph — it's a standalone unit.

## Non-goals (v0.2)

- `kind: run` (orchestration / wiring) artifacts.
- `executor: python` — deferred; v0.2 is deep-agent-only.
- Claude Code skill integration (`artifact-runner` skill).
- Input schema validation. Inputs are declared with a human-readable description only.
- Cost budgeting and approval metadata.
- Cross-artifact dependencies (`deps`).
- MCP server exposure.
- Retention policies for old runs.
- Multi-repo composition.

These are coherent future extensions. Explicitly deferred.

---

## The artifact directory

One artifact is one directory. The directory name is its identity — conventionally prefixed with a DIKW level digit (`0-` raw data, `1-` info, `2-` knowledge, `3-` wisdom), but that's a convention, not a semantic requirement.

```
1-github-report/
├── ARTIFACT.md            # the recipe — frontmatter + prompt/instructions
├── src/                   # optional — for future executors; unused in v0.2
├── runs/                  # append-only history — every run lands here
│   └── 2026-04-19T14-23-01-0700/
│       ├── manifest.json
│       ├── in/            # snapshot of inputs at run time
│       ├── params.json
│       └── out/           # outputs produced by this run
└── outs/                  # promoted runs — mutable, label-addressable
    └── alice/
        ├── manifest.json
        ├── in/
        ├── params.json
        └── out/
```

Five invariants:

1. **`ARTIFACT.md` is the only required file.** A fresh artifact is one file.
2. **`runs/` is append-only.** Nothing is ever modified in place inside a run directory. Runs may be deleted (retention), never edited.
3. **`outs/<label>/` is a copy of a run's entire `runs/<timestamp>/` directory, never a symlink.** That means `outs/<label>/` contains `manifest.json`, `in/`, `params.json`, and `out/` — the full provenance travels with the promoted output. Portable across filesystems and consumers.
4. **Every run has a `manifest.json`** recording inputs (with content hashes), params, executor, model, the SHA of the `ARTIFACT.md` that produced it, and any labels it was promoted to.
5. **Outputs live in runs first, labels second.** A label points at a run. No output exists outside a run.

## Timestamps

Run directories use **ISO 8601 local time with timezone offset**, colons replaced with hyphens for filesystem safety: `2026-04-19T14-23-01-0700`. The timezone is the machine's local tz at run time. Rationale: humans looking at `runs/` should see timestamps that match their wall clock without mental conversion. The manifest also records a proper ISO-8601 string for machine consumption.

## ARTIFACT.md

YAML frontmatter + prose body.

```yaml
---
kind: transform                    # transform only in v0.2
executor: deepagent                # deepagent only in v0.2
model: anthropic:claude-sonnet-4-6 # required

inputs:
  - name: events.json
    desc: |
      GitHub events export for one user over a date range.
      Array of {type, repo, timestamp, payload} records.
  - name: mission.md
    desc: |
      Target org's mission statement. Freeform markdown.

params:
  - name: user
    type: string
    required: true
    desc: GitHub username the report is about.
  - name: focus
    type: string
    required: false
    default: general
    desc: Optional focus area (e.g. "security", "performance").

outputs:
  - name: report.md
    desc: Narrative report summarizing the user's activity and mission alignment.
  - name: stats.json
    desc: Structured counts and aggregates (PR count, languages, etc.).
---

You are producing a GitHub activity report for {{ params.user }}.

Read events.json and produce:

1. `out/report.md` — a narrative report. One H2 per theme. Cite specific
   events by link. End with a section on mission alignment, referencing
   mission.md if relevant.

2. `out/stats.json` — JSON with:
   {
     "pr_count": <int>,
     "commit_count": <int>,
     "languages": [<string>],
     "most_active_repo": <string>
   }

If `params.focus` is set, emphasize activity relevant to that focus.
```

Field rules:

- **`kind: transform`** — artifact has inputs/params and produces outputs via a deep agent.
- **`executor: deepagent`** — body is a system prompt for a deep agent with filesystem access scoped to the run directory. Model is set by `model:` field.
- **`inputs`** — named files the artifact consumes. Description is prose; no schema yet.
- **`params`** — scalar knobs. Type is `string | int | float | bool`. `required: true` with no default means the runner refuses to run without it.
- **`outputs`** — declared names with descriptions. The runner enforces that declared outputs exist in `out/` after execution; undeclared output files are a warning, not an error.

Template variables available in the body: `{{ params.<name> }}` for each declared param, `{{ inputs.<name> }}` for the path to each staged input inside the run. Substituted before dispatch.

---

## Execution

One command:

```
artifacts run <artifact-dir> [--input name=path]... [--param name=value]... [--promote-as label]
```

The runner does, in order:

1. **Parse `ARTIFACT.md`.** Validate frontmatter: required fields present, executor is `deepagent`, kind is `transform`, all required params supplied, all declared inputs have `--input` mappings.
2. **Create a run directory.** `runs/<local-timestamp-with-tz>/`, e.g. `runs/2026-04-19T14-23-01-0700/`.
3. **Stage inputs.** For each `--input name=path`, copy the file to `runs/<id>/in/<name>`. Compute SHA-256. Refuse to run if path doesn't exist.
4. **Write params.** Resolved param values (explicit + defaults) to `runs/<id>/params.json`.
5. **Template the body.** Substitute `{{ params.* }}` and `{{ inputs.* }}` (the latter becomes absolute paths to the staged files).
6. **Dispatch.** `create_deep_agent(model=<frontmatter.model>, system_prompt=<templated body>, backend=FilesystemBackend(root_dir=runs/<id>/))`. Invoke with one user message: "Execute the recipe. Write outputs to `out/` matching the declared output names." Wait for completion.
7. **Verify outputs.** Every name in `outputs` must exist in `runs/<id>/out/`. Missing outputs = run fails. Extra files = warning.
8. **Write manifest.** `runs/<id>/manifest.json`:
    ```json
    {
      "artifact": "1-github-report",
      "run_id": "2026-04-19T14-23-01-0700",
      "timestamp": "2026-04-19T14:23:01-07:00",
      "artifact_md_sha256": "a3f8...",
      "executor": "deepagent",
      "model": "anthropic:claude-sonnet-4-6",
      "inputs": [
        {"name": "events.json", "sha256": "b2c7...", "source": "/abs/path/from/--input"},
        {"name": "mission.md", "sha256": "e4f1...", "source": "/abs/path/from/--input"}
      ],
      "params": {"user": "alice", "focus": "general"},
      "outputs": ["report.md", "stats.json"],
      "promoted_to": []
    }
    ```
9. **Promote, if requested.** If `--promote-as <label>`: copy the entire `runs/<id>/` directory — manifest, `in/`, `params.json`, `out/` — into `outs/<label>/`. Add `<label>` to `promoted_to` in both the original run's manifest and the copy under `outs/`.

The runner exits with the path to the run directory on stdout.

---

## Worked examples

### Example 1 — Standard transform: `1-github-report`

The one from the ARTIFACT.md example above. Takes an `events.json` produced elsewhere and a mission file, produces a narrative report and a stats JSON.

```
artifacts run 1-github-report/ \
  --input events.json=/path/to/alice-events.json \
  --input mission.md=/path/to/growth-mission.md \
  --param user=alice \
  --promote-as alice
```

The runner stages both files into `runs/2026-04-19T14-23-01-0700/in/`, writes `params.json`, templates the ARTIFACT.md body, hands it to a deep agent with the run directory as filesystem root. The agent reads `in/events.json` and `in/mission.md`, writes `out/report.md` and `out/stats.json`. Runner verifies both outputs exist. Promotion copies the whole run directory to `outs/alice/` — so consumers can see the report *and* the exact inputs and params that produced it.

### Example 2 — No-input survey artifact: `1-trending-rust-crates`

No file inputs. One param. Runs periodically.

```yaml
---
kind: transform
executor: deepagent
model: anthropic:claude-sonnet-4-6
params:
  - name: as_of
    type: string
    required: true
    desc: "Date the report reflects, e.g. '2026-04-19'."
outputs:
  - name: trending.md
    desc: A survey of currently-trending Rust crates with short notes.
---

Survey currently-trending Rust crates using web search. For each:
- Name, one-line purpose, GitHub stars (approximate if needed).
- One sentence on what's interesting about it right now.

Write out/trending.md as a flat list under an H1 dated {{ params.as_of }}.
```

Run: `artifacts run 1-trending-rust-crates/ --param as_of=2026-04-19 --promote-as latest`. Runs again next week with a new `as_of`, promoted to `latest` again; old ones remain in `runs/` for history. `git diff outs/latest/out/trending.md` shows what changed week-over-week.

### Example 3 — Ephemeral / unpromoted run

Same `1-github-report` artifact as example 1. This time:

```
artifacts run 1-github-report/ \
  --input events.json=/path/to/bob-events.json \
  --input mission.md=/path/to/growth-mission.md \
  --param user=bob \
  --param focus=security
```

No `--promote-as`. The run lands in `runs/2026-04-19T15-02-44-0700/`, no promotion. The user inspects `runs/<id>/out/report.md`; if it's good, they run again with `--promote-as bob-security`; if not, they tweak params and try again. The unpromoted run remains in `runs/` until retention prunes it — no consumer sees it, nothing downstream broke.

### Example 4 — Multi-output artifact: `2-competitor-brief`

Two outputs from one invocation, both declared, both verified.

```yaml
---
kind: transform
executor: deepagent
model: anthropic:claude-sonnet-4-6
inputs:
  - name: pricing.csv
    desc: Scraped competitor pricing data, columns [company, tier, price, features].
params:
  - name: target
    type: string
    required: true
    desc: Name of the competitor to brief on.
outputs:
  - name: brief.md
    desc: Two-page narrative brief on the target competitor.
  - name: comparison.json
    desc: |
      Structured tier-by-tier comparison of us vs target, shape:
      {"tiers": [{"name", "us_price", "them_price", "gap_notes"}]}
---

Produce a competitor brief for {{ params.target }} using pricing.csv.

Write:
- out/brief.md — narrative: positioning, tier structure, where they're
  cheaper, where they're expensive, what bundles they offer that we don't.
- out/comparison.json — tier-by-tier structured comparison per the schema
  described above.
```

Runner verifies both files exist after the deep agent finishes. Missing either one fails the run.

---

## CLI surface

Minimum commands for v0.2:

```
artifacts run <dir> [--input name=path]... [--param name=value]... [--promote-as <label>]
    Execute one artifact. Creates a run, optionally promotes.

artifacts promote <dir> <run-id> --as <label>
    Promote an existing run to a label after the fact.

artifacts runs <dir>
    List runs in an artifact, most recent first, showing params and promoted labels.

artifacts show <dir>
    Print the artifact's ARTIFACT.md frontmatter plus its current labels under outs/.
```

No subcommands for scaffolding, no daemon, no watch mode. A user can create an artifact with `mkdir` and an editor.

## Git conventions

- `ARTIFACT.md`, `src/` — committed always.
- `outs/` — committed always. This is the published state of the artifact, including provenance.
- `runs/` — ignored by default The rule:
    ```
    # .gitignore
    runs/*
    ```
    
## Success criteria

This PRD is satisfied when a user can:

1. Create a new directory containing only an `ARTIFACT.md` with valid frontmatter.
2. Run it from the CLI, supplying inputs and params as needed.
3. See a locally-timestamped run under `runs/` containing `in/`, `params.json`, `out/`, and `manifest.json`.
4. Promote a run to a label and see `outs/<label>/` contain the full run directory (manifest, inputs, params, outputs).
5. Inspect `manifest.json` for any run and reconstruct exactly what went into producing its outputs: the ARTIFACT.md hash, the input file hashes, the param values, the model.
6. Git-clone the repo on a fresh machine and see the same `outs/<label>/` state, with every promoted run's history intact.

## Open questions for v0.3

These are named so they don't get forgotten, not resolved here:

- *Python executor.* `src/main.py` with uv: `uv run --project <artifact-dir> src/main.py`. Each artifact gets its own `pyproject.toml` under `src/`; the runner delegates environment isolation to uv. Pulled from v0.2 to keep scope tight; the directory shape already reserves `src/` for it.
- *Passthrough executor.* Human-authored artifacts where running captures current state.
- *Claude Code skill integration.* `artifact-runner` skill that parses `@ARTIFACT.md` references and invokes the runner.
- *Input schemas.* When does "prose description" become insufficient? Probably at the first shape-drift bug.
- *Cost/approval metadata.* Needed before exposing via MCP to other agents.
- *Deps and run-artifacts.* The orchestration primitive.
- *Retention.* When does `runs/` get too large to tolerate?
- *Label namespacing.* Are labels flat strings forever, or do they need structure (`user/alice`, `region/us`)?
- *Parameter fan-out.* One invocation producing many labeled outputs (e.g., "run the report for all users in this list").

Not problems now. Listed so they're visible when they become problems.
