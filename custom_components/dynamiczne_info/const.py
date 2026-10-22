"""Constants for the dynamiczne.info integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

from .scheduler import MODE_CHEAPEST_WINDOW

DOMAIN: Final = "dynamiczne_info"

CONF_OPERATOR: Final = "operator"
CONF_TARIFF: Final = "tariff"
CONF_INCLUDE_SELL: Final = "include_sell"

# Load scheduler (config subentries on each operator/tariff entry).
CONF_LOAD_NAME: Final = "name"
CONF_MODE: Final = "mode"
SUBENTRY_TYPE_LOAD: Final = "load"
# Dispatcher signal prefix; the full signal is f"{SIGNAL_LOAD}_{subentry_id}".
SIGNAL_LOAD: Final = "dynamiczne_info_load"

DEFAULT_MODE: Final = MODE_CHEAPEST_WINDOW
DEFAULT_DURATION: Final = 3

# The public API runs on a single fixed host; there is nothing to configure.
DEFAULT_BASE_URL: Final = "https://dynamiczne.info"
DEFAULT_INCLUDE_SELL: Final = True

# Day-ahead prices change at most daily; tomorrow is published in the early
# afternoon. Poll every 30 min for newly published prices; a local hour-boundary
# callback updates current values from the cache without another API request.
UPDATE_INTERVAL: Final = timedelta(minutes=30)

# Consumption advice values mirrored from the API (AdviceLevel).
ADVICE_USE: Final = "use"
ADVICE_NEUTRAL: Final = "neutral"
ADVICE_LIMIT: Final = "limit"
ADVICE_OPTIONS: Final = [ADVICE_USE, ADVICE_NEUTRAL, ADVICE_LIMIT]
