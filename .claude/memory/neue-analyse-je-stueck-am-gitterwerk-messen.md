---
name: neue-analyse-je-stueck-am-gitterwerk-messen
description: Eine Analyse je Überhangstück, die an der Schüssel in 1 s lief, brauchte am Eiffelturm eine halbe Stunde — vor dem Commit an einem Gitterwerk aus dem Korpus messen.
metadata:
  type: feedback
---

`analysis.model_support` (RM-247, Kanaldecken) war an der Waschschüssel gemessen:
89 Kanalfragen, 1,07 s. Am Eiffelturm aus `F:\3D Dateien` (313 000 Dreiecke,
16 323 Überhangstücke) waren es 14 755 Fragen zu je 123 ms — hochgerechnet
30 Minuten für die Druckvorschläge. Die alte Frage (`support_on_model`) brach beim
ersten Stück ab und kostete dort 0 s; niemand hatte den Unterschied gemessen,
der Fehler war schon gepusht.

**Why:** Die Zahl der Stücke wächst mit dem Modell, nicht mit der Schicht. Ein
Körper mit wenigen großen Decken sagt über die Laufzeit einer Frage je Stück
nichts; ein Gitter hat tausende. Bei Roberts Beschwerde „Vorschläge dauern ewig"
ist genau das der Fall, der zählt.

**How to apply:** Wer in der Schichtanalyse eine Frage **je Stück** oder **je
Säule** einführt, fährt sie vor dem Commit am Eiffelturm
(`埃菲尔铁塔18cm_repariert.stl`) und zählt die Aufrufe. Bündeln je Schicht,
vektorisierte GEOS-Aufrufe (geben den GIL frei) und die Arbeitergruppen von
`_support_volume` sind die erprobten Wege; ein Raster verlor dort die dünnen
Streben. Siehe auch [[index-messen-und-pruefen]] und [[uebergabe-je-modell-slicer-drucker]].
