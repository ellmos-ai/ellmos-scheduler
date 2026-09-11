# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.3] - 2026-09-11

### Discoverability, Visual Architecture, Bilingual Parity, Third-Party Licenses & Metadata Contract (Pfad B)
- **Bilingual 15-Point Quick Navigation Parity**: Expanded table of contents navigation in `README.md` and `README_de.md` to full 15-point quick navigation with dedicated anchors for Third-Party Licenses & Transparency and Marketing & Target Personas.
- **Third-Party Licenses & Dependency Transparency**: Added repository-level `THIRD_PARTY_LICENSES.md` inventory detailing runtime (`tzdata`, Python standard library) and development dependencies (`pytest`, `tomli`, `ruff`, `setuptools`), certifying 100% OSI-approved permissive licensing and verifying compliance with zero-egress (`INV-LOCAL-01`) and non-elevation (`INV-PRIV-02`).
- **Canonical Governance & Runtime Invariant IDs**: Integrated standardized identifiers (`INV-LOCAL-01` through `INV-SLA-10`) into the bilingual Governance & Runtime Invariants matrices in `README.md`, `README_de.md`, and `MARKETING-LOG.txt`.
- **Target Personas & Competitive Positioning**: Overhauled `MARKETING-LOG.txt` with 4 detailed user journeys (Autonomous Multi-Agent Swarm Engineers, Local-First Builders, DevOps/SREs, and Security Auditors), bilingual high-intent keyword matrices, and a 5-way competitive positioning matrix comparing ellmos-scheduler to OS Cron, Celery, APScheduler, and Cloud Schedulers.
- **PEP 621 Standard Ecosystem Project URLs**: Augmented `[project.urls]` in `pyproject.toml` with `Third-Party Licenses`, `Marketing Log`, and `LLM Ready` endpoints.
- **Shields.io Badges Enhancement**: Added badges for Third-Party Audited (100% Permissive) and Marketing Log, synchronized version badge to `0.3.3`, and updated test suite badge to 118+ passed tests.
- **Metadata Parity & Version Alignment**: Synchronized version `0.3.3` across `pyproject.toml`, `src/ellmos_scheduler/__init__.py`, `ellmos-module.v2.json`, `README.md`, `README_de.md`, and `llms.txt`.
- **Contract Testsuite Expansion**: Expanded `tests/test_metadata.py` with contract tests verifying `THIRD_PARTY_LICENSES.md` inventory, extended PEP 621 URLs, 15-point quick navigation anchors, canonical invariant IDs, and changelog recency (118/118 passed tests, 100% green).

## [0.3.2] - 2026-09-09

### Repository Hygiene, CI Bytecode Preflight, Gitignore Hardening & Metadata Parity (Pfad A)
- **CI Workflow Hardening & Bytecode Compilation**: Integrated `python -m compileall -q src tests` bytecode compilation preflight gate in `.github/workflows/test.yml` and standardized test execution command to `python -m pytest -ra -v`.
- **PEP 621 Standard Classifiers & Pytest Options**: Added explicit operating system classifiers (`Operating System :: Microsoft :: Windows`, `Operating System :: POSIX :: Linux`, `Operating System :: MacOS`) and standardized `[tool.pytest.ini_options]` with `addopts = "-ra -v"` in `pyproject.toml`.
- **Multi-Host Gitignore Defense**: Augmented `.gitignore` with multi-host synchronization conflict patterns (`*-conflict-*`, `*.sync-conflict-*`, `*.conflict`, `*-CONFLIT-*`, `*.sync-temp-*`, `*-ASUS-GEI.*`), multi-agent lock patterns (`LOCK`, `LOCK.*`, `LOCK*.txt`, `*.lock`, `LOCK.permissions.json`), and build/editor artifacts (`wheelhouse/`, `*.swp`, `*.log`).
- **Bilingual Security Policy Contact Alignment**: Added umbrella security contact `security@open-bricks.org` across English and German vulnerability reporting sections in `SECURITY.md`.
- **Contract Testsuite Expansion**: Expanded `tests/test_metadata.py` with contract tests verifying CI bytecode compilation preflight, pytest options, OS classifiers, security contacts, and changelog recency (113/113 passed tests, 100% green).
- **Metadata Parity & Version Synchronization**: Bumped version to `0.3.2` across `pyproject.toml`, `src/ellmos_scheduler/__init__.py`, `ellmos-module.v2.json`, `README.md`, `README_de.md`, and `llms.txt`.

## [0.3.1] - 2026-09-08

### Discoverability, Visual Architecture, Governance Invariants & Metadata Parity (Pfad B)
- **Bilingual 14-Point Quick Navigation**: Added structured table of contents navigation in `README.md` and `README_de.md` linking directly to all 14 architectural and operational documentation sections.
- **Governance & Runtime Invariants Matrix**: Formulated comprehensive bilingual matrix defining 10 foundational system invariants (100% Local-First & Zero-Egress, Unprivileged Non-Elevation Execution / RunAsInvoker, Atomic SQLite Leases & Deduplicated Claims, Double Read-Only Authority Preflight with SHA-256 integrity, Strict UTF-8 & Fail-Closed Stream Decoding, Shell-Free Safe Process Invocation, Fail-Closed Timeout & Abandoned Lease Recovery, Declarative Modular Integration Outside Monoliths, Multi-OS Cross-Platform Parity, and Cryptographic Receipt Persistence).
- **Shields.io Badges Enhancement**: Added badges for CI status (Multi-OS GitHub Actions workflow), Code Style (Ruff), and Privacy (Zero-Egress), with test badge synchronized to 111 passed tests.
- **Security Policy Hardening**: Refined `SECURITY.md` in English and German with explicit 48h acknowledgement SLA and 5-business-day triage SLA.
- **Local Marketing & Discoverability Log**: Established repository-local `MARKETING-LOG.txt` tracking discoverability audits, architecture parity, and non-automated distribution steps.
- **Contract Testsuite Expansion**: Expanded `tests/test_metadata.py` with 5 new automated tests verifying quick navigation anchors, governance invariants tables, CI/quality badges, local marketing log existence, and changelog recency (111/111 Pytest tests passed, 100% green).
- **AI Discovery Index**: Refreshed `llms.txt` to `2026-09-08` baseline with references to governance invariants, test suite count, and local marketing register.

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
