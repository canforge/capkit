"""Common frame and log-metadata models."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Frame:
    """A single CAN frame read from a log file."""

    timestamp: float
    arbitration_id: int
    data: bytes
    channel: int | None = None
    is_extended_frame: bool = False
    is_fd: bool = False
    is_remote_frame: bool = False
    is_error_frame: bool = False
    is_rx: bool | None = None
    dlc: int | None = None


@dataclass(frozen=True, slots=True)
class LogMeta:
    """Cheap, header-derived metadata about a log file."""

    format: str
    start_time: datetime | None = None
    extra: dict[str, str] = field(default_factory=dict)
