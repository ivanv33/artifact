---
name: artifact-create
description: "Create a single reproducible artifact: write the ARTIFACT.md recipe, then execute it to produce outputs + receipts under out/<date>/. Use when user says 'save as artifact', '/artifact create', or when called by artifact-create-plan-artifacts for each plan step."
user-invocable: true
---

# artifact-create

Create a single artifact — write the recipe.

Read the parent skill at `../SKILL.md` for artifact structure, DIKW prefixes, and design principles.

## Design principle: Self-contained and generic

Each artifact must be **self-contained** — it describes what kind of inputs it expects (shape, format, columns), never where those inputs come from. No `@` references to other artifacts in ARTIFACT.md. Wiring (which artifact feeds which) lives in the plan file, not in individual artifacts.

Apply the **Lego Test**: each artifact is a generic primitive, reusable beyond the specific question that spawned it. Specifics go in params.

## Agent workflow

### 1. Identify what to capture

What's the primary output? What inputs fed it? Separate **entities** from conversational work.

### 2. Assign numeric DIKW prefix

- **0-** (Data) — raw, close to source
- **1-** (Info) — aggregated, filtered, derived
- **2-** (Knowledge) — patterns, analysis, models
- **3-** (Wisdom) — decisions, recommendations

Pick the next available number. Naming: `<prefix>-<lowercase-hyphenated>` (e.g., `0-daily-weather`).

### 3. Write ARTIFACT.md

YAML frontmatter declares the interface, markdown body is the recipe.

```markdown
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

# Goal

Fetch current apartment listings from StreetEasy for a target NYC zip code.

# Steps

1. Navigate to StreetEasy search filtered by `zip_code` parameter.
2. Scrape all listing cards (no pagination cap — fetch everything).
3. Normalize data: strip $, convert sqft to int, parse dates to ISO 8601.
4. Write tidy CSV to `out/<date>/streeteasy_listings.csv`.

# Output

Create these files:
- `out/<date>/streeteasy_listings.csv` — one row per listing, columns: address, price, sqft, bedrooms, bathrooms, date_listed
- `out/<date>/receipts/streeteasy_listings.csv.md` — receipt (mandatory)

# Output Log Format

The receipt `out/<date>/receipts/streeteasy_listings.csv.md` must have:
- **YAML frontmatter**: timestamp, model, params used, artifact_sha (`git hash-object ARTIFACT.md`)
- **Markdown body**: free-form generation log — what happened during this run:
  - Data source and API/scrape method used
  - Number of listings found vs expected
  - Any errors, retries, or rate limits hit
  - Data quality notes (missing fields, outliers filtered, etc.)
```

**Use `params:` sparingly.** Only include keys whose value is genuinely variable across runs (zip code, date range, region). Hardcoded selection criteria, scoring weights, or fixed thresholds belong as prose in the body — typically a `# Criteria` section. The example above declares `zip_code` because it's the natural knob; it does NOT add `max_listings`, `min_price`, etc. as params just because they could be tunable. Inlining keeps the artifact honest about what's actually configurable.

For artifacts with upstream inputs, add `inputs:` to the frontmatter. Keys are **filenames only** (no paths), values describe what shape of data is expected:

```yaml
inputs:
  daily_weather.csv:
    desc: "Historical daily weather — columns: date, precipitation_mm, high_f, low_f, conditions"
```

Steps reference inputs generically (e.g., "Read the daily weather input") — never use `@` references to specific artifacts. The plan file handles wiring.

**Anti-pattern — leaking wiring into the artifact:**

```yaml
# BAD: input desc is vague, doesn't describe expected shape
inputs:
  company-criteria.md:
    desc: "Selection criteria with tier definitions, inclusion/exclusion rules"
```
```markdown
# BAD: step references a specific artifact path
1. Read `@0-company-criteria/out/<date>/company-criteria.md` for tier definitions.
```

```yaml
# GOOD: filename only, desc says what it expects
inputs:
  company-criteria.md:
    desc: "Company selection criteria — tier definitions, sector coverage, inclusion/exclusion rules"
```
```markdown
# GOOD: step references input by name, no path
1. Read company-criteria.md for tier definitions and inclusion/exclusion rules.
```

The artifact doesn't know or care where the criteria came from. It just needs a file called `company-criteria.md` with selection criteria.

**Prefer ARTIFACT.md over scripts.** Only create `scripts/` when you need deterministic, repeatable execution. When you do create scripts:

- **Scripts must be self-contained.** Use PEP 723 inline dependency metadata so they run with `uv run` without any external setup:

```python
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyluach", "scipy"]
# ///
"""Analyze Passover rain patterns from daily weather data."""
import sys
# ... rest of script
```

- No `requirements.txt` — deps live in the script header
- Scripts should accept input file paths as CLI arguments, not hardcode them
- Run with: `uv run scripts/analyze.py <input.csv>`

### 4. Scaffold the artifact directory

If this is a first-time scaffold (no existing `.gitignore`), write `.gitignore` at the artifact root with:

```
out/*
!out/latest
```

Do **not** create `out/latest`, `out/`, or any dated output directory at scaffold time. Dated output dirs come into existence only when step 5 runs. `out/latest` is never created by the skill — the `!out/latest` line in `.gitignore` is a reservation in case the user chooses to curate one later.

### 5. Execute the recipe

Run the recipe to produce outputs:

1. Create `out/<today>/` and `out/<today>/receipts/` (YYYY-MM-DD format).
2. Write the output file(s) under `out/<today>/`.
3. Write a **mandatory** receipt for **every** output under `out/<today>/receipts/`. Naming pattern: append `.md` to the full output filename, extension included.

   | Output file (`out/<date>/…`) | Receipt (`out/<date>/receipts/…`) |
   |------------------------------|-----------------------------------|
   | `streeteasy_listings.csv`    | `streeteasy_listings.csv.md`      |
   | `toyota.md`                  | `toyota.md.md`                    |
   | `report.parquet`             | `report.parquet.md`               |

   Required receipt frontmatter:
   ```yaml
   ---
   timestamp: <ISO 8601>
   model: <model id>
   params: <map of values, or omit if no params>
   artifact_sha: <git blob sha of ARTIFACT.md — `git hash-object ARTIFACT.md`>
   ---
   ```
   Body: free-form generation log per the artifact's Output Log Format section.

**Do not create `out/latest`.** The skill never writes a `latest` symlink or directory — `!out/latest` in `.gitignore` is just a reservation.

### 6. Report

```
Created artifact: 0-streeteasy-listings/
  ├── ARTIFACT.md                       (recipe)
  ├── .gitignore                        (out/* except out/latest)
  └── out/
      └── 2026-04-08/
          ├── streeteasy_listings.csv   (47 rows)
          └── receipts/
              └── streeteasy_listings.csv.md
```

## Edge cases

- **Multiple outputs**: List all in `outputs:` frontmatter. Each gets its own `receipts/<output>.<ext>.md`.
- **Per-item outputs (e.g. one file per listing)**: The `outputs:` frontmatter describes the filename pattern (e.g. `"<vehicle-id>.md"`). Each emitted file still gets its own receipt under `receipts/` using the same `.md` / `.md.md` rule.
- **No deterministic gen possible**: The ARTIFACT.md recipe IS the gen script. Execute conversationally.
- **Uploaded files**: Ask whether to wrap as a data artifact or reference as external input.
- **Called from create-plan-artifacts**: Params, inputs, and output log instructions come from the plan step. Use them directly.
- **Run files**: `/artifact create` does NOT create, update, or look for a run file. Run files exist only when the plan is executed end-to-end (by prompting Claude with `@<plan>-plan.md`), which is outside this skill. A single `/artifact create` invocation is not "a run of the plan" — it is one artifact being built.

See `../examples/car-search.md` for a worked example with per-item outputs, a `# Criteria` block, and a full run-file lifecycle.
