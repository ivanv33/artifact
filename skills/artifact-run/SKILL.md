---
name: artifact-run
description: Use whenever the user wants to execute an artifact — a directory containing an ARTIFACT.md file (an LLM recipe with declared inputs, params, and outputs). Triggers on phrases like "run the X artifact", "execute 1-github-report", "let's run this artifact", or any request to invoke `artf run` / `artifact run` against a directory. Use this skill even when the user doesn't say the word "artifact" explicitly, as long as they're referencing a directory that has an ARTIFACT.md. The skill reads the frontmatter, collects param values and input sources from the user, stages any user-provided input content into a fresh tmp dir, shows the exact CLI command (`uvx artf run ...`), and only invokes the CLI after explicit confirmation.
---

# artifact-run

You are helping the user execute one run of an artifact. An **artifact** is a directory containing `ARTIFACT.md` (YAML frontmatter + prompt body) that declares required `inputs`, `params`, `model`, and `outputs`. The CLI is invoked as `uvx artf run <dir> --input NAME=PATH ... --param NAME=VALUE ...` — `uvx` fetches the published `artf` package, so you can run it from any directory without needing a local checkout.

Your job is to turn a vague "run X" into a correct, confirmed CLI invocation — without ever guessing at values the user hasn't supplied, and without running the command before the user approves it.

## Why this skill exists

The `artf` CLI is strict: every declared input must be passed as `--input name=path`, every required param as `--param name=value`, and the paths in `--input` must point at real files on disk. Users often have the data in their head, in a chat message, or sitting in a random location — not yet staged as files with the exact declared names. This skill handles that gap: it reads the contract from `ARTIFACT.md`, asks the user only what it actually needs, stages ad-hoc input content into a tmp dir via `mktemp -d`, and confirms the whole command before executing.

If you skip confirmation, you risk spending API credits on a run with wrong params. If you guess inputs the user hasn't provided, you fabricate data. Both are bad. The skill's discipline is what makes it trustworthy.

## Workflow

Work through these steps in order. Don't skip ahead — each step's output feeds the next.

### 1. Resolve the artifact directory

The user will reference the artifact by name, relative path, or implicitly ("run this", "run it").

- If the user said a name/path, check that `<dir>/ARTIFACT.md` exists with `ls` or `Read`.
- If the reference is ambiguous (multiple candidates, or no obvious one), use `Glob` with pattern `**/ARTIFACT.md` to list candidates and ask the user which one.
- If no `ARTIFACT.md` exists at the referenced path, stop and tell the user — don't try to create one.

### 2. Read and parse `ARTIFACT.md` frontmatter

Use `Read` on `<dir>/ARTIFACT.md`. The frontmatter is YAML between `---` lines. Extract:

- `model` — the default model string (only shown to user if they want to override).
- `inputs` — list of `{name, desc}`. All declared inputs are required by the CLI.
- `params` — list of `{name, type, required, default?, desc}`. Track which are required vs optional-with-default.
- `outputs` — list of `{name, desc}`. Informational only; shown to user so they know what to expect.

You don't need to execute the prompt body — that's the CLI's job. You just need the contract.

### 3. Collect param values

For each declared param:

- **Required params**: must be resolved to a concrete value before running. Check the conversation history first — the user may have already stated the value ("run X for user=alice"). If not present, ask.
- **Optional params with defaults**: don't ask unless the user has indicated they want to override. Mention them in the confirmation summary as "(default: <value>)" so the user can redirect.
- **Optional params without defaults**: ask whether the user wants to set them, but don't force it.

When asking, group questions into one message — don't ping-pong. Example: "I need values for these params: `user` (GitHub username, required), `focus` (optional, defaults to 'general'). What should I use?"

### 4. Collect input sources

For each declared input, figure out **where the file content will come from**. There are three cases:

**(a) User already has a file on disk** — they'll give you a path. Verify the file exists with `ls` before wiring it in. Pass it directly to `--input name=/absolute/path`.

**(b) User gives you content inline** (pastes JSON, markdown, etc., or says "use the data I showed you earlier") — you'll stage it into a scratch directory:

```bash
STAGE=$(mktemp -d -t artifact-run-XXXXXX)
```

If `mktemp` is blocked by your environment (sandboxed shells often block `/tmp` and `mktemp`), fall back to creating a fresh subdirectory in the current working area, e.g. `mkdir .artifact-stage-$(date +%s)` or any writable path — the CLI doesn't care where the file lives, only that the `--input` path points at a file with the exact declared name. If even `mkdir` is blocked, use `Write` directly against a fresh workspace path and treat it as the scratch location.

Then `Write` each piece of content to `$STAGE/<input-name>` (use the exact declared input name as the filename — the CLI matches on this). Pass `--input name=$STAGE/<input-name>`.

**(c) User hasn't provided it yet** — ask. Offer the three modes: "For `events.json`, do you have (1) a file path, (2) content you want to paste, or (3) a description of what you want me to generate for you?"

**(d) User asks you to generate the content** ("make me up some sample events", "write a mission statement about growth", "I'll describe it, you write it") — generate it, show the user the generated content before staging, and stage it into the same tmp dir as case (b). Label it in the confirmation summary as generated (e.g., `events.json → /tmp/.../events.json (generated from: "five sample push events on repo foo")`). The user has opted into synthesis; your job is to keep it visible, not silent.

Print the tmp dir path in your confirmation so the user knows what got created and where.

### 5. Confirm before running

Before invoking the CLI, show the user a compact summary and wait for an explicit go-ahead. Use this structure:

```
Ready to run `<artifact-dir>`:

Params:
  user = alice
  focus = (default: general)

Inputs:
  events.json → /Users/poplar/data/alice-events.json
  mission.md  → /tmp/artifact-run-abc123/mission.md (staged from pasted content)

Model: anthropic:claude-sonnet-4-6 (from ARTIFACT.md)

Command:
  uvx artf run <artifact-dir> \
    --input events.json=/Users/poplar/data/alice-events.json \
    --input mission.md=/tmp/artifact-run-abc123/mission.md \
    --param user=alice

Proceed?
```

Don't run until the user says yes (or equivalent). If they want to change something, loop back to the relevant step.

If the user's initial request already contains pre-approval ("go ahead and run it", "approved — proceed", "just execute it"), treat that as the explicit go-ahead for this invocation: still show the summary so the user can see what you're about to do, but you don't need to wait for a second confirmation. The point of confirmation is catching wrong param/input values; if the user waived that deliberately, respect it.

### 6. Execute and report

Invoke via `Bash`:

```bash
uvx artf run <artifact-dir> --input ... --param ...
```

`uvx` fetches the `artf` package from PyPI and runs it — no local checkout or `cd` needed. You can invoke it from anywhere; the artifact directory is resolved from the path argument. If the user asked to promote the run, add `--promote-as <label>`. If they asked to override the model, add `--model <provider:name>`.

After it finishes, the CLI prints the run directory (something like `runs/<timestamp>/`) inside the artifact dir. Surface that to the user along with the output file names so they know where to look.

If the CLI exits non-zero, relay the stderr verbatim — don't editorialize. The error messages are designed to be actionable.

## Input staging details

**Filenames must match declared input names exactly.** If the artifact declares an input named `events.json`, the file you stage must be named `events.json` in the tmp dir — not `events_alice.json` or `input.json`. The `--input name=path` flag uses `name` to look up the declared input, and the file at `path` gets copied into `runs/<id>/in/<name>`.

**One tmp dir per run is fine** — you don't need a separate dir per input. Create it once with `mktemp -d` at the start of step 4 if any input needs staging, then write all user-provided content into that same dir.

**Don't delete the tmp dir after running.** The CLI copies content into the run directory, so the tmp files are no longer load-bearing — but leaving them around costs nothing and helps the user debug if something looks wrong.

## When the user wants to override the model

The `model` in `ARTIFACT.md` is the default. If the user says something like "run it with haiku" or "use anthropic:claude-haiku-4-5", add `--model <provider:name>` to the command. Show this in the confirmation summary explicitly so the user can verify.

## When the user wants to promote the run

If the user says "promote as alice" or "save this as the alice output" or similar, add `--promote-as <label>`. This copies the run to `outs/<label>/` after a successful execution. Mention this in the confirmation.

## Things to avoid

- **Don't quietly synthesize input content.** If the user says "run X" and you don't have a path or pasted content for a declared input, ask — never silently generate plausible-looking JSON or markdown to fill a gap and then run with it. It's fine to generate content when the user explicitly asks for it ("make up some sample events" or "write a mission statement about growth") — in that case, produce it, show the user what you wrote before staging it, and label it in the confirmation summary as "(generated from description: '<what they asked for>')" so there's no ambiguity that the input is synthetic.
- **Don't skip confirmation** even on what looks like a trivial run. The user may have a reason for asking you to run something — the cost of confirming is small; the cost of a wrong run is API spend and a polluted runs/ history.
- **Don't run the prompt body yourself.** You're invoking the CLI, not executing the artifact. The CLI handles the LLM call.
- **Don't invent params or inputs not declared in frontmatter.** The CLI will reject them anyway.
- **Don't cd into the artifact dir to run.** `uvx artf` is a self-contained invocation — pass the artifact dir as an argument from wherever you are.

## Quick reference: the CLI flags

```
uvx artf run <artifact-dir>
    [--input NAME=PATH]...     # repeat for each declared input
    [--param NAME=VALUE]...    # repeat for each param you set
    [--model PROVIDER:NAME]    # override ARTIFACT.md's model
    [--promote-as LABEL]       # also copy the run to outs/<LABEL>/
```
