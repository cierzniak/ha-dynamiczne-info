"""Unit tests for the dependency-free outlook helpers."""

from datetime import UTC, datetime

from outlook import (
    extract_now_block,
    extract_today_summary,
    parse_iso,
    resolve_current_hour,
    resolve_now_block,
)


def _hour(hour: int, advice: str = "use") -> dict:
    return {
        "hour": hour,
        "startsAt": f"2026-06-10T{hour:02d}:00:00+02:00",
        "buyGrossPlnPerKwh": round(0.1 * hour, 4),
        "consumption": advice,
        "sell": False,
    }


def test_parse_iso_keeps_offset() -> None:
    parsed = parse_iso("2026-06-10T14:00:00+02:00")
    assert parsed is not None
    assert parsed.utcoffset() is not None
    assert parsed.utcoffset().total_seconds() == 7200


def test_parse_iso_assumes_utc_when_naive() -> None:
    parsed = parse_iso("2026-06-10T14:00:00")
    assert parsed is not None
    assert parsed.tzinfo is UTC


def test_parse_iso_rejects_garbage() -> None:
    assert parse_iso("not-a-date") is None
    assert parse_iso(None) is None
    assert parse_iso(123) is None


def test_extract_now_block_defaults() -> None:
    assert extract_now_block(None) == {}
    assert extract_now_block({"now": "oops"}) == {}
    assert extract_now_block({"now": {"hour": {}}}) == {"hour": {}}


def test_extract_today_summary_defaults() -> None:
    assert extract_today_summary(None) == {}
    assert extract_today_summary({"today": {}}) == {}
    assert extract_today_summary({"today": {"summary": {"useHours": 5}}}) == {
        "useHours": 5
    }


def test_resolve_current_hour_prefers_server_now() -> None:
    data = {
        "now": {"hour": {**_hour(14), "marker": "server"}},
        "today": {"hours": [_hour(0)]},
    }
    now = datetime(2026, 6, 10, 12, 30, tzinfo=UTC)
    assert resolve_current_hour(data, now)["marker"] == "server"


def test_resolve_current_hour_falls_back_to_client_scan() -> None:
    data = {"today": {"hours": [_hour(11), _hour(12), _hour(13)]}}
    # 12:00+02:00 starts at 10:00 UTC; 10:30 UTC lands inside hour 12.
    now = datetime(2026, 6, 10, 10, 30, tzinfo=UTC)
    row = resolve_current_hour(data, now)
    assert row is not None
    assert row["hour"] == 12


def test_resolve_current_hour_returns_none_without_match() -> None:
    now = datetime(2026, 6, 10, 23, tzinfo=UTC)
    assert resolve_current_hour({"today": {"hours": [_hour(0)]}}, now) is None
    assert resolve_current_hour(None, now) is None
    assert resolve_current_hour({"today": {}}, now) is None


def test_stale_server_hour_is_replaced_at_boundary():
    data = {"now": {"hour": _hour(10)}, "today": {"hours": [_hour(10), _hour(11)]}}
    assert (
        resolve_current_hour(data, datetime(2026, 6, 10, 9, tzinfo=UTC))["hour"] == 11
    )


def test_midnight_uses_cached_tomorrow():
    row = {**_hour(0), "startsAt": "2026-06-11T00:00:00+02:00"}
    data = {"now": {"hour": _hour(23)}, "tomorrow": {"hours": [row]}}
    now = datetime(2026, 6, 10, 22, tzinfo=UTC)
    assert resolve_current_hour(data, now) == row
    assert resolve_current_hour(data, now.replace(day=12)) is None


def test_missing_server_timestamp_does_not_override_current_row():
    data = {"now": {"hour": {"hour": 10}}, "today": {"hours": [_hour(11)]}}
    assert (
        resolve_current_hour(data, datetime(2026, 6, 10, 9, tzinfo=UTC))["hour"] == 11
    )


def test_upcoming_advice_advances_without_fetching():
    data = {"today": {"hours": [_hour(10), _hour(11), {**_hour(12), "sell": True}]}}
    now = datetime(2026, 6, 10, 9, tzinfo=UTC)
    block = resolve_now_block(data, now)
    assert block["hour"]["hour"] == 11
    assert block["nextCheapHour"]["hour"] == 12
    assert block["nextSellHour"]["hour"] == 12
    block = resolve_now_block(data, now.replace(hour=10))
    assert block["nextCheapHour"] is None
    assert block["nextSellHour"] is None


def test_repeated_dst_hours_are_distinct_instants():
    first = {"startsAt": "2026-10-25T02:00:00+02:00", "buyGrossPlnPerKwh": 0.1}
    second = {"startsAt": "2026-10-25T02:00:00+01:00", "buyGrossPlnPerKwh": 0.9}
    data = {"now": {"hour": first}, "today": {"hours": [first, second]}}
    assert (
        resolve_current_hour(data, datetime(2026, 10, 25, 1, 30, tzinfo=UTC)) == second
    )
