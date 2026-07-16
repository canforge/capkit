"""Adapters exposed to dbckit through package entry points."""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from capkit.model import Frame
from capkit.readers import create_reader


class DispatchReader:
    """Sniff and delegate generic file extensions such as ``.txt``."""

    def __init__(self, *, strict: bool = False, **reader_options: object) -> None:
        self.strict = strict
        self.reader_options = reader_options

    def read(self, path: Path) -> Iterator[Frame]:
        """Lazily sniff *path* and yield frames from the matching reader."""
        options = {"strict": self.strict, **self.reader_options}
        reader = create_reader(path, options=options, sniff_only=True)
        yield from reader.read(path)
