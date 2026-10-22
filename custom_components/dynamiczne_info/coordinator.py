"""Data update coordinator polling the dynamiczne.info outlook endpoint."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import async_track_utc_time_change
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import DynamiczneInfoApiClient, DynamiczneInfoApiError
from .const import (
    CONF_INCLUDE_SELL,
    CONF_OPERATOR,
    CONF_TARIFF,
    DEFAULT_BASE_URL,
    DOMAIN,
    UPDATE_INTERVAL,
)
from .outlook import extract_today_summary, resolve_current_hour, resolve_now_block

if TYPE_CHECKING:
    from .load_scheduler import LoadScheduler

_LOGGER = logging.getLogger(__name__)

# Newer Home Assistant links a child device through the parent's registry id and
# deprecates the identifier-tuple `via_device` (removed in 2027.8). The minimum
# supported release (2025.3) only knows `via_device`, so pick by what DeviceInfo
# declares.
_VIA_DEVICE_ID = "via_device_id" in DeviceInfo.__annotations__


def load_device_info(
    coordinator: DynamiczneInfoOutlookCoordinator, subentry_id: str, name: str
) -> dict[str, Any]:
    """Device descriptor for a load, linked to its parent tariff device."""
    info: dict[str, Any] = {
        "identifiers": {(DOMAIN, f"load_{subentry_id}")},
        "name": name,
        "manufacturer": "dynamiczne.info",
        "model": "Load scheduler",
    }
    if _VIA_DEVICE_ID:
        info["via_device_id"] = coordinator.device_id
    else:
        info["via_device"] = (DOMAIN, f"{coordinator.operator}_{coordinator.tariff}")
    return info


class DynamiczneInfoOutlookCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetches the outlook once per interval and exposes the current hour."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: DynamiczneInfoApiClient,
        integration_version: str | None = None,
    ) -> None:
        self._client = client
        self.operator: str = entry.data[CONF_OPERATOR]
        self.tariff: str = entry.data[CONF_TARIFF]
        self.include_sell: bool = entry.data.get(CONF_INCLUDE_SELL, True)
        self.integration_version = integration_version
        self.loads: dict[str, LoadScheduler] = {}
        # Registry id of the tariff device, set in async_setup_entry before the
        # platforms load so load devices can name it as their via device.
        self.device_id: str | None = None
        super().__init__(
            hass,
            logger=_LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {self.operator}/{self.tariff}",
            update_interval=UPDATE_INTERVAL,
        )
        entry.async_on_unload(
            async_track_utc_time_change(hass, self._hour_changed, minute=0, second=0)
        )

    @callback
    def _hour_changed(self, _now: Any) -> None:
        """Publish cached values without changing API polling or availability."""
        self.async_update_listeners()

    def device_info(self) -> dict[str, Any]:
        """Shared device descriptor for every entity of this config entry."""
        return {
            "identifiers": {(DOMAIN, f"{self.operator}_{self.tariff}")},
            "name": f"dynamiczne.info {self.operator.upper()} {self.tariff.upper()}",
            "manufacturer": "dynamiczne.info",
            "model": "Godzinowy fixing (RDN)",
            "sw_version": self.integration_version,
            "configuration_url": DEFAULT_BASE_URL,
        }

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self._client.async_get_outlook(
                self.operator, self.tariff, include_sell=self.include_sell
            )
        except DynamiczneInfoApiError as err:
            raise UpdateFailed(str(err)) from err

    def now_block(self) -> dict[str, Any]:
        """Return forward-looking advice evaluated at the current time."""
        return resolve_now_block(self.data, dt_util.utcnow())

    def today_summary(self) -> dict[str, Any]:
        """Return today's aggregate summary (cheapest/dearest hour, counts)."""
        return extract_today_summary(self.data)

    def current_hour(self) -> dict[str, Any] | None:
        """Return the hour row covering 'now' (server-preferred, client fallback)."""
        return resolve_current_hour(self.data, dt_util.utcnow())
