"""Shared base for read-only load entities driven by a dispatcher signal."""

from __future__ import annotations

from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .coordinator import load_device_info
from .load_scheduler import LoadScheduler


class LoadSignalEntity(Entity):
    """Refreshes when its LoadScheduler dispatches; shows the load as a device."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, load: LoadScheduler, name: str) -> None:
        self._load = load
        self._attr_device_info = load_device_info(
            load.coordinator, load.subentry_id, name
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self._load.signal, self.async_write_ha_state
            )
        )
