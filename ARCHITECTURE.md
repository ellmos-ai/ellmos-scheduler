# Architektur

## Schichten

1. `schedules.py`: plattformneutrale Due-Berechnung in UTC.
2. `store.py`: SQLite-Schema, Jobs, Controls, Claims und Run-Historie.
3. `authorities.py`: providerneutrale Registry, validierter Quellvertrag und
   read-only Hash-/Readback-Auflösung vor jeder Ausführung.
4. `executors.py`: isolierbare Registry, schmales Executor-Protokoll und sichere
   Built-ins.
5. `adapters.py`: lazy geladene COMA- und argv-basierte MarbleRun-Anbindung.
6. `bach.py`: read-only Legacy-Import und BACH-Consumer-API.
7. `service.py`: Tick-/Lease-/Authority-/Ausführungsschleife mit injizierbaren
   Registries.
8. `cli.py`: Operatoroberfläche.

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

## Autoritätsauflösung

Jobs speichern nur explizite, secretfreie Quellmetadaten. Resolver müssen dafür
eine Source-Allowlist/Validierung registrieren; unbekannte Felder, Raw-Inhalte,
credential-artige Werte und unbekannte Resolver werden bereits vor dem
Job-Write abgewiesen. Der Service claimt den Run, löst alle Quellen read-only
auf und persistiert den Beleg noch im Zustand `claimed`. Erst danach darf der
Run zu `running` wechseln und der Executor starten. Der Beleg enthält
Authority-ID/-Typ, Requirement, Resolver, Herkunft, SHA-256,
Readback-SHA-256, Bytezahl und code-only Status/Fehler. Raw-Inhalte werden weder
an den Executor übergeben noch in SQLite gespeichert.

Ein nicht aufgelöstes `required`-Element beendet den Run in der Phase
`authority-resolution`; ein typisiertes `optional`-Element bleibt im Beleg
sichtbar und blockiert nicht. Der Authority-Set-Hash ist über Läufe stabil,
solange Status, Herkunft und Bytes gleich bleiben. Die einzelne `receipt_id`
bindet denselben Beleg zusätzlich an die konkrete `run_id`.

Alte Datenbanken werden additiv migriert und alte Jobs erhalten `[]`. Für
produktive, vollständig migrierte Laufzeiten erzwingen `tick
--require-authorities` und `serve --require-authorities`, dass kein Job ohne
explizite Autoritätskonfiguration startet. Konkrete kanonische Authority-IDs
werden nicht vom Scheduler erfunden; sie müssen durch den zuständigen Owner
konfiguriert werden.
