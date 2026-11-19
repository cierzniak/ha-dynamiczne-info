"""Unit tests for the thin dynamiczne.info API client (no Home Assistant required)."""

from typing import Any

import pytest
from api import (
    DynamiczneInfoApiClient,
    DynamiczneInfoApiError,
    DynamiczneInfoAuthError,
)


class _FakeResponse:
    def __init__(self, status: int, payload: Any) -> None:
        self.status = status
        self._payload = payload
        self.headers: dict[str, str] = {"Retry-After": "30"}

    def raise_for_status(self) -> None:
        if self.status >= 400:
            raise AssertionError("raise_for_status called on an error status")

    async def json(self) -> Any:
        return self._payload


class _FakeGet:
    def __init__(self, response: _FakeResponse) -> None:
        self._response = response

    async def __aenter__(self) -> _FakeResponse:
        return self._response

    async def __aexit__(self, *_exc: object) -> bool:
        return False


class _FakeSession:
    def __init__(self, response: _FakeResponse) -> None:
        self._response = response
        self.calls: list[tuple[str, dict[str, str] | None]] = []
        self.headers: list[dict[str, str] | None] = []

    def get(
        self,
        url: str,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        timeout: Any = None,
    ) -> _FakeGet:
        self.calls.append((url, params))
        self.headers.append(headers)
        return _FakeGet(self._response)


def _client(
    status: int, payload: Any, token: str | None = None
) -> tuple[DynamiczneInfoApiClient, _FakeSession]:
    session = _FakeSession(_FakeResponse(status, payload))
    return DynamiczneInfoApiClient("https://example.test/", session, token), session


async def test_token_sent_as_bearer_header() -> None:
    client, session = _client(200, {"data": []}, token="dyn_abc")
    await client.async_list_operators()
    assert session.headers[0] == {"Authorization": "Bearer dyn_abc"}


async def test_no_token_sends_no_auth_header() -> None:
    client, session = _client(200, {"data": []})
    await client.async_list_operators()
    assert session.headers[0] is None


async def test_401_raises_auth_error() -> None:
    client, _ = _client(401, {}, token="dyn_bad")
    with pytest.raises(DynamiczneInfoAuthError):
        await client.async_list_operators()


async def test_429_raises_api_error_with_retry_after() -> None:
    client, _ = _client(429, {})
    with pytest.raises(DynamiczneInfoApiError, match="30"):
        await client.async_list_operators()


async def test_get_outlook_unwraps_data_and_passes_sell_true() -> None:
    payload = {"data": {"operator": "energa", "today": {"hours": []}}, "meta": {}}
    client, session = _client(200, payload)
    data = await client.async_get_outlook("energa", "g11f", include_sell=True)
    assert data["operator"] == "energa"
    assert session.calls[0][0] == "https://example.test/api/v1/outlook/energa/g11f"
    assert session.calls[0][1] == {"sell": "true"}


async def test_get_outlook_sell_false_param() -> None:
    payload = {"data": {"operator": "pge"}}
    client, session = _client(200, payload)
    await client.async_get_outlook("pge", "g12", include_sell=False)
    assert session.calls[0][1] == {"sell": "false"}


async def test_get_outlook_404_raises() -> None:
    client, _ = _client(404, {})
    with pytest.raises(DynamiczneInfoApiError):
        await client.async_get_outlook("x", "y", include_sell=False)


async def test_get_outlook_missing_data_raises() -> None:
    client, _ = _client(200, {"meta": {}})
    with pytest.raises(DynamiczneInfoApiError):
        await client.async_get_outlook("energa", "g11f", include_sell=True)


async def test_list_operators_filters_non_dicts() -> None:
    payload = {"data": [{"code": "energa", "name": "Energa"}, "junk", {"code": "pge"}]}
    client, _ = _client(200, payload)
    operators = await client.async_list_operators()
    assert [op["code"] for op in operators] == ["energa", "pge"]


async def test_list_tariffs_extracts_codes() -> None:
    payload = {"data": [{"code": "g11"}, {"nope": 1}, {"code": "g12"}]}
    client, _ = _client(200, payload)
    assert await client.async_list_tariffs("energa") == ["g11", "g12"]
