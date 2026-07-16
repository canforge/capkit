"""Tests for lazy third-party reader entry-point discovery."""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import capkit
import capkit.readers as reader_registry
from capkit import Frame, LogMeta
from capkit.readers.candump import CandumpReader


class PluginReader:
    name = "plugin-reader"
    extensions = (".plugin",)

    def __init__(self, *, strict: bool = False) -> None:
        self.strict = strict

    def sniff(self, sample: str) -> bool:
        return sample.startswith("PLUGIN")

    def probe(self, path: Path) -> LogMeta:
        return LogMeta(format=self.name)

    def read(self, path: Path) -> Iterator[Frame]:
        yield Frame(timestamp=1.0, arbitration_id=1, data=b"\x01")


class FakeEntryPoint:
    def __init__(self, name: str, value: Any, *, distribution: str = "example-plugin") -> None:
        self.name = name
        self.value = f"tests:{name}"
        self.dist = SimpleNamespace(name=distribution)
        self._value = value
        self.load_calls = 0

    def load(self) -> Any:
        self.load_calls += 1
        if isinstance(self._value, Exception):
            raise self._value
        return self._value


class BrokenFactoryReader(PluginReader):
    name = "broken-factory-reader"

    def __init__(self) -> None:
        raise RuntimeError("factory exploded")


@pytest.fixture
def isolated_discovery(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(reader_registry, "_READERS", reader_registry._READERS.copy())
    monkeypatch.setattr(reader_registry, "_ENTRY_POINTS_LOADED", False)


def test_discovery_is_lazy_cached_and_used_by_public_io(
    isolated_discovery: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    entry_point = FakeEntryPoint("plugin", PluginReader)
    scan_calls = 0

    def entry_points(*, group: str):
        nonlocal scan_calls
        scan_calls += 1
        assert group == "capkit.readers"
        return [entry_point]

    monkeypatch.setattr(reader_registry.metadata, "entry_points", entry_points)
    assert scan_calls == 0

    path = tmp_path / "trace.plugin"
    path.write_text("PLUGIN\n", encoding="ascii")
    assert "plugin-reader" in capkit.available_formats()
    assert scan_calls == 1
    assert entry_point.load_calls == 1
    assert capkit.probe(path) == LogMeta(format="plugin-reader")
    assert len(list(capkit.read(path))) == 1
    assert capkit.available_formats().count("plugin-reader") == 1
    assert scan_calls == 1
    assert entry_point.load_calls == 1


def test_register_reader_does_not_trigger_discovery(
    isolated_discovery: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scans = 0

    def entry_points(*, group: str):
        nonlocal scans
        scans += 1
        return []

    class RegisteredReader(PluginReader):
        name = "registered-before-scan"

    monkeypatch.setattr(reader_registry.metadata, "entry_points", entry_points)
    capkit.register_reader(RegisteredReader)

    assert scans == 0
    assert "registered-before-scan" in capkit.available_formats()
    assert scans == 1


def test_duplicate_with_builtin_names_entry_point_and_distribution(
    isolated_discovery: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entry_point = FakeEntryPoint("socketcan", CandumpReader, distribution="collision-dist")
    monkeypatch.setattr(reader_registry.metadata, "entry_points", lambda *, group: [entry_point])

    with pytest.raises(
        RuntimeError,
        match=r"entry point 'socketcan'.*distribution 'collision-dist'.*log format 'candump'",
    ):
        capkit.available_formats()


def test_duplicate_between_plugins_is_rejected_atomically(
    isolated_discovery: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = FakeEntryPoint("first", PluginReader, distribution="first-dist")
    second = FakeEntryPoint("second", PluginReader, distribution="second-dist")
    monkeypatch.setattr(reader_registry.metadata, "entry_points", lambda *, group: [first, second])

    with pytest.raises(RuntimeError, match=r"entry point 'second'.*distribution 'second-dist'"):
        capkit.available_formats()
    assert "plugin-reader" not in reader_registry._READERS


@pytest.mark.parametrize(
    ("entry_point", "message"),
    [
        (FakeEntryPoint("broken-load", RuntimeError("load exploded"), distribution="broken-dist"), "load exploded"),
        (FakeEntryPoint("not-a-class", None, distribution="invalid-dist"), "requires a reader class"),
        (
            FakeEntryPoint("broken-factory", BrokenFactoryReader, distribution="factory-dist"),
            "factory exploded",
        ),
    ],
)
def test_broken_entry_points_wrap_failures_with_provenance(
    isolated_discovery: None,
    monkeypatch: pytest.MonkeyPatch,
    entry_point: FakeEntryPoint,
    message: str,
) -> None:
    monkeypatch.setattr(reader_registry.metadata, "entry_points", lambda *, group: [entry_point])

    with pytest.raises(RuntimeError) as exc_info:
        capkit.available_formats()

    error = str(exc_info.value)
    assert entry_point.name in error
    assert entry_point.dist.name in error
    assert message in error
