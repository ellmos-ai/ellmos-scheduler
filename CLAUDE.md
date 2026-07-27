---
name: ellmos-scheduler
profile: python-module
created: 2026-07-27
---

# Projekt

Eigenständiger, plattformneutraler Scheduler für ellmos-Stacks und das modulare
Wonderland/Riverfall-Zielbild. BACH konsumiert dieses Modul später über einen
Adapter; BACH-internes Scheduler-Verhalten ist nur Migrationsquelle.

## Regeln

- Der Scheduler entscheidet **wann**, nicht **welches LLM oder welcher Workflow**.
- Provider-Ausführung wird über registrierte Executor-Adapter eingebunden.
- SQLite-Zustand gehört dem Modul und liegt außerhalb des Quellbaums.
- Claims verhindern Doppelmutation, sind aber kein Erfolgsbeleg; Erfolg benötigt
  einen abgeschlossenen Run-Record.
- Keine Shell-Strings im eingebauten Command-Executor; nur `argv`-Listen.
- BACH-spezifische Imports gehören ausschließlich in einen Adapter.
