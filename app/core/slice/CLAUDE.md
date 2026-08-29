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
| `orientation.py` | Die Suche nach einer Druckorientierung (§22.3) |

Ebenenschnitt und Konturverkettung haben einen übersetzten Teil —
`tools/build_slice_core.py` baut ihn, das Budget dafür steht in §31.

## Grenzen

- **Kein eigener Slicer**, auch nicht „nur für den Anfang".
- Leistung wird gemessen, nicht gefühlt: `pytest -m performance`, Zielwerte
  §31, Regressionsschwelle 25 %.
- Messungen unter Fremdlast sind keine Messungen — die Marke allein fahren.
