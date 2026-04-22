"""Executor that runs an artifact recipe via the local ``claude`` CLI.

The executor shells out to ``claude -p --output-format stream-json`` with the
artifact body piped in as the system prompt. No Python SDK sits in the stack:
the CLI's stream-json output is a committed public contract, and parsing it
ourselves keeps the dep surface minimal.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
from pathlib import Path
from typing import Callable, Iterable, TextIO

from artifact.errors import RunnerError
from artifact.spec import Spec


def _build_argv(*, spec: Spec, templated_body: str, kickoff: str) -> list[str]:
    """Build argv for ``subprocess.Popen``. Pure function.

    ``--verbose`` is passed because ``claude -p --output-format stream-json``
    produces richer output under verbose (the CLI is prone to suppressing
    assistant-text events otherwise). This can be removed later if empirical
    testing proves it unnecessary.
    """
    argv = [
        "claude",
        "-p",
        kickoff,
        "--output-format",
        "stream-json",
        "--verbose",
        "--permission-mode",
        "bypassPermissions",
        "--system-prompt",
        templated_body,
    ]
    if spec.model:
        argv.extend(["--model", spec.model])
    return argv


def _consume_stream(
    lines: Iterable[str], *, stdout: TextIO
) -> dict | None:
    """Parse ``--output-format stream-json`` lines; forward readable events.

    - ``assistant`` events: each ``text`` content block is written to
      ``stdout`` as-is, flushed. Each ``tool_use`` content block renders as
      ``\\n[ToolName]\\n``.
    - ``result`` event: captured and returned.
    - Malformed JSON line: warning to stderr; continue.
    - Any other event type (``system``, ``user``, ``stream_event``,
      ``rate_limit_event``, unknown future types): silently skipped for
      forward-compatibility.

    Returns the final ``result`` event dict, or ``None`` if none was seen.
    """
    result: dict | None = None
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            print(
                f"warning: claude CLI emitted non-JSON line: {line!r}",
                file=sys.stderr,
            )
            continue
        etype = event.get("type")
        if etype == "assistant":
            content = (event.get("message") or {}).get("content") or []
            for block in content:
                btype = block.get("type")
                if btype == "text":
                    text = block.get("text", "")
                    if text:
                        stdout.write(text)
                        stdout.flush()
                elif btype == "tool_use":
                    name = block.get("name", "?")
                    stdout.write(f"\n[{name}]\n")
                    stdout.flush()
        elif etype == "result":
            result = event
    return result


_USER_KICKOFF = (
    "Execute the recipe in your system prompt. "
    "Read inputs from in/ and write outputs to out/ using the declared output names."
)

_RESULT_FIELD_MAP = {
    "session_id": "session_id",
    "model": "model_used",
    "num_turns": "num_turns",
    "duration_ms": "duration_ms",
    "total_cost_usd": "total_cost_usd",
}


def claude_cli_executor(
    *,
    spec: Spec,
    run_dir: Path,
    templated_body: str,
    popen_factory: Callable[..., subprocess.Popen] = subprocess.Popen,
) -> dict | None:
    """Execute an artifact by shelling out to the local ``claude`` CLI.

    Streams the CLI's ``--output-format stream-json`` output: assistant text
    and tool-use summaries are forwarded to our stdout live; the final
    ``result`` event is extracted and returned under a ``claude_cli:`` manifest
    block.

    Raises:
        RunnerError: if ``claude`` is missing from PATH, the subprocess exits
            non-zero, the stream ends without a ``result`` event, or the
            ``result`` event carries ``is_error: true``.
    """
    argv = _build_argv(
        spec=spec, templated_body=templated_body, kickoff=_USER_KICKOFF
    )
    try:
        proc = popen_factory(
            argv,
            cwd=str(run_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
    except FileNotFoundError as e:
        raise RunnerError(
            "claude CLI not found on PATH; install with "
            "`npm i -g @anthropic-ai/claude-code`"
        ) from e

    stderr_tail: list[str] = []

    def _pump_stderr() -> None:
        for line in proc.stderr:
            stderr_tail.append(line)
            if len(stderr_tail) > 20:
                stderr_tail.pop(0)
            sys.stderr.write(line)
            sys.stderr.flush()

    pump = threading.Thread(target=_pump_stderr, daemon=True)
    pump.start()
    try:
        result = _consume_stream(proc.stdout, stdout=sys.stdout)
    finally:
        try:
            proc.stdout.close()
        except Exception:
            pass
    rc = proc.wait()
    pump.join(timeout=1.0)

    if rc != 0:
        tail = "".join(stderr_tail).rstrip()
        raise RunnerError(
            f"claude CLI exited with code {rc}"
            + (f"; stderr tail:\n{tail}" if tail else "")
        )
    if result is None:
        raise RunnerError("claude CLI exited without a final result event")
    if result.get("is_error") is True:
        raise RunnerError(
            f"claude CLI reported error: subtype={result.get('subtype')!r} "
            f"result={result.get('result')!r}"
        )

    extracted = {
        dst: result[src]
        for src, dst in _RESULT_FIELD_MAP.items()
        if src in result
    }
    return {"claude_cli": extracted}
