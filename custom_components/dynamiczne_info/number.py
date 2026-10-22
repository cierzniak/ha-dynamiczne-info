"""Numeric parameters (duration, price ceiling) for each load subentry."""

from __future__ import annotations

import contextlib

from homeassistant.components.number import NumberEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import DynamiczneInfoConfigEntry
from .const import DEFAULT_DURATION, SUBENTRY_TYPE_LOAD
from .coordinator import load_device_info
from .load_scheduler import LoadScheduler


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DynamiczneInfoConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add the duration and price-ceiling numbers for every load subentry."""
    coordinator = entry.runtime_data
    for subentry_id, subentry in entry.subentries.items():
        if subentry.subentry_type != SUBENTRY_TYPE_LOAD:
            continue
        load = coordinator.loads[subentry_id]
        async_add_entities(
            [
                DynamiczneInfoDurationNumber(load, subentry.title),
                DynamiczneInfoPriceCeilingNumber(load, subentry.title),
            ],
            config_subentry_id=subentry_id,
        )


class _DynamiczneInfoLoadNumber(NumberEntity, RestoreEntity):
    _attr_has_entity_name = True
    _param: str
    _default: float

    def __init__(self, load: LoadScheduler, name: str, key: str) -> None:
        self._load = load
        self._attr_unique_id = f"{load.subentry_id}_{key}"
        self._attr_device_info = load_device_info(
            load.coordinator, load.subentry_id, name
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None:
            with contextlib.suppress(TypeError, ValueError):
                setattr(self._load, self._param, self._coerce(float(last.state)))
        self._load.recompute()

    def _coerce(self, value: float) -> float | int:
        return value

    @property
    def native_value(self) -> float:
        return float(getattr(self._load, self._param))

    async def async_set_native_value(self, value: float) -> None:
        self._load.set_param(self._param, self._coerce(value))
        self.async_write_ha_state()


class DynamiczneInfoDurationNumber(_DynamiczneInfoLoadNumber):
    """How many hours the load should run (cheapest_window mode)."""

    _attr_translation_key = "duration"
    _attr_icon = "mdi:timer-sand"
    _attr_native_min_value = 1
    _attr_native_max_value = 12
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "h"
    _param = "duration_h"
    _default = DEFAULT_DURATION

    def __init__(self, load: LoadScheduler, name: str) -> None:
        super().__init__(load, name, "duration")

    def _coerce(self, value: float) -> int:
        return int(value)

    @property
    def native_value(self) -> int:
        return int(self._load.duration_h)


class DynamiczneInfoPriceCeilingNumber(_DynamiczneInfoLoadNumber):
    """Run while the buy price is at or below this ceiling (price_below mode)."""

    _attr_translation_key = "price_ceiling"
    _attr_icon = "mdi:cash"
    _attr_native_min_value = 0
    _attr_native_max_value = 5
    _attr_native_step = 0.05
    _attr_native_unit_of_measurement = "PLN/kWh"
    _param = "price_ceiling"
    _default = 0.0

    def __init__(self, load: LoadScheduler, name: str) -> None:
        super().__init__(load, name, "price_ceiling")

    @property
    def native_value(self) -> float:
        return float(self._load.price_ceiling or 0.0)
