"""Executor that runs an artifact recipe via the local ``claude`` CLI.

The executor shells out to ``claude -p --output-format stream-json`` with the
artifact body piped in as the system prompt. No Python SDK sits in the stack:
the CLI's stream-json output is a committed public contract, and parsing it
ourselves keeps the dep surface minimal.
"""

from __future__ import annotations

import json
import sys
from typing import Iterable, TextIO

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
