---
name: unbelegter-rand-ist-nicht-scharf
description: "Eine Regel „jede Naht ist scharf“ über face_adjacency prüft nur die Nähte, die das Netz kennt — an einer STL mit T-Stößen hat ein Streifen fast keine Nachbarn und besteht die Regel leer; die Kantenzahl gegenzählen"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: f56e0441-974f-4150-ac77-8e36658dc05b
  modified: 2026-09-20T16:30:20.119Z
---

Am 20.09.2026 machte `_facets_standing_apart` (P1.5, kleine Flächen mit
scharfen Rändern) an `plate_countersunk.stl` jeden zweiten Bohrungsstreifen
zur Fläche: 30 „Flächen“ zu 1,9 mm² auf einem Mantel, 36 Wände statt 4 in
der Formschräge. Die Regel „alle Nähte zu fremden Dreiecken sind scharf“
war über `body.face_adjacency` erfüllt — die STL schreibt die Streifen mit
T-Stößen, die Naht zum Nachbarstreifen existiert für trimesh gar nicht, und
die zwei Nähte, die es gab (Boden, Senkung), waren scharf.

**Why:** „Für alle Nähte gilt X“ ist über einer Nachbarschaftsliste dieselbe
Falle wie ein Verbotstest über eine leere Menge ([[waechter-sieht-nur-das-getane]],
[[any-ueber-einen-flicken-misst-den-rand]]): Was die Liste nicht enthält,
verstößt nie. Am welded Netz aus dem exakten Kern fällt das nicht auf; am
Kundenkorpus sofort.

**How to apply:** Wer eine Bedingung über alle Ränder eines Flecks prüft,
zählt die Ränder gegen: `3·n` Kanten je `n` Dreiecke, jede innere
Nachbarschaft deckt zwei, jede äußere eine — bleibt ein Rest, ist der Rand
unbelegt und die Bedingung nicht erfüllt. Und den Gegenfall an einer
Korpus-STL messen, nicht nur an einem tessellierten exakten Körper.
