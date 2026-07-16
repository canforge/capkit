# Release process

## Versioning

capkit follows [Semantic Versioning](https://semver.org/) from `1.0.0` onward.
Pre-1.0 minor releases may change the API.

- **Patch** — bug fixes, no API changes.
- **Minor** — new backwards-compatible features.
- **Major** — breaking API changes. Requires a migration note in CHANGELOG.

## Pre-release checklist

Before tagging a release:

- [ ] All CI checks pass on `main` (tests, ruff, mypy, coverage ≥ 90%, build check).
- [ ] `CHANGELOG.md` entry written for this version (see format below).
- [ ] Version bumped in `pyproject.toml`.
- [ ] README examples still accurate for the new version.

CI's build check already verifies that the wheel contains `capkit/py.typed` and the
three `dbckit.readers` entry points for `.asc`, `.log`, and `.txt`.

## Steps

Publishing is tag-driven: pushing a `v*` tag triggers
`.github/workflows/release.yml`, which builds the sdist and wheel and uploads
them to PyPI via [trusted publishing](https://docs.pypi.org/trusted-publishers/)
(OIDC, GitHub environment `pypi`) — no API tokens are involved.

```bash
# 1. Bump version
#    Edit pyproject.toml: version = "X.Y.Z"

# 2. Update CHANGELOG (see format below)

# 3. Commit the release
git add pyproject.toml CHANGELOG.md
git commit -m "chore: release X.Y.Z"
git push origin main

# 4. Tag — this triggers the release workflow
git tag -a vX.Y.Z -m "Release X.Y.Z"
git push origin vX.Y.Z

# 5. Verify
gh run watch                        # release workflow builds and publishes
open https://pypi.org/project/capkit/
```

## First publication

One-time setup before the first tag can publish:

1. Add a *pending publisher* on pypi.org for the `capkit` project name:
   repository `canforge/capkit`, workflow `release.yml`, environment `pypi`.
2. Create the protected `pypi` environment in the GitHub repository settings.

## CHANGELOG format

```markdown
## [0.1.0] — 2026-07-15

### Added
- ...

### Fixed
- ...

### Changed
- ...

### Removed
- ...
```

While unreleased work exists, collect its entries under an `## [Unreleased]`
section at the top; retitle it to the dated version when releasing.

## dbckit integration tests

dbckit is a separate package on PyPI; capkit has no runtime dependency on it. The
`dev` extra installs it only so `tests/test_integration_dbckit.py` (guarded by
`pytest.importorskip`) runs during development and CI. The core and contract
suites pass without it.
