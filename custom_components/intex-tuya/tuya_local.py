"""Local Tuya device communication via TinyTuya."""
from __future__ import annotations

import asyncio
import logging
import socket
from typing import Any

import tinytuya

_LOGGER = logging.getLogger(__name__)

SOCKET_TIMEOUT = 10  # seconds
CONNECTION_RETRY_LIMIT = 1
CONNECTION_RETRY_DELAY = 0
PROTOCOL_VERSION = 3.4


class TuyaLocalDevice:
    """Local Tuya device communicator."""

    def __init__(self, host: str, device_id: str, local_key: str) -> None:
        """Initialize the Tuya local device."""
        self.host = host
        self.device_id = device_id
        self.local_key = local_key
        self._lock = asyncio.Lock()
        self._device = self._create_device()

    def _create_device(self) -> tinytuya.Device:
        """Create and configure the TinyTuya device."""
        device = tinytuya.Device(
            dev_id=self.device_id,
            address=self.host,
            local_key=self.local_key,
            version=PROTOCOL_VERSION,
            persist=False,
            connection_timeout=SOCKET_TIMEOUT,
            connection_retry_limit=CONNECTION_RETRY_LIMIT,
            connection_retry_delay=CONNECTION_RETRY_DELAY,
        )
        device.set_version(PROTOCOL_VERSION)
        device.set_socketTimeout(SOCKET_TIMEOUT)
        device.set_socketRetryLimit(CONNECTION_RETRY_LIMIT)
        device.set_socketRetryDelay(CONNECTION_RETRY_DELAY)
        return device

    def test_connection(self) -> bool:
        """Test if we can connect to the device (sync version for config flow)."""
        try:
            with socket.create_connection((self.host, 6668), timeout=5):
                return True
        except OSError as err:
            _LOGGER.error("Failed to test connection: %s", err)
            return False

    async def connect(self) -> bool:
        """Validate that the device responds over the configured protocol."""
        status = await self.get_status()
        return status is not None

    async def disconnect(self) -> None:
        """Disconnect from the device."""
        async with self._lock:
            await asyncio.to_thread(self._close_device)

    def _close_device(self) -> None:
        """Close the TinyTuya connection if it is open."""
        close = getattr(self._device, "close", None)
        if callable(close):
            try:
                close()
            except Exception as err:
                _LOGGER.debug("Error closing TinyTuya device: %s", err)

    async def get_status(self) -> dict[str, Any] | None:
        """Get device status."""
        async with self._lock:
            return await asyncio.to_thread(self._get_status_sync)

    def _get_status_sync(self) -> dict[str, Any] | None:
        """Read device status using TinyTuya."""
        try:
            status = self._device.status()
        except Exception as err:
            _LOGGER.error("Error getting device status: %s", err, exc_info=True)
            self._close_device()
            return None

        if not isinstance(status, dict):
            _LOGGER.error("Unexpected status response: %r", status)
            self._close_device()
            return None

        if "dps" in status and isinstance(status["dps"], dict):
            _LOGGER.debug("Device status - DPs: %s", status["dps"])
            return status

        data = status.get("data")
        if isinstance(data, dict) and "dps" in data and isinstance(data["dps"], dict):
            normalized = dict(status)
            normalized["dps"] = data["dps"]
            _LOGGER.debug("Device status - nested DPs: %s", normalized["dps"])
            return normalized

        _LOGGER.error("Failed to read response message: %s", status)
        self._close_device()
        return None

    async def set_value(self, dp: str, value: Any) -> bool:
        """Set a device value."""
        async with self._lock:
            return await asyncio.to_thread(self._set_value_sync, dp, value)

    def _set_value_sync(self, dp: str, value: Any) -> bool:
        """Write a device value using TinyTuya."""
        try:
            result = self._device.set_value(int(dp), value)
        except Exception as err:
            _LOGGER.error("Error setting device value: %s", err, exc_info=True)
            self._close_device()
            return False

        if isinstance(result, dict):
            if result.get("success") is True:
                return True

            if "dps" in result or (
                isinstance(result.get("data"), dict) and "dps" in result["data"]
            ):
                return True

            if not result.get("Error") and not result.get("Err"):
                return True

        _LOGGER.error("Failed to write DP %s: %s", dp, result)
        self._close_device()
        return False
