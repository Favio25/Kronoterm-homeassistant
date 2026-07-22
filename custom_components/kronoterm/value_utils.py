"""Helpers for decoding Kronoterm register values."""

UINT16_MASK = 0xFFFF


def combine_u16_words(high_word: int, low_word: int) -> int:
    """Combine two unsigned Modbus words into one 32-bit value."""
    return ((int(high_word) & UINT16_MASK) << 16) | (int(low_word) & UINT16_MASK)


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
