"""Reader for Vector CANalyzer/CANoe ASC text logs."""
from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

from capkit.model import Frame, LogMeta
from capkit.readers.base import read_sample


class VectorAscReader:
    """Read the fixture-pinned Vector ASC dialect."""

    name = "vector-asc"
    extensions = (".asc",)

    _DATE_RE = re.compile(
        r"^date\s+\S+\s+"
        r"(?P<month>[A-Za-z]{3})\s+(?P<day>\d{1,2})\s+"
        r"(?P<hour>\d{1,2}):(?P<minute>\d{2}):(?P<second>\d{2})"
        r"(?:\.(?P<fraction>\d{1,6}))?\s+(?P<year>\d{4})\s*$",
        re.IGNORECASE,
    )
    _BASE_RE = re.compile(
        r"^base\s+(?P<base>hex|dec)"
        r"(?:\s+timestamps\s+(?P<timestamps>absolute|relative))?\s*$",
        re.IGNORECASE,
    )
    _TIMESTAMP_RE = re.compile(r"^\d+(?:\.\d+)?$")
    _MONTHS = {
        "jan": 1,
        "feb": 2,
        "mar": 3,
        "apr": 4,
        "may": 5,
        "jun": 6,
        "jul": 7,
        "aug": 8,
        "sep": 9,
        "oct": 10,
        "nov": 11,
        "dec": 12,
    }

    def __init__(self, *, strict: bool = False) -> None:
        self.strict = strict

    @classmethod
    def _parse_date(cls, line: str) -> datetime:
        match = cls._DATE_RE.fullmatch(line)
        if match is None:
            raise ValueError(f"Unsupported Vector ASC date header: {line!r}.")

        month_name = match.group("month").lower()
        try:
            month = cls._MONTHS[month_name]
        except KeyError as error:
            raise ValueError(f"Unsupported Vector ASC month '{match.group('month')}'.") from error

        fraction = (match.group("fraction") or "").ljust(6, "0")
        return datetime(
            int(match.group("year")),
            month,
            int(match.group("day")),
            int(match.group("hour")),
            int(match.group("minute")),
            int(match.group("second")),
            int(fraction or "0"),
        )

    @classmethod
    def _is_known_noise(cls, line: str) -> bool:
        normalized = line.strip()
        lower = normalized.lower()
        if (
            lower.startswith("//")
            or lower.startswith("version ")
            or lower.startswith("begin triggerblock ")
            or lower == "end triggerblock"
            or re.fullmatch(r"(?:no\s+)?internal\s+events\s+logged", lower) is not None
        ):
            return True

        tokens = normalized.split()
        if not tokens or cls._TIMESTAMP_RE.fullmatch(tokens[0]) is None:
            return False
        remainder = " ".join(tokens[1:]).lower()
        return (
            remainder.startswith("start of measurement")
            or re.match(r"can\s+\d+\s+status:", remainder) is not None
            or re.match(r"\d+\s+statistic:", remainder) is not None
            or re.match(r"\d+\s+j1939tp\b", remainder) is not None
            or remainder.startswith("trigger ")
        )

    @classmethod
    def _base_directive(cls, line: str) -> int | None:
        match = cls._BASE_RE.fullmatch(line)
        if match is None:
            return None
        if (match.group("timestamps") or "absolute").lower() == "relative":
            raise ValueError("Vector ASC relative timestamps are not supported.")
        return 16 if match.group("base").lower() == "hex" else 10

    @staticmethod
    def _identifier(token: str, base: int) -> tuple[int, bool]:
        is_extended = token[-1:].lower() == "x"
        value = token[:-1] if is_extended else token
        return int(value, base), is_extended

    @staticmethod
    def _data(tokens: list[str], length: int, base: int) -> bytes:
        if len(tokens) < length:
            raise ValueError(f"declares {length} data bytes, got {len(tokens)}")
        values = [int(token, base) for token in tokens[:length]]
        if any(value < 0 or value > 0xFF for value in values):
            raise ValueError("data byte is outside the range 0..255")
        return bytes(values)

    @classmethod
    def _classic_frame(cls, tokens: list[str], base: int) -> Frame | None:
        if len(tokens) < 3:
            return None

        timestamp = float(tokens[0])
        channel = int(tokens[1])
        if tokens[2].lower() == "errorframe":
            return Frame(
                timestamp=timestamp,
                arbitration_id=0,
                data=b"",
                channel=channel,
                is_extended_frame=True,
                is_error_frame=True,
                is_rx=True,
            )

        if len(tokens) < 5 or tokens[3].lower() not in {"rx", "tx"}:
            return None
        frame_type = tokens[4].lower()
        if frame_type not in {"d", "r"}:
            return None

        arbitration_id, is_extended = cls._identifier(tokens[2], base)
        is_rx = tokens[3].lower() == "rx"
        if frame_type == "r":
            dlc = None
            if len(tokens) > 5:
                try:
                    dlc = int(tokens[5], base)
                except ValueError:
                    pass
            return Frame(
                timestamp=timestamp,
                arbitration_id=arbitration_id,
                data=b"",
                channel=channel,
                is_extended_frame=is_extended,
                is_remote_frame=True,
                is_rx=is_rx,
                dlc=dlc,
            )

        if len(tokens) < 6:
            raise ValueError("data frame has no DLC")
        declared_length = int(tokens[5], base)
        data = cls._data(tokens[6:], declared_length, base)
        return Frame(
            timestamp=timestamp,
            arbitration_id=arbitration_id,
            data=data,
            channel=channel,
            is_extended_frame=is_extended,
            is_rx=is_rx,
            dlc=declared_length if declared_length != len(data) else None,
        )

    @classmethod
    def _fd_frame(cls, tokens: list[str], base: int) -> Frame:
        if len(tokens) < 5:
            raise ValueError("incomplete CANFD record")

        timestamp = float(tokens[0])
        channel = int(tokens[2])
        is_rx = tokens[3].lower() == "rx"
        if tokens[3].lower() not in {"rx", "tx"}:
            raise ValueError(f"unknown CANFD direction {tokens[3]!r}")
        if tokens[4].lower() == "errorframe":
            return Frame(
                timestamp=timestamp,
                arbitration_id=0,
                data=b"",
                channel=channel,
                is_extended_frame=True,
                is_fd=True,
                is_error_frame=True,
                is_rx=is_rx,
            )

        arbitration_id, is_extended = cls._identifier(tokens[4], base)
        cursor = 5
        if cursor >= len(tokens):
            raise ValueError("incomplete CANFD record")
        if tokens[cursor] not in {"0", "1"}:
            cursor += 1
        if len(tokens) < cursor + 4:
            raise ValueError("incomplete CANFD flags and length fields")

        bitrate_switch = tokens[cursor] == "1"
        error_state_indicator = tokens[cursor + 1] == "1"
        dlc_code = int(tokens[cursor + 2], base)
        data_length = int(tokens[cursor + 3], 10)
        data = cls._data(tokens[cursor + 4 :], data_length, base)
        return Frame(
            timestamp=timestamp,
            arbitration_id=arbitration_id,
            data=data,
            channel=channel,
            is_extended_frame=is_extended,
            is_fd=True,
            is_remote_frame=data_length == 0,
            is_rx=is_rx,
            dlc=dlc_code if dlc_code != data_length else None,
            bitrate_switch=bitrate_switch,
            error_state_indicator=error_state_indicator,
        )

    @classmethod
    def _record(cls, line: str, base: int) -> Frame | None:
        tokens = line.split()
        if len(tokens) < 2 or cls._TIMESTAMP_RE.fullmatch(tokens[0]) is None:
            return None
        if tokens[1].upper() == "CANFD":
            return cls._fd_frame(tokens, base)
        if tokens[1].isdigit():
            return cls._classic_frame(tokens, base)
        return None

    def sniff(self, sample: str) -> bool:
        """Recognize an ASC base directive or supported frame row."""
        for raw_line in sample.splitlines():
            line = raw_line.strip()
            if self._BASE_RE.fullmatch(line) is not None:
                return True
            try:
                if self._record(line, 16) is not None:
                    return True
            except (ValueError, IndexError):
                continue
        return False

    def probe(self, path: Path) -> LogMeta:
        """Return the header date and format without scanning frame rows."""
        sample = read_sample(path)
        if not self.sniff(sample):
            raise ValueError(f"File '{path.name}' is not a Vector ASC log.")

        start_time = None
        for raw_line in sample.splitlines():
            line = raw_line.strip()
            if line.lower().startswith("date "):
                start_time = self._parse_date(line)
            if self._BASE_RE.fullmatch(line) is not None:
                self._base_directive(line)
        return LogMeta(format=self.name, start_time=start_time)

    def read(self, path: Path) -> Iterator[Frame]:
        """Lazily parse Vector ASC frame records from *path*."""
        base = 16
        with path.open(encoding="latin-1") as stream:
            for line_number, raw_line in enumerate(stream, start=1):
                line = raw_line.strip()
                if not line:
                    continue

                if line.lower().startswith("date "):
                    self._parse_date(line)
                    continue
                if self._BASE_RE.fullmatch(line) is not None:
                    try:
                        base = self._base_directive(line) or base
                    except ValueError as error:
                        raise ValueError(f"Vector ASC line {line_number}: {error}") from error
                    continue
                if self._is_known_noise(line):
                    continue

                try:
                    frame = self._record(line, base)
                except (IndexError, ValueError) as error:
                    raise ValueError(
                        f"Invalid Vector ASC frame at line {line_number}: {error}."
                    ) from error
                if frame is None:
                    if self.strict:
                        raise ValueError(f"Unrecognized Vector ASC line {line_number}: {line!r}.")
                    continue
                yield frame
