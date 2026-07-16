"""Reader for the can-utils ``candump -L`` text format."""
from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path
from re import Match

from capkit.model import Frame, LogMeta
from capkit.readers.base import read_sample


class CandumpReader:
    """Read the can-utils log format emitted by ``candump -L``."""

    name = "candump"
    extensions = (".log",)

    _ERROR_FLAG = 0x20000000
    _FRAME_RE = re.compile(
        r"^\s*"
        r"\((?P<timestamp>\d+(?:\.\d+)?)\)"
        r"\s+(?P<interface>\S+)"
        r"\s+(?P<identifier>[0-9A-Fa-f]{3}|[0-9A-Fa-f]{8})"
        r"(?:"
        r"##(?P<fd_flags>[0-9A-Fa-f])(?P<fd_data>(?:[0-9A-Fa-f]{2})*)"
        r"|#(?:[Rr](?P<remote_dlc>[0-9A-Fa-f]?)|(?P<data>(?:[0-9A-Fa-f]{2})*))"
        r")"
        r"(?:\s+(?P<direction>[RrTt]))?"
        r"\s*$"
    )

    def __init__(self, *, strict: bool = False) -> None:
        self.strict = strict

    @staticmethod
    def _channel(interface: str) -> int | None:
        match = re.search(r"(\d+)$", interface)
        return int(match.group(1)) if match is not None else None

    @staticmethod
    def _is_rx(direction: str | None) -> bool | None:
        if direction is None:
            return None
        return direction.upper() == "R"

    @classmethod
    def _is_error_frame(cls, match: Match[str]) -> bool:
        return bool(int(match.group("identifier"), 16) & cls._ERROR_FLAG)

    def sniff(self, sample: str) -> bool:
        """Recognize a complete can-utils log record."""
        return any(self._FRAME_RE.fullmatch(line) is not None for line in sample.splitlines())

    def probe(self, path: Path) -> LogMeta:
        """Return candump metadata after validating a bounded sample."""
        if not self.sniff(read_sample(path)):
            raise ValueError(f"File '{path.name}' is not a candump log.")
        return LogMeta(format=self.name)

    def _frame(self, match: Match[str]) -> Frame:
        identifier = match.group("identifier")
        fd_flags = match.group("fd_flags")
        remote_dlc = match.group("remote_dlc")
        is_fd = fd_flags is not None
        is_remote = remote_dlc is not None
        flags = int(fd_flags, 16) if fd_flags is not None else 0
        data_hex = match.group("fd_data") if is_fd else match.group("data")

        return Frame(
            timestamp=float(match.group("timestamp")),
            arbitration_id=int(identifier, 16),
            data=bytes.fromhex(data_hex or ""),
            channel=self._channel(match.group("interface")),
            is_extended_frame=len(identifier) == 8,
            is_fd=is_fd,
            is_remote_frame=is_remote,
            is_rx=self._is_rx(match.group("direction")),
            dlc=int(remote_dlc, 16) if remote_dlc else None,
            bitrate_switch=bool(flags & 0x1),
            error_state_indicator=bool(flags & 0x2),
        )

    def read(self, path: Path) -> Iterator[Frame]:
        """Lazily parse can-utils frame records from *path*."""
        with path.open(encoding="latin-1") as stream:
            for line_number, raw_line in enumerate(stream, start=1):
                line = raw_line.rstrip("\r\n")
                if not line.strip():
                    continue

                match = self._FRAME_RE.fullmatch(line)
                if match is None or self._is_error_frame(match):
                    if self.strict:
                        raise ValueError(f"Unrecognized candump line {line_number}: {line!r}.")
                    continue

                yield self._frame(match)
