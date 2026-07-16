# Fixture provenance

- `kvaser/kvaser.txt` — a 300-frame excerpt of a real Kvaser CanKing TXT export.
  Identifiers, payloads, and timestamps are anonymized; the line grammar, column
  layout, header, and trailer are preserved exactly as captured.
- `candump/candump.log` — the same 300 anonymized frames serialized to the
  can-utils log format (the `candump -L` dialect with the direction suffix) by
  python-can 4.6.1's `CanutilsLogWriter`, the ecosystem's reference
  implementation, and round-trip verified with its `CanutilsLogReader`.
  Timestamps are epoch seconds, as real candump logs record. Replace or extend
  with a raw `candump -L` capture when one is available.
- `vector_asc/python_can_logfile.asc` — `test/data/logfile.asc` from
  [`hardbyte/python-can`](https://github.com/hardbyte/python-can) commit
  `b4f82abede25ff83376be793a2935c41f81c3869`, byte-identical to the golden
  fixture dbckit ships. A real Vector-format trace mixing frame, status, error,
  statistics, J1939, and CAN FD rows. Licensed under LGPL-3.0; see
  `vector_asc/LICENSE.python-can.txt`.
