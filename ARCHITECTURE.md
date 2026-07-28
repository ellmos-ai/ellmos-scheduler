# Architektur

## Schichten

1. `schedules.py`: plattformneutrale Due-Berechnung in UTC.
2. `store.py`: SQLite-Schema, Jobs, Controls, Claims und Run-Historie.
3. `executors.py`: isolierbare Registry, schmales Executor-Protokoll und sichere
   Built-ins.
4. `adapters.py`: lazy geladene COMA- und argv-basierte MarbleRun-Anbindung.
5. `bach.py`: read-only Legacy-Import und BACH-Consumer-API.
6. `service.py`: Tick-/Lease-/Ausführungsschleife mit injizierbarer Registry.
7. `cli.py`: Operatoroberfläche.

Der Scheduler-Kern kennt weder die BACH-Implementierung noch einen
LLM-Anbieter. Integrationen registrieren einen Executor in einer
`ExecutorRegistry`. Die prozessweite `register_executor(...)`-Funktion bleibt
als Kompatibilitätsweg bestehen, überschreibt Namen aber nur noch mit dem
expliziten Argument `replace=True`.

## Zustandsmodell

`scheduled -> claimed -> running -> succeeded|failed|timed_out`

Ein beim nächsten Tick abgelaufener `claimed`- oder `running`-Datensatz wird
`abandoned`. Das betreffende Fenster kann mit einer neuen Recovery-Run-ID
erneut beansprucht werden; die Historie bleibt erhalten.

## Komposition

Wonderland/Riverfall kann den Scheduler als Capability
`automation.schedule` auswählen. BACH 1.x kann den exportierten
`BachSchedulerAdapter` hinter seiner Provider-Seam verwenden. Der
Legacy-Importer öffnet die BACH-Datenbank ausschließlich mit SQLite
`mode=ro`; nur der Ziel-Store ist schreibbar. Nach dem noch ausstehenden
Parallelvergleich soll dadurch genau eine schreibbare Scheduler-Implementierung
existieren.
