# Agententermine im Kalender

Stand: 04.11.2026.

## SOLL

Kalender und Agentenverwaltung bearbeiten dieselben einmaligen Termine mit
stabiler ID und Versionsprüfung. Wiederkehrende und persönliche Termine bleiben
fachlich unterscheidbar. Es entsteht keine zweite editierbare Terminquelle.

## IST

`ellmos_scheduler.calendar.AgentCalendar` projiziert ausschließlich native
`AgentTriggers`-Definitionen vom Typ `once`. Anlage, Zeitänderung, Aktivierung
und Löschung delegieren an denselben Store und CAS-Vertrag. Änderungen aus der
Agentenverwaltung sind bei der nächsten Kalenderabfrage sichtbar und umgekehrt.
Löschung erzeugt denselben Tombstone und erhält die Laufhistorie. Reads legen
keine Datenbank an und migrieren nichts. Eine Terminzeit benötigt eine Zeitzone.

Die Python-Projektion hat noch keinen eigenen CLI-, HTTP- oder GUI-Adapter.
Kalenderanzeige, komfortable Bearbeitung und tatsächliche Agentenausführung sind
damit weiterhin offen. Kein Produktivstart oder Nutzer-Endabnahme behauptet.
