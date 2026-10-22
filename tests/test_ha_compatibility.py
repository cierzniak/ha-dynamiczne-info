"""Import all platforms and config flows against the CI Home Assistant matrix."""

import importlib
import sys
from pathlib import Path

import pytest

pytest.importorskip("homeassistant")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.mark.parametrize(
    "module",
    [
        "",
        ".config_flow",
        ".sensor",
        ".binary_sensor",
        ".select",
        ".switch",
        ".time",
        ".number",
        ".diagnostics",
    ],
)
def test_platform_imports(module):
    importlib.import_module(f"custom_components.dynamiczne_info{module}")
