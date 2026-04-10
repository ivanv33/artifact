---
name: artifact-plan
description: "Decompose an ambiguous objective into a DAG of reusable DIKW artifacts and write an executable plan.md file. Use when user says 'plan artifacts for X', has a broad goal needing decomposition, or wants to design an artifact chain before creating anything. This command produces the plan only — it does NOT create artifact directories or outputs."
user-invocable: true
---

# artifact-plan

Transform an ambiguous objective into an executable plan — a markdown file with numbered steps that Claude can follow to create a chain of artifacts.

**This is a conversational subcommand.** Work back and forth with the user, starting with open questions and outline, before writing the plan.

**This command produces the plan only.** It does NOT create artifact directories or outputs. Use `/artifact plan-artifacts` after to create everything.

Read the parent skill at `../SKILL.md` for artifact structure, DIKW prefixes, and `@` reference syntax.

## Agent workflow

### 1. Identify the terminal artifact

What is the final decision or insight? Usually `2x` (knowledge) or `3x` (wisdom).

### 2. Reverse-engineer the lineage

Work backward: what data does the terminal need? Each dependency becomes a node.

**Always save raw data as an artifact.** Every decomposition starts with data — the ground truth that everything else builds on.

**The DIKW layers are a progression from truth to judgment:**

- **Data (0x)** — Raw facts. Downloaded, scraped, or imported. Close to the source, no opinions. Always worth saving — this is the ground truth you can always go back to. Example: `00-weather` downloads a weather CSV. `00-rental-listings` scrapes StreetEasy.
- **Info (1x)** — Derivative of data, still close to truth. Filtered, joined, aggregated, tagged — but not yet making predictions. Example: `10-passover-weather` tags weather rows by Hebrew calendar dates. `10-buy-vs-rent-costs` joins listings + rates into a cost comparison. Only create info artifacts when the derived dataset is reusable on its own.
- **Knowledge (2x)** — Prediction models built from data and info. This is where the heavy thinking happens — write a Python script that reads data/info, applies domain logic, computes statistics, builds models. Example: `20-passover-rain-verdict` writes a script that reads weather CSV, uses a Hebrew calendar lib, runs Fisher exact test, produces a statistical verdict.
- **Wisdom (3x)** — Conclusions and decisions using knowledge, info, and data. Synthesizes the numbers with qualitative factors into actionable recommendations. Example: `30-housing-decision` reads the analysis and produces "buy if X, rent if Y."

**Don't over-decompose.** If intermediate processing is only useful as a stepping stone (not reusable on its own), fold it into the downstream artifact's script. The test: **would someone reuse this intermediate artifact independently?** If not, it's a step inside a script, not a separate artifact.

**Example — "Is it always rainy on Passover in NYC?"**
- `00-weather` (data) — download 10 years of NYC daily weather. Generic, reusable for any weather question.
- `20-passover-rain-verdict` (knowledge) — writes a Python script that reads the weather CSV, uses `pyluach` to find Passover dates, tags target vs baseline days, runs Fisher exact test, computes odds ratio, writes a markdown verdict with statistics.

No info layer needed here — the tagging and stats are steps inside the knowledge script, not separate reusable datasets.

### 3. Apply the Lego Test

Each artifact must be a **generic primitive** — reusable beyond this specific question.

- **DO**: `00-weather` with `location` and `date_range` params
- **DON'T**: `00-passover-weather` (too specific — Passover logic belongs in the knowledge artifact)
- **DO**: `00-rental-listings` with `neighborhood` param
- **DON'T**: `00-bushwick-rentals` (too specific)

Specifics go in `params:` defaults, not the artifact name.

### 4. Write the plan file

Produce `<name>-plan.md` in the artifact root. The plan is the **execution and wiring** document — it says which artifacts to run and how their outputs feed into each other. Artifact creation (ARTIFACT.md scaffolding) is handled separately by `plan-artifacts`.

Each step uses `Run @<artifact-dir>` and wires inputs with `@` refs:

```markdown
# Bushwick Buy vs. Rent Analysis

Determine whether it is cheaper to buy or rent in Bushwick right now.

## Steps

1. **Run @00-rental-listings** — Get current Bushwick rental market data to establish baseline rent levels.
   Params: neighborhood=Bushwick, borough=Brooklyn, bedrooms=[1,2], date_range=last_90_days
   Inputs: none
   Output: @00-rental-listings/out/<date>/rental_listings.csv — one row per listing: address, price, sqft, bedrooms, bathrooms, date_listed

2. **Run @01-sale-listings** — Get current Bushwick sale prices to estimate purchase costs.
   Params: neighborhood=Bushwick, borough=Brooklyn, property_type=[condo,coop], date_range=last_90_days
   Inputs: none
   Output: @01-sale-listings/out/<date>/sale_listings.csv — one row per listing: address, price, sqft, bedrooms, bathrooms, hoa_monthly, date_listed

3. **Run @02-mortgage-rates** — Get current rates to compute monthly mortgage payments.
   Params: date=latest, loan_types=[30yr_fixed,15yr_fixed,5_1_arm]
   Inputs: none
   Output: @02-mortgage-rates/out/<date>/mortgage_rates.csv — columns: rate_type, rate_pct, points, date

4. **Run @10-buy-vs-rent-costs** — Combine listings and rates into an apples-to-apples annual cost comparison.
   Params: down_payment_pct=20, holding_period_years=7, annual_rent_growth=0.03, discount_rate=0.05
   Inputs:
     - @00-rental-listings/out/<date>/rental_listings.csv
     - @01-sale-listings/out/<date>/sale_listings.csv
     - @02-mortgage-rates/out/<date>/mortgage_rates.csv
   Output: @10-buy-vs-rent-costs/out/<date>/cost_comparison.csv — annual costs for buy vs rent by year, cumulative totals, NPV difference

5. **Run @20-buy-vs-rent-analysis** — Find breakeven year and stress-test assumptions to see how robust the conclusion is.
   Params: none
   Inputs: @10-buy-vs-rent-costs/out/<date>/cost_comparison.csv
   Output: @20-buy-vs-rent-analysis/out/<date>/buy_vs_rent_analysis.md — breakeven year, sensitivity tables (rate ±1%, appreciation ±2%, holding 5/7/10yr), neighborhood risk factors

6. **Run @30-housing-decision** — Synthesize numbers + lifestyle factors into an actionable recommendation.
   Params: none
   Inputs: @20-buy-vs-rent-analysis/out/<date>/buy_vs_rent_analysis.md
   Output: @30-housing-decision/out/<date>/housing_decision.md — "buy if X, rent if Y" recommendation with explicit assumptions and confidence level
```

**Every step must specify:**
- **Run @artifact-dir** — which artifact to execute
- **Why** — one sentence explaining this step's role in the analysis
- **Params** — override values (or omit to use ARTIFACT.md defaults)
- **Inputs** — `@` refs wiring upstream outputs (or "none" for leaf nodes)
- **Output** — `@` ref to the expected output path + description of what the output contains

### 5. Iterate with the user

Ask: Does this decomposition make sense? Missing nodes? Too specific?

## What happens next

After the plan is approved:
1. User runs `/artifact plan-artifacts` with this plan
2. That creates all artifact directories, ARTIFACT.md files, and outputs
3. The plan.md gets updated with concrete `@` paths to real outputs
