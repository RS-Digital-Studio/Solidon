---
name: generator-netz-ist-ein-fleck
description: "Ein glattes Generatornetz (TripoSG) ist für die 30-Grad-Trennung ein einziger Riesenfleck; der Freiformkorpus ist verrauscht und deckt das nicht — und jede Prüfung je Kandidatenmenge, die über den Fleck läuft, wird dort quadratisch."
metadata: 
  node_type: memory
  type: project
  modified: 2026-09-20T19:28:37.710Z
  originSessionId: 59b5a676-368b-4813-8176-ed848d55f183
---

**Was passiert ist (20.09.2026):** Roberts Drache aus ComfyUI/TripoSG
(`image_00001_.glb`, 325 244 Dreiecke, wasserdicht, eine Komponente) hing in
Solidon minutenlang bei „Merkmale erkennen“ — gemessen 482 s für null
Merkmale. Die Kerbenschließung vom 17.09. (`_notch_faces`/`_closing_set`)
lief je Kandidatenmenge noch einmal über den ganzen Fleck und alle Paare von
`face_adjacency`; der Drache ist bei der 30-Grad-Trennung **ein** Fleck mit
307 063 Dreiecken und 65 Kandidaten, also 2 145 Durchgänge à 80 ms.

**Warum der Korpus es nicht sah:** Die Freiform-Leistungsfälle (RM-132) sind
**verrauscht** — 120 610 Flecken an 200 000 Dreiecken, jeder klein. Ein
Marching-Cubes-Netz aus einem Generator ist **glatt**: kaum ein Knick über
30 Grad, 94 Prozent der Dreiecke in einem Fleck. Was je Fleck linear ist,
ist an diesem Körper das ganze Netz, und was je Kandidatenmenge über den
Fleck läuft, ist quadratisch. Dieselbe Erkennung kostete am verrauschten
Körper 1,5 s.

**How to apply:**
- Eine Prüfung je Kandidatenmenge (Kombinationen!) darf nur an der Menge
  selbst messen — Rand und Nachbarn einmal je Fleck zählen, dann O(1) je
  Menge (`_rim_of`, `_closes`, `_neighbour_index` in `perceive/features.py`).
- Wer Leistung an „einer Freiform“ misst, braucht **beide** Gestalten: die
  verrauschte (viele kleine Flecken) und die glatte (ein Riesenfleck aus
  einem Generator). Der Rest des Drachen (151 s unter Fremdlast: 27 690
  Splitstücke durch vier Einpassungen, `_surface_support` je Knoten in
  Python) steht als RM-193 im Register.
- Die Datei liegt bei Robert in `Downloads/image_00001_.glb`; als Meter
  gelesen ist sie 1,9 m hoch, als cm 190 mm — beide Größen messen.

Siehe [[lehre-schuetzt-nur-ihre-eigene-gestalt]] und
[[leistungstests-fremdlast]].
