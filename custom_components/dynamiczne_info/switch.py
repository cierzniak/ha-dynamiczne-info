"""Schedule enable switch for each load subentry."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import DynamiczneInfoConfigEntry
from .const import SUBENTRY_TYPE_LOAD
from .coordinator import load_device_info
from .load_scheduler import LoadScheduler


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DynamiczneInfoConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add the schedule switch for every load subentry."""
    coordinator = entry.runtime_data
    for subentry_id, subentry in entry.subentries.items():
        if subentry.subentry_type != SUBENTRY_TYPE_LOAD:
            continue
        load = coordinator.loads[subentry_id]
        async_add_entities(
            [DynamiczneInfoScheduleSwitch(load, subentry.title)],
            config_subentry_id=subentry_id,
        )


class DynamiczneInfoScheduleSwitch(SwitchEntity, RestoreEntity):
    """Master enable for a load's schedule."""

    _attr_has_entity_name = True
    _attr_translation_key = "schedule"
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, load: LoadScheduler, name: str) -> None:
        self._load = load
        self._attr_unique_id = f"{load.subentry_id}_schedule"
        self._attr_device_info = load_device_info(
            load.coordinator, load.subentry_id, name
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        self._load.enabled = last is None or last.state == "on"
        self._load.recompute()

    @property
    def is_on(self) -> bool:
        return self._load.enabled

    async def async_turn_on(self, **_kwargs: Any) -> None:
        self._load.set_param("enabled", True)
        self.async_write_ha_state()

    async def async_turn_off(self, **_kwargs: Any) -> None:
        self._load.set_param("enabled", False)
        self.async_write_ha_state()
