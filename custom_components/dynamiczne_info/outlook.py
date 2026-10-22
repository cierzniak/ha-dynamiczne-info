"""Pure helpers for reading the dynamiczne.info outlook payload.

Deliberately free of any Home Assistant import so the parsing/selection logic
can be unit-tested without spinning up a hass instance - the HA-coupled glue
(coordinator, entities) delegates here.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any


def parse_iso(value: Any) -> datetime | None:
    """Parse an ISO 8601 ``startsAt`` into a timezone-aware datetime, or None."""
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def extract_now_block(data: dict[str, Any] | None) -> dict[str, Any]:
    """Return the server-computed forward-looking ``now`` block (may be empty)."""
    block = (data or {}).get("now")
    return block if isinstance(block, dict) else {}


def extract_today_summary(data: dict[str, Any] | None) -> dict[str, Any]:
    """Return today's aggregate summary (cheapest/dearest hour, counts)."""
    today = (data or {}).get("today") or {}
    summary = today.get("summary")
    return summary if isinstance(summary, dict) else {}


def resolve_current_hour(
    data: dict[str, Any] | None, now: datetime
) -> dict[str, Any] | None:
    """Return the hour row covering ``now``.

    Use the server row only while its interval covers now. Cached today and
    tomorrow rows keep values correct across hour and midnight boundaries.
    """
    server = extract_now_block(data).get("hour")
    if isinstance(server, dict):
        start = parse_iso(server.get("startsAt"))
        if start is not None and start <= now < start + timedelta(hours=1):
            return server

    for row in _hour_rows(data):
        start = parse_iso(row.get("startsAt"))
        if start is not None and start <= now < start + timedelta(hours=1):
            return row
    return None


def _hour_rows(data: dict[str, Any] | None) -> list[dict[str, Any]]:
    rows = []
    for key in ("today", "tomorrow"):
        day = (data or {}).get(key)
        hours = day.get("hours") if isinstance(day, dict) else None
        if isinstance(hours, list):
            rows.extend(row for row in hours if isinstance(row, dict))
    return rows


def resolve_now_block(data: dict[str, Any] | None, now: datetime) -> dict[str, Any]:
    """Derive forward-looking advice from cached rows without an API request."""
    upcoming = []
    for row in _hour_rows(data):
        start = parse_iso(row.get("startsAt"))
        if start is not None and start > now:
            upcoming.append((start, row))
    upcoming.sort(key=lambda item: item[0])
    return {
        **extract_now_block(data),
        "hour": resolve_current_hour(data, now),
        "nextCheapHour": next(
            (row for _, row in upcoming if row.get("consumption") == "use"), None
        ),
        "nextSellHour": next(
            (row for _, row in upcoming if row.get("sell") is True), None
        ),
    }
