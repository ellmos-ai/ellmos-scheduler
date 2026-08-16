# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.2] - 2026-08-16

### Maintenance & Technical Hygiene (Pfad A)
- Standardized linting configuration: integrated `[tool.ruff]` and `[tool.ruff.lint]` configuration in `pyproject.toml` (`target-version = "py310"`, `line-length = 120`, `E402`/`E501` ignore).
- Verified full test suite passing (96/96 Pytest tests, 0 ruff errors, 100% `compileall`).
- Refreshed `llms.txt` discovery index and metadata to 2026-08-16 baseline.

## [0.3.1] - 2026-08-14

### Maintenance & Technical Hygiene
- Added `.ruff_cache/` and `.mypy_cache/` to `.gitignore`.
- Re-verified full test suite passing (96/96 Pytest tests, 0 ruff errors).
- Synchronized package version to `0.3.1` across project metadata, manifest, and docs.
- Refreshed `llms.txt` discovery index and metadata to 2026-08-14 baseline.

## [0.3.0] - 2026-08-07

### Maintenance
- Synchronized README badges and status text with the package version.
- Updated AI discovery metadata to the current 96-test verification baseline.
- Reverified the public repository metadata after the visibility manifest update.
- Refreshed `llms.txt` with the 2026-08-12 technical hygiene readback.

## [0.2.2] - 2026-08-03

### Maintenance & Discoverability
- Added `llms.txt` AI discovery index and machine-readable metadata.
- Added Shields.io status and ecosystem badges to `README.md` and `README_de.md`.
- Added interactive Mermaid system architecture diagram to documentation.
- Verified 90/90 Pytest test suite passing on Python 3.10+.
