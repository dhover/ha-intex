"""Climate entity for Intex pool heater via Tuya."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_WHOLE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, DP_HEATER, DP_TARGET_TEMP, DP_TEMPERATURE
from .tuya_local import TuyaLocalDevice

_LOGGER = logging.getLogger(__name__)

MIN_TEMP = 20  # Celsius
MAX_TEMP = 40  # Celsius


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up climate entities from a config entry."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    device = data["device"]
    device_id = data["device_id"]
    
    async_add_entities(
        [
            IntexPoolClimate(
                device,
                device_id,
            )
        ]
    )


class IntexPoolClimate(ClimateEntity):
    """Climate entity for Intex pool heater."""

    _attr_has_entity_name = True
    _attr_name = "Heater"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_precision = PRECISION_WHOLE
    _attr_min_temp = MIN_TEMP
    _attr_max_temp = MAX_TEMP
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )

    def __init__(
        self,
        device: TuyaLocalDevice,
        device_id: str,
    ) -> None:
        """Initialize the climate entity."""
        self.device = device
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_heater"
        self._current_temp: float | None = None
        self._target_temp: float | None = None
        self._heater_on: bool = False

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
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._current_temp

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        return self._target_temp

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode."""
        if self._heater_on:
            return HVACMode.HEAT
        return HVACMode.OFF

    @property
    def hvac_action(self) -> HVACAction:
        """Return current HVAC action."""
        if self._heater_on:
            return HVACAction.HEATING
        return HVACAction.OFF

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set target temperature."""
        if ATTR_TEMPERATURE in kwargs:
            self._target_temp = kwargs[ATTR_TEMPERATURE]
            _LOGGER.debug("Set target temperature to %s", self._target_temp)
            await self.device.set_value(DP_TARGET_TEMP, int(self._target_temp))

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        if hvac_mode == HVACMode.HEAT:
            self._heater_on = True
        else:
            self._heater_on = False
        
        _LOGGER.debug("Set HVAC mode to %s", hvac_mode)
        await self.device.set_value(DP_HEATER, self._heater_on)

    async def async_update(self) -> None:
        """Update the entity."""
        status = await self.device.get_status()
        if status and "dps" in status:
            dps = status["dps"]
            _LOGGER.debug("Climate update - Available DPs: %s", dps)
            if DP_TEMPERATURE in dps:
                self._current_temp = float(dps[DP_TEMPERATURE]) / 10
                _LOGGER.debug("Updated current temp from DP %s: %s -> %s°C", DP_TEMPERATURE, dps[DP_TEMPERATURE], self._current_temp)
            if DP_TARGET_TEMP in dps:
                self._target_temp = float(dps[DP_TARGET_TEMP]) / 10
                _LOGGER.debug("Updated target temp from DP %s: %s -> %s°C", DP_TARGET_TEMP, dps[DP_TARGET_TEMP], self._target_temp)
            if DP_HEATER in dps:
                self._heater_on = bool(dps[DP_HEATER])
                _LOGGER.debug("Updated heater state from DP %s: %s", DP_HEATER, self._heater_on)
