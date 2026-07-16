"""Reader registry and format-resolution logic."""
from __future__ import annotations

from importlib import metadata
from pathlib import Path
from typing import cast

from capkit.readers.base import Reader, read_sample
from capkit.readers.candump import CandumpReader
from capkit.readers.kvaser_txt import KvaserTxtReader
from capkit.readers.vector_asc import VectorAscReader

_READERS: dict[str, type[Reader]] = {
    CandumpReader.name: cast(type[Reader], CandumpReader),
    KvaserTxtReader.name: cast(type[Reader], KvaserTxtReader),
    VectorAscReader.name: cast(type[Reader], VectorAscReader),
}
_ENTRY_POINTS_LOADED = False


def _validate_reader(reader_type: object) -> tuple[str, type[Reader]]:
    if not isinstance(reader_type, type):
        raise TypeError("register_reader() requires a reader class, not an instance.")

    name = getattr(reader_type, "name", None)
    if not isinstance(name, str) or not name.strip():
        raise TypeError("Reader type must define a non-empty string 'name'.")

    normalized = name.strip().lower()
    extensions = getattr(reader_type, "extensions", None)
    if (
        not isinstance(extensions, tuple)
        or not extensions
        or any(not isinstance(extension, str) or not extension.startswith(".") for extension in extensions)
    ):
        raise TypeError(
            f"Reader type '{normalized}' must define a non-empty tuple of dot-prefixed extensions."
        )

    try:
        reader = reader_type()
    except Exception as error:
        raise TypeError(
            f"Reader type '{normalized}' must be zero-argument constructible: {error}"
        ) from error

    if any(not callable(getattr(reader, method, None)) for method in ("sniff", "probe", "read")):
        raise TypeError(f"Reader type '{normalized}' must define callable sniff(), probe(), and read() methods.")

    return normalized, cast(type[Reader], reader_type)


def register_reader(reader_type: type[Reader]) -> None:
    """Register a zero-argument reader class for process-wide format resolution."""
    normalized, validated_type = _validate_reader(reader_type)
    if normalized in _READERS:
        raise ValueError(f"Log format '{normalized}' is already registered.")
    _READERS[normalized] = validated_type


def _distribution_name(entry_point: metadata.EntryPoint) -> str:
    distribution = getattr(entry_point, "dist", None)
    name = getattr(distribution, "name", None)
    if isinstance(name, str) and name:
        return name
    distribution_metadata = getattr(distribution, "metadata", None)
    if distribution_metadata is not None:
        try:
            metadata_name = distribution_metadata["Name"]
        except (KeyError, TypeError):
            pass
        else:
            if isinstance(metadata_name, str) and metadata_name:
                return metadata_name
    return "unknown"


def _entry_point_context(entry_point: metadata.EntryPoint) -> str:
    return (
        f"capkit.readers entry point '{entry_point.name}' "
        f"from distribution '{_distribution_name(entry_point)}'"
    )


def _load_entry_point_readers() -> None:
    global _ENTRY_POINTS_LOADED
    if _ENTRY_POINTS_LOADED:
        return

    discovered: dict[str, type[Reader]] = {}
    for entry_point in metadata.entry_points(group="capkit.readers"):
        context = _entry_point_context(entry_point)
        try:
            loaded = entry_point.load()
            normalized, reader_type = _validate_reader(loaded)
        except Exception as error:
            raise RuntimeError(f"Failed to load {context}: {error}") from error

        if normalized in _READERS or normalized in discovered:
            raise RuntimeError(
                f"Reader {context} conflicts with already registered log format '{normalized}'."
            )
        discovered[normalized] = reader_type

    _READERS.update(discovered)
    _ENTRY_POINTS_LOADED = True


def registered_formats() -> list[str]:
    """Return sorted registered reader names."""
    _load_entry_point_readers()
    return sorted(_READERS)


def _available_label() -> str:
    return ", ".join(registered_formats())


def _reader_type_for(
    path: Path,
    *,
    format: str | None = None,
    sniff_only: bool = False,
) -> type[Reader]:
    _load_entry_point_readers()
    if not _READERS:
        raise ValueError("No log formats are registered.")

    if format is not None:
        normalized = format.strip().lower()
        reader_type = _READERS.get(normalized)
        if reader_type is None:
            raise ValueError(f"Unknown log format '{format}'. Available formats: {_available_label()}.")
        return reader_type

    if not sniff_only:
        extension = path.suffix.lower()
        candidates = [
            reader_type
            for reader_type in _READERS.values()
            if extension and extension in (claimed.lower() for claimed in reader_type.extensions)
        ]
        if len(candidates) == 1:
            return candidates[0]

    sample = read_sample(path)
    matches = [reader_type for reader_type in _READERS.values() if reader_type().sniff(sample)]
    if len(matches) == 1:
        return matches[0]

    raise ValueError(f"Unknown log format for '{path.name}'. Available formats: {_available_label()}.")


def create_reader(
    path: Path,
    *,
    format: str | None = None,
    options: dict[str, object] | None = None,
    sniff_only: bool = False,
) -> Reader:
    """Resolve and construct a reader for *path*."""
    reader_type = _reader_type_for(path, format=format, sniff_only=sniff_only)
    return cast(Reader, reader_type(**(options or {})))


__all__ = ["CandumpReader", "KvaserTxtReader", "Reader", "VectorAscReader", "register_reader"]
