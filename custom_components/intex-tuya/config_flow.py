"""Config flow for Intex Tuya integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_DEVICE_ID, CONF_LOCAL_KEY, DOMAIN
from .tuya_local import TuyaLocalDevice

_LOGGER = logging.getLogger(__name__)


class IntexTuyaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Intex Tuya."""

    VERSION = 1

    @staticmethod
    def _schema() -> vol.Schema:
        """Return the config schema."""
        return vol.Schema(
            {
                vol.Required(CONF_NAME): str,
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_DEVICE_ID): str,
                vol.Required(CONF_LOCAL_KEY): str,
            }
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate the input
            try:
                await self._validate_input(user_input)
            except ConnectionError:
                errors["base"] = "connection_error"
            except Exception as err:
                _LOGGER.exception("Unexpected error validating input: %s", err)
                errors["base"] = "unknown"
            else:
                # Check if entry already exists
                await self.async_set_unique_id(user_input[CONF_DEVICE_ID])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME, user_input[CONF_DEVICE_ID]),
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self._schema(),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle reconfiguration of the integration."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            try:
                await self._validate_input(user_input)
            except ConnectionError:
                errors["base"] = "connection_error"
            except Exception as err:
                _LOGGER.exception("Unexpected error validating input: %s", err)
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(user_input[CONF_DEVICE_ID])
                self._abort_if_unique_id_mismatch(reason="wrong_device")
                self.hass.config_entries.async_update_entry(
                    entry,
                    title=user_input.get(CONF_NAME, user_input[CONF_DEVICE_ID]),
                )
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates=user_input,
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(self._schema(), entry.data),
            errors=errors,
        )

    async def _validate_input(self, user_input: dict[str, Any]) -> None:
        """Validate the user input allows us to connect.

        Data has the host, device_id, and local_key entered.
        """
        device = TuyaLocalDevice(
            host=user_input[CONF_HOST],
            device_id=user_input[CONF_DEVICE_ID],
            local_key=user_input[CONF_LOCAL_KEY],
        )
        try:
            status = await device.get_status()
        finally:
            await device.disconnect()

        if not status or "dps" not in status:
            raise ConnectionError("Unable to connect to device")
