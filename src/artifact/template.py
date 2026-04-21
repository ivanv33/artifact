"""Substitute ``{{ params.X }}`` and ``{{ inputs.X }}`` placeholders in a body."""

from __future__ import annotations

import re

_PLACEHOLDER_RE = re.compile(r"\{\{\s*(params|inputs)\.([^\s}]+?)\s*\}\}")


class TemplateError(ValueError):
    """Raised when a template references an unknown name."""


def render(body: str, *, params: dict[str, object], inputs: dict[str, str]) -> str:
    """Substitute ``{{ params.X }}`` and ``{{ inputs.X }}`` placeholders.

    Whitespace around the dotted name is tolerated. Non-matching braces are
    left untouched.

    Args:
        body: The text containing placeholders.
        params: Mapping of param name to value. Non-string scalars are coerced with ``str()``.
        inputs: Mapping of input name to absolute path string.

    Returns:
        The body with all recognized placeholders substituted.

    Raises:
        TemplateError: If a placeholder names a key absent from its mapping.
    """

    def _sub(match: re.Match[str]) -> str:
        kind, name = match.group(1), match.group(2)
        table: dict[str, object] = params if kind == "params" else inputs
        if name not in table:
            raise TemplateError(f"unknown template variable: {kind}.{name}")
        return str(table[name])

    return _PLACEHOLDER_RE.sub(_sub, body)
