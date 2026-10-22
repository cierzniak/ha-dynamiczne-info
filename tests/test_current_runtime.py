"""Publish fresh cached values without resetting failed-fetch availability."""

import sys
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

pytest.importorskip("homeassistant")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from homeassistant.core import HomeAssistant

from custom_components.dynamiczne_info.coordinator import (
    DynamiczneInfoOutlookCoordinator,
)

MODULE = "custom_components.dynamiczne_info.coordinator"


async def test_hour_tick_notifies_without_fetching_or_changing_availability(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    entry = Mock(data={"operator": "pge", "tariff": "g11"})
    client = Mock()
    cancel = Mock()
    with patch(f"{MODULE}.async_track_utc_time_change", return_value=cancel) as track:
        coordinator = DynamiczneInfoOutlookCoordinator(hass, entry, client)
        listener = Mock()
        remove = coordinator.async_add_listener(listener)
        coordinator.last_update_success = False
        track.call_args.args[1](datetime(2026, 9, 22, 11, tzinfo=UTC))
        listener.assert_called_once()
        client.async_get_outlook.assert_not_called()
        assert coordinator.last_update_success is False
        entry.async_on_unload.assert_any_call(cancel)
        remove()
        await coordinator.async_shutdown()
    await hass.async_stop()
