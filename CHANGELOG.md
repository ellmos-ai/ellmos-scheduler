# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.6] - 2026-09-22

### Release Gate Härtung (10/10 PASS), Gate 1 .gitignore, Gate 10 TODO.md, PEP 639 Lizenzinventar & Plan-D-Parität (Pfad A)
- **10/10 Release Gates Vollständigkeit**: Erfolgreiche Zertifizierung aller 10 Release-Readiness-Gates durch `_scripts/final_gate_check.py` (10 PASS, 0 FAIL, 0 WARN) mit Prädikat `READY FOR PUBLIC RELEASE`.
- **Gate 1 Gitignore-Härtung**: `.gitignore` um verbindliche Gate-1-Ausschlussmuster (`*.pyc`, `.env`, `.env.*`, `.idea/`, `.vscode/`, `data/`) gehärtet bei gleichzeitiger Bewahrung von Cache-, Lock- und Multi-Host-Konfliktschutzregeln.
- **Gate 10 Standard TODO.md mit STATUS-Tabelle**: Strukturierte `TODO.md` mit normierter `## STATUS`-Tabelle, 10 Kategorien, Invariantenbezügen (`INV-LOCAL-01` bis `INV-SLA-10`) und formalisierten Folgeaufgaben (`TASK-SCHED-01` bis `TASK-SCHED-04`) etabliert.
- **PEP 639 Lizenzdateien-Deklaration**: `pyproject.toml` um vollständige Angabe `license-files = ["LICENSE", "THIRD_PARTY_LICENSES.md"]` ergänzt zur lückenlosen Transparenz von Haupt- und Drittanbieter-Lizenzen.
- **Manifest- & Paritätsaktualisierung**: Manifest `ellmos-module.v2.json` auf Version `0.3.6`, Status `active`, echte deutsche Umlaute in der Beschreibung und kanonischen Plan-D-Zustand (`ownership: external`, `location: external`) synchronisiert.
- **Plan-D-Spiegelung & Pointer**: Vollständige Synchronisation aller getrackten Repository-Dateien in die OneDrive-Projektion `.MODULES/.CONTROL/ellmos-scheduler` inklusive `PLAN_D_POINTER.md` und `REPO.pointer.json` unter striktem Ausschluss von `.git`, temporären Dateien und Test-Caches.
- **Vertragstest-Erweiterung**: 4 neue automatisierte Vertragstests in `tests/test_metadata.py` für `TODO.md`-Hygiene, PEP 639 `license-files`, Gate-1-Muster und Changelog-Eintrag integriert (132/132 Tests bestanden, 100% grün).

## [0.3.5] - 2026-09-14

### Discoverability, 10-Dimension Comparative Matrix, 16-Point Navigation Parity & Metadata Contract (Pfad B)
- **16-Point Bilingual Quick Navigation Parity**: Expanded table of contents navigation in `README.md` and `README_de.md` to 16 points, adding dedicated mutual anchor parity for Comparative Matrix vs. Alternatives (`#comparative-matrix-vs-alternatives` and `#vergleichsmatrix-gegenüber-alternativen`).
- **10-Dimension Comparative Matrix vs. 4 Alternatives**: Directly integrated the architectural comparison table into both `README.md` and `README_de.md`, benchmarking ellmos-scheduler against OS Cron / Windows Task Scheduler, Celery Beat / Redis Queue, APScheduler, and Cloud Schedulers across 10 dimensions (Zero-Egress, Atomic SQLite Leases, Preflight Authority Gate, Privilege Model, Audit Receipts, Multi-OS Parity, Agent Ready, Shell Safety, Stream Encoding, and Lease Fault Recovery).
- **High-Intent Search Queries & Discoverability**: Embedded primary intent and long-tail architecture keyword matrices in English and German in both READMEs to boost discoverability for agent swarms, zero-egress pipelines, and local cron alternatives.
- **Third-Party Licenses & Governance Update**: Updated `THIRD_PARTY_LICENSES.md` to Stand `2026-09-14`, affirming compliance across all 10 Governance and Runtime Invariants (`INV-LOCAL-01` to `INV-SLA-10`).
- **Marketing Log Audit Section**: Expanded `MARKETING-LOG.txt` with Section 9 detailing the 2026-09-14 Pfad B enhancements, 16-point navigation, and positioning matrix.
- **Metadata Parity & Version Synchronization**: Synchronized version `0.3.5` across `pyproject.toml`, `src/ellmos_scheduler/__init__.py`, `ellmos-module.v2.json`, `README.md`, `README_de.md`, and `llms.txt`.
- **Contract Testsuite Expansion**: Added 4 automated contract tests in `tests/test_metadata.py` verifying 16-point navigation parity, comparative matrix presence, embedded SEO keywords, license audit recency, and changelog release entry (128/128 passed tests, 100% green).

## [0.3.4] - 2026-09-13

### Repository Hygiene, CI Timeout & Stale Workflow, Gitignore Hardening & Metadata Parity (Pfad A)
- **CI Workflow Hardening**: Configured explicit `timeout-minutes: 15` ceiling on multi-OS matrix testing jobs in `.github/workflows/test.yml` to prevent runaway hanging runners.
- **Automated Lifecycle Management**: Added scheduled and dispatchable `.github/workflows/stale.yml` workflow for automated triage and marking of inactive issues and pull requests with strict permissions (`issues: write`, `pull-requests: write`).
- **Multi-Host Sync & Lock Defense**: Hardened `.gitignore` against cross-device conflict markers (`*conflicted copy*`, `* (kopie)*`, `* (copy)*`, `*-WORKSTATION*`, `*-WORKSTATION-LG*`, `*-ASUS*`, `*-LAPTOP*`), multi-agent lock variants (`uv.lock`, `!package-lock.json`), and test caches (`.tox/`, `.turbo/`).
- **PEP 621 Standard License Files & Ruff Extension**: Declared explicit `license-files = ["LICENSE"]` in `pyproject.toml` and broadened Ruff linter rulesets to `E`, `F`, `W`, `B`, `SIM`, `C4`, `RUF` while maintaining zero warnings.
- **Codebase Hygiene**: Applied alphabetical isort-style sorting to `__all__` in `src/ellmos_scheduler/__init__.py` (RUF022), eliminated unused cron parsing unpack variables in `schedules.py` (RUF059), and streamlined COMA adapter status determination in `adapters.py`.
- **Contract Testsuite Expansion**: Added 6 new automated contract tests in `tests/test_metadata.py` verifying CI timeouts, stale workflow presence, multi-host conflict patterns, PEP 621 license files, sorted exports, and release recency.
- **Metadata Parity & Version Synchronization**: Synchronized version `0.3.4` across `pyproject.toml`, `src/ellmos_scheduler/__init__.py`, `ellmos-module.v2.json`, `README.md`, `README_de.md`, and `llms.txt`.

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
