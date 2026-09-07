# `app/core/slice/` — Schichtanalyse

Kennzahlen und Konturen aus dem Modell. **Bewusst kein G-Code-Slicer** (§22).

Die Regeln stehen in `.claude/rules/schichtanalyse.md`.

## Die Abgrenzung, die nicht verhandelbar ist

Die Datei, die auf den Drucker geht, kommt vom **externen** Slicer. Was hier
entsteht, ist Analyse: Ebene-Mesh-Schnitt, Konturen, Kennzahlen — in
Millisekunden, ohne Fremdprozess.

**G-Code wird gelesen, nie geschrieben.**

## Zwei Herkünfte, die nie verschmelzen

```
analysis.py  ──> geschätzt   (aus der Geometrie, sofort)
gcode.py     ──> gemessen    (aus dem G-Code des Slicers, nach dem Lauf)
```

Regel 14: **Kennzahlen aus beiden Quellen werden nie vermischt.** Jeder Wert
weist seine Herkunft aus — ein geschätztes Stützvolumen ist etwas anderes als
ein gemessenes, und der Prüfbericht sagt welches.

In der Oberfläche heißt es „Schichtanalyse", nicht „Vorschau".

## Die Karte

| Datei | Rolle |
|---|---|
| `analysis.py` | Der Analyse-Schneider: Konturen, Überhänge, Inseln, Brücken (§22) |
| `advise.py` | **Einstellungen, die die Geometrie selbst verlangt** (§22.2, §29) — knapp 1 000 Zeilen Schlussfolgerung |
| `gcode.py` | G-Code zurücklesen (§28.1, §28.2) |
| `estimate.py` | Was ein Teil kostet, ohne es zu schneiden |
| `orientation.py` | Die Suche nach einer Druckorientierung; eine kleine Grundflächen-Vorauswahl für Auto Split wird mit demselben echten Stützvolumen und derselben Fünf-Prozent-Grenze entschieden (§22.3) |

Ebenenschnitt und Konturverkettung haben einen übersetzten Teil —
`tools/build_slice_core.py` baut ihn, das Budget dafür steht in §31.

Eine geschlossene verkettete Kontur kann geometrisch trotzdem ungültig sein,
etwa wenn eine Ebene genau durch die auslaufende Ecke eines Verbinders geht
und der Rand auf derselben Linie vor- und zurückläuft. Dann bekommt
`polygonize` die **ursprünglichen losen Segmente**. Ein schon daraus gebauter
ungültiger `LinearRing` hat die nötigen Knoten verloren und darf nicht als
Reparatureingang dienen. Der analytische Korpusfall dazu steht in
`tests/data/meshes/dovetail_vertex_plane.ply`; `tests/test_slice_core.py`
hält Schichtfolge, Querschnitt und Stützvolumen zwischen beiden Wegen gleich.

## Grenzen

- **Kein eigener Slicer**, auch nicht „nur für den Anfang".
- Leistung wird gemessen, nicht gefühlt: `pytest -m performance`, Zielwerte
  §31, Regressionsschwelle 25 %.
- Messungen unter Fremdlast sind keine Messungen — die Marke allein fahren.

## Materialvorgaben und Verbrauch

Warnungen vergleichen ungekürzte Materialvorgaben mit den Grenzen des
Druckers. Ein vorher auf das Düsenmaximum gedeckelter Sollwert kann eine
unzureichende Temperatur nicht mehr nachweisen. G-Code-Verbrauchslisten
werden über alle Slots summiert; eine ausdrücklich ausgewiesene Gesamtsumme
hat Vorrang vor gerundeten Einzelwerten.

G-Code-Wörter benötigen keinen Leerraum als Trenner. `E` bezeichnet die
Extrusion auch unmittelbar hinter einer Koordinate; wissenschaftliche
Zahlenschreibweise darf deshalb keine Extrusionswörter verschlucken.
