# Roadmap

capkit 0.2.0 is [on PyPI](https://pypi.org/project/capkit/); the release checklist is complete
and retired (the release process lives in [docs/releasing.md](docs/releasing.md)). Readers are
fixture-first: a format lands only with a real capture under `tests/fixtures/<format>/`.

## Planned readers

- [ ] PCAN TRC (`.trc`)
- [ ] Configurable generic CSV (`.csv`)
- [ ] SocketCAN pcap/pcapng (`.pcap`, `.pcapng`)
- [ ] Vector BLF (`.blf`) and ASAM MF4 (`.mf4`) through optional adapters
- [ ] Additional Kvaser dialects (absolute start-time headers) as real fixtures arrive

## Reading pipeline

- [ ] File-object and stdin input alongside paths, so live captures pipe straight in
  (`candump can0 | ...`)
- [ ] Transparent reading of gzip-compressed logs (stdlib `gzip`; captures are large)
- [ ] Collected-error mode between the two current extremes: skip unrecognized lines but
  report them (count and line numbers) instead of skipping silently or raising on the
  first

## Stream operations

- [ ] Filters: by ID set, channel, and time window
- [ ] Merge several logs into one time-ordered stream (multi-bus and multi-file captures)
- [ ] Explicit, opt-in timestamp rebasing helper — `read()` itself keeps returning
  timestamps exactly as recorded
- [ ] J1939 arbitration-ID decomposition (priority, PGN, source address): pure per-frame
  arithmetic with no DBC awareness. dbckit 1.1 derives PGNs internally for DBC message
  matching; this is the frame-stream-side counterpart with no dbckit dependency

## CLI (`capkit[cli]`)

- [ ] `probe`, `head`, and `stats` commands (unique IDs, per-ID counts, time span)
- [ ] `convert` between supported formats once writers exist

## Deferred additions

- [ ] Writers and format conversion
- [ ] Dataframe export (pandas/polars) — recipes first, optional helpers only if the
  recipes prove insufficient
- [ ] python-can `Message` interop helpers
- [ ] Benchmark suite pinning parse throughput on large logs
