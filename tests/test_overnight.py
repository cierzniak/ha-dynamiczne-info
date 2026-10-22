"""Fixed schedules retain the active block across midnight and DST."""

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from scheduler import MODE_FIXED, plan_run

WARSAW = ZoneInfo("Europe/Warsaw")


@pytest.mark.parametrize(
    ("hour", "minute", "running"),
    [
        (21, 59, False),
        (22, 0, True),
        (23, 59, True),
        (0, 0, True),
        (2, 0, True),
        (5, 59, True),
        (6, 0, False),
    ],
)
def test_overnight_boundaries(hour, minute, running):
    now = datetime(2026, 9, 22, hour, minute, tzinfo=WARSAW)
    result = plan_run(
        mode=MODE_FIXED, now=now, hours=[], start_at=time(22), stop_at=time(6)
    )
    assert result.run_now is running
    if running and hour < 6:
        assert result.selected_starts[0].astimezone(WARSAW).day == 21


@pytest.mark.parametrize(("month", "day", "count"), [(3, 29, 7), (10, 25, 9)])
def test_dst_overnight_counts_elapsed_hours(month, day, count):
    now = datetime(2026, month, day, 3, 30, tzinfo=WARSAW)
    result = plan_run(
        mode=MODE_FIXED, now=now, hours=[], start_at=time(22), stop_at=time(6)
    )
    assert result.run_now
    starts = [value.astimezone(UTC) for value in result.selected_starts]
    assert len(starts) == count
    assert all(
        b - a == timedelta(hours=1) for a, b in zip(starts, starts[1:], strict=False)
    )


def test_single_hour_start_before_midnight():
    result = plan_run(
        mode=MODE_FIXED,
        now=datetime(2026, 9, 22, 0, 15, tzinfo=WARSAW),
        hours=[],
        start_at=time(23, 30),
    )
    assert result.run_now
