"""J1939 arbitration-ID decomposition helpers."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class J1939Fields:
    """Frame-level fields derived from a 29-bit J1939 arbitration ID.

    ``destination_address`` is populated for destination-specific PDU1 IDs.
    It is ``None`` for PDU2 IDs, where the same byte is a group extension and
    therefore remains part of the PGN.
    """

    priority: int
    pgn: int
    source_address: int
    destination_address: int | None


def decompose_j1939_id(arbitration_id: int) -> J1939Fields:
    """Decompose a clean 29-bit J1939 arbitration ID.

    The PGN retains the extended data-page, data-page, and PDU-format bits.
    For PDU1 IDs (PDU format below ``0xF0``), the PDU-specific byte is a
    destination address and is cleared from the PGN. For PDU2 IDs, that byte
    is a group extension and remains in the PGN.

    Raises ``TypeError`` for non-integer inputs and ``ValueError`` for values
    outside the 29-bit CAN arbitration-ID range.
    """
    if not isinstance(arbitration_id, int):
        raise TypeError("arbitration_id must be an integer")
    if not 0 <= arbitration_id <= 0x1FFFFFFF:
        raise ValueError("arbitration_id must be between 0x00000000 and 0x1FFFFFFF")

    priority = (arbitration_id >> 26) & 0x7
    pdu_format = (arbitration_id >> 16) & 0xFF
    pdu_specific = (arbitration_id >> 8) & 0xFF
    source_address = arbitration_id & 0xFF

    pgn = (arbitration_id >> 8) & 0x3FFFF
    destination_address: int | None = None
    if pdu_format < 0xF0:
        pgn &= 0x3FF00
        destination_address = pdu_specific

    return J1939Fields(
        priority=priority,
        pgn=pgn,
        source_address=source_address,
        destination_address=destination_address,
    )
