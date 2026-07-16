"""Reader for Kvaser CanKing text exports."""
from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path
from re import Match

from capkit.model import Frame, LogMeta
from capkit.readers.base import read_sample


class KvaserTxtReader:
    """Read the whitespace-delimited Kvaser CanKing TXT dialect."""

    name = "kvaser-txt"
    extensions = (".txt",)

    _FRAME_RE = re.compile(
        r"^\s*"
        r"(?P<channel>\d+)"
        r"\s+(?P<identifier>[0-9A-Fa-f]+)"
        r"(?:\s+(?P<flag>[xX]))?"
        r"\s+(?P<dlc>\d+)"
        r"(?P<data>(?:\s+[0-9A-Fa-f]{2})*)"
        r"\s+(?P<timestamp>\d+(?:\.\d+)?)"
        r"\s+(?P<direction>[RrTt])"
        r"\s*$"
    )

    def __init__(self, *, strict: bool = False) -> None:
        self.strict = strict

    @staticmethod
    def _is_header(line: str) -> bool:
        normalized = " ".join(line.lower().split())
        return normalized.startswith("chn identifier flg dlc") and "time" in normalized and "dir" in normalized

    @staticmethod
    def _data_tokens(match: Match[str]) -> list[str]:
        return match.group("data").split()

    @classmethod
    def _is_complete_frame(cls, match: Match[str]) -> bool:
        return len(cls._data_tokens(match)) == int(match.group("dlc"))

    def sniff(self, sample: str) -> bool:
        """Recognize the Kvaser table header or a complete frame line."""
        for line in sample.splitlines():
            if self._is_header(line):
                return True
            match = self._FRAME_RE.fullmatch(line)
            if match is not None and self._is_complete_frame(match):
                return True
        return False

    def probe(self, path: Path) -> LogMeta:
        """Return Kvaser metadata without scanning the frame body."""
        if not self.sniff(read_sample(path)):
            raise ValueError(f"File '{path.name}' is not a Kvaser TXT log.")
        return LogMeta(format=self.name)

    def read(self, path: Path) -> Iterator[Frame]:
        """Lazily parse Kvaser frame records from *path*."""
        with path.open(encoding="latin-1") as stream:
            for line_number, raw_line in enumerate(stream, start=1):
                line = raw_line.rstrip("\r\n")
                if not line.strip():
                    continue

                match = self._FRAME_RE.fullmatch(line)
                if match is None:
                    if self.strict:
                        raise ValueError(f"Unrecognized Kvaser TXT line {line_number}: {line!r}.")
                    continue

                data_tokens = self._data_tokens(match)
                dlc = int(match.group("dlc"))
                if len(data_tokens) != dlc:
                    raise ValueError(
                        f"Invalid Kvaser TXT frame at line {line_number}: "
                        f"DLC {dlc} declares {dlc} data bytes, got {len(data_tokens)}."
                    )

                yield Frame(
                    timestamp=float(match.group("timestamp")),
                    arbitration_id=int(match.group("identifier"), 16),
                    data=bytes.fromhex(" ".join(data_tokens)),
                    channel=int(match.group("channel")),
                    is_extended_frame=match.group("flag") is not None,
                    is_rx=match.group("direction").upper() == "R",
                )
