"""Tests for public I/O and internal reader resolution."""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

import capkit
import capkit.readers as reader_registry
from capkit import Frame, LogMeta
from capkit.integration import DispatchReader
from capkit.readers.kvaser_txt import KvaserTxtReader

FRAME_LINE = "0 123 1 AA 1.25 R\n"


class StaticReader:
    name = "static"
    extensions = (".static",)
    sniff_calls = 0

    def __init__(self, *, strict: bool = False) -> None:
        self.strict = strict

    def sniff(self, sample: str) -> bool:
        type(self).sniff_calls += 1
        return sample.startswith("STATIC")

    def probe(self, path: Path) -> LogMeta:
        return LogMeta(format=self.name)

    def read(self, path: Path) -> Iterator[Frame]:
        yield Frame(timestamp=0.0, arbitration_id=1, data=b"")


class AlsoKvaserReader(KvaserTxtReader):
    name = "also-kvaser"
    extensions = (".other",)


class StaticTxtReader(StaticReader):
    name = "static-txt"
    extensions = (".txt",)


@pytest.fixture
def isolated_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(reader_registry, "_READERS", reader_registry._READERS.copy())


def test_register_reader_supports_public_resolution(
    isolated_registry: None,
    tmp_path: Path,
) -> None:
    capkit.register_reader(StaticReader)
    path = tmp_path / "sample.static"
    path.write_text("STATIC\n", encoding="ascii")

    assert "static" in capkit.available_formats()
    assert len(list(capkit.read(path, format="STATIC"))) == 1
    StaticReader.sniff_calls = 0
    assert len(list(capkit.read(path))) == 1
    assert StaticReader.sniff_calls == 0
    assert capkit.probe(path) == LogMeta(format="static")


@pytest.mark.parametrize("reader_type", [KvaserTxtReader, StaticReader])
def test_register_reader_rejects_duplicate_names(
    isolated_registry: None,
    reader_type: type[StaticReader] | type[KvaserTxtReader],
) -> None:
    if reader_type is StaticReader:
        capkit.register_reader(reader_type)

    with pytest.raises(
        ValueError,
        match=rf"^Log format '{reader_type.name}' is already registered\.$",
    ):
        capkit.register_reader(reader_type)


def test_register_reader_rejects_nonconforming_classes(isolated_registry: None) -> None:
    class NoName:
        pass

    class NoExtensions(StaticReader):
        name = "no-extensions"
        extensions = ()

    class RequiredOption(StaticReader):
        name = "required-option"

        def __init__(self, required: object) -> None:
            self.required = required

    class MissingRead:
        name = "missing-read"
        extensions = (".missing",)

        def sniff(self, sample: str) -> bool:
            return False

        def probe(self, path: Path) -> LogMeta:
            return LogMeta(format=self.name)

    for reader_type in (NoName, NoExtensions, RequiredOption, MissingRead):
        with pytest.raises(TypeError):
            capkit.register_reader(reader_type)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match=r"requires a reader class"):
        capkit.register_reader(StaticReader())  # type: ignore[arg-type]


def test_registered_txt_reader_uses_sniffing_and_dispatch(
    isolated_registry: None,
    tmp_path: Path,
) -> None:
    capkit.register_reader(StaticTxtReader)
    path = tmp_path / "sample.txt"
    path.write_text("STATIC\n", encoding="ascii")

    assert len(list(capkit.read(path))) == 1
    assert len(list(DispatchReader().read(path))) == 1


def test_registered_txt_reader_ambiguous_sniff_fails_clearly(
    isolated_registry: None,
    tmp_path: Path,
) -> None:
    class AlsoKvaserTxtReader(KvaserTxtReader):
        name = "also-kvaser-txt"

    capkit.register_reader(AlsoKvaserTxtReader)
    path = tmp_path / "trace.txt"
    path.write_text(FRAME_LINE, encoding="ascii")

    with pytest.raises(ValueError, match=r"^Unknown log format for 'trace\.txt'"):
        list(capkit.read(path))


def test_available_formats_are_sorted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        reader_registry,
        "_READERS",
        {"static": StaticReader, "also-kvaser": AlsoKvaserReader},
    )

    assert capkit.available_formats() == ["also-kvaser", "static"]


def test_extension_resolution_is_case_insensitive(tmp_path: Path) -> None:
    path = tmp_path / "trace.TXT"
    path.write_text(FRAME_LINE, encoding="ascii")

    assert list(capkit.read(path))[0].data == b"\xaa"


def test_sole_extension_claim_does_not_sniff(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    StaticReader.sniff_calls = 0
    monkeypatch.setattr(reader_registry, "_READERS", {"static": StaticReader})

    frames = list(capkit.read(tmp_path / "does-not-need-to-exist.static"))

    assert len(frames) == 1
    assert StaticReader.sniff_calls == 0


def test_explicit_format_overrides_extension(tmp_path: Path) -> None:
    path = tmp_path / "trace.bin"
    path.write_text(FRAME_LINE, encoding="ascii")

    frame = list(capkit.read(path, format="KVASER-TXT"))[0]

    assert frame.arbitration_id == 0x123


def test_unknown_explicit_format_lists_available_formats(tmp_path: Path) -> None:
    frames = capkit.read(tmp_path / "trace.bin", format="missing")

    with pytest.raises(ValueError) as exc_info:
        next(frames)

    assert str(exc_info.value) == (
        "Unknown log format 'missing'. Available formats: candump, kvaser-txt, vector-asc."
    )


def test_unknown_extension_uses_content_sniffing(tmp_path: Path) -> None:
    path = tmp_path / "trace.dat"
    path.write_text(FRAME_LINE, encoding="ascii")

    assert list(capkit.read(path))[0].data == b"\xaa"


def test_unknown_content_lists_available_formats(tmp_path: Path) -> None:
    path = tmp_path / "trace.dat"
    path.write_text("not a log\n", encoding="ascii")

    with pytest.raises(ValueError) as exc_info:
        list(capkit.read(path))

    assert str(exc_info.value) == (
        "Unknown log format for 'trace.dat'. Available formats: candump, kvaser-txt, vector-asc."
    )


def test_ambiguous_sniff_fails_clearly(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        reader_registry,
        "_READERS",
        {"kvaser-txt": KvaserTxtReader, "also-kvaser": AlsoKvaserReader},
    )
    path = tmp_path / "trace.dat"
    path.write_text(FRAME_LINE, encoding="ascii")

    with pytest.raises(ValueError, match=r"Unknown log format for 'trace\.dat'"):
        list(capkit.read(path))


def test_empty_registry_fails_cleanly(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(reader_registry, "_READERS", {})

    assert capkit.available_formats() == []
    with pytest.raises(ValueError, match=r"^No log formats are registered\.$"):
        list(capkit.read(tmp_path / "trace.txt"))
    with pytest.raises(ValueError, match=r"^No log formats are registered\.$"):
        capkit.probe(tmp_path / "trace.txt")


def test_read_is_lazy(tmp_path: Path) -> None:
    frames = capkit.read(tmp_path / "missing.txt")

    assert iter(frames) is frames
    with pytest.raises(FileNotFoundError):
        next(frames)


def test_probe_returns_metadata_and_validates_content(tmp_path: Path) -> None:
    valid = tmp_path / "valid.txt"
    valid.write_text(FRAME_LINE, encoding="ascii")
    invalid = tmp_path / "invalid.txt"
    invalid.write_text("noise\n", encoding="ascii")

    assert capkit.probe(valid) == LogMeta(format="kvaser-txt")
    with pytest.raises(ValueError, match=r"is not a Kvaser TXT log"):
        capkit.probe(invalid)


def test_probe_preserves_os_errors(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        capkit.probe(tmp_path / "missing.txt")


def test_dispatch_reader_always_sniffs_txt_content(tmp_path: Path) -> None:
    path = tmp_path / "noise.txt"
    path.write_text("noise\n", encoding="ascii")

    assert list(capkit.read(path)) == []
    with pytest.raises(ValueError, match=r"Unknown log format for 'noise\.txt'"):
        list(DispatchReader().read(path))


def test_public_strict_option_reaches_reader(tmp_path: Path) -> None:
    path = tmp_path / "strict.txt"
    path.write_text("header or noise\n", encoding="ascii")

    with pytest.raises(ValueError, match=r"Unrecognized Kvaser TXT line 1"):
        list(capkit.read(path, strict=True))
