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

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate the input
            try:
                await self.hass.async_add_executor_job(
                    self._validate_input, user_input
                )
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

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME): str,
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_DEVICE_ID): str,
                vol.Required(CONF_LOCAL_KEY): str,
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    def _validate_input(self, user_input: dict[str, Any]) -> None:
        """Validate the user input allows us to connect.

        Data has the host, device_id, and local_key entered.
        """
        device = TuyaLocalDevice(
            host=user_input[CONF_HOST],
            device_id=user_input[CONF_DEVICE_ID],
            local_key=user_input[CONF_LOCAL_KEY],
        )
        # Test connection
        if not device.test_connection():
            raise ConnectionError("Unable to connect to device")
