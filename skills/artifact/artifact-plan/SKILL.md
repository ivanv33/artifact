---
name: artifact-plan
description: "Decompose an ambiguous objective into a DAG of reusable DIKW artifacts and write an executable plan.md file. Use when user says 'plan artifacts for X', has a broad goal needing decomposition, or wants to design an artifact chain before creating anything. This command produces the plan only — it does NOT create artifact directories or outputs."
user-invocable: true
---

# artifact-plan

Transform an ambiguous objective into an executable plan — a markdown file with numbered steps that Claude can follow to create a chain of artifacts.

**This is a conversational subcommand.** Work back and forth with the user, starting with open questions and outline, before writing the plan.

**This command produces the plan only.** It does NOT create artifact directories or outputs. Use `/artifact create-plan-artifacts` after to create everything.

Read the parent skill at `../SKILL.md` for artifact structure, DIKW prefixes, and `@` reference syntax.

## Agent workflow

### 1. Identify the terminal artifact

What is the final decision or insight? Usually `2-` (knowledge) or `3-` (wisdom).

### 2. Reverse-engineer the lineage

Work backward: what data does the terminal need? Each dependency becomes a node.

**Always save raw data as an artifact.** Every decomposition starts with data — the ground truth that everything else builds on.

**The DIKW layers are a progression from truth to judgment:**

- **Data (0-)** — Raw facts. Downloaded, scraped, or imported. Close to the source, no opinions. Always worth saving — this is the ground truth you can always go back to. Example: `0-weather` downloads a weather CSV. `0-rental-listings` scrapes StreetEasy.
- **Info (1-)** — Derivative of data, still close to truth. Filtered, joined, aggregated, tagged — but not yet making predictions. Example: `1-passover-weather` tags weather rows by Hebrew calendar dates. `1-buy-vs-rent-costs` joins listings + rates into a cost comparison. Only create info artifacts when the derived dataset is reusable on its own.
- **Knowledge (2-)** — Prediction models built from data and info. This is where the heavy thinking happens — write a Python script that reads data/info, applies domain logic, computes statistics, builds models. Example: `2-passover-rain-verdict` writes a script that reads weather CSV, uses a Hebrew calendar lib, runs Fisher exact test, produces a statistical verdict.
- **Wisdom (3-)** — Conclusions and decisions using knowledge, info, and data. Synthesizes the numbers with qualitative factors into actionable recommendations. Example: `3-housing-decision` reads the analysis and produces "buy if X, rent if Y."

**Don't over-decompose.** If intermediate processing is only useful as a stepping stone (not reusable on its own), fold it into the downstream artifact's script. The test: **would someone reuse this intermediate artifact independently?** If not, it's a step inside a script, not a separate artifact.

**Example — "Is it always rainy on Passover in NYC?"** See `../examples/passover-rain.md` for the full walkthrough. Two artifacts: `0-weather` (data) feeds `2-passover-rain-verdict` (knowledge script). No info layer — the tagging and stats are steps inside the knowledge script, not separate reusable datasets.

### 3. Apply the Lego Test

Each artifact must be a **generic primitive** — reusable beyond this specific question.

- **DO**: `0-weather` with `location` and `date_range` params
- **DON'T**: `0-passover-weather` (too specific — Passover logic belongs in the knowledge artifact)
- **DO**: `0-rental-listings` with `neighborhood` param
- **DON'T**: `0-bushwick-rentals` (too specific)

Specifics go in `params:` defaults — but only when the value is genuinely variable across runs (zip code, date range, region, from/to).

**Don't pad `params:` with everything that could be a knob.** Fixed selection criteria, scoring weights, hardcoded thresholds, or one-shot inputs that won't be tuned belong as prose in the artifact body (often a `# Criteria` section). Inlining keeps the artifact honest about what's actually configurable.

Example: a car-search pipeline with `<$20k, <150k mi, dry states, body-on-frame` is better expressed as a `# Criteria` block in the data artifact than as four `params:` keys nobody will override.

### 4. Write the plan file

Produce `<name>-plan.md` in the artifact root. The plan is the **execution and wiring** document — it says which artifacts to run and how their outputs feed into each other. Artifact creation (ARTIFACT.md scaffolding) is handled separately by `create-plan-artifacts`.

Each step uses `Run @<artifact-dir>` and wires inputs with `@` refs.

**Every step must specify:**
- **Run @artifact-dir** — which artifact to execute
- **Why** — one sentence explaining this step's role in the analysis
- **Params** — override values (or omit if the artifact has no params or defaults are fine)
- **Inputs** — `@` refs wiring upstream outputs (or "none" for leaf nodes)
- **Output** — `@` ref to the expected output path + description of what the output contains

See `../examples/bushwick-buy-vs-rent.md` for a full 6-step plan, and `../examples/car-search.md` for a plan with per-item outputs and a `# Criteria` block in the data artifact.

**Every plan must include a `## Run file` section** describing the run-log lifecycle. The run file is created ONLY when the plan itself is executed (i.e., when the user prompts Claude with `@<plan>-plan.md`) — not by `/artifact plan`, not by `/artifact create-plan-artifacts`, and not by `/artifact create`. Those subcommands produce recipes and single-artifact outputs; they do not constitute "a run of the plan." The plan's `## Run file` section is therefore written for the future executor, not for any `/artifact` subcommand. It must instruct:

1. **Scaffold**: when the plan starts executing, create `runs/<YYYY-MM-DD-HHMM>-<plan-name>-run.md` (sibling to the plan file) with frontmatter (`plan:`, `started:`, `status: in_progress`, `plan_sha:`, `reused_artifacts: []`) and a `## Progress` table with one row per step plus an empty `## Log` section.
2. **Update**: after each `Run @<artifact>` step, append a `### <artifact> — <timestamp>` log entry (Status, Outputs, Issues, Handoff) and flip that row's Status in the Progress table.
3. **Close**: when the terminal artifact finishes, set frontmatter `status: completed`.
4. **Reuse**: `plan_sha` is `git hash-object <plan-name>-plan.md`. If a prior run in `runs/` has the same `plan_sha` and upstream outputs are unchanged, offer to reuse its outputs instead of re-executing.

**Frontmatter for Run file (embed in plan.md):**

```yaml
---
plan: <name>-plan.md
started: <ISO 8601 local time>
status: in_progress      # in_progress | completed | aborted
plan_sha: <chars>
reused_artifacts: []     # list of artifact names whose output was reused from a prior run
---
```

**Body template:**

```markdown
# Run — <YYYY-MM-DD-HHMM>

## Progress

| # | Artifact | Status | Output Date | Notes |
|---|----------|--------|-------------|-------|
| 1 | 0-foo   | —      | —           |       |
| 2 | 1-bar   | —      | —           |       |
| ... | ...    | —      | —           |       |

## Log

(append one entry per artifact as it completes)
```

The Progress table has one row per artifact in the plan, in execution order. Status starts blank, transitions to `done | failed | partial | reused (<date>)` as `create` runs each artifact. Notes is free-form (e.g., file counts, salient outputs).

**Reuse semantics.** Before `create` runs an artifact, it checks: did a prior run produce output for this artifact AND is `plan_sha` unchanged AND have the upstream inputs not changed? If yes, ask the user whether to reuse. If reused, append the artifact name to `reused_artifacts` and mark the row `reused (<date>)`.

See `../examples/car-search.md` §"Run file" for the exact frontmatter and table shape to reproduce verbatim in the plan.

### 5. Iterate with the user

Ask: Does this decomposition make sense? Missing nodes? Too specific?

## What happens next

After the plan is approved write it as <plan-name>-plan.md.
