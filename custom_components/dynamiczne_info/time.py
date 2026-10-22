"""Time-of-day parameters (ready_by, start_at, stop_at) for each load."""

from __future__ import annotations

from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from . import DynamiczneInfoConfigEntry
from .const import SUBENTRY_TYPE_LOAD
from .coordinator import load_device_info
from .load_scheduler import LoadScheduler


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DynamiczneInfoConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add the ready_by/start_at/stop_at times for every load subentry."""
    coordinator = entry.runtime_data
    for subentry_id, subentry in entry.subentries.items():
        if subentry.subentry_type != SUBENTRY_TYPE_LOAD:
            continue
        load = coordinator.loads[subentry_id]
        async_add_entities(
            [
                DynamiczneInfoLoadTime(
                    load, subentry.title, "ready_by", "mdi:clock-end"
                ),
                DynamiczneInfoLoadTime(
                    load, subentry.title, "start_at", "mdi:clock-start"
                ),
                DynamiczneInfoLoadTime(
                    load, subentry.title, "stop_at", "mdi:clock-remove"
                ),
            ],
            config_subentry_id=subentry_id,
        )


class DynamiczneInfoLoadTime(TimeEntity, RestoreEntity):
    """A single time-of-day parameter mapped onto a LoadScheduler attribute."""

    _attr_has_entity_name = True

    def __init__(self, load: LoadScheduler, name: str, param: str, icon: str) -> None:
        self._load = load
        self._param = param
        self._attr_translation_key = param
        self._attr_icon = icon
        self._attr_unique_id = f"{load.subentry_id}_{param}"
        self._attr_device_info = load_device_info(
            load.coordinator, load.subentry_id, name
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None:
            parsed = dt_util.parse_time(last.state)
            if parsed is not None:
                setattr(self._load, self._param, parsed)
        self._load.recompute()

    @property
    def native_value(self) -> time | None:
        return getattr(self._load, self._param)

    async def async_set_value(self, value: time) -> None:
        self._load.set_param(self._param, value)
        self.async_write_ha_state()
