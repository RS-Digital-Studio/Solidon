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
| `solver.py` | Der 2D-Löser — und sein Zugmodus (`dragged`, `start`) |
| `profile.py` | Vom gelösten Element zum geschlossenen Umriss |
| `shapes.py` | Die Grundformen und die zwei Lochbilder; `grid_centres` hält die gemeinsame mittige Rasterlage für Skizze und Feldschnitt |
| `planes.py` | Wo eine Skizze liegt |
| `edit.py` | Trimmen, Verlängern, Versetzen, Spiegeln — an einer Ecke Verrunden und Fase (`corner_at`, `fillet`, `chamfer`), und die vier Formen aus zwei Klicks (`polygon_at`, `slot_between`, `hole_grid_between`, `bolt_circle_at` — die Lochbilder halten über Bedingungen zwischen den Mitten, nicht über Festpunkte) |
| `ops.py` | Die Operationen der Kategorie „Skizze“; `cut_regions` teilt den bestehenden Taschenschnitt mit aufgelösten Feldern, einschließlich Ebene, Durchgang und Z-Bezug |
| `serialize.py` | **Die ganze Skizze als ein Parameterwert** einer Operation |

## Warum `serialize.py` der Schlüssel ist

Eine Skizze wird mit hundert Mausbewegungen gezeichnet, und trotzdem ist sie
**ein** Schritt im Stapel. Das geht, weil der Editor in einen Parameterwert
schreibt und die Geometrie erst bei der Auswertung entsteht — Regel 2 erlaubt
genau das, solange das Ergebnis vollständig aus den Parametern folgt.

Das ist dasselbe Muster wie bei `geom/sculpt.py` und `geom/pose.py`. Wer es
bricht, bricht die Reproduzierbarkeit der Auswertung.

`sketch_parameter_references(strict=True)` reicht unlesbare Skizzen und
Maßausdrücke weiter, damit die Verwendungsabfrage ein beschädigtes Maß nicht
als unbenutzt ausweist. Ohne `strict` bleibt der Cachevertrag erhalten:
Die Operation meldet den Fehler bei ihrer Auswertung.

`resolve_sketch_values(text, parameters)` löst ausschließlich die Maßwerte
der Bedingungen in einer temporären Kopie auf. Damit kann ein Baustein ohne
eigenen Szenenkontext dieselbe Zeichnung bauen wie die Platzierungsvorschau.
Punkte, Ebene und Bedingungsarten bleiben unverändert; die Geometrie löst
weiterhin `solve_sketch`. Fehlende Projektmaße bleiben Ausdrucksfehler. Der
gespeicherte Originaltext und seine Cache-/Verwendungsabhängigkeiten bleiben
erhalten.

## Grenzen

- **Fünfzehn Bedingungsarten, und „konzentrisch" ist keine davon.** Zwei
  Kreise mit gemeinsamer Mitte sind die Deckung ihrer Mittelpunkte; eine
  eigene Art wäre ein zweiter Weg, denselben Sachverhalt zu speichern, zu
  prüfen und zu migrieren. Das Wort steht trotzdem an einem Knopf der
  Oberfläche (`sketch_editor.ConstraintAction`) — eine Bedeutung, ein
  Datenmodell, zwei Namen für zwei Anlässe. Aus demselben Grund gibt es **ein**
  `equal` und kein `equal_radius`: Linienlänge und Radius sind beide der
  Abstand zweier Punkte, also dieselbe Gleichung.
- **Der Winkel rechnet als Sinus und nicht als Bogen** (`_angle_equation`).
  `sin(φ − θ)` ist bei θ = 0 die Gleichung von `parallel` und bei θ = 90° die
  von `perpendicular`; `atan2(…) − θ` hätte bei ±180° einen Sprung, den keine
  Ableitung kennt. Der Preis ist die Periode 180 — deshalb nimmt ein
  Winkelmaß nur Werte echt zwischen 0 und `MOST_ANGLE_DEGREES`. Die Zahl
  steht in **Grad** in der Datei und wird erst in der Gleichung Bogenmaß; §11
  gilt den Längen.
- **Eine neue Bedingungsart erhöht `format_version` nicht.** Der Aufbau der
  Projektdatei ändert sich nicht, und jede ältere Datei liest sich
  unverändert — es gibt nichts zu migrieren (AGENTS.md, Checkliste
  „Dateiformat ändern", Punkt 4). Was sich ändert, ist der **Wertebereich**
  einer vorhandenen Aufzählung, und der wächst nur nach vorn: Eine neue Datei
  in einer alten Version wird ohnehin am Versionsdeckel abgewiesen (§16.2),
  nicht an einer unbekannten Bedingung. Die zwei Listen der Arten
  (`solver._CONSTRAINT_TARGETS`, `serialize._CONSTRAINT_KINDS`) hält
  `tests/test_sketch.py` deckungsgleich.
- **Die zwei gezeichneten Formen halten sich selbst, ohne bemaßt zu sein**
  (`polygon_at`, `slot_between`). Das Vieleck hängt an einem **Hilfskreis**:
  alle Ecken auf ihm, alle Seiten gleich lang — zusammen genau so viele
  Gleichungen, wie ein geschlossener Zug an Formfreiheiten hat. Über Winkel
  an den Ecken ginge die Rechnung nicht auf, denn die letzten beiden bringt
  der Zug selbst mit. Gemessen: 3 Freiheitsgrade (Mitte und Radius), mit
  Festpunkt und bemaßtem Umkreis null. Das Langloch trägt vier
  `perpendicular` zwischen Flanke und Radiusstrahl und ein `equal` zwischen
  den beiden Radien — 5 Freiheitsgrade, beide Mitten und die Breite, und das
  in jeder Richtung gleich.
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
- **Der Zug ist ein eigener Modus des Lösers** (`solve_sketch(..., dragged=,
  start=)`, 13.09.2026). Ohne ihn beginnt der Löser bei den gespeicherten
  Punkten und findet die *nächste* Lösung — beim Ziehen die falsche: Ein
  Rechteckpunkt, um zwanzig Millimeter gezogen, kam bei fünf an, weil die
  Deckung mit dem Nachbarn hälftig ausgeglichen wurde. Mit `dragged` stehen
  die gezogenen Punkte am Zeiger und alles andere folgt mit der kleinsten
  Bewegung ab `start`, dem zuletzt gelösten Stand. **Zwei Stufen**: erst
  werden die gezogenen Koordinaten aus dem System genommen (exakt — ein auf
  das Raster gefangener Punkt landet auf der Rasterzahl); lassen die
  Bedingungen den Ort nicht zu, rechnet die zweite Stufe sie als zähe
  Variablen mit (`DRAG_STIFFNESS`, ein Zwanzigstel wie in SolveSpace) — ein
  Punkt auf einer Waagerechten folgt seitlich, einer am festen Maß läuft auf
  seinem Kreis, ein `fixed` hält. Gemessen: 2 ms je Zugschritt am Rechteck;
  bei nichtlinearen Bedingungen (Radius, Senkrechte) driftet ein einzelner
  Sprung um zehn Millimeter im Nullraum um 2·10⁻⁴ mm, fünfzig Schritte à
  0,2 mm bleiben unter 10⁻⁸ — die Maus zieht in Schritten, und so prüft es
  `tests/test_sketch_edit.py`.
- **Eine Rundung trägt ihre Tangente als Senkrechte** (`edit.fillet`). Die
  Tangentenbedingung misst den Abstand der Mitte zur Geraden gegen den
  Radius; an einem Bogenende, das per Deckung *auf* der Linie liegt, ist das
  ein doppelter Nullpunkt — die Ableitung nach dem Ende ist null, die
  Jacobimatrix singulär, und die Rangprüfung meldete „legt fest, was schon
  festliegt" über eine bestimmte Skizze. `perpendicular` zwischen Linie und
  Radiusstrahl zum Berührpunkt sagt dasselbe mit einer Ableitung, die trägt.
  Die Fase hält nur ihre Länge als Maß; ihr Winkel bleibt ein Freiheitsgrad,
  weil „gleich weit von einer Ecke, die es nicht mehr gibt" keine Bedingung
  der Liste ist und eine neue Art ein Dateiformat wäre.
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
  Die Anfangstangente muss senkrecht zum XY-Querschnitt nach oben oder unten
  zeigen; ein schräger Beginn wird vor der Geometrieerzeugung zurückgewiesen.
  Die Umsetzungskennung der Operation hält ältere Sweep-Ergebnisse mit
  verlorenem Innenraum oder ungeprüftem Bahnbeginn aus dem Cache fern.
- **Der Übergang nimmt zwei unabhängige Zeichnungen** (`sketch_loft`, RM-147
  E2). `top` entscheidet, woher der obere Umriss kommt: aus dem unteren
  gerechnet (`top_scale`) oder als eigene Zeichnung (`top_sketch`). Geprüft
  wird vorher — dieselbe Ebene, gleich viele getrennte Umrisse; die gleiche
  Zahl der Löcher je Paar prüft `brep.profiles.loft` selbst. Verbunden wird in
  der Reihenfolge von `regions_of`, und der `doc`-Satz sagt das.
- **Ein Lochbild ist eine Grundform mit mehreren Umrissen** (`bolt_circle`,
  `hole_grid`, RM-147). Sie stehen in `shapes.PATTERN_CHOICES` und nicht in
  `SHAPE_CHOICES`: Nur *Grundform hochziehen* und *Tasche schneiden* rechnen
  mit mehreren Umrissen, Drehen, Ziehen und Übergang mit genau einem. Das
  Hauptmaß bleibt `length` — beim Lochkreis der Teilkreisdurchmesser, beim
  Raster der Abstand von Mitte zu Mitte —, dazu kommen `count`, `columns`,
  `rows` und `hole_diameter` über `depends_on`. Assoziativ ist daran nichts
  (Konzept P15, E11): Die Parametrik liegt eine Ebene höher, ein
  Projektparameter dreht den Teilkreis.
- **Kein Qt.** Der Editor ruft hier herein, nie umgekehrt.
