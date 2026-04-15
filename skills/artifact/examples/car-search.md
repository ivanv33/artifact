# Example: Used-truck market search

A multi-vehicle deal-hunting pipeline. Shows three patterns the simpler examples don't:

1. **A `# Criteria` block** for fixed inputs (budget cap, mileage cap, region) instead of pretending they're tunable params.
2. **Per-item outputs** — the deal-finder emits dozens of files (one per discovered vehicle), not a single CSV.
3. **A run-file lifecycle** — scaffolded and updated only when the plan itself is executed (by prompting Claude with `@<plan>.md`). No `/artifact` subcommand touches the run file.

A live execution of this pipeline lives at `/Users/poplar/mycontext/artifacts/car-search/` for readers who want to inspect real outputs.

## Important: the example is a pattern, not a prescription

This pipeline does **not** prescribe which vehicle makes to consider. The data artifact (`0-makes`) is responsible for *discovering* the makes worth searching given the criteria — it could surface Toyota and Lexus, or Ford and Jeep, or any other body-on-frame manufacturer that fits the budget. Downstream artifacts adapt to whatever makes Phase 1 returns.

When adapting this pattern to a different domain (laptops, cameras, apartments), the same shape applies: the data artifact discovers the candidates; downstream artifacts iterate over whatever it finds.

## Decomposition

| Tier | Artifact | Why |
|------|----------|-----|
| Data | `0-makes` | Discover makes that fit the criteria, then deep-dive each into a buyer's guide |
| Info | `1-online-resources` | For each discovered make, list the online resources (URLs, scraping notes) where listings can be monitored |
| Knowledge | `2-deal-finder` | Visit each resource, scrape current listings, emit one file per vehicle |
| Wisdom | `3-market-report` | Synthesize all vehicles into a ranked report |

## Plan file (key sections)

```markdown
# Car Search Pipeline

Find the best used body-on-frame trucks under the budget cap. Discover candidate makes, identify monitoring resources, hunt live deals, produce a ranked market report.

## Steps

1. **Run @0-makes** — Discover all body-on-frame SUV makes worth considering, then deep-dive each.
   Params: none (fixed criteria live in ARTIFACT.md as a `# Criteria` block)
   Inputs: none (web research)
   Output: @0-makes/out/<date>/<make>.md — one file per discovered make. Buyer's guide: generations, known issues, sweet-spot years, citations.

2. **Run @1-online-resources** — For each make from 0-makes, list agent-accessible monitoring resources.
   Inputs: @0-makes/out/<latest>/<make>.md
   Output: @1-online-resources/out/<date>/<make>-online-resources.md — one file per make.

3. **Run @2-deal-finder** — Visit each resource, scrape listings, emit one file per vehicle.
   Inputs: @1-online-resources/out/<date>/<make>-online-resources.md
   Output: @2-deal-finder/out/<date>/<date-posted><STATE>-<city>-<year-make-model-trim>.md — N vehicle files.

4. **Run @3-market-report** — Synthesize all vehicles into a ranked report.
   Inputs: all vehicle files from @2-deal-finder/out/<date>/
   Output: @3-market-report/out/<date>/<date>-market-report.md
```

## `# Criteria` block in `0-makes/ARTIFACT.md`

The selection criteria are fixed for a given run — they're not knobs you tune between executions. So they live as prose, not in `params:`:

```markdown
---
name: 0-makes
description: Buyer's guide per discovered vehicle make
outputs:
  "<make>.md":
    desc: "One file per discovered make — comprehensive buyer's guide"
---

# Goal

Discover every make worth considering for a used body-on-frame SUV under the criteria below, then produce a citation-backed buyer's guide per make.

# Criteria

- **Budget:** under the cap (see params block in plan, or hardcoded for a one-shot run)
- **Mileage:** under the cap
- **Region:** dry states only (no rust belt)
- **Platform:** body-on-frame only (no unibody crossovers)

# Priorities

1. Reliability — non-negotiable
2. Modern appearance
3. Value (reliability-to-price ratio)

# Steps

## Phase 1 — Discovery (1 agent)
Identify candidate makes that fit the criteria. Output a shortlist.

## Phase 2 — Deep Dive (1 agent per discovered make)
For each make from Phase 1, research generations, known issues, sweet-spot years; emit `<make>.md`.
```

If a particular value *is* tunable (a budget cap that varies between runs), promote it to `params:`. If it isn't, keep it prose.

## Per-item outputs in `2-deal-finder`

The output declaration uses a filename pattern, not a single fixed name:

```yaml
outputs:
  "<date-posted><STATE>-<city>-<year-make-model-trim>.md":
    desc: "One file per discovered vehicle, fully YAML-headed"
```

Each emitted vehicle file gets its own receipt in the sibling `receipts/` directory, named by appending `.md` to the output filename:

```
2-deal-finder/out/2026-04-12/
  2026-04-10CO-denver-2005-make-model-trim.md
  2026-04-07AZ-phoenix-2008-make-model-trim.md
  ...
  receipts/
    2026-04-10CO-denver-2005-make-model-trim.md.md   ← receipt
    2026-04-07AZ-phoenix-2008-make-model-trim.md.md  ← receipt
    ...
```

This scales — 50+ vehicles each with a receipt is fine. A per-item receipt usually documents *that item's* provenance (source URL, scrape timestamp, normalization notes).

## Run file

Run logs live in a `runs/` subdirectory next to the plan, one file per execution: `runs/<YYYY-MM-DD-HHMM>-<plan-name>-run.md`. The run file is created only when the plan itself is executed — i.e., when the user prompts Claude with `@car-search-plan.md` and Claude follows the plan's `## Run file` instructions. No `/artifact` subcommand (`plan`, `create-plan-artifacts`, `create`) creates or modifies this file:

```
artifacts/car-search/
  car-search-plan.md
  runs/
    2026-04-12-1800-car-search-plan-run.md
    2026-04-13-0900-car-search-plan-run.md
```


```yaml
---
plan: car-search-plan.md
started: 2026-04-12T18:00 local
status: completed
plan_sha: e892d3f4
reused_artifacts: []
---
```

```markdown
## Progress

| # | Artifact | Status | Output Date | Notes |
|---|----------|--------|-------------|-------|
| 1 | 0-makes            | done | 2026-04-12 | <N> makes discovered      |
| 2 | 1-online-resources | done | 2026-04-12 | <N> resource files        |
| 3 | 2-deal-finder      | done | 2026-04-12 | 51 vehicles               |
| 4 | 3-market-report    | done | 2026-04-12 | 8 top picks               |

## Log

### 0-makes — 2026-04-12T18:06
- **Status**: done
- **Outputs**: <make-A>.md, <make-B>.md (+ receipts)
- **Issues**: none
- **Handoff**: Phase 1 surfaced <N> makes; key model years for downstream resource search: ...

### 1-online-resources — 2026-04-12T18:20
- **Status**: done
- **Outputs**: ...
- **Issues**: Several major aggregators returned 403 (anti-bot). Excluded.
- **Handoff**: Tier-1 (curl-friendly): ... ; Tier-2 (JS-rendered): ...
```

The `plan_sha` is `git hash-object <plan-name>-plan.md`. If a later run produces the same hash AND the upstream artifact outputs are unchanged, `create` can offer to reuse a prior run's output instead of re-executing.
