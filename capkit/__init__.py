"""Read CAN log files into a common stream of frame objects."""
from __future__ import annotations

from capkit.io import available_formats, probe, read
from capkit.model import Frame, LogMeta
from capkit.readers import register_reader

__all__ = [
    # model
    "Frame", "LogMeta",
    # io
    "read", "probe", "available_formats", "register_reader",
]
