"""Canon EOS PTP extension implementation."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Iterator

from .constants import (
    CanonEOSEvent,
    CanonEOSOperation,
    CanonEOSProperty,
    PTPResponse,
)
from .protocol import PTPProtocol


@dataclass
class EOSPropertyValue:
    """A Canon EOS property value from event data."""

    property_code: int
    value: int | bytes


class CanonEOSProtocol(PTPProtocol):
    """Canon EOS-specific PTP protocol extension."""

    def _send_canon_command(self, operation: int, params: list[int] | None = None) -> None:
        """Send a Canon command and raise on failure."""
        response_code, _ = self.transport.send_command(operation, params=params)
        if response_code != PTPResponse.OK:
            raise RuntimeError(f"Command {operation:#06x} failed: {response_code:#06x}")

    def get_event(self) -> list[EOSPropertyValue]:
        """Get all property values from camera. Returns all current values on first call."""
        response_code, data = self.transport.send_command(CanonEOSOperation.GET_EVENT)
        if response_code != PTPResponse.OK:
            raise RuntimeError(f"GetEvent failed: {response_code:#06x}")
        return list(self._parse_event_data(data))

    def _parse_event_data(self, data: bytes) -> Iterator[EOSPropertyValue]:
        """Parse event records. Each: length(4) + event_code(4) + data. Ends when length=0."""
        offset = 0
        while offset + 8 <= len(data):
            record_len, event_code = struct.unpack_from("<II", data, offset)
            if record_len == 0 or event_code == 0:
                break

            if event_code == CanonEOSEvent.PROP_VALUE_CHANGED:
                record_data = data[offset + 8 : offset + record_len]
                if len(record_data) >= 4:
                    prop_code = struct.unpack_from("<I", record_data, 0)[0]
                    prop_value = record_data[4:]
                    if len(prop_value) == 4:
                        yield EOSPropertyValue(prop_code, struct.unpack("<I", prop_value)[0])
                    elif prop_value:
                        yield EOSPropertyValue(prop_code, prop_value)

            offset += record_len

    def get_shutter_count(self) -> tuple[int, int] | None:
        """
        Get shutter count from 0xD167 property.

        Returns (mechanical_count, total_count) or None. Counts are in 1000 increments.
        """
        for event in self.get_event():
            if event.property_code == CanonEOSProperty.SHUTTER_RELEASE_COUNTER:
                if isinstance(event.value, bytes) and len(event.value) >= 16:
                    mechanical, total = struct.unpack("<II", event.value[8:16])
                    return (mechanical, total)
        return None

    def initialize_eos_session(self) -> None:
        """Initialize a Canon EOS session with required mode settings."""
        self.open_session()
        self._send_canon_command(CanonEOSOperation.SET_REMOTE_MODE, [1])
        self._send_canon_command(CanonEOSOperation.SET_EVENT_MODE, [1])

    def __enter__(self) -> CanonEOSProtocol:
        self.initialize_eos_session()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> bool:
        self.close_session()
        return False
