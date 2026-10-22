"""Thin async client for the dynamiczne.info public REST API (ADR 0030/0031)."""

from __future__ import annotations

from typing import Any

from aiohttp import ClientError, ClientSession, ClientTimeout

_TIMEOUT = ClientTimeout(total=20)


class DynamiczneInfoApiError(Exception):
    """Raised when the dynamiczne.info API cannot be reached or returns an error."""


class DynamiczneInfoApiClient:
    """Calls the public, anonymous dynamiczne.info API."""

    def __init__(self, base_url: str, session: ClientSession) -> None:
        self._base_url = base_url.rstrip("/")
        self._session = session

    async def async_list_operators(self) -> list[dict[str, str]]:
        """Return the supported distribution operators (code + name)."""
        payload = await self._get("/api/v1/operators")
        data = payload.get("data", [])
        return [op for op in data if isinstance(op, dict)]

    async def async_list_tariffs(self, operator: str) -> list[str]:
        """Return the tariff codes available for the given operator."""
        payload = await self._get(f"/api/v1/operators/{operator}/tariffs")
        data = payload.get("data", [])
        return [row["code"] for row in data if isinstance(row, dict) and "code" in row]

    async def async_get_outlook(
        self, operator: str, tariff: str, *, include_sell: bool
    ) -> dict[str, Any]:
        """Return the today + tomorrow outlook with per-hour advice."""
        sell = "true" if include_sell else "false"
        payload = await self._get(
            f"/api/v1/outlook/{operator}/{tariff}", params={"sell": sell}
        )
        data = payload.get("data")
        if not isinstance(data, dict):
            raise DynamiczneInfoApiError("Outlook response missing 'data' object")
        return data

    async def _get(
        self, path: str, params: dict[str, str] | None = None
    ) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        try:
            async with self._session.get(
                url, params=params, timeout=_TIMEOUT
            ) as response:
                if response.status == 404:
                    raise DynamiczneInfoApiError(f"Not found: {path}")
                response.raise_for_status()
                body = await response.json()
        except ClientError as err:
            raise DynamiczneInfoApiError(f"Request to {url} failed: {err}") from err
        if not isinstance(body, dict):
            raise DynamiczneInfoApiError(f"Unexpected response shape from {path}")
        return body
