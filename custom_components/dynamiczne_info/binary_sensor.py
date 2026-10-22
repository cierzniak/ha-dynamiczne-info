"""Binary sensors: 'sell now' advice and per-load 'run now' signal."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DynamiczneInfoConfigEntry
from .const import SUBENTRY_TYPE_LOAD
from .coordinator import DynamiczneInfoOutlookCoordinator
from .load_entity import LoadSignalEntity
from .load_scheduler import LoadScheduler


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DynamiczneInfoConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the 'sell now' sensor and each load's 'run now' signal."""
    coordinator = entry.runtime_data
    if coordinator.include_sell:
        async_add_entities([DynamiczneInfoSellNowBinarySensor(coordinator)])
    for subentry_id, subentry in entry.subentries.items():
        if subentry.subentry_type != SUBENTRY_TYPE_LOAD:
            continue
        load = coordinator.loads[subentry_id]
        async_add_entities(
            [DynamiczneInfoRunNowBinarySensor(load, subentry.title)],
            config_subentry_id=subentry_id,
        )


class DynamiczneInfoSellNowBinarySensor(
    CoordinatorEntity[DynamiczneInfoOutlookCoordinator], BinarySensorEntity
):
    _attr_has_entity_name = True
    _attr_translation_key = "sell_now"
    _attr_icon = "mdi:battery-arrow-up"

    def __init__(self, coordinator: DynamiczneInfoOutlookCoordinator) -> None:
        super().__init__(coordinator)
        device = f"{coordinator.operator}_{coordinator.tariff}"
        self._attr_unique_id = f"{device}_sell_now"
        self._attr_device_info = coordinator.device_info()

    @property
    def is_on(self) -> bool | None:
        row = self.coordinator.current_hour()
        return None if row is None else bool(row.get("sell"))


class DynamiczneInfoRunNowBinarySensor(LoadSignalEntity, BinarySensorEntity):
    """On while the load should run in the current hour; the blueprint trigger."""

    _attr_translation_key = "run_now"
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_icon = "mdi:play-circle"

    def __init__(self, load: LoadScheduler, name: str) -> None:
        super().__init__(load, name)
        self._attr_unique_id = f"{load.subentry_id}_run_now"

    @property
    def is_on(self) -> bool:
        return self._load.result.run_now
