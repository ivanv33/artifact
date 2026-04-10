---
name: artifact
description: "Create and manage reproducible DIKW artifacts. Three commands: /artifact plan (decompose a goal into an artifact DAG and write an executable plan.md), /artifact plan-artifacts (take a plan.md and create all artifacts with outputs), /artifact create (create a single artifact with ARTIFACT.md recipe and out/<date>/ outputs). Use this skill whenever the user says /artifact, 'save as artifact', 'make this reproducible', 'plan artifacts for X', or references artifacts, ARTIFACT.md, the DIKW system, or artifact pipelines."
user-invocable: true
argument-hint: "<plan|plan-artifacts|create> [goal or artifact name]"
---

# Artifact Manager

An **artifact** is the product — the CSV, the report, the dataset in `out/`. **ARTIFACT.md** is the recipe — how to make it. **Plans** are executable markdown — English-language algorithms with numbered steps that Claude follows.

**Key principle:** Prefer writing ARTIFACT.md over creating scripts. The recipe IS the artifact definition. Scripts are an optimization you reach for when deterministic execution is needed — not the default.

---

## Three Commands

| Command | What it does | Produces |
|---------|-------------|----------|
| **plan** | Decompose goal into artifact DAG | `<name>-plan.md` |
| **plan-artifacts** | Take plan.md → scaffold all artifact dirs | `<name>-plan-artifacts.md` + artifact dirs with ARTIFACT.md (NO outputs) |
| **create** | Create a single artifact (with outputs) | `XX-name/ARTIFACT.md` + `out/<date>/output` + `out/<date>/output.md` sidecar |

## Artifact Structure

```
00-daily-weather/
├── ARTIFACT.md          # Recipe: YAML frontmatter (inputs, params, outputs) + markdown prompt
├── scripts/             # Optional: deterministic helpers (.py, .sh)
└── out/
    └── 2026-04-08/
        ├── daily_weather.csv    # The artifact (output file)
        └── daily_weather.md     # Sidecar: YAML header (params, timestamp) + generation log
```

## Numeric DIKW Prefix

Flat directory structure — layer encoded in the prefix:

| Prefix | Layer     | What it is | Examples |
|--------|-----------|-----------|----------|
| `0x`   | Data      | Raw facts, ground truth — downloaded, scraped, imported | `00-weather`, `01-rental-listings` |
| `1x`   | Info      | Derivative of data, still close to truth — filtered, joined, tagged | `10-buy-vs-rent-costs` |
| `2x`   | Knowledge | Prediction models built from data/info — scripts that compute stats, find patterns | `20-passover-rain-verdict` |
| `3x`   | Wisdom    | Conclusions using knowledge + info + data — actionable decisions | `30-housing-decision` |

## ARTIFACT.md Anatomy

YAML frontmatter declares the interface. Markdown body is the agent prompt recipe.

```yaml
---
name: 00-streeteasy-listings
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
- `params` — tunable parameters, each with `desc` and `default`
- `outputs` — named output files, each with `desc`

**Body sections:**
- `# Goal` — what and why
- `# Steps` — numbered list describing how to produce the output. Reference inputs by filename only — no `@` paths (wiring lives in plan files)
- `# Output` — list files to create in `out/<date>/`, including the sidecar `.md`
- `# Output Log Format` — what the sidecar should contain

## `@` Reference Syntax

Reference another artifact's output: `@<artifact-dir>/out/<date>/filename`

- `@00-daily-weather/out/<date>/daily_weather.csv`
- `<date>` = a specific date like `2026-04-08`

Used in **plan files** to wire artifacts together. Never in ARTIFACT.md — artifacts are self-contained.

## Output Sidecar

Every output file gets a paired `.md` sidecar in the same `out/<date>/` directory:
- **YAML frontmatter**: params used, timestamp, model, sha256 hash
- **Markdown body**: free-form generation log — API calls, errors, retries, agent reasoning, data quality notes

## Subcommand Dispatch

| User says | Subskill |
|-----------|----------|
| "plan artifacts for X", "decompose this goal" | `artifact-plan` |
| "create artifacts from this plan", "run the plan" | `artifact-plan-artifacts` |
| "save as artifact", "make this reproducible" | `artifact-create` |

## Design Principles

- **Entities, not tasks**: Artifacts represent what (a dataset, analysis, decision), not how (a session, step).
- **Lego Test**: Each artifact is a generic primitive — reusable. Specifics go in params.
- **Tidy data**: One file per concept, one row per observation, one column per variable.
- **Prefer recipes over scripts**: Write ARTIFACT.md first. Only create scripts/ when needed.
