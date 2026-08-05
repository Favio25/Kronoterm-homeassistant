"""Helpers for decoding Kronoterm register values."""

UINT16_MASK = 0xFFFF
MEASURED_TEMPERATURE_MIN = -60.0
MEASURED_TEMPERATURE_MAX = 150.0
PERFORMANCE_FACTOR_NAMES = {"cop_value", "scop_value"}
PERFORMANCE_FACTOR_PREFERRED_MAX = 10.0
PERFORMANCE_FACTOR_HARD_MAX = 20.0
PERFORMANCE_FACTOR_SCALES = (1.0, 0.1, 0.01, 0.001)
POOL_UNAVAILABLE_TEMPERATURES = {-60.0, -40.0, 0.0}


def combine_u16_words(high_word: int, low_word: int) -> int:
    """Combine two unsigned Modbus words into one 32-bit value."""
    return ((int(high_word) & UINT16_MASK) << 16) | (int(low_word) & UINT16_MASK)


def documented_to_modbus_address(documented_address: int) -> int:
    """Convert Kronoterm's one-based manual address to Modbus zero-based form."""
    if documented_address < 1:
        raise ValueError("Documented Modbus addresses must be positive")
    return documented_address - 1


def is_measured_temperature_plausible(value: object) -> bool:
    """Return True when a measured temperature is within a sane heat-pump range."""
    try:
        temperature = float(value)
    except (TypeError, ValueError):
        return False
    return MEASURED_TEMPERATURE_MIN <= temperature <= MEASURED_TEMPERATURE_MAX


def normalize_performance_factor(value: object) -> float | None:
    """Normalize COP/SCOP values across controllers with different scaling."""
    try:
        raw_value = float(value)
    except (TypeError, ValueError):
        return None
    if raw_value < 0:
        return None
    if raw_value == 0:
        return 0.0

    candidates = [
        raw_value * scale
        for scale in PERFORMANCE_FACTOR_SCALES
        if 0.0 < raw_value * scale <= PERFORMANCE_FACTOR_HARD_MAX
    ]
    if not candidates:
        return None

    preferred = [
        candidate
        for candidate in candidates
        if candidate <= PERFORMANCE_FACTOR_PREFERRED_MAX
    ]
    return round(preferred[0] if preferred else candidates[0], 2)


def is_pool_temperature_available(value: object) -> bool:
    """Return True when a pool temperature is a real reading, not a sentinel."""
    try:
        temperature = float(value)
    except (TypeError, ValueError):
        return False
    return temperature not in POOL_UNAVAILABLE_TEMPERATURES and 0.0 < temperature < 60.0


def is_pool_setpoint_available(value: object) -> bool:
    """Return True when a pool setpoint is in the documented operating range."""
    try:
        setpoint = float(value)
    except (TypeError, ValueError):
        return False
    return 19.9 <= setpoint <= 35.0


class KronotermTcpPacketNormalizer:
    """Normalize the fixed transaction ID returned by Kronoterm TCP servers.

    The controller returns its device ID (20) in the MBAP transaction-ID field.
    Pymodbus serializes client requests, so replacing that field with the current
    request ID is safe and leaves the rest of the response untouched.
    """

    def __init__(self) -> None:
        self._request_transaction_id: bytes | None = None

    @staticmethod
    def _has_mbap_header(data: bytes) -> bool:
        return len(data) >= 7 and data[2:4] == b"\x00\x00"

    def __call__(self, sending: bool, data: bytes) -> bytes:
        if not self._has_mbap_header(data):
            return data
        if sending:
            self._request_transaction_id = data[:2]
            return data
        if self._request_transaction_id is None:
            return data
        return self._request_transaction_id + data[2:]
