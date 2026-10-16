# TODO.md — Active work

**Version:** 0.3.6  
**Updated:** 2026-09-22  
**Reason:** Release-Gate-Härtung (10/10 PASS), Gate 1 .gitignore, Gate 10 TODO.md, PEP 639 Lizenzinventar und Plan-D-Parität  
**Purpose:** Aufgaben- und Statusverfolgung gemäß kanonischen Release-Gates und Invarianten.

## STATUS

| Category | Status | Details |
|---|---|---|
| Core Scheduler & Timing Engine | DONE | Unterstützt `interval`, `daily` (zeitzonenbewusst) und 5-Feld `cron` inklusive Schaltjahr-, DST-Gap- und Fold-0-Behandlung (`INV-LOCAL-01`, `INV-STRM-05`). |
| Lease & Claim Concurrency | DONE | Atomare SQLite-Leases, deduplizierte Claims und Wiederherstellung verfallener Ansprüche bei Worker-Ausfall (`INV-CONC-03`). |
| Preflight Authority Gate | DONE | Doppelte Read-Only-Prüfung mit SHA-256-Integritätshash aller Regel- und Richtliniendateien vor der Ausführung (`INV-AUTH-04`, `INV-PRIV-02`). |
| Executors & Adapters | DONE | Shell-freie Prozessausführung via Argv für native Befehle, COMA-Agenten, MarbleRun-Ketten und anpassbare Executor-Registries (`INV-EXEC-06`). |
| Stream Encoding & Fail-Closed Safety | DONE | Strikter UTF-8-Standard mit konfigurierbaren Legacy-Codecs (CP1252, Latin-1, ASCII) ohne verlustbehaftete Dekodierungs-Handler (`INV-STRM-05`). |
| Path Neutrality & Hygiene | DONE | Neutrales Umfeld, gehärtete `.gitignore`, null persönliche Entwicklerpfade, null hardcodierte Credentials oder API-Keys (`INV-LOCAL-01`). |
| AI Discoverability & Metadata | DONE | Maschinenlesbares `llms.txt`, PEP 621 Metadaten & Classifiers, PEP 639 Lizenzinventar (`THIRD_PARTY_LICENSES.md`) und 16-Punkte zweisprachige README-Parität (`INV-MOD-08`). |
| CI Workflows & Multi-Host Defense | DONE | Multi-OS GitHub Actions Matrix (Python 3.10–3.13 auf Linux, Windows, macOS), Stale-Workflow, Timeout-Guardrails und Multi-Host-Konfliktschutz (`INV-PLAT-09`). |
| Ecosystem & Plan-D Parity | DONE | Registriert in `.MODULES/.CONTROL/ellmos-scheduler`, Plan-D-Pointer konfiguriert, gitloser Multi-Device-Spiegel synchronisiert (`INV-RES-07`). |
| Public Release Gate | USER | MIT-Lizenz bestätigt; 10/10 automatisierte Release-Gates bestanden; öffentliche Freigabe bereit zur Nutzerentscheidung (`INV-SLA-10`). |

## Formalized next tasks

- [ ] **TASK-SCHED-05: Private POSIX-Zustandsdateien** (`effort=medium`, `scope=store`, priority `high`).
  - **Befund:** `SchedulerStore.connect()` erzeugt bei umask 022 einen Zustandsordner mit 0755 und SQLite mit 0644. Andere lokale Benutzer können Payloads und Run-Ausgaben lesen, wenn alle Vorfahren durchsuchbar sind. Ein Home mit 0700 schützt den Standardpfad. Keine Windows-ACL- oder Remote-Exposition belegt.
  - **Korrekturzweig vom 16.10.2026:** Neue moduleigene Verzeichnisse einschließlich Zwischenverzeichnissen erhalten 0700; neue Datenbanken werden exklusiv mit 0600 angelegt. Regressionen prüfen umask 022, WAL/SHM, Wiederöffnen und unveränderte gemeinsame Verzeichnisse. Bestehende Datenbankrechte werden nicht migriert. Unabhängige Prüfung und Integration stehen aus; deshalb bleibt der Punkt offen.

- [ ] **TASK-SCHED-06: Sicherheitsversprechen gegen konkrete Kontrollen abgleichen** (`effort=medium`, `scope=documentation`, priority `normal`).
  - **Befund:** CLI `status`/`authority-receipt` initialisieren den Store; externe Executoren unterliegen keiner Scheduler-Netzwerksperre; Receipts sind Hashbelege und keine Signaturen oder unveränderliche Ablage. Absolute Datei-URIs und vollständige Payloads bleiben lokal gespeichert. Kein belegter Autorisierungsbypass.
  - **Korrekturzweig vom 16.10.2026:** Die vier Inspektionsbefehle lesen mit `mode=ro` ohne Initialisierung/Migration und melden fehlende oder unpassende Zustände ausdrücklich. Regressionen prüfen aktuelle WAL-Daten und konsistente Snapshots; EN/DE/SECURITY beschreiben den Umfang. Unabhängige Prüfung und Integration stehen aus.
  - **Dokumentationszweig vom 16.10.2026:** EN/DE/SECURITY und die Inventare begrenzen Aussagen zu Netzwerk-/Aufruferrechten, gespeicherten Inhalten, Hashbelegen und CI-/Abhängigkeitsnachweisen auf den Quellcode. Unabhängige Prüfung und Integration stehen aus.
  - **Prozesszweig vom 16.10.2026:** Geerbte Pipes hielten einen Windows-Lauf trotz 1-Sekunden-Timeout rund 4,16 Sekunden offen. Command-/Subprocess-Ausführung verwendet nun ein vor Freigabe gebundenes Windows-Jobobjekt bzw. ein POSIX-Gate mit eigener Sitzungsgruppe, Controller-EOF-Bereinigung und 16-MiB-Ausgabegrenze. Physische Tests prüfen Timeout, normales Ende, Controller-Abbruch, fremde synthetische Geschwister und fehlgeschlagene Containment-Schritte. Ausdrückliche erfolgreiche MarbleRun-Hintergrundstarts übergeben die Prozessverantwortung; fehlgeschlagene Starts bleiben begrenzt. Unabhängige Prüfung und Integration stehen aus.
  - **Gitignore-Zweig vom 16.10.2026:** Lokale `.db`-/`.sqlite`-/`.sqlite3`-Dateien einschließlich WAL/SHM/Rollback-Journals und benannte konventionelle Authdateien werden ignoriert. Neutrale `.env.example`/`.env.sample`/`.env.template` bleiben eincheckbar. Echte Git-Prüfungen decken Root und Unterordner ab; keine allgemeine Geheimniserkennung oder rückwirkende Entfernung bereits getrackter Inhalte. Unabhängige Prüfung und Integration stehen aus.
  - **Weiter offen:** Lease-Fencing, CPU-/RAM-Grenzen sowie abgetrennte/brokervermittelte und eigene Executoren separat prüfen.

- [ ] **TASK-SCHED-07: CI-Dependency-Hinweise verifizieren** (`effort=medium`, `scope=ci`, priority `normal`).
  - **Befund vom 16.10.2026:** OSV meldet `wheel==0.45.1` (GHSA-8rrh-rw8j-w5fx) und `setuptools==80.9.0` (GHSA-h35f-9h28-mq5c). Betroffene `wheel unpack`- bzw. macOS-MANIFEST/sdist-Aufrufe sind im aktuellen Wheel-CI nicht belegt; kein Advisory-Gesamt-PASS. Lokales tzdata 2026.2 liegt hinter PyPI 2026.5.
  - **Korrekturzweig vom 16.10.2026:** Die beiden Advisories wurden über GitHub und OSV bestätigt. CI-Pins wechseln auf die ersten korrigierten Versionen `setuptools==83.0.0` und `wheel==0.46.2`. Das inzwischen zurückgezogene `build==1.5.1` wird durch das nicht zurückgezogene, Python-3.10-kompatible `build==1.6.1` ersetzt. CI prüft die installierten Abhängigkeiten mit `pip check` und protokolliert ihre tatsächlich aufgelösten Versionen. Versionsgebundene Advisory-Prüfung, native Matrix und unabhängige Prüfung sind getrennte Nachweise; keine allgemeine Sicherheitsfreigabe.
  - **Installer-Befund:** Die frische lokale Prüfumgebung enthielt `pip==25.0.1` mit aktuellen Advisory-Treffern. CI legt deshalb vor der weiteren Auflösung `pip==26.2.1` fest; diese Version unterstützt Python 3.10 und wurde separat geprüft. Das belegt keinen früheren CI-Exploit.
  - **Weiter offen:** Unabhängige Prüfung und Integration; die allgemeine Build-Backend-Mindestanforderung und bereits installierte Umgebungen werden nicht migriert. tzdata bleibt eine unbeschränkte Laufzeitauflösung innerhalb der bestehenden Mindestanforderung.

- [x] **TASK-SCHED-08: Private Dokumentationspfade neutralisieren** (`effort=low`, `scope=documentation`, priority `normal`).
  - **Ergebnis vom 16.10.2026:** Beide Quick-Start-Payloads nutzen denselben neutralen Beispielordner; der Marketing-Log enthält keinen lokalen Klonpfad mehr. Keine Historienbereinigung oder Löschung; Source-Audit auf f2740ba7 bleibt revisionsgebunden.

- [ ] **TASK-SCHED-01: Dynamische Wiederholungsintervalle bei adaptiver Systemlast (Backoff-Strategie)** (`effort=medium`, `scope=engine`, priority `normal`).
  - **Ziel:** Intelligente Verlängerung von Job-Intervallen bei hoher Systemauslastung oder wiederholten Adapter-Fehlern.
  - **Definition of Done:** Konfigurierbarer Exponential-Backoff im SchedulerStore und automatisierte Regressionstests.

- [ ] **TASK-SCHED-02: Erweiterte Metrik-Exporte für Prometheus / OpenTelemetry Endpunkte** (`effort=large`, `scope=observability`, priority `low`).
  - **Ziel:** Bereitstellung von Prometheus-kompatiblen Metrik-Ausgaben für Ticks, Lease-Claims und Ausführungsdauern.
  - **Definition of Done:** CLI-Kommando `ellmos-scheduler export-metrics` und formatierte Endpunkte mit Testabdeckung.

- [x] **TASK-SCHED-03: Release-Hygiene, Lizenzinventar & Gate-Bereitschaft (v0.3.6)** (`effort=low`, `scope=hygiene`, priority `high`).
  - **Ergebnis:** Standard-`TODO.md` mit `## STATUS`-Tabelle etabliert, `.gitignore` um Release-Pflichtmuster gehärtet, PEP 639 `license-files` in `pyproject.toml` synchronisiert und `final_gate_check.py` auf 10/10 PASS gebracht.

- [x] **TASK-SCHED-04: PEP 639 Metadaten, Vertragstests & Plan-D-Parität (v0.3.6)** (`effort=low`, `scope=metadata`, priority `high`).
  - **Ergebnis:** Single-Source-Version 0.3.6 synchronisiert, neue Vertragstests in `tests/test_metadata.py` ergänzt, Plan-D-Spiegel `.MODULES/.CONTROL/ellmos-scheduler` mit `PLAN_D_POINTER.md` und `REPO.pointer.json` synchronisiert.

---
<!-- REMEMBER: ENDUSERTEXTE BEKOMMEN ECHTE UMLAUTE Ü Ö Ä ß -->
