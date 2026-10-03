# RM-252: Koordinatenverlust bei der 3MF-Ausgabe

## Ursache und Änderung

Ausgangsstand: `5a7ab992f`. Modell:
`F:\3D Dateien\Modern++Cutlery+Organizer+with+Divider.3mf`.
Import über `import_plan`, `History.apply` und die normale Szenenauswertung;
Übergabe über `writer.write_assembly` und `handover.slice_model`.

Das importierte Netz hat 29.790 Ecken, 59.744 Dreiecke und fünf geschlossene
Komponenten. Der Vergleich gegen das ursprüngliche XML findet dieselben
orientierten Dreiecke; die größte Koordinatendifferenz nach Ausrichtung liegt
bei 7,11 × 10⁻¹⁴ mm. Der Import verändert die Topologie nicht.

Erst die 3MF-Ausgabe rundete jede Koordinate auf sechs Nachkommastellen.
80.832 Koordinaten änderten sich, höchstens um 0,0000005 mm. Dabei entstanden
weder doppelte Ecken noch flächenlose Dreiecke. Trotzdem stürzt die Kombination
aus dieser Rundung, Farbzuweisung und Gitterstützen in beiden untersuchten
Slicern ab. Die genaue interne Absturzstelle der externen Programme wurde
nicht bestimmt; der auslösende Unterschied der Übergabedatei ist isoliert.

`threemf._write_geometry` schreibt Körper und Stützsperren jetzt mit 17
signifikanten Stellen. Die gespeicherten float64-Koordinaten bleiben beim
Rücklesen erhalten. Das gilt auch für einzelne Körper und die Cura-/Prusa-
Schreibweisen. Die [3MF-Kernspezifikation, ST_Number](https://github.com/3MFConsortium/spec_core/blob/master/3MF%20Core%20Specification.md)
erlaubt dabei Dezimal- und Exponentialschreibweise. Solidons Projektformat
ändert sich nicht.

## Reale Gegenproben

Alle Läufe nutzen ausdrücklich gewählte Gitterstützen, soweit nicht anders
genannt. Die Sonden und unveränderten Dateien stehen unter
`F:\solidon-review-reports\B-slicer-rest\rm252`.

| Lauf | Ergebnis |
|---|---|
| ElegooSlicer 1.5.3.5, alte Ausgabe | Absturz, erneut bestätigt mit Rückgabe 3221226505 (`0xC0000409`) |
| Alte Ausgabe, Grundfarbe ohne native Bemalungsattribute | Derselbe Absturzcode; die explizite Grundfarbe ist nicht die Ursache |
| Gleiches Netz ohne Farben | 800 Schichten, 380,98 g, ein Werkzeug; nur Diagnose, kein Fix |
| Alte Ausgabe, nur Koordinaten verlustfrei ersetzt | 800 Schichten, 472,32 g, zwei Werkzeuge |
| Elegoo, vollständiger Kundenweg nach Fix | 800 Schichten, 472,32 g, 66.508 s Slicerzeit; 148.517,37 und 9.842,23 mm Filament, 45.066,92 mm³ Stützmaterial |
| Originalprojekt, aktuelles Elegoo mit Gitterstützen | 800 Schichten, 466,59 g, zwei Werkzeuge; unterstützt den früheren Originalbeleg |
| OrcaSlicer 2.4.2, A1, alte Rundung wieder eingesetzt | Absturz mit `0xC0000409` |
| Orca, vollständiger Kundenweg nach Fix | 800 Schichten, 403,15 g, 66.330 s Slicerzeit; 127.170,39 und 7.999,08 mm Filament, 48.167,38 mm³ Stützmaterial |

Die Zeiten sind Angaben aus dem G-Code, keine gemessenen Druckzeiten.
Original und Solidon-Projekt sind hinsichtlich Profil-/Farbvorgaben nicht
identisch; ihre Materialzahlen sind kein Qualitätsvergleich.

Der Dateivergleich sichert zu: Außer der Zahlendarstellung der Ecken ist der
gesamte Modell-XML-Inhalt identisch, und alle übrigen ZIP-Einträge sind
bytegleich. 59.711 Dreiecke behalten Farbe 1 und 33 Dreiecke Farbe 2; beide
Werkzeuge extrudieren im G-Code. Die Build-Verschiebung bleibt `(128, 128, 0)`.
Die gepackte Datei wächst von 662.093 auf 819.359 Byte.

Die alte Rohnetzprobe aus `besteck_absturz3.out` hatte beim Ersetzen des Netzes
auch dessen Slots verloren. Sie belegte deshalb keinen Unterschied durch die
Netzaufbereitung. Der neue reine Koordinatenvergleich erhält die Slots.

Der Elegoo-Lauf meldet weiterhin `gcode.off_the_bed`, beide Programme melden
`slicer.arranged_itself`. Diese Anordnungs-/Mehrfarbenbefunde sind nicht mit
dem behobenen Absturz gleichzusetzen; sie gehören zur parallel bearbeiteten
Übergabereihe RM-475/476. Auch der Hinweis auf Filamentwerte aus Solidons
Tabelle bleibt sichtbar. Es wurden keine Befunde unterdrückt.

## Bleibende Absicherung und Veröffentlichung

Acht Fälle in `tests/test_export.py` lesen die Koordinaten aus der tatsächlich
geschriebenen 3MF: Einzelkörper, Orca-, Prusa- und Cura-Baugruppe, jeweils mit
und ohne Farben; die Baugruppen enthalten eine Stützsperre. Verglichen wird
die Bitdarstellung der gespeicherten Werte. Ein geometrischer EPS-Vergleich
hätte den Fehler übersehen. Vor dem Fix: acht rot; danach: acht grün.

Die feste Sechserrundung stammt aus `c4b890e2c` (zuvor fünf Stellen), die
Stützsperre übernahm sie in `1db1dbfdd`. `git tag --contains c4b890e2c` nennt
unter anderem `v0.5.1`. Ein Kundenpunkt steht deshalb in allen sechs
Changelogs unter 0.5.2. Der umfassende Entwicklungslauf und der Commit werden
im Abschlussbericht dokumentiert; Fenster-, Renderer- und Leistungsläufe
gehören zur Releaseabnahme.
