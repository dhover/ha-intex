"""The Intex Tuya integration."""
from __future__ import annotations

import logging
from typing import Final

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS
from .tuya_local import TuyaLocalDevice

_LOGGER: logging.Logger = logging.getLogger(__name__)

PLATFORMS: Final = PLATFORMS


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Intex Tuya from a config entry."""

    hass.data.setdefault(DOMAIN, {})
    
    # Create local Tuya device
    device = TuyaLocalDevice(
        host=entry.data.get("host"),
        device_id=entry.data.get("device_id"),
        local_key=entry.data.get("local_key"),
    )
    
    hass.data[DOMAIN][entry.entry_id] = {
        "device": device,
        "host": entry.data.get("host"),
        "device_id": entry.data.get("device_id"),
        "name": entry.data.get(CONF_NAME, "Intex Pool"),
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        device = hass.data[DOMAIN][entry.entry_id].get("device")
        if device:
            await device.disconnect()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
