# artifact

A Claude Code skill and plugin for creating reproducible DIKW artifact pipelines.

## What it does

Turns chat sessions into reproducible, composable artifacts organized by the DIKW hierarchy:

Artifacts use double-digit numeric prefixes — the first digit marks the DIKW tier, the second digit orders artifacts within that tier (e.g. `00-`, `01-`, ..., `09-`, `10-`, ...).

- **Data (`00-` through `09-`)** — Raw facts: downloaded, scraped, imported
- **Info (`10-` through `19-`)** — Derivative of data, still close to truth: filtered, joined, tagged
- **Knowledge (`20-` through `29-`)** — Prediction models built from data/info: scripts that compute stats, find patterns
- **Wisdom (`30-` through `39-`)** — Conclusions using knowledge + info + data: actionable decisions

## Three commands

| Command | What it does |
|---------|-------------|
| `/artifact plan` | Decompose a goal into an artifact DAG, produce an executable plan.md |
| `/artifact create-plan-artifacts` | Take a plan.md, scaffold all artifact dirs with ARTIFACT.md recipes |
| `/artifact create` | Create a single artifact with outputs |

## Artifact structure

```
00-weather/
├── ARTIFACT.md          # Recipe: YAML frontmatter + markdown prompt
├── .gitignore           # out/* except out/latest  (out/latest is never created by the skill)
├── scripts/             # Optional: self-contained Python/shell helpers
└── out/
    └── 2026-04-08/
        ├── daily_weather.csv           # The artifact
        └── receipts/
            └── daily_weather.csv.md    # Receipt: params + generation log + artifact_sha
```

## Install as Claude Code plugin

```
claude plugin add ivanv33/artifact
```

## Install as skill (manual)

Clone and symlink into your skills directory:

```bash
git clone https://github.com/ivanv33/artifact.git
ln -s $(pwd)/artifact/skills/artifact ~/.agent/skills/artifact
```
