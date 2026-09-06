---
name: geteilte-umgebung-fragt-das-schloss
description: "Vor einem Eingriff in F:\\3D Druck\\.venv (Tausch, Paketwechsel) zählt gate_lock.py status und die Ansage der anderen Sitzungen — die Prozessliste ist zwischen zwei Fensterdateien eines Torlaufs leer und sagt nichts."
metadata:
  type: feedback
  originSessionId: f07e3f31-b0f2-4cae-b55c-218ecd11e007
  modified: 2026-09-06T14:41:14.102Z
---

Am 06.09.2026 um 15:19 tauschte ich `F:\3D Druck\.venv` (3.13) gegen die
neue 3.14.7-Umgebung, nachdem die Prozessliste null Prozesse aus `.venv`
gezeigt hatte. c4s Torlauf lief aber gerade — die geteilte Suite fährt jede
Fensterdatei als eigenen Prozess, und zwischen zwei Dateien hält niemand die
Umgebung. Die zweite Hälfte ihres Laufs fuhr damit auf einer anderen
Umgebung als die erste; c4 verwarf den Lauf und fuhr ihn neu.

**Why:** Die Prozessliste beantwortet „hält gerade jemand eine Datei?", nicht
„fährt gerade jemand einen Lauf?". Ein Torlauf unter `gate_lock.py` ist als
Schloss sichtbar, nicht als Prozess; und c4 hatte ausdrücklich um ein
„fertig" gebeten, das ich beim Tausch nicht mehr abgewartet habe.

**How to apply:** Vor einem Tausch, einem `pip install` oder einem Löschen in
der geteilten `.venv`: erstens `python tools/gate_lock.py status` — ist das
Tor belegt, warten; zweitens die Sitzungen auf dem Brett fragen und deren
„fertig" abwarten; erst dann die Prozessliste als letzte Kontrolle. Dieselbe
Regel für jede geteilte Ressource: Kataloge, `website/dl`, den Hauptbaum.
Verwandt: [[speicherzusage-zu-dritt]], [[gemessene-frage-ist-nicht-die-gestellte]].
