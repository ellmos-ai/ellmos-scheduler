# Security Policy / Sicherheitsrichtlinie

**[English](#english)** | **[Deutsch](#deutsch)**

---

<a name="english"></a>
## English

### Security & Privacy Invariants

`ellmos-scheduler` provides standalone, local-first cron, interval, and daily task scheduling with hash/readback authority records and atomic claim transactions. The following mechanisms have explicit execution and trust boundaries:

1. **Local state & execution boundaries**:
   - Scheduling and lease state use SQLite; deployment paths, remote filesystems and executed programs can access remote resources.
   - No network filter or executor sandbox is installed. Programs inherit caller permissions; host policy must enforce any offline or privilege restrictions.
2. **Authority Preflight & Cryptographic Integrity**:
   - Jobs can declare mandatory authority sources (`policy`, `rule`, `decision`, `workflow`, `user-preference`).
   - Before executing any job payload, the scheduler verifies canonical file sources via dual read-only passes and SHA-256 integrity hash verification (`--require-authorities`).
   - Authority receipts omit referenced file contents, but include IDs, absolute file origins, hashes, byte counts and verdicts. Validation rejects recognized credential-like metadata; it is not general secret detection. Job payloads and captured output/error remain stored and can be sensitive.
   - Operators supply trusted source references. Matching hashes compare observed bytes; source meaning, approval authenticity and permission to execute are not established by a hash alone.
3. **Fail-Closed Execution & Safe Encoding**:
   - Subprocess and command executors accept explicit `argv` lists only and execute directly without shell interpolation (`shell=False`).
   - Output stream decoding enforces strict error handling (`PYTHONIOENCODING=utf-8:strict`). Undecodable output terminates the run with a failed status rather than silently corrupting audit logs.
4. **Atomic Concurrency & Lease Safety**:
   - Deterministic `run_id` generation and transactions serialize claims during valid leases. Retry after expiry can overlap an older process unless external termination or fencing is established.
   - Expiry records an abandoned claim and permits recovery; it does not prove process-tree termination or bound all executor resources.
5. **Read-Only Inspection Surface**:
   - `status`, `jobs`, `runs` and `authority-receipt` open existing databases with SQLite `mode=ro`; each read connection uses one transaction snapshot. They perform no initialization, schema migration or record updates. Missing/incompatible/corrupt state is an error, and committed live WAL data is included. SQLite may maintain WAL coordination files. Dry-run imports (`import-bach --dry-run`) preview changes without importing job records.

### Stored records and integrity

Jobs retain full payload JSON; run output and error retain up to 20,000 characters each.
Treat the database, its WAL/SHM sidecars and backups as potentially sensitive. Hashes
and receipt IDs support readback comparison; no signing key or append-only store is
implemented. Writers with database access can change history.

### New POSIX state files

New state directories, including missing intermediate parents, are created with
mode `0700`; a new database is exclusively created with mode `0600` before SQLite
can write payloads. SQLite WAL and shared-memory files inherit the database's
private permissions. The process umask may restrict these modes further and is
not changed by the store. Existing directories and database permissions remain
unchanged: owners must separately inspect and restrict older or intentionally
shared state, including pre-existing sidecar files. Use a trusted parent directory;
this is not protection against an attacker who can replace its entries. Windows
ACLs are unaffected.

### Supported Versions

| Version | Supported | Notes |
|---------|-----------|-------|
| `0.3.x` | :white_check_mark: | Active release stream |
| `< 0.3.0` | :x: | Legacy release branch |

### Reporting a Vulnerability

If you discover a security vulnerability or boundary violation in `ellmos-scheduler`:

1. **Do not open a public issue.**
2. Report the vulnerability privately via [GitHub Security Advisories](https://github.com/ellmos-ai/ellmos-scheduler/security/advisories) or by contacting the maintainers directly at [security@ellmos.ai](mailto:security@ellmos.ai) (fallbacks: [security@open-bricks.org](mailto:security@open-bricks.org), [support@lukasgeiger.com](mailto:support@lukasgeiger.com), [lukas@open-bricks.org](mailto:lukas@open-bricks.org)).
3. Please provide a clear description of the vulnerability, reproduction steps, affected platform/environment, and impact assessment.
4. **Binding Response SLA**: We commit to acknowledging receipt within **48 hours** and providing an initial triage assessment within **5 business days**, followed by coordinated remediation.

### Statutory Notice & Liability Limitation (§ 521 BGB Gefälligkeitsrecht)
The provision of this software and its associated documentation is gratuitous (unentgeltliche Bereitstellung). In accordance with the statutory liability regime under German Civil Law governing gratuitous services (**§ 521 BGB** — *Haftung des Schenkers*), liability for any defects of quality or title (Sach- und Rechtsmängel) is strictly limited to cases of intentional misconduct (**Vorsatz**) and gross negligence (**grobe Fahrlässigkeit**). Any broader statutory warranty or tortious liability for slight negligence is expressly excluded to the fullest extent permitted by applicable law.

---

<a name="deutsch"></a>
## Deutsch

### Sicherheits- & Datenschutz-Invarianten

`ellmos-scheduler` stellt eine eigenständige, lokale Cron-, Intervall- und Tagesplan-Steuerung mit Hash-/Rücklesebelegen und atomaren Claim-Transaktionen bereit. Die folgenden Mechanismen besitzen ausdrücklich beschriebene Ausführungs- und Vertrauensgrenzen:

1. **Lokaler Zustand & Ausführungsgrenzen**:
   - Zeitplanung und Lease-Zustand verwenden SQLite; konfigurierte Pfade, entfernte Dateisysteme und ausgeführte Programme können entfernte Ressourcen ansprechen.
   - Ein Netzwerkfilter oder eine Executor-Sandbox wird nicht eingerichtet. Programme übernehmen Aufruferrechte; Offline- und Rechtebeschränkungen müssen durch die Host-Richtlinie umgesetzt werden.
2. **Authority-Preflight & Kryptographische Integrität**:
   - Aufgaben können verbindliche Autorisierungsquellen (`policy`, `rule`, `decision`, `workflow`, `user-preference`) deklarieren.
   - Vor Ausführung einer Aufgabe liest der Scheduler die Referenzdokumente zweifach schreibgeschützt ein und verifiziert die SHA-256-Prüfsumme (`--require-authorities`).
   - Authority-Belege lassen referenzierte Dateiinhalte aus, enthalten aber IDs, absolute Datei-Ursprünge, Hashes, Byte-Zahlen und Statuswerte. Die Validierung weist erkannte Zugangsdaten-Muster ab; sie ist keine allgemeine Geheimniserkennung. Job-Payloads und erfasste Ausgaben/Fehler bleiben gespeichert und können sensibel sein.
   - Betreiber stellen vertrauenswürdige Quellenreferenzen bereit. Gleiche Hashes vergleichen beobachtete Bytes; Quellbedeutung, Echtheit einer Freigabe und Ausführungsberechtigung sind durch einen Hash allein nicht nachgewiesen.
3. **Fail-Closed Ausführung & Sichere Zeichenkodierung**:
   - Befehls- und Subprozess-Adapter akzeptieren ausschließlich explizite `argv`-Listen und starten ohne Shell (`shell=False`).
   - Die Dekodierung der Prozessausgaben erzwingt strikte Fehlerbehandlung (`PYTHONIOENCODING=utf-8:strict`). Nicht dekodierbare Ausgabe führt zum sauberen Fehlschlag des Laufs, statt Audit-Logs still zu korrumpieren.
4. **Atomare Nebenläufigkeit & Lease-Sicherheit**:
   - Deterministische `run_id`-Erzeugung und Transaktionen serialisieren Claims während gültiger Leases. Ein erneuter Versuch nach Ablauf kann mit einem älteren Prozess überlappen, solange dessen Ende oder externes Fencing nicht nachgewiesen ist.
   - Ablauf protokolliert einen abandoned Claim und ermöglicht Wiederaufnahme; er beweist weder das Ende des Prozessbaums noch allgemeine Ressourcengrenzen.
5. **Rein lesende Prüfschnittstellen**:
   - `status`, `jobs`, `runs` und `authority-receipt` öffnen vorhandene Datenbanken mit SQLite `mode=ro`; jede Leseverbindung verwendet einen Transaktions-Snapshot. Initialisierung, Schemamigration und Datensatzänderungen bleiben aus. Fehlende/inkompatible/beschädigte Zustände führen zu Fehlern; bestätigte Daten aus einer aktiven WAL-Datei werden berücksichtigt. SQLite kann WAL-Koordinationsdateien pflegen. Trockenläufe (`import-bach --dry-run`) zeigen Änderungen vorab, ohne Job-Datensätze zu importieren.

### Gespeicherte Datensätze und Integrität

Jobs enthalten die vollständige Payload als JSON; Ausgaben und Fehler enthalten jeweils
bis zu 20.000 Zeichen. Datenbank, WAL/SHM-Dateien und Sicherungen sind als möglicherweise
sensibel zu behandeln. Hashes und Receipt-IDs dienen dem Rücklesevergleich; ein
Signaturschlüssel oder append-only Speicher ist nicht implementiert. Schreibberechtigte
können die Historie verändern.

### Neue POSIX-Zustandsdateien

Neue Zustandsverzeichnisse einschließlich fehlender Zwischenverzeichnisse erhalten
den Modus `0700`. Eine neue Datenbank wird vor dem ersten SQLite-Schreibzugriff
exklusiv mit `0600` angelegt. SQLite-WAL- und Shared-Memory-Dateien übernehmen die
privaten Datenbankrechte. Die Prozess-umask kann die Rechte weiter einschränken und
wird vom Store nicht verändert. Bestehende Verzeichnisse und Datenbankrechte bleiben
unverändert: Eigentümer müssen ältere oder bewusst gemeinsam genutzte Zustände und
bereits vorhandene Begleitdateien separat prüfen und absichern. Das übergeordnete
Verzeichnis muss vertrauenswürdig sein; ein Angreifer mit Austauschrechten für dessen
Einträge wird dadurch nicht abgewehrt. Windows-ACLs bleiben unverändert.

### Unterstützte Versionen

| Version | Unterstützt | Anmerkungen |
|---------|-------------|-------------|
| `0.3.x` | :white_check_mark: | Aktiver Versionszweig |
| `< 0.3.0` | :x: | Frühere Versionszweige |

### Schwachstellen melden

Sollten Sie eine Sicherheitslücke oder eine Verletzung der Sicherheitsrichtlinien in `ellmos-scheduler` feststellen:

1. **Bitte erstellen Sie kein öffentliches Issue.**
2. Melden Sie die Schwachstelle vertraulich über [GitHub Security Advisories](https://github.com/ellmos-ai/ellmos-scheduler/security/advisories) oder per E-Mail an [security@ellmos.ai](mailto:security@ellmos.ai) (Fallback: [security@open-bricks.org](mailto:security@open-bricks.org), [support@lukasgeiger.com](mailto:support@lukasgeiger.com), [lukas@open-bricks.org](mailto:lukas@open-bricks.org)).
3. Bitte fügen Sie eine Beschreibung, Reproduktionsschritte und eine Einschätzung der Auswirkungen bei.
4. **Verbindliche Reaktions-SLA**: Wir verpflichten uns, den Eingang von Sicherheitsmeldungen innerhalb von **48 Stunden** zu bestätigen und innerhalb von **5 Werktagen** eine fundierte erste Triage-Bewertung bereitzustellen.

### Gesetzlicher Hinweis & Haftungsbeschränkung (§ 521 BGB Gefälligkeitsrecht)
Die Bereitstellung dieser Software sowie der dazugehörigen Dokumentation erfolgt unentgeltlich (Gefälligkeitsverhältnis). Gemäß dem gesetzlichen Haftungsregime des deutschen Bürgerlichen Gesetzbuches (**§ 521 BGB** — *Haftung des Schenkers*) ist die Haftung für Sach- und Rechtsmängel ausdrücklich auf **Vorsatz** und **grobe Fahrlässigkeit** beschränkt. Eine Haftung für einfache oder leichte Fahrlässigkeit ist im gesetzlich zulässigen Rahmen vollständig ausgeschlossen.
