"""The dynamiczne.info integration."""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components import frontend
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration

from .api import DynamiczneInfoApiClient
from .const import DEFAULT_BASE_URL, DOMAIN, SUBENTRY_TYPE_LOAD
from .coordinator import DynamiczneInfoOutlookCoordinator
from .load_scheduler import LoadScheduler

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.TIME,
]

type DynamiczneInfoConfigEntry = ConfigEntry[DynamiczneInfoOutlookCoordinator]

# This integration is configured only through config entries (no YAML).
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

# The integration serves the bundled card file itself (static path) and then makes
# custom:dynamiczne-info-card available without any manual step. In storage mode it
# registers the file as a Lovelace resource -- the same mechanism HACS cards use --
# so the card loads as part of the dashboard and is reliably defined before cards
# render, including after a restart. add_extra_js_url loads outside the Lovelace
# resource pipeline and races the dashboard on cold starts ("Custom element doesn't
# exist"), so it is only the fallback for YAML mode, where resources are read-only.
CARD_URL = "/dynamiczne_info/dynamiczne-info-card.js"
CARD_PATH = Path(__file__).parent / "frontend" / "dynamiczne-info-card.js"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Serve and register the bundled Lovelace card once, app-wide."""
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(CARD_PATH), False)]
    )
    integration = await async_get_integration(hass, DOMAIN)
    await _async_register_card(hass, str(integration.version))
    return True


async def _async_register_card(hass: HomeAssistant, version: str) -> None:
    """Expose custom:dynamiczne-info-card so it is defined before dashboards render.

    Storage mode: register (or update) the card as a Lovelace resource, keyed on
    the version so updates bust the browser cache. YAML mode (read-only resources)
    or no dashboards component: fall back to a frontend extra module.
    """
    card_url = f"{CARD_URL}?v={version}"
    lovelace = hass.data.get("lovelace")
    resources = getattr(lovelace, "resources", None)

    if getattr(lovelace, "resource_mode", None) != "storage" or resources is None:
        frontend.add_extra_js_url(hass, card_url)
        return

    try:
        if not resources.loaded:
            await resources.async_get_info()
        for item in resources.async_items():
            if str(item.get("url", "")).split("?", 1)[0] != CARD_URL:
                continue
            if item.get("url") != card_url:
                await resources.async_update_item(
                    item["id"], {"res_type": "module", "url": card_url}
                )
            return
        await resources.async_create_item({"res_type": "module", "url": card_url})
    except Exception:  # never break setup over a cosmetic card resource
        _LOGGER.warning(
            "Could not register the Lovelace resource for the card; "
            "falling back to a frontend module",
            exc_info=True,
        )
        frontend.add_extra_js_url(hass, card_url)


async def async_setup_entry(
    hass: HomeAssistant, entry: DynamiczneInfoConfigEntry
) -> bool:
    """Set up dynamiczne.info from a config entry."""
    session = async_get_clientsession(hass)
    client = DynamiczneInfoApiClient(DEFAULT_BASE_URL, session)
    integration = await async_get_integration(hass, DOMAIN)
    coordinator = DynamiczneInfoOutlookCoordinator(
        hass, entry, client, str(integration.version)
    )
    await coordinator.async_config_entry_first_refresh()
    # Register the tariff device up front: load devices link to it by registry
    # id, and the sensor platform that would otherwise create it may load after
    # the load platforms.
    coordinator.device_id = (
        dr.async_get(hass)
        .async_get_or_create(
            config_entry_id=entry.entry_id, **coordinator.device_info()
        )
        .id
    )

    coordinator.loads = {}
    for subentry_id, subentry in entry.subentries.items():
        if subentry.subentry_type != SUBENTRY_TYPE_LOAD:
            continue
        load = LoadScheduler(hass, coordinator, subentry_id, dict(subentry.data))
        coordinator.loads[subentry_id] = load
        await load.async_restore()

    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    for load in coordinator.loads.values():
        entry.async_on_unload(load.async_start())
    return True


async def _async_reload_entry(
    hass: HomeAssistant, entry: DynamiczneInfoConfigEntry
) -> None:
    """Reload so a newly added/removed load subentry materialises its entities."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, entry: DynamiczneInfoConfigEntry
) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        for load in entry.runtime_data.loads.values():
            await load.async_save()
    return unloaded
