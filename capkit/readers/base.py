"""Shared reader protocol and bounded file-sampling helper."""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Protocol

from capkit.model import Frame, LogMeta

SNIFF_SIZE = 4096


class Reader(Protocol):
    """A stateless log-format reader."""

    name: str
    extensions: tuple[str, ...]

    def sniff(self, sample: str) -> bool:
        """Return whether *sample* looks like this reader's format."""
        ...

    def probe(self, path: Path) -> LogMeta:
        """Return cheap metadata from *path*."""
        ...

    def read(self, path: Path) -> Iterator[Frame]:
        """Lazily yield frames from *path*."""
        ...


def read_sample(path: Path) -> str:
    """Read and Latin-1 decode at most the first 4 KiB of *path*."""
    with path.open("rb") as stream:
        return stream.read(SNIFF_SIZE).decode("latin-1")
