# Log format support

This document is the authoritative statement of which log formats and dialects `capkit`
supports. A reader is added only when a real captured fixture pins its dialect under
`tests/fixtures/<format>/`.

---

## Support matrix

| Format | Reader name | Extensions | Status | Dependency |
|---|---|---|---|---|
| Kvaser CanKing TXT | `kvaser-txt` | `.txt` | Supported | none |
| candump text | `candump` | `.log` | Supported | none |
| Vector ASC | `vector-asc` | `.asc` | Supported | none |
| PCAN TRC | `pcan-trc` | `.trc` | Planned | none |
| Generic CSV | `csv-table` | `.csv` | Planned | none |
| Vector BLF | `vector-blf` | `.blf` | Planned adapter | `python-can` |
| ASAM MF4 | `asam-mf4` | `.mf4` | Planned adapter | `asammdf` |

Only supported rows are registered as readers or advertised through package entry points.

---

## Kvaser CanKing TXT (`kvaser-txt`)

The supported dialect is pinned by `tests/fixtures/kvaser/kvaser.txt`, a 300-frame excerpt of a
real capture. Identifiers, payloads, and timestamps are anonymized; the line grammar, column
layout, header, and trailer are preserved exactly as captured. Records are whitespace-delimited:

```text
Chn Identifier Flg   DLC  D0...1...2...3...4...5...6..D7       Time     Dir
 0    0CFBFFDB X       8  1B  31  20  EB  B3  FF  D9  FF     100.000139 R
```

### Supported

- Decimal channel, DLC, and relative timestamp
- Hexadecimal identifier without `0x`; two-digit hexadecimal data bytes
- Optional `X` flag marking extended (29-bit) identifiers
- `R` and `T` direction markers, mapped to `Frame.is_rx`
- Variable column whitespace and Latin-1 text
- Headers, trailers, comments, and unrelated lines skipped by default,
  rejected with a line-numbered `ValueError` under `strict=True`

A record that parses as a frame but declares a DLC different from its data byte count
raises `ValueError` in both modes.

### Not supported

- Memorator and other Kvaser dialects with absolute date headers — `probe()`
  returns `start_time=None`
- Remote, error, and CAN FD record grammars
- Timestamp rebasing or inferred absolute time

---

## can-utils candump (`candump`)

The supported dialect is the line-oriented format emitted by `candump -L`, pinned by the
300-frame `tests/fixtures/candump/candump.log` fixture:

```text
(1752624000.000139) vcan0 0CFBFFDB#1B3120EBB3FFD9FF R
```

### Supported

- Epoch timestamps in parentheses, returned as the recorded `float` without conversion
- Three-hex-digit standard and eight-hex-digit extended identifiers
- `ID#HEX` data records, including empty payloads
- `ID#R[dlc]` remote records; an explicit DLC is preserved in `Frame.dlc`
- `ID##FHEX` CAN FD records; flag bit 0 maps to `bitrate_switch` and bit 1 to
  `error_state_indicator`
- Optional `R`/`T` suffixes; absent direction maps to `Frame.is_rx=None`
- The trailing decimal digits of an interface name map to `Frame.channel` (`vcan0` → `0`);
  interface names without trailing digits map to `None`
- Unrecognized nonblank lines skipped by default and rejected with a line-numbered
  `ValueError` under `strict=True`

### Not supported

- can-utils error-flag identifiers as `Frame.is_error_frame`; those records are skipped by
  default and rejected in strict mode
- Inference of a capture-level start time; `probe()` returns `start_time=None` because the
  format has no header

---

## Vector ASC (`vector-asc`)

The supported dialect is pinned by `tests/fixtures/vector_asc/python_can_logfile.asc`, a
mixed Vector trace containing classic data, remote, error, CAN FD, status, statistics, and
J1939 rows.

### Supported

- `date` headers with English month abbreviations, returned by `probe()` as a naive
  `LogMeta.start_time`; the locale-dependent weekday token is ignored
- `base hex|dec` for identifiers, DLCs, and payload values
- `timestamps absolute`; frame timestamps are returned exactly as recorded
- Classic data rows with standard or `x`-suffixed extended identifiers and `Rx`/`Tx`
  direction
- All fixture remote shapes: bare `r`, `r` followed by metadata, and `r <dlc>`
- Classic and CAN FD `ErrorFrame` rows
- `CANFD` rows with optional symbolic message names, BRS/ESI flags, DLC code, decimal data
  length, and payload; a DLC code that differs from `len(data)` is preserved in `Frame.dlc`
- Literal channel integers as recorded in the file (Vector/python-can readers often normalize
  these to zero-based channels)
- Version/comments, trigger-block markers, measurement starts, status/statistic rows, and
  J1939 transport rows as recognized non-frame grammar, skipped in both modes
- Other unrecognized nonblank lines skipped by default and rejected under `strict=True`

### Not supported

- `timestamps relative`; the directive raises a clear `ValueError`
- Non-English month abbreviations in `date` headers
