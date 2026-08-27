---
name: fremde-zwischenstaende-verfaelschen-messungen
description: "Ein Tor misst nicht den eigenen Stand, sondern den Arbeitsbaum zum Zeitpunkt des Laufs — bei einem roten Lauf zuerst den Zeitstempel der genannten Datei lesen, nicht den eigenen Code."
metadata: 
  node_type: memory
  type: project
  originSessionId: 799ace2e-c6ff-4779-a0eb-abab386cc893
  modified: 2026-08-22T23:05:53.906Z
---

In der Nacht zum 23.08.2026 haben vier Sitzungen in `F:\3D Druck` parallel
gearbeitet. Drei Torläufe sind an fremden Zwischenständen gestorben, jeder mit
einer anderen Gestalt — und keiner davon fällt unter die Commit-Regeln aus
[[parallele-sitzungen-solidon3d]], denn hier ging es nie um einen Commit.

**Erstens, im Prüfling.** 27 rote Tests über zwölf Dateien, alle mit derselben
Zeile: `ImportError: cannot import name 'pair_radii'`. `maps.py` trug den
Import seit 20:36, `features.py` bekam die Funktion um 00:02:47 — dazwischen
war der Baum nicht importierbar, und ein Torlauf fiel genau hinein. (Ursache
war ein Aufräum-Skript, das beim Entfernen zweier verwaister Konstanten fünf
Funktionen mitgelöscht hatte.)

**Zweitens, im Prüfwerkzeug.** Ein Lauf starb mit einem Syntaxfehler in
`suite-getrennt.sh:123` — an einer Zeile, die dort völlig in Ordnung stand
(`bash -n` sagte „ok"). **Bash liest ein Skript zeilenweise nach und merkt
sich die Byte-Position.** Wird die Datei während des Laufs geändert, liest der
laufende Prozess an der alten Position in der neuen Datei weiter und landet
mitten in einem Wort. Behoben, indem das Skript sich beim Start in den
Temp-Ordner kopiert und die Kopie fährt.

**Drittens, in der Prüfkonfiguration.** `mypy <einzeldatei>` meldete 14 Fehler,
`mypy` ohne Argument (wie im Tor) meldete null über 214 Dateien. Der Aufruf mit
Dateinamen umgeht Teile der Projektkonfiguration.

**Warum:** Ein privater Git-Index schützt vor fremden *Commits*. Er schützt
nicht davor, dass ein fremder halbfertiger Zustand in den eigenen *Lauf* gerät
— und das ist der Fall, der Stunden kostet, weil die Fehlermeldung auf den
eigenen Code zeigt.

**How to apply:** Bei einem roten Lauf, dessen Datei nicht in `git status`
steht, zuerst `git status` und den **Zeitstempel** der genannten Datei lesen,
dann den Code. Nennen viele Testdateien dieselbe Zeile, ist die Frage nicht
„was habe ich kaputtgemacht", sondern „wann wurde diese Datei geschrieben" —
das hat hier zehn Sekunden gekostet statt einer Stunde. Vor einer Änderung am
Prüfwerkzeug ins Schloss sehen (`gate_lock.py status`). Und beim Nachmessen
den Tor-Aufruf benutzen, nicht die bequeme Einzeldatei-Variante.
