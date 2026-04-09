# artifact

A Claude Code skill and plugin for creating reproducible DIKW artifact pipelines.

## What it does

Turns chat sessions into reproducible, composable artifacts organized by the DIKW hierarchy:

- **Data (0x)** — Raw facts: downloaded, scraped, imported
- **Info (1x)** — Derivative of data, still close to truth: filtered, joined, tagged
- **Knowledge (2x)** — Prediction models built from data/info: scripts that compute stats, find patterns
- **Wisdom (3x)** — Conclusions using knowledge + info + data: actionable decisions

## Three commands

| Command | What it does |
|---------|-------------|
| `/artifact plan` | Decompose a goal into an artifact DAG, produce an executable plan.md |
| `/artifact plan-artifacts` | Take a plan.md, scaffold all artifact dirs with ARTIFACT.md recipes |
| `/artifact create` | Create a single artifact with outputs |

## Artifact structure

```
00-weather/
├── ARTIFACT.md          # Recipe: YAML frontmatter + markdown prompt
├── scripts/             # Optional: self-contained Python/shell helpers
└── out/
    └── 2026-04-08/
        ├── daily_weather.csv    # The artifact
        └── daily_weather.md     # Sidecar: params + generation log
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
