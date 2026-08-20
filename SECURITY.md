# Security Policy / Sicherheitsrichtlinie

**[English](#english)** | **[Deutsch](#deutsch)**

---

<a name="english"></a>
## English

### Security & Privacy Invariants

`ellmos-scheduler` provides standalone, local-first cron, interval, and daily task scheduling with cryptographic authority receipts and atomic execution leasing. The module adheres to strict architectural security invariants:

1. **Local-First & Zero-Egress Invariant**:
   - All scheduling calculations, lease management, state storage (SQLite), and run histories operate strictly locally on the host.
   - No implicit network connections, telemetry beacons, cloud analytics, or unauthorized telemetry exist.
2. **Authority Preflight & Cryptographic Integrity**:
   - Jobs can declare mandatory authority sources (`policy`, `rule`, `decision`, `workflow`, `user-preference`).
   - Before executing any job payload, the scheduler verifies canonical file sources via dual read-only passes and SHA-256 integrity hash verification (`--require-authorities`).
   - Authority receipts store only public IDs, hashes, byte counts, and resolution verdicts. Raw source content or secrets are strictly rejected and never persisted.
3. **Fail-Closed Execution & Safe Encoding**:
   - Subprocess and command executors accept explicit `argv` lists only and execute directly without shell interpolation (`shell=False`).
   - Output stream decoding enforces strict error handling (`PYTHONIOENCODING=utf-8:strict`). Undecodable output terminates the run with a failed status rather than silently corrupting audit logs.
4. **Atomic Concurrency & Lease Safety**:
   - Deterministic `run_id` generation and atomic database leases prevent double-execution across concurrent scheduler workers or parallel host processes.
   - Expired or abandoned leases are safely recovered without leaving orphaned execution locks.
5. **Read-Only Inspection Surface**:
   - Commands such as `status`, `authority-receipt`, and dry-run imports (`import-bach --dry-run`) are strictly read-only and never mutate database records or execution states.

### Supported Versions

| Version | Supported | Notes |
|---------|-----------|-------|
| `0.3.x` | :white_check_mark: | Active release stream |
| `< 0.3.0` | :x: | Legacy release branch |

### Reporting a Vulnerability

If you discover a security vulnerability or boundary violation in `ellmos-scheduler`:

1. **Do not open a public issue.**
2. Report the vulnerability privately via GitHub Security Advisories or by contacting the maintainers directly at [security@ellmos.ai](mailto:security@ellmos.ai).
3. Please provide a clear description of the vulnerability, reproduction steps, affected platform/environment, and impact assessment.
4. We aim to acknowledge receipt within 48 hours and provide a coordinated remediation release.

---

<a name="deutsch"></a>
## Deutsch

### Sicherheits- & Datenschutz-Invarianten

`ellmos-scheduler` stellt eine eigenständige, lokale Cron-, Intervall- und Tagesplan-Steuerung mit kryptographischen Authority-Receipts und atomarer Ausführungs-Leasesteuerung bereit. Das Modul erfüllt verbindliche Sicherheitsregeln:

1. **Local-First & Zero-Egress-Invariante**:
   - Alle Zeitplan-Berechnungen, Lease-Verwaltung, Zustandsdatenbanken (SQLite) und Ausführungshistorien verbleiben strikt lokal auf dem Host-System.
   - Es existieren keine Hintergrundnetzwerkverbindungen, Telemetrie-Dienste, Cloud-Analysen oder unautorisierte Uploads.
2. **Authority-Preflight & Kryptographische Integrität**:
   - Aufgaben können verbindliche Autorisierungsquellen (`policy`, `rule`, `decision`, `workflow`, `user-preference`) deklarieren.
   - Vor Ausführung einer Aufgabe liest der Scheduler die Referenzdokumente zweifach schreibgeschützt ein und verifiziert die SHA-256-Prüfsumme (`--require-authorities`).
   - Authority-Receipts speichern ausschließlich öffentliche IDs, Hashes, Byte-Zahlen und Statuswerte. Rohe Textinhalte oder Geheimnisse werden strikt abgewiesen und nicht persistiert.
3. **Fail-Closed Ausführung & Sichere Zeichenkodierung**:
   - Befehls- und Subprozess-Adapter akzeptieren ausschließlich explizite `argv`-Listen und starten ohne Shell (`shell=False`).
   - Die Dekodierung der Prozessausgaben erzwingt strikte Fehlerbehandlung (`PYTHONIOENCODING=utf-8:strict`). Nicht dekodierbare Ausgabe führt zum sauberen Fehlschlag des Laufs, statt Audit-Logs still zu korrumpieren.
4. **Atomare Nebenläufigkeit & Lease-Sicherheit**:
   - Determinative `run_id`-Erzeugung und atomare Datenbank-Leases verhindern Doppelstarts bei parallelen Scheduler-Workern.
   - Abgelaufene oder verwaiste Leases werden sicher bereinigt (`abandoned`), ohne blockierte Zustände zu hinterlassen.
5. **Rein lesende Prüfschnittstellen**:
   - Befehle wie `status`, `authority-receipt` oder `import-bach --dry-run` sind rein lesend und verändern zu keinem Zeitpunkt Datensätze oder Ausführungszustände.

### Unterstützte Versionen

| Version | Unterstützt | Anmerkungen |
|---------|-------------|-------------|
| `0.3.x` | :white_check_mark: | Aktiver Versionszweig |
| `< 0.3.0` | :x: | Frühere Versionszweige |

### Schwachstellen melden

Sollten Sie eine Sicherheitslücke oder eine Verletzung der Sicherheitsrichtlinien in `ellmos-scheduler` feststellen:

1. **Bitte erstellen Sie kein öffentliches Issue.**
2. Melden Sie die Schwachstelle vertraulich über GitHub Security Advisories oder per E-Mail an [security@ellmos.ai](mailto:security@ellmos.ai).
3. Bitte fügen Sie eine Beschreibung, Reproduktionsschritte und eine Einschätzung der Auswirkungen bei.
4. Wir bestätigen den Eingang in der Regel innerhalb von 48 Stunden und stellen ein koordiniertes Update bereit.
