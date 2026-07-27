# Architektur

## Schichten

1. `schedules.py`: plattformneutrale Due-Berechnung in UTC.
2. `store.py`: SQLite-Schema, Jobs, Controls, Claims und Run-Historie.
3. `executors.py`: schmales Executor-Protokoll und sichere Built-ins.
4. `service.py`: Tick-/Lease-/Ausführungsschleife.
5. `cli.py`: Operatoroberfläche.

Der Kern kennt weder BACH noch einen LLM-Anbieter. Integrationen registrieren
einen Executor mit `register_executor(name, callable)`.

## Zustandsmodell

`scheduled -> claimed -> running -> succeeded|failed|timed_out`

Ein beim nächsten Tick abgelaufener `claimed`- oder `running`-Datensatz wird
`abandoned`. Das betreffende Fenster kann mit einer neuen Recovery-Run-ID
erneut beansprucht werden; die Historie bleibt erhalten.

## Komposition

Wonderland/Riverfall kann den Scheduler als Capability
`automation.schedule` auswählen. BACH 1.x erhält später einen Adapter, der
seine CLI auf dieselbe API abbildet. Dadurch existiert nach der Migration nur
eine schreibbare Scheduler-Implementierung.
