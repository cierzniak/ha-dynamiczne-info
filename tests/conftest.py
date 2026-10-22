"""Make the dependency-free integration modules importable without Home Assistant.

``outlook`` and ``api`` carry no Home Assistant imports, so adding the component
directory to ``sys.path`` lets the tests import them as top-level modules without
triggering the package ``__init__`` (which does pull in homeassistant).
"""

import sys
from pathlib import Path

_COMPONENT = (
    Path(__file__).resolve().parents[1] / "custom_components" / "dynamiczne_info"
)
sys.path.insert(0, str(_COMPONENT))
