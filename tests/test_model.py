"""Tests for immutable frame and metadata models."""
from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from capkit import Frame, LogMeta


def test_frame_defaults_and_structural_contract() -> None:
    frame = Frame(timestamp=1.25, arbitration_id=0x123, data=b"\x01\x02")

    assert isinstance(frame.timestamp, float)
    assert isinstance(frame.arbitration_id, int)
    assert isinstance(frame.data, bytes)
    assert frame.channel is None
    assert frame.is_extended_frame is False
    assert frame.is_fd is False
    assert frame.is_remote_frame is False
    assert frame.is_error_frame is False
    assert frame.is_rx is None
    assert frame.dlc is None
    assert frame.bitrate_switch is False
    assert frame.error_state_indicator is False


def test_frame_fd_flags_append_without_breaking_positional_construction() -> None:
    frame = Frame(1.0, 0x123, b"\x01", 2, False, True, False, False, True, None, True, True)

    assert frame.bitrate_switch is True
    assert frame.error_state_indicator is True


def test_frame_is_frozen_and_slotted() -> None:
    frame = Frame(timestamp=0.0, arbitration_id=0, data=b"")

    assert not hasattr(frame, "__dict__")
    with pytest.raises(FrozenInstanceError):
        frame.timestamp = 2.0  # type: ignore[misc]


def test_log_meta_extra_uses_an_independent_default() -> None:
    first = LogMeta(format="first")
    second = LogMeta(format="second")

    first.extra["source"] = "header"

    assert second.extra == {}
