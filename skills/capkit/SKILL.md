---
name: capkit
description: >
  Correct usage of the capkit Python library for reading CAN bus capture
  logs (Kvaser CanKing TXT, candump, Vector ASC) into one common frame
  stream: streaming frames, probing header metadata, format detection and
  sniffing, lazy ID/channel/time-window filtering, explicit lazy timestamp
  rebasing, lazy merging of ordered streams, dependency-free J1939 ID
  decomposition, strict mode, custom reader registration, and feeding frames
  into dbckit for DBC signal decoding. Use
  this skill whenever a task
  involves CAN capture, log, or trace files (.txt, .log, .asc), CAN frame
  streams, or log-format conversion in a project that has capkit installed
  or mentions capkit — even if the request doesn't name the library. This
  includes building tools or scripts ON TOP of capkit (analyzers,
  converters, MCP servers, CI checks). Also consult it before reaching for
  python-can idioms: capkit only reads finished log files into frozen
  Frame objects, and python-can habits (bus I/O, writers, mutable
  Message) produce code that fights the API.
---

# capkit

capkit is a Python library (`pip install capkit`, Python ≥ 3.11, zero runtime
dependencies) that reads CAN bus capture logs into one common stream of frozen
`Frame` objects. It is **not python-can** and it is not a decoder: it has no
DBC or signal awareness (that is dbckit's job), no hardware I/O, no writers,
and no CLI. Every supported format parses into the same `Frame` dataclass, so
downstream code never depends on which tool captured the log.

The public API is eleven names: `read`, `probe`, `available_formats`,
`register_reader`, `decompose_j1939_id`, `filter_frames`, `merge_frames`,
`rebase_timestamps`, `Frame`, `LogMeta`, `J1939Fields`. Reader classes remain
importable from `capkit.readers.<module>` for format-specific use.

## The rules that prevent silently wrong results

```python
import capkit

for frame in capkit.read("trace.txt"):      # lazy Iterator[Frame]
    print(frame.timestamp, hex(frame.arbitration_id), frame.data.hex())

j1939 = capkit.decompose_j1939_id(0x18EF20A5)
j1939.priority, j1939.pgn                 # 6, 0xEF00
j1939.source_address, j1939.destination_address  # 0xA5, 0x20

filtered = capkit.filter_frames(            # also lazy; all criteria use AND
    capkit.read("trace.txt"),
    arbitration_ids={0x123, 0x456},
    channels={1, 2},
    start_time=10.0,                        # inclusive
    end_time=20.0,                          # inclusive
)

relative = capkit.rebase_timestamps(        # first output timestamp is 0.0
    capkit.read("capture.log"),
)

merged = capkit.merge_frames(               # each input is already ordered
    capkit.read("powertrain.asc"),
    capkit.read("body.asc"),
)

meta = capkit.probe("trace.asc")            # header-only; never scans the body
print(meta.format, meta.start_time)         # "vector-asc", datetime | None

capkit.available_formats()                  # ['candump', 'kvaser-txt', 'vector-asc']
```

- **`read()` is lazy and one-shot.** Nothing is opened or parsed until the
  returned iterator is consumed — even an unknown-format `ValueError` surfaces
  at the first `next()`, not at the `read()` call. The iterator is consumed
  once; `list()` it for multiple passes, or call `read()` again.
- **`filter_frames()` is lazy and identity-preserving.** It accepts any frame
  iterable, combines ID/channel/time criteria with AND semantics, preserves
  source order, and yields the original frame objects. Empty ID or channel
  collections match nothing; `channels={None}` selects frames without a
  recorded channel. A reversed time window raises `ValueError` before the
  frame source is consumed.
- **`merge_frames()` is a lazy k-way merge, not a sort.** Every input must be
  nondecreasing by timestamp and use a comparable time base. It buffers at
  most one frame per active source, preserves frame identity and source order,
  and breaks equal-timestamp ties by positional source index. A backwards
  timestamp raises `ValueError` when that source is advanced.
- **`rebase_timestamps()` is lazy and explicit.** By default it maps the first
  frame's timestamp to zero. With `origin=` and `offset=`, it applies
  `recorded - origin + offset`, where the source origin maps to the output
  offset. It creates frozen replacement frames, changes only timestamps, and
  never reads ahead.
- **`decompose_j1939_id()` is immediate arithmetic.** It accepts a clean
  29-bit integer and returns frozen `J1939Fields` containing priority, PGN,
  source address, and the optional PDU1 destination. PDU1 destination bytes
  are cleared from the PGN; PDU2 group extensions remain in it. It does not
  inspect `Frame.is_extended_frame`, a DBC, or any signal model.
- **Reader timestamps are exactly as recorded.** `kvaser-txt` records
  device-relative seconds, `candump` records epoch seconds, and `vector-asc`
  absolute-mode trace seconds. `read()` never rebases; use the separate helper
  only when requested. The absolute capture start (when recorded) comes from
  `probe()`, not from the frames.
- **Frames are frozen, slotted dataclasses.** Assigning to a field raises;
  use `dataclasses.replace(frame, ...)` for a modified copy. `frame.data` is
  immutable `bytes`.

## Format detection

1. An explicit `format=` names a reader (`capkit.read(p, format="kvaser-txt")`)
   and wins; an unknown name raises `ValueError`.
2. Otherwise a file extension claimed by exactly one reader selects it.
3. Otherwise the first 4 KiB are read as Latin-1 and offered to every reader's
   `sniff()`; exactly one match selects it, anything else raises `ValueError`
   listing the available formats.

So a Kvaser log named `capture.bin` still resolves via sniffing, and an
extension lie (`candump` content in a `.txt` file) is caught by content, not
trusted by name.

## Dirty logs and strict mode

Readers skip headers, trailers, comments, and unrelated noise by default.
`strict=True` instead raises a line-numbered `ValueError` on the first
unrecognized nonblank line:

```python
frames = capkit.read("trace.txt", strict=True)
```

In **both** modes, a frame record whose DLC disagrees with its data byte
count raises `ValueError` — corrupt frames are never silently dropped.

What strict rejects is per-format grammar: `vector-asc` recognizes
version/comment, status, statistic, trigger-block, measurement-start, and
J1939 transport rows and skips them even under `strict=True`, but
`kvaser-txt` rejects its own header and trailer lines under strict — so
strict there only suits frame-only excerpts, not full CanKing exports.

Error frames differ by format: `vector-asc` parses `ErrorFrame` rows into
frames with `is_error_frame=True`, while `candump` error-flag records are
skipped by default and rejected in strict mode (decoding them is not claimed).

## Frame and LogMeta fields

`Frame`: `timestamp: float`, `arbitration_id: int`, `data: bytes`,
`channel: int | None`, `is_extended_frame`, `is_fd`, `is_remote_frame`,
`is_error_frame`, `is_rx: bool | None` (`None` when the log records no
direction), `dlc: int | None`, `bitrate_switch`, `error_state_indicator`.

- `dlc` is populated **only** when it conveys information different from
  `len(data)` (remote frames with a declared DLC, CAN FD DLC codes). For
  ordinary data frames use `len(frame.data)`.
- `channel` comes from the log's channel column, or the trailing digits of a
  candump interface name (`vcan0` → `0`; no digits → `None`).

`LogMeta` (from `probe()`): `format` (reader name), `start_time`
(`datetime | None` — only `vector-asc` currently records one; naive, from the
file's `date` header), `extra: dict[str, str]`.

## Coming from python-can

| python-can habit | capkit reality |
|---|---|
| `can.LogReader(path)` yields `can.Message` | `capkit.read(path)` yields frozen `capkit.Frame` |
| `can.Bus(...)`, `Notifier`, live capture | out of scope — capkit reads finished files only |
| `msg.data` is a mutable `bytearray` | `frame.data` is immutable `bytes` |
| `msg.dlc` always set | `frame.dlc` is `None` unless it differs from `len(data)` |
| `msg.is_rx` defaults to `True` | `frame.is_rx` is `None` when the log has no direction column |
| writers (`can.Logger`, `ASCWriter`) | no writers — export yourself (see recipes) |
| some readers synthesize absolute timestamps | timestamps pass through as recorded; absolute start via `probe()` |

Both `capkit.Frame` and `can.Message` satisfy dbckit's `FrameLike` protocol,
so either feeds `dbckit.decode_frames()` — but do not mix python-can parsing
into a capkit task for formats capkit supports.

## Custom readers

Register a zero-argument reader class to make it available to `read()`,
`probe()`, and detection:

```python
from collections.abc import Iterator
from pathlib import Path

import capkit


class MyReader:
    name: str = "my-format"                      # registry key, lowercased
    extensions: tuple[str, ...] = (".mylog",)    # dot-prefixed

    def __init__(self, *, strict: bool = False) -> None:   # all options need defaults
        self.strict = strict

    def sniff(self, sample: str) -> bool:        # first 4 KiB, Latin-1
        return sample.startswith("MYLOG")

    def probe(self, path: Path) -> capkit.LogMeta:
        return capkit.LogMeta(format=self.name)

    def read(self, path: Path) -> Iterator[capkit.Frame]:
        yield from ()                            # generator, O(1) state


capkit.register_reader(MyReader)                 # validates immediately, process-global
```

Duplicate names raise `ValueError`; extension overlaps are legal (sniffing
disambiguates). Installed packages can instead advertise reader classes in the
`capkit.readers` entry-point group — discovered lazily on the first `read()` /
`probe()` / `available_formats()` call, with conflicts and broken entry points
raising `RuntimeError` naming the entry point and distribution.

## Use with dbckit

capkit and dbckit are separate packages — neither imports the other.

For raw J1939 frame fields, use `capkit.decompose_j1939_id()`. dbckit may
derive the same PGN to match an incoming frame against DBC messages, then
decodes signals; capkit performs neither DBC lookup nor decoding.

Two DBC decoding composition patterns:

```python
import capkit
import dbckit

# explicit: capkit makes frames, dbckit makes signals
db = dbckit.load("truck.dbc")
for decoded in dbckit.decode_frames(db, capkit.read("trace.txt")):
    print(decoded.timestamp, decoded.signals)

# zero wiring: capkit registers extension-keyed dbckit.readers entry points
# named txt, log, and asc, so with both installed this just works
for decoded in dbckit.decode_log(db, "trace.txt"):
    print(decoded.signals)
```

The entry-point keys are file extensions, not capkit reader names: `txt` maps
to `kvaser-txt`, `log` maps to `candump`, and `asc` maps to `vector-asc` for the
fixtures currently shipped. The generic `txt` and `log` entries use a sniffing
dispatcher, so any log whose content matches a capkit reader resolves correctly
regardless of what the extension suggests. The `asc` entry directly exposes
capkit's richer `VectorAscReader` and deliberately takes over dbckit's built-in
ASC path where entry-point precedence is supported.

## Hard limits — don't fight these

- **No signal decoding, ever.** Anything involving a DBC, signals, or physical
  values is dbckit's job; raw J1939 arbitration-ID decomposition is the
  frame-side exception and remains pure arithmetic.
- **Supported readers: `candump`, `kvaser-txt`, `vector-asc`.**
  PCAN TRC, generic CSV, pcap/pcapng, Vector BLF, and ASAM MF4 are roadmap
  items — `capkit.read("x.trc")` raises unknown-format `ValueError` today; do
  not invent support for them.
- Paths only: no file-object or stdin input, no gzip transparency (roadmap).
- Kvaser dialects with absolute date headers (Memorator style) are
  unsupported; `probe()` returns `start_time=None` for `kvaser-txt` and
  `candump`.
- Vector ASC `timestamps relative` directives and non-English month names are
  rejected with clear errors instead of being interpreted approximately.
- No writers, no CLI, no dataframe export in core — `Frame` is a dataclass,
  so `dataclasses.asdict()` feeds pandas directly (see recipes).

## Full reference

Bundled with this skill — read them instead of searching installed sources or
the web when a question goes beyond this file:

- `references/recipes.md` — counting and decomposing IDs, frame-stream
  filters, timestamp rebasing and merging, cycle-time estimation, CSV export,
  and dataframes
- `references/api-reference.md` — the complete public API contract, every
  model field, function signature, error message, and reader class
- `references/format-support.md` — the exact dialect each reader accepts,
  per-format supported/unsupported lists, and fixture provenance
