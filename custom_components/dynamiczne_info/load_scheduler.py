"""Per-subentry runtime that turns outlook prices + load params into a plan.

One LoadScheduler exists per ``load`` config subentry. It holds the load's live
parameters (set by the input entities), recomputes the run plan on three events
(hour boundary, price refresh, parameter change), and notifies the output
entities through a dispatcher signal. All scheduling maths is delegated to the
pure ``scheduler`` module.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import time
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DEFAULT_DURATION, DEFAULT_MODE, DOMAIN, SIGNAL_LOAD
from .coordinator import DynamiczneInfoOutlookCoordinator
from .cycle import CheapestCycle
from .schedule_time import next_schedule_tick
from .scheduler import MODE_CHEAPEST_WINDOW, ScheduleResult, merge_hours, plan_run


class LoadScheduler:
    """Holds one load's parameters and recomputes its run plan."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: DynamiczneInfoOutlookCoordinator,
        subentry_id: str,
        data: dict[str, Any],
    ) -> None:
        self.hass = hass
        self.coordinator = coordinator
        self.subentry_id = subentry_id
        self.signal = f"{SIGNAL_LOAD}_{subentry_id}"
        self.enabled: bool = True
        self.mode: str = data.get("mode", DEFAULT_MODE)
        self.ready_by: time | None = None
        self.start_at: time | None = None
        self.stop_at: time | None = None
        self.duration_h: int = DEFAULT_DURATION
        self.price_ceiling: float | None = None
        self.result: ScheduleResult = ScheduleResult()
        self._unsub_tick: Callable[[], None] | None = None
        self._ready = False
        self._cycle = CheapestCycle()
        self._store: Store[dict[str, Any]] = Store(
            hass, 1, f"{DOMAIN}.load_cycle.{subentry_id}"
        )

    async def async_restore(self) -> None:
        """Restore the cycle before input entities finish restoring parameters."""
        self._cycle = CheapestCycle.from_dict(await self._store.async_load())

    async def async_save(self) -> None:
        """Flush the latest budget when the config entry is unloaded."""
        await self._store.async_save(self._cycle.as_dict())

    def async_start(self) -> Callable[[], None]:
        """Subscribe to prices and exact schedule boundaries; return an unsub."""
        self._ready = True
        unsub_coord = self.coordinator.async_add_listener(self.recompute)
        self.recompute()

        def _unsub() -> None:
            self._ready = False
            unsub_coord()
            if self._unsub_tick is not None:
                self._unsub_tick()
                self._unsub_tick = None

        return _unsub

    @callback
    def _tick(self, _now: Any) -> None:
        """Recompute at the next schedule boundary.

        Must stay a callback: an undecorated sync target makes HassJob pick
        HassJobType.Executor, and the dispatcher send in recompute() then runs
        off the event loop, which Home Assistant rejects for a custom
        integration. The plan would be recomputed and never published.
        """
        self._unsub_tick = None
        self.recompute()

    def _schedule_tick(self) -> None:
        """Replace the old timer after a parameter change or price update."""
        if not self._ready:
            return
        if self._unsub_tick is not None:
            self._unsub_tick()
        when = next_schedule_tick(
            dt_util.now(),
            ready_by=self.ready_by,
            start_at=self.start_at,
            stop_at=self.stop_at,
            selected_starts=self.result.selected_starts,
        )
        self._unsub_tick = async_track_point_in_utc_time(self.hass, self._tick, when)

    def set_param(self, name: str, value: Any) -> None:
        """Set a parameter from an input entity and recompute."""
        setattr(self, name, value)
        self.recompute()

    def recompute(self) -> None:
        """Recompute the plan and notify the load's entities."""
        # All restore entities must finish before a default value can create
        # or reset the persisted cycle, or publish a transient run signal.
        if not self._ready:
            return
        if not self.enabled:
            self.result = ScheduleResult()
        elif self.mode == MODE_CHEAPEST_WINDOW:
            before = self._cycle.as_dict()
            self.result = self._cycle.plan(
                dt_util.now(),
                merge_hours(self.coordinator.data),
                self.ready_by,
                self.duration_h,
            )
            if before != self._cycle.as_dict():
                self._store.async_delay_save(self._cycle.as_dict, 1)
        else:
            self.result = plan_run(
                mode=self.mode,
                now=dt_util.now(),
                hours=merge_hours(self.coordinator.data),
                ready_by=self.ready_by,
                start_at=self.start_at,
                stop_at=self.stop_at,
                duration_h=self.duration_h,
                price_ceiling=self.price_ceiling,
            )
        self._schedule_tick()
        async_dispatcher_send(self.hass, self.signal)
