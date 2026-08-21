# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.1] - 2026-08-21

### Technical Hygiene & Packaging Parity
- **PEP 621 Packaging Standards**: Enhanced `pyproject.toml` with standard PEP 621 classifiers (Beta status, OS Independent, Python 3.10-3.13 support, System Monitoring topic) and explicit `[project.urls]` (Homepage, Repository, Issues).
- **AI Modules Care Alignment**: Refreshed `llms.txt` and `test_metadata.py` verification timestamp to 2026-08-21 baseline.
- **Ecosystem Mirror Synchronization**: Synchronized OneDrive module mirror `.CONTROL/ellmos-scheduler` with complete 0.3.1 package code, authority receipts, test suites, and updated `PLAN_D_POINTER.md`.

## [0.3.1] - 2026-08-20

### Discoverability, README-Design, Badges & Metadata Parity (Pfad B)
- **Badges Synchronization**: Updated badges in `README.md` and `README_de.md` for Platform (`Windows | macOS | Linux`), Python (`>=3.10`), Security (`Local-First`), Test Suite (`103 Passed`), License (`MIT`), Ecosystem (`ellmos-ai`), Umbrella (`open-bricks`), and AI Discovery (`llms.txt`).
- **Execution Lifecycle Visualization**: Integrated interactive Mermaid sequence diagram for the complete Execution & Authority Preflight Lifecycle (Tick -> Lease Claim -> Dual Read-Only SHA-256 Authority Preflight -> Executor Dispatch -> Receipt Persistence).
- **Security Policy**: Added comprehensive bilingual [`SECURITY.md`](SECURITY.md) documenting Local-First, Zero-Egress, Authority Preflight verification, Fail-Closed stream decoding, and private vulnerability reporting workflows.
- **Ecosystem & Sibling Matrix**: Added structured cross-linking table to 20+ sibling projects across `ellmos-ai`, `dev-bricks`, `doc-bricks`, `entertain-and-more`, and `open-bricks`.
- **Automated Metadata Parity Testsuite**: Implemented [`tests/test_metadata.py`](tests/test_metadata.py) covering version alignment, badge parity, language links, Mermaid diagrams, sibling matrix links, `llms.txt` schema, `SECURITY.md` invariants, and module manifest validity (7/7 passed).
- **AI Discovery Index**: Refreshed [`llms.txt`](llms.txt) with `2026-08-20` timestamp, test suite status, and repository key file map.

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
