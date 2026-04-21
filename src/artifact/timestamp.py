"""Local-timezone ISO-8601 run ID generator.

Run IDs are filesystem-safe (colons replaced with hyphens) and carry the
machine's local timezone offset, so humans scanning ``runs/`` see timestamps
that match their wall clock without mental conversion.
"""

from __future__ import annotations

from datetime import datetime


def make_run_id(now: datetime | None = None) -> str:
    """Return a fresh run ID for the current moment.

    Args:
        now: Override for the current time. Defaults to wall clock in local tz.

    Returns:
        A filesystem-safe run ID in ``YYYY-MM-DDTHH-MM-SS±HHMM`` form.
    """
    dt = now if now is not None else datetime.now().astimezone()
    if dt.tzinfo is None:
        dt = dt.astimezone()
    return format_run_id(dt)


def format_run_id(dt: datetime) -> str:
    """Format a timezone-aware ``datetime`` as a filesystem-safe run ID.

    Args:
        dt: A timezone-aware ``datetime``.

    Returns:
        The string ``YYYY-MM-DDTHH-MM-SS±HHMM``.

    Raises:
        ValueError: If ``dt`` is naive (has no ``tzinfo``).
    """
    if dt.tzinfo is None:
        raise ValueError("format_run_id requires a timezone-aware datetime")
    return dt.strftime("%Y-%m-%dT%H-%M-%S%z")
