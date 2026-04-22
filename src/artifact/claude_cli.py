"""Executor that runs an artifact recipe via the local ``claude`` CLI.

The executor shells out to ``claude -p --output-format stream-json`` with the
artifact body piped in as the system prompt. No Python SDK sits in the stack:
the CLI's stream-json output is a committed public contract, and parsing it
ourselves keeps the dep surface minimal.
"""

from __future__ import annotations

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
