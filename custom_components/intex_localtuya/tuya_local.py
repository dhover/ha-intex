"""Local Tuya device communication via TinyTuya."""
from __future__ import annotations

import asyncio
import logging
import socket
from typing import Any

import tinytuya

from .const import DEFAULT_PROTOCOL_VERSION, SUPPORTED_PROTOCOL_VERSIONS

_LOGGER = logging.getLogger(__name__)

SOCKET_TIMEOUT = 10  # seconds
CONNECTION_RETRY_LIMIT = 1
CONNECTION_RETRY_DELAY = 0


class TuyaLocalDevice:
    """Local Tuya device communicator."""

    def __init__(
        self,
        host: str,
        device_id: str,
        local_key: str,
        protocol_version: str = DEFAULT_PROTOCOL_VERSION,
    ) -> None:
        """Initialize the Tuya local device."""
        self.host = host
        self.device_id = device_id
        self.local_key = local_key
        self.protocol_version = protocol_version
        self._lock = asyncio.Lock()
        self._device = self._create_device()

    def _create_device(self) -> tinytuya.Device:
        """Create and configure the TinyTuya device."""
        version = float(self.protocol_version)
        device = tinytuya.Device(
            dev_id=self.device_id,
            address=self.host,
            local_key=self.local_key,
            version=version,
            persist=False,
            connection_timeout=SOCKET_TIMEOUT,
            connection_retry_limit=CONNECTION_RETRY_LIMIT,
            connection_retry_delay=CONNECTION_RETRY_DELAY,
        )
        device.set_version(version)
        device.set_socketTimeout(SOCKET_TIMEOUT)
        device.set_socketRetryLimit(CONNECTION_RETRY_LIMIT)
        device.set_socketRetryDelay(CONNECTION_RETRY_DELAY)
        return device

    def _set_protocol_version(self, protocol_version: str) -> None:
        """Recreate the TinyTuya device using a new protocol version."""
        if protocol_version == self.protocol_version:
            return

        self._close_device()
        self.protocol_version = protocol_version
        self._device = self._create_device()

    def _alternate_protocol_versions(self) -> list[str]:
        """Return protocol versions to try after the configured one."""
        return [
            version
            for version in SUPPORTED_PROTOCOL_VERSIONS
            if version != self.protocol_version
        ]

    @staticmethod
    def _is_protocol_or_key_error(response: Any) -> bool:
        """Return True when TinyTuya signals a protocol/key mismatch."""
        return (
            isinstance(response, dict)
            and response.get("Err") == "914"
            and response.get("Error") == "Check device key or version"
        )

    def _normalize_status(self, status: Any) -> dict[str, Any] | None:
        """Normalize TinyTuya status responses into a top-level DPS payload."""
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

        return None

    def _try_alternate_protocols_for_status(self) -> dict[str, Any] | None:
        """Retry status reads across common Tuya protocol versions."""
        original_version = self.protocol_version
        saw_protocol_or_key_error = False
        for version in self._alternate_protocol_versions():
            _LOGGER.info(
                "Retrying Tuya status with protocol version %s for %s",
                version,
                self.host,
            )
            self._set_protocol_version(version)
            try:
                status = self._device.status()
            except Exception as err:
                _LOGGER.debug(
                    "Protocol version %s status retry failed: %s",
                    version,
                    err,
                    exc_info=True,
                )
                continue

            _LOGGER.debug(
                "TinyTuya full status response with protocol %s: %r",
                version,
                status,
            )
            if self._is_protocol_or_key_error(status):
                saw_protocol_or_key_error = True
            normalized = self._normalize_status(status)
            if normalized is not None:
                _LOGGER.info(
                    "Tuya protocol version %s works for %s",
                    version,
                    self.host,
                )
                return normalized

        self._set_protocol_version(original_version)
        if saw_protocol_or_key_error:
            _LOGGER.error(
                "All supported Tuya protocol versions failed for %s. "
                "This usually means the Local Key or Device ID is wrong, stale, "
                "or the device firmware no longer supports local Tuya access.",
                self.host,
            )
        return None

    def _try_alternate_protocols_for_set_value(self, dp: str, value: Any) -> bool:
        """Retry write requests across common Tuya protocol versions."""
        original_version = self.protocol_version
        saw_protocol_or_key_error = False
        for version in self._alternate_protocol_versions():
            _LOGGER.info(
                "Retrying Tuya write for DP %s with protocol version %s for %s",
                dp,
                version,
                self.host,
            )
            self._set_protocol_version(version)
            try:
                result = self._device.set_value(int(dp), value)
            except Exception as err:
                _LOGGER.debug(
                    "Protocol version %s write retry failed for DP %s: %s",
                    version,
                    dp,
                    err,
                    exc_info=True,
                )
                continue

            _LOGGER.debug(
                "TinyTuya full set_value response for DP %s with protocol %s: %r",
                dp,
                version,
                result,
            )
            if self._is_protocol_or_key_error(result):
                saw_protocol_or_key_error = True
            if self._is_successful_write(result):
                _LOGGER.info(
                    "Tuya protocol version %s works for writes to %s",
                    version,
                    self.host,
                )
                return True

        self._set_protocol_version(original_version)
        if saw_protocol_or_key_error:
            _LOGGER.error(
                "All supported Tuya protocol versions failed for writes to %s. "
                "This usually means the Local Key or Device ID is wrong, stale, "
                "or the device firmware no longer supports local Tuya access.",
                self.host,
            )
        return False

    @staticmethod
    def _is_successful_write(result: Any) -> bool:
        """Return True if a TinyTuya write response looks successful."""
        return isinstance(result, dict) and (
            result.get("success") is True
            or "dps" in result
            or (isinstance(result.get("data"), dict) and "dps" in result["data"])
            or (not result.get("Error") and not result.get("Err"))
        )

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

        _LOGGER.debug("TinyTuya full status response: %r", status)
        normalized = self._normalize_status(status)
        if normalized is not None:
            return normalized

        if self._is_protocol_or_key_error(status):
            recovered = self._try_alternate_protocols_for_status()
            if recovered is not None:
                return recovered

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

        _LOGGER.debug("TinyTuya full set_value response for DP %s: %r", dp, result)

        if self._is_successful_write(result):
            return True

        if self._is_protocol_or_key_error(result):
            if self._try_alternate_protocols_for_set_value(dp, value):
                return True

        _LOGGER.error("Failed to write DP %s: %s", dp, result)
        self._close_device()
        return False
