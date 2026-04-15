---
name: artifact-create-plan-artifacts
description: "Take an existing plan.md and scaffold all artifact directories with ARTIFACT.md recipes (no outputs, no run file). Use when user says 'create artifacts from this plan', 'scaffold the plan', or after /artifact plan has produced a plan.md file. Does NOT execute recipes — use /artifact create for that. Does NOT create a run file — run files are created only when the plan itself is executed (by prompting Claude with @<plan>.md), which is outside this skill."
user-invocable: true
---

# artifact-create-plan-artifacts

Take an existing `<name>-plan.md` and produce, in order:

1. Draft `<name>-plan-artifacts.md` — an ordered list of `/artifact create` calls derived from the plan. Iterate with the user until approved, then write it to disk.
2. Execute the artifact list (delegate to a subagent) to scaffold each artifact directory with `ARTIFACT.md` + `.gitignore`. Does NOT produce outputs.

**No run file is created here.** Run files (`runs/<YYYY-MM-DD-HHMM>-<plan-name>-run.md`) are never produced by any `/artifact` subcommand. They are only created when the plan itself is executed end-to-end — i.e., when the user prompts Claude with `@<plan>-plan.md`, causing Claude to follow the `## Run file` instructions embedded in the plan. `/artifact create-plan-artifacts` only scaffolds recipes; `/artifact create` only builds one artifact at a time. Neither constitutes "a run of the plan."

Read the parent skill at `../SKILL.md` for artifact structure and conventions.
Read the create subskill at `../artifact-create/SKILL.md` for single-artifact creation workflow.

## Agent workflow

### 1. Read the plan

Parse `<name>-plan.md`. Extract each step's artifact name, params, inputs, output, and output log instructions.

### 2. Draft the artifact list and confirm with the user

Draft `<name>-plan-artifacts.md` — an ordered list of `/artifact create` commands derived from the plan.

Each item must include everything needed to create the artifact — description, params, inputs (described abstractly, NOT wired to specific artifacts), and outputs. Artifacts don't know about each other — they describe what kind of input they need. The wiring (which artifact feeds which) lives in the plan.md, not here.

See `../examples/bushwick-buy-vs-rent.md` for the artifact-list format.

**Before writing the file to disk, show the draft list to the user and confirm:**

- The filename: `<name>-plan-artifacts.md`
- The ordered list of `/artifact create` calls with their descriptions/params/inputs/outputs

Only proceed to step 3 after the user approves. If they request changes, revise and re-confirm.

### 3. Execute the artifact list in a subagent

Once the list is approved, delegate execution to a subagent (e.g., via the `Agent` tool). Hand the subagent:

- The path to `<name>-plan-artifacts.md`
- The parent skill at `../SKILL.md` (for structure/conventions)
- Instructions to walk the list in topological order (leaves first) and, for each artifact:

  1. Create the directory `XX-name/`
  2. Write `ARTIFACT.md` with:
     - YAML frontmatter: name, description, inputs (from plan), params (from plan — only the genuinely variable ones), outputs (from plan)
     - Markdown body: recipe derived from the plan step — Goal, optional Criteria, Steps, Output, Output Log Format
  3. Write `.gitignore` at the artifact root with:
     ```
     out/*
     !out/latest
     ```
     This ensures dated output dirs stay local. `out/latest` is only a reserved name in the ignore rule — the skill never creates it.
  4. Optionally create `scripts/` if the plan step implies deterministic execution.

**The subagent MUST NOT execute recipes, pre-create `out/`, or produce any outputs.** It only creates scaffolding: `ARTIFACT.md`, `.gitignore`, and optionally `scripts/`. Execution happens later via `/artifact create` for individual artifacts — that step creates `out/<date>/` and `out/<date>/receipts/`. Neither step creates `out/latest`.


### 4. Update the plan

After all artifact dirs are scaffolded, update `<name>-plan.md`:
- Add a `## Status` section listing which artifact dirs were created.

### 5. Report

```
Plan: bushwick-buy-vs-rent-plan.md

Scaffolded 6 artifacts:
  [1/6] 0-rental-listings/ARTIFACT.md        ✓
  [2/6] 0-sale-listings/ARTIFACT.md          ✓
  [3/6] 0-mortgage-rates/ARTIFACT.md         ✓
  [4/6] 1-buy-vs-rent-costs/ARTIFACT.md      ✓
  [5/6] 2-buy-vs-rent-analysis/ARTIFACT.md   ✓
  [6/6] 3-housing-decision/ARTIFACT.md       ✓

No run file created — nothing has run yet.
Run /artifact create <artifact> to execute a single artifact, or
prompt Claude with @bushwick-buy-vs-rent-plan.md to execute the full plan
(the plan's own instructions will scaffold and update runs/<...>-run.md).
```
