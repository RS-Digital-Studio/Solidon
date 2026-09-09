# `app/core/sketch/` — Skizzen mit Zwangsbedingungen

2D-Geometrie, die durch einen Löser bestimmt wird statt durch gezogene Punkte
(§30.1). Die Grundlage für alles, was aus einem Umriss entsteht.

Der **grafische Editor** liegt in `app/ui/sketch_editor.py` und hat eine
eigene Regeldatei (`.claude/rules/zeichenflaeche.md`). Hier steht die Rechnung
darunter.

## Der Weg

```
shapes.py     Grundformen (Linie, Kreis, Bogen …)
     │
     ▼
solver.py     Zwangsbedingungen lösen  ──>  bestimmte Koordinaten
     │
     ▼
profile.py    geschlossene Umrisse finden, Hierarchie aus Außen und Löchern
     │
     ▼
ops.py        Extrudieren, Rotieren, Ausschneiden — die Skizzen-Operationen
```

`planes.py` beantwortet die Frage davor: **wo** die Skizze liegt — auf einer
Grundebene oder auf einer Fläche des Modells.

## Die Karte

| Datei | Rolle |
|---|---|
| `solver.py` | Der 2D-Löser |
| `profile.py` | Vom gelösten Element zum geschlossenen Umriss |
| `shapes.py` | Die Grundformen (Ausgabestufe eins) |
| `planes.py` | Wo eine Skizze liegt |
| `edit.py` | Trimmen, Verlängern, Versetzen, Spiegeln |
| `ops.py` | Die Operationen der Kategorie „Skizze" |
| `serialize.py` | **Die ganze Skizze als ein Parameterwert** einer Operation |

## Warum `serialize.py` der Schlüssel ist

Eine Skizze wird mit hundert Mausbewegungen gezeichnet, und trotzdem ist sie
**ein** Schritt im Stapel. Das geht, weil der Editor in einen Parameterwert
schreibt und die Geometrie erst bei der Auswertung entsteht — Regel 2 erlaubt
genau das, solange das Ergebnis vollständig aus den Parametern folgt.

Das ist dasselbe Muster wie bei `geom/sculpt.py` und `geom/pose.py`. Wer es
bricht, bricht die Reproduzierbarkeit der Auswertung.

## Grenzen

- **Eine Splinekurve für Vorschau und Körper.** `profile.spline_controls`
  liefert die Catmull-Rom-Bézierstücke; die 2D-Schnittprüfung und der
  B-Rep-Kern verwenden dieselben Kontrollpunkte. Jede kubische Teilkurve
  erhält eine eigene B-Rep-Kante, damit auch Flächenintegrale an den
  Stückgrenzen getrennt werden. Der Drehsinn folgt dem exakten Integral.
- **Ringe müssen getrennte Grenzen haben.** Kreisverschachtelung wird
  analytisch entschieden, andere exakte Umrisse über ihre B-Rep-Grenzen.
  Kreuzungen, Berührungen und doppelte Ringe halten mit Vorschlag an.
- **Das Löserbudget zählt alle dichten Zeilen**, einschließlich der
  zusätzlichen Kreis-Eichzeilen bei ansonsten freien Skizzen.

- **Der Löser rät nicht.** Ein unterbestimmtes System bleibt unterbestimmt;
  ein widersprüchliches meldet `SketchConflictError` mit Handlungsvorschlag.
  Gezeichnete Skizzen geben verbleibende Freiheitsgrade mit dem Ergebnis der
  Operation zurück. Vorgegebene Grundformen erzeugen diesen Hinweis nicht.
- **Flächenrahmen übernehmen die orientierte Merkmalsnormale.** Die Mitte
  des Hüllquaders entscheidet keine Innen-/Außenrichtung, insbesondere an
  Innenböden und konkaven Körpern. Eine blinde Tasche endet in beiden Kernen
  genau an ihrer eingegebenen Oberkante und Tiefe.
- **Der Sweep läuft auch an einer gezeichneten Bahn entlang** (`sketch_sweep`,
  RM-147 E3). `along` entscheidet zwischen dem Bogen aus Radius und Winkel und
  der Zeichnung in `path_sketch`. Die Bahn kommt aus `profile.path_of` — eine
  **offene** Kette statt eines Rings, mit genau zwei freien Enden; ein Kreis
  ist keine. Sie liegt auf XZ oder YZ (`brep.profiles.PATH_PLANES`), und ihr
  Anfang wandert in den Ursprung: Sie beschreibt einen Verlauf, keinen Ort.
- **Der Übergang nimmt zwei unabhängige Zeichnungen** (`sketch_loft`, RM-147
  E2). `top` entscheidet, woher der obere Umriss kommt: aus dem unteren
  gerechnet (`top_scale`) oder als eigene Zeichnung (`top_sketch`). Geprüft
  wird vorher — dieselbe Ebene, gleich viele getrennte Umrisse; die gleiche
  Zahl der Löcher je Paar prüft `brep.profiles.loft` selbst. Verbunden wird in
  der Reihenfolge von `regions_of`, und der `doc`-Satz sagt das.
- **Kein Qt.** Der Editor ruft hier herein, nie umgekehrt.
