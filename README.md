# capkit

[![PyPI](https://img.shields.io/pypi/v/capkit)](https://pypi.org/project/capkit/)
[![CI](https://github.com/canforge/capkit/actions/workflows/ci.yml/badge.svg)](https://github.com/canforge/capkit/actions/workflows/ci.yml)
[![Python versions](https://img.shields.io/pypi/pyversions/capkit)](https://pypi.org/project/capkit/)
[![License: MIT](https://img.shields.io/pypi/l/capkit)](LICENSE)

`capkit` is a Python library that reads **CAN bus capture logs into one common
frame stream**. Every supported format parses into the same frozen `Frame`
dataclass, so code that consumes frames never depends on which tool captured
the log.

Use it to:

- read captures from different tools as one lazy stream of typed `Frame` objects
- filter frame streams lazily by arbitration ID, channel, and timestamp
- probe a file for header metadata without scanning the frame body
- detect the log format from the file extension or the file content
- skip real-world log noise by default, or reject it with `strict=True`
- feed frames into [dbckit](https://github.com/canforge/dbckit) for DBC signal decoding

| Format | Reader name | Extensions | Status | Dependency |
|---|---|---|---|---|
| Kvaser CanKing TXT | `kvaser-txt` | `.txt` | Supported | none |
| candump text | `candump` | `.log` | Supported | none |
| Vector ASC | `vector-asc` | `.asc` | Supported | none |
| PCAN TRC | `pcan-trc` | `.trc` | Planned | none |
| Generic CSV | `csv-table` | `.csv` | Planned | none |
| Vector BLF | `vector-blf` | `.blf` | Planned adapter | `python-can` |
| ASAM MF4 | `asam-mf4` | `.mf4` | Planned adapter | `asammdf` |

See [format support](docs/format-support.md) for the exact dialect each reader
accepts, and the [roadmap](ROADMAP.md) for sequencing.

## Install

```bash
pip install capkit
```

Requires Python `>=3.11`. capkit has no runtime dependencies.

## Design

- `Frame` and `LogMeta` are frozen, slotted dataclasses.
- `read()` is lazy and keeps constant parser state, so file size does not matter.
- Timestamps are returned exactly as recorded in the source, never rebased or
  converted to absolute time.
- A format is added only when a real captured fixture pins its dialect under
  `tests/fixtures/`; unsupported dialects fail clearly instead of parsing
  approximately.

## Quick Start

```python
import capkit

# stream frames
for frame in capkit.read("trace.txt"):
    print(frame.timestamp, hex(frame.arbitration_id), frame.data.hex())

# compose lazy stream filters with inclusive time bounds
filtered = capkit.filter_frames(
    capkit.read("trace.txt"),
    arbitration_ids={0x123, 0x456},
    channels={1, 2},
    start_time=10.0,
    end_time=20.0,
)

# header metadata only
meta = capkit.probe("trace.txt")
print(meta.format, meta.start_time)

# registered reader names
print(capkit.available_formats())   # ['candump', 'kvaser-txt', 'vector-asc']
```

The public API is seven names: `read`, `probe`, `available_formats`,
`register_reader`, `filter_frames`, `Frame`, and `LogMeta`.

## Features

### Format detection

An explicit `format=` names a reader and takes precedence over the file
extension:

```python
frames = capkit.read("capture.bin", format="kvaser-txt")
```

Without `format=`, capkit matches the extension against registered readers and
sniffs the first 4 KiB when the extension is unknown or ambiguous.

### Add your own reader

Register a zero-argument reader class to make it available to `read()`,
`probe()`, and format detection:

```python
from collections.abc import Iterator
from pathlib import Path

import capkit


class MyReader:
    name: str = "my-format"
    extensions: tuple[str, ...] = (".mylog",)

    def __init__(self, *, strict: bool = False) -> None:
        self.strict = strict

    def sniff(self, sample: str) -> bool:
        return sample.startswith("MYLOG")

    def probe(self, path: Path) -> capkit.LogMeta:
        return capkit.LogMeta(format=self.name)

    def read(self, path: Path) -> Iterator[capkit.Frame]:
        # Parse path lazily and yield capkit.Frame objects here.
        yield from ()


capkit.register_reader(MyReader)
```

Registration is process-global. Installed packages can also advertise reader
classes through the `capkit.readers` entry-point group; capkit discovers and
caches them on the first `read()`, `probe()`, or `available_formats()` call.
dbckit's `.txt` entry point sniffs among all registered readers, so a reader
whose `sniff()` uniquely matches the content of a `.txt` log is used there
too, regardless of the extensions it claims.

### Dirty logs and strict mode

Readers skip headers, trailers, comments, blank lines, and unrelated noise by
default. Pass `strict=True` to raise a line-numbered `ValueError` on the first
unrecognized nonblank line instead:

```python
frames = capkit.read("trace.txt", strict=True)
```

A frame record whose DLC disagrees with its data bytes raises in both modes;
corrupt frames are never silently dropped.

## Use with dbckit

[dbckit](https://github.com/canforge/dbckit) decodes CAN frames against a DBC
database. capkit and dbckit are separate packages — neither depends on or
imports the other — with adjacent jobs: capkit turns bytes on disk into frames,
dbckit turns frames plus a DBC into signals.

```python
import capkit
import dbckit

db = dbckit.load("truck.dbc")
for decoded in dbckit.decode_frames(db, capkit.read("trace.txt")):
    print(decoded.timestamp, decoded.signals)
```

capkit also publishes exactly three extension-keyed entries in dbckit's
`dbckit.readers` group: `txt` and `log` use capkit's sniffing
`DispatchReader`, while `asc` uses `VectorAscReader` directly. These keys are
file extensions, not capkit reader names: the corresponding capkit formats are
`kvaser-txt`, `candump`, and `vector-asc`. With both packages installed,
`dbckit.decode_log()` therefore reads `.txt`, `.log`, and `.asc` logs through
capkit without manual registration:

```python
for decoded in dbckit.decode_log(db, "trace.txt"):
    print(decoded.signals)
```

## Scope and Caveats

- Kvaser dialects with absolute start-time headers are not supported;
  `probe()` returns `start_time=None` for `kvaser-txt`.
- candump error-flag records are skipped by default and rejected in strict
  mode; decoding them as CAN error frames is not claimed.
- Vector ASC relative timestamp directives and non-English month names are
  rejected instead of being interpreted approximately.
- capkit reads frames only: no DBC or signal awareness (that is dbckit's job),
  no hardware I/O, no log writing, no dataframe export, no CLI.

## Documentation

- [Format support](docs/format-support.md) — supported formats and the exact
  dialect each reader accepts
- [API reference](docs/api-reference.md) — the public API contract
- [Recipes](docs/recipes.md) — counting IDs, filtering frame streams, cycle-time
  estimation, CSV export, and dataframes

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

The `dev` extra includes dbckit so the entry-point integration tests run; the
core and contract suites pass without it.

## License

MIT
