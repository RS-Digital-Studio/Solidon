---
name: changelog-vor-dem-versionssprung
description: Der Changelog-Abschnitt der nächsten Fassung entsteht vor der Versionserhöhung und nimmt auch noch unfertige Arbeit auf.
metadata: 
  node_type: memory
  type: feedback
  originSessionId: f1ba3a31-cff7-4f79-875f-3590b120e196
  modified: 2026-09-09T21:30:26.442Z
---

Robert lässt den Changelog-Abschnitt einer Fassung **vor** dem Versionssprung
schreiben — mit allem seit dem letzten Tag, „auch was gerade noch in Arbeit
ist, bis zur Veröffentlichung ist es fertig" (09.09.2026, für 0.4.0).

**Warum:** Die Auswahl der Punkte ist die eigentliche Arbeit und braucht den
Überblick über alle Commits seit dem letzten Tag; sie am Bautag nachzuholen
heißt, sie unter Zeitdruck zu machen. Was bis zur Veröffentlichung doch nicht
steht, wird vorher gestrichen — das ist billiger als ein fehlender Punkt.

**How to apply:** `git log <letzter tag>..HEAD` mit Body lesen, dazu den
ungestageten Baum (dort liegt die unfertige Arbeit). Die Version **nicht**
anheben — das macht `bump_version.py` beim Bau, und `website/version.json`
sowie die Pakete stehen bis dahin auf der alten. Beim Abliefern die Punkte
nennen, die noch offene Arbeit beschreiben, damit Robert sie streichen kann.

Der Verlaufstest kannte den Fall vorher nicht: `entries[0].version ==
APP_VERSION` galt nur, solange der Abschnitt mit der Versionsnummer entstand.
Geprüft wird jetzt die Reihenfolge. Siehe [[app-zeigt-drei-changelogs]].
