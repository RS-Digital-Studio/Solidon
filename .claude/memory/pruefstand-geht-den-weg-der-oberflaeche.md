---
name: pruefstand-geht-den-weg-der-oberflaeche
description: "Wo ein Prüfstand den Kern direkt ruft statt über den Weg der Oberfläche, baut er einen Zustand, den es im Betrieb nicht gibt — vier Fehlbefunde an einem Tag."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 4e2b249b-1d42-4020-bb0e-bdcf350ef625
  modified: 2026-08-30T05:50:08.091Z
---

Am 30.08.2026 vier Mal in einer Sitzung, jedes Mal beinahe als Befund
gemeldet:

| Prüfstand rief | übersprungen | falscher Schluss |
|---|---|---|
| `slice_model` direkt | die Profilprüfung des Dialogs | „ElegooSlicer nimmt keinen Auftrag an" |
| `readiness()` ohne Argument | `_workflow()`, das Text und Bild trennt | „die Bereitschaft prüft den falschen Ablauf" |
| `Session()` ohne `load_operations()` | den Registeraufbau | „das Beispielprojekt hat null Objekte" |
| `Project()` statt `new_project()` | das Dokument | Abbruch vor der ersten Messung |

Alle vier sahen nach einem Anwendungsfehler aus. Alle vier waren ein
Prüfstand, der einen Schritt ausließ, den die Anwendung macht.

**Why:** Der Kern ist absichtlich freizügig — er nimmt entgegen, was man ihm
gibt. Die Vorprüfungen leben in der Oberfläche, weil dort die Bedienung
entscheidet. Wer den Kern direkt ruft, umgeht sie und misst eine Lage, die
kein Klick herstellt. Zweimal stand die Antwort sogar als Kommentar an der
übersprungenen Stelle: „Der Lauf lief bis dahin los und endete in ‚Der Slicer
hat keine Druckdatei geschrieben' — ein Satz über das Ende, nicht über die
Ursache."

**How to apply:** Der Prüfstand geht denselben Weg wie der Klick — oder er
begründet, warum nicht. Vor jedem Befund die Frage: *Was tut die Oberfläche
vor diesem Aufruf?* Ein `grep` nach dem Funktionsnamen in `app/ui/` beantwortet
sie in Sekunden und zeigt die Vorprüfung, die man gerade übersprungen hat.

Und es gilt für die **Suite** genauso: Ein Test, der ein Widget ohne das
Anwendungs-Stylesheet baut, misst eine Lage, die es beim Kunden nie gibt —
derselbe Fehler, andere Richtung.

Die Schwester dazu ist [[testprojekt-trifft-den-fall-nicht]]: Dort fehlen die
Daten, die die Anwendung erzeugt; hier fehlen die Schritte, die sie geht.
Siehe auch [[messwerkzeug-misst-sich-selbst]].
