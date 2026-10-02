# Contributing to ellmos-scheduler

Thank you for your interest in contributing to **ellmos-scheduler** (`ellmos-ai/ellmos-scheduler`), a standalone, modular scheduler and execution run recorder built for modular ellmos stacks, autonomous multi-agent environments, and external adapters (BACH, COMA, MarbleRun, swarm-ai).

[English](#english) | [Deutsch](#deutsch)

---

<a id="english"></a>
## English

### 1. Architectural Principles & Invariants

Every contribution must preserve our 10 foundational system and operational invariants:

- **100% Local-First & Zero-Egress (`INV-LOCAL-01`)**: No unauthorized network sockets, outbound telemetry, analytics beacons, or remote dependencies.
- **Unprivileged Non-Elevation Execution (`INV-PRIV-02`)**: Executes strictly in user-mode (`RunAsInvoker`), never requiring administrative or root elevation.
- **Atomic Concurrency & Leases (`INV-CONC-03`)**: Content-addressed deterministic `run_id` generation and atomic SQLite leases prevent concurrent double-execution.
- **Preflight Authority Integrity Gate (`INV-AUTH-04`)**: Dual read-only passes + SHA-256 hash checks validate mandatory authority files prior to execution.
- **Strict UTF-8 & Stream Hygiene (`INV-STRM-05`)**: Subprocess stream decoding enforces strict error handling (`utf-8:strict`) without data corruption.
- **Shell Injection Safety (`INV-EXEC-06`)**: Subprocess execution strictly uses explicit `argv` lists (`shell=False`).
- **Resilient Lease Recovery (`INV-RES-07`)**: Overdue, hanging, or crashed worker leases are marked `abandoned` and reclaimed safely without deadlocks.
- **Modular Ecosystem Integration (`INV-MOD-08`)**: Pluggable executor registry and clean decoupling outside monoliths.
- **Multi-OS Parity (`INV-PLAT-09`)**: Full operational parity across Windows (with `tzdata` fallback for IANA zones), Linux, and macOS.
- **Audit Trails & Security SLA (`INV-SLA-10`)**: Immutable SQLite receipts, Level 1 SBOM transparency, and a binding 48h Security Response SLA.

### 2. Local Development & Environment Setup

1. **Clone the repository** (Plan D canonical clone):
   ```bash
   git clone https://github.com/ellmos-ai/ellmos-scheduler.git
   cd ellmos-scheduler
   ```

2. **Create and activate a virtual environment**:
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # Linux / macOS:
   source .venv/bin/activate
   ```

3. **Install development dependencies**:
   ```bash
   pip install -e ".[dev]"
   pip install ruff
   ```

### 3. Testing & Verification Gates

Before submitting any Pull Request, ensure that all quality gates pass cleanly:

1. **Run full automated test suite**:
   ```bash
   pytest
   ```
   All unit and metadata contract tests must pass (100% green).
2. **Run Ruff static analysis**:
   ```bash
   ruff check .
   ```
3. **Verify Python compilation**:
   ```bash
   python -m compileall src tests
   ```
4. **Verify git diff cleanliness**:
   ```bash
   git diff --check
   ```

### 4. Version Freeze & Release Discipline

- **Version Freeze (`T-20260920-167562623`)**: Do not increment or bump the package version in `pyproject.toml`, `ellmos-module.v2.json`, or code manifests. Version bumps are strictly governed by coordinated release procedures.
- **Conventional Commits**: Use conventional prefixes (`feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`).

### 5. Reporting Security Vulnerabilities

Please do not open public GitHub issues for security vulnerabilities. Instead, refer to our [Security Policy](SECURITY.md) and report via `security@open-bricks.org` in accordance with our binding 48-hour response SLA.

---

<a id="deutsch"></a>
## Deutsch

### 1. Architektonische Prinzipien & Invarianten

Jeder Beitrag muss unsere 10 grundlegenden System- und Betriebsinvarianten wahren:

- **100% Local-First & Zero-Egress (`INV-LOCAL-01`)**: Keine ausgehenden Netzwerk-Sockets, Telemetrie, Analyse-Beacons oder unerwünschte Cloud-Verbindungen.
- **Nicht-privilegierte Ausführung (`INV-PRIV-02`)**: Strikter Benutzermodus (`RunAsInvoker`), niemals Administrator- oder Root-Rechte erforderlich.
- **Atomare Nebenläufigkeit & Leases (`INV-CONC-03`)**: Deterministische `run_id`-Generierung und transaktionale SQLite-Leases verhindern Doppel-Ausführungen.
- **Preflight-Autoritäts-Prüfung (`INV-AUTH-04`)**: Zweifache Read-Passes mit kryptographischer SHA-256-Integritätsprüfung vor der Auftragsabwicklung.
- **Strikte UTF-8-Stream-Hygiene (`INV-STRM-05`)**: Subprozess-Dekodierung erzwingt strikte Fehlerbehandlung (`utf-8:strict`) ohne Datenverlust.
- **Schutz vor Shell-Injection (`INV-EXEC-06`)**: Subprozess-Ausführung nutzt ausschließlich explizite `argv`-Listen (`shell=False`).
- **Resilientes Lease-Reclaiming (`INV-RES-07`)**: Abgestürzte oder abgelaufene Worker-Leases werden als `abandoned` markiert und ohne Deadlocks zurückgewonnen.
- **Modulare Systemintegration (`INV-MOD-08`)**: Steckbare Executor-Registry und saubere Trennung außerhalb monolithischer Blöcke.
- **Plattformübergreifende Parität (`INV-PLAT-09`)**: Gleiches Verhalten unter Windows (mit `tzdata`-Fallback für IANA-Zonen), Linux und macOS.
- **Revisionssicherheit & 48h SLA (`INV-SLA-10`)**: Unveränderliche SQLite-Receipts, Level 1 SBOM Transparenz und verbindliche 48h Sicherheits-Reaktions-SLA.

### 2. Lokale Entwicklung & Setup

1. **Repository klonen**:
   ```bash
   git clone https://github.com/ellmos-ai/ellmos-scheduler.git
   cd ellmos-scheduler
   ```

2. **Virtuelle Umgebung einrichten**:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. **Abhängigkeiten installieren**:
   ```bash
   pip install -e ".[dev]"
   pip install ruff
   ```

### 3. Qualitätsprüfung vor dem Commit

1. **Testsuite ausführen**: `pytest`
2. **Linter prüfen**: `ruff check .`
3. **Syntaxprüfung**: `python -m compileall src tests`
4. **Git Diff prüfen**: `git diff --check`
