---
name: natives-volumen-mit-bezugspunkt
description: "Volumen eines exakten Körpers nativ je Fläche mit Hüllmitte als Bezugspunkt — der UV-Weg in Python kostete Sekunden, und eine starre Bewegung braucht gar kein Integral"
metadata: 
  node_type: memory
  type: project
  originSessionId: 7708995f-8153-4da1-9385-1fa5f014d252
  modified: 2026-09-21T22:55:54.456Z
---

Bis 21.09.2026 rechnete `brep/properties.py` Volumen und Fläche über eine
UV-Abtastung in Python: 7–16 s je STEP-Körper, und `edit.transformed`
rechnete vor und nach jeder Bewegung ein konvergiertes Integral (27 s für
das Verschieben eines M6-Bolzens). Nativ (`BRepGProp_Vinert` je Fläche des
knotenzerlegten Verbunds, Bezugspunkt = Hüllmitte, Leiter 1/2/4 bis
`INTEGRAL_RELATIVE_ERROR`) sind es 0,2 s; die UV-Rechnung bleibt Rückfall
für Körper, deren Nähte ihre Toleranz nicht halten.

**Why:** OCCTs Standardbezugspunkt und `SameParameter` ließen die Leiter an
Gewindeflanken nicht konvergieren; mit rohen Pcurve-Schnitten und festem
Bezugspunkt konvergiert sie. Und ein alter Fuzzy-Bolzen (Grad 9, C⁰ an
jedem Knoten) hat unterhalb ~1e-7 **kein definiertes Volumen** — zwei
exakte Green-Integrale liefern dieselbe Fläche um 1e-8 verschieden; dort
entscheidet keine Toleranz, sondern ein sauberer Erzeuger (genähtes Gewinde).

**How to apply:** Volumenprobe nur, wo sie etwas belegt: starre Bewegungen
über `IsPartner` erkennen und ohne Integral durchlassen; Maßstab, Spiegel,
Scherung behalten die Probe. Wer an Nähten „konvergiert nicht" sieht, prüft
erst, ob das Volumen überhaupt definiert ist. Siehe
[[fuzzy-vereinigung-ist-chaotisch]].
