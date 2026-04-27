"""Local Tuya device communication."""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import struct
import time
from typing import Any

from Crypto.Cipher import AES

_LOGGER = logging.getLogger(__name__)

# Tuya protocol constants
TUYA_PROTOCOL_VERSION_BYTES = b"3.1"
TUYA_MESSAGE_HEADER_SIZE = 16
TUYA_MESSAGE_SUFFIX_SIZE = 8
HEARTBEAT_INTERVAL = 60  # seconds
SOCKET_TIMEOUT = 10  # seconds


class TuyaLocalDevice:
    """Local Tuya device communicator."""

    def __init__(self, host: str, device_id: str, local_key: str) -> None:
        """Initialize the Tuya local device."""
        self.host = host
        self.device_id = device_id
        self.local_key = local_key
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None
        self.session_id = 0
        self.last_heartbeat = 0
        self._lock = asyncio.Lock()

    def test_connection(self) -> bool:
        """Test if we can connect to the device (sync version for config flow)."""
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((self.host, 6668))
            sock.close()
            return result == 0
        except Exception as err:
            _LOGGER.error("Failed to test connection: %s", err)
            return False

    async def connect(self) -> bool:
        """Connect to the device."""
        try:
            if self.reader and self.writer:
                _LOGGER.debug("Already connected to device at %s", self.host)
                return True
                
            _LOGGER.debug("Attempting to connect to device at %s:6668", self.host)
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, 6668),
                timeout=SOCKET_TIMEOUT,
            )
            _LOGGER.info("Successfully connected to device at %s", self.host)
            
            # Get socket info for debugging
            if self.writer:
                try:
                    sock = self.writer.get_extra_info('socket')
                    if sock:
                        _LOGGER.debug("Socket info: %s", sock.getpeername())
                except Exception as e:
                    _LOGGER.debug("Could not get socket info: %s", e)
            
            return True
        except asyncio.TimeoutError:
            _LOGGER.error("Connection timeout to %s:6668", self.host)
            self.reader = None
            self.writer = None
            return False
        except Exception as err:
            _LOGGER.error("Failed to connect to device: %s", err, exc_info=True)
            self.reader = None
            self.writer = None
            return False

    async def disconnect(self) -> None:
        """Disconnect from the device."""
        if self.writer:
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except Exception as err:
                _LOGGER.error("Error closing connection: %s", err)
        self.reader = None
        self.writer = None

    async def get_status(self) -> dict[str, Any] | None:
        """Get device status."""
        try:
            if not self.reader or not self.writer:
                if not await self.connect():
                    return None

            async with self._lock:
                # Send status request
                payload = {
                    "gwId": self.device_id,
                    "devId": self.device_id,
                    "uid": "",
                    "t": int(time.time()),
                    "dps": {},
                }
                
                message = await self._create_message(payload, "status")
                if not message:
                    return None

                _LOGGER.debug("Sending status request message: %s", message.hex())
                self.writer.write(message)
                await asyncio.wait_for(self.writer.drain(), timeout=SOCKET_TIMEOUT)
                
                # Receive response with timeout
                response = await self._read_message()
                if not response:
                    _LOGGER.error("Failed to read response message")
                    return None
                    
                _LOGGER.debug("Raw response from device: %s", response.hex())
                _LOGGER.debug("Response length: %d bytes", len(response))
                result = await self._parse_response(response)
                _LOGGER.debug("Parsed response: %s", result)
                return result
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout waiting for device response")
            await self.disconnect()
            return None
        except asyncio.IncompleteReadError as err:
            _LOGGER.debug("Device closed connection or sent incomplete data: %d bytes received", len(err.partial))
            await self.disconnect()
            return None
        except Exception as err:
            _LOGGER.error("Error getting device status: %s", err, exc_info=True)
            await self.disconnect()
            return None

    async def set_value(self, dp: str, value: Any) -> bool:
        """Set a device value."""
        try:
            if not self.reader or not self.writer:
                if not await self.connect():
                    return False

            async with self._lock:
                payload = {
                    "gwId": self.device_id,
                    "devId": self.device_id,
                    "uid": "",
                    "t": int(time.time()),
                    "dps": {dp: value},
                }

                _LOGGER.debug("Setting DP %s to %s", dp, value)
                message = await self._create_message(payload, "control")
                if not message:
                    return False

                _LOGGER.debug("Sending control message: %s", message.hex())
                self.writer.write(message)
                await asyncio.wait_for(self.writer.drain(), timeout=SOCKET_TIMEOUT)
                
                # Receive response with timeout
                response = await self._read_message()
                if not response:
                    _LOGGER.error("Failed to read control response message")
                    return False
                    
                _LOGGER.debug("Control response from device: %s", response.hex())
                result = await self._parse_response(response)
                return result is not None
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout waiting for control response")
            await self.disconnect()
            return False
        except asyncio.IncompleteReadError as err:
            _LOGGER.debug("Device closed connection or sent incomplete data during control")
            await self.disconnect()
            return False
        except Exception as err:
            _LOGGER.error("Error setting device value: %s", err, exc_info=True)
            await self.disconnect()
            return False

    async def _create_message(self, payload: dict[str, Any], cmd: str = "status") -> bytes | None:
        """Create a Tuya protocol message."""
        try:
            payload_json = json.dumps(payload)
            _LOGGER.debug("Creating %s message with payload: %s", cmd, payload_json)
            payload_bytes = payload_json.encode("utf-8")

            # Encrypt the payload
            cipher = AES.new(
                self.local_key.encode("utf-8").ljust(16, b"\x00")[:16],
                AES.MODE_ECB,
            )
            encrypted = cipher.encrypt(self._pad(payload_bytes))
            _LOGGER.debug("Encrypted payload (%d bytes): %s", len(encrypted), encrypted.hex())

            # Create header
            self.session_id = (self.session_id + 1) % 256
            msg_type = self._get_message_type(cmd)
            
            header = struct.pack(
                ">IIII",
                0x000055AA,  # prefix
                self.session_id,
                msg_type,
                len(encrypted),
            )
            _LOGGER.debug("Message header - Session: %d, Type: %d, PayloadLen: %d", self.session_id, msg_type, len(encrypted))

            # Calculate MD5
            data_with_version = self.device_id.encode("utf-8") + b":" + TUYA_PROTOCOL_VERSION_BYTES + b":" + encrypted
            md5 = hashlib.md5(data_with_version).digest()
            _LOGGER.debug("MD5 checksum: %s", md5.hex())

            # Create message
            message = (
                header
                + encrypted
                + md5
                + b"\x00\x00\xAA\x55"
            )

            return message
        except Exception as err:
            _LOGGER.error("Error creating message: %s", err)
            return None

    async def _read_message(self) -> bytes | None:
        """Read a complete Tuya protocol message from the device."""
        try:
            if not self.reader:
                return None
                
            # Try to read any available data first to see what device sends
            _LOGGER.debug("Waiting for device response...")
            
            # Read header (16 bytes)
            try:
                header = await asyncio.wait_for(
                    self.reader.readexactly(TUYA_MESSAGE_HEADER_SIZE),
                    timeout=SOCKET_TIMEOUT,
                )
            except asyncio.IncompleteReadError as e:
                _LOGGER.error("Could not read header - got %d bytes, connection closed", len(e.partial))
                if e.partial:
                    _LOGGER.debug("Partial header received: %s", e.partial.hex())
                return None
            
            if len(header) < TUYA_MESSAGE_HEADER_SIZE:
                _LOGGER.error("Invalid header length: %d", len(header))
                return None
            
            _LOGGER.debug("Header received: %s", header.hex())
            
            # Parse header to get payload length
            prefix, session_id, msg_type, payload_len = struct.unpack(">IIII", header)
            _LOGGER.debug("Parsed header - Prefix: 0x%08x, Session: %d, Type: %d, PayloadLen: %d", 
                         prefix, session_id, msg_type, payload_len)
            
            if prefix != 0x000055AA:
                _LOGGER.error("Invalid message prefix: 0x%08x (expected 0x000055aa)", prefix)
                return None
            
            # Read payload + MD5
            total_data_len = payload_len + 16  # payload + MD5
            _LOGGER.debug("Reading %d bytes of payload+MD5", total_data_len)
            
            try:
                data = await asyncio.wait_for(
                    self.reader.readexactly(total_data_len),
                    timeout=SOCKET_TIMEOUT,
                )
            except asyncio.IncompleteReadError as e:
                _LOGGER.error("Could not read payload - got %d bytes, expected %d", len(e.partial), total_data_len)
                if e.partial:
                    _LOGGER.debug("Partial payload received: %s", e.partial.hex()[:200])
                return None
            
            # Read suffix (4 bytes)
            try:
                suffix = await asyncio.wait_for(
                    self.reader.readexactly(4),
                    timeout=SOCKET_TIMEOUT,
                )
            except asyncio.IncompleteReadError as e:
                _LOGGER.error("Could not read suffix - got %d bytes", len(e.partial))
                return None
            
            if suffix != b"\x00\x00\xAA\x55":
                _LOGGER.warning("Invalid message suffix: %s (expected 0000aa55)", suffix.hex())
            
            # Combine and return complete message
            message = header + data + suffix
            _LOGGER.debug("Complete message received (%d bytes total)", len(message))
            return message
            
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout reading response from device after %s seconds", SOCKET_TIMEOUT)
            return None
        except Exception as err:
            _LOGGER.error("Error reading message: %s", err, exc_info=True)
            return None

    async def _parse_response(self, response: bytes) -> dict[str, Any] | None:
        """Parse a Tuya protocol response."""
        try:
            if len(response) < TUYA_MESSAGE_HEADER_SIZE + TUYA_MESSAGE_SUFFIX_SIZE:
                _LOGGER.error("Response too short: %d bytes (need at least %d)", len(response), TUYA_MESSAGE_HEADER_SIZE + TUYA_MESSAGE_SUFFIX_SIZE)
                return None

            # Extract header info
            header = response[:TUYA_MESSAGE_HEADER_SIZE]
            prefix, session_id, msg_type, payload_len = struct.unpack(">IIII", header)
            _LOGGER.debug("Response header - Prefix: 0x%08x, Session: %d, Type: %d, PayloadLen: %d", prefix, session_id, msg_type, payload_len)

            # Extract encrypted payload
            encrypted = response[TUYA_MESSAGE_HEADER_SIZE:-TUYA_MESSAGE_SUFFIX_SIZE]
            _LOGGER.debug("Encrypted payload (%d bytes): %s", len(encrypted), encrypted.hex())

            # Decrypt
            cipher = AES.new(
                self.local_key.encode("utf-8").ljust(16, b"\x00")[:16],
                AES.MODE_ECB,
            )
            decrypted = cipher.decrypt(encrypted)
            _LOGGER.debug("Decrypted payload (%d bytes): %s", len(decrypted), decrypted.hex())
            
            # Remove padding
            payload_json = self._unpad(decrypted).decode("utf-8")
            _LOGGER.debug("JSON payload: %s", payload_json)
            result = json.loads(payload_json)
            if "dps" in result:
                _LOGGER.info("Device status - DPs: %s", result["dps"])
            return result
        except Exception as err:
            _LOGGER.error("Error parsing response: %s", err, exc_info=True)
            return None

    def _pad(self, data: bytes) -> bytes:
        """PKCS7 padding."""
        pad_len = 16 - (len(data) % 16)
        return data + bytes([pad_len] * pad_len)

    def _unpad(self, data: bytes) -> bytes:
        """Remove PKCS7 padding."""
        pad_len = data[-1]
        return data[:-pad_len]

    def _get_message_type(self, cmd: str) -> int:
        """Get message type for command."""
        cmd_map = {
            "status": 10,
            "control": 7,
            "heartbeat": 9,
        }
        return cmd_map.get(cmd, 10)
