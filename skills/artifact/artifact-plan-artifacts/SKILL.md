---
name: artifact-plan-artifacts
description: "Take an existing plan.md and scaffold all artifact directories with ARTIFACT.md recipes (no outputs). Use when user says 'create artifacts from this plan', 'scaffold the plan', or after /artifact plan has produced a plan.md file. Does NOT execute recipes — use /artifact create for that."
---

# artifact-plan-artifacts

Take an existing `<name>-plan.md` and scaffold all artifact directories with ARTIFACT.md recipes. Does NOT execute recipes or produce outputs — that happens via `/artifact create`.

Read the parent skill at `../SKILL.md` for artifact structure and conventions.
Read the create subskill at `../artifact-create/SKILL.md` for single-artifact creation workflow.

## Agent workflow

### 1. Read the plan

Parse `<name>-plan.md`. Extract each step's artifact name, params, inputs, output, and output log instructions.

### 2. Produce the artifact list

Write `<name>-plan-artifacts.md` — an ordered list of `/artifact create` commands derived from the plan:

Each item must include everything needed to create the artifact — description, params, inputs (described abstractly, NOT wired to specific artifacts), and outputs. Artifacts don't know about each other — they describe what kind of input they need. The wiring (which artifact feeds which) lives in the plan.md, not here.

```markdown
# Bushwick Buy vs. Rent — Artifact List

Derived from `bushwick-buy-vs-rent-plan.md`.

## Artifacts

1. `/artifact create 00-rental-listings` — Scrape current rental listings for a neighborhood (params: neighborhood, borough, bedrooms, date_range; defaults: Bushwick, Brooklyn, [1,2], last_90_days). No upstream inputs — leaf node fetching from StreetEasy. Output: rental_listings.csv with one row per listing (address, price, sqft, bedrooms, bathrooms, date_listed).

2. `/artifact create 01-sale-listings` — Scrape current for-sale listings for a neighborhood (params: neighborhood, borough, property_type, date_range; defaults: Bushwick, Brooklyn, [condo,coop], last_90_days). No upstream inputs — leaf node fetching from StreetEasy. Output: sale_listings.csv with one row per listing (address, price, sqft, bedrooms, bathrooms, hoa_monthly, date_listed).

3. `/artifact create 02-mortgage-rates` — Fetch current average mortgage rates by loan type (params: date, loan_types; defaults: latest, [30yr_fixed,15yr_fixed,5_1_arm]). No upstream inputs — leaf node fetching from Freddie Mac PMMS. Output: mortgage_rates.csv (rate_type, rate_pct, points, date).

4. `/artifact create 10-buy-vs-rent-costs` — Compute side-by-side annual cost comparison for buying vs renting (params: down_payment_pct=20, holding_period_years=7, annual_rent_growth=0.03, discount_rate=0.05). Inputs: a rental listings CSV, a sale listings CSV, and a mortgage rates CSV. Output: cost_comparison.csv with annual costs for both scenarios and NPV.

5. `/artifact create 20-buy-vs-rent-analysis` — Analyze breakeven year, run sensitivity on appreciation rate (±2%), mortgage rate (±1%), and holding period (5/7/10yr), flag neighborhood-specific risks. Input: a buy-vs-rent cost comparison CSV. Output: buy_vs_rent_analysis.md with breakeven, sensitivity tables, and risk factors.

6. `/artifact create 30-housing-decision` — Synthesize a "buy if X, rent if Y" recommendation weighing financial breakeven against lifestyle factors (flexibility, maintenance burden, equity vs liquidity). Input: a buy-vs-rent analysis report. Output: housing_decision.md with explicit assumptions and confidence level.
```

### 3. Scaffold each artifact

Walk through the list in topological order (leaves first). For each artifact:

1. Create the directory `XX-name/`
2. Write `ARTIFACT.md` with:
   - YAML frontmatter: name, description, inputs (from plan), params (from plan), outputs (from plan)
   - Markdown body: recipe derived from the plan step — Goal, Steps, Output, Output Log Format
3. Optionally create `scripts/` if the plan step implies deterministic execution

**Do NOT execute the recipe or produce `out/<date>/` outputs.** This step only creates the scaffolding. Execution happens later via `/artifact create` for individual artifacts.

### 4. Update the plan

After all artifact dirs are scaffolded, update `<name>-plan.md`:
- Add a `## Status` section noting which artifact dirs were created

### 5. Report

```
Plan: bushwick-buy-vs-rent-plan.md
Scaffolded 6 artifacts:
  [1/6] 00-rental-listings/ARTIFACT.md        ✓
  [2/6] 01-sale-listings/ARTIFACT.md           ✓
  [3/6] 02-mortgage-rates/ARTIFACT.md          ✓
  [4/6] 10-buy-vs-rent-costs/ARTIFACT.md       ✓
  [5/6] 20-buy-vs-rent-analysis/ARTIFACT.md    ✓
  [6/6] 30-housing-decision/ARTIFACT.md        ✓

Run @bushwick-buy-vs-rent-plan.md` to execute individual artifacts.
```
