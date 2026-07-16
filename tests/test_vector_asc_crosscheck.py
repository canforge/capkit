"""Cross-check Vector ASC parsing against python-can's reference reader."""
from __future__ import annotations

from pathlib import Path

import pytest

from capkit.readers.vector_asc import VectorAscReader

can = pytest.importorskip("can")

FIXTURE = Path(__file__).parent / "fixtures" / "vector_asc" / "python_can_logfile.asc"


def test_golden_fixture_matches_python_can_field_by_field() -> None:
    actual = list(VectorAscReader().read(FIXTURE))
    reference = list(can.ASCReader(FIXTURE))

    assert len(actual) == len(reference)
    for frame, message in zip(actual, reference, strict=True):
        assert frame.timestamp == pytest.approx(message.timestamp)
        assert frame.arbitration_id == message.arbitration_id
        assert frame.data == bytes(message.data)
        assert frame.channel == message.channel + 1
        assert frame.is_extended_frame is message.is_extended_id
        assert frame.is_fd is message.is_fd
        assert frame.is_remote_frame is message.is_remote_frame
        assert frame.is_error_frame is message.is_error_frame
        assert frame.is_rx is message.is_rx
        assert frame.bitrate_switch is message.bitrate_switch
        assert frame.error_state_indicator is message.error_state_indicator


def test_capkit_preserves_asc_dlc_codes_only_when_informative() -> None:
    frames = list(VectorAscReader().read(FIXTURE))

    assert frames[3].dlc is None
    assert frames[5].dlc == 8
    assert frames[16].dlc is None
    assert frames[17].dlc == 5
    assert frames[18].dlc == 0xF
