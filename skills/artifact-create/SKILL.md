---
name: artifact-create
description: Use whenever the user wants to scaffold a new artifact directory — an ARTIFACT.md recipe plus a `runs/*`-ignoring `.gitignore`. Triggers on phrases like "create a new artifact", "scaffold an artifact for X", "make me an ARTIFACT.md", "new 0-weather artifact", or any request to invoke `artf create` / `artifact create`. Use this skill even if the user doesn't say "artifact" explicitly, as long as they're asking you to produce an ARTIFACT.md for a directory that doesn't yet exist.
---

# artifact-create

Scaffold a new artifact directory by running `uvx artf template`, editing the reference to match the user's description, confirming the draft, and piping it into `uvx artf create <name>`.

## Steps

### 1. Resolve the directory name (and DIKW prefix)

If the user already gave a full name with a DIKW prefix (`0-weather`, `2-shortlist`), use it. If they gave a bare name (`weather`, `shortlist`), **suggest a prefix yourself** based on what the artifact does:

- **0-** raw data, close to source (scraped, fetched, imported)
- **1-** info derived from data (filtered, joined, tagged, summarized — still data in shape)
- **2-** knowledge — statistical findings, forecasts, probabilities, patterns. *Answers "what does the data say?"* The reader still makes the call.
- **3-** wisdom — direct recommendations, shortlists, action calls. *Answers "what should I do?"* The artifact makes the call.

**Tiebreaker when you're unsure between 2 and 3:** if the output is primarily a number or finding with context, it's `2-`. If the output tells the reader what to do, it's `3-`. A probability-of-rain memo is `2-` (a finding). A "buy vs rent" verdict is `3-` (a call). A "top 5 cars to test-drive" shortlist is `3-` (a call). Don't let the word "verdict" or "recommendation" in the artifact name alone push you to `3-` — look at what the output actually does.

The prefix is a convention, not enforced by the CLI, but it's how pipeline directories stay navigable. Say which level you picked and why in one line (e.g. "I'll use `0-weather` since this fetches raw NOAA data"), and let the user redirect.

If the target directory already exists and isn't empty, `artf create` will refuse — stop and ask before doing anything destructive.

### 2. Get the template

```bash
uvx artf template
```

Always re-fetch. The template is the source of truth and evolves with the tool — don't write frontmatter from memory.

### 3. Edit to match the user's description

The core of this step — and of the whole skill — is turning the user's description into a precise transform: **declare the inputs, declare the outputs, and specify the algorithm that maps one to the other**. The frontmatter is the interface; the body is the algorithm. Don't treat the body as boilerplate.

**Frontmatter:** Prune and rewrite `inputs`, `params`, `outputs`, `executor`, `model`. Drop sections that don't apply (e.g. no `inputs:` list if there are no inputs). Keep the template's conventions — list-form entries with `name:` and `desc:`, bare filenames in `name:`. Each `desc:` should describe the **shape** of the data (columns, JSON fields with types, prose structure), not its provenance.

**Body prompt:** this is where you write the algorithm. A vague body produces unreliable output; a specific body produces reproducible output. Apply these patterns:

- **Decompose into explicit steps.** Numbered or labeled phases that follow the actual data flow — typically some combination of *read → filter → group → compute → format → emit*. Don't collapse a multi-step transform into a single sentence; the agent follows the structure you give it.

- **Specify output shape concretely.** For structured outputs, show a fenced template or enumerate the fields with types and constraints. "A JSON object with some metrics" is not a spec; `{"revenue_yoy_pct": <float, negative if declining>, "eps_consensus": <float or null if not stated>}` is. For prose outputs, specify paragraph count / section order / length.

- **Kill ambiguity in conventions.** Every transform has choices the spec must make for the agent: sort order and tie-breaking (*"descending by count, break ties by name ascending"*), units (*"return_pct is a float, 0.125 not 12.5%"*), rounding (*"do not round — emit the full float"*), timezone (*"dates are UTC"*), field ordering (*"preserve holdings.csv order"*). If two reasonable readings exist, pick one in the body.

- **Handle edge cases explicitly.** Null values, empty inputs, missing joins, zero denominators. *"If active_days is 0, say so rather than dividing."* *"If a ticker has no price row for as_of_date, include it with price-derived fields set to null rather than dropping."* Edge-case clauses are what separate a recipe that works on every input from one that works on the happy path.

- **Reference inputs and params by the exact declared names**, using `{{ inputs.<filename> }}` and `{{ params.<name> }}` templating. Don't paraphrase ("the weather file", "the chosen year") — that leaves the agent guessing which thing you meant.

- **Use verbs, not adjectives.** Describe what the agent *does*, not what the output *is*: "Look up the price row for (ticker, as_of_date)" beats "The output includes current prices." Verbs compose into a recipe; adjectives don't.

Put constraints that are easy to miss (type conventions, edge-case rules, ordering) either at the top of the body or right next to the step they govern — not buried in the middle. Models attend to the beginning and end of a prompt more reliably than to its middle.

**What NOT to put in the body:** error-handling around the CLI (`artf run` manages that), output paths like `out/<date>/...` or receipts (the runner writes `runs/<timestamp>/out/...` on its own; the recipe just names output files), or provenance metadata (that goes in the run manifest, not the recipe).

### 4. Show the draft and confirm

Show the user the final ARTIFACT.md in a fenced code block, along with the directory name you plan to pass to `artf create`. Wait for an explicit yes before piping — it's cheaper to fix typos now than after `artf create` has written the directory.

If the user pre-approved ("just scaffold it", "no need to confirm"), still show the draft so they can see what's about to land, but skip the wait.

### 5. Pipe into `artf create`

`artf create` requires stdin to be a pipe, not a TTY. Stage the draft to a file (via `Write` — byte-safe for any content) and redirect:

```bash
uvx artf create <name> < /path/to/draft.md
```

Don't heredoc-pipe directly into the command — backticks and `$` in the body will bite you.

### 6. Verify and report

**Don't trust exit codes alone** — check that the directory is actually on disk before claiming success:

```bash
ls <name>/ARTIFACT.md <name>/.gitignore
```

Both files must exist. If either is missing, something went wrong — surface the full CLI stderr verbatim and don't pretend it worked. If everything's there, tell the user what was created and point them at the `artifact-run` skill if they want to execute it next.

## Gotchas

- **Directory must not exist or must be empty.** `artf create` refuses to clobber. If the target exists and isn't empty, ask — don't force.
- **Names unique within each list.** `inputs` / `params` / `outputs` reject duplicates as `SpecError`.
- **UTF-8 only.** A stray BOM or Latin-1 byte fails validation.
