# Recipes

Common tasks on top of the frame stream. `read()`, `filter_frames()`, and
`merge_frames()` are lazy, so every recipe streams in constant memory unless
noted otherwise.

All examples assume:

```python
import capkit
```

## Count arbitration IDs

How often each CAN ID appears in a log:

```python
from collections import Counter

counts = Counter(f.arbitration_id for f in capkit.read("trace.txt"))

for arb_id, n in counts.most_common(10):
    print(f"{arb_id:#010x}  {n}")
```

## Keep only some IDs

```python
wanted = {0x0CF00400, 0x18F0093E}

frames = capkit.filter_frames(capkit.read("trace.txt"), arbitration_ids=wanted)
```

## Keep only some channels

`None` selects frames whose source did not record a channel:

```python
frames = capkit.filter_frames(capkit.read("trace.txt"), channels={1, 2, None})
```

## Slice a time window

Timestamps are seconds exactly as recorded in the source, so compare against
values from the same log:

```python
window = capkit.filter_frames(
    capkit.read("trace.txt"),
    start_time=255.0,
    end_time=260.0,
)
```

Both bounds are inclusive. Omit either one for an open-ended window.

## Combine filters

All supplied criteria use AND semantics:

```python
frames = capkit.filter_frames(
    capkit.read("trace.txt"),
    arbitration_ids={0x0CF00400, 0x18F0093E},
    channels={1, 2},
    start_time=255.0,
    end_time=260.0,
)
```

`filter_frames()` preserves source order and yields the original frame objects.
For arbitrary predicates, use a generator expression over the frame stream:

```python
received = (frame for frame in capkit.read("trace.txt") if frame.is_rx is True)
```

## Merge time-ordered logs

Merge captures from multiple files or buses whose timestamps use the same time
base:

```python
frames = capkit.merge_frames(
    capkit.read("powertrain.asc"),
    capkit.read("body.asc"),
    capkit.read("diagnostics.asc"),
)

for frame in frames:
    print(frame.timestamp, frame.channel, frame.data.hex())
```

Every input must already be ordered by nondecreasing timestamp. Equal
timestamps are deterministic: frames from the earlier positional input come
first, while order within each input is preserved. The helper buffers at most
one frame per active input and yields the original frame objects.

`merge_frames()` does not change timestamps. Do not directly merge relative
timestamps from unrelated captures or mix relative and epoch timestamps;
rebase them explicitly onto a common time base first.

## Estimate a message's cycle time

Median gap between consecutive occurrences of one ID:

```python
from statistics import median

times = [f.timestamp for f in capkit.read("trace.txt") if f.arbitration_id == 0x0CF00400]
deltas = [b - a for a, b in zip(times, times[1:])]

print(f"{median(deltas) * 1000:.1f} ms")
```

## Export to CSV

```python
import csv

with open("frames.csv", "w", newline="") as out:
    writer = csv.writer(out)
    writer.writerow(["timestamp", "arbitration_id", "channel", "data"])
    for f in capkit.read("trace.txt"):
        writer.writerow([f.timestamp, f"{f.arbitration_id:X}", f.channel, f.data.hex()])
```

## Build a pandas DataFrame

`Frame` is a dataclass, so `dataclasses.asdict()` feeds `pandas` directly.
Requires `pandas`, which capkit does not depend on; this loads the whole log
into memory:

```python
from dataclasses import asdict

import pandas as pd

df = pd.DataFrame(asdict(f) for f in capkit.read("trace.txt"))

print(df.groupby("arbitration_id").size().sort_values(ascending=False).head())
```

## Decode signals

Signal decoding needs a DBC database and lives in
[dbckit](https://github.com/canforge/dbckit). The explicit composition works for
every capkit-supported format and does not depend on reader registration:

```python
import dbckit

db = dbckit.load("truck.dbc")
for decoded in dbckit.decode_frames(db, capkit.read("trace.txt")):
    print(decoded.timestamp, decoded.signals)
```

When both packages are installed, capkit's extension-keyed `dbckit.readers`
entries also make the file-oriented shortcut work without manual registration:

```python
for decoded in dbckit.decode_log(db, "trace.txt"):
    print(decoded.timestamp, decoded.signals)
```

The entry-point keys are `txt`, `log`, and `asc`; the corresponding capkit
reader names are `kvaser-txt`, `candump`, and `vector-asc`. Generic `.txt` and
`.log` files still go through content sniffing.
