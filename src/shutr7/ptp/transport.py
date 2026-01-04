"""USB transport layer for PTP communication."""

from __future__ import annotations

import struct
from typing import TYPE_CHECKING

import usb.core
import usb.util

from .constants import CANON_R7_PRODUCT_ID, CANON_VENDOR_ID, PTPPacketType

if TYPE_CHECKING:
    from usb.core import Device, Endpoint


class USBTransportError(Exception):
    """USB transport layer error."""

    pass


class USBTransport:
    """USB transport for PTP protocol communication."""

    TIMEOUT_MS = 5000  # 5 second timeout
    # Large buffer for reading - Canon cameras can return 10KB+ on GetEvent
    READ_BUFFER_SIZE = 65536

    def __init__(
        self,
        vendor_id: int = CANON_VENDOR_ID,
        product_id: int = CANON_R7_PRODUCT_ID,
    ) -> None:
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.device: Device | None = None
        self.in_ep: Endpoint | None = None
        self.out_ep: Endpoint | None = None
        self.intr_ep: Endpoint | None = None
        self._transaction_id = 0
        self._max_packet_size = 512  # Will be updated from endpoint descriptor

    def find_device(self) -> Device:
        """Find and return the Canon R7 USB device."""
        device = usb.core.find(idVendor=self.vendor_id, idProduct=self.product_id)
        if device is None:
            raise USBTransportError(
                f"Canon camera not found (VID={self.vendor_id:#06x}, "
                f"PID={self.product_id:#06x}). "
                "Ensure the camera is connected and powered on."
            )
        return device

    def connect(self) -> None:
        """Connect to the camera and configure USB endpoints."""
        self.device = self.find_device()

        # Detach kernel driver if active
        try:
            if self.device.is_kernel_driver_active(0):
                self.device.detach_kernel_driver(0)
        except (usb.core.USBError, NotImplementedError):
            # Some platforms don't support this
            pass

        # Set configuration
        try:
            self.device.set_configuration()
        except usb.core.USBError as e:
            if "Resource busy" in str(e):
                raise USBTransportError(
                    "Camera is busy. Close any other applications using the camera "
                    "(e.g., EOS Utility, gphoto2)."
                ) from e
            raise

        # Get the active configuration
        cfg = self.device.get_active_configuration()
        intf = cfg[(0, 0)]  # Interface 0, Alternate setting 0

        # Find endpoints
        self.out_ep = usb.util.find_descriptor(
            intf,
            custom_match=lambda e: (
                usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT
                and usb.util.endpoint_type(e.bmAttributes) == usb.util.ENDPOINT_TYPE_BULK
            ),
        )

        self.in_ep = usb.util.find_descriptor(
            intf,
            custom_match=lambda e: (
                usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN
                and usb.util.endpoint_type(e.bmAttributes) == usb.util.ENDPOINT_TYPE_BULK
            ),
        )

        self.intr_ep = usb.util.find_descriptor(
            intf,
            custom_match=lambda e: (
                usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN
                and usb.util.endpoint_type(e.bmAttributes) == usb.util.ENDPOINT_TYPE_INTR
            ),
        )

        if self.out_ep is None or self.in_ep is None:
            raise USBTransportError("Required USB endpoints not found")

        # Get max packet size from endpoint
        self._max_packet_size = self.in_ep.wMaxPacketSize

    def disconnect(self) -> None:
        """Disconnect from the camera."""
        if self.device:
            usb.util.dispose_resources(self.device)
            self.device = None
            self.in_ep = None
            self.out_ep = None
            self.intr_ep = None

    @property
    def transaction_id(self) -> int:
        """Get the current transaction ID and increment for next use."""
        tid = self._transaction_id
        self._transaction_id += 1
        return tid

    def reset_transaction_id(self) -> None:
        """Reset transaction ID to 0."""
        self._transaction_id = 0

    def send_command(
        self,
        operation_code: int,
        params: list[int] | None = None,
        data: bytes | None = None,
    ) -> tuple[int, bytes]:
        """
        Send a PTP command and receive response.

        Args:
            operation_code: PTP operation code
            params: Optional list of 32-bit parameter values
            data: Optional data payload to send

        Returns:
            Tuple of (response_code, response_data)
        """
        if self.out_ep is None or self.in_ep is None:
            raise USBTransportError("Not connected")

        if params is None:
            params = []

        tid = self.transaction_id

        # Build and send command packet
        # Format: length (4) + type (2) + code (2) + tid (4) + params
        param_data = b"".join(struct.pack("<I", p) for p in params)
        cmd_packet = struct.pack(
            "<IHHI",
            12 + len(param_data),  # length
            PTPPacketType.COMMAND,  # type
            operation_code,  # code
            tid,  # transaction id
        ) + param_data

        try:
            self.out_ep.write(cmd_packet, self.TIMEOUT_MS)
        except usb.core.USBError as e:
            raise USBTransportError(f"Failed to send command: {e}") from e

        # Send data phase if needed
        if data is not None:
            data_packet = struct.pack(
                "<IHHI",
                12 + len(data),
                PTPPacketType.DATA,
                operation_code,
                tid,
            ) + data
            try:
                self.out_ep.write(data_packet, self.TIMEOUT_MS)
            except usb.core.USBError as e:
                raise USBTransportError(f"Failed to send data: {e}") from e

        # Read response (may include data phase first)
        response_data = b""
        try:
            while True:
                # Read first packet with large buffer
                raw = self.in_ep.read(self.READ_BUFFER_SIZE, self.TIMEOUT_MS)
                raw_bytes = bytes(raw)

                if len(raw_bytes) < 12:
                    raise USBTransportError(
                        f"Invalid response packet: too short ({len(raw_bytes)} bytes)"
                    )

                pkt_len, pkt_type, pkt_code, pkt_tid = struct.unpack("<IHHI", raw_bytes[:12])

                if pkt_type == PTPPacketType.DATA:
                    # Accumulate data from first packet
                    response_data = raw_bytes[12:]

                    # Continue reading if more data expected
                    while len(response_data) + 12 < pkt_len:
                        more = self.in_ep.read(self.READ_BUFFER_SIZE, self.TIMEOUT_MS)
                        response_data += bytes(more)

                    # Trim to exact length
                    response_data = response_data[: pkt_len - 12]

                elif pkt_type == PTPPacketType.RESPONSE:
                    return pkt_code, response_data

                else:
                    raise USBTransportError(f"Unexpected packet type: {pkt_type}")

        except usb.core.USBError as e:
            raise USBTransportError(f"Failed to receive response: {e}") from e

    def __enter__(self) -> USBTransport:
        self.connect()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> bool:
        self.disconnect()
        return False
