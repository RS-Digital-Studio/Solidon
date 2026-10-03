# Begründungen zu `app/core/slice/CLAUDE.md`

> Stand 27.09.2026. Aus der Karte verschoben, als sie auf Module, Datenfluss,
> Einstiege und Stolperfallen verdichtet wurde. Die Karte steht dort; hier
> stehen die ausführlichen Fassungen, das Warum und die Messwerte und Anlässe
> ihres Tages — wörtlich, gegliedert nach den Überschriften der Karte. *Früher
> unter …* nennt die Stelle der alten Karte.

## Die Orientierungssuche

*Früher unter „Die Karte“.*

Die Orientierungskandidaten kommen deterministisch aus den flächengeordneten
Normalen der konvexen Hülle, den Achsen und den großen Körperflächen (§28.2).
Der echte Druckbereich wird vor der Schichtanalyse geprüft. Geschnitten
werden höchstens acht Finalisten der Heuristik (`FINALISTS`, nach Standfläche
und Überhangfläche), dazu die acht Lagen mit dem kleinsten **geschätzten
Stützraum** (`SUPPORT_FINALISTS`, `geom.orient.Orientation.support`:
Überhangfläche in Projektion mal Höhe über dem Bett; spiegelgleiche Lagen mit
bitgleichen Zahlen einmal), die sechs Achsen und eine zulässige
Ausgangslage; der Bericht trennt betrachtete, passende und geschnittene Lagen.
Die Überhangfläche allein weiß nicht, wie hoch ein Überhang hängt — an Roberts
Getränkehalter standen die besten Lagen von Schirm und Mast dort auf Rang 182
und 51 (RM-190).
Eine unzulässige Ausgangslage hat `baseline=None`, und dafür wird keine
Einsparung behauptet. Stützräume misst die Suche am auf 20 000 Dreiecke
ausgedünnten Ersatznetz, **Standfläche und Stand am Original**, und die
Vorauswahl bewertet Ausgangslage, Achsen und große Körperflächen ebenfalls
am Original: Ein schmaler flacher Rand überlebt die Ausdünnung nicht als
Ebene, und ein Gitter zeigt in jeder Lage die Hälfte seiner Flächen nach
unten — beides ließ die Suche am Gitterbecher (20.09.2026) die Lage
verwerfen, die ohne Stützen druckt.
Der Schwerpunkt muss in der Hülle der tatsächlichen Auflage liegen, und
**stehen heißt, die erste Schicht lässt sich drucken**: Mit Druckerprofil misst
`judge(…, line_width=)` die Auflage um eine halbe Linienbreite nach innen
versetzt (`Candidate.footing`), und daran gilt die kleinste Aufstandsfläche —
eine Kante trägt keine Linie, auch eine lange nicht. Unter
stehenden Kandidaten entscheidet Stützvolumen, innerhalb fünf Prozent die
Auflagefläche. `SearchResult.transform` beschreibt die vollständige geprüfte
Bewegung; `seed` bleibt als Aufrufparameter für bestehende Projekte lesbar,
hat aber keinen Einfluss auf die geometrische Kandidatenauswahl.

**Das Original wird dabei nie kopiert.** Zweihundert Kandidatenlagen hießen
bis zum 21.09.2026 zweihundert Kopien des ganzen Netzes (`print_transform`,
`fitting_transform`), und jede beurteilte Lage drehte das Original noch
einmal und rechnete seinen Schwerpunkt neu — an 1,3 Millionen Dreiecken
35 s je Suche, 755 ms je `judge`. Jetzt kennt das Netz seine äußersten
Ecken einmal (`geom.orient.extreme_points`, im Cache des Netzes; bei einer
Kugel sind das alle), und die Hüllbox jeder Lage kommt aus ihnen
(`turned_extents`, bitgleich mit der Kopie); `judge` dreht nur Schwerpunkt
und die Dreiecke, die die Aufstandsebene kreuzen (`_contact`). Die Lagen
der Vorauswahl werden je Netz in einem Zug bewertet
(`evaluate_directions`), die Hüllnormalen der Kandidaten kommen aus einer
Stichprobe der Ecken (`HULL_SAMPLE`). Gemessen: 200 000 Dreiecke 4,8 → 1,2 s
ohne und 9,2 → 1,2 s mit Druckerprofil, 1,3 Millionen 35,4 → 5,4 s, `judge`
755 → 90 ms — dieselben Lagen, dieselben Matrizen.

## Der Schnitt

*Früher unter „Die Karte“.*

`slice_body` und `cross_sections` nehmen optional einen `CancelToken`. Ohne
Token bleibt der native Fastpath ohne Python-Rückruf. Mit Token prüft der
Cython-Kern periodisch im Flächen- und Flächen-mal-Schichten-Lauf;
der NumPy-Rückfallweg verarbeitet
begrenzte Flächenblöcke. Polygonaufbau, GEOS-Messung und Stützvolumen prüfen
zwischen Schichten beziehungsweise Differenzen. Jeder Weg behält dieselbe
Segmentreihenfolge und dieselben Analysewerte.

## Wo die Zeit hingeht

*Früher unter „Die Karte“.*

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
- **Der Keil an jeder fünften Schicht.** `taper_length` kostete an einer Vase
  ein Drittel der Analyse; `_measure_all` fragt ihn nur an jeder
  `TAPER_SAMPLE`. gemessenen Schicht und schreibt den Wert dazwischen fort.
  Ein Keil kürzer als fünf Schichten wird dabei je nach Lage verfehlt oder
  fünffach gezählt — unter jeder Schwelle, die ihn liest (`advise`, ein
  Fünftel der Schichten). Die Grenze steht als Test in `test_slice.py`.
- **Stückflächen ohne GEOS und ohne NumPy.** `largest_overhang_patch` rechnet
  tausende kleine Ringe mit `units.ring_area` (die Schnürsenkelformel in einer
  Python-Schleife, gemessen zwanzigmal schneller als das Umpacken in ein
  Feld): 287 → 19 ms je Vorschlagsrechnung am Gitterbecher.

- **Gestapelt statt je Schicht.** `_measure_all` gibt jedem Arbeiter einen
  Block von höchstens `BATCH_LAYERS` Schichten, und `_measure_batch` stellt
  jede Frage (Überhang, Inseln, Breitensuche) als **einen** vektorisierten
  GEOS-Aufruf über den Block. Einzeln gestellt warteten die kleinen Aufrufe
  auf den Interpreter-Lock, und sechs Arbeiter waren kaum schneller als
  einer. Die Einzelfunktionen (`_islands`, `minimum_width`,
  `_opening_loss`, `_survives_opening`) sind Blöcke aus einem Element.
- **Den Vorgänger nur einmal vorbereiten.** `_islands_many` baut den
  GEOS-Index der Vorgängerschichten vor ihren wiederholten räumlichen
  Prädikaten auf; tausende Konturen teilen denselben Index. Die Konturen,
  Randberührungen und Schwelle für gemeinsame Fläche bleiben unverändert.
- **Die Öffnung zählt, was der Form fehlt.** Die gefaste Aufweitung kann
  Nadeln über die Form hinaus treiben; `_opening_loss` wirft Splitter unter
  `WIDTH_SIMPLIFY` weg und rechnet die Fläche außerhalb (`_protrusion`:
  Identität, Rasterabgleich der Ecken, Schranke, erst dann Fenster um die
  Nadeln). Die Halbierung läuft über die Bilanz, die größte bestandene Weite
  wird genau nachgefragt (`_minimum_widths`, `_halved`). Geöffnet wird an
  einer Douglas-Peucker-Kontur (`_width_outline`), vereinfacht und
  abgetastet wird eine geordnete (`_canonical`) — Anfangspunkt und
  Umlaufsinn eines Rings sind Sache des Wegs, nicht des Körpers.
- **Mehrere verkettete Ringe ohne `polygonize`** (`_nested`): ein Punkt je
  Ring gegen die übrigen, gerade Tiefe ist Material.
- **Früherer GEOS-Weg (bis RM-486): Säulen auf Arbeitern, je Schicht.** `_support_volume` läuft einmal
  von oben nach unten; ab `SUPPORT_SHARE_FROM` offenen Stücken teilen sich
  `SUPPORT_WORKERS` Arbeiter die Stücke der Schicht
  (`_above_material_shared`, gestreut), und die Liste kommt in der Folge
  zurück, in der sie einfädig entstünde. Die Summe hat damit eine einzige
  feste Folge, gleich wie viele Kerne (RM-266; vorher Gruppen je
  Startschicht, deren Summe in der letzten Stelle an der Kernzahl hing und
  deren Last an einer einzigen Gruppe). Einfädig benutzt `_above_material`
  den räumlichen Baum nur für Hüllboxtreffer, **sortiert** sie und prüft
  exakt mit den eigenen Säulenteilen als erstem Operand. Die untere Schicht
  wird gemeinsam gelesen; ein vorbereiteter GEOS-Index darf nicht parallel
  als Prädikatindex verwendet werden: GEOS baut darin weitere
  Suchstrukturen erst bei der Abfrage auf.
- **Die Suchen lesen nur Zahlen.** `judge` ruft `slice_body(...,
  with_layers=False)`: Stützvolumen und Aufstandsfläche bitgleich, ohne
  Schichten in Konturen zurückzuübersetzen.
- **Früherer Stützort auf Arbeitern** (`model_support`, 26.09.2026, bis RM-486). Er führt
  denselben Abstieg je Stück, in Gruppen je Startschicht; jede Gruppe
  bereitet ihre eigene Kopie der Schicht vor (aus WKB), die Differenzen
  einer Schicht gehen in einem Aufruf, und die Baumtreffer werden
  sortiert — sonst hinge die letzte
  Stelle der Flächen an der Arbeiterzahl. Die Kanalfrage wird **je Schicht**
  gestellt (`_in_channels`: Material Teil für Teil aufgeweitet und vereinigt,
  dann die umschriebene Scheibe je Punkt), der Kanalraum vereinigt die
  Umkreise je Scheibe auf Arbeitern (`channel_space`). Am Eiffelturm aus dem
  Korpus (16 323 Stücke, 14 755 davon auf dem Modell): die Beratung eine
  halbe Stunde → 2,8 s, der Kanalraum 9 → 2,3 s; an der Waschschüssel 1,1 →
  0,8 s und 1,1 → 0,3 s, mit denselben Antworten.

- **Clipper-Säulen (RM-486).** Die feste Abwärtsfolge und ihre Summe bleiben,
  aber Überhangvereinigung und Materialdifferenz rechnen mit `CrossSection`.
  Gerichtete Außenringe und Löcher kommen ohne Vereinfachung aus den bereits
  ermittelten Materialflächen. Jede Schicht wird nur einmal konvertiert;
  Zwischenkonturen werden nicht nach GEOS zurückübersetzt. Die örtliche
  Säule behält ihren ursprünglichen Besitzer auch nach einer Teilung.
  `model_support` teilt die Materialkonturen unverändert zwischen Gruppen,
  `findings._column_under` innerhalb eines Befundlaufs. Lokale Caches leben
  nur für diesen Aufruf. Die GEOS-Öffnung und Kanalurteile bleiben erhalten.
  Die frühere GEOS-Prädikatgrenze entfällt für diese Differenzen; Prüfungen
  halten Abbruch, Löcher, Berührungen und gleiche Antworten auf mehreren
  Arbeitern weiterhin fest. CrossSection quantisiert intern: Vergleiche
  zwischen altem und neuem Weg prüfen deshalb relative Volumenabweichung
  bis 1e-9, Plattformvergleiche desselben Wegs weiter den Fingerabdruck.

## G-Code und Verbrauch

*Früher unter „Materialvorgaben und Verbrauch“.*

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


## Warnungen aus dem Slicerlauf

Ein erfolgreiches Prozessende bedeutet nicht, dass der Slicer keine Probleme
gemeldet hat. `handover._print_warnings` liest stdout und stderr innerhalb
des gemeinsamen `SLICER_OUTPUT_LIMIT` und übernimmt Prusas Warnblöcke ab
`print warning:` beziehungsweise `print_object warning:` einschließlich
ihrer Folgezeilen. Eine neue Warnung, eine native Fortschrittszeile oder die
Ausgabezeile beendet den vorherigen Block. Die freien Nutztextzeilen einer
Stabilitätsmeldung bleiben Nutztext, auch wenn ein Objektname wie eine solche
Steuerzeile aussieht. Zwischen den beiden Streams wird kein Block verbunden.

`_merged_warnings` ergänzt den vollständigen Prozessblock zu den gelesenen
G-Code-Kommentaren. Identische Blöcke werden einmal behalten; ein verkürzter
einzeiliger Kommentar darf dem vollständigen Block weichen. Unterschiedliche
mehrzeilige Meldungen bleiben dagegen erhalten, auch bei gleicher Überschrift.
Leerraum innerhalb von Objektnamen und ihre Schreibweise sind bedeutend.

Der Bericht führt diese Warnungen als `gcode.warning` mit Herkunft `gcode`.
Damit bleiben Aussagen des Slicers von Solidons eigener Schichtanalyse
unterscheidbar. Eine mit `Empty layer` beginnende Meldung trägt Fehlerstufe;
andere Warnungen behalten ihre Warnstufe. Der Originaltext bleibt im Befund
verfügbar und wird nicht durch den gekürzten Fehlerauszug des Prozesses ersetzt.
