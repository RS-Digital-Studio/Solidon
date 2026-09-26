---
name: kernausgabe-ist-per-index-dicht
description: manifold3d gibt ein per Index dichtes Netz ohne doppelte Ecken aus; ein unbedingtes merge_vertices reißt es dort auf, wo Schalen sich berühren — Eiffelturm, Splitter des Piratenschiffs (RM-212, 26.09.2026)
metadata:
  type: project
---

Aus einem `Mesh64` nur mit Positionen gibt `manifold3d` die Ecken **geteilt**
zurück — ein Würfel kommt mit acht Ecken, dicht per Index (gemessen
26.09.2026). Doppelte Orte trägt die Ausgabe nur, wo zwei Schalen einander
berühren; `merge_vertices` legt dann vier Flächen an eine Kante, und das
Netz ist nicht mehr dicht. Am Eiffelturm (zwei Teile) und an den zwölf
Splittern, die `simplify(0,2)` am Piratenschiff stehen ließ, lehnte die
Boolesche Kette das grobe Netz deshalb ab, und jede Zahl im Bohrdialog
rechnete genau (16–54 s). Der Docstring von `mesh_ops._as_mesh` behauptete
das Gegenteil („an jeder scharfen Kante mehrere Eckpunkte").

**Why:** Die Messung „grob erstmals / danach" allein hätte es verdeckt: Die
Sonde meldet eine Zeit auch für eine grobe Vorschau, die still genau
rechnete. Erst die Spalte `grob=False` zeigte es, und erst das Netz Schale
für Schale die Ursache.

**How to apply:** Wer eine Kernausgabe zurück ins Netz holt, verschweißt nur,
wenn es dicht bleibt (`_as_mesh`, `boolean._tidied`), und besorgt eigene
C-Puffer (`fast_simplification` nimmt sonst nichts an). Wer eine grobe
Vorschau misst, liest `grob=` mit, nicht nur die Zeit. Siehe
[[obergrenze-ist-keine-zusicherung]].
