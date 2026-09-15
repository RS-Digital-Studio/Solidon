---
name: downloads-ordner-als-3mf-korpus
description: "Sechzehn echte 3MF aus MakerWorld und vom Elegoo-Slicer liegen in C:\\Users\\rober\\Downloads — der Messkorpus für den 3MF-Leser, wenn die Kundendatei fehlt"
metadata: 
  node_type: memory
  type: reference
  originSessionId: 7293a802-9169-410a-a096-ea49bc8955e1
  modified: 2026-09-14T15:37:45.195Z
---

`C:\Users\rober\Downloads\*.3mf` — am 14.09.2026 sechzehn Dateien aus
MakerWorld (Bambu Studio) und vom Elegoo-Slicer, darunter `chufang.3mf`
(5,5 Mio Dreiecke, 28 Modelldateien, 744 429 Bemalungscodes mit echter
Teilflächenbemalung) und drei Elegoo-Dateien mit `<slic3rpe:shape …/>` ohne
Namensraum. Nicht im Repository, nicht in `tests/data/`.

**Am 15.09.2026 gegen 05:42 waren alle sechzehn aus dem Ordner verschwunden**
— mitten in einer Sitzung, in der der Vorher/Nachher-Vergleich der Erkennung
eine halbe Stunde vorher noch über alle lief. Wer den Korpus braucht, prüft
zuerst, ob er noch da ist, und bittet Robert sonst um die Dateien (MakerWorld
gibt sie nur angemeldet heraus).

**Why:** Ein Kundenbericht ohne Anhang (S-20260914-e4b6d7) nennt nur die
Fehlerzeile; MakerWorld gibt die Datei nur angemeldet heraus. Der Ordner hat
in einer Minute vier von sechzehn Dateien als abgewiesen gezeigt und beide
Ursachen geliefert — der Bericht allein hätte keine davon genannt.

**How to apply:** Vor jeder Änderung am 3MF-Leser alle Dateien des Ordners
durch `threemf.read_objects(payload, findings)` und `count_objects` schicken
(Skriptmuster: `scratchpad/probe_3mf3.py` dieser Sitzung — Körperzahl gegen
Zählweg, dicht, mehrfarbig, Befunde je Datei). Nach der Änderung dasselbe.
Siehe [[testprojekt-trifft-den-fall-nicht]] — eine synthetische Box prüft die
Regel, der Ordner prüft die Dateien, die Kunden wirklich haben.
