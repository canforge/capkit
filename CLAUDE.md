# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

capkit is a zero-runtime-dependency Python library that reads CAN bus capture logs
(Kvaser CanKing TXT, candump, Vector ASC) into one common stream of frozen `Frame`
dataclasses. Published to PyPI as `capkit` from this repo (github.com/canforge/capkit).
Sister package to dbckit with a strict division of labor: capkit turns bytes on disk into
frames, dbckit turns frames + a DBC into signals. They compose through entry points and a
structural protocol — **neither package ever imports the other**.

DEFINITION.md is the founding spec (implementation follows it; it is updated when reality
wins an argument). ROADMAP.md is the authority on what lands next.

## Commands

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"                          # dev extra includes dbckit + python-can (test-only)

pytest                                           # full suite
pytest tests/test_vector_asc.py                  # one file
pytest tests/test_candump.py -k golden           # one test
python -m pytest --cov=capkit --cov-fail-under=90 -q   # the CI coverage gate
ruff check .                                     # lint, whole repo (CI-blocking)
mypy capkit                                      # types (CI-blocking)
python -m build                                  # sdist+wheel (CI-blocking)
```

CI's build check also asserts the wheel ships `capkit/py.typed` and the three
`dbckit.readers` entry points (`asc`, `log`, `txt`). The core and contract suites pass
without dbckit or python-can installed; the integration tests guard with
`pytest.importorskip`.

## Architecture

One-way pipeline, lazy end to end:

```
path ──> readers/__init__.py  (registry: format= > unique extension > 4 KiB sniff)
     ──> readers/<format>.py  (generator, O(1) state, never materializes the file)
     ──> model/frame.py       (frozen slotted Frame stream)
```

- **`model/frame.py`** — `Frame`/`LogMeta` are frozen, slotted **dataclasses, deliberately
  not pydantic** (unlike dbckit): frames are the hot path and the core stays at zero
  runtime dependencies. Don't "upgrade" them.
- **`io.py`** — `read()`/`probe()`/`available_formats()`. `read()` defers everything,
  including format resolution and its errors, into the returned generator.
- **`readers/__init__.py`** — the reader registry, the only global mutable state in the
  package. Also lazy, cached discovery of the `capkit.readers` entry-point group;
  name conflicts and broken entry points raise provenance-rich `RuntimeError`s naming the
  entry point and distribution. Extension overlaps are legal — sniffing disambiguates.
- **`readers/base.py`** — the `Reader` protocol and the 4 KiB Latin-1 `read_sample()`
  used for sniffing.
- **Format readers** (`kvaser_txt.py`, `candump.py`, `vector_asc.py`) — streaming line
  scanners sharing one policy: skip unrecognized nonblank lines by default, raise a
  line-numbered `ValueError` under `strict=True`; a DLC that disagrees with the data
  bytes raises in both modes; timestamps pass through exactly as recorded, never rebased.
- **`integration.py`** — the dbckit-facing surface, kept in one module so the coupling is
  auditable. `DispatchReader` sniffs content for generic extensions; pyproject registers
  `asc` directly to `VectorAscReader` and `log`/`txt` to the dispatcher. One entry point
  per extension ecosystem-wide (dbckit raises on duplicates), and generic extensions go
  through the dispatcher only — never a concrete format reader.
- **`operations/`** — lazy, dependency-free stream operations over frame iterables
  (`filter_frames`, `merge_frames`, `rebase_timestamps`, `decompose_j1939_id`), all
  re-exported from the package root. They accept iterables and return iterators without
  materializing, reordering, or mutating frames; `rebase_timestamps` is the only opt-in
  timestamp transform — readers still never rebase.
- **`writers/`** — reserved and empty on purpose; don't populate it ahead of the roadmap.

## The dbckit contract (structural, test-enforced)

DEFINITION.md §2 is the compliance contract: frames expose
`timestamp`/`arbitration_id`/`data` (plus `channel` and `is_extended_frame` read via
`getattr`); readers are zero-argument constructible with `read(path)`; entry-point name =
extension without the dot. `tests/test_contract.py` replicates the shape checks **without
importing dbckit**; `tests/test_integration_dbckit.py` (importorskip) is the executable
proof against the real package. Keep it that way — a `import dbckit` anywhere in
`capkit/` is a design violation, not a convenience.

## Scope walls (policy, not gaps)

These fail loudly by design — "fixing" them is a roadmap decision, not a bug fix:

- No DBC or signal awareness, ever — that is dbckit's job.
- No hardware/bus I/O — that is python-can's job; capkit reads finished files.
- No writers, no CLI, no pandas in core — reserved growth directions, not omissions.
- **Fixture-first rule:** no reader code without a real captured fixture in
  `tests/fixtures/<format>/`. Formats grow from evidence, not format documentation.
- Unsupported dialects fail clearly instead of parsing approximately: ASC
  `timestamps relative` and non-English months, Kvaser absolute-date headers, candump
  error-flag decoding.

## Testing conventions

- Golden fixture tests per format: frame count plus first/last frame field-by-field, and
  both skip-mode and strict-mode coverage for every reader behavior.
- `tests/fixtures/README.md` records provenance. Fixtures are anonymized real captures or
  licensed python-can material — never regenerate or "fix" them. The `vector_asc` fixture
  is byte-identical to the golden fixture dbckit ships; keep it that way.
- CI matrix: Python 3.11–3.14.

## Docs that must move together

A change to the public surface touches all of: `docs/api-reference.md` (pins the version
it covers — bump it), `docs/format-support.md`, `docs/recipes.md`, `CHANGELOG.md` (Keep a
Changelog; semver from 1.0.0), and the verbatim copies in `skills/capkit/references/`
(sync = `cp` from docs/). README stays a teaser — full API and format detail lives in
docs/, not README.

## Releasing

Tag-driven, identical to dbckit: bump `pyproject.toml`, update CHANGELOG, push `main`,
then `git tag -a vX.Y.Z && git push origin vX.Y.Z` — `.github/workflows/release.yml`
builds and publishes to PyPI via trusted publishing (OIDC, environment `pypi`, no
tokens). Full steps: docs/releasing.md.

## Repo quirks

- `skills/capkit/` is a user-facing agent skill for *consumers* of the library; this file
  is the guidance for *developing* it. Keep the two audiences straight.
- DEFINITION.md is a founding document, not live API docs — where it and shipped code
  disagree, update DEFINITION.md to match reality (its own stated rule); the live
  contract is docs/api-reference.md.
