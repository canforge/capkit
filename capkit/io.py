"""Public file-reading and format-discovery operations."""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from capkit.model import Frame, LogMeta
from capkit.readers import create_reader, registered_formats


def read(
    path: str | Path,
    *,
    format: str | None = None,
    strict: bool = False,
    **reader_options: object,
) -> Iterator[Frame]:
    """Lazily read frames from *path* using an explicit or detected format."""
    source = Path(path)

    def frames() -> Iterator[Frame]:
        options = {"strict": strict, **reader_options}
        reader = create_reader(source, format=format, options=options)
        yield from reader.read(source)

    return frames()


def probe(path: str | Path, *, format: str | None = None) -> LogMeta:
    """Return cheap, header-derived metadata for *path*."""
    source = Path(path)
    reader = create_reader(source, format=format)
    return reader.probe(source)


def available_formats() -> list[str]:
    """Return the sorted names of registered log formats."""
    return registered_formats()
