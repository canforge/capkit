"""Tests for dependency-free J1939 arbitration-ID decomposition."""
from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

import capkit
from capkit import J1939Fields, decompose_j1939_id
from capkit.operations import J1939Fields as OperationsJ1939Fields
from capkit.operations import decompose_j1939_id as operations_decompose_j1939_id


def test_decomposes_canonical_eec1_identifier() -> None:
    fields = decompose_j1939_id(0x0CF00400)

    assert fields == J1939Fields(
        priority=3,
        pgn=0xF004,
        source_address=0x00,
        destination_address=None,
    )


def test_pdu1_returns_destination_and_excludes_it_from_pgn() -> None:
    fields = decompose_j1939_id(0x18EF20A5)

    assert fields.priority == 6
    assert fields.pgn == 0xEF00
    assert fields.source_address == 0xA5
    assert fields.destination_address == 0x20


def test_pdu_format_boundary_distinguishes_pdu1_and_pdu2() -> None:
    pdu1 = decompose_j1939_id(0x18EFFF80)
    pdu2 = decompose_j1939_id(0x18F00180)

    assert pdu1.pgn == 0xEF00
    assert pdu1.destination_address == 0xFF
    assert pdu2.pgn == 0xF001
    assert pdu2.destination_address is None


def test_pdu1_destination_does_not_change_pgn() -> None:
    first = decompose_j1939_id(0x18EA00A5)
    second = decompose_j1939_id(0x18EAFFA5)

    assert first.pgn == second.pgn == 0xEA00
    assert first.destination_address == 0x00
    assert second.destination_address == 0xFF


def test_pdu2_group_extension_changes_pgn() -> None:
    first = decompose_j1939_id(0x18F000A5)
    second = decompose_j1939_id(0x18F0FFA5)

    assert first.pgn == 0xF000
    assert second.pgn == 0xF0FF
    assert first.destination_address is None
    assert second.destination_address is None


def test_retains_both_page_bits_in_pgn() -> None:
    fields = decompose_j1939_id(0x03F01234)

    assert fields.priority == 0
    assert fields.pgn == 0x3F012
    assert fields.source_address == 0x34


def test_priority_and_source_address_do_not_change_pgn() -> None:
    first = decompose_j1939_id(0x0CF00400)
    second = decompose_j1939_id(0x18F004AA)

    assert first.pgn == second.pgn == 0xF004
    assert (first.priority, first.source_address) == (3, 0x00)
    assert (second.priority, second.source_address) == (6, 0xAA)


@pytest.mark.parametrize(
    ("arbitration_id", "expected"),
    [
        (0x00000000, J1939Fields(0, 0, 0, 0)),
        (0x1FFFFFFF, J1939Fields(7, 0x3FFFF, 0xFF, None)),
    ],
)
def test_accepts_29_bit_range_endpoints(
    arbitration_id: int,
    expected: J1939Fields,
) -> None:
    assert decompose_j1939_id(arbitration_id) == expected


@pytest.mark.parametrize("arbitration_id", [None, 1.5, "0x18F00400", b"\x00"])
def test_rejects_non_integer_inputs(arbitration_id: object) -> None:
    with pytest.raises(TypeError, match="arbitration_id must be an integer"):
        decompose_j1939_id(arbitration_id)  # type: ignore[arg-type]


@pytest.mark.parametrize("arbitration_id", [-1, 0x20000000])
def test_rejects_values_outside_29_bit_range(arbitration_id: int) -> None:
    with pytest.raises(
        ValueError,
        match="arbitration_id must be between 0x00000000 and 0x1FFFFFFF",
    ):
        decompose_j1939_id(arbitration_id)


def test_result_is_frozen_and_slotted() -> None:
    fields = decompose_j1939_id(0x0CF00400)

    assert not hasattr(fields, "__dict__")
    with pytest.raises(FrozenInstanceError):
        fields.priority = 1  # type: ignore[misc]


def test_public_exports_reference_the_same_api() -> None:
    assert capkit.J1939Fields is OperationsJ1939Fields
    assert capkit.decompose_j1939_id is operations_decompose_j1939_id
