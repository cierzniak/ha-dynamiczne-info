"""A daily cutoff must stop an otherwise continuously matching schedule."""

from datetime import datetime, time
from zoneinfo import ZoneInfo

import pytest
from scheduler import MODE_ADVICE_USE, MODE_PRICE_BELOW, HourRow, plan_run

WARSAW = ZoneInfo("Europe/Warsaw")


@pytest.mark.parametrize("mode", [MODE_PRICE_BELOW, MODE_ADVICE_USE])
@pytest.mark.parametrize(
    ("day", "hour", "minute", "running"),
    [
        (22, 5, 59, True),
        (22, 6, 0, False),
        (22, 6, 1, False),
        (22, 23, 59, False),
        (23, 0, 0, True),
    ],
)
def test_stop_remains_off_until_next_day(mode, day, hour, minute, running):
    now = datetime(2026, 9, day, hour, minute, tzinfo=WARSAW)
    hours = [HourRow(now.replace(minute=0), 0.1, "use")]
    result = plan_run(
        mode=mode, now=now, hours=hours, stop_at=time(6), price_ceiling=0.5
    )
    assert result.run_now is running
    if not running:
        assert not result.selected_starts
        assert result.planned_start is None


@pytest.mark.parametrize("mode", [MODE_PRICE_BELOW, MODE_ADVICE_USE])
def test_minute_cutoff_inside_matching_hour(mode):
    now = datetime(2026, 9, 22, 6, 15, tzinfo=WARSAW)
    result = plan_run(
        mode=mode,
        now=now,
        hours=[HourRow(now.replace(minute=0), 0.1, "use")],
        stop_at=time(6, 15),
        price_ceiling=0.5,
    )
    assert not result.run_now
