"""Persist the hourly-slot budget of a cheapest-hours scheduling cycle."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, time, timedelta
from typing import Any

try:
    from .outlook import parse_iso
    from .scheduler import HourRow, ScheduleResult
except ImportError:  # dependency-free unit tests
    from outlook import parse_iso
    from scheduler import HourRow, ScheduleResult


@dataclass
class CheapestCycle:
    """Retain started slots; optimize only the remaining budget on price updates.

    A slot already selected when it starts consumes one unit, even if HA was
    offline or the load was disabled. This conservative accounting cannot grant
    extra runtime after a restart. Changing duration/deadline starts a new cycle.
    """

    end: datetime | None = None
    deadline: str | None = None
    duration: int = 0
    selected: list[HourRow] = field(default_factory=list)

    def plan(
        self, now: datetime, hours: list[HourRow], ready_by: time | None, duration: int
    ) -> ScheduleResult:
        boundary = ready_by or time()
        deadline = boundary.isoformat()
        utc_now = now.astimezone(UTC)
        if (
            self.end is None
            or utc_now >= self.end
            or self.deadline != deadline
            or self.duration != duration
        ):
            end = now.replace(
                hour=boundary.hour,
                minute=boundary.minute,
                second=boundary.second,
                microsecond=0,
            )
            if end.astimezone(UTC) <= utc_now:
                end += timedelta(days=1)
            self.end = end.astimezone(UTC)
            self.deadline = deadline
            self.duration = duration
            self.selected = []

        committed = {row.start: row for row in self.selected if row.start <= utc_now}
        # A new forecast may improve future slots, but never replenish used ones.
        floor = now.replace(minute=0, second=0, microsecond=0).astimezone(UTC)
        pool = {}
        for row in hours:
            start = row.start.astimezone(UTC)
            if (
                row.price is not None
                and start >= floor
                and start not in committed
                and start + timedelta(hours=1) <= self.end
            ):
                pool[start] = HourRow(start, row.price, row.advice)
        remaining = max(0, duration - len(committed))
        chosen = sorted(pool.values(), key=lambda row: (row.price, row.start))[
            :remaining
        ]
        self.selected = sorted(
            [*committed.values(), *chosen], key=lambda row: row.start
        )
        starts = tuple(row.start for row in self.selected)
        total = sum(row.price for row in self.selected if row.price is not None)
        return ScheduleResult(
            selected_starts=starts,
            planned_start=next(
                (start for start in starts if start + timedelta(hours=1) > utc_now),
                None,
            ),
            run_now=any(
                start <= utc_now < start + timedelta(hours=1) for start in starts
            ),
            total_price=total if starts else None,
            avg_price=total / len(starts) if starts else None,
        )

    def as_dict(self) -> dict[str, Any]:
        """Serialize timestamps explicitly for Home Assistant's storage helper."""
        return {
            "end": self.end.isoformat() if self.end else None,
            "deadline": self.deadline,
            "duration": self.duration,
            "selected": [
                {"startsAt": row.start.isoformat(), "price": row.price}
                for row in self.selected
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> CheapestCycle:
        """Restore our versioned storage payload; tolerate absent initial data."""
        if not data:
            return cls()
        selected = []
        for row in data.get("selected", []):
            start = parse_iso(row.get("startsAt"))
            if start is not None:
                selected.append(HourRow(start.astimezone(UTC), row.get("price"), None))
        return cls(
            end=parse_iso(data.get("end")),
            deadline=data.get("deadline"),
            duration=data.get("duration", 0),
            selected=selected,
        )
