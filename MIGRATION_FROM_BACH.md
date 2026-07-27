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

## Noch offene Paritätsflächen

- BACH-`chain`-/`task`-Jobtypen als Adapter
- Session-Scheduler-Legacy und dessen Deprecation
- Operator-Steering bis zum sicheren Chain-Checkpoint
- Doctor-/Recovery-Ausgaben
- GUI-Adapter
- kontrollierter Import der bestehenden SQLite-Tabellen

Der BACH-Fremd-Lock auf WORKSTATION-LG verhindert aktuell die Adapteränderung.
Das ist ein korrektes Gate, kein Grund für eine zweite Fork-Implementierung in
BACH.
