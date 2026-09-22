# P1.6 — Formabweichung: Anschluss- und Messplan

Stand der lesenden Vorbereitung: 20.09.2026, HEAD `0094eea20`, daneben die
koordinierten, noch uncommittierten P1.2/P1.3-Änderungen. Dieser Plan ändert
keine Produktdatei und behauptet keinen bestandenen Lauf. P1.6 folgt als
eigenständiger Punkt nach dem nächsten Gate; der aktuelle P1.2-Stand wird
hierfür noch nicht erweitert.

## Auftrag und verbindliche Grenze

`konzepte/konzept-vollwertiges-cad-2026-09.md`, §13.10/P1.6 (Zeile 1011),
fordert Abstand je Facette zur bereits eingepassten Fläche, Legende,
Zahlenbereich und Zugang über den Prüfbericht. Die Fits aus P1.1/P1.2 werden
gelesen, nicht wiederholt. Bauplan §18.4 regelt den vorhandenen Kartenweg,
§18.5 die Merkmalsauswahl, Regel 18 die zweite Kodierung.

Der Bauplan enthält bisher sieben Karten; „Formabweichung“ ist die beauftragte
Ergänzung aus dem CAD-Konzept und RM-188. Die konkrete Statistik je Dreieck
ist dort noch nicht festgelegt. Der folgende Maximalabstand ist deshalb eine
begründete Umsetzungsempfehlung, keine schon vorhandene Zusicherung.

Gemessen wird die heutige Facettengeometrie gegen ihren vorhandenen
analytischen Träger. Daraus folgen weder ursprüngliche Konstruktionsabsicht
noch eine Unsicherheit des Nennmaßes, Montagefähigkeit oder Kollisionsfreiheit.
P4.0 verlangt später zusätzlich eine beidseitige Formprüfung des rekonstruierten
Körpers; eine gerichtete P1.6-Karte erfüllt diese Zusage allein nicht.

## 1. Vorhandene Anschlussstellen

Die Zeilennummern dienen der Orientierung im gelesenen Stand; parallel
bearbeitete Dateien können sich verschieben.

| Bereich | Bestehender Anschluss | Ergänzung für P1.6 |
|---|---|---|
| Kernkarte | `app/core/perceive/maps.py:55`, `MapKind`; `:133`, `AnalysisMap`; `:304`, `build` | Art `deviation`, expliziter Zweig zu einem gemeinsamen Kartenrechner. Der letzte Zweig von `build` fällt derzeit auf `support_map` zurück; eine neue Art darf dort nicht versehentlich landen. |
| Geometrieeingang | `maps._mesh_of`, `as_mesh_data(entry.mesh)` | Die Originaldreiecke beziehungsweise dieselbe native Anzeigetessellation verwenden, deren Indizes die Trägerdaten tragen. Kein Remeshing oder Dezimieren im Messpfad. |
| Kartenwahl | `app/ui/analysis_bar.py:57`, `MAP_ORDER`; ausdrückliche Eintragsliste in `AnalysisBar.__init__` | Beide Stellen um „Formabweichung“ mit verständlicher Erklärung ergänzen. |
| Legende | `MapLegend.show_map`, `_legend_entries` | Kontinuierliche Millimeterwerte, sichtbarer Umfang/Quelle, unbekannte Flächen, erforderliche numerische Begrenzung; alle Texte über Übersetzungskataloge. |
| Hintergrund | `app/ui/main_window.py:732`, `_MapWorker`; `:11343`, `_analysis_map` | Vorhandenen abbrechbaren Arbeiter und Anfrage-/Szenenkennung verwenden. Keine Messung im Qt-Hauptthread. |
| Ergebnisannahme | `_map_is_current`, `_map_ready`, `_show_map` | Abgebrochene/veraltete Ergebnisse bleiben wirkungslos; keine Teilkarte nach Abbruch veröffentlichen. |
| Kartencache | `_analysis_cache_key` und `_refresh` | Der Schlüssel enthält unter anderem Objekt, Art und Dreieckzahl; `_refresh` leert den Cache bei einer neuen Auswertung. Gleiche Dreieckzahl bei geänderter Geometrie oder geändertem Träger muss trotzdem einen neuen Wert liefern. |
| Darstellung | `app/ui/viewport.py:8196`, `set_analysis_map`; `:6601`, `_map_values`; `:6620`, `_map_clim` | Bestehende Skalarfarben verwenden. Der aktive Kartenkörper wird bereits nicht dezimiert (`:5578`); Werteanzahl und Dreieckzuordnung bleiben verbindlich. |
| Berichtsklick | `maps.map_for`, `maps.location_of`, `maps.focus_point`; `MainWindow._on_finding_activated` | Eigenen Befundcode vor dem allgemeinen `perceive.*`-Zweig auf `deviation` abbilden und den tatsächlichen Ort nach der asynchronen Rechnung zeigen. |

`AnalysisMap.values` enthält bereits genau einen Wert je Originaldreieck;
`NaN` bedeutet unbekannt. `low/high`, Schwelle und Werte bleiben physisch;
`display_values` und `display_limits` ändern nur die Farbdarstellung. Die
Einheit `mm` läuft in der Legende über den bestehenden Einheitenwechsel.
`source="internal"` bezeichnet interne Berechnung gegenüber G-Code und ist
keine Aussage über Mesh-Fit oder native Exaktheit.

## 2. Trägerdaten vor semantischem Zusammenfassen erhalten

Der derzeitige Vertrag `Feature.kind + params + face_indices` reicht nicht
für alle Flächen aus. Beleg: `perceive/features.py::_partial_cones_folded`
hängt die Dreiecke einer erkannten Halbkegel-Mündungsfase an das Langloch und
entfernt das eigenständige Kegelmerkmal. Das Langloch behält bewusst seine
Maße ohne Fase. Auch `slots_instead_of_half_bores` fasst mehrere geometrische
Träger zu einem verständlichen Kundenmerkmal zusammen.

Ein Slot besitzt daher nicht einen einzigen Zylinder- oder Kegelträger.
Ebenso bedeutet `kind="fillet"` nicht automatisch einen Zylinder: Kugel- und
Torusanteile müssen nach ihrer wirklich erkannten Flächenart behandelt werden.

Empfehlung: ein enges unveränderliches, rein abgeleitetes Teilträgerdatum
am bestehenden `Feature`, beispielsweise `surface_patches`. Es beschreibt
je ursprünglichem analytischem Patch dessen Art, validierte Trägerparameter,
Dreiecksindizes und Herkunft (`fit` oder `native`). Die Eigentümerschaft
folgt dem enthaltenden Feature, statt eine zweite Sammlung semantischer IDs
zu erfinden. Die genaue Benennung gehört zur Umsetzung; erforderlich ist
die Erhaltung derselben vorhandenen Lösung, nicht ein neuer Fitter.

Anschlüsse dieser Daten:

1. Bei der Veröffentlichung aus den vorhandenen `CylinderFit`, `ConeFit`,
   `SphereFit`, `TorusFit` beziehungsweise den nativen Flächenträgern die
   zugehörigen originalen Patchindizes mitnehmen. Die Karte ruft weder
   `detect` noch `fit_*` noch einen Nativerkennungsdurchlauf auf.
2. Slot-/Fasen-/Verrundungszusammenfassung übernimmt die Teilträger. Eine
   semantische Vereinigung vereinigt nicht automatisch die Trägerparameter.
3. `perceive/local.py` bildet bei örtlicher Erkennung bereits Featureindizes
   vom Ausschnitt zurück auf den Gesamtkörper ab; die Patchindizes müssen
   dieselbe Abbildung bekommen. Unvollständige Randbereiche bleiben unbekannt.
4. `matching.moved_features`/`transformed_features` führen Trägerorte,
   Achsen und Maße mit. Starre Verschiebung, Drehung und Spiegelung erhalten
   die Abstandswerte; gleichförmige Skalierung skaliert sie. Bei Scherung
   oder ungleichförmiger Skalierung nur mathematisch erhaltene Träger
   übernehmen; sonst invalidieren und den ohnehin zuständigen
   Erkennungspfad rechnen lassen. Kein heimlicher Wiederholungsfit der Karte.
5. Topologieänderungen/Neuindizierung dürfen nur nach nachgewiesener
   Dreieckszuordnung alte Träger übernehmen. Verlorene Randanteile werden
   nicht dem nächstgelegenen Träger zugeschlagen.
6. Bestehenden Merkmalscache in `features.py` und dessen Indexbudget um die
   zusätzlichen Patchindizes ergänzen. Keine zweite globale Cacheverwaltung.
7. `scene/cache.py::_feature_to_data/_feature_from_data` und die bestehende
   Cacheversion ergänzen; alter Cache führt zur regulären Neuberechnung.
   Speicher- und Plattencache, History, Undo/Redo und Laden führen dieselben
   abgeleiteten Daten. Keine neue Geometrie oder Fitlösung in Projektdateien
   speichern und deshalb auch kein neues Projektformat allein für P1.6.

Ungültige Achse, fehlender Radius, NaN/Inf, fehlende Herkunft, veraltete
Indizes oder widersprüchliche Teilträger erlauben keinen Wert null. Wo zwei
unterschiedliche Träger dasselbe Dreieck beanspruchen, ist die Zuordnung
unbekannt; weder Reihenfolge noch Minimum über beide darf darüber entscheiden.
Ein bloß vom Baustein deklarierter Durchmesser ist noch kein geprüfter Träger.

## 3. Daten-, Einheiten- und Messvertrag

Empfohlener Skalar für Originaldreieck `T_i` mit eindeutigem Träger `S_i`:

`d_i = max { dist(p, S_i) : p liegt im ausgefüllten Dreieck T_i }`, in mm.

Damit wird die ganze Facette berücksichtigt. Ein Eckpunktfit kann auf einem
regelmäßigen Vieleck exakt sein, während seine Sehne deutlich vom Kreis
abweicht. Eckpunktminimum, Eckpunktmaximum, Schwerpunktprobe oder mittlerer
Fitrest allein erfüllen diesen Vertrag nicht.

Die Fläche `S_i` ist der analytische Träger, nicht ein geschlossenes Werkzeug
mit Deckeln. Seine Zuordnung ist auf den bekannten Patch beschränkt; der
Träger selbst wird für den Abstand unbeschnitten ausgewertet. Ein Kegel
umfasst dabei die belegte Nappe, keinen willkürlich verlängerten Doppelkegel.

### Bereits vorhandene Parameterbedeutungen

| Träger | Größen aus der bestehenden Lösung | Punktabstand |
|---|---|---|
| Zylinder | Achsenpunkt `c`, normierte Achse `a`, `R=diameter/2` | Mit `q=p-c`, `z=q·a`, `rho=norm(q-z*a)`: `abs(rho-R)` |
| Kugel | Kugelmittelpunkt `C`, `R=diameter/2` | `abs(norm(p-C)-R)` |
| Kegel | `centre` ist der Achsenpunkt am weiten Ende, Achse zeigt Spitze → weites Ende; `angle` ist voller Öffnungswinkel in Grad, `R=diameter/2` | Halbwinkel `alpha=angle*pi/360`, Spitze `A=centre-a*R/tan(alpha)`. Für `q=p-A`, `z=q·a`, `rho=norm(q-z*a)`, `t=rho*sin(alpha)+z*cos(alpha)`: bei `t>=0` `abs(rho*cos(alpha)-z*sin(alpha))`, sonst `hypot(rho,z)`. |
| Ringtorus | Zentrum `c`, Achse `a`; `R=diameter/2` ist der große Ringradius, `r=tube_diameter/2` der Rohrradius | `abs(hypot(rho-R,z)-r)`; hier `R>r>0`, kein still angenommener Horn-/Spindeltorus. |

Alle Koordinaten und Radien bleiben float64 in mm; Winkelkonvertierung nur
an der Rechenstelle. Vorhandene numerische Konstanten prüfen Entartung,
Materialprofile verändern diese geometrischen Zahlen nicht. `residual`
eines vorhandenen Fits darf nicht direkt als Millimeterabweichung erscheinen.

### Ganze Dreiecke zuverlässig behandeln

Für Zylinder und Kugel sind enge direkte Extremwerte verfügbar:

- Kugel: kleinster Abstand des Mittelpunkts zum ausgefüllten Dreieck und
  größter Abstand zu seinen drei Ecken liefern das Radiusintervall.
- Zylinder: das Dreieck in die achsnormalen Koordinaten projizieren; kleinster
  Abstand des Ursprungs zum ausgefüllten projizierten Dreieck und größter
  Abstand zu seinen Ecken liefern das radiale Intervall. Auch zur Strecke
  zusammengefallene Projektionen korrekt behandeln.
- In beiden Fällen ist der Maximalfehler das Maximum der absoluten
  Abweichungen beider Intervallenden vom Radius.

Für Kegel/Torus muss die Umsetzung den Maximalwert einschließlich Kanten-
und Innenextrema nachweisen. Ein brauchbarer vollständiger Anschluss ist
eine begrenzte geometrische Optimierung über das Dreieck, keine erneute
Einpassung einer Fläche. Entweder werden sämtliche analytischen
Extremenkandidaten behandelt oder untere und obere Schranken geführt.

Eine nachvollziehbare konservative Schranke nutzt die 1-Lipschitz-Eigenschaft
des Punktabstands: für Mittelpunkt `q` eines Teildreiecks und größten
Eckabstand `h` ist dessen Maximum höchstens `dist(q,S)+h`; ausgewertete
Punkte liefern eine untere Schranke. Unterteilung kann das Intervall gezielt
schließen. Dies ist ein Beweisweg, keine Empfehlung für ungeprüft millionen-
faches blindes Unterteilen. Geometriespezifische engere Schranken und die
direkten Zylinder-/Kugelwege sind vorzuziehen.

Die numerische Zielbreite ist ausdrücklich zu benennen. `EPS_DISPLAY` kann
eine Anzeigeauflösung begründen, ist aber weder Fertigungsgrenze noch
automatisch hinreichend für einen behaupteten exakten Maximalwert. Falls ein
Intervall bleibt, werden konservative obere Werte nur als solche beschriftet
und mit der belegten Berechnungsbreite ausgegeben. Die Unsicherheit betrifft
ausschließlich die Rechnung an bekannter Geometrie, niemals ein erfundenes
Nennmaß. Ein nicht geschlossenes Intervall darf nicht als genauer Nullwert
oder bestandenes Formkriterium erscheinen.

`AnalysisMap.resolution` heißt derzeit ausdrücklich **Rasterweite** und wird
als „Raster …“ dargestellt. Es ist kein Platz für eine Fehlerobergrenze.
Falls der gewählte Rechner eine solche Grenze braucht, ist ein entsprechend
benanntes Ergebnisfeld samt eigener Anzeige erforderlich. Diese kleine
API-Entscheidung vor der Umsetzung festziehen.

Keine Geometrieänderung, Reparatur, Verschweißung, Jitter oder Voxelrechnung
im Kartenpfad. Abbruch vor, innerhalb und nach den begrenzten Arbeitsstücken
prüfen; keine abgebrochene Teilkarte cachen. Die vorhandene Dreiecksgrenze
bleibt ein Schutz, kein Nachweis eines erfüllten Laufzeitbudgets.

## 4. Verständlicher Kundenweg und Prüfbericht

1. Körper wählen → Analyse → **Formabweichung**.
2. Während der Rechnung bestehende Fortschritts-/Abbruchanzeige; alte Farben
   sofort entwerten, neue Kartenanfrage ersetzt die vorige.
3. Karte zeigt tatsächlichen Zahlenbereich ab null, Textlegende und Quelle.
   Keine selbst erfundene Rot-/Grün-Grenze aus Materialspiel oder Fitresidual.
4. Graue/ungefärbte Anteile erklären „keine sicher zugeordnete erkannte Form“.
   Eine vollständig unbekannte Karte zeigt keinen gemessenen Bereich 0–0.
5. Native Körper benennen den Gegenstand als Abweichung ihrer angezeigten
   Facetten vom nativen Träger. Das ist Tessellierungsabweichung, kein Fehler
   des nativen Körpers. Bei Mesh-Fits ist es Abweichung zur erkannten Form.
6. Der Prüfbericht bietet den gleichen Weg und einen nachvollziehbaren Ort.

Vorgeschlagene sichtbare Texte, noch keine Katalogänderung:

- „Formabweichung“
- „Zeigt, wie weit die Facetten von der erkannten Form entfernt sind.“
- „Größter Abstand je Facette; keine Aussage zum ursprünglichen Nennmaß.“
- „Bei diesem exakten Körper wird die Facettierung der Anzeige geprüft.“
- „Für diese Flächen ist keine erkannte Form sicher zugeordnet.“
- „Formabweichung anzeigen“

Der Bericht braucht einen wirklichen Erzeuger seines Befunds; ein Eintrag
in `map_for` oder eine als „geschätzt“ beschriftete Maßzahl erzeugt keine
anklickbare Zeile. Empfehlung: ein leichter Info-Befund je betroffenem Körper
aus den vorhandenen Trägerdaten, beispielsweise
`perceive.form_deviation_available`, mit Objekt und Merkmalbezügen. Er
behauptet keinen schon errechneten Maximalwert und erzwingt keinen Kartenlauf
bei jeder Auswertung. Seine Handlung beziehungsweise sein Klick öffnet die
Karte. Ein geschätzter Träger allein begründet keine Warnung „Form fehlerhaft“.

`map_for` muss den Code **vor** dem allgemeinen `perceive.* → features`
auflösen. Der bestehende Code `mesh.deviation` meint die Abweichung einer
Geometrieoperation; er darf nicht pauschal umgewidmet werden.

Für einen behaupteten örtlichen Höchstwert benötigt das Kartenergebnis den
tatsächlichen Zeugenpunkt und gegebenenfalls seinen Featurebezug. Der heutige
`focus_point` mittelt Dreiecksschwerpunkte; bei zwei gegenüberliegenden
Maxima läge das Ziel mitten im Hohlraum. Zudem gibt `location_of` bei
Featurebezügen schon vor fertiger Karte einen Schwerpunkt zurück. Der neue
Berichtsweg muss deshalb die endgültige Ortsmarke bewusst bis zum gültigen
Kartenergebnis zurückstellen. `_finding_awaiting_map` und `_map_ready` sind
der vorhandene Anschluss. Eine vorläufige Körperauswahl darf sofort erfolgen.

Legendenpräzision mitprüfen: `length` rundet regulär auf die Anzeigeauflösung.
Ein positiver Wert unterhalb dieser Auflösung darf keinen scheinbar
eindeutigen Nullnachweis erzeugen. Dafür eine verständliche Untergrenzen-
schreibweise beziehungsweise passende Zahlenpräzision im vorhandenen
Formatierungspfad verwenden; physische Werte nicht vorzeitig runden.

## 5. Unabhängige Gegenfälle vor der Umsetzung

Die direkten Rechentests liefern ihre Träger ausdrücklich analytisch.
Getrennte Anschlusstests benutzen einmal die reale Erkennung und beweisen
anschließend, dass die Karte deren Lösung nur liest.

| Gegenfall | Unabhängiges Soll / dadurch vermiedener Fehler |
|---|---|
| Regelmäßiger 16-Eck-Zylinder, R=15 mm | Größte Sehnenabweichung `15*(1-cos(pi/16))`, ungefähr 0,288221 mm. Alle Kreisecken können exakt passen; die Facette bleibt abweichend. |
| Bewusst polygonales Loch mit derselben Geometrie | Gleicher Messwert, keine Behauptung eines ursprünglich falschen Durchmessers und kein automatischer Glättungs-/Reparaturbeweis. |
| Kugeldreieck `(R,0,0)`, `(0,R,0)`, `(0,0,R)` | Alle Ecken liegen auf der Kugel; im ausgefüllten Dreieck beträgt das Maximum `R*(1-1/sqrt(3))`, am inneren Lotfuß. |
| Kegel mit analytisch vorgegebenem Halbwinkel 30° und 60° | Eine rein radiale Störung ist nicht schon der kürzeste Flächenabstand; die Normalprojektion berücksichtigt `cos(alpha)`. Punkte hinter der Spitze treffen nicht eine erfundene zweite Nappe. |
| Ringtorus R=10 mm, r=2 mm | Äquator außen bei Radius 12, innen bei 8, Scheitel bei z=2. Verwechslung von großem Durchmesser und Außendurchmesser wird rot; Innen- und Außenkrümmung getrennt prüfen. |
| Ein einzelner kleiner Ausreißer | Bekannte radiale Eckstörung bleibt im lokalen/globalen Maximum sichtbar und verschwindet nicht in Flächengewichtung oder Mittelwert. |
| Reine ebene Unterteilung jedes Originaldreiecks | Globales Maximum unverändert, jedes Teilmaximum höchstens das ursprüngliche Maximum; kein neues Erkennungsresultat voraussetzen. |
| Umgeordnete/unverschweißte deckungsgleiche STL-Ecken | Gleiche örtliche Werte nach bekannter Indexpermutation; keine Abhängigkeit von Vertexteilung. |
| Starr gedrehter, weit verschobener, gespiegelter Körper | Gleiche Werte in mm; Zeugenpunkt und Achsen wandern mit. Gleichförmige Skalierung skaliert Werte, Scherung invalidiert nicht erhaltene Träger. |
| Langloch mit Mündungsfase | Bögen und Fase lesen die erhaltenen getrennten Zylinder-/Kegelträger; die erweiterten Slotindizes werden nie insgesamt gegen einen einzelnen Kreis gemessen. |
| Örtliche Erkennung mit abgeschnittenem Patchrand | Globale Dreiecksindizes korrekt; der unbestimmte Rand bleibt unbekannt, ohne nächstgelegene Form zu erfinden. |
| Fehlender/mehrdeutiger Träger, NaN/Inf, Nullachse, falsche Indizes | Unbekannt samt Grund beziehungsweise regulärer verständlicher Rechenfehler; niemals grüner Nullwert, stiller Standardradius oder Standardachse +Z. |
| Nativer Körper bei zwei Tessellierungsfeinheiten | Native Trägerparameter unverändert, Facettenabweichung entsprechend verschieden. Mesh-/Native-Zwillinge messen die gleiche Größe gegen die jeweilige belegte Quelle. |
| Fitter und `detect` beim Kartenaufruf auf Ausnahme gesetzt | Der Kartenrechner bleibt mit bereitgestellten Trägern funktionsfähig; dadurch ist der Ausschluss einer zweiten Einpassung direkt belegt. |
| Abbruch vor/in/nach Rechnung, nachfolgende neue Anfrage | Keine Teilwerte, kein Cacheeintrag, keine verspäteten Farben; aktuelle Anfrage bleibt maßgeblich. |
| Cache, Undo/Redo, Speichern/Laden, gleicher Facecount bei neuem Träger | Identische aktuelle Daten nach Rundreise; veraltete Werte werden verworfen. Projektdatei enthält keine neue abgeleitete Geometrie. |
| Einheitenwechsel mm/Zoll und sehr kleine positive Werte | Physische Werte bleiben unverändert; Legende zeigt passende Einheit und keinen erfundenen Nullnachweis. |
| Berichtsklick bei leerem Kartencache | Passende Karte, Legende, Körperauswahl und echte Ortsmarke nach gültigem Ergebnis; keine Marke aus dem Mittel zweier gegenüberliegender Stellen. |

Für einen numerisch begrenzten Kegel-/Torusrechner kommen Fälle mit bekannten
analytischen Extremwerten und ein unabhängiges dichtes Referenzraster hinzu.
Das Raster ist nur Gegenprobe; die vom Produktionsrechner behauptete obere
Schranke benötigt ihren eigenen mathematischen Nachweis. Verfeinerung darf
das bewiesene Intervall nicht vergrößern.

## 6. Umsetzungspakete und Prüfumfang

1. **Rote Kernverträge:** explizite Sollträger, Sehnen-/Innenextrema,
   unbekannte Anteile, kein zweiter Fit, Abbruch. Bestehende `test_maps.py`
   nutzen; größere Trägerarithmetik gegebenenfalls als eigene reine Kerndatei.
2. **Abgeleitete Teilträger:** bestehende Erkennung → Zusammenfassung →
   örtliche Zuordnung → Transformation → beide Caches, einschließlich
   nativer und gemischter Zwillinge. Kartenrechner bleibt reiner Verbraucher.
3. **Kartenkern:** ein gemeinsamer geometrischer Rechner und `maps.build`,
   definierte Werte/Schranken, Quelle, unbekannte Teile und Zeugenpunkt.
4. **Oberfläche/Bericht:** Selector, Legende, Info-Befund, vorhandener
   asynchroner Weg, fokussierter Ort und übersetzte Texte. Karten- und
   Quellenkarten-Doku auf den zuständigen Ebenen nachziehen.
5. **Gezielte Kern-/Statikprüfung**, danach koordiniertes Entwicklungstor
   durch Root. Fensterdateien und Leistung bleiben bis zum Release offen.

Vorhandene geeignete Kerntests: `tests/test_maps.py` (unter anderem
`test_a_map_stops_when_nobody_waits_for_it_any_more`,
`test_a_finding_picks_its_map`,
`test_an_analysis_map_works_on_an_exact_body`),
`tests/test_map_display_scale.py`; für Erhalt `tests/test_matching.py`,
`tests/test_cache.py`, passende native Flächentests und die neuen
`tests/test_round_surface_measurements.py`.

**Ausschließlich beim Release ausführen:** `tests/test_analysis_ui.py`
als gesamte Fensterdatei. Dort erweitern insbesondere
`test_every_map_of_the_table_is_offered`,
`test_a_measured_map_shows_its_range_and_its_origin`,
`test_constant_map_legend_does_not_invent_a_larger_measured_range`,
`test_a_map_request_discards_old_colours_and_late_replies`,
`test_a_report_click_keeps_its_mark_across_the_async_map` und
`test_a_cached_map_replaces_the_shown_one_in_a_single_pass`.
Die Rendererprüfung `test_cell_colours_categorical_and_mapped` belegt bereits
Skalarfarben; sie ersetzt weder die Dreieckszuordnung noch den Kundenweg.
Vor einem Lauf entscheidet der gemeinsame Fenstercollector über die ganze
Datei, keine handgepflegte Ausnahme.

Leistung erst beim Release auf Referenzhardware messen. Weder die gelesene
Grenze von 900.000 Dreiecken noch eine später grüne Kernsammlung beweist,
dass eine neue Extremwertsuche das Zeit-/Speicherbudget einhält.

## Ergebnis dieser Vorbereitung

Die vorhandene asynchrone Kartenanzeige ist wiederverwendbar. Vor ihr fehlen
ein vollständiger erhaltener Teilträgervertrag, eine ausdrücklich definierte
Facettenstatistik und der echte Berichtsbefund samt Ortsanschluss. Alle drei
sind Teil von P1.6. Diese Vorbereitung hat nur gelesen und diese Plandatei
geschrieben; keine Produkt-/Teständerung, kein Fenster-/Leistungslauf, kein
Commit und keine Websiteänderung.
