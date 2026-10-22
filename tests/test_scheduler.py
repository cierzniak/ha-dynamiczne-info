"""Unit tests for the pure load scheduler (no Home Assistant required)."""

from datetime import datetime, time, timedelta, timezone

from scheduler import (
    MODE_ADVICE_USE,
    MODE_CHEAPEST_WINDOW,
    MODE_FIXED,
    MODE_PRICE_BELOW,
    HourRow,
    ScheduleResult,
    merge_hours,
    plan_run,
)

PL = timezone(timedelta(hours=2))  # CEST, stable offset for tests


def _h(hour, price, advice="neutral", day="2026-06-28"):
    return {
        "startsAt": f"{day}T{hour:02d}:00:00+02:00",
        "buyGrossPlnPerKwh": price,
        "consumption": advice,
    }


def _row(hour, price, advice="neutral", day=28):
    return HourRow(datetime(2026, 6, day, hour, tzinfo=PL), price, advice)


# --- merge_hours ----------------------------------------------------------


def test_merge_hours_concats_today_then_tomorrow_sorted():
    data = {
        "today": {"hours": [_h(23, 0.9), _h(22, 0.8)]},
        "tomorrow": {"hours": [_h(0, 0.5, day="2026-06-29")]},
    }
    rows = merge_hours(data)
    assert [r.start.hour for r in rows] == [22, 23, 0]
    assert rows[0].price == 0.8
    assert rows[2].start.day == 29


def test_merge_hours_skips_junk_and_missing_price():
    data = {"today": {"hours": ["junk", {"startsAt": "bad"}, _h(5, None)]}}
    rows = merge_hours(data)
    assert len(rows) == 1
    assert rows[0].price is None


def test_merge_hours_handles_empty_and_none():
    assert merge_hours(None) == []
    assert merge_hours({}) == []
    assert merge_hours({"today": {"hours": None}}) == []


# --- cheapest_window ------------------------------------------------------


def test_cheapest_window_picks_two_cheapest_before_deadline():
    now = datetime(2026, 6, 28, 21, 30, tzinfo=PL)
    hours = [
        _row(22, 0.4),
        _row(23, 0.7),
        _row(0, 0.3, day=29),
        _row(5, 0.2, day=29),
    ]
    res = plan_run(
        mode=MODE_CHEAPEST_WINDOW,
        now=now,
        hours=hours,
        ready_by=time(6, 0),
        duration_h=2,
    )
    assert sorted(s.hour for s in res.selected_starts) == [0, 5]
    assert res.planned_start.hour == 0
    assert res.run_now is False


def test_cheapest_window_ignores_stop_at():
    # ready_by bounds the window; a (stale) stop_at must not clip cheapest_window.
    now = datetime(2026, 6, 28, 21, 30, tzinfo=PL)
    hours = [_row(22, 0.4), _row(23, 0.7), _row(0, 0.3, day=29)]
    res = plan_run(
        mode=MODE_CHEAPEST_WINDOW,
        now=now,
        hours=hours,
        ready_by=time(6, 0),
        stop_at=time(23, 0),  # would clip to before 23:00 if honoured
        duration_h=2,
    )
    assert sorted(s.hour for s in res.selected_starts) == [0, 22]


def test_cheapest_window_run_now_true_when_current_hour_selected():
    now = datetime(2026, 6, 29, 5, 10, tzinfo=PL)
    hours = [_row(5, 0.2, day=29), _row(6, 0.9, day=29)]
    res = plan_run(
        mode=MODE_CHEAPEST_WINDOW,
        now=now,
        hours=hours,
        ready_by=time(8, 0),
        duration_h=1,
    )
    assert res.run_now is True
    assert res.selected_count == 1


def test_cheapest_window_empty_pool_returns_blank():
    now = datetime(2026, 6, 28, 21, 30, tzinfo=PL)
    res = plan_run(
        mode=MODE_CHEAPEST_WINDOW,
        now=now,
        hours=[],
        ready_by=time(6, 0),
        duration_h=2,
    )
    assert res.selected_starts == ()
    assert res.planned_start is None
    assert res.run_now is False


# --- fixed ----------------------------------------------------------------


def test_fixed_single_hour_block():
    now = datetime(2026, 6, 28, 20, 0, tzinfo=PL)
    res = plan_run(mode=MODE_FIXED, now=now, hours=[], start_at=time(22, 0))
    assert res.planned_start.hour == 22
    assert res.run_now is False


def test_fixed_block_with_stop_runs_now_inside():
    now = datetime(2026, 6, 28, 5, 30, tzinfo=PL)
    res = plan_run(
        mode=MODE_FIXED, now=now, hours=[], start_at=time(5, 0), stop_at=time(7, 0)
    )
    assert res.run_now is True
    assert sorted(s.hour for s in res.selected_starts) == [5, 6]


def test_fixed_overnight_block_crosses_midnight():
    now = datetime(2026, 6, 28, 23, 30, tzinfo=PL)
    res = plan_run(
        mode=MODE_FIXED, now=now, hours=[], start_at=time(22, 0), stop_at=time(6, 0)
    )
    assert res.run_now is True


# --- price_below / advice_use --------------------------------------------


def test_price_below_selects_cheap_upcoming_hours():
    now = datetime(2026, 6, 28, 12, 0, tzinfo=PL)
    hours = [_row(12, 0.3), _row(13, 0.9), _row(14, 0.25)]
    res = plan_run(mode=MODE_PRICE_BELOW, now=now, hours=hours, price_ceiling=0.5)
    assert sorted(s.hour for s in res.selected_starts) == [12, 14]
    assert res.run_now is True


def test_advice_use_selects_use_hours_only():
    now = datetime(2026, 6, 28, 12, 0, tzinfo=PL)
    hours = [
        _row(12, 0.3, advice="use"),
        _row(13, 0.4, advice="neutral"),
        _row(14, 0.5, advice="use"),
    ]
    res = plan_run(mode=MODE_ADVICE_USE, now=now, hours=hours)
    assert sorted(s.hour for s in res.selected_starts) == [12, 14]


def test_price_below_stop_at_caps_window():
    now = datetime(2026, 6, 28, 3, 0, tzinfo=PL)
    hours = [_row(3, 0.2), _row(5, 0.2), _row(7, 0.2)]
    res = plan_run(
        mode=MODE_PRICE_BELOW,
        now=now,
        hours=hours,
        price_ceiling=0.5,
        stop_at=time(6, 0),
    )
    assert sorted(s.hour for s in res.selected_starts) == [3, 5]


def test_disabled_mode_unknown_returns_blank():
    now = datetime(2026, 6, 28, 12, 0, tzinfo=PL)
    res = plan_run(mode="nonsense", now=now, hours=[_row(12, 0.1)])
    assert res == ScheduleResult()
