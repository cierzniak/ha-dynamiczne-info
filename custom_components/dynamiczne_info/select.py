"""Mode select for each load subentry."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import DynamiczneInfoConfigEntry
from .const import SUBENTRY_TYPE_LOAD
from .coordinator import load_device_info
from .load_scheduler import LoadScheduler
from .scheduler import MODES


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DynamiczneInfoConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add the mode select for every load subentry."""
    coordinator = entry.runtime_data
    for subentry_id, subentry in entry.subentries.items():
        if subentry.subentry_type != SUBENTRY_TYPE_LOAD:
            continue
        load = coordinator.loads[subentry_id]
        async_add_entities(
            [DynamiczneInfoModeSelect(load, subentry.title)],
            config_subentry_id=subentry_id,
        )


class DynamiczneInfoModeSelect(SelectEntity, RestoreEntity):
    """Which scheduling strategy a load uses."""

    _attr_has_entity_name = True
    _attr_translation_key = "mode"
    _attr_icon = "mdi:tune-variant"
    _attr_options = MODES

    def __init__(self, load: LoadScheduler, name: str) -> None:
        self._load = load
        self._attr_unique_id = f"{load.subentry_id}_mode"
        self._attr_device_info = load_device_info(
            load.coordinator, load.subentry_id, name
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state in MODES:
            self._load.mode = last.state
        self._load.recompute()

    @property
    def current_option(self) -> str:
        return self._load.mode

    async def async_select_option(self, option: str) -> None:
        self._load.set_param("mode", option)
        self.async_write_ha_state()
