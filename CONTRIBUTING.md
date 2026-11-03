# Contributing to ellmos-scheduler

Thank you for your interest in contributing to **ellmos-scheduler** (`ellmos-ai/ellmos-scheduler`), a standalone, modular scheduler and execution run recorder built for modular ellmos stacks, autonomous multi-agent environments, and external adapters (BACH, COMA, MarbleRun, swarm-ai).

[English](#english) | [Deutsch](#deutsch)

---

<a id="english"></a>
## English

### 1. Architectural Principles & Invariants

Contributions must preserve these ten mechanisms and document their execution and trust boundaries:

- **Local state & network boundaries (`INV-LOCAL-01`)**: SQLite scheduling needs no mandatory cloud service; external executors and remote filesystem paths retain host network permissions. No network filter is installed.
- **Caller permissions (`INV-PRIV-02`)**: RunAsInvoker inherits the caller's rights without requesting elevation or dropping existing privileges. Use an appropriate OS account.
- **Valid-lease claims (`INV-CONC-03`)**: Transactions serialize claims during valid leases. Retry after expiry does not prove the previous process has stopped.
- **Authority readback (`INV-AUTH-04`)**: Two reads and SHA-256 compare observed bytes of trusted configured sources; hashes alone do not establish approval authenticity or permission to execute.
- **Strict output decoding (`INV-STRM-05`)**: UTF-8 is the default; supported selected codecs are decoded strictly. A failed result does not undo prior program effects or redact captured output.
- **Shell Injection Safety (`INV-EXEC-06`)**: Subprocess execution strictly uses explicit `argv` lists (`shell=False`).
- **Timeouts and abandoned claims (`INV-RES-07`)**: Direct command processes have a timeout; expiry permits claim recovery, without proving descendant termination or general resource bounds.
- **Modular Ecosystem Integration (`INV-MOD-08`)**: Pluggable executor registry and clean decoupling outside monoliths.
- **Platform tests (`INV-PLAT-09`)**: CI covers Windows, Linux and macOS; record skips and separate native device/provider acceptance rather than promising universal parity.
- **Stored records and inventory (`INV-SLA-10`)**: Local hash/readback records are mutable by database writers, not signed or append-only. Payloads/output can be sensitive; selected license inventories are not complete dependency audits. See SECURITY.md for disclosure policy.

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

Beiträge müssen diese zehn Mechanismen erhalten und ihre Ausführungs- und Vertrauensgrenzen dokumentieren:

- **Lokaler Zustand und Netzwerkgrenzen (`INV-LOCAL-01`)**: SQLite-Zeitplanung braucht keinen verpflichtenden Cloud-Dienst; externe Executoren und entfernte Dateisystempfade behalten die Netzwerkrechte des Hosts. Ein Netzwerkfilter wird nicht eingerichtet.
- **Aufruferrechte (`INV-PRIV-02`)**: RunAsInvoker übernimmt vorhandene Rechte, ohne zusätzliche anzufordern oder geerbte Rechte abzulegen. Ein geeignetes OS-Konto verwenden.
- **Claims mit gültigen Leases (`INV-CONC-03`)**: Transaktionen serialisieren Claims während gültiger Leases. Ein erneuter Versuch nach Ablauf beweist nicht, dass der vorige Prozess beendet ist.
- **Authority-Rücklesen (`INV-AUTH-04`)**: Zwei Lesevorgänge und SHA-256 vergleichen beobachtete Bytes vertrauenswürdiger Quellen; Hashes allein beweisen weder Freigabeechtheit noch Ausführungsberechtigung.
- **Strikte Ausgabedekodierung (`INV-STRM-05`)**: UTF-8 ist der Standard; unterstützte gewählte Codecs werden strikt dekodiert. Ein fehlgeschlagenes Ergebnis macht Programmwirkungen nicht rückgängig und schwärzt erfasste Ausgaben nicht.
- **Schutz vor Shell-Injection (`INV-EXEC-06`)**: Subprozess-Ausführung nutzt ausschließlich explizite `argv`-Listen (`shell=False`).
- **Timeouts und abgelaufene Claims (`INV-RES-07`)**: Direkte Befehlsprozesse haben einen Timeout; Ablauf erlaubt die Claim-Wiederaufnahme, beweist aber weder Nachkommenbeendigung noch allgemeine Ressourcengrenzen.
- **Modulare Systemintegration (`INV-MOD-08`)**: Steckbare Executor-Registry und saubere Trennung außerhalb monolithischer Blöcke.
- **Plattformtests (`INV-PLAT-09`)**: CI prüft Windows, Linux und macOS; Auslassungen und separate Geräte-/Provider-Abnahmen dokumentieren statt universelle Parität zu versprechen.
- **Gespeicherte Datensätze und Inventar (`INV-SLA-10`)**: Lokale Hash-/Rücklesebelege sind durch DB-Schreibberechtigte veränderbar, weder signiert noch append-only. Payloads/Ausgaben können sensibel sein; ausgewählte Lizenzinventare sind keine vollständigen Abhängigkeitsaudits. Meldewege stehen in SECURITY.md.

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
