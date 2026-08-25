# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.1] - 2026-08-25

### Technical Hygiene, Multi-OS CI Matrix & Contract Testsuite (Pfad A)
- **CI Workflow Concurrency & Multi-OS Matrix**: Hardened `.github/workflows/test.yml` with concurrency control (`cancel-in-progress: true`), expanded matrix with `macos-latest` (Ubuntu, Windows, macOS across Python 3.10 and 3.13), and standard action references (`actions/checkout@v4`, `actions/setup-python@v5`).
- **PEP 621 Standard Ecosystem URLs**: Expanded `[project.urls]` in `pyproject.toml` with `Changelog`, `Documentation`, `Security`, `Parent Organization` (`https://github.com/ellmos-ai`), and `Umbrella Ecosystem` (`https://github.com/open-bricks`).
- **Bilingual Security Policy Enhancement**: Updated `SECURITY.md` with direct security fallback contacts (`support@lukasgeiger.com`, `lukas@open-bricks.org`), advisory workflow link, and reinforced 48h response SLA.
- **Repository Hygiene & .gitignore**: Augmented `.gitignore` with synchronization conflict patterns (`*.sync-conflict-*`, `*.conflict`, `*-CONFLIT-*`), coverage directories, lockfiles, temporary files, and isolated test wheel targets (`.wheel-smoke/`).
- **Automated Contract Test Suite**: Expanded `tests/test_metadata.py` with 4 new contract tests validating CI workflow concurrency, PEP 621 ecosystem URLs, security policy structure/contacts, and gitignore hygiene patterns (106/106 Pytest tests passed, 100% green).
- **Metadata & LLM Discovery Index**: Refreshed `llms.txt` and README badges to `2026-08-25` baseline and 106 passed tests.

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
