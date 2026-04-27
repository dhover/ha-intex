"""Switch entities for Intex pool via Tuya."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, DP_BUBBLES, DP_FILTER, DP_POWER
from .tuya_local import TuyaLocalDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch entities from a config entry."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    device = data["device"]
    device_id = data["device_id"]

    entities = [
        IntexPoolSwitch(device, device_id, DP_POWER, "Power"),
        IntexPoolSwitch(device, device_id, DP_FILTER, "Filter"),
        IntexPoolSwitch(device, device_id, DP_BUBBLES, "Bubbles"),
    ]

    async_add_entities(entities)


class IntexPoolSwitch(SwitchEntity):
    """Switch entity for pool controls."""

    _attr_has_entity_name = True

    def __init__(
        self,
        device: TuyaLocalDevice,
        device_id: str,
        dp: str,
        name: str,
    ) -> None:
        """Initialize the switch."""
        self.device = device
        self._device_id = device_id
        self._dp = dp
        self._attr_name = name
        self._attr_unique_id = f"{device_id}_{dp}"
        self._is_on = False

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": "Intex Pool",
            "manufacturer": "Intex",
            "model": "Smart Pool",
        }

    @property
    def is_on(self) -> bool:
        """Return True if the switch is on."""
        return self._is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        self._is_on = True
        _LOGGER.debug("Turned on switch %s", self._dp)
        await self.device.set_value(self._dp, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        self._is_on = False
        _LOGGER.debug("Turned off switch %s", self._dp)
        await self.device.set_value(self._dp, False)

    async def async_update(self) -> None:
        """Update the entity."""
        status = await self.device.get_status()
        if status and "dps" in status:
            dps = status["dps"]
            _LOGGER.debug("Switch %s update - Available DPs: %s", self._dp, dps)
            if self._dp in dps:
                self._is_on = bool(dps[self._dp])
                _LOGGER.debug("Switch %s state updated: %s", self._dp, self._is_on)
            else:
                _LOGGER.warning("DP %s not found in response. Available: %s", self._dp, list(dps.keys()))
