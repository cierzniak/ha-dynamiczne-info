"""Pure scheduling logic for load helpers.

Free of any Home Assistant import (like outlook.py): given outlook hour rows and
a load's parameters, decide which hours the load should run. Unit-tested without
spinning up hass; the HA-coupled runtime (load_scheduler.py) delegates here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from datetime import time as dt_time
from typing import Any

try:  # HA runtime: imported as a package module
    from .outlook import parse_iso
except ImportError:  # tests: component dir is on sys.path
    from outlook import parse_iso

MODE_CHEAPEST_WINDOW = "cheapest_window"
MODE_FIXED = "fixed"
MODE_PRICE_BELOW = "price_below"
MODE_ADVICE_USE = "advice_use"
MODES = [MODE_CHEAPEST_WINDOW, MODE_FIXED, MODE_PRICE_BELOW, MODE_ADVICE_USE]

ADVICE_USE = "use"


@dataclass(frozen=True)
class HourRow:
    """One outlook hour: when it starts, its buy price, its advice level."""

    start: datetime
    price: float | None
    advice: str | None


@dataclass(frozen=True)
class ScheduleResult:
    """The computed plan for a single load."""

    selected_starts: tuple[datetime, ...] = ()
    planned_start: datetime | None = None
    run_now: bool = False
    total_price: float | None = None
    avg_price: float | None = None

    @property
    def selected_count(self) -> int:
        return len(self.selected_starts)


def merge_hours(data: dict[str, Any] | None) -> list[HourRow]:
    """Flatten today+tomorrow outlook hours into a sorted, parsed HourRow list."""
    rows: list[HourRow] = []
    for day_key in ("today", "tomorrow"):
        day = (data or {}).get(day_key) or {}
        hours = day.get("hours")
        if not isinstance(hours, list):
            continue
        for row in hours:
            if not isinstance(row, dict):
                continue
            start = parse_iso(row.get("startsAt"))
            if start is None:
                continue
            price = row.get("buyGrossPlnPerKwh")
            rows.append(
                HourRow(
                    start=start,
                    price=float(price) if isinstance(price, (int, float)) else None,
                    advice=row.get("consumption"),
                )
            )
    rows.sort(key=lambda r: r.start)
    return rows


def _resolve(now: datetime, t: dt_time) -> datetime:
    """Concrete datetime at local time ``t`` in now's tz; if not after now, next day."""
    candidate = now.replace(
        hour=t.hour, minute=t.minute, second=t.second, microsecond=0
    )
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate


def _covers_now(start: datetime, now: datetime) -> bool:
    return start <= now < start + timedelta(hours=1)


def _summary(rows: list[HourRow]) -> tuple[float | None, float | None]:
    prices = [r.price for r in rows if r.price is not None]
    if not prices:
        return None, None
    total = sum(prices)
    return total, total / len(prices)


def _result(selected: list[HourRow], now: datetime) -> ScheduleResult:
    """Assemble a ScheduleResult from the selected rows."""
    selected = sorted(selected, key=lambda r: r.start)
    starts = tuple(r.start for r in selected)
    total, avg = _summary(selected)
    run_now = any(_covers_now(r.start, now) for r in selected)
    planned = next((s for s in starts if s > now), starts[0] if starts else None)
    return ScheduleResult(
        selected_starts=starts,
        planned_start=planned,
        run_now=run_now,
        total_price=total,
        avg_price=avg,
    )


def _resolve_block(
    now: datetime, start_at: dt_time, stop_at: dt_time | None
) -> tuple[datetime, datetime]:
    """Return (start_dt, stop_dt) for the fixed block around now, overnight-aware."""
    start_dt = now.replace(
        hour=start_at.hour,
        minute=start_at.minute,
        second=start_at.second,
        microsecond=0,
    )
    if stop_at is None:
        stop_dt = start_dt + timedelta(hours=1)
    else:
        stop_dt = now.replace(
            hour=stop_at.hour,
            minute=stop_at.minute,
            second=stop_at.second,
            microsecond=0,
        )
        if stop_dt <= start_dt:  # overnight: stop is the next day
            stop_dt += timedelta(days=1)
    if stop_dt <= now:  # whole block already in the past: roll to next day
        start_dt += timedelta(days=1)
        stop_dt += timedelta(days=1)
    # Before today's start, yesterday's overnight block may still be active.
    previous_start = start_dt - timedelta(days=1)
    previous_stop = stop_dt - timedelta(days=1)
    if (
        previous_start.astimezone(UTC)
        <= now.astimezone(UTC)
        < previous_stop.astimezone(UTC)
    ):
        return previous_start, previous_stop
    return start_dt, stop_dt


def _block_hours(
    start_dt: datetime, stop_dt: datetime, hours: list[HourRow]
) -> list[HourRow]:
    """Whole-hour starts within the block; reuse real rows when present."""
    by_start = {r.start: r for r in hours}
    out: list[HourRow] = []
    # Advance elapsed hours, retaining both occurrences of a repeated DST hour.
    cursor = start_dt.astimezone(UTC)
    while cursor < stop_dt.astimezone(UTC):
        local_start = cursor.astimezone(start_dt.tzinfo)
        out.append(by_start.get(cursor, HourRow(local_start, None, None)))
        cursor += timedelta(hours=1)
    return out


def plan_run(
    *,
    mode: str,
    now: datetime,
    hours: list[HourRow],
    ready_by: dt_time | None = None,
    start_at: dt_time | None = None,
    stop_at: dt_time | None = None,
    duration_h: int = 1,
    price_ceiling: float | None = None,
    advice_levels: tuple[str, ...] = (ADVICE_USE,),
) -> ScheduleResult:
    """Pick the hours a load should run, given its mode and parameters."""
    if mode == MODE_CHEAPEST_WINDOW:
        # "ready_by" already bounds the window, so this mode ignores stop_at on
        # purpose (the card does not expose a stop here either).
        end = _resolve(now, ready_by) if ready_by else None
        floor = now.replace(minute=0, second=0, microsecond=0)
        pool = [
            r
            for r in hours
            if r.price is not None
            and r.start >= floor
            and (end is None or r.start < end)
        ]
        pool.sort(key=lambda r: (r.price, r.start))
        return _result(pool[: max(duration_h, 0)], now)

    if mode == MODE_FIXED and start_at is not None:
        start_dt, stop_dt = _resolve_block(now, start_at, stop_at)
        selected = _block_hours(start_dt, stop_dt, hours)
        run_now = (
            start_dt.astimezone(UTC) <= now.astimezone(UTC) < stop_dt.astimezone(UTC)
        )
        starts = tuple(r.start for r in selected)
        total, avg = _summary(selected)
        planned = now if run_now else start_dt
        return ScheduleResult(starts, planned, run_now, total, avg)

    if mode in (MODE_PRICE_BELOW, MODE_ADVICE_USE):
        floor = now.replace(minute=0, second=0, microsecond=0)
        # A stop is a daily cutoff, not a rolling deadline. After it, remain
        # off until the next local day instead of silently extending to tomorrow.
        stop = (
            now.replace(
                hour=stop_at.hour,
                minute=stop_at.minute,
                second=stop_at.second,
                microsecond=0,
            )
            if stop_at
            else None
        )
        if stop is not None and now >= stop:
            return ScheduleResult()

        def _match(r: HourRow) -> bool:
            if mode == MODE_PRICE_BELOW:
                return (
                    price_ceiling is not None
                    and r.price is not None
                    and r.price <= price_ceiling
                )
            return r.advice in advice_levels

        selected = [
            r
            for r in hours
            if r.start >= floor and (stop is None or r.start < stop) and _match(r)
        ]
        return _result(selected, now)

    return ScheduleResult()
