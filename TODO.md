# TODO.md — Active work

**Version:** 0.3.6  
**Updated:** 2026-11-03
**Reason:** Lokale Ignore-Regeln und belegte Main-Integrationen; Abhängigkeits- und Releasefreigaben bleiben separat.
**Purpose:** Aufgaben- und Statusverfolgung gemäß kanonischen Release-Gates und Invarianten.

## STATUS

| Category | Status | Details |
|---|---|---|
| Core Scheduler & Timing Engine | DONE | Unterstützt `interval`, `daily` (zeitzonenbewusst) und 5-Feld `cron` inklusive Schaltjahr-, DST-Gap- und Fold-0-Behandlung (`INV-LOCAL-01`, `INV-STRM-05`). |
| Lease & Claim Concurrency | DONE | Atomare SQLite-Leases, deduplizierte Claims und Wiederherstellung verfallener Ansprüche bei Worker-Ausfall (`INV-CONC-03`). |
| Preflight Authority Gate | DONE | Doppelte Read-Only-Prüfung mit SHA-256-Integritätshash aller Regel- und Richtliniendateien vor der Ausführung (`INV-AUTH-04`, `INV-PRIV-02`). |
| Executors & Adapters | DONE | Shell-freie Prozessausführung via Argv für native Befehle, COMA-Agenten, MarbleRun-Ketten und anpassbare Executor-Registries (`INV-EXEC-06`). |
| Stream Encoding & Fail-Closed Safety | DONE | Strikter UTF-8-Standard mit konfigurierbaren Legacy-Codecs (CP1252, Latin-1, ASCII) ohne verlustbehaftete Dekodierungs-Handler (`INV-STRM-05`). |
| Path Neutrality & Hygiene | DONE | Benannte lokale Zustands-/Authdateien werden ignoriert; bereinigte Vorlagen bleiben trackbar. Keine allgemeine Geheimniserkennung oder rückwirkende Entfernung getrackter Inhalte (`INV-LOCAL-01`). |
| AI Discoverability & Metadata | DONE | Maschinenlesbares `llms.txt`, PEP 621 Metadaten & Classifiers, PEP 639 Lizenzinventar (`THIRD_PARTY_LICENSES.md`) und 16-Punkte zweisprachige README-Parität (`INV-MOD-08`). |
| CI Workflows & Multi-Host Defense | DONE | Multi-OS GitHub Actions Matrix (Python 3.10–3.13 auf Linux, Windows, macOS), Stale-Workflow, Timeout-Guardrails und Multi-Host-Konfliktschutz (`INV-PLAT-09`). |
| Ecosystem & Plan-D Parity | DONE | Registriert in `.MODULES/.CONTROL/ellmos-scheduler`, Plan-D-Pointer konfiguriert, gitloser Multi-Device-Spiegel synchronisiert (`INV-RES-07`). |
| Public Release Gate | USER | MIT-Lizenz bestätigt; 10/10 automatisierte Release-Gates bestanden; öffentliche Freigabe bereit zur Nutzerentscheidung (`INV-SLA-10`). |

## Formalized next tasks

- [x] **TASK-SCHED-05: Private POSIX-Zustandsdateien** (`effort=medium`, `scope=store`, priority `high`).
  - **Historischer Befund:** `SchedulerStore.connect()` erzeugt bei umask 022 einen Zustandsordner mit 0755 und SQLite mit 0644. Andere lokale Benutzer können Payloads und Run-Ausgaben lesen, wenn alle Vorfahren durchsuchbar sind. Ein Home mit 0700 schützt den Standardpfad. Keine Windows-ACL- oder Remote-Exposition belegt.
  - **Korrektur auf aktueller Defaultbasis (03.11.2026):** Neue moduleigene Verzeichnisse einschließlich Zwischenverzeichnissen erhalten 0700; neue Datenbanken werden vor SQLite exklusiv mit 0600 angelegt. Regressionen prüfen umask 022, aktive WAL/SHM, Wiederöffnen und unveränderte gemeinsame Verzeichnisse. Bestehende Datenbankrechte werden nicht migriert. Unabhängig abgenommen und als PR #20 auf main integriert (a70cccb6930a99f916a2be319bd559c62ea46faf). Echte UID65534/65533-Proben bestätigten private Neuanlage und erhaltenes absichtliches Sharing; Bestandsmigration, Windows-ACL und angreiferkontrollierte Eltern liegen außerhalb dieses abgeschlossenen Teilumfangs.

- [ ] **TASK-SCHED-06: Sicherheitsversprechen gegen konkrete Kontrollen abgleichen** (`effort=medium`, `scope=documentation`, priority `normal`).
  - **Historischer Befund:** CLI `status`/`authority-receipt` initialisieren den Store; externe Executoren unterliegen keiner Scheduler-Netzwerksperre; Receipts sind Hashbelege und keine Signaturen oder unveränderliche Ablage. Absolute Datei-URIs und vollständige Payloads bleiben lokal gespeichert. Kein belegter Autorisierungsbypass.
  - **Korrektur auf aktueller Defaultbasis (03.11.2026):** Die vier Inspektionsbefehle lesen mit `mode=ro` ohne Initialisierung/Migration und melden fehlende oder unpassende Zustände ausdrücklich. Regressionen prüfen aktuelle WAL-Daten und konsistente Snapshots; EN/DE/SECURITY beschreiben den Umfang einschließlich möglicher WAL-Koordinationsdateien. Unabhängig abgenommen und als PR #21 integriert (8b8f164127e123c282ecac75d846360d88b03027).
  - **Dokumentation auf aktueller Defaultbasis (03.11.2026):** EN/DE/SECURITY, Index und Inventare begrenzen Aussagen zu Netzwerk-/Aufruferrechten, gespeicherten Inhalten, veränderbaren Hashbelegen und CI-/Abhängigkeitsnachweisen auf tatsächlich implementierte Mechanismen. Vergleichszeilen, CLI-Name und historischer Testzähler sind angeglichen; strikte Dekodierung wird von einer rückwirkenden Verhinderung bereits erfolgter Programmwirkungen getrennt. Unabhängig abgenommen und als PR #22 integriert (400c5a47991071e158a1c79779814ee7797c24f7).
  - **Befehlslaufzeiten auf aktueller Defaultbasis (03.11.2026):** Die auf aktuellem main reproduzierte geerbte Ausgabepipe verzögerte einen 0,3-Sekunden-Timeout auf rund 1,72 Sekunden und ließ einen synthetischen Nachkommen weiterschreiben. Übernommen wurde die unabhängig geprüfte Job-/Gruppensteuerung aus PR #15 mit Freigabe erst nach Containment-Zuordnung, geschlossener Eingabe, Controller-EOF-Bereinigung und gemeinsamer 16-MiB-Ausgabegrenze. Erfolgreicher ausdrücklicher MarbleRun-Hintergrunddispatch übergibt Verantwortung; Fehler bleiben begrenzt. Die aktuelle Main-Fassung wurde mit vollständigen Windows-/Linux-Suiten unabhängig abgenommen und als PR #23 integriert (1e163db0d5c25995f666d756d43f936e31c3fcaa).
  - **Ignore-Regeln auf aktueller Defaultbasis (03.11.2026):** `.db`/`.sqlite`/`.sqlite3` und zugehörige WAL/SHM/Rollback-Journals sowie benannte konventionelle Authdateien werden ignoriert; bereinigte `.env.example`/`.env.sample`/`.env.template` bleiben trackbar. Sechs echte Git-Semantikfälle scheiterten vor der Übernahme auf aktuellem main. Keine allgemeine Geheimniserkennung oder Historienbereinigung; unabhängig abgenommen und als PR #24 integriert (37a8f58b83eb7c72178a547a76ea60df697696c1).
  - **Spätresultate auf aktueller Defaultbasis (03.11.2026):** Vier echte Recoverykonflikte beim Receipt-/Start-/Fail-Claimed-/Finish-Übergang brechen auf aktuellem main den Tick mit RuntimeError ab. Die übernommene Korrektur aus PR #18 meldet Zustandskonflikte pro Lauf, lässt ursprüngliche und erneut vergebene Datensätze unverändert und bearbeitet andere beanspruchte Jobs weiter. Andere Speicherfehler propagieren. Dies ist keine externe Ausführungssperre, Ownerprüfung oder Lease-Verlängerung; mit vollständigen aktuellen Windows-/Linux-Suiten unabhängig abgenommen und als PR #25 integriert (5fb87981f4c89a7467f3e67980b3c2151be03e57).
  - **Zeitgrenzen auf aktueller Defaultbasis (03.11.2026):** Von 25 echten Zeitgrenzentests scheiterten auf aktuellem main 15 direkt an verfrühter/verpasster Vergabe, abgelaufener Startzulassung, Historienordnung, fehlendem Fehlerrollback oder zu früh beobachteter Uhr vor einer Writersperre. Die Korrektur aus PR #19 nutzt präzise UTC-Schlüssel für Z-/Offset-Zeitstempel und erlangt vor der realen Startzeitbeobachtung den Writerlock; gespeicherte Rohwerte und Run-IDs bleiben unverändert. Start bei exakter Expiry bleibt erlaubt, streng danach nicht. Keine Lease-Verlängerung, Ownerprüfung oder Beendigung laufender externer Arbeit; unabhängige aktuelle Head-Abnahme und Integration stehen noch aus.
  - **Weiter offen:** Lease-Fencing, allgemeine CPU-/RAM-/Privileggrenzen sowie absichtlich abgetrennte, brokervermittelte und eigene Executoren separat prüfen. TASK-SCHED-07 bleibt für aufgelöste Abhängigkeiten und Advisories getrennt offen.

- [ ] **TASK-SCHED-07: CI-Dependency-Hinweise verifizieren** (`effort=medium`, `scope=ci`, priority `normal`).
  - **Befund vom 16.10.2026:** OSV meldet `wheel==0.45.1` (GHSA-8rrh-rw8j-w5fx) und `setuptools==80.9.0` (GHSA-h35f-9h28-mq5c). Betroffene `wheel unpack`- bzw. macOS-MANIFEST/sdist-Aufrufe sind im aktuellen Wheel-CI nicht belegt; kein Advisory-Gesamt-PASS. Lokales tzdata 2026.2 liegt hinter PyPI 2026.5.
  - **Nächster Schritt:** Toolchain und transitive Auflösung isoliert auf allen unterstützten Plattformen prüfen; nur verifizierte Pins ändern. Keine riskanten Upgrades im Audit.

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
