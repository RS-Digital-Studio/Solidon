---
name: exakte-differenz-scheitert-still
description: "OCCT-Differenz kann lagenabhängig still scheitern — gültig laut BRepCheck, aber Volumen des Ausgangs und undichter Zwilling; am Zwilling prüfen."
metadata:
  type: project
---

`BRepAlgoAPI_Cut` meldet nicht immer, wenn es nicht schneiden konnte. An
`pegboard-gs-100-v2.step` (BSpline-Rundung hinter der unteren Schraubbohrung)
kam die Kette, um 1,5 mm nach oben versetzt, mit genau dem Volumen des
gefüllten Körpers zurück: 57 statt 50 Flächen, `BRepCheck_Analyzer` gültig,
`is_closed` wahr — nur der Netz-Zwilling war undicht (+5 176 mm³). Körper
minus Werkzeug ergab dort „leer", die Schnittmenge null. Unschärfewert
(`SetFuzzyValue` 1e-5, 1e-4) half nicht; ein anderer Mündungsüberstand schon
(0,02 mm scheitert, 0,04/0,06 hält, 0,1 scheitert wieder) — die Lage, nicht
das Werkzeug.

**Why:** Ohne Prüfung liefert die Handlung einen kaputten Körper, und alle
Merkmale gelten als verloren. Einzeln nachgestellt sah es zuerst zufällig aus,
weil die Probe für diese Bohrung eine andere Querachse wählte (Z statt X, eine
Achse `(1,2e-16 | 1 | 0)` und `argmin`).

**How to apply:** Eine exakte Differenz, deren Ergebnis weiterverwendet wird,
am dichten Zwilling prüfen (`as_mesh_data(result).is_watertight`) und mit
anderem Überstand wiederholen — `prepare_ops._exact_chain_cut_holding`. Bei
einer Sonde, die „zufällig" anders rechnet, zuerst die Eingaben vergleichen
(Achse, Richtung), bevor man Zustand oder Merker verdächtigt.
