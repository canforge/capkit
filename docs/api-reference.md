# `capkit` API Reference

Version covered: `0.2.0`

This file documents the public Python API exported by `capkit`:

- `read`, `probe`, `available_formats`, `register_reader`
- `Frame`, `LogMeta`

Also public, importable from their submodules:

- `capkit.readers.candump.CandumpReader`
- `capkit.readers.kvaser_txt.KvaserTxtReader`
- `capkit.readers.vector_asc.VectorAscReader`
- `capkit.integration.DispatchReader`

Internal helpers prefixed with `_` are not public.

## API conventions

- Models are frozen, slotted dataclasses.
- `read()` is lazy: nothing is opened or parsed until the returned iterator is
  consumed.
- Unknown or undetectable formats raise `ValueError`; unreadable paths raise the
  underlying `OSError` subclass, unchanged.
- Reader options are keyword-only and have defaults; every reader is
  constructible with no arguments.

## Models

### `Frame`

A single CAN frame read from a log file.

Fields:

- `timestamp: float` — seconds, exactly as recorded in the source
- `arbitration_id: int`
- `data: bytes`
- `channel: int | None = None`
- `is_extended_frame: bool = False`
- `is_fd: bool = False`
- `is_remote_frame: bool = False`
- `is_error_frame: bool = False`
- `is_rx: bool | None = None` — `None` when the log records no direction
- `dlc: int | None = None` — populated only when it conveys information
  different from `len(data)`
- `bitrate_switch: bool = False` — CAN FD bit-rate switch flag
- `error_state_indicator: bool = False` — CAN FD error-state indicator flag

### `LogMeta`

Header-derived metadata returned by `probe()`.

Fields:

- `format: str` — the reader name, e.g. `"kvaser-txt"`
- `start_time: datetime | None = None` — absolute capture start when the header
  records one; `kvaser-txt` currently always returns `None`
- `extra: dict[str, str] = {}` — reader-specific header values

## Functions

### `read()`

```python
read(
    path: str | Path,
    *,
    format: str | None = None,
    strict: bool = False,
    **reader_options,
) -> Iterator[Frame]
```

Returns a lazy iterator of frames. Format resolution:

1. `format=` names a reader; an unknown name raises `ValueError`.
2. Otherwise, a file extension claimed by exactly one reader selects it.
3. Otherwise, the first 4 KiB are read as Latin-1 and offered to every reader's
   `sniff()`; exactly one match selects it, anything else raises `ValueError`
   listing the available formats.

`strict=False` (default) skips unrecognized nonblank lines; `strict=True` raises
a line-numbered `ValueError` on the first one. A recognized frame record whose
DLC disagrees with its data byte count raises `ValueError` in both modes.

### `probe()`

```python
probe(path: str | Path, *, format: str | None = None) -> LogMeta
```

Selects a reader the same way as `read()`, then reads only the bounded 4 KiB
header sample needed for metadata. Raises `ValueError` when the sample does not
match the selected format.

### `available_formats()`

```python
available_formats() -> list[str]
```

Returns built-in and discovered reader names, sorted. With no third-party reader
plugins installed, `0.2.0` returns
`["candump", "kvaser-txt", "vector-asc"]`.

### `register_reader()`

```python
register_reader(reader_type: type[Reader]) -> None
```

Registers a reader class process-wide. The class must define a non-empty
`name: str`, a non-empty `extensions: tuple[str, ...]` of dot-prefixed
extensions, be constructible with no arguments, and provide callable
`sniff(sample)`, `probe(path)`, and `read(path)` methods. Validation happens
immediately.

Names are normalized to lowercase. Registering a name already used by a
built-in or custom reader raises `ValueError`; multiple readers may claim the
same extension, in which case normal content sniffing disambiguates them.

### Installed reader discovery

Installed distributions may expose reader classes through the
`capkit.readers` entry-point group. Discovery is lazy and cached after the first
`read()`, `probe()`, or `available_formats()` resolution. Entry-point readers
receive the same validation as classes passed to `register_reader()`.

A discovered reader name that conflicts with a built-in, explicitly registered,
or other discovered reader raises `RuntimeError` naming the entry point and its
distribution. Loading or constructing a broken entry-point reader raises the
same provenance-rich `RuntimeError`. Extension overlaps remain legal and are
resolved through content sniffing.

## Errors

- No readers registered: `No log formats are registered.`
- Unknown explicit name: `Unknown log format 'name'. Available formats: ...`
- Failed detection: `Unknown log format for 'file'. Available formats: ...`
- Duplicate registration: `Log format 'name' is already registered.`
- Invalid reader class: `TypeError` at registration time.
- Unreadable path: the underlying `OSError` subclass.
- Invalid record: `ValueError` naming the format, source line, and mismatch.

## Reader classes

### `KvaserTxtReader`

`capkit.readers.kvaser_txt.KvaserTxtReader` — the `kvaser-txt` reader, public
for format-specific use.

- `KvaserTxtReader(*, strict: bool = False)`
- `name = "kvaser-txt"`, `extensions = (".txt",)`
- `sniff(sample)`, `probe(path)`, `read(path)` per the reader protocol

### `CandumpReader`

`capkit.readers.candump.CandumpReader` — the `candump` reader for the
can-utils `candump -L` dialect.

- `CandumpReader(*, strict: bool = False)`
- `name = "candump"`, `extensions = (".log",)`
- `sniff(sample)`, `probe(path)`, `read(path)` per the reader protocol

### `VectorAscReader`

`capkit.readers.vector_asc.VectorAscReader` — the `vector-asc` reader for
Vector CANalyzer/CANoe ASC text logs.

- `VectorAscReader(*, strict: bool = False)`
- `name = "vector-asc"`, `extensions = (".asc",)`
- `probe()` returns the header date as a naive `LogMeta.start_time`
- `sniff(sample)`, `probe(path)`, `read(path)` per the reader protocol

### `DispatchReader`

`capkit.integration.DispatchReader` — the adapter registered in the
`dbckit.readers` entry-point group for the generic `.txt` and `.log`
extensions. It sniffs file content and delegates to the matching capkit reader;
it never trusts the extension alone. Vector `.asc` is registered directly to
`VectorAscReader`.

- `DispatchReader(*, strict: bool = False, **reader_options)`
- `read(path)` yields frames from the sniffed reader
