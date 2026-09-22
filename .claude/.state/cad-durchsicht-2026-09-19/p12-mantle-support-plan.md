# P1.2 — Mantelpunkte vor dem Endmaßfit

Lesender Anschluss an [p12-measurement-plan.md](p12-measurement-plan.md),
20.09.2026, HEAD `7eea517fc` mit eingefrorenen P1.1-/P2-Änderungen.
Grundlage: CAD-Konzept §4.3/§13.2, Bauplan §21.1 und die aktuellen
Wahrnehmungsfunktionen. **Entwurf, keine ausgeführte Sonde oder Abnahme.**
Nur diese Arbeitsnotiz wird geschrieben; Produkt und Tests bleiben stehen.

## Gemeinsamer Weg: der unveränderte Netzknick, nicht jede gespeicherte Ecke

1. **Einen lokalen Index je Fitfleck aufbauen.** Die `np.unique`-Zuordnung
   von Koordinaten und Normalen-Inzidenzen aus `fit_cylinder` herauslösen,
   etwa als privaten Helfer `_surface_support`. Deckungsgleiche STL-Ecken
   erhalten einen gemeinsamen Leseindex, die ursprünglichen Dreiecksnummern
   bleiben erhalten. Keine Verschiebung, Rundung oder Verschweißung der Quelle.
   Vor Quadrat-/Kreuzprodukten lokal zentrieren und für den Löser skalieren.

2. **Kinder einer ebenen Facette haben zusammen genau deren Gewicht.**
   `body.facets`, `face_adjacency`, `_facet_centre` und `area_faces` liefern
   vorhandene Bausteine. `body.facets` ist allein kein Ebenenbeweis:
   `trimesh.graph.facets` gruppiert über eine Radius/Spannweiten-Heuristik.
   Kandidatengruppen gegen eine gemeinsame lokale Ebene, gleiche Orientierung
   und alle zugehörigen Punkte prüfen; nicht über fortgesetzte kleine Winkel
   eine gekrümmte Kette zusammenziehen. Einzelne Dreiecke ergänzen.
   Numerische Ebenengleichheit und Formtoleranz bleiben getrennt; vorhandene
   `EPS_GEOM`-/`weld_tolerance`-Verträge nicht als Fertigungsspiel auslegen.

3. **Den Normalenfächer am Ort auswerten, nicht seine Dreieckszahl.**
   Ein innerer Unterteilungspunkt trägt eine Ebene; ein Punkt auf einer alten
   geraden Sehne höchstens zwei. Ein nicht entfernbarer Netzeckpunkt trägt
   mindestens drei unabhängig belegte Mantelfacetten. Identische Ebenen
   mehrfach zu zählen würde gerade einseitige Unterteilung wieder belohnen.
   Doppelte Gegenflächen und getrennte Fächer an einem Berührpunkt gelten
   nicht gemeinsam als Stützung. T-Verbindungen dürfen weder Kindzahlen
   erhöhen noch wegen fehlender identischer Kantenindizes echte Fächer löschen:
   geometrisch gleiche Punkte und Teilkanten nur im privaten Leseindex ordnen.

4. **Drei Rollen getrennt halten:** maßführende Netzecken, gerade
   Zweifacettenketten und bloße Flächen-/Trimmbelege. Kugel und Torus benutzen
   zunächst die erste Gruppe. Ketteninnere und reine Schnittpunkte gehen
   weiterhin in Flächen-, Ausreißer- und Normalenprüfungen ein, aber nicht in
   ihre Radiusgleichung. Die Stützung belegt eine nicht durch lineare
   Unterteilung entstandene Netzecke; erst der Formfit belegt deren Zugehörigkeit
   zum geschätzten analytischen Träger. Sie beweist keine Konstruktionsabsicht.

5. **Kegel-Ausnahme geometrisch belegen.** Gerade Zweifacettenketten können
   echte Mantellinien sein: Ihre Geraden müssen zur selben Kegelspitze laufen
   und denselben Öffnungswinkel tragen. Erst dann dürfen auch ihre Punkte das
   Maß stützen. Damit bleiben ein regulärer Kegelstumpf ohne innere Punkte und
   ein quer durch seine Facetten geschnittener Rand möglich. Kollineare
   Ketteninnere für die Gewichtung entfernen; sie liefern keine zusätzliche
   Information. Bei ungleichen Rändern/verkanteten Dreiecken zuerst die
   stärker gestützten Punkte einpassen und den Mantellinienbeleg danach prüfen.

**Grenze bei Trimmung:** Ein Randpunkt zwischen nur zwei Mantelfacetten kann
ein ursprünglicher Abtastpunkt oder ein nachträglicher Sehnenschnitt sein.
Ohne erhaltenen Fächer beziehungsweise beim Kegel den Mantellinienbeleg ist
das aus dem Netz nicht eindeutig rekonstruierbar. Kein pauschales Aufwerten
von Randknicken und keine konvexe Hülle über Kugel/Torus. Reichen die sicheren
Stützen nicht, bleibt das Maß unbestimmt; nicht alle Vertices nachladen.

## Endmaße gemeinsam an den belegten Punkten bestimmen

Einmal je ursprünglicher Stütze gewichten. Facettennormalen zur Initialisierung
mit zusammengefassten Facettenflächen gewichten; die Summe der am Eckpunkt
verbliebenen Kinddreiecke wäre bei einseitiger Unterteilung gerade nicht
invariant. Eine neue Tessellierung mit neuen echten Flächenpunkten ist dagegen
eine neue Eingabe; sie muss dasselbe unabhängige Soll treffen, nicht dieselben
Rauschreste erzeugen.

| Form | Start und gemeinsamer Endfit | Bestimmtheit und gültiger Bereich |
|---|---|---|
| Kugel | Lokal skaliertes lineares System `[2x, 2y, 2z, 1] -> x²+y²+z²`; anschließend bei Bedarf geometrisch `norm(p-c)-R` minimieren. Mittelpunkt und Radius gemeinsam, keine Facettenebenen als Radius. | Rang vier; SVD des geometrischen Jacobis. `_sphere_is_recognisable` behält zwei Krümmungsrichtungen und lokale Güte, erhält dafür unterteilungsinvariante Gewichte. Die bestehenden 5°-/2°-/Band-Gegenfälle bleiben maßgeblich. |
| Kegel | Vorhandene Normalen-/Ebenengleichungen nur lokal zentrierte Initialisierung. Gemeinsamer geometrischer Fehler `rho*cos(alpha)-z*sin(alpha)` mit `z=(p-apex)·axis`, `rho=norm((p-apex)-z*axis)`. Spitze, zwei Achsrichtungen und Winkel gemeinsam verfeinern. | Sechs bestimmte Freiheitsgrade; eine gerichtete Kegelseite, gültiger vorhandener Winkelbereich. `centre=apex+axis*z_max`, `radius=z_max*tan(alpha)` aus demselben Modell; echte Trimmgrenzen bestimmen `z_max`. Keine unabhängige Maximalradius-Korrektur. |
| Torus | Vorhandenes `fit_torus_samples` bleibt Initialisierung: repräsentative Punkte/Normalen der geprüften Facetten. Endfit an gestützten Punkten mit `sqrt((rho-R)²+z²)-r`, `z=(p-c)·axis`. Gemeinsam `c`, zwei Achsrichtungen, `R`, `r`. | Sieben bestimmte Freiheitsgrade, weiterhin `R>r>0`; Jacobi-Rang und Empfindlichkeit beider Radien und der Achslage. Keine Rotation um die eigene Achse als zusätzlicher Parameter und keine pauschale Mindestbogenlänge. |

`_plane_basis` und `_fit_circle` bleiben gemeinsame Bausteine. Eine begrenzte,
deterministische Verfeinerung auf vorhandener NumPy/SciPy-Numerik genügt;
kein Zufall, kein RANSAC und keine neue Bibliothek. Der bestehende native
`fit_torus_samples`-Aufrufer liefert echte Punkte/Ableitungen und beweist
anschließend seine NURBS-Fläche. Mesh-Aufbereitung gehört vor diesen Weg;
native Stichproben dürfen nicht wie Facettenkinder behandelt werden.

**Konvergenz ist kein Maßnachweis.** Der skalierte End-Jacobi muss vollen Rang
haben. Seine Pseudoinverse liefert die Empfindlichkeit der Ausgabegrößen auf
Punktfehler. Eine kleine Residue mit großem Fernmittelpunkt bleibt unsicher.
Für Kegel/Torus fehlt derzeit eine entsprechend begründete Freigabegrenze;
sie wird vor der Umsetzung gegen unabhängige Positiv-/Negativkörper festgelegt,
nicht durch Kopieren der Kugelzahl 2000 oder Lockerung vorhandener Schranken.
Float32-Quellen und direkte Float64-Konstruktionen getrennt prüfen. Unbekannte
Quellgenauigkeit ist keine Nullunsicherheit. Öffentliche Diagnosefelder bleiben
mit dem Passungs-/Matching-Vertrag abzustimmen.

## Flächenbeleg und Anschlüsse

- `fit_error` bezeichnet den maximalen geometrischen Abstand der Stützpunkte
  zum Fit in mm; ein relativer Rückstand bleibt dimensionslos. Abstand der
  tatsächlichen Dreieckshaut und Fertigungsspiel bleiben eigene Auskünfte.
  Beim Torus sind Vertexextrema insbesondere kein Beweis für Extrema über
  ganze Dreiecke. Solange eine Flächenschranke nicht berechnet wurde, bleibt
  sie unbekannt; ein Stichprobenmaximum darf nicht als Obergrenze erscheinen.
- `_surface_normals_are_consistent`, `_cone_vertices_are_consistent` und
  `_sphere_is_recognisable` müssen alle ursprünglichen Flächen prüfen und
  Stützpunktfehler von Sehnenabweichung unterscheiden. Keine weggeworfenen
  Randpunkte, Ausreißer oder Normalen und keine nachträgliche Glättung.
- `_fitted.classify`, `_large_facet_faces`, `_a_ball_fits_far_better`,
  `_merged_cones`, `_merged_tori`, `_cylinder_beside_a_torus` und lokale
  Erkennung verwenden denselben Endfit. Größenfilter durch den belegten
  lokalen Trägervertrag ersetzen, nicht pauschal löschen. Unsicher verworfene
  Kugeln dürfen anschließend nicht als sicherer Kegel/Torus erscheinen.
- Optionalen `check_cancelled` vom Aufrufer durch Aufbereitung, Ebenengruppen,
  Fit-Residual/Jacobi und Abschlussprüfung reichen; feste Auswertungsgrenze,
  keine Teilmerkmale oder Cacheeinträge bei Abbruch. Keine Zeitmessung nötig.
- `detect_spheres/cones/tori` runden nicht im Kern. Parent koordiniert native
  Kugelkorrektur, Passung, Cache und Verbraucher; Oberflächen-Maßquellen bleiben
  ein eigener Anschluss. Künftiger Mesh-Code liegt in `perceive/features.py`,
  direkte lokale Aufrufer und `perceive/CLAUDE.md` nach Scope-Abstimmung.

## Zuerst nachzuweisende Gegenfälle

1. **Gemeinsame Stützung:** originale Ecke, Facettenmittelpunkt, alte
   Kantenmitte; gleichmäßige und nur einseitige Unterteilung, T-Verbindung,
   deckungsgleiche STL-Ecken, vertauschte Dreiecke, zwei getrennte Fächer am
   selben Ort. Unterteilung verändert die Stützmenge/Endmaße nicht.
2. **Trimmung:** Schnitt mitten durch Facetten und alte Kanten getrennt von
   Auswahl unverändert vorhandener Dreiecke; ausreichend erhaltene Innenpunkte
   positiv, ausschließlich mehrdeutige Randstützen negativ. Kein neuer
   Kugel-/Torusradius aus Sehnenenden. Beim Kegel echter Mantellinienschnitt
   positiv, nur scheinbar zur Spitze laufende Freiformkante negativ.
3. **Kugel:** R8, Halb-/Vollkugel, R80/5°-Kalotten in UV-/Ikosaedernetzen;
   negative 2°-Kalotte, schmales Band, Ellipsoid und einzelner Ausreißer.
4. **Kegel:** Vollkegel, Stumpf, 45°-Ausschnitt eines 60°-Kegels, vorhandene
   120/64-Ränder und schiefe Schnitte; Spitze/Achse/Winkel unabhängig. Die
   übergroße einzelne Facette und vorhandenen Freiformen bleiben negativ.
5. **Torus:** R20/r5 und R17/r3; beide Bogenrichtungen separat/getrennt
   beschneiden, ungleiche Auflösungen, Naht, innere Sattelseite und obere
   parabolische Linie. Dazu unterbestimmter Ausschnitt, Freiform, elliptische
   Röhre, einzelne Beule und getrennte Ringstücke als Gegenfälle.
6. Jede Form: Innen/Außen, Spiegelung, Rotation, große Translation, Maßstab;
   unveränderte Arrays und tatsächliche `detect`-Veröffentlichung zusätzlich
   zum Rohfit. Abbruch mitten in Aufbereitung und Verfeinerung plus Neustart.

Tests zunächst in den vorhandenen `test_sphere_fit_quality.py`,
`test_cone_fit_quality.py`, `test_cone_oblique_boundary_fit.py`,
`test_cone_vertex_support.py`, `test_torus_fit_quality.py`; gemeinsame
analytische Unterteilungsfälle bei Bedarf in einer neuen
`tests/test_round_surface_measurements.py`. Native Torusverträge aus
`test_brep_surfaces.py` müssen erhalten bleiben. Nur betroffene Kerntests;
Fenster und Leistung ausschließlich beim Release.
