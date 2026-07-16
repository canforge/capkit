"""Optional end-to-end contract tests against an installed dbckit."""
from __future__ import annotations

from itertools import islice
from pathlib import Path

import pytest

import capkit

dbckit = pytest.importorskip("dbckit")
log_module = pytest.importorskip("dbckit.operations.log")

FIXTURE = Path(__file__).parent / "fixtures" / "kvaser" / "kvaser.txt"

MINIMAL_DBC = """VERSION "1.0"

NS_ :

BS_ :

BU_ : ECU

BO_ 2365325275 EngineData: 8 ECU
 SG_ SecondByte : 8|8@1+ (1,0) [0|255] "" ECU
"""


@pytest.fixture
def database():
    return dbckit.parse(MINIMAL_DBC)


def test_decode_frames_accepts_capkit_frame(database) -> None:
    decoded = list(islice(dbckit.decode_frames(database, capkit.read(FIXTURE)), 1))

    assert len(decoded) == 1
    assert decoded[0].timestamp == pytest.approx(100.000139)
    assert decoded[0].arbitration_id == 0x0CFBFFDB
    assert decoded[0].signals["SecondByte"] == pytest.approx(49.0)
    assert decoded[0].channel == 0
    assert decoded[0].is_extended_frame is True


def test_decode_log_discovers_txt_entry_point(database, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(log_module, "_ENTRY_POINTS", None)
    monkeypatch.setattr(log_module, "_ENTRY_POINT_READERS", {})

    decoded = list(islice(dbckit.decode_log(database, FIXTURE), 1))

    assert len(decoded) == 1
    assert decoded[0].signals["SecondByte"] == pytest.approx(49.0)
