"""PTP and Canon EOS protocol constants for R-series cameras."""

from enum import IntEnum


class PTPOperation(IntEnum):
    """Standard PTP operation codes."""

    GET_DEVICE_INFO = 0x1001
    OPEN_SESSION = 0x1002
    CLOSE_SESSION = 0x1003


class CanonEOSOperation(IntEnum):
    """Canon EOS vendor operation codes."""

    SET_REMOTE_MODE = 0x9114
    SET_EVENT_MODE = 0x9115
    GET_EVENT = 0x9116


class CanonEOSProperty(IntEnum):
    """Canon EOS property codes."""

    SHUTTER_RELEASE_COUNTER = 0xD167  # 16-byte struct on R-series


class PTPResponse(IntEnum):
    """PTP response codes."""

    OK = 0x2001
    DEVICE_BUSY = 0x2019


class CanonEOSEvent(IntEnum):
    """Canon EOS event codes."""

    PROP_VALUE_CHANGED = 0xC189


class PTPPacketType(IntEnum):
    """PTP USB container types."""

    COMMAND = 1
    DATA = 2
    RESPONSE = 3


# Canon R7 USB IDs
CANON_VENDOR_ID = 0x04A9
CANON_R7_PRODUCT_ID = 0x32F7

# Canon R7 rated shutter life
CANON_R7_SHUTTER_LIFE = 200000
