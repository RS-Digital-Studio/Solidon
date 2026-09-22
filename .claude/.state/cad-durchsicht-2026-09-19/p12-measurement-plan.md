# P1.2 — Maßverträge für Kegel, Kugel und Torus

Arbeitsnotiz aus der abgeschlossenen lesenden Prüfung vom 20.09.2026.
Quelle: `konzepte/konzept-vollwertiges-cad-2026-09.md`, §4.3 und §13.2
(P1.2); verbindliche Grundlagen: Bauplan §21.1 und AGENTS-Regeln 6 und 21.
Die Notiz plant den nächsten Umsetzungsblock. Die ursprüngliche Planung
beruht ausschließlich auf Lesen; die anschließend ausdrücklich beauftragte
Kernsonde und ihre Messergebnisse stehen getrennt am Ende. Produktänderung
und P1.2-Abnahme sind damit nicht erfolgt. Zeilennummern beziehen sich auf
den gelesenen Arbeitsstand; die benannten Funktionen sind die Anker.

## Bereits anderweitig behoben

`matching.transformed_features` führte den dimensionslosen `residual` als
Länge und skalierte ihn bei gleichförmiger Vergrößerung mit. Root hat diesen
Anschluss im laufenden P1.1-Vertrag korrigiert und drei zuvor rote Fälle grün
geprüft. Das ist keine verbleibende P1.2-Arbeit. Neue Diagnosewerte müssen
weiterhin ausdrücklich zwischen relativen Fehlern und Längen unterscheiden.

## Konkrete Befunde

### 1. Native Kugel: Mittelpunkt und Materialseite

`app/core/brep/features.py::_describe`, Kugelzweig um Zeile 941:

- `sphere.params["centre"]` erhält `middle` aus `properties(face).centre`,
  also den Flächenschwerpunkt. Der Kugelmittelpunkt steht bereits in
  `ball.Location()`. Bei einer Halbkugel liegt der Flächenschwerpunkt um
  R/2 neben dem Kugelzentrum. Mesh-`SphereFit.centre` bezeichnet dagegen
  den Kugelmittelpunkt.
- `hollow = not _point_in_material(inside, ball.Location())` bestimmt die
  Rolle durch die Lage des Kugelzentrums im gesamten Solid. Eine massive
  obere R8-Kalotte mit z ≥ 4 hat ihr Zentrum außerhalb ihres Materials und
  wird deshalb als Pfanne statt als Kuppel ausgegeben. Der Helfer akzeptiert
  ausschließlich `TopAbs_IN`.
- `geom/prepare_ops.py::_feature_solid`, um Zeile 682, baut eine Kugel mit
  diesem Durchmesser und diesem Mittelpunkt als tatsächliches Werkzeug.
  Matching und Maßbezüge lesen denselben Ort.

Enger Fix: Für ein echtes `sphere`-Merkmal `ball.Location()` übernehmen;
die Materialseite aus der orientierten tatsächlichen Flächennormale relativ
zum Kugelzentrum bestimmen. Die vorhandene Normalenprobe in
`brep/canonical.py::_point_and_normal` beziehungsweise der Torusanschluss
ist der Wiederverwendungsweg. Keine zweite Mittelpunkt-im-Material-Heuristik
bauen. Die kugelige Eckverrundung bleibt fachlich eine eigene Ausgabe; ihren
Anzeigevertrag nicht blind mit dem Kugelmerkmal gleichsetzen.

### 2. Vollkörper-Größenfilter sperren gültige Teilflächen aus

`perceive/features.py::_fitted.classify`, um Zeile 1450, fordert über
`_fits_in_the_body_by_size` für Kugeln und Tori den Durchmesser des
vollständigen analytischen Trägers innerhalb der Körperabmessungen.
Die vorhandene echte R80/5°-Kalotte ist quer nur ungefähr 14 mm breit;
ihr R80-Kandidat kann deshalb nicht in `spheres` gelangen, obwohl die
örtliche Bestimmtheitsprüfung diese Kalotte ausdrücklich zulässt.
Entsprechende Vollkörperannahmen bestehen für Kegel in
`_fits_in_the_body`.

Die positiven Tests der drei Fit-Qualitätsdateien übergeben bisher häufig
eine vorgegebene Fitliste an `detect_spheres`, `detect_cones` beziehungsweise
`detect_tori`. Damit umgehen sie diesen Eintritt der echten Klassifikation.

Enger Fix: Teilflächen an ihrer örtlichen Bestimmtheit und ihren vollständig
belegten Originalflächen prüfen, nicht daran, ob der nicht vorhandene
Vollkörper in ihre Abmessungen passen würde. Die Schutzfälle gegen große
Freiform-Phantome bleiben bestehen; die Größenschranke nicht pauschal löschen.
Rohfit und tatsächliches `detect` müssen getrennt geprüft werden.

### 3. Kegelwinkel kommt aus Facettenebenen

`perceive/features.py::fit_cone`, um Zeile 3436, liest den Radius und die
größte axiale Ausdehnung bereits aus Ecken, den Halbwinkel jedoch über
`asin(abs(mean(normals @ axis)))` aus Facettennormalen.
Für einen regelmäßig facettierten Kegel folgt analytisch:

```text
tan(gemessener Halbwinkel) = tan(Sollhalbwinkel) · cos(π/n)
```

Radius, Winkel und daraus rekonstruierte Spitze beschreiben dadurch nicht
dasselbe analytische Modell. Ungleiche Winkelschritte und einseitige
Unterteilung können zusätzlich Achse und Spitze gewichten. Die
Spitzengleichung wird anders als Kugel- und Torusrechnung noch direkt mit
Weltkoordinaten aufgebaut.

Enger Fix: Normalen zur Formwahl und Initialisierung behalten; die
endgültigen Maße gemeinsam an belegten Mantelpunkten bestimmen. Vor der
Rechnung lokal zentrieren. Ein stumpfbeschnittener Kegel braucht eine
gemeinsame Achse und Spitze sowie einen konsistenten Winkel; ein weiterer
unabhängiger Maximalradius ist keine Ausreißerkorrektur.

### 4. Kugelradius beschreibt Facettenebenen, Torusradien Schwerpunkte

`perceive/features.py::fit_sphere`, um Zeile 3512, passt mit
`n · p = n · c + R` die Ebenen der Facetten an. Deren Abstand ist nicht
allgemein der Radius der Kugel durch die belegten ursprünglichen Punkte.
Bei ungleichmäßiger Vernetzung beziehungsweise Unterteilung ändern sich
auch die Gewichte der Facetten. Die anschließende Güteprüfung an
Dreiecksschwerpunkten trennt diesen Maßfehler nicht von der Facettierung.

`fit_torus`, um Zeile 3566, übergibt Dreiecksschwerpunkte und
Facettennormalen an `fit_torus_samples`. Der Meridiankreisfit verwendet
dadurch innere Sehnenpunkte. Ring- und Röhrenradius sowie bei Teilabdeckung
die Achslage müssen unabhängig gegen Sollwerte geprüft werden.

Eine gemeinsame Umstellung aller Fits auf sämtliche Vertices reicht nicht:
nachträgliche Unterteilung erzeugt zusätzliche Punkte auf Sehnen. Benötigt
werden geometriespezifisch belegte ursprüngliche Kontur-/Mantelpunkte und
ein separater Nachweis der tatsächlichen Netzabweichung. Vorhandene
Normalen-, Bestimmtheits- und Gegenformprüfungen dürfen nicht durch eine
größere Restfehlerschranke ersetzt werden.

### 5. Vorzeitige Rundung

`detect_cones`, `detect_spheres`, `detect_tori` und die native Kugelausgabe
runden Durchmesser beziehungsweise Winkel bereits im Kern. Volle
Rechengenauigkeit muss bis zu den Verbrauchern erhalten bleiben. Die
Formatierung in `ui/labels.py` und `perceive/digest.py` ist der Anzeigeort.
Eine Rundung im Fit-Ergebnis ist keine Aussage über seine Unsicherheit.

## Vorhandene Testgrundlage und fehlende Maßfälle

| Form | Vorhandener Korpus und Tests | Analytische Ergänzungen |
|---|---|---|
| Kegel | `plate_countersunk.stl`, `plate_countersunk_blind.stl`, `plate_chamfer_and_taper.stl`; `test_cone_fit_quality.py`, `test_cone_oblique_boundary_fit.py`, `test_cone_vertex_support.py` | Vollkegel und Stumpf; vorhandener 45°-Teilbogen eines 60°-Kegels; schiefe Ränder mit 120/64 Punkten; ungleiche Winkelschritte; zusätzliche Sehnenpunkte; Innen/Außen |
| Kugel | `sphere_socket.stl` mit R8 und Zentrum `(0, 0, 7.5)`; beide R80/5°-Kalotten; `ambiguous_sphere_ribbon.stl`, `indeterminate_sphere_cap.stl`, `near_sphere_ellipsoid.stl`; `test_sphere_fit_quality.py` | Vollkugel, Halbkugel, massive flache Kalotte; UV- und Ikosaedervernetzung; ungleichmäßige Unterteilung; einzelne Ausreißer |
| Torus | `torus_ring.stl` mit R20/r5, `post_with_fillet.stl`; `test_torus_fit_quality.py` | Ring- und Röhrenbogen getrennt beschneiden; unterschiedliche Auflösung beider Richtungen; R17/r3-Zwillinge aus `test_brep_surfaces.py`; Wulst/Kehle; getrennte Ringstücke |

Die analytischen Gegenkörper werden aus unabhängigen Sollparametern
aufgebaut. `tests/data/make_corpus.py` enthält die Quellen der vorhandenen
Korpusdateien. Für native Zwillinge stehen die OCP-Konstruktoren und
vorhandenen STEP-Rundreisen zur Verfügung; keine nur vermuteten
registrierten Erzeuger voraussetzen.

Für positive Reihen prüfen:

- Radien, vollständigen Mittelpunkt, Kegelspitze und Winkel; gerichtete
  Kegelachse, vorzeichenunabhängige Torusachse; belegte Innen-/Außenrolle.
- Reine Dreiecksunterteilung getrennt von einer neuen Tessellierung.
  Zusätzliche Sehnenpunkte sind keine neuen Punkte der analytischen Fläche.
- Rotation, Spiegelung, große Translation und gleichförmigen Maßstab.
- Beide Qualitäten und ungleichmäßige Punktdichte; Verschiebung darf weder
  Kondition noch Formentscheidung von Weltkoordinaten abhängig machen.
- Unveränderte Ausgangsgeometrie und Originalflächenzuordnung.

Testtoleranzen aus Eingabepräzision und belegter Bestimmtheit ableiten,
nicht aus den bisherigen breiten Erkennungstoleranzen. Eine feine STL mit
float32-Koordinaten und ein direkt erzeugter float64-Sollkörper haben nicht
dieselbe Eingabeauflösung. Die bestehenden Freiform-, Ellipsoid-,
Extrusionswand-, instabilen Teilring- und Vertex-Ausreißerfälle bleiben
fachliche Absagen. Keine pauschale Mindestwinkelgrenze für alle Tori
einführen; ein einzelner instabiler Ausschnitt belegt eine solche nicht.

## Enger Implementierungsablauf

1. **Verträge und reproduzierende Kerntests zuerst.** Die bestehenden
   Testdateien um unabhängige Maße ergänzen. Neben Rohfits ausdrücklich
   `detect`/`features_of` abnehmen, damit Größenfilter, Formwahl und
   Veröffentlichungsgrenzen wirklich durchlaufen werden.

2. **Belegte Punkte gemeinsam aufbereiten, Formen getrennt einpassen.**
   Die vorhandene Zuordnung deckungsgleicher Ecken und angrenzender
   Facetten wiederverwenden. Unterteilung anhand der tatsächlichen
   Facettenstruktur behandeln. Keine allgemeine konvexe Hülle über Kugel
   oder Torus und keine Kopie des Zylindermaßverfahrens für alle Formen.
   Lokal zentrierte float64-Rechnung, deterministische Initialisierung und
   begrenzte Verfeinerung verwenden. Normalen-, Ausreißer- und
   Bestimmtheitsprüfungen bleiben eigenständige Nachweise.

3. **Sämtliche Fit-Einstiege anschließen.** In
   `app/core/perceive/features.py` neben `fit_cone`, `fit_sphere`,
   `fit_torus` auch `_fitted.classify`, `_large_facet_faces`,
   `_a_ball_fits_far_better`, `_merged_cones`, `_merged_tori` und
   `_cylinder_beside_a_torus` berücksichtigen. Eine neue Fehlerdefinition
   darf die Formauswahl nicht unbeabsichtigt umdrehen. Neue Schleifen lesen
   den bestehenden Abbruchrückruf und die vorhandenen Arbeitsgrenzen;
   Abbruch veröffentlicht weder Teilmerkmale noch einen Teilcache.

4. **Den nativen Toruszwilling erhalten.**
   `app/core/brep/canonical.py::_torus_surface`, um Zeile 391, verwendet
   bereits `fit_torus_samples` mit echten NURBS-Punkten und Ableitungen.
   Danach prüft `_torus_matches` die vollständige rationale Trägerfläche.
   Mesh-spezifische Facettenkorrekturen gehören vor den gemeinsamen
   Kandidatenweg und dürfen dessen native Annahmen nicht verändern.
   `test_brep_surfaces.py` hält native Maße, Teilflächen, NURBS-Gegenform,
   Naht, große Lage, Originalerhalt und Arbeitsgrenze. Diese Nachweise
   bleiben bestehen; bloße Stichproben ersetzen den Flächennachweis nicht.

5. **Verbraucher mit echten Ergebnissen prüfen.**
   `geom/prepare_ops.py` baut Kugelwerkzeuge und Kegelabschnitte aus den
   Maßen; besonders `_feature_solid` und `_measured_section` müssen ihre
   Lage und Geometrie treffen. `relations.alike_for_action` vergleicht
   Zielmaße und tatsächliche Flächen für Gruppen. `matching` und
   `local.detect_known` tragen Lage, Maße und IDs nach. Die gemeinsame
   Auskunft muss außerdem `scene.placement`,
   `maps._radii_from_features`, `digest` und `ui/labels` erreichen.
   Keine zweite Messung für Baum, Dialog, Karte oder Agent hinzufügen.

6. **History- und Persistenzanschluss.** Mindestens je Form ein echter
   Auftrag über Qualitätswechsel, Folgeoperation, Undo/Redo, Cache und
   Speicherung/Wiederöffnung. Die maßführende Fläche und ihre Kennung
   prüfen, nicht nur Objektzahl oder Volumen. Dazu bestehende
   `test_features.py`, `test_feature_groups.py`, `test_matching.py`,
   `test_maps.py`, `test_prepare.py`, `test_geometry_review_regressions.py`
   und `test_local_detection.py` gezielt erweitern, soweit der jeweilige
   Verbraucher betroffen ist.

Neue Diagnosewerte benötigen ausdrücklich Einheit und Bedeutung. Relativer
Fitfehler, absoluter Fehler belegter Punkte, tatsächliche Netzabweichung
und Fertigungsspiel sind verschiedene Größen. Ältere fehlende Auskünfte
sind keine Nullabweichung. Transformation und
`relations._DIAGNOSTIC_PARAMETERS` müssen neue Auskünfte mitführen;
die Cacheversion gehört in den koordinierten Abschluss. P1.6 soll diese
gemeinsamen Fits später lesen, ohne einen weiteren Fit zu berechnen.

## Prüf- und Abschlussgrenze

Der lesende Plan enthält keine neuen gemessenen Fitwerte. Die genannten
Auswirkungen folgen den vorhandenen Gleichungen und Kontrollflüssen.
Ein tatsächlicher roter Gegenfall und sein grüner Nachlauf gehören jeweils
zum folgenden Implementierungsschritt.

Während der Entwicklung nur betroffene Kerntests und statische Prüfungen;
funktionale Abbruch-/Arbeitsgrenzentests sind keine Geschwindigkeitsmessung.
Fensterdateien und Leistungsprüfungen ausschließlich beim Release.
Bediennachweise für aktuelle Maße, Gruppen, Vorschau und Übernahme dürfen
vorbereitet werden, gelten bis dahin aber nicht als bestanden.

## Ausgeführte Kernsonde: native Kugelmitte und Materialseite

Am 20.09.2026 wurde ausschließlich die zusätzlich beauftragte analytische
Sonde ausgeführt. Kein Produktcode wurde dafür geändert.

- Skript: [p12-native-sphere-probe.py](p12-native-sphere-probe.py)
- Vollständige Werte: [p12-native-sphere-probe.json](p12-native-sphere-probe.json)
- Lesbares Protokoll: [p12-native-sphere-probe.txt](p12-native-sphere-probe.txt)
- Tatsächlicher Prozess-Exit: [p12-native-sphere-probe-exit.txt](p12-native-sphere-probe-exit.txt),
  **1 wegen beobachteter Vertragsverletzungen**, kein grüner Prüflauf.

Aufruf aus dem Repository:

```powershell
.venv\Scripts\python.exe .claude/.state/cad-durchsicht-2026-09-19/p12-native-sphere-probe.py
```

Stand: HEAD `7eea517fc6102496ae081d8e5c6ae158fbc63029` mit den parallelen
Arbeitsbaumänderungen. Die SHA-256-Werte der sechs gelesenen Produktmodule
stehen vor und nach der Sonde im JSON und waren während des Laufs gleich.
Umgebung: `cadquery-ocp-novtk` und `cadquery-ocp-proxy` 8.0.1.0.0,
NumPy 2.5.3, SciPy 1.18.1, trimesh 5.1.0. Tatsächliche Tessellierungsabweichung:
`DEFLECTION = 0.05 mm`; kein Zufall und keine Qualitäts-/Leistungsmessreihe.
Alle Nutzerverzeichnisse waren bereits vor den Produktimporten in einen
privaten temporären Bereich umgeleitet.

### Unabhängige Konstruktion und Sollwerte

`BRepPrimAPI_MakeSphere` erzeugt jeweils eine geschlossene massive R8-Kugel
mit eingeschränktem Breitenwinkel:

- Halbkugel: z ≥ 0, Höhe 8 mm, Volumen `1024π/3 = 1072.330292425316 mm³`.
- Obere Kalotte: z ≥ 4, Höhe 4 mm, Volumen `320π/3 = 335.1032163829113 mm³`.

Beide Körper sind außen konvex: **`recess=False`** ist in allen Lagen das
Soll. Die Kugelzentren liegen vor der Transformation bei `(0, 0, 0)`.
Die Flächenschwerpunkte ihrer Kugelhäute liegen dagegen bei `(0, 0, 4)`
beziehungsweise `(0, 0, 6)`; diese unabhängige Flächenformel erklärt die
beobachteten falschen Merkmalszentren.

Drei Lagen je Körper: Ursprung; Translation `(37, -19, 83)`;
dieselbe Translation plus Drehung um 0.73 rad um die normierte Richtung
`(1, 2, -0.5)`. Die Drehung erfolgt um den ursprünglichen Kugelmittelpunkt.
Beide Quellkörper sind nativ gültig. Die unabhängig gelesenen nativen
Volumina weichen in allen sechs Fällen um weniger als `1e-9 mm³` vom
analytischen Soll ab. Die Halbkugel hat 912 Dreiecke, davon 872 Kugelhaut;
die obere Kalotte 580, davon 540 Kugelhaut.

### Tatsächlich veröffentlichte native Kugelmerkmale

Alle sechs `features_of`-Aufrufe liefern genau ein `sphere` mit Ø16 mm.
**Alle sechs liefern fälschlich `recess=True`.** Die Tabelle rundet nur zur
Darstellung; das JSON enthält sämtliche gespeicherten Werte.

| Körper / Lage | Sollmittelpunkt in mm | Istmittelpunkt in mm | Ortsfehler |
|---|---|---|---:|
| Halbkugel, Ursprung | `(0, 0, 0)` | `(0, 0, 4)` | 4 mm |
| Halbkugel, versetzt | `(37, -19, 83)` | `(37, -19, 87)` | 4 mm |
| Halbkugel, gedreht/versetzt | `(37, -19, 83)` | `(39.231290, -20.358336, 86.029236)` | 4 mm |
| Kalotte, Ursprung | `(0, 0, 0)` | `(0, 0, 6)` | 6 mm |
| Kalotte, versetzt | `(37, -19, 83)` | `(37, -19, 89)` | 6 mm |
| Kalotte, gedreht/versetzt | `(37, -19, 83)` | `(40.346935, -21.037504, 87.543854)` | 6 mm |

Damit sind beide nativen Befunde reproduziert. Die falsche Rolle betrifft
auch die Halbkugel: Ihr Zentrum liegt auf der ebenen Abschlussfläche und
ist für den verwendeten Klassierer nicht `TopAbs_IN`.

### Tatsächlicher Mesh-Zwilling

Die Sonde benutzt ausdrücklich `detect(as_mesh_data(solid))`, ohne
vorbereitete Fitlisten oder künstlich erzeugte Merkmale.

| Körper / Lage | Kugelergebnis | Gemessenes Zentrum in mm | Ø / Ortsfehler / Rolle |
|---|---|---|---|
| Halbkugel, Ursprung | eine Kugel | `(0.0009818904, 0, 0.0162816600)` | Ø15.9251 mm; Fehler 0.0163112403 mm; `recess=False` |
| Halbkugel, versetzt | eine Kugel | `(37.0009818904, -19, 83.0162816600)` | Ø15.9251 mm; Fehler 0.0163112403 mm; `recess=False` |
| Halbkugel, gedreht/versetzt | **keine Kugel** | nicht vorhanden | eine `curved_face` und eine `face` |
| Kalotte, Ursprung | **keine Kugel** | nicht vorhanden | eine `curved_face` und eine `face` |
| Kalotte, versetzt | **keine Kugel** | nicht vorhanden | eine `curved_face` und eine `face` |
| Kalotte, gedreht/versetzt | **keine Kugel** | nicht vorhanden | eine `curved_face` und eine `face` |

Der gemessene Durchmesser der beiden erkannten Mesh-Halbkugeln liegt
0.0749 mm unter dem analytischen Soll. Die Mesh-Ortsabweichung wird im
Skript auch gegen `EPS_GEOM` markiert; das ist hier ein Abweichungsmelder,
keine neu beschlossene allgemeine Genauigkeitszusage für fremde Netze.
Die fehlende beziehungsweise lageabhängige Erkennung ist eine reale
End-to-End-Beobachtung. Diese kleine Sonde isoliert deren weitere Ursache
nicht; der Größenfilter bleibt dafür ein bereits am Kontrollfluss
belegter Anschluss des Implementierungsplans.

### Originalerhalt und Grenzen

In **allen sechs Fällen** sind sämtliche fünf Kontrollen wahr:

1. Native ursprüngliche Konstruktorform vor/nach der privaten Transformation.
2. Native Solid-Bytes vor/nach `features_of`.
3. Native Solid-Bytes vor/nach dem Abruf der Tessellierung.
4. Native Solid-Bytes vor/nach vollständiger Mesh-Erkennung.
5. Mesh-Punkt- und Dreiecksdaten vor/nach `detect`.

Die geprüfte Erkennung verändert die Originalgeometrie in dieser Sonde
somit nicht. Mittelpunkt und Materialseite sind dennoch falsch; Erhalt
allein wäre kein Maßnachweis.

Ein erster Start brach vor der Geometrieauswertung ausschließlich am
Distributionsnamen der Versionsauskunft ab: installiert ist
`cadquery-ocp-novtk`, nicht `cadquery-ocp`. Nach dieser Korrektur im
Sondenskript lief die vollständige Sechserreihe und lieferte die oben
aufgezeichneten Ergebnisse. Keine Fensterdatei, Leistungsprüfung,
Vollsuite oder Nutzerdatei wurde verwendet. Die Sonde ersetzt weder
die anschließenden Regressionstests noch die Release-Abnahme.
