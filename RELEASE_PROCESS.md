# Release Process

## Scope

This process applies to all tagged Oathweaver releases (`vX.Y.Z` or pre-release tags like `vX.Y.Z-rc`).

## Roles and Permission

A release can be cut by a maintainer with:
- write access to `main`
- permission to create annotated tags
- permission to publish GitHub releases

## Version Source of Truth

- Primary version file: `VERSION` (repo root)
- Packaging scripts read from this file:
  - `create_clean_zip.ps1`
  - `build_installer_exe.ps1`

## Changelog Convention

- Maintain `CHANGELOG.md` using Keep-a-Changelog sections.
- `## [Unreleased]` is always present.
- Before tagging, move unreleased entries into the new version section and add release date.

## Pre-Release Smoke Matrix

Required before cutting release candidates and finals:
- Ubuntu 24.04 clean install via `./install_oathweaver_linux.sh`
- Ubuntu 22.04 clean install via `./install_oathweaver_linux.sh`
- Windows 11 install via `install_oathweaver.ps1`
- Web GUI reachability at expected port
- One research turn and one make turn complete successfully
- Core tests pass in CI (Python 3.10 and 3.12 lanes)

## Tag and Release Flow

1. Update `VERSION` and `CHANGELOG.md`.
2. Confirm docs pointers in `README.md` and release notes are current.
3. Commit release prep.
4. Create annotated tag:
   - `git tag -a vX.Y.Z -m "Oathweaver vX.Y.Z"`
5. Push commit and tag:
   - `git push origin main --follow-tags`
6. Publish GitHub release using the corresponding release notes doc body.

## Artifact Build

- ZIP package: `create_clean_zip.ps1`
- Optional installer launcher EXE: `build_installer_exe.ps1`
- Ensure produced filenames include the current `VERSION` value.

## Post-Release

- Open a follow-up issue for any deferred release-note items.
- Re-open `## [Unreleased]` with placeholders for next cycle.
