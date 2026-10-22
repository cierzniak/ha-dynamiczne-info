"""Advance scheduling cycles through completed slots, midnight, and restarts."""

import json
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from cycle import CheapestCycle
from scheduler import HourRow

WARSAW = ZoneInfo("Europe/Warsaw")


def at(hour, day=22, minute=0):
    return datetime(2026, 9, day, hour, minute, tzinfo=WARSAW)


def rows(*hours):
    return [HourRow(at(hour), float(hour), "use") for hour in hours]


def test_one_hour_budget_is_not_replenished_each_hour():
    cycle = CheapestCycle()
    hours = rows(10, 11, 12, 13, 14, 15)
    running = []
    for hour in range(10, 16):
        result = cycle.plan(at(hour), hours, time(16), 1)
        running.append(result.run_now)
        assert result.selected_count == 1
    assert running == [True, False, False, False, False, False]
    assert result.planned_start is None


def test_restart_retains_spent_budget():
    cycle = CheapestCycle()
    cycle.plan(at(10), rows(10, 11, 12), time(16), 1)
    restored = CheapestCycle.from_dict(json.loads(json.dumps(cycle.as_dict())))
    assert not restored.plan(at(11), rows(11, 12), time(16), 1).run_now


def test_midnight_does_not_replenish_overnight_cycle():
    cycle = CheapestCycle()
    cycle.plan(at(23), rows(23), time(6), 1)
    hours = [HourRow(at(0, day=23), 0.01, "use")]
    result = cycle.plan(at(0, day=23), hours, time(6), 1)
    assert not result.run_now
    assert result.selected_count == 1


def test_new_forecast_can_only_optimize_remaining_slots():
    cycle = CheapestCycle()
    cycle.plan(at(10), rows(10, 11, 12), time(16), 2)
    hours = [HourRow(at(12), 0.01, "use"), *rows(10, 11)]
    result = cycle.plan(at(10, minute=30), hours, time(16), 2)
    assert [start.astimezone(WARSAW).hour for start in result.selected_starts] == [
        10,
        12,
    ]
    assert not cycle.plan(at(11), hours, time(16), 2).run_now
    assert cycle.plan(at(12), hours, time(16), 2).run_now
    assert not cycle.plan(at(13), hours + rows(13), time(16), 2).run_now


def test_next_cycle_gets_a_new_budget():
    cycle = CheapestCycle()
    cycle.plan(at(10), rows(10), time(16), 1)
    assert cycle.plan(at(16), rows(16), time(16), 1).run_now


def test_no_deadline_resets_at_midnight():
    cycle = CheapestCycle()
    cycle.plan(at(23), rows(23), None, 1)
    next_day = [HourRow(at(0, day=23), 0.1, "use")]
    assert cycle.plan(at(0, day=23), next_day, None, 1).run_now


def test_missing_prices_do_not_spend_budget():
    cycle = CheapestCycle()
    assert not cycle.plan(at(10), [], time(16), 1).run_now
    assert cycle.plan(at(11), rows(11), time(16), 1).run_now


def test_parameter_change_starts_a_new_cycle():
    cycle = CheapestCycle()
    cycle.plan(at(10), rows(10), time(16), 1)
    assert cycle.plan(at(11), rows(11), time(16), 2).run_now


def test_partial_final_hour_cannot_overrun_deadline():
    cycle = CheapestCycle()
    result = cycle.plan(at(10), rows(10, 11), time(11, 30), 2)
    assert result.selected_count == 1
    assert all(
        start + timedelta(hours=1) <= cycle.end for start in result.selected_starts
    )


def test_dst_repeated_hours_have_separate_budgets():
    first = datetime.fromisoformat("2026-10-25T02:00:00+02:00")
    second = datetime.fromisoformat("2026-10-25T02:00:00+01:00")
    hours = [HourRow(first, 0.1, "use"), HourRow(second, 0.2, "use")]
    cycle = CheapestCycle()
    assert cycle.plan(first.astimezone(WARSAW), hours, time(6), 1).run_now
    assert not cycle.plan(second.astimezone(WARSAW), hours, time(6), 1).run_now
