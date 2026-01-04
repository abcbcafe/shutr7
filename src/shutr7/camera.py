"""High-level Canon R7 camera interface."""

from __future__ import annotations

from dataclasses import dataclass

from .ptp.canon import CanonEOSProtocol
from .ptp.constants import CANON_R7_PRODUCT_ID, CANON_R7_SHUTTER_LIFE, CANON_VENDOR_ID
from .ptp.transport import USBTransport


@dataclass
class ShutterInfo:
    """Shutter count information. Counts are approximate (1000 increments on R-series)."""

    mechanical_count: int
    total_count: int
    life_expectancy: int
    percentage_used: float

    @property
    def remaining(self) -> int:
        return max(0, self.life_expectancy - self.mechanical_count)

    @property
    def percentage_remaining(self) -> float:
        return 100.0 - self.percentage_used


@dataclass
class CameraInfo:
    """Camera information."""

    manufacturer: str
    model: str
    firmware_version: str


class CanonR7:
    """High-level interface for Canon R7 camera."""

    def __init__(
        self,
        vendor_id: int = CANON_VENDOR_ID,
        product_id: int = CANON_R7_PRODUCT_ID,
        shutter_life: int = CANON_R7_SHUTTER_LIFE,
    ) -> None:
        self.transport = USBTransport(vendor_id, product_id)
        self.protocol: CanonEOSProtocol | None = None
        self._shutter_life = shutter_life

    def connect(self) -> None:
        """Connect to the camera."""
        self.transport.connect()
        self.protocol = CanonEOSProtocol(self.transport)
        self.protocol.initialize_eos_session()

    def disconnect(self) -> None:
        """Disconnect from the camera."""
        if self.protocol:
            self.protocol.close_session()
            self.protocol = None
        self.transport.disconnect()

    def get_camera_info(self) -> CameraInfo:
        """Get camera information."""
        if not self.protocol:
            raise RuntimeError("Not connected")

        info = self.protocol.get_device_info()
        return CameraInfo(
            manufacturer=info.manufacturer,
            model=info.model,
            firmware_version=info.device_version,
        )

    def get_shutter_count(self) -> ShutterInfo:
        """Get shutter count information."""
        if not self.protocol:
            raise RuntimeError("Not connected")

        result = self.protocol.get_shutter_count()
        if result is None:
            raise RuntimeError("Shutter count not available")

        mechanical, total = result
        return ShutterInfo(
            mechanical_count=mechanical,
            total_count=total,
            life_expectancy=self._shutter_life,
            percentage_used=(mechanical / self._shutter_life) * 100,
        )

    def __enter__(self) -> CanonR7:
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
