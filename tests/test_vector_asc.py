"""Golden and edge-case tests for the Vector ASC reader."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

import capkit
from capkit.readers.candump import CandumpReader
from capkit.readers.kvaser_txt import KvaserTxtReader
from capkit.readers.vector_asc import VectorAscReader

FIXTURE = Path(__file__).parent / "fixtures" / "vector_asc" / "python_can_logfile.asc"
KVASER_FIXTURE = Path(__file__).parent / "fixtures" / "kvaser" / "kvaser.txt"
CANDUMP_FIXTURE = Path(__file__).parent / "fixtures" / "candump" / "candump.log"


def test_full_fixture_golden_frames() -> None:
    frames = list(capkit.read(FIXTURE))

    assert len(frames) == 20
    assert sum(frame.is_fd for frame in frames) == 4
    assert sum(frame.is_error_frame for frame in frames) == 4
    assert sum(frame.is_remote_frame for frame in frames) == 4
    assert sum(frame.is_extended_frame for frame in frames) == 13
    assert sum(frame.is_rx is True for frame in frames) == 15

    first = frames[0]
    assert first.timestamp == pytest.approx(2.501000)
    assert first.channel == 1
    assert first.arbitration_id == 0
    assert first.data == b""
    assert first.is_error_frame is True

    last = frames[-1]
    assert last.timestamp == pytest.approx(30.806898)
    assert last.channel == 5
    assert last.is_fd is True
    assert last.is_error_frame is True
    assert last.is_extended_frame is True
    assert last.is_rx is False


def test_fd_flags_dlc_codes_names_and_remote_shape() -> None:
    frames = list(VectorAscReader().read(FIXTURE))
    first_fd, remote_fd, long_fd, _error_fd = frames[-4:]

    assert first_fd.data == bytes.fromhex("01 02 03 04 05 06 07 08")
    assert first_fd.bitrate_switch is True
    assert first_fd.error_state_indicator is False
    assert first_fd.dlc is None

    assert remote_fd.is_extended_frame is True
    assert remote_fd.is_remote_frame is True
    assert remote_fd.dlc == 5

    assert len(long_fd.data) == 64
    assert long_fd.dlc == 0xF


def test_probe_returns_naive_header_datetime() -> None:
    assert capkit.probe(FIXTURE) == capkit.LogMeta(
        format="vector-asc",
        start_time=datetime(2017, 9, 30, 15, 6, 13, 191000),
    )


def test_decimal_base_and_optional_fd_symbolic_name(tmp_path: Path) -> None:
    path = tmp_path / "decimal.asc"
    path.write_text(
        "date Mon Jan 2 03:04:05.006 2023\n"
        "base dec timestamps absolute\n"
        "internal events logged\n"
        "0.100000 2 291 Rx d 2 10 255\n"
        "0.200000 3 300x Tx r 8 Length = 10\n"
        "0.300000 CANFD 4 Rx 801 Message_Name 1 1 9 12 "
        "0 1 2 3 4 5 6 7 8 9 10 255 metadata\n",
        encoding="ascii",
    )

    data, remote, fd = list(VectorAscReader().read(path))

    assert data.arbitration_id == 291
    assert data.data == b"\x0a\xff"
    assert remote.arbitration_id == 300
    assert remote.is_extended_frame is True
    assert remote.dlc == 8
    assert fd.arbitration_id == 801
    assert fd.data[-1] == 255
    assert fd.dlc == 9
    assert fd.bitrate_switch is True
    assert fd.error_state_indicator is True


def test_relative_timestamps_fail_in_probe_and_read(tmp_path: Path) -> None:
    path = tmp_path / "relative.asc"
    path.write_text(
        "date Mon Jan 2 03:04:05.006 2023\n"
        "base hex timestamps relative\n"
        "internal events logged\n",
        encoding="ascii",
    )

    with pytest.raises(ValueError, match=r"relative timestamps are not supported"):
        VectorAscReader().probe(path)
    with pytest.raises(ValueError, match=r"Vector ASC line 2: .*relative timestamps"):
        list(VectorAscReader().read(path))


def test_known_noise_is_skipped_in_strict_mode(tmp_path: Path) -> None:
    path = tmp_path / "noise.asc"
    path.write_text(
        "date Mon Jan 2 03:04:05 2023\n"
        "base hex timestamps absolute\n"
        "internal events logged\n"
        "// version 9.0\n"
        "Begin Triggerblock Mon Jan 2 03:04:05 2023\n"
        "0.0 Start of measurement\n"
        "0.1 CAN 1 Status:chip status error active\n"
        "0.2 1 Statistic: D 0 R 0\n"
        "0.3 1 J1939TP FEE3p ignored\n"
        "End TriggerBlock\n"
        "0.4 1 123 Rx d 1 AA\n",
        encoding="ascii",
    )

    assert [frame.data for frame in VectorAscReader(strict=True).read(path)] == [b"\xaa"]


def test_dirty_and_corrupt_rows_follow_strict_policy(tmp_path: Path) -> None:
    dirty = tmp_path / "dirty.asc"
    dirty.write_text("base hex timestamps absolute\ngarbage\n0.1 1 123 Rx d 1 AA\n", encoding="ascii")

    assert len(list(VectorAscReader().read(dirty))) == 1
    with pytest.raises(ValueError, match=r"Unrecognized Vector ASC line 2: 'garbage'"):
        list(VectorAscReader(strict=True).read(dirty))

    corrupt = tmp_path / "corrupt.asc"
    corrupt.write_text("base hex timestamps absolute\n0.1 1 123 Rx d 2 AA\n", encoding="ascii")
    with pytest.raises(ValueError, match=r"line 2: declares 2 data bytes, got 1"):
        list(VectorAscReader().read(corrupt))


def test_non_english_month_is_not_claimed(tmp_path: Path) -> None:
    path = tmp_path / "month.asc"
    path.write_bytes(
        "date Sam Mär 30 15:06:13.191 2017\nbase hex timestamps absolute\n".encode("latin-1")
    )

    with pytest.raises(ValueError, match=r"Unsupported Vector ASC date header"):
        VectorAscReader().probe(path)


def test_sniff_cross_format_and_os_errors(tmp_path: Path) -> None:
    sample = FIXTURE.read_text(encoding="latin-1")[:4096]
    reader = VectorAscReader()

    assert reader.sniff(sample) is True
    assert reader.sniff(KVASER_FIXTURE.read_text(encoding="latin-1")[:4096]) is False
    assert reader.sniff(CANDUMP_FIXTURE.read_text(encoding="latin-1")[:4096]) is False
    assert KvaserTxtReader().sniff(sample) is False
    assert CandumpReader().sniff(sample) is False
    with pytest.raises(FileNotFoundError):
        reader.probe(tmp_path / "missing.asc")
