---
name: pruefstand-misst-seine-nachstellung
description: "Ein Prüfstand, der eine alte Bauart nachstellt statt sie zu benutzen, misst seine eigene Nachstellung — fünf von fünf rot, und die Ursache war das Messwerkzeug."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: e44e7ebf-a72f-4543-a02a-0efbcc35b48d
  modified: 2026-09-03T16:52:20.405Z
---

Wer prüfen will, ob eine Änderung einen Fehler behoben hat, stellt die alte
Bauart gern nach, statt sie zu holen. Die Nachstellung sitzt dann an einer
anderen Stelle im Ablauf als das Original — und misst etwas anderes.

Am 03.09.2026 sah es so aus, als fiele in Solidon jedes eingestellte
Navigationsschema beim Start auf `slicer` zurück: fünf von fünf rot, ein
plausibler Kundenfehler seit Monaten. Die alte Bauart hatte
`set_navigation("slicer")` **im Plotter-Aufbau**; meine Nachstellung rief
dieselbe Zeile **nach** `_apply_settings`. Der echte Aufbau läuft davor, also
überschrieb er nichts. Es gab keinen Fehler.

**Why:** Ein erfundener Befund ist teurer als ein übersehener — die nächste
Sitzung glaubt ihn und sucht an der falschen Stelle. Und er ist schwer zu
entdecken, weil ein rotes Ergebnis wie ein Fund aussieht und nicht wie eine
Frage.

**How to apply:** Bevor ein roter Prüfstand ein Befund wird, die
**Reihenfolge** messen, nicht annehmen — hier: steht der Plotter schon nach
dem Konstruktor, und läuft `_apply_settings` davor oder danach? Drei Zeilen
Ausgabe entschieden es. Wo möglich die alte Bauart **holen** statt sie
nachzubauen (eigener Worktree auf dem Commit davor, [[sonde-im-geteilten-baum]]).
Und: Ein Prüfstand, der den Weg des Kunden gehen soll, muss den ganzen Weg
gehen — hier fehlte `window._apply_settings()`, das `app.py` gleich nach dem
Fensterbau ruft. Ohne diese eine Zeile misst er einen Weg, den niemand geht
([[pruefstand-geht-den-weg-der-oberflaeche]]).

Verwandt: [[gegenprobe-bei-geaenderter-bauart]],
[[eigener-messfehler-widerlegt-den-befund-nicht]], [[sondenbau]].
