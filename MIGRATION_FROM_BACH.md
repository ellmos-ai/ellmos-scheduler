# Migration aus BACH

Der vorhandene Scheduler in `BACH/system/hub/scheduler.py` ist eine
funktionsreiche Legacy-Quelle, aber nicht die Ziel-Quelle der Wahrheit.

## Phasen

1. **Inventar:** BACH-Tabellen `scheduler_jobs`/`scheduler_runs`, CLI-Kommandos,
   Pause/Steer, Doctor und Session-Legacy vollständig als Vertrag erfassen.
2. **Adapter:** `bach scheduler ...` ruft `ellmos_scheduler` auf. BACH-spezifische
   Jobtypen werden Executor-Adapter.
3. **Read-only Import:** Bestehende BACH-Jobs werden einmalig mit stabiler
   Provenienz-ID übernommen; noch keine Löschung.
4. **Parallelvergleich:** Due-Zeiten und Status werden über mindestens 14 Tage
   verglichen, aber nur ein Scheduler darf mutierend ausführen.
5. **Umschalten:** Das eigenständige Modul wird alleiniger State Owner.
6. **Rückbau:** BACH-interne Fachlogik archivieren; BACH behält nur CLI-/GUI-
   Adapter und Kompositionsmanifest.

## Umgesetzter Migrationspfad

`ellmos_scheduler.bach` enthält den kontrollierten Übergang:

- `read_legacy_jobs(...)` öffnet die Legacy-Datenbank zwingend mit SQLite
  `mode=ro`.
- `import_legacy_jobs(...)` bietet einen mutierungsfreien Dry-Run und übernimmt
  unterstützte Jobs idempotent als `bach:<legacy-id>`. Bestehende Ziel-Jobs
  werden nie überschrieben. Quell- und Zieldatenbank müssen verschiedene
  Dateien sein; identische Pfade und Hardlinks werden vor dem Ziel-`init()`
  abgewiesen.
- Intervalle (`s`, `m`, `h`, `d`) und fünfteilige Cron-Ausdrücke erhalten die
  Due-Semantik des BACH-Daemons. Bei gleichzeitig eingeschränktem
  Tag-des-Monats und Wochentag gilt wie bei `croniter` die Oder-Semantik.
  Nicht existierende lokale Fälligkeitszeiten aus Cron oder
  `last_run + interval` werden wie beim Legacy-Due-Vergleich am ersten gültigen
  Zeitpunkt nach dem DST-Spring-Gap fällig.
- Skript- und einfache Command-Jobs werden in argv-basierte
  `subprocess`-Payloads überführt. Shell-Operatoren, Variablenexpansion,
  Wildcards und weitere Shell-Metazeichen werden nicht emuliert, sondern mit
  einem expliziten Skip-Grund gemeldet.
- Name, Beschreibung, Legacy-ID, Retry-Konfiguration und ursprünglicher
  Zeitplan bleiben unter `_bach` als Provenienz erhalten.
- `BachSchedulerAdapter` stellt BACH eine schmale API für Status, Jobs,
  Pause/Resume, Tick und Import bereit.

Vor jedem echten Import zuerst:

```powershell
ellmos-scheduler --db C:\state\scheduler.db import-bach `
  --source-db C:\path\to\bach.db `
  --bach-root C:\path\to\BACH `
  --timezone Europe/Berlin `
  --dry-run --json
```

Ohne `--dry-run` wird ausschließlich der Ziel-Store ergänzt.

## Bewusst offene Umschalt-Gates

- BACH-`chain`-/`toolchain`-Jobs besitzen im Legacy-Daemon keine automatische
  Due-Berechnung und werden deshalb nicht fälschlich als Zeitjob importiert.
  Neue Kettenjobs verwenden direkt den `marblerun`-Executor.
- Event-/Manual- und Session-Scheduler-Legacy bleiben bis zu einem expliziten
  manuellen Trigger-Vertrag außerhalb des Imports.
- Retry-Felder werden als Provenienz erhalten, aber noch nicht als neue
  Retry-Policy interpretiert.
- Operator-Steering, Doctor-/Recovery-Ausgaben und GUI-Routing müssen vor dem
  Umschalten in BACH an den neuen Adapter angeschlossen werden.
- Der 14-Tage-Parallelvergleich ist ein Betriebs-Gate und wird durch diese
  Implementierung nicht vorgetäuscht.
- Änderungen im derzeit fremd gesperrten BACH-Checkout sind nicht Bestandteil
  dieses Moduls. Die dortige Provider-Seam kann den hier exportierten Adapter
  nach Freigabe anbinden.
