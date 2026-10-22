"""Exercise timer replacement and unload on the real Home Assistant runtime."""

import sys
from datetime import UTC, datetime, time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

pytest.importorskip("homeassistant")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from homeassistant.core import HomeAssistant

from custom_components.dynamiczne_info.load_scheduler import LoadScheduler

MODULE = "custom_components.dynamiczne_info.load_scheduler"


async def test_timer_reschedules_on_changes_and_cancels_on_unload(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    coord = SimpleNamespace(data={}, async_add_listener=Mock(return_value=Mock()))
    cancellations = []

    def track(*_args):
        cancel = Mock()
        cancellations.append(cancel)
        return cancel

    now = datetime(2026, 9, 22, 6, 10, tzinfo=UTC)
    with (
        patch(f"{MODULE}.dt_util.now", return_value=now) as clock,
        patch(f"{MODULE}.async_track_point_in_utc_time", side_effect=track) as timer,
    ):
        load = LoadScheduler(hass, coord, "test-timing", {"mode": "fixed"})
        load.start_at = time(6, 15)
        load.stop_at = time(6, 45)
        stop = load.async_start()
        assert timer.call_args.args[2] == now.replace(minute=15)
        load.set_param("start_at", time(6, 20))
        cancellations[0].assert_called_once()
        assert timer.call_args.args[2] == now.replace(minute=20)

        clock.return_value = now.replace(minute=20)
        timer.call_args.args[1](clock.return_value)
        assert load.result.run_now
        assert timer.call_args.args[2] == now.replace(minute=45)
        clock.return_value = now.replace(minute=45)
        timer.call_args.args[1](clock.return_value)
        assert not load.result.run_now

        stop()
        cancellations[-1].assert_called_once()
        coord.async_add_listener.return_value.assert_called_once()
        calls = timer.call_count
        load.recompute()
        assert timer.call_count == calls
    await hass.async_stop()
