# Herkunft je Dreieck — gebaut, gemessen, verworfen (09.09.2026)

Robert am laufenden Fenster: „versteifungsrippe hat auch nur eine seite, die
anderen sind beim modell gelandet". Der Baustein `rib` meldet genau ein
Merkmal (`rib_1`); die übrigen Flächen findet die Erkennung, und der
Objektbaum hängt eine Fläche über `feature.created_by` unter ihren
Bausteinschritt. Ohne Erzeuger landet sie beim Körper.

Gewählt wurde daraufhin (Robert, aus drei Wegen) die **Herkunft je Dreieck**:
`MeshData.origins` trägt je Dreieck die Op-Kennung, `carry_origins` überträgt
sie durch jede Operation, und `Feature.shaped_by` sagt, aus welchem Schritt die
Dreiecke einer Fläche stammen.

## Warum er trotzdem nicht hinausgeht

**Der Fall war beim Messen bereits behoben.** Die Bausteinarbeit desselben
Tages (`parts_version` 16) hat ihn miterledigt; Roberts laufendes Fenster
zeigte den Stand davor. Der Objektbaum ist mit und ohne Umbau identisch:

```
Halter
  Versteifungsrippe
    Linke Seite innen   154 mm²
    Oberseite           119 mm²
    Rechte Seite        150 mm²
```

**Und es gibt keinen zweiten Fall.** Über alle 27 Bausteine gemessen — Quader
bauen, Baustein einsetzen, auswerten (`sonde_alle_bausteine.py`) — hängt der
Umbau **keine einzige** Fläche um. Die bestehende Zuordnung über `created_by`
erfasst bereits jede Fläche, die zum Bausteinschritt gehört. Am echten Projekt
`weg2-halter-konstruieren.p3d` ändert er genau fünf Flächen von „kein Schritt"
auf `create_box` — und der ist kein Bausteinschritt, also bleibt es unsichtbar.

## Was der Weg trotzdem gebracht hat

Drei Messungen, die auch ohne den Umbau gelten:

1. **Eine Vereinigung erhält weniger Dreiecke, als man denkt.** Rippe auf
   Platte: von 28 Dreiecken nur zwölf Ecke für Ecke unverändert. Die sechzehn
   übrigen enthalten die Rippe **und** die Plattenoberseite um sie herum — wer
   alles Neue dem letzten Schritt zuschlägt, hängt die Oberseite des Halters
   unter „Versteifungsrippe" (`sonde_dreiecke.py`).
2. **Die Suche nach der nächsten Oberfläche kostet rund 0,25 ms je Dreieck.**
   Am Dosenbeispiel: 41 434 offene Zeilen gegen zwei Quellen, 9,8 Sekunden von
   11,9 (`sonde_kosten.py`). Das ist derselbe Fall, den `on_surface` schon
   einmal über Größenbänder entschärfen musste (29.08.2026) — eine Ebene
   höher wiederholt.
3. **`tuple(int(x) for x in array)` ist bei zehntausenden Dreiecken die
   Rechnung selbst**, nicht ihr Rand: `tolist()` an einer Stelle brachte den
   Leistungstest von 1765 auf unter die Marke von 1228 ms.

## Drei Riegel, die dabei fast gefallen wären

Der erste Entwurf schrieb die Herkunft nach `created_by`. Drei Tests wurden
rot, und sie hatten recht — sie halten fest, dass ein **erkanntes** Merkmal
keinen Erzeuger bekommt:

| Test | Was er schützt |
|---|---|
| `test_loading_a_model_gives_no_detected_feature_an_originator` | nach dem Laden keiner |
| `test_an_operation_that_declares_nothing_gives_no_originator` | Aushöhlen führt keine Merkmale ein |
| `test_a_contested_feature_never_gets_an_originator` | umstrittene Kandidaten bleiben frei (Einwand 3d-druck-61) |

`created_by` beantwortet „wer verantwortet dieses Merkmal", nicht „wer hat
diese Dreiecke gebaut". Wer den Patch je wieder aufnimmt, hält die beiden
getrennt — `shaped_by` daneben, nicht `created_by` erweitern.

## Wann er wieder infrage kommt

Wenn ein Baustein Flächen erzeugt, **ohne sie zu benennen**, und sie deshalb
beim Körper landen. `sonde_alle_bausteine.py` beantwortet das in einem Lauf:
Solange die Spalte „nur über shaped_by" überall null zeigt, gibt es das
Problem nicht.

`umbau.patch` ist gegen `411eb667` gerechnet und vollständig: `origins` im
Netz und im Cache, `carry_origins` mit exakter und naher Runde, `shaped_by` am
Merkmal, die Zuordnung in der Auswertung, der Baumzugriff und acht Tests.
