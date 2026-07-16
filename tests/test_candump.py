"""Golden and edge-case tests for the can-utils candump reader."""
from __future__ import annotations

from pathlib import Path

import pytest

import capkit
from capkit.readers.candump import CandumpReader
from capkit.readers.kvaser_txt import KvaserTxtReader

FIXTURE = Path(__file__).parent / "fixtures" / "candump" / "candump.log"
KVASER_FIXTURE = Path(__file__).parent / "fixtures" / "kvaser" / "kvaser.txt"


def test_full_fixture_golden_frames() -> None:
    frames = list(capkit.read(FIXTURE))

    assert len(frames) == 300
    assert all(frame.is_extended_frame for frame in frames)
    assert all(frame.is_rx is True for frame in frames)
    assert all(frame.channel == 0 for frame in frames)

    first = frames[0]
    assert first.timestamp == pytest.approx(1752624000.000139)
    assert first.arbitration_id == 0x0CFBFFDB
    assert first.data == bytes.fromhex("1B3120EBB3FFD9FF")

    last = frames[-1]
    assert last.timestamp == pytest.approx(1752624000.589590)
    assert last.arbitration_id == 0x18F964C8
    assert last.data == bytes.fromhex("FFFFFFFFFFFFFFFF")


def test_parses_standard_tx_empty_remote_fd_and_missing_direction(tmp_path: Path) -> None:
    path = tmp_path / "variants.log"
    path.write_text(
        "(1.000001) can7 123#0AFF T\n"
        "(2.0) bus 000001AB#\n"
        "(3.0) vcan2 456#R\n"
        "(4.0) vcan2 456#R8 R\n"
        "(5.0) can9 000001AB##3010203 R\n",
        encoding="ascii",
    )

    standard, empty, remote, remote_with_dlc, fd = list(CandumpReader().read(path))

    assert standard.arbitration_id == 0x123
    assert standard.data == b"\x0a\xff"
    assert standard.channel == 7
    assert standard.is_extended_frame is False
    assert standard.is_rx is False

    assert empty.data == b""
    assert empty.channel is None
    assert empty.is_extended_frame is True
    assert empty.is_rx is None

    assert remote.is_remote_frame is True
    assert remote.data == b""
    assert remote.dlc is None
    assert remote_with_dlc.dlc == 8

    assert fd.is_fd is True
    assert fd.data == b"\x01\x02\x03"
    assert fd.bitrate_switch is True
    assert fd.error_state_indicator is True


def test_python_can_writer_variants_round_trip(tmp_path: Path) -> None:
    can = pytest.importorskip("can")
    path = tmp_path / "writer.log"
    writer = can.CanutilsLogWriter(path)
    try:
        writer.on_message_received(
            can.Message(timestamp=1.0, arbitration_id=0x123, data=[1, 2], channel="can4", is_rx=False)
        )
        writer.on_message_received(
            can.Message(timestamp=2.0, arbitration_id=0x1ABCDE, is_extended_id=True, is_remote_frame=True, dlc=6)
        )
        writer.on_message_received(
            can.Message(
                timestamp=3.0,
                arbitration_id=0x321,
                data=[3, 4, 5],
                is_fd=True,
                bitrate_switch=True,
                error_state_indicator=True,
            )
        )
    finally:
        writer.stop()

    standard, remote, fd = list(CandumpReader().read(path))

    assert standard.is_rx is False
    assert standard.channel == 4
    assert remote.is_remote_frame is True
    assert remote.dlc is None  # python-can's writer emits bare ``#R`` records
    assert fd.is_fd is True
    assert fd.bitrate_switch is True
    assert fd.error_state_indicator is True


def test_default_skips_malformed_and_error_records_while_strict_rejects(tmp_path: Path) -> None:
    path = tmp_path / "dirty.log"
    path.write_text(
        "comment\n"
        "(1.0) can0 123#ABC\n"
        "(2.0) can0 20000000#0000000000000000 R\n"
        "(3.0) can0 123#AA R\n",
        encoding="ascii",
    )

    assert [frame.data for frame in CandumpReader().read(path)] == [b"\xaa"]
    with pytest.raises(ValueError, match=r"Unrecognized candump line 1: 'comment'"):
        list(CandumpReader(strict=True).read(path))

    error_only = tmp_path / "error.log"
    error_only.write_text("(2.0) can0 20000000#00 R\n", encoding="ascii")
    with pytest.raises(ValueError, match=r"Unrecognized candump line 1"):
        list(CandumpReader(strict=True).read(error_only))


def test_probe_sniff_cross_format_and_os_errors(tmp_path: Path) -> None:
    reader = CandumpReader()

    assert reader.probe(FIXTURE) == capkit.LogMeta(format="candump")
    assert reader.sniff(FIXTURE.read_text(encoding="ascii")[:4096]) is True
    assert reader.sniff(KVASER_FIXTURE.read_text(encoding="ascii")[:4096]) is False
    assert KvaserTxtReader().sniff(FIXTURE.read_text(encoding="ascii")[:4096]) is False

    invalid = tmp_path / "invalid.log"
    invalid.write_text("not a log\n", encoding="ascii")
    with pytest.raises(ValueError, match=r"is not a candump log"):
        reader.probe(invalid)
    with pytest.raises(FileNotFoundError):
        reader.probe(tmp_path / "missing.log")
