"""Choose the next local schedule boundary as an unambiguous UTC instant."""

from datetime import UTC, datetime, time, timedelta


def next_schedule_tick(
    now: datetime,
    *,
    ready_by: time | None,
    start_at: time | None,
    stop_at: time | None,
    selected_starts: tuple[datetime, ...],
) -> datetime:
    """Wake at time controls, selected intervals, midnight, or the next hour."""
    utc_now = now.astimezone(UTC)
    candidates = [
        utc_now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    ]
    for offset in (0, 1):
        day = now.date() + timedelta(days=offset)
        for value in (time(), ready_by, start_at, stop_at):
            if value is None:
                continue
            # Both folds matter on the autumn transition. Reject nonexistent
            # spring times; the next real hour still causes a recomputation.
            for fold in (0, 1):
                local = datetime.combine(day, value, now.tzinfo).replace(fold=fold)
                utc = local.astimezone(UTC)
                if utc.astimezone(now.tzinfo).replace(tzinfo=None) != local.replace(
                    tzinfo=None
                ):
                    continue
                candidates.append(utc)
                if value == start_at and stop_at is None:
                    candidates.append(utc + timedelta(hours=1))
    for start in selected_starts:
        candidates.extend(
            (start.astimezone(UTC), start.astimezone(UTC) + timedelta(hours=1))
        )
    return min(candidate for candidate in candidates if candidate > utc_now)
