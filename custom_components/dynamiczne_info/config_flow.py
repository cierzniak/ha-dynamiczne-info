"""Config flow for the dynamiczne.info integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import (
    DynamiczneInfoApiClient,
    DynamiczneInfoApiError,
    DynamiczneInfoAuthError,
)
from .const import (
    CONF_API_TOKEN,
    CONF_INCLUDE_SELL,
    CONF_LOAD_NAME,
    CONF_OPERATOR,
    CONF_TARIFF,
    DEFAULT_BASE_URL,
    DEFAULT_INCLUDE_SELL,
    DOMAIN,
    SUBENTRY_TYPE_LOAD,
)


class DynamiczneInfoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Two steps: operator -> tariff + buy/sell mode. The API URL is fixed."""

    VERSION = 1

    def __init__(self) -> None:
        self._operator: str | None = None
        self._operators: list[dict[str, str]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._operator = user_input[CONF_OPERATOR]
            return await self.async_step_tariff()

        try:
            self._operators = await self._client().async_list_operators()
        except DynamiczneInfoApiError:
            return self.async_abort(reason="cannot_connect")

        options = [
            SelectOptionDict(value=op["code"], label=op.get("name", op["code"]))
            for op in self._operators
            if "code" in op
        ]
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_OPERATOR): SelectSelector(
                        SelectSelectorConfig(
                            options=options, mode=SelectSelectorMode.DROPDOWN
                        )
                    )
                }
            ),
        )

    async def async_step_tariff(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        assert self._operator is not None

        if user_input is not None:
            unique_id = f"{self._operator}:{user_input[CONF_TARIFF]}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"dynamiczne.info {self._operator}/{user_input[CONF_TARIFF]}",
                data={
                    CONF_OPERATOR: self._operator,
                    CONF_TARIFF: user_input[CONF_TARIFF],
                    CONF_INCLUDE_SELL: user_input[CONF_INCLUDE_SELL],
                },
            )

        try:
            tariffs = await self._client().async_list_tariffs(self._operator)
        except DynamiczneInfoApiError:
            return self.async_abort(reason="cannot_connect")

        options = [SelectOptionDict(value=code, label=code) for code in tariffs]
        return self.async_show_form(
            step_id="tariff",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_TARIFF): SelectSelector(
                        SelectSelectorConfig(
                            options=options, mode=SelectSelectorMode.DROPDOWN
                        )
                    ),
                    vol.Required(
                        CONF_INCLUDE_SELL, default=DEFAULT_INCLUDE_SELL
                    ): BooleanSelector(),
                }
            ),
        )

    def _client(self) -> DynamiczneInfoApiClient:
        return DynamiczneInfoApiClient(
            DEFAULT_BASE_URL, async_get_clientsession(self.hass)
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return DynamiczneInfoOptionsFlow()

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Loads (EV, boiler, ...) are added as subentries of a tariff entry."""
        return {SUBENTRY_TYPE_LOAD: LoadSubentryFlowHandler}


class DynamiczneInfoOptionsFlow(OptionsFlow):
    """Optional API token; an empty field means anonymous access."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            token = (user_input.get(CONF_API_TOKEN) or "").strip()
            if not token:
                return self.async_create_entry(data={})
            client = DynamiczneInfoApiClient(
                DEFAULT_BASE_URL, async_get_clientsession(self.hass), token
            )
            try:
                await client.async_list_operators()
            except DynamiczneInfoAuthError:
                errors["base"] = "invalid_auth"
            except DynamiczneInfoApiError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(data={CONF_API_TOKEN: token})

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Optional(CONF_API_TOKEN): TextSelector(
                            TextSelectorConfig(type=TextSelectorType.PASSWORD)
                        )
                    }
                ),
                user_input or self.config_entry.options,
            ),
            errors=errors,
            description_placeholders={"token_url": f"{DEFAULT_BASE_URL}/api/token"},
        )


class LoadSubentryFlowHandler(ConfigSubentryFlow):
    """Add a schedulable load (EV charger, boiler, ...) under a tariff entry."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        if user_input is not None:
            # Only the name is asked here; the mode defaults to cheapest_window
            # (LoadScheduler reads data.get("mode", DEFAULT_MODE)) and is changed
            # later via the load's "mode" select entity / the scheduler card.
            return self.async_create_entry(
                title=user_input[CONF_LOAD_NAME], data=user_input
            )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_LOAD_NAME): TextSelector(),
                }
            ),
        )
