"""Sensor entities for Intex pool values via Tuya."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    DP_ERROR_CODE,
    DP_HVAC_ACTION,
    DP_TARGET_TEMP,
    DP_TEMPERATURE,
)
from .tuya_local import TuyaLocalDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities from a config entry."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    device = data["device"]
    device_id = data["device_id"]

    entities = [
        IntexPoolSensor(
            device,
            device_id,
            DP_TEMPERATURE,
            "Current Temperature",
            SensorDeviceClass.TEMPERATURE,
            UnitOfTemperature.FAHRENHEIT,
        ),
        IntexPoolSensor(
            device,
            device_id,
            DP_TARGET_TEMP,
            "Target Temperature",
            SensorDeviceClass.TEMPERATURE,
            UnitOfTemperature.FAHRENHEIT,
        ),
        IntexPoolSensor(
            device,
            device_id,
            DP_HVAC_ACTION,
            "Heat Indicator",
        ),
        IntexPoolSensor(
            device,
            device_id,
            DP_ERROR_CODE,
            "Error Code",
        ),
    ]

    async_add_entities(entities)


class IntexPoolSensor(SensorEntity):
    """Sensor for pool values."""

    _attr_has_entity_name = True

    def __init__(
        self,
        device: TuyaLocalDevice,
        device_id: str,
        dp: str,
        name: str,
        device_class: SensorDeviceClass | None = None,
        unit: str | None = None,
    ) -> None:
        """Initialize the sensor."""
        self.device = device
        self._device_id = device_id
        self._dp = dp
        self._attr_name = name
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        self._attr_unique_id = f"{device_id}_{dp}"
        self._attr_native_value: Any = None

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": "Intex Pool",
            "manufacturer": "Intex",
            "model": "Smart Pool",
        }

    async def async_update(self) -> None:
        """Update the entity."""
        status = await self.device.get_status()
        if not status or "dps" not in status:
            return

        dps = status["dps"]
        _LOGGER.debug(
            "Sensor %s (%s) update - Available DPs: %s",
            self._attr_name,
            self._dp,
            dps,
        )
        if self._dp in dps:
            raw_value = dps[self._dp]
            self._attr_native_value = raw_value
            _LOGGER.debug("Sensor %s updated: raw=%s", self._attr_name, raw_value)
        else:
            _LOGGER.warning(
                "DP %s not found in response. Available: %s",
                self._dp,
                list(dps.keys()),
            )
