# Example: Should I buy or rent in Bushwick?

A 6-artifact pipeline that touches all four DIKW layers. Demonstrates when an info layer is justified (the cost-comparison CSV is independently reusable across the analysis and decision steps).

## Decomposition

| Tier | Artifact | Why |
|------|----------|-----|
| Data | `0-rental-listings` | Scrape current rentals — generic, takes a `neighborhood` param |
| Data | `0-sale-listings` | Scrape for-sale listings — same shape, different feed |
| Data | `0-mortgage-rates` | Fetch current PMMS rates |
| Info | `1-buy-vs-rent-costs` | Join the three datasets into an annual cost comparison CSV — reusable as input to multiple analyses |
| Knowledge | `2-buy-vs-rent-analysis` | Find breakeven year, run sensitivities |
| Wisdom | `3-housing-decision` | Synthesize numbers + lifestyle into "buy if X, rent if Y" |

## Plan file (excerpt)

```markdown
# Bushwick Buy vs. Rent Analysis

Determine whether it is cheaper to buy or rent in Bushwick right now.

## Steps

1. **Run @0-rental-listings** — Get current Bushwick rental market data to establish baseline rent levels.
   Params: neighborhood=Bushwick, borough=Brooklyn, bedrooms=[1,2], date_range=last_9_days
   Inputs: none
   Output: @0-rental-listings/out/<date>/rental_listings.csv — one row per listing: address, price, sqft, bedrooms, bathrooms, date_listed

2. **Run @0-sale-listings** — Get current Bushwick sale prices to estimate purchase costs.
   Params: neighborhood=Bushwick, borough=Brooklyn, property_type=[condo,coop], date_range=last_9_days
   Inputs: none
   Output: @0-sale-listings/out/<date>/sale_listings.csv — one row per listing: address, price, sqft, bedrooms, bathrooms, hoa_monthly, date_listed

3. **Run @0-mortgage-rates** — Get current rates to compute monthly mortgage payments.
   Params: date=latest, loan_types=[30yr_fixed,15yr_fixed,5_1_arm]
   Inputs: none
   Output: @0-mortgage-rates/out/<date>/mortgage_rates.csv — columns: rate_type, rate_pct, points, date

4. **Run @1-buy-vs-rent-costs** — Combine listings and rates into an apples-to-apples annual cost comparison.
   Params: down_payment_pct=20, holding_period_years=7, annual_rent_growth=0.03, discount_rate=0.05
   Inputs:
     - @0-rental-listings/out/<date>/rental_listings.csv
     - @0-sale-listings/out/<date>/sale_listings.csv
     - @0-mortgage-rates/out/<date>/mortgage_rates.csv
   Output: @1-buy-vs-rent-costs/out/<date>/cost_comparison.csv — annual costs for buy vs rent by year, cumulative totals, NPV difference

5. **Run @2-buy-vs-rent-analysis** — Find breakeven year and stress-test assumptions.
   Inputs: @1-buy-vs-rent-costs/out/<date>/cost_comparison.csv
   Output: @2-buy-vs-rent-analysis/out/<date>/buy_vs_rent_analysis.md — breakeven, sensitivity tables, neighborhood risk factors

6. **Run @3-housing-decision** — Synthesize numbers + lifestyle factors into an actionable recommendation.
   Inputs: @2-buy-vs-rent-analysis/out/<date>/buy_vs_rent_analysis.md
   Output: @3-housing-decision/out/<date>/housing_decision.md — "buy if X, rent if Y" with assumptions and confidence
```

## Artifact list (`bushwick-buy-vs-rent-plan-artifacts.md`)

```markdown
# Bushwick Buy vs. Rent — Artifact List

1. `/artifact create 0-rental-listings` — Scrape current rental listings for a neighborhood (params: neighborhood, borough, bedrooms, date_range; defaults: Bushwick, Brooklyn, [1,2], last_90_days). No upstream inputs — leaf node fetching from StreetEasy. Output: rental_listings.csv with one row per listing (address, price, sqft, bedrooms, bathrooms, date_listed).

2. `/artifact create 0-sale-listings` — ...

(... one paragraph per artifact, inputs described abstractly, no @ wiring)
```

## Params discipline

Note that `params:` is used for things that genuinely vary across runs (neighborhood, date range, holding period). Things like "use NPV not undiscounted totals" or "exclude listings under 400 sqft" stay as prose in the artifact body. Don't pad `params:` with everything that *could* be a knob.

## Why an info layer here (and not in the Passover example)?

The cost-comparison CSV at `1-buy-vs-rent-costs` is reusable: the analysis step (`2`) and the decision step (`3`) both consume it, and a different question ("what holding period maximizes ROI?") could consume it without touching `2`. That passes the Lego Test. In contrast, Passover-tagged weather is only useful for the one specific question, so it stays inline in the verdict script.
