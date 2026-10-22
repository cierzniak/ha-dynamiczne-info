"""Timer selection for exact schedule boundaries without network polling."""

from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo

from schedule_time import next_schedule_tick
from scheduler import MODE_FIXED, plan_run

WARSAW = ZoneInfo("Europe/Warsaw")


def tick(now, **kwargs):
    return next_schedule_tick(
        now,
        **{
            "ready_by": None,
            "start_at": None,
            "stop_at": None,
            "selected_starts": (),
            **kwargs,
        },
    )


def test_start_and_stop_at_minute_and_second_precision():
    now = datetime(2026, 9, 22, 6, 10, tzinfo=WARSAW)
    start, stop = time(6, 15, 30), time(6, 45, 20)
    first = tick(now, start_at=start, stop_at=stop).astimezone(WARSAW)
    assert first.time() == start
    assert plan_run(
        mode=MODE_FIXED, now=first, hours=[], start_at=start, stop_at=stop
    ).run_now
    last = tick(first, start_at=start, stop_at=stop).astimezone(WARSAW)
    assert last.time() == stop
    assert not plan_run(
        mode=MODE_FIXED, now=last, hours=[], start_at=start, stop_at=stop
    ).run_now


def test_default_one_hour_end():
    now = datetime(2026, 9, 22, 7, tzinfo=WARSAW)
    assert tick(now, start_at=time(6, 15)).astimezone(WARSAW).time() == time(7, 15)


def test_hour_boundary_is_not_delayed_ten_seconds():
    now = datetime(2026, 9, 22, 6, 59, 59, tzinfo=WARSAW)
    assert tick(now).astimezone(WARSAW).time() == time(7)


def test_ready_by_and_parameter_change_replace_next_boundary():
    now = datetime(2026, 9, 22, 6, 10, tzinfo=WARSAW)
    assert tick(now, ready_by=time(6, 20)).astimezone(WARSAW).time() == time(6, 20)
    assert tick(now, ready_by=time(6, 30)).astimezone(WARSAW).time() == time(6, 30)


def test_dst_repeated_time_keeps_second_occurrence():
    now = datetime(2026, 10, 25, 2, 10, tzinfo=WARSAW, fold=1)
    assert tick(now, start_at=time(2, 15)) == datetime(2026, 10, 25, 1, 15, tzinfo=UTC)


def test_dst_missing_time_wakes_at_next_real_hour():
    now = datetime(2026, 3, 29, 1, 59, tzinfo=WARSAW)
    assert tick(now, start_at=time(2, 15)) == datetime(2026, 3, 29, 1, tzinfo=UTC)
