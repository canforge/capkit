# Recipes

Common tasks on top of the frame stream. None of these are capkit API: `read()`
returns a lazy iterator of `Frame` objects, so each task is a few lines of
standard library. Unless noted, every recipe streams in constant memory.

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

frames = (f for f in capkit.read("trace.txt") if f.arbitration_id in wanted)
```

The same pattern filters on any `Frame` field — `channel`, `is_extended_frame`,
`is_rx`, and so on.

## Slice a time window

Timestamps are seconds exactly as recorded in the source, so compare against
values from the same log:

```python
window = (f for f in capkit.read("trace.txt") if 255.0 <= f.timestamp <= 260.0)
```

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
[dbckit](https://github.com/canforge/dbckit) — see
[Use with dbckit](../README.md#use-with-dbckit) in the README.
