"""Link load devices to the tariff device with keys the running HA accepts."""

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

pytest.importorskip("homeassistant")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import frame

from custom_components.dynamiczne_info.const import DOMAIN
from custom_components.dynamiczne_info.coordinator import load_device_info


def _coordinator(device_id=None):
    return SimpleNamespace(operator="pge", tariff="g11", device_id=device_id)


def test_load_device_info_uses_only_supported_keys():
    info = load_device_info(_coordinator("parent-id"), "sub", "Ladowarka")
    assert set(info) <= set(dr.DeviceInfo.__annotations__)


async def test_load_device_is_linked_to_tariff_device(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    entry = Mock(entry_id="entry", domain=DOMAIN, subentries={"sub": Mock()})
    hass.config_entries = Mock(async_get_entry=Mock(return_value=entry))
    # Older releases set these helpers up implicitly and lack the functions.
    for helper in (frame, dr):
        if hasattr(helper, "async_setup"):
            helper.async_setup(hass)
    await dr.async_load(hass)
    registry = dr.async_get(hass)

    parent = registry.async_get_or_create(
        config_entry_id="entry", identifiers={(DOMAIN, "pge_g11")}, name="Taryfa"
    )
    child = registry.async_get_or_create(
        config_entry_id="entry",
        config_subentry_id="sub",
        **load_device_info(_coordinator(parent.id), "sub", "Ladowarka"),
    )

    assert child.via_device_id == parent.id
    await hass.async_stop()
