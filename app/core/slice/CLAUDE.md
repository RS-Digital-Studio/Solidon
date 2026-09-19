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
gcode.py     ──> geplant     (aus dem G-Code des Slicers, nach dem Lauf)
```

Regel 14: **Kennzahlen aus beiden Quellen werden nie vermischt.** Jeder Wert
weist seine Herkunft aus — ein geschätztes Stützvolumen ist etwas anderes als
ein aus G-Code geplantes, und der Prüfbericht sagt welches. Erst eine
Feststellung am gedruckten Werkstück ist eine Messung des Verbrauchs.

In der Oberfläche heißt es „Schichtanalyse", nicht „Vorschau".

## Die Karte

| Datei | Rolle |
|---|---|
| `analysis.py` | Der Analyse-Schneider: Konturen, Überhänge, Inseln, Brücken (§22) |
| `advise.py` | Einstellungen aus Geometrie, Material und Maschine (§22.2, §29); `combine` vereint die Anforderungen des Ausgabeumfangs ohne benötigte Stützen zu verlieren |
| `gcode.py` | G-Code zurücklesen (§28.1, §28.2) |
| `estimate.py` | Was ein Teil kostet, ohne es zu schneiden |
| `orientation.py` | Die Suche nach einer Druckorientierung; eine kleine Grundflächen-Vorauswahl für Auto Split wird mit demselben echten Stützvolumen und derselben Fünf-Prozent-Grenze entschieden (§22.3) |

Die Orientierungskandidaten kommen deterministisch aus den flächengeordneten
Normalen der konvexen Hülle, den Achsen und den großen Körperflächen (§28.2).
Der echte Druckbereich wird vor der Schichtanalyse geprüft. Höchstens acht
Finalisten und eine zulässige Ausgangslage werden geschnitten; der Bericht
trennt betrachtete, passende und geschnittene Lagen. Eine unzulässige
Ausgangslage hat `baseline=None`, und dafür wird keine Einsparung behauptet.
Der Schwerpunkt muss in der Hülle der tatsächlichen Auflage liegen. Unter
stehenden Kandidaten entscheidet Stützvolumen, innerhalb fünf Prozent die
Auflagefläche. `SearchResult.transform` beschreibt die vollständige geprüfte
Bewegung; `seed` bleibt als Aufrufparameter für bestehende Projekte lesbar,
hat aber keinen Einfluss auf die geometrische Kandidatenauswahl.

Ebenenschnitt und Konturverkettung haben einen übersetzten Teil —
`tools/build_slice_core.py` baut ihn, das Budget dafür steht in §31.
Der Ebenenschnitt verlangt `PLANE_SEGMENTS_API = 2`, einschließlich des
optionalen Abbruchrückrufs. Ein älterer oder unbekannter lokaler Bau nimmt
für diese Rechnung den NumPy-Weg. Die nativen Vergleichstests nennen den
nötigen Neubau, statt einen unpassenden Aufruf zu versuchen.

Eine geschlossene verkettete Kontur kann geometrisch trotzdem ungültig sein,
etwa wenn eine Ebene genau durch die auslaufende Ecke eines Verbinders geht
und der Rand auf derselben Linie vor- und zurückläuft. Dann bekommt
`polygonize` die **ursprünglichen losen Segmente**. Ein schon daraus gebauter
ungültiger `LinearRing` hat die nötigen Knoten verloren und darf nicht als
Reparatureingang dienen. Der analytische Korpusfall dazu steht in
`tests/data/meshes/dovetail_vertex_plane.ply`; `tests/test_slice_core.py`
hält Schichtfolge, Querschnitt und Stützvolumen zwischen beiden Wegen gleich.

`slice_body` und `cross_sections` nehmen optional einen `CancelToken`. Ohne
Token bleibt der native Fastpath ohne Python-Rückruf. Mit Token prüft der
Cython-Kern periodisch im Flächen- und Flächen-mal-Schichten-Lauf;
der NumPy-Rückfallweg verarbeitet
begrenzte Flächenblöcke. Polygonaufbau, GEOS-Messung und Stützvolumen prüfen
zwischen Schichten beziehungsweise Differenzen. Jeder Weg behält dieselbe
Segmentreihenfolge und dieselben Analysewerte.

Die Analysekarten reichen ihr Abbruch- und Budgetsignal über `solid_field`
auch in diesen Schnittweg. Das Füllen des Voxelfelds prüft es vor jedem
Querschnitt und vor der Rückgabe; ein abgebrochenes Feld wird nicht veröffentlicht.

**Wo die Zeit hingeht, und was dagegen steht** (gemessen 19.09.2026, Befund
Robert „Vorschläge beim Slicen dauern ewig"). Drei Stellen, drei Antworten:

- **Gleiche Schicht, gleiche Zahlen.** `_measure_all` misst eine Schicht nur,
  wenn sie ihrer Vorgängerin nicht gleicht (`_same_layer`: Fläche, Umfang,
  Hüllbox, dann die kanonisch geordneten Ecken ohne Kollineare); gleiche
  bekommen die Zahlen der Quelle (`_repeated`) — kein Überhang, keine Insel,
  keine Brücke gegen eine identische Schicht darunter. Hilft prismatischen
  Körpern; ein Gitterbecher oder eine Figur ändert sich je Schicht.
- **Spannweiten ohne Overlay.** `_supported_span` bündelt gleiche Richtungen
  über den Winkel in einem Zug (nicht jede gegen jede vorige), nimmt die
  Bänder aus der vereinfachten Kontur und schneidet die Bahnen als
  Abtastzeile in numpy (`_cuts_along`, Paritätsregel über alle Ringe) statt
  mit `shapely.intersection`. Drachenfigur, 2,3 Mio. Dreiecke: 120 s → 7,6 s
  für die Brücken aller Schichten, dieselben Zahlen.
- **Säulen nur, wo sie jemand liest.** `slice_body(support_volume=False)`
  lässt `_support_volume` aus; die Druckvorschläge nehmen den Weg, und der
  Druckdialog behält den letzten gemessenen Stand in der Sitzung
  (`Session.remember_analyses`), damit ein zweites Öffnen nicht wieder
  schneidet.

Die Arbeiterzahl der vollständigen Messung steht bei sechs (`FULL_WORKERS`);
die Messreihe dazu steht an der Konstante.

## Grenzen

`slice_body(overhang_angle=...)` erhält den zulässigen Winkel gegen die
Senkrechte aus dem wirksamen Material- und Prozessprofil. Ohne Angabe gilt
die Startregel. Der Winkel bestimmt die Reichweite zur unteren Schicht;
Analysekarten, Orientierungssuche und Agentenbericht verwenden denselben
Vertrag. Messwerte aus einer anderen Düse oder einem anderen Druckraster
werden bereits im Profil verworfen, nicht erst in der Darstellung.

`slice_body(first_layer_height=...)` setzt das tatsächliche Druckraster und
die Abstände zur darunterliegenden Schicht. Ohne Angabe bleibt das
gleichmäßige Suchraster erhalten. Offene Brückenbereiche werden anhand ihrer
beidseitigen Auflager gemessen; ein seitlich ungestützter kurzer Querschnitt
gilt nicht als kürzere Brücke.

- **Kein eigener Slicer**, auch nicht „nur für den Anfang".
- Leistung wird gemessen, nicht gefühlt: `pytest -m performance`, Zielwerte
  §31, Regressionsschwelle 25 %.
- Messungen unter Fremdlast sind keine Messungen — die Marke allein fahren.

## Materialvorgaben und Verbrauch

Warnungen vergleichen ungekürzte Materialvorgaben mit den Grenzen des
Druckers. Ein vorher auf das Düsenmaximum gedeckelter Sollwert kann eine
unzureichende Temperatur nicht mehr nachweisen. G-Code-Verbrauchslisten
bleiben zusätzlich als `filament_mm_by_tool` und `filament_grams_by_tool`
erhalten: Der Index ist die Werkzeugnummer der jeweiligen Platte,
einschließlich Werkzeug 0, ungenutzter Nullen und unbekannter Einträge als
`None`. Nur vollständige Listen ergeben eine Summe; eine ausdrücklich
ausgewiesene Gesamtsumme hat Vorrang vor gerundeten Einzelwerten und füllt
keine Lücken. `combine` verbindet Werkzeugnummern verschiedener Platten
nicht, denn sie können unterschiedliche Spulen bezeichnen.

`used_tools` hält zusätzlich Werkzeugwechsel mit tatsächlicher Extrusion
fest. Dadurch wird eine kommentarlose Gesamtlänge nicht irrtümlich dem
einzigen Modellfilament zugeschlagen, wenn der Slicer weiteres Material
verwendet. Unbelegte Einzelwerte werden aus solchen Wechseln nicht geraten.

`grams_by_tool` wandelt fehlende Grammmengen nur mit belegter Dichte und
belegtem Durchmesser je Werkzeug um. Angaben im Dateikopf gewinnen vor
mitgegebenen Materialdaten. Bewegungen liefern werkzeugweise Längen;
`M200` liefert direkt Volumen, auch ohne bekannten Filamentdurchmesser.
Die Mengenbilanz zählt neue Förderung auch stationär und bei `G0`.
Rückzug bleibt je Werkzeug als offener Weg erhalten; Wiederförderung verbraucht
ihn zuerst, und ein Endrückzug senkt keinen bereits entstandenen Verbrauch.
Ein Wechsel zwischen linearer und volumetrischer Extrusion rechnet offene
Rückzüge mit dem belegten Durchmesser um; fehlt er, bleibt die Menge unbekannt.
Druckbahnen, Modellgrenzen und Stützvolumen bleiben von stationärer Reinigung
und Leerfahrten getrennt. Ausdrückliche Mengenheader behalten ihren Vorrang.
Angegebene Grammmengen gelten auch
bei null. Eigene Ausgaben tragen `resolved_filament_grams` aus demselben
eingefrorenen Bedarf wie das Lagerangebot. Die Gesamtmethode `grams` verwendet
diese Auflösung; spätere Dialogwerte dürfen das Ergebnis nicht verändern.
Jede dieser Mengen ist aus G-Code geplanter Verbrauch, keine Messung am Werkstück.

Bambus `T255`, `T1000` und `T1100` wechseln kein Filament. Dieser Vertrag
gilt bei belegter Bambu-Herkunft oder dessen Maschinenbefehlen; fremde
Firmware erbt ihn nicht. Komprimierte Bambu-Kopfwerte folgen den
einsbasierten Kennungen in `filament:`. Werkzeugnummern und Kopfkennungen
werden vor der Allokation werkzeugweiser Ergebnislisten begrenzt.

`handover.off_the_bed` prüft zuerst die Hüllbox. Reicht sie für eine
polygonale Druckkontur oder Sperrfläche nicht aus, prüft ein abbrechbarer
zweiter Lesedurchlauf die tatsächlichen Geraden und Bögen. Dabei werden keine
Bahnen gesammelt. Dateiangaben haben Vorrang vor dem Druckerprofil;
Reinigung vor der ersten Modellschicht zählt nicht als Modellbahn.

G-Code-Wörter benötigen keinen Leerraum als Trenner. `E` bezeichnet die
Extrusion auch unmittelbar hinter einer Koordinate; wissenschaftliche
Zahlenschreibweise darf deshalb keine Extrusionswörter verschlucken.
