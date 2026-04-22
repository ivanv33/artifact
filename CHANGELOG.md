# Changelog

All notable changes to `artifact` / `artf` are documented here. Format based on [Keep a Changelog](https://keepachangelog.com/); project follows SemVer.

## [0.3.0] — 2026-04-22

### Added

- **`artifact template`** — emits a complete reference `ARTIFACT.md` (frontmatter + body) to stdout. No flags, no arguments; `# one of: …` comments are interpolated from the parser's authoritative `ALLOWED_*` constants so they can't drift.
- **`artifact create <dir>`** — reads `ARTIFACT.md` from stdin, validates it through the same parser `run` uses, and writes `<dir>/ARTIFACT.md` plus `<dir>/.gitignore` (containing `runs/*`). Validation failures abort before any file is written. Refuses non-empty destinations.
- **Pipe-composable one-liner:** `artifact template | artifact create my-artifact` scaffolds a working artifact in one step.
- **Public parser API:** `artifact.spec.ALLOWED_KINDS`, `ALLOWED_EXECUTORS`, `ALLOWED_PARAM_TYPES`, and `parse_spec_from_str(content, path)` are now part of the supported surface.
- **`cli.main` stdin injection seam:** tests can pass `stdin=` to `cli.main(...)` to exercise the `create` branch without monkeypatching `sys.stdin`, mirroring the existing `executor=` seam.

### Changed

- Parser error messages for `inputs[].name` / `outputs[].name` now call out "bare filename" violations (e.g. `name: ../x.md`, `name: /abs/x.md`) at parse time instead of letting them surface downstream at run time.
- Parser now rejects duplicate `name:` entries within an `inputs:`, `params:`, or `outputs:` list. Previously these parsed silently and produced an ambiguous `Spec`.
- Parser now surfaces non-UTF-8 content (bytes smuggled via stdin's `surrogateescape` handler) as a clean `SpecError` instead of a leaking `UnicodeEncodeError` traceback.

### Fixed

- `artifact create` no longer leaks a Python traceback on non-UTF-8 stdin content. The error is now a single-line `error: …: content contains non-UTF-8 bytes: …` message.

### Non-goals (explicitly deferred)

- Identifier-shape validation on `params[].name` (still accepts any non-empty string).
- Ancestor `.gitignore` detection — `create` always writes a local `runs/*` line.
- A positional template selector (`artifact template <name>`) — deferred until a second shipped template exists.
- Project-level scaffolding (`pyproject.toml`, README) — `create` produces one artifact directory, nothing more.

## [0.2.1] — prior release

See `git log v0.2.0..v0.2.1` for the full change list. Highlights: `claude_cli` executor, `--model` override on `run`, integration-test infrastructure.

## [0.2.0] — initial public release

See `git log v0.2.0` for the initial feature set: `run`, `promote`, `runs`, `show`.
