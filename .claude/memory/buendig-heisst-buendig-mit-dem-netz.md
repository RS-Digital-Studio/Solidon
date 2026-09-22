---
name: buendig-heisst-buendig-mit-dem-netz
description: "Ein Körper, der bündig auf eine gewölbte Fläche soll, liegt bündig mit ihrem Netz — auf den Facetten, an deren Grenzen geteilt —, nicht mit der Form, die das Netz meint; sonst bleiben Stufen von der Sehnenabweichung, und die nächste Einpassung findet die Form nicht mehr"
metadata:
  node_type: memory
  type: feedback
  originSessionId: f56e0441-974f-4150-ac77-8e36658dc05b
  modified: 2026-09-22T18:30:00.000Z
---

Gemessen am 22.09.2026 an `perceive/patterns.py`, Stopfen für Zellen um
einen Zylinder Ø 30 in 96 Facetten: Der Stopfen wurde auf den **Kreis**
gebogen (Radius 15, fein geteilt). Der Mantel liegt aber auf den
**Facetten**, und die hängen zwischen zwei Ecken 0,008 mm unter dem Kreis.
Nach der Vereinigung stand der Stopfen dort um so viel über dem Mantel; die
Stufe am Rand hatte Wände quer zur Achse — hundert Dreiecke, 0,7 mm² —, und
`fit_cylinder` lehnte den ganzen Mantel ab (`max |n·axis| > 0,1`): aus einem
Stift wurden 135 Flächen. Auf die Facetten gelegt und an jeder
Facettengrenze geteilt (`Frame.facets`, `_split_along` über
`split_by_plane` des exakten Kerns), war der Mantel danach wieder ein Stift,
das Volumen bis auf 10⁻³ Prozent zurück.

Drei Fallen darunter, alle am selben Tag: Ein Dreieck, das eine
Facettengrenze überspannt, liegt mit seinen Ecken auf zwei Ebenen und mit
seiner Mitte unter beiden — feiner teilen hilft nicht, nur schneiden. Eine
Verfeinerung mit `trimesh.remesh.subdivide_to_size` reißt an der Naht
zwischen verschieden oft geteilten Flächen; der exakte Kern teilt konform.
Und `merge_vertices` nach dem Kern verschweißt zwei Schalen, die sich in
einem Punkt berühren, zu einem Körper mit einer Kante an drei Dreiecken
(`mesh_ops.refined` verschweißt deshalb nicht).

**Why:** Eine Boolesche Rechnung kennt keine Formen, nur Dreiecke. „Bündig"
ist eine Aussage über zwei Netze, und sie stimmt nur, wenn beide dieselben
Ebenen an denselben Stellen haben. Ein Körper, der der Form folgt, ist
gegenüber dem Netz, das die Form nur meint, überall ein wenig daneben — und
„ein wenig" reicht für eine Stufe, an der die nächste Frage scheitert.

**How to apply:** Wer einen Körper auf eine gekrümmte Netzfläche legt, liest
zuerst deren Facetten (Normalenwinkel und Ebenenabstand je Facette) und
baut den Körper aus denselben Ebenen, geteilt an denselben Grenzen. Danach
messen, was die nächste Stufe sieht — hier die Zylindereinpassung —, nicht
nur das Volumen: Das war exakt, und der Mantel trotzdem keiner mehr. Siehe
[[naht-nicht-schneiden-sondern-waehlen]] für die andere Seite derselben
Rechnung.
