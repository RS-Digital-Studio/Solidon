---
name: csgraph-antwortet-in-int32
description: scipy.sparse.csgraph gibt Reihenfolge, Vorgänger und Teilnummern als int32 zurück — eine Kantennummer a·n+b daraus läuft still über
metadata:
  type: project
---

`breadth_first_order`, `connected_components` und ihre Geschwister in
`scipy.sparse.csgraph` liefern **`int32`**, auch wenn die Eingabe `int64` war.
Mit NumPy 2 übernimmt ein Python-`int` im Ausdruck den Typ des Felds (NEP 50):
`np.minimum(parent, node) * (count + 1)` rechnet in 32 Bit und läuft ab rund
46 000 Dreiecken still über. Gefunden am 24.09.2026 in
`repair.wind_consistently` an der Gähnenden Katze (452 316 Dreiecke): Die
Kantennummern der Baumkanten trafen falsche Paare, und die Wicklung blieb
uneinheitlich, während alle kleinen Proben bitgleich mit trimesh waren.

**Why:** Der Fehler zeigt sich erst ab einer Netzgröße, die in Kerntests nicht
vorkommt; kleine Gegenproben sind grün.

**How to apply:** Was aus `csgraph` kommt und in eine Rechnung mit Nummern
geht, sofort `np.asarray(..., dtype=np.int64)`. Eine Gegenprobe gegen die
alte Umsetzung gehört auch an ein großes echtes Netz (Korpus
`F:\3D Dateien`), nicht nur an erzeugte Körper. Siehe
[[verifikation-an-echten-modellen]].
