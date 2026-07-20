"""Read CAN log files into a common stream of frame objects."""
from __future__ import annotations

from capkit.io import available_formats, probe, read
from capkit.model import Frame, LogMeta
from capkit.operations import J1939Fields, decompose_j1939_id, filter_frames, merge_frames, rebase_timestamps
from capkit.readers import register_reader

__all__ = [
    # model
    "Frame", "LogMeta", "J1939Fields",
    # io
    "read", "probe", "available_formats", "register_reader",
    # operations
    "decompose_j1939_id", "filter_frames", "merge_frames", "rebase_timestamps",
]
