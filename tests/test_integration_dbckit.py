"""Optional end-to-end contract tests against an installed dbckit."""
from __future__ import annotations

import re
from collections.abc import Iterator
from importlib.metadata import version
from itertools import islice
from pathlib import Path

import pytest

import capkit
from capkit.readers.vector_asc import VectorAscReader

dbckit = pytest.importorskip("dbckit")
log_module = pytest.importorskip("dbckit.operations.log")

FIXTURE = Path(__file__).parent / "fixtures" / "kvaser" / "kvaser.txt"
CANDUMP_FIXTURE = Path(__file__).parent / "fixtures" / "candump" / "candump.log"
ASC_FIXTURE = Path(__file__).parent / "fixtures" / "vector_asc" / "python_can_logfile.asc"

_DBCKIT_VERSION_MATCH = re.match(r"^(\d+)\.(\d+)", version("dbckit"))
assert _DBCKIT_VERSION_MATCH is not None
DBCKIT_MAJOR_MINOR = tuple(int(component) for component in _DBCKIT_VERSION_MATCH.groups())

MINIMAL_DBC = """VERSION "1.0"

NS_ :

BS_ :

BU_ : ECU

BO_ 2365325275 EngineData: 8 ECU
 SG_ SecondByte : 8|8@1+ (1,0) [0|255] "" ECU

BO_ 418119424 AscData: 8 ECU
 SG_ FirstByte : 0|8@1+ (1,0) [0|255] "" ECU
"""


@pytest.fixture
def database():
    return dbckit.parse(MINIMAL_DBC)


def _reset_dbckit_reader_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reset entry-point discovery across dbckit versions in one isolated place."""
    for module in (dbckit, log_module):
        reset = getattr(module, "reset_reader_cache", None)
        if callable(reset):
            reset()
            return

    if DBCKIT_MAJOR_MINOR >= (1, 2):
        pytest.fail("dbckit >=1.2 must expose the public reset_reader_cache() hook")

    private_cache_names = ("_ENTRY_POINTS", "_ENTRY_POINT_READERS")
    missing = [name for name in private_cache_names if not hasattr(log_module, name)]
    if missing:
        pytest.fail(
            "dbckit has no public reset_reader_cache() and its compatibility "
            f"cache layout is unrecognized (missing: {', '.join(missing)})"
        )

    # dbckit 1.0/1.1 compatibility fallback. Keep private-state knowledge here.
    monkeypatch.setattr(log_module, "_ENTRY_POINTS", None)
    monkeypatch.setattr(log_module, "_ENTRY_POINT_READERS", {})


@pytest.fixture
def fresh_dbckit_reader_discovery(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    _reset_dbckit_reader_cache(monkeypatch)
    yield
    _reset_dbckit_reader_cache(monkeypatch)


def test_decode_frames_accepts_capkit_frame(database) -> None:
    decoded = list(islice(dbckit.decode_frames(database, capkit.read(FIXTURE)), 1))

    assert len(decoded) == 1
    assert decoded[0].timestamp == pytest.approx(100.000139)
    assert decoded[0].arbitration_id == 0x0CFBFFDB
    assert decoded[0].signals["SecondByte"] == pytest.approx(49.0)
    assert decoded[0].channel == 0
    assert decoded[0].is_extended_frame is True


@pytest.mark.parametrize(
    (
        "path",
        "expected_timestamp",
        "expected_arbitration_id",
        "signal_name",
        "expected_signal",
        "expected_channel",
    ),
    [
        pytest.param(FIXTURE, 100.000139, 0x0CFBFFDB, "SecondByte", 49.0, 0, id="kvaser-txt"),
        pytest.param(CANDUMP_FIXTURE, 1752624000.000139, 0x0CFBFFDB, "SecondByte", 49.0, 0, id="candump"),
        pytest.param(ASC_FIXTURE, 3.098426, 0x18EBFF00, "FirstByte", 1.0, 1, id="vector-asc"),
    ],
)
def test_decode_log_discovers_capkit_entry_points(
    database,
    fresh_dbckit_reader_discovery: None,
    path: Path,
    expected_timestamp: float,
    expected_arbitration_id: int,
    signal_name: str,
    expected_signal: float,
    expected_channel: int,
) -> None:
    decoded = next(dbckit.decode_log(database, path))

    assert decoded.timestamp == pytest.approx(expected_timestamp)
    assert decoded.arbitration_id == expected_arbitration_id
    assert decoded.signals[signal_name] == pytest.approx(expected_signal)
    assert decoded.channel == expected_channel
    assert decoded.is_extended_frame is True


@pytest.mark.skipif(
    DBCKIT_MAJOR_MINOR < (1, 2),
    reason="dbckit 1.2 formalizes capkit's ASC takeover contract",
)
def test_decode_log_prefers_capkit_vector_asc_reader(
    database,
    fresh_dbckit_reader_discovery: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    read_calls = 0
    original_read = VectorAscReader.read

    def observed_read(self: VectorAscReader, path: Path) -> Iterator[capkit.Frame]:
        nonlocal read_calls
        read_calls += 1
        yield from original_read(self, path)

    monkeypatch.setattr(VectorAscReader, "read", observed_read)

    decoded = next(dbckit.decode_log(database, ASC_FIXTURE))

    assert read_calls == 1
    assert decoded.signals["FirstByte"] == pytest.approx(1.0)
