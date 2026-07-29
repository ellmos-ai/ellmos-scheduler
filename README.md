# ellmos Scheduler

Eigenständiger Zeitgeber und Run-Recorder für modulare ellmos-Stacks. Das Modul
ist bewusst **außerhalb von BACH** angelegt. BACH, Wonderland/Riverfall,
Desktop-Automationen, COMA, MarbleRun/llmauto und swarm-ai können es über
schmale Adapter konsumieren.

Status: `0.1.0` (MVP, 2026-07-27).

## Verantwortungsgrenze

- ellmos Scheduler: Zeitplan, Due-Ermittlung, Lease/Claim, deduplizierende
  `run_id`, Pause/Resume, Run-Historie und Heartbeat.
- COMA: Provider-Prozess starten und Ergebnis abholen.
- MarbleRun/llmauto: Ketten ausführen.
- swarm-ai: Agentenmuster ausführen.
- `.SYNC/automation-exchange`: systemübergreifender Aufgaben-,
  Abdeckungs- und Vertretungsvertrag.
- BACH: Consumer über `BachSchedulerAdapter`, nicht Eigentümer der
  Scheduler-Logik.

## Unterstützte Zeitpläne

```json
{"kind": "interval", "seconds": 3600}
{"kind": "daily", "time": "04:00", "timezone": "Europe/Berlin"}
{"kind": "cron", "expression": "*/15 * * * *", "timezone": "Europe/Berlin"}
```

Cron unterstützt fünf Felder, `*`, Listen, Bereiche und Schritte.

## Schnellstart

```powershell
python -m pip install -e ".[dev]"
ellmos-scheduler --db "$env:LOCALAPPDATA\ellmos\scheduler.db" init
ellmos-scheduler --db "$env:LOCALAPPDATA\ellmos\scheduler.db" add `
  --id sync.daily.cross-system `
  --schedule '{"kind":"daily","time":"09:00","timezone":"Europe/Berlin"}' `
  --executor command `
  --payload '{"argv":["python","C:\\path\\to\\task.py"],"cwd":"C:\\Users\\lukas"}'
ellmos-scheduler --db "$env:LOCALAPPDATA\ellmos\scheduler.db" status --json
ellmos-scheduler --db "$env:LOCALAPPDATA\ellmos\scheduler.db" serve
```

`command` und der gleichwertige Name `subprocess` akzeptieren ausschließlich
eine `argv`-Liste und starten ohne Shell. Zusätzlich sind `noop`, `coma` und
`marblerun` registriert:

```json
{"executor":"coma","payload":{"provider":"codex","prompt":"Prüfe den Build","cwd":"C:\\repo"}}
{"executor":"marblerun","payload":{"chain":"review-chain","background":false}}
```

COMA wird erst beim tatsächlichen Lauf importiert. Der MarbleRun-Adapter startet
die öffentliche CLI als sichere argv-Liste und respektiert den
Scheduler-Timeout. Die jeweiligen Pakete müssen für diese Adapter installiert
sein. Codex-Custom-Prompts und App-Aufgaben nicht durch einen unbelegten
`codex exec /command`-Aufruf simulieren; der jeweilige native Einstieg muss
separat live verifiziert sein.

Eigene Integrationen erhalten eine isolierte Registry:

```python
from ellmos_scheduler import ExecutionResult, ExecutorRegistry, SchedulerService

registry = ExecutorRegistry()
registry.register(
    "my-adapter",
    lambda payload, timeout: ExecutionResult("succeeded", output="ok"),
)
service = SchedulerService(store, registry=registry)
```

Eine doppelte Registrierung schlägt fehl. Absichtliches Ersetzen erfordert
`replace=True`; dadurch können parallel laufende Scheduler-Instanzen getrennte
Adaptermengen verwenden.

## Sicherheits- und Verfügbarkeitsmodell

- Fällige Läufe erhalten atomar eine deterministische `run_id`.
- Eine Lease verhindert einen zweiten Writer für dasselbe Jobfenster.
- Ein Claim gilt nicht als Erfolg; erst der abgeschlossene Run-Record zählt.
- Ausgelaufene Claims werden als `abandoned` markiert und dürfen erneut geplant
  werden.
- Globales und jobbezogenes Pause/Resume bleibt getrennt von `enabled`.
- Status liefert `last_tick_at`, Jobzahlen und Runzahlen maschinenlesbar.

## Migration aus BACH

Siehe [MIGRATION_FROM_BACH.md](MIGRATION_FROM_BACH.md). Der bestehende
`BACH/system/hub/scheduler.py` bleibt bis zum Betriebsvergleich als
Legacy-Quelle in Betrieb. Ein Dry-Run zeigt übertragbare und bewusst
übersprungene Jobs, ohne die Quell- oder Zieldatenbank anzulegen bzw. zu ändern:

```powershell
ellmos-scheduler --db C:\state\scheduler.db import-bach `
  --source-db C:\BACH\system\data\bach.db `
  --bach-root C:\BACH `
  --timezone Europe/Berlin `
  --dry-run --json
```

Der Python-Einstieg `create_bach_adapter(state_db)` liefert die schmale
Consumer-API, die BACH hinter seiner `scheduler_provider`-Seam verwenden kann.

## Bundles und Partner

`ellmos-scheduler` bleibt ein einzeln nutzbarer Zeitgeber. In der
V4-Komposition ist es ein erforderlicher Zeit- und Run-Recorder im
`ellmos-automation-control-bundle`; es entscheidet weiterhin nur **wann**
etwas fällig ist, nicht welcher Provider, Workflow oder Agent ausführt.

Direkte Bundlepartner sind die erforderliche Automationsregistry und
Runtime-Readback-Komponente; die Cloud-Control-Schicht ist empfohlen. Für das
Profil `self-healing` ist `automation-self-care` der erforderliche
Skillpartner: Er wird deklarativ aufgelöst und kann bezogen werden, aktiviert
oder verändert aber ohne die vorgesehenen Freigabe-, Native-Readback- und
Rollback-Gates keine Automatisierung.

Die verbindliche Mitgliedschaft, Versionen, Profile und privaten
Zusammensetzungsrezepte stehen ausschließlich im Bundle-Manifest. Diese
Übersicht ist öffentlich und dient nur der Partner-Discovery.
