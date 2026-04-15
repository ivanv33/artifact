---
name: artifact
description: "Create and manage reproducible DIKW artifacts. Three commands: /artifact plan (decompose a goal into an artifact DAG and write an executable plan.md), /artifact create-plan-artifacts (take a plan.md and create all artifacts with outputs), /artifact create (create a single artifact with ARTIFACT.md recipe and out/<date>/ outputs). Use this skill whenever the user says /artifact, 'save as artifact', 'make this reproducible', 'plan artifacts for X', or references artifacts, ARTIFACT.md, the DIKW system, or artifact pipelines."
user-invocable: true
argument-hint: "<plan|create-plan-artifacts|create> [goal or artifact name]"
---

# Artifact Manager

An **artifact** is the product — the CSV, the report, the dataset in `out/`. **ARTIFACT.md** is the recipe — how to make it. **Plans** are executable markdown — English-language algorithms with numbered steps that Claude follows.

**Key principle:** Prefer writing ARTIFACT.md over creating scripts. The recipe IS the artifact definition. Scripts are an optimization you reach for when deterministic execution is needed — not the default.

---

## Three Commands

| Command | What it does | Produces |
|---------|-------------|----------|
| **plan** | Decompose goal into artifact DAG | `<name>-plan.md` |
| **create-plan-artifacts** | Take plan.md → scaffold all artifact dirs | `<name>-plan-artifacts.md` + artifact dirs with ARTIFACT.md (NO outputs) |
| **create** | Create a single artifact (with outputs) | `XX-name/ARTIFACT.md` + `out/<date>/<output>` + `out/<date>/receipts/<output>.<ext>.md` |

## Artifact Structure

```
0-daily-weather/
├── ARTIFACT.md          # Recipe: YAML frontmatter (inputs, params, outputs) + markdown prompt
├── .gitignore           # out/* except out/latest  (scaffolded once, never committed output history)
├── scripts/             # Optional: deterministic helpers (.py, .sh)
└── out/
    └── 2026-04-08/
        ├── daily_weather.csv           # The artifact (output file)
        └── receipts/
            └── daily_weather.csv.md    # Receipt: YAML header + generation log
```

**`.gitignore` policy.** Each artifact dir contains a scaffolded `.gitignore`:

```
out/*
!out/latest
```

Dated output dirs stay local. The `!out/latest` line is a **reservation** — if a user chooses to create `out/latest` themselves (as a symlink or a curated copy of one run's outputs), it will be tracked by git. The skill never creates `out/latest` and never writes dated subdirectories eagerly — only the `.gitignore` is scaffolded upfront. Dated output dirs come into existence the first time `/artifact create` runs.

A pipeline of artifacts may also have a **run file** at `runs/<YYYY-MM-DD-HHMM>-<plan-name>-run.md` that tracks a single execution of the plan — frontmatter with status + plan_sha + reused_artifacts, a progress table, and append-only log entries. `<YYYY-MM-DD-HHMM>` is **local time** (not UTC) — this is the single source of truth for the timestamp convention; subskills and examples inherit it. See `artifact-plan/SKILL.md`.

## Numeric DIKW Prefix

Flat directory structure — layer encoded in the prefix:

| Prefix | Layer     | What it is | Examples |
|--------|-----------|-----------|----------|
| `0-`   | Data      | Raw facts, ground truth — downloaded, scraped, imported | `0-weather`, `0-rental-listings` |
| `1-`   | Info      | Derivative of data, still close to truth — filtered, joined, tagged | `1-buy-vs-rent-costs` |
| `2-`   | Knowledge | Prediction models built from data/info — scripts that compute stats, find patterns | `2-passover-rain-verdict` |
| `3-`   | Wisdom    | Conclusions using knowledge + info + data — actionable decisions | `3-housing-decision` |

## ARTIFACT.md Anatomy

YAML frontmatter declares the interface. Markdown body is the agent prompt recipe.

```yaml
---
name: 0-streeteasy-listings
description: NYC apartment listings from StreetEasy for a given zip code
params:
  zip_code:
    desc: NYC zip code to search
    default: "11206"
outputs:
  streeteasy_listings.csv:
    desc: "One row per listing: address, price, sqft, bedrooms, bathrooms, date_listed"
---
```

**Frontmatter fields:**
- `name` — artifact directory name (with numeric prefix)
- `description` — what this artifact is
- `inputs` — upstream artifact dependencies, each with `desc` (include shape info)
- `params` — tunable parameters, each with `desc` and `default`. **Use sparingly** — only when the value is genuinely variable across runs (zip code, date range, from/to). Hardcoded selection criteria, scoring weights, or fixed thresholds belong as prose in the body (often a `# Criteria` section), not in `params:`.
- `outputs` — named output files, each with `desc`

**Body sections:**
- `# Goal` — what and why
- `# Criteria` *(optional)* — fixed inputs that aren't tunable params: budget caps, allowed regions, scoring weights
- `# Steps` — numbered list describing how to produce the output. Reference inputs by filename only — no `@` paths (wiring lives in plan files)
- `# Output` — list files to create in `out/<date>/`, plus receipts in `out/<date>/receipts/`
- `# Output Log Format` — what the receipt should contain

## `@` Reference Syntax

Reference another artifact's output: `@<artifact-dir>/out/<date>/filename`

- `@0-daily-weather/out/<date>/daily_weather.csv`
- `<date>` = a specific date like `2026-04-08`

Used in **plan files** to wire artifacts together. Never in ARTIFACT.md — artifacts are self-contained.

## Output Receipt

**Every output file MUST have a paired receipt** in the sibling `receipts/` directory. Naming pattern: the output's full filename (extension included) with `.md` appended.

| Output file (`out/<date>/…`) | Receipt (`out/<date>/receipts/…`) |
|------------------------------|-----------------------------------|
| `daily_weather.csv`          | `daily_weather.csv.md`            |
| `toyota.md`                  | `toyota.md.md`                    |
| `cost_comparison.parquet`    | `cost_comparison.parquet.md`      |

Keeping receipts in a separate `receipts/` subdir keeps the published outputs clean while still binding each one to a provenance record by filename.

**Required frontmatter:**
```yaml
---
timestamp: <ISO 8601>
model: <model id used to generate>
params: <map of param values used; omit if artifact has no params>
artifact_sha: <git blob sha of ARTIFACT.md — `git hash-object ARTIFACT.md`>
---
```

The `artifact_sha` binds this receipt to the exact version of the recipe that produced the output. A later run with a modified ARTIFACT.md will have a different sha; this is the integrity anchor.

**Body** is a free-form generation log: data sources hit, API calls / scrape methods, errors, retries, rate limits, data quality notes, exclusions and reasoning, methodology weights (for ranked outputs).

The main output is what you publish; the receipt is the audit trail.

## Examples

Worked examples live in `examples/`:

- `examples/passover-rain.md` — minimal 2-artifact pipeline (data + knowledge), PEP 723 script
- `examples/bushwick-buy-vs-rent.md` — 6-artifact pipeline showing data → info → knowledge → wisdom layering
- `examples/car-search.md` — multi-make car search; demonstrates the run file, receipts on every output, `# Criteria` section for fixed inputs, and per-item outputs scaling to dozens of files

## Subcommand Dispatch

| User says | Subskill |
|-----------|----------|
| "plan artifacts for X", "decompose this goal" | `artifact-plan` |
| "create artifacts from this plan", "run the plan" | `artifact-create-plan-artifacts` |
| "save as artifact", "make this reproducible" | `artifact-create` |

## Design Principles

- **Entities, not tasks**: Artifacts represent what (a dataset, analysis, decision), not how (a session, step).
- **Lego Test**: Each artifact is a generic primitive — reusable. Specifics go in params.
- **Tidy data**: One file per concept, one row per observation, one column per variable.
- **Prefer recipes over scripts**: Write ARTIFACT.md first. Only create scripts/ when needed.
