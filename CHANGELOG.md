# Changelog

All notable changes to capkit are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning will follow [Semantic Versioning](https://semver.org/) from 1.0.0 onward.

---

## [0.2.0] — 2026-07-16

### Added

- can-utils `candump -L` reader (`candump`) with classic, remote, and CAN FD support,
  pinned by a 300-frame fixture.
- Vector CANalyzer/CANoe ASC reader (`vector-asc`) covering classic, remote, error,
  and CAN FD rows plus header-derived capture start times.
- `Frame.bitrate_switch` and `Frame.error_state_indicator` CAN FD flags.
- Lazy, cached discovery of third-party readers through the `capkit.readers`
  entry-point group, including validated conflict and failure reporting.
- python-can reference writer/reader cross-checks in the development test suite.

### Changed

- dbckit integration now handles `.log` through the sniffing dispatcher and
  supersedes dbckit's built-in `.asc` reader with capkit's richer implementation.

## [0.1.0] — 2026-07-16

Initial public release.

### Added

- Frozen, slotted `Frame` and `LogMeta` models; no runtime dependencies.
- Lazy `read()`, header-only `probe()`, and `available_formats()`.
- Public `register_reader()` for validated, process-wide custom reader classes.
- Kvaser CanKing TXT reader (`kvaser-txt`) with noise-skipping and strict modes,
  pinned by an anonymized excerpt of a real capture.
- Generic `.txt` dispatch through the `dbckit.readers` entry-point group.
- `py.typed` typing metadata.
- CI on Python 3.11–3.14: pytest with coverage ≥ 90%, ruff, mypy, and a wheel
  metadata build check.
- Tag-driven release workflow publishing to PyPI with trusted publishing (OIDC).
