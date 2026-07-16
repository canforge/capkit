"""Golden and edge-case tests for the Kvaser TXT reader."""
from __future__ import annotations

from pathlib import Path

import pytest

import capkit
from capkit.readers.kvaser_txt import KvaserTxtReader

FIXTURE = Path(__file__).parent / "fixtures" / "kvaser" / "kvaser.txt"


def test_full_fixture_golden_frames() -> None:
    frames = list(capkit.read(FIXTURE))

    assert len(frames) == 300

    first = frames[0]
    assert first.timestamp == pytest.approx(100.000139)
    assert first.arbitration_id == 0x0CFBFFDB
    assert first.data == bytes.fromhex("1B3120EBB3FFD9FF")
    assert first.channel == 0
    assert first.is_extended_frame is True
    assert first.is_rx is True
    assert first.dlc is None

    last = frames[-1]
    assert last.timestamp == pytest.approx(100.589590)
    assert last.arbitration_id == 0x18F964C8
    assert last.data == bytes.fromhex("FFFFFFFFFFFFFFFF")
    assert last.channel == 0
    assert last.is_extended_frame is True
    assert last.is_rx is True


def test_parses_standard_extended_tx_and_empty_frames(tmp_path: Path) -> None:
    path = tmp_path / "variants.txt"
    path.write_text(
        "  2   123      2  0A  ff    0.125000 T\n"
        "3 1ABCDE X 0 1.500000 R\n",
        encoding="ascii",
    )

    standard, extended = list(KvaserTxtReader().read(path))

    assert standard.channel == 2
    assert standard.arbitration_id == 0x123
    assert standard.data == b"\x0a\xff"
    assert standard.timestamp == pytest.approx(0.125)
    assert standard.is_extended_frame is False
    assert standard.is_rx is False

    assert extended.channel == 3
    assert extended.arbitration_id == 0x1ABCDE
    assert extended.data == b""
    assert extended.timestamp == pytest.approx(1.5)
    assert extended.is_extended_frame is True
    assert extended.is_rx is True


def test_default_mode_skips_noise_and_latin1_text(tmp_path: Path) -> None:
    path = tmp_path / "latin1.txt"
    path.write_bytes(
        "Chn Identifier Flg DLC D0 Time Dir\n"
        "# comentário de aquisição\n"
        "0 123 1 AA 2.0 R\n"
        "Logging stopped.\n".encode("latin-1")
    )

    frames = list(KvaserTxtReader().read(path))

    assert len(frames) == 1
    assert frames[0].data == b"\xaa"


def test_strict_mode_names_unrecognized_line_and_content(tmp_path: Path) -> None:
    path = tmp_path / "strict.txt"
    path.write_text("0 123 1 AA 1.0 R\ngarbage record\n", encoding="ascii")

    with pytest.raises(ValueError, match=r"line 2: 'garbage record'"):
        list(KvaserTxtReader(strict=True).read(path))


def test_strict_mode_rejects_header(tmp_path: Path) -> None:
    path = tmp_path / "header.txt"
    path.write_text("Chn Identifier Flg DLC D0 Time Dir\n", encoding="ascii")

    with pytest.raises(ValueError, match=r"line 1: 'Chn Identifier"):
        list(KvaserTxtReader(strict=True).read(path))


def test_malformed_dlc_fails_even_in_default_mode(tmp_path: Path) -> None:
    path = tmp_path / "malformed.txt"
    path.write_text("0 123 3 01 02 1.0 R\n", encoding="ascii")

    with pytest.raises(ValueError, match=r"DLC 3 declares 3 data bytes, got 2"):
        list(KvaserTxtReader().read(path))


def test_reader_preserves_os_errors(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        list(KvaserTxtReader().read(tmp_path / "missing.txt"))


def test_sniff_accepts_header_or_complete_frame() -> None:
    reader = KvaserTxtReader()

    assert reader.sniff("Chn Identifier Flg   DLC  D0 Time Dir\n") is True
    assert reader.sniff("0 123 1 FF 0.0 R\n") is True
    assert reader.sniff("0 123 2 FF 0.0 R\n") is False
    assert reader.sniff("unrelated text\n") is False
