"""Exercise cycle persistence and restore ordering with Home Assistant's Store."""

import sys
from datetime import datetime, time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

import pytest

pytest.importorskip("homeassistant")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from homeassistant.core import HomeAssistant

from custom_components.dynamiczne_info.load_scheduler import LoadScheduler

MODULE = "custom_components.dynamiczne_info.load_scheduler"
WARSAW = ZoneInfo("Europe/Warsaw")


async def test_budget_survives_storage_reload_and_parameter_restoration(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    now = datetime(2026, 9, 22, 10, tzinfo=WARSAW)
    coord = SimpleNamespace(
        data={
            "today": {
                "hours": [
                    {
                        "startsAt": now.replace(hour=h).isoformat(),
                        "buyGrossPlnPerKwh": h,
                    }
                    for h in (10, 11, 12)
                ]
            }
        },
        async_add_listener=Mock(return_value=Mock()),
    )
    with patch(f"{MODULE}.dt_util.now", return_value=now) as clock:
        load = LoadScheduler(hass, coord, "test-budget", {})
        await load.async_restore()
        load.ready_by = time(16)
        load.duration_h = 1
        stop = load.async_start()
        assert load.result.run_now
        await load.async_save()
        stop()

        restored = LoadScheduler(hass, coord, "test-budget", {})
        await restored.async_restore()
        snapshot = restored._cycle.as_dict()
        # Entity platforms restore individually. No default-parameter plan may
        # overwrite the cycle or publish an "on" while they are still loading.
        restored.recompute()
        assert restored._cycle.as_dict() == snapshot
        assert not restored.result.run_now
        restored.ready_by = time(16)
        restored.duration_h = 1
        clock.return_value = now.replace(hour=11)
        stop_restored = restored.async_start()
        assert not restored.result.run_now
        restored.set_param("enabled", False)
        restored.set_param("enabled", True)
        assert not restored.result.run_now
        await restored.async_save()
        stop_restored()
        coord.async_add_listener.return_value.assert_called()
    await hass.async_stop()
