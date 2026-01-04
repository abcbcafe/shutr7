"""PTP protocol layer implementation."""

from __future__ import annotations

import struct
from dataclasses import dataclass

from .constants import PTPOperation, PTPResponse
from .transport import USBTransport


@dataclass
class DeviceInfo:
    """PTP device information (subset we care about)."""

    manufacturer: str
    model: str
    device_version: str


class PTPProtocol:
    """PTP protocol implementation."""

    def __init__(self, transport: USBTransport) -> None:
        self.transport = transport

    def open_session(self) -> None:
        """Open a PTP session."""
        response_code, _ = self.transport.send_command(PTPOperation.OPEN_SESSION, params=[1])
        if response_code != PTPResponse.OK:
            raise RuntimeError(f"Failed to open session: {response_code:#06x}")
        self.transport.reset_transaction_id()

    def close_session(self) -> None:
        """Close the current PTP session."""
        try:
            self.transport.send_command(PTPOperation.CLOSE_SESSION)
        except Exception:
            pass

    def get_device_info(self) -> DeviceInfo:
        """Get device information."""
        response_code, data = self.transport.send_command(PTPOperation.GET_DEVICE_INFO)
        if response_code != PTPResponse.OK:
            raise RuntimeError(f"Failed to get device info: {response_code:#06x}")
        return self._parse_device_info(data)

    def _parse_device_info(self, data: bytes) -> DeviceInfo:
        """Parse device info, extracting only manufacturer/model/version."""
        offset = 8  # Skip: standard_version(2) + vendor_ext_id(4) + vendor_ext_ver(2)
        _, offset = self._read_ptp_string(data, offset)  # vendor_extension_desc
        offset += 2  # functional_mode
        for _ in range(5):  # Skip 5 arrays: ops, events, props, capture_fmts, image_fmts
            offset = self._skip_uint16_array(data, offset)

        manufacturer, offset = self._read_ptp_string(data, offset)
        model, offset = self._read_ptp_string(data, offset)
        device_version, offset = self._read_ptp_string(data, offset)

        return DeviceInfo(manufacturer=manufacturer, model=model, device_version=device_version)

    @staticmethod
    def _read_ptp_string(data: bytes, offset: int) -> tuple[str, int]:
        """Read a PTP string (length-prefixed UTF-16LE)."""
        if offset >= len(data):
            return "", offset

        num_chars = data[offset]
        offset += 1

        if num_chars == 0:
            return "", offset

        # Each char is 2 bytes (UTF-16LE), includes null terminator
        byte_len = num_chars * 2
        if offset + byte_len > len(data):
            return "", offset

        # Decode without null terminator
        try:
            string = data[offset : offset + byte_len - 2].decode("utf-16-le")
        except UnicodeDecodeError:
            string = ""

        offset += byte_len
        return string, offset

    @staticmethod
    def _skip_uint16_array(data: bytes, offset: int) -> int:
        """Skip a PTP array of uint16 values, return new offset."""
        if offset + 4 > len(data):
            return offset
        count = struct.unpack_from("<I", data, offset)[0]
        return offset + 4 + count * 2
