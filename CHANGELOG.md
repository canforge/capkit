# Changelog

All notable changes to capkit are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning will follow [Semantic Versioning](https://semver.org/) from 1.0.0 onward.

---

## [Unreleased]

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
