---
name: pruefstand-nimmt-den-ladeweg-der-anwendung
description: "Ein Korpusprüfstand lädt Modelle wie die load-Operation (normalise mit Verschweißen) — read_mesh allein gab ein anderes Netz, und die frische Erkennung am gedrehten Netz wich scheinbar von der mitgeführten ab"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: ebc8112f-3e6f-44e4-b117-6d2044e135a9
  modified: 2026-09-22T08:16:24.247Z
---

Der Prüfstand für `F:\3D Dateien` (22.09.2026) lud STL über `read_model`
ohne `normalise` und verglich die mitgeführte Erkennung (`carry_detection`)
mit einer frischen am um 37° gedrehten Netz: 19 von 125 Körpern wichen ab
(Verrundung 56 statt 52 Dreiecke, `tangent` fehlte, Flächen 29 statt 27). Am
selben Modell über `normalise(read_mesh(...), "mm")` — dem Weg der
`load`-Operation — war alles gleich. Das unverschweißte Netz trug
Nachbarschaften, die an der Rundung der gedrehten Koordinaten hingen.

**Why:** Ein Prüfstand belegt nur den Weg, den er fährt. Ein Netz, das die
Anwendung so nie sieht, zeigt Abweichungen, die der Kunde nie sieht — und
verdeckt vielleicht welche, die er sieht. Der echte Fund desselben Laufs
(`moved_features` streckte die kurze Normale einer gerundeten Seite auf
eins) war dagegen an beiden Ladewegen sichtbar.

**How to apply:** Korpus- und Vergleichsläufe nehmen den Ladeweg aus
`ingest/ops.py`: 3MF über `threemf.read_objects` je Körper, sonst
`read_model`, und jeden Körper durch `normalise(..., "mm",
weld_is_reading=suffix == ".stl")`. Bevor eine Abweichung als Fehler gilt, den
Weg der Anwendung nachstellen (siehe [[pruefstand-geht-den-weg-der-oberflaeche]]
und [[kundenweg-im-fenster-messen-nicht-im-kern]]).
