"""Tests for capkit's dbckit-compatible structural contract."""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import capkit
import capkit.readers as reader_registry
from capkit.integration import DispatchReader

FIXTURE = Path(__file__).parent / "fixtures" / "kvaser" / "kvaser.txt"


def test_root_exports_are_intentionally_small() -> None:
    assert capkit.__all__ == [
        "Frame", "LogMeta",
        "read", "probe", "available_formats", "register_reader",
        "filter_frames", "merge_frames",
    ]


def test_registered_readers_are_zero_argument_constructible() -> None:
    for reader_type in reader_registry._READERS.values():
        reader = reader_type()
        assert callable(reader.read)
        assert callable(reader.probe)
        assert callable(reader.sniff)


def test_dispatch_reader_is_zero_argument_constructible() -> None:
    assert callable(DispatchReader().read)


def test_read_returns_lazy_structurally_compatible_frames() -> None:
    frames = capkit.read(FIXTURE)

    assert isinstance(frames, Iterator)
    frame = next(frames)
    assert isinstance(frame.timestamp, float)
    assert isinstance(frame.arbitration_id, int)
    assert isinstance(frame.data, bytes)
    assert hasattr(frame, "channel")
    assert hasattr(frame, "is_extended_frame")
