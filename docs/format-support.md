# Log format support

This document is the authoritative statement of which log formats and dialects `capkit`
supports. A reader is added only when a real captured fixture pins its dialect under
`tests/fixtures/<format>/`.

---

## Support matrix

| Format | Reader name | Extensions | Status | Dependency |
|---|---|---|---|---|
| Kvaser CanKing TXT | `kvaser-txt` | `.txt` | Supported | none |
| candump text | `candump` | `.log` | Planned | none |
| Vector ASC | `vector-asc` | `.asc` | Planned | none |
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
