# Example: Is it always rainy on Passover in NYC?

A minimal 2-artifact pipeline (data + knowledge). No info layer — the date-tagging and statistical work live inside the knowledge script, not as a separate reusable dataset.

## Decomposition

- **`0-weather`** (data) — download N years of NYC daily weather. Generic and reusable for any weather question, not just Passover.
- **`2-passover-rain-verdict`** (knowledge) — Python script that reads the weather CSV, uses `pyluach` to find Passover dates, tags target vs baseline days, runs Fisher's exact test, computes an odds ratio, and writes a markdown verdict.

That's it. No `1-passover-weather` info artifact — the tagging is one line of pandas inside the verdict script.

## Plan file

```markdown
# Is it always rainy on Passover in NYC?

## Steps

1. **Run @0-weather** — Get historical NYC daily weather to test the rain-on-Passover hypothesis.
   Params: location=NYC, date_range=2015-01-01..2024-12-31
   Inputs: none
   Output: @0-weather/out/<date>/daily_weather.csv — columns: date, precipitation_mm, high_f, low_f, conditions

2. **Run @2-passover-rain-verdict** — Test whether Passover days are wetter than non-Passover days at p<0.05.
   Params: none
   Inputs: @0-weather/out/<date>/daily_weather.csv
   Output: @2-passover-rain-verdict/out/<date>/verdict.md — yes/no/inconclusive verdict with odds ratio, p-value, sample sizes
```

## Knowledge artifact (script-backed)

`2-passover-rain-verdict/ARTIFACT.md` declares one input + one output and the body says "run `scripts/verdict.py daily_weather.csv`". The script is self-contained via PEP 723:

```python
# /// script
# requires-python = ">=3.11"
# dependencies = ["pandas", "pyluach", "scipy"]
# ///
"""Test whether Passover days have more rain than baseline NYC days."""
import sys, pandas as pd
from pyluach import dates
from scipy.stats import fisher_exact
# ... read CSV, tag passover days, build 2x2, run test, write verdict.md
```

Run with: `uv run scripts/verdict.py daily_weather.csv`. No `requirements.txt`, no virtualenv setup.

## Outputs (after `/artifact create` runs)

```
0-weather/out/2026-04-08/
  daily_weather.csv
  receipts/
    daily_weather.csv.md        ← receipt (mandatory)

2-passover-rain-verdict/out/2026-04-08/
  verdict.md
  receipts/
    verdict.md.md               ← receipt (mandatory)
```

Receipts live in a sibling `receipts/` subdirectory. The `.csv.md` and `.md.md` extensions look odd at first; the rule is just "append `.md` to the full output filename". Pairing by filename keeps the output and its receipt unambiguous.

## Why no info layer?

The Lego Test: would anyone reuse `1-passover-weather` (a CSV of NYC weather tagged by Hebrew calendar) for a different question? Almost certainly not. So the tagging stays inside the knowledge script. If a downstream question wanted Hanukkah rain too, *then* it'd be worth promoting the tagger to its own artifact.
