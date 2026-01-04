"""PTP protocol implementation for Canon R-series cameras."""

from .constants import (
    CANON_R7_PRODUCT_ID,
    CANON_R7_SHUTTER_LIFE,
    CANON_VENDOR_ID,
)
from .transport import USBTransport, USBTransportError

__all__ = [
    "CANON_R7_PRODUCT_ID",
    "CANON_R7_SHUTTER_LIFE",
    "CANON_VENDOR_ID",
    "USBTransport",
    "USBTransportError",
]
