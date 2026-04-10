---
name: artifact-create
description: "Create a single reproducible artifact: write ARTIFACT.md recipe. Use when user says 'save as artifact', 'make this reproducible', '/artifact create', or when called by artifact-plan-artifacts for each plan step."
user-invocable: true
---

# artifact-create

Create a single artifact — write the recipe.

Read the parent skill at `../SKILL.md` for artifact structure, DIKW prefixes, and design principles.

## When to use

- User says "save as artifact" or "make this reproducible"
- The session produced a valuable output worth persisting

## Design principle: Self-contained and generic

Each artifact must be **self-contained** — it describes what kind of inputs it expects (shape, format, columns), never where those inputs come from. No `@` references to other artifacts in ARTIFACT.md. Wiring (which artifact feeds which) lives in the plan file, not in individual artifacts.

Apply the **Lego Test**: each artifact is a generic primitive, reusable beyond the specific question that spawned it. Specifics go in params.

## Agent workflow

### 1. Identify what to capture

What's the primary output? What inputs fed it? Separate **entities** from conversational work.

### 2. Assign numeric DIKW prefix

- **0x** (Data) — raw, close to source
- **1x** (Info) — aggregated, filtered, derived
- **2x** (Knowledge) — patterns, analysis, models
- **3x** (Wisdom) — decisions, recommendations

Pick the next available number. Naming: `<prefix>-<lowercase-hyphenated>` (e.g., `00-daily-weather`).

### 3. Write ARTIFACT.md

YAML frontmatter declares the interface, markdown body is the recipe.

```markdown
---
name: 00-streeteasy-listings
description: NYC apartment listings from StreetEasy for a given zip code
params:
  zip_code:
    desc: NYC zip code to search
    default: "11206"
  max_listings:
    desc: Maximum number of listings to fetch
    default: 50
outputs:
  streeteasy_listings.csv:
    desc: "One row per listing: address, price, sqft, bedrooms, bathrooms, date_listed"
---

# Goal

Fetch current apartment listings from StreetEasy for a target NYC zip code.

# Steps

1. Navigate to StreetEasy search filtered by `zip_code` parameter.
2. Scrape all listing cards up to `max_listings`.
3. Normalize data: strip $, convert sqft to int, parse dates to ISO 8601.
4. Write tidy CSV to `out/<date>/streeteasy_listings.csv`.

# Output

Create these files in `out/<date>/`:
- `streeteasy_listings.csv` — one row per listing, columns: address, price, sqft, bedrooms, bathrooms, date_listed
- `streeteasy_listings.md` — generation log sidecar for every output

# Output Log Format

The sidecar `streeteasy_listings.md` must have:
- **YAML frontmatter**: params used, timestamp, model, sha256 hash of the output file
- **Markdown body**: free-form generation log — what happened during this run:
  - Data source and API/scrape method used
  - Number of listings found vs expected
  - Any errors, retries, or rate limits hit
  - Data quality notes (missing fields, outliers filtered, etc.)
```

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
1. Read `@00-company-criteria/out/<date>/company-criteria.md` for tier definitions.
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

### 4. Execute the recipe

Run the recipe to produce outputs:
1. Create `out/<today>/` directory (YYYY-MM-DD format)
2. Write the output file(s)
3. Write the sidecar `.md` for each output:
   - YAML frontmatter: `params`, `timestamp`, `model`, `sha256`
   - Markdown body: generation log as described in ARTIFACT.md's Output Log Format section

### 5. Report

```
Created artifact: 00-streeteasy-listings/
  ├── ARTIFACT.md          (recipe)
  └── out/2026-04-08/
      ├── streeteasy_listings.csv    (47 rows)
      └── streeteasy_listings.md     (generation log)
```

## Edge cases

- **Multiple outputs**: List all in `outputs:` frontmatter. Each gets its own sidecar.
- **No deterministic gen possible**: The ARTIFACT.md recipe IS the gen script. Execute conversationally.
- **Uploaded files**: Ask whether to wrap as a data artifact or reference as external input.
- **Called from plan-artifacts**: Params, inputs, and output log instructions come from the plan step. Use them directly.
