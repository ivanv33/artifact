# DD: `--model` override

*Addendum to `artifact-dd.md` — adds one flag to `artifact run`.*

## Problem

`ARTIFACT.md` pins `model:`. Iterating on model choice (A/B, cost, "try the cheap one first") requires editing and re-committing the recipe. The recipe shouldn't change to flip the model.

## Change

Add `--model STR` to `artifact run`. When set, replaces `spec.model` at dispatch for this run only. The manifest records both the effective and declared model so provenance survives promotion.

```
artifact run <dir>
    [--input NAME=PATH]...
    [--param NAME=VALUE]...
    [--model PROVIDER:NAME]     # NEW — override ARTIFACT.md's model for this run
    [--promote-as LABEL]
```

`--model` is an opaque string handed to the executor. `artifact/` does not parse provider prefixes.

## Wiring

1. `cli.py`: add `--model` to the `run` subparser; reject empty string with `error: --model requires a non-empty string` and exit 1 before calling into the runner.
2. `runner.run(...)` gains `model: str | None = None`.
3. In `runner.run`, when `model` is set, produce an overridden spec via `dataclasses.replace(spec, model=model)` and thread *that* spec into the executor. Executors keep trusting `spec.model`; no `Executor` protocol change.
4. `_write_manifest` takes the original (parsed) spec and the override string; writes both fields below.

## Manifest

Two fields added, one field's semantics sharpen:

```json
{
  "model":            "claude_code:haiku",
  "model_declared":   "anthropic:claude-sonnet-4-6",
  "model_overridden": true
}
```

- `model` — effective model used for the run (was already present; always equals what the executor saw).
- `model_declared` — verbatim `spec.model` from the parsed `ARTIFACT.md`.
- `model_overridden` — `true` iff `--model` was passed.

When `--model` is absent: `model == model_declared`, `model_overridden: false`.

A reader of a promoted `outs/<label>/manifest.json` can tell, without re-parsing the recipe, whether this label's output came from the recipe's declared model or a one-off override.

## Claude Code CLI as a backend — deferred

Original intent: `--model claude_code:haiku` + the [`langchain-claude-code-cli`](https://pypi.org/project/langchain-claude-code-cli/) package would route the run through the local `claude` CLI on a Pro/Max subscription instead of a paid API key, with no code change in `artifact/`.

**That path does not work as of 2026-04-21.** Verified by manual test against `langchain-claude-code-cli==0.1.0` on `langchain==1.2.15`:

- The package's `__init__.py` only exposes `ChatClaudeCode` as a class. It does **not** register `claude_code` with LangChain's `init_chat_model`.
- LangChain's `_parse_model` (`.venv/.../langchain/chat_models/base.py`) only honors a `provider:` prefix when the provider is in `_BUILTIN_PROVIDERS`. `claude_code` is not in that set.
- Resolution falls through to `_attempt_infer_model_provider`, which at `base.py:529` matches `model.lower().startswith("claude")` and returns `"anthropic"`.
- Net effect: `claude_code:haiku` silently routes to `langchain_anthropic.ChatAnthropic`, which then fails on `Could not resolve authentication method` when no `ANTHROPIC_API_KEY` is set — surfacing the wrong error and hiding what actually went wrong.

### What's needed to make it work

An adapter in `src/artifact/exec.py` that detects the `claude_code:` prefix, strips it, and instantiates `langchain_claude_code.ChatClaudeCode(model=<tail>, ...)` directly. Pass the **instance** to `create_deep_agent` — its signature is `model: str | BaseChatModel | None`, so an instance bypasses `init_chat_model` entirely. ~10 lines in the executor, plus the package as a dependency (optional extra or hard dep — TBD).

Deferred until that adapter lands. Not blocking the rest of this feature.

### What works today

`--model` works for any provider `init_chat_model` already resolves — `anthropic:`, `google_genai:`, `openai:`, and peers. That is what this feature ships with. The unit + integration tests cover it.

### Requirements, once the adapter exists (inherited from the package)

- `claude` on `$PATH` (`npm i -g @anthropic-ai/claude-code`).
- Authenticated session (`claude /login`).
- TTY; won't work backgrounded.

## Testing

Unit tests via a fake `Executor` (per MEMORY.md — inject, don't monkeypatch):

- `--model X` on a spec declaring `model: Y` → executor sees `spec.model == X`; manifest has `model=X`, `model_declared=Y`, `model_overridden=true`.
- No `--model` → executor sees `spec.model == Y`; manifest has `model=Y`, `model_declared=Y`, `model_overridden=false`.
- `--model ""` → exit 1, stderr matches `error: --model requires a non-empty string`, no run directory created.

No new integration test. The override changes a string, not dispatch behavior.

## Non-goals

- A `model:` override at promotion time.
- An `ARTIFACT_MODEL` env default.
- Per-param or per-step model routing.
- A new executor. `executor: deepagent` remains the only executor in v0.2; `--model` only changes the string passed to it.
- LangSmith wiring inside `artifact`. Enabling LangSmith for a `claude_code:` run is a Claude Code plugin concern (see `docs.langchain.com/langsmith/trace-claude-code`) — install the plugin and set `TRACE_TO_LANGSMITH=true` in the host env; traces attach to the `claude` process, not to `artifact`.

## Open questions

- Should `--model` also be honored by `artifact promote` replay (if/when replay exists)? Likely yes — treat as manifest-driven. Deferred with replay itself.
- Warn when `--model` is used with `--promote-as`? The recipe's declared model no longer produced the promoted output; useful to catch "I promoted the cheap-model run by accident." Current answer: no warning — the manifest makes it explicit, and warnings that users learn to ignore are worse than none.
