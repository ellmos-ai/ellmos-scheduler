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
