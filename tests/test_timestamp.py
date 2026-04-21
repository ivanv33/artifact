import re
from datetime import datetime, timezone

from artifact.timestamp import format_run_id, make_run_id


def test_format_run_id_shape():
    dt = datetime(2026, 4, 19, 14, 23, 1, tzinfo=timezone.utc)
    assert format_run_id(dt) == "2026-04-19T14-23-01+0000"


def test_format_run_id_with_offset():
    from datetime import timedelta

    tz = timezone(timedelta(hours=-7))
    dt = datetime(2026, 4, 19, 14, 23, 1, tzinfo=tz)
    assert format_run_id(dt) == "2026-04-19T14-23-01-0700"


def test_make_run_id_is_filesystem_safe():
    run_id = make_run_id()
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}[+-]\d{4}", run_id)
    assert ":" not in run_id


def test_format_run_id_requires_tz():
    import pytest

    with pytest.raises(ValueError):
        format_run_id(datetime(2026, 4, 19, 14, 23, 1))  # naive
