# `capkit` API Reference

Version covered: `0.3.0`

This file documents the public Python API exported by `capkit`:

- `read`, `probe`, `available_formats`, `register_reader`, `filter_frames`,
  `merge_frames`, `rebase_timestamps`, `decompose_j1939_id`
- `Frame`, `LogMeta`, `J1939Fields`

Also public, importable from their submodules:

- `capkit.operations.J1939Fields`
- `capkit.operations.filter_frames`
- `capkit.operations.decompose_j1939_id`
- `capkit.operations.merge_frames`
- `capkit.operations.rebase_timestamps`
- `capkit.readers.candump.CandumpReader`
- `capkit.readers.kvaser_txt.KvaserTxtReader`
- `capkit.readers.vector_asc.VectorAscReader`
- `capkit.integration.DispatchReader`

Internal helpers prefixed with `_` are not public.

## API conventions

- Models are frozen, slotted dataclasses.
- `decompose_j1939_id()` is immediate, dependency-free arithmetic over one
  integer; it does not inspect a `Frame`, DBC, or signal model.
- `read()` is lazy: nothing is opened or parsed until the returned iterator is
  consumed.
- `filter_frames()` is lazy: it does not touch its frame iterable until the
  returned iterator is consumed.
- `merge_frames()` is lazy: it does not touch its frame iterables until the
  returned iterator is consumed.
- `rebase_timestamps()` is lazy: it does not touch its frame iterable until the
  returned iterator is consumed.
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

### `J1939Fields`

A frozen, slotted result returned by `decompose_j1939_id()`.

Fields:

- `priority: int` — the three-bit J1939 priority
- `pgn: int` — the derived 18-bit parameter group number
- `source_address: int` — the transmitting ECU address
- `destination_address: int | None` — the PDU1 destination; `None` for PDU2,
  where the PDU-specific byte is a group extension included in `pgn`

## Functions

### `decompose_j1939_id()`

```python
decompose_j1939_id(arbitration_id: int) -> J1939Fields
```

Decomposes a clean 29-bit J1939 arbitration ID into frame-level fields. The
result retains the ID's priority and source address and derives its PGN from
the extended data-page, data-page, PDU-format, and PDU-specific bits.

When the PDU format is below `0xF0` (PDU1), the PDU-specific byte is a
destination address. It is returned as `destination_address` and cleared from
the PGN. At `0xF0` and above (PDU2), that byte is a group extension, remains in
the PGN, and `destination_address` is `None`.

```python
fields = decompose_j1939_id(0x18EF20A5)

assert fields.priority == 6
assert fields.pgn == 0xEF00
assert fields.source_address == 0xA5
assert fields.destination_address == 0x20
```

The helper accepts every integer in `0x00000000..0x1FFFFFFF`; it does not
require the high-order bits to be nonzero or separately inspect an
`is_extended_frame` flag. Non-integer values raise `TypeError`. Integers below
zero or above `0x1FFFFFFF` raise `ValueError`.

This is raw frame-ID arithmetic only. It neither reads DBC `PGN` attributes
nor matches or decodes messages. dbckit's J1939 matching remains the
DBC-aware layer and can consume frames produced by capkit without either
package importing the other.

### `filter_frames()`

```python
filter_frames(
    frames: Iterable[Frame],
    *,
    arbitration_ids: Iterable[int] | None = None,
    channels: Iterable[int | None] | None = None,
    start_time: float | None = None,
    end_time: float | None = None,
) -> Iterator[Frame]
```

Returns a lazy iterator over the frames that match every supplied criterion:

- `arbitration_ids` accepts one or more CAN arbitration IDs.
- `channels` accepts one or more channel values, including `None` for frames
  whose source did not record a channel.
- `start_time` and `end_time` are inclusive. Either bound may be omitted.

Omitted criteria are unrestricted, while a supplied empty ID or channel
iterable matches no frames. Multiple criteria compose with AND semantics.

The ID and channel iterables are snapshotted when `filter_frames()` is called;
the frame iterable is not touched until the returned iterator is advanced. The
helper consumes only as far as the next match, never reads beyond a yielded
frame, preserves input order, and yields the original `Frame` objects without
copying them. It does not assume timestamp ordering, so it scans the full input
rather than stopping after a timestamp exceeds `end_time`.

Passing both time bounds with `start_time > end_time` raises `ValueError`
without consuming the frame iterable.

### `rebase_timestamps()`

```python
rebase_timestamps(
    frames: Iterable[Frame],
    *,
    origin: float | None = None,
    offset: float = 0.0,
) -> Iterator[Frame]
```

Returns a lazy iterator that translates every timestamp onto an explicitly
chosen time base:

```text
new_timestamp = frame.timestamp - source_origin + offset
```

`origin` names a timestamp in the source time base, and `offset` is the output
timestamp that source origin maps to. For example, `origin=1_752_624_000.0`
and `offset=10.0` map that epoch instant to 10 seconds. The origin does not
need to equal any frame timestamp.

When `origin` is omitted, the first frame's recorded timestamp becomes the
source origin. With the default `offset=0.0`, the first output frame therefore
has timestamp zero. Supplying only `offset` maps the inferred first-frame
origin to that value.

Calling `rebase_timestamps()` does not touch the input. On first iteration, an
omitted origin requires reading one frame to resolve the source origin; that
replacement frame is yielded immediately. The helper then consumes and yields
one frame at a time without reading ahead or materializing the stream. An empty
input produces an empty iterator.

Each output is a new frozen `Frame` with only `timestamp` replaced. Every
non-timestamp field is preserved, input frames remain unchanged, and applying
one translation preserves source order and timestamp deltas, including for
negative and epoch-scale inputs. No ordering validation is performed.

This operation is separate from reading: `read()` and every reader continue to
return timestamps exactly as recorded.

### `merge_frames()`

```python
merge_frames(*streams: Iterable[Frame]) -> Iterator[Frame]
```

Merges any number of frame iterables into one lazy, timestamp-ordered iterator.
Each input must already be ordered by nondecreasing `Frame.timestamp`; the
helper merges ordered sources but does not sort an individual source.

The inputs are positional. When frames from different inputs have equal
timestamps, all available frames from the lower-indexed input are yielded
first. Order within each input is always preserved, including for equal
timestamps.

Calling `merge_frames()` does not touch its inputs. The first iteration reads
one frame from each input to establish the earliest head. Thereafter it keeps
at most one head per active input and advances only the source whose frame was
just yielded, using memory proportional to the number of inputs rather than
the total frame count. Empty inputs and exhausted streams are skipped; passing
no streams returns an empty iterator.

Frames are yielded unchanged and without copying, so their timestamps and all
other fields retain their exact values and object identity. Inputs therefore
need timestamps on a comparable time base; timestamp rebasing is a separate,
explicit operation.

Ordering is validated incrementally as each source advances. If a frame has a
timestamp smaller than the preceding frame from the same source,
`merge_frames()` raises `ValueError` identifying the zero-based input index and
both timestamps. Equal timestamps are valid. Frames yielded before a later
violation is encountered cannot be retracted.

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
- Non-integer J1939 ID: `arbitration_id must be an integer` (`TypeError`).
- Out-of-range J1939 ID: `arbitration_id must be between 0x00000000 and 0x1FFFFFFF`
  (`ValueError`).
- Reversed filter time window: `start_time must be less than or equal to end_time`.
- Out-of-order merge input: `input stream N is not time-ordered: timestamp ... follows ...`.
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

`capkit.integration.DispatchReader` — the adapter used for generic extensions
in dbckit's reader registry. capkit publishes exactly these extension-keyed
entries:

- `asc = capkit.readers.vector_asc:VectorAscReader`
- `log = capkit.integration:DispatchReader`
- `txt = capkit.integration:DispatchReader`

dbckit interprets each entry-point name as a file extension without the leading
dot. The keys are therefore `asc`, `log`, and `txt`, not capkit's reader names
`vector-asc`, `candump`, and `kvaser-txt`. `DispatchReader` sniffs file content
and delegates to the matching capkit reader, preserving content-based
disambiguation when readers share an extension. Vector `.asc` is registered
directly to `VectorAscReader` so capkit takes over dbckit's ASC path where
entry-point precedence is supported.

- `DispatchReader(*, strict: bool = False, **reader_options)`
- `read(path)` yields frames from the sniffed reader
