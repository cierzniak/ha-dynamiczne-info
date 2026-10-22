"""Diagnostics support for the dynamiczne.info integration."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import DynamiczneInfoConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: DynamiczneInfoConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry. The API is anonymous, so there is
    nothing to redact."""
    coordinator = entry.runtime_data
    return {
        "config": {
            "operator": coordinator.operator,
            "tariff": coordinator.tariff,
            "include_sell": coordinator.include_sell,
            "integration_version": coordinator.integration_version,
        },
        "outlook": coordinator.data,
    }
