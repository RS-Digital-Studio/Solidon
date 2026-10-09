# `app/core/perceive/` — Wahrnehmung

Was das Modell **ist**, nicht was es anzeigt: Merkmale, stabile Bezeichner,
Analysekarten und der Steckbrief (§21, §18.4, §23). Erkennen heißt nicht
ändern — hier entsteht keine Geometrie; Mehrdeutigkeit wird gemeldet, nicht
aufgelöst (§15.7, Regel 21).

Die Regeln: `.claude/rules/schichtanalyse.md` (Erkennung, Freiform,
Formtoleranz, Verengung, Hohlraum, Muster, Panel), `kern.md` (Nummerierung,
gemerkte und örtliche Fragen, Merker über die Körpergrenze), `operationen.md`
(beide Kerne sagen dasselbe), `gruppen.md` (funktionale Gruppen). Ausführliches, Messwerte und Anlässe unter
denselben Überschriften: `konzepte/begruendungen/karte-app-core-perceive.md`.

## Die Karte

| Datei | Rolle |
|---|---|
| `features.py` | Vollerkennung `detect` (§21.1): Ebenen, `_fitted` in Runden (Zylinder, Krümmungssplit, Stadion, `_arcs_of_a_prism`, `_pieces_at_a_seam`, tangentiale Trennung `_tangential_pieces` mit ebenen Reststücken `Fitted.flat`, Zügen `_drawn_chains`, eingeschlossenen Stücken `_enclosed_rounds` und den Keimgrenzen `TANGENTIAL_FIRST_SEEDS`/`TANGENTIAL_FUTILE_SEEDS`), Zusammenlegen, `detect_holes`, `detect_voids`, `narrowings_marked`, Anschnitt, Eckverrundungen `_corners_named_as_fillets` (Radiusfrage `rounds_the_corner`, auch am exakten Kern), `is_a_freeform`, zuletzt `detect_curved_faces` (nie auf einer Freiform); Fits (Felder an `CylinderFit`, `ConeFit`, `StadiumFit`), Merker, `numbering_order` und die Fragen, die Kantenweg und Panel teilen (`planar_facet`, `planes_beside`, `replaces_an_edge`, `tangent_walls`, `sits_at_the_mouth_of`); `_screened_fits` meldet den Rundform-Fortschritt schon bei den vorbereiteten Flecken |
| `refine.py` | Der Löser der Rundformen im Stapel (RM-209): `exhausted` sagt für viele Kegel- und Ringverfeinerungen zugleich, welcher Lauf sein Budget sicher ausschöpft — mit Abständen zu jedem Zweig, zu jedem Abbruch und einem Schattenlauf; die Blockzahl hält die kalibrierte Spitzenschätzung mit `BATCH_PEAK_FACTOR` innerhalb `BATCH_BYTES`; `_run` meldet nach jeder Solverrunde; `solve` ist SciPys `least_squares` auf diesem Weg, bitgleich nachgebaut, und rechnet jeden Lauf mit Ableitung (`features._refined_fit`); `_vector_norm` führt dessen reelle Vektornorm unmittelbar als Skalarprodukt und Wurzel aus, mit unveränderter Rechenfolge |
| `helix.py` | Gewinde am eingelesenen Netz: Spektrum `_best_pitch` (beide Vorzeichen), Kantenleser `_measured_helix`; was eine Wendel verschluckt, sagt `features.without_phantoms_on` für beide Kerne. Bausteingewinde laufen nie hindurch (§24.1) |
| `slots.py` | Langlöcher, topologisch: zwei Halbzylinder, zwei ebene Flanken (Gegenprobe `tests/test_slot_features.py`); `slots_from_stadiums`, `open_slots_instead_of_fillets`, `native_open_slot_measures`, Paarsuche `_PairPlan` |
| `patterns.py` | Muster (§25): Erkennung `find_patterns` und ausdrückliche Zusammenfassung `grouped_pattern` über dieselbe Zellenlesung `_read_cells`, Absagen `group_refusal`; `Frame`, Stopfen `plug_for`, Feld `field_outline` für `remove_feature`/`resize_feature` in `geom/prepare_ops.py`; `carrier_of` findet den Träger über Ebene oder Achse, nie über eine Kennung; `cylinder_facet_groups` ordnet die Mantelnormalen plattformgleich über die Winkelnaht, `cylinder_facet_lines` liest daraus die achsparallelen Facettengeraden — dieselben für Stopfen (`FacetPolygon` mit Ecken am Schnitt der Facetten, Stirnenden `Frame.ends`) und Quellausrichtung |
| `relations.py` | Nachbarschaften: Hohlraumketten (unten), Rohrwand (`sleeve_at`, `thinnest_sleeve`), Dreieckseigentum (`cell_owner_table`, `CONTESTED`), Gleichartigkeit (`alike_for_actions`, `_same_surface_patch`), Gruppensätze (`group_evidence_texts`, `group_reason_texts` — das Panel liest sie von hier) |
| `groups.py` | Funktionale Gruppen (Dateiaudit §7): Kammer, Tasche, Nut, Kanal, Anschluss, Gewinde mit Einlauf und Schulter, Bajonett und Rastung (auch runde Mulden), Scharnier, Steckaufnahme, Schrift — `functional_groups` (je Netz und Merkmalsliste gemerkt, geteilt), `chamber_region` für *Kammer ändern*, `reason_against_group` (mit `trough_walls`) als Absage für Fenster und Operation; für *Verschluss ändern* je Stellung (`stations`) `closure_flanks`, `closure_pairs`, `closure_stops` und die Absagen `reason_against_play`/`_turn`/`_closure_change`; ein Merkmal steht in höchstens einer Gruppe, Bausteinmerkmale in keiner |
| `matching.py` | Stabile Bezeichner (§21.3): `match` (gemerkt je Eingang, begrenzt über Kennungen, Bytes in `matched_bytes`; `forget_matches`), `settled_by_surface` (Zwillinge nach der Lage ihrer Oberfläche; `settled_twins` mit den Orten beider Seiten aus `surface_places`, für jeden zuordnenden Weg beider Kerne), `resolve`, `apply_mapping`, `inherit_originators`, `transformed_features`, `moved_features`; `planar_source`, `planar_faces`, `pieces_in_place` prüfen die räumliche Herkunft ebener Restflächen gemeinsam für Auswertung und Abschneiden |
| `match_records.py` | JSON-Struktur und körperqualifizierte Antwortschlüssel; Domänen `group:`, `native-group:`, `edge-answer:`, `recognition-answer:` als Konstanten |
| `match_decisions.py` | Ganze Zuordnungsentscheidungen wiedererkennen und atomar prüfen; `resolve_group(scope=...)` gibt eine native Wahl nur für denselben Scope frei, eine Netzantwort nie für die native Frage; keine zweite Zuordnung |
| `local.py` | Begrenzte Suche am großen Netz (unten) |
| `ops.py` | `detect_region`: die örtliche Suche als Operation — ändert keine Geometrie, erhält IDs, Provenienz, Erzeuger; übereinanderliegende Flächen fragt `ctx.ask`. `group_pattern`: gewählte Einzelmerkmale als Muster `grouped_<Schritt>`, ohne Geometrieänderung |
| `recognition_time.py` | Zeitspanne der Vollerkennung aus einer Rechenprobe je Prozess — nur Anzeige, keine Uhr in `detect` (§15.1) |
| `surfaces.py` | Teilträger (`SurfacePatch`): `valid_patch`, `planar_patch`, `clipped_patches`, `reindexed_patches` |
| `actions.py` | Was der Kunde an einem Merkmal tun kann und was nicht (unten) |
| `digest.py` | Steckbrief für den Agenten (Format: §23); `_selection_lines` fragt denselben Weg wie das Panel, Schrittnummern `types.step_numbers`, hinter einem Schritt „aus“, „ruht“ oder „Ergebnis entfernt“ mit dem Wort des Verlaufsfelds (`scene.history.step_state_word`, träge geladen) |
| `maps.py` | Analysekarten (§18.4, unten) |

`__init__.py` trägt nur den Paketdocstring.

## Der Weg durch die Erkennung

- **Konkurrierende Rundformen brauchen vollständige Nachweise**: Ein Zylinder
  beendet die Frage vor dem Kegellauf nur, wenn seine Originalecken bis
  `EPS_GEOM` und seine senkrechten Normalen bis `EPS_ANGLE` stimmen.
  An angenäherten Wänden wird der Kegel ebenfalls geprüft. Bestehen beide
  Nachweise, bleibt die Form mit dem kleineren maximalen Abstand zur
  Originalhaut; ein fehlender Fehlerwert bestätigt keinen Vorrang.
  `_screened_fits` überspringt nur dieselben bereits belegten Zylinder.
- **Kegelläufe verwenden einen lokalen Rahmen**: `_cone_plan` legt die
  beobachtete Achse auf Z und einen tatsächlichen radialen Stützpunkt auf X.
  Die Normierung liest die Entfernung zum gewichteten Ursprung statt einer
  Weltbox. Einzel- und Stapellöser erhalten denselben Plan; erst das Ergebnis
  geht zurück in Weltkoordinaten. Budget und Nachweise bleiben unabhängig
  von dieser Wahl des Rechenrahmens. Schöpft der Lauf vom Normalenstart sein
  Budget aus, rechnet ein zweiter von der Quadrik der Stützpunkte
  (`_quadric_cone_start`, `_ConePlan.seed`) — der Normalenstart steht an
  flachen Streifen im falschen Tal. Der Stapel fragt beide Läufe
  (`fit_cone_seed` in `_SCREENED`); wo der erste ankommt, bleibt er.
- **Größenbelege folgen der Geometrie**: `_fits_in_the_body` misst die
  Diagonale des kleinsten Rechtecks der quer zur Fitachse projizierten
  Körperhülle. Zwei wirkliche Ecken können das positive Urteil schon vorher
  belegen. `_area_and_reach` misst den größten tatsächlichen Eckabstand;
  `_point_diameter` benutzt Suchbaumboxen nur als obere Schranken und
  begrenzt die Punktpaarfelder auf Blattpaare. Der Breitenentscheid darf
  enden, sobald eine obere oder untere Schranke seine Antwort beweist.
  Weltboxen werden dadurch nicht zu lageabhängigen Merkmalsmaßen.

- **Importierte Musterfelder** bleiben nach räumlicher Nachbarschaft und
  Streifenrichtung getrennt; ihre Zellgrenzen werden nicht abgesenkt.
  `without_pattern_cells` faltet nur vollständig in einem belegten Muster
  enthaltene Einzelmerkmale. `detect_region` behält bei überlappenden Funden
  die bereits belegte Textur samt Herkunft; Teilmerkmale werden nicht gekürzt.
- **Ausdrücklich zusammengefasste Zellen** (`grouped`) binden sich wie
  erzeugte Texturen (`bound_to_its_surface`); der exakte Körper fragt
  dieselbe Mustersuche (`brep.features.features_of`).
- **Erzeugte Texturen**: `patterns.rebound_textures` bindet ihre belegten
  Dreiecke neu; `without_texture_cells` faltet die Einzelformen und misst
  verbleibende Trägerflächen nach. Der Oberflächenbeleg gilt auch für kleine
  Felder, die ohne Erzeugerwissen unter der Mustererkennungsschwelle liegen.
  `cylinder_envelope` begrenzt ihren Stopfen an den belegten Mantelfacetten;
  ein unbelegbarer Träger bleibt eine ausdrückliche Ablehnung.
- **Erst der Merker.** Die Auswertung fragt vor jeder Erkennung
  (`scene.evaluate._with_features`): `detect` legt jede vollständige Erkennung
  unter `_mesh_key` ab; `carry_detection` (starr bewegt, Beleg `moved_twin`;
  ohne gemeldete Matrix nennt der Bewegungsvermerk `note_movement` aus
  `geom.transform.apply` Eingang und Matrix, geglaubt über `moved_from`, auf
  der Platte als `moved_from` im Eintrag),
  `carry_refined_detection` (feiner geteilt, `note_refinement`, Beleg
  `refined_twin`; der Vermerk reist als `<n>.origin.npy` durch den
  Plattencache) und `known_detection` (Live-Vorschau) antworten ohne Rechnung.
- **Vergebliche Löserläufe entfallen im Stapel**: Vor jeder Runde (ganze
  Flecken, Stücke, Mantelnachweis) legt `_screened_fits` Plan und Urteil
  aller Kegel- und Ringläufe in `_SCREENED` (`_screening`), dazu je Fleck
  Lesung und Kennzahl, aus denen `_surface_support` und `_rigid_key` in der
  Runde antworten;
  `_fit_cone_measured`/`_fit_torus_measured` lassen nur die sicher
  vergeblichen aus, alles andere rechnet der Löser Zahl für Zahl.
- **Wo neu gerechnet wird, antworten Einpassungen und Nachweise über die
  Körpergrenze** (`_by_geometry`, `GEOMETRY_KEYED_ANSWERS`), bitgleich
  geschlüsselt nach Stützpunktlesung (`_SurfaceSupport.digest`), Toleranz vom
  Aufrufer, Fit und Löserbudgets, gehalten von den fragenden Abstammungen
  (`_Lineage.geometric`). Das trifft, weil eine Boolesche Unberührtes in der
  Darstellung des Eingangs zurückgibt (`geom.attributes.in_source_layout`).
- **Je Körper merkt `remembered`** (`_BodyMemory`, ein Schloss
  `_MEMORY_LOCK`; ein abgebrochener Auftrag bekommt keine Antwort); eine Kopie
  für einen Nebenfaden liest aus ihrem Original (`copy_with_answers`).
  `moved_twin` teilt den vollständigen Bewegungsbeleg über alle Verbraucher,
  geschlüsselt nach beiden Geometrieabdrücken und der tatsächlichen Matrix;
  eine andere Matrix oder veränderte Ecke braucht einen neuen Beleg.
- **Der Ursprung vor dem Teilen reist mit** (`geom.mesh.refined_units`: durch
  Boolesche an unberührten Dreiecken, Verschweißen, `MeshData.replacing`,
  Plattencache; frisch −1). Die Zählregeln lesen daran das ungeteilte Netz
  (`_face_count`, `_flat_counts`, `_outline_corners`, `face_radii` über
  `_by_origin`); `_mesh_key` nimmt den Abdruck mit.
- **Dann die Namen**: `matching.apply_mapping`; Verlorenes fragt
  `scene/orphans.py`. `detect` meldet nur wachsend (`_Share`), bricht über
  `check_cancelled` ab und veröffentlicht danach keinen Cacheeintrag.

## Große Netze: örtlich statt ganz

- **Staffel** (§21.1): automatisch bis `FEATURE_LIMIT_TRIANGLES`, bestätigt bis
  `CONFIRMED_FEATURE_LIMIT_TRIANGLES`, darüber örtlich; `recognition_minutes`
  und `recognition_gigabytes` sind Anzeige, keine Grenze. Die Speicheranzeige
  rechnet mit 2 200 Byte je Dreieck (inklusive Reserve gegen den Messwert am
  Meshy-Murmelbrett). Speicherfehler: `remember_out_of_memory` (`kern.md`).
- **`detect_local`** veröffentlicht nur vollständig belegte Merkmale mit
  globalen Dreiecksnummern, nie eine Randöffnung des Ausschnitts: Treffer aus
  den Dreiecken am Punkt (`_region(bounded=False)`, beide Würfel aus einem
  Durchgang `_within`), Budget für den Teil am Treffer (`_connected_to`), die
  ebene Facette dazu (`proven`); bleibt sie allein (`alone`:
  `_could_be_complete`, `_reaches_beyond`), entfallen die Ganzkörperfragen.
  Läuft eine Fläche glatt über den Suchrand, bleibt sie bis zum nächsten
  Krümmungssprung des ganzen Körpers gesperrt. Das Budget ändert keine
  Toleranz; ohne Abschluss kommt ein Handlungsvorschlag (Grund `budget`), nie
  Teilgeometrie.
- **`detect_known`** misst nach einer Operation nach, hält nur für `required`
  an, übernimmt `standing` und **fragt örtlich** (`curvature_jumps_at`,
  `face_radii_at`, `_surface_owners_near`; gemerkt als `radii_near`,
  `surfaces_near`, ab `LOCAL_RADII_SHARE` der ganze Körper) mit denselben
  Antworten wie am ganzen Körper (`_known_answer`). Eine Kette misst sich oft
  erst an der Suche ihres Nachbarn; gesucht wird im eigenen, dann im belegten
  Umfang (`recorded`, `matching.transformed_features(...).candidates`).
- **`features_in_region`** begrenzt die Auswahl an belegten Originalpunkten,
  ohne zweite Erkennung; `local_error` trägt den Grund als `constraint` mit
  Präfix `local_` — die Oberfläche steuert darüber, nie über Sätze.

## Zwei Fragen, zwei Dateien

`features.py` fragt „was ist das hier", `relations.py` „gehören zwei
zusammen". **Die Richtung ist einseitig**: `relations.py` liest Schwellen
(`SINK_AXIS_LIMIT`, `SINK_FIT_LIMIT`) und Bedingung (`sits_at_the_mouth_of`)
aus `features.py`, nie umgekehrt.

Eine Hohlraumkette (`cavity_chain_at`, je Objektbaum `cavity_chains`) hängt
nur über vollständig gemeinsame geschlossene Randringe zusammen; eine ebene
Ringschulter mit genau zwei Ringen darf dazwischen liegen
(`cavity_surface_indices` — ein Abstand oder eine ähnliche Achse ersetzt sie
nicht). Mit `mouth_blends=True` reist ein wandnaher Übergang mit
(`_near_the_wall`, `cavity_blend_indices`). Die Kette beginnt am engsten
Zylinder, liegt er in der Mitte, folgen die Seiten (`cavity_sides`);
Doppelbelegung, Verzweigung, Zyklus oder ein uneindeutiger Anfang geben keine
Auskunft, `cavity_chain_state_at` trägt den Grund (`operationen.md`).

## Die Auskunft für das Merkmalspanel

`actions.py` ist die eine Stelle, die sagt, welche Handlung für welche Art
gilt — **abgeleitet aus `applies_to`**, keine Tabelle daneben (`actions_for`);
die Oberfläche fragt die Art nicht, sie rendert die Liste. Der Kern fragt
dasselbe (`reason_against`, gerufen von `geom/prepare_ops.py`), `instead_of`
nennt die Schwester einer Zeile;
`tests/test_features.py::test_the_operation_refuses_exactly_what_the_panel_greys_out`
hält beide Wege zusammen.

- **Was nicht gilt, steht trotzdem da** (`op=None` mit Satz), und **jedes Feld
  trägt seinen gemessenen Wert** — eine andere Vorgabe wäre eine stille
  Änderung. `ActionField.measurement` ist der Ausgangswert.
- **Versetzen fragt eine Funktion**: `move_refusal` ist die Zeile *Merkmal
  verschieben* (`actions_for(only=)`); `move_feature` und der Griff
  (`FeaturePanel.refuses`) lesen sie. Nur dort sagt `move_blocked` zusätzlich
  ab (Zapfen oder Kuppel als ganzer Körper, Zapfen desselben Teils in der
  Bohrung; ein getrenntes Teil dort nennt `OTHER_PART_IN_THE_BORE`), und eine
  Haltelippe (`only_a_rim_inside`) sperrt nicht. An der Fläche steht in dieser
  Zeile *Fläche versetzen*, der Weg beginnt bei 0 (`_STARTS_AT_ZERO`).
- **Grau mit dem Satz der Operation**: geteilter Hohlraum
  (`_shares_its_cavity`; ohne Netz keine Sperre), kein eigener Körper
  (`no_own_body`), Verengung (`cone_reason`, `not_offered_at`), Bohrung einer
  Kette mit Verengung (`narrowing_reason`), Kegel einer Kette bei *Merkmal
  ändern* (`_countersink_unsized` → `countersink_resize_refusal`), Verrundung
  ohne zwei Ebenen (`fillet_blocked` — liest die Ebenen aus `planar_mask`
  wie `edges._around`, nicht die `face`-Einträge des Baums).
- `bore_action` bietet die ursprünglichen Schrittwerte an und ändert über
  `step` den vorhandenen Schritt; eine Transformation wird nicht
  zurückgerechnet. Eine ermittelte Kette geht als `cavity` an `actions_for()`
  und `scene.placement.bore_advice()` — `()` heißt geprüft keine.
- **Gleichartig für diese Handlung**: die Größenhandlung vergleicht nur ihr
  Maß (`feature_value_source`), die übrigen den ganzen Flächenausschnitt; eine
  Kette ist der Umfang jedes Mitglieds, sortiert nach Kennung, Fehlendes steht
  in `uncertain`.
- **Jede Maßquelle hat ein sichtbares Wort** (`MEASURE_SOURCE_WORDS`,
  `measure_qualifier`) — Steckbrief, Bohrhinweis und Panel lesen dieselben.
  Die Maßspalte des Objektbaums ist dafür zu schmal: Dort steht die Zahl ganz,
  ein warnendes Wort wird `labels.MEASURE_MARK` (≈), das Wort tragen Tooltip
  und Vorlesetext (`feature_measure(marked=True)`, RM-490).

## Analysekarten (`maps.py`)

`maps.build` rechnet, die Ansicht malt; `AnalysisMap` trennt Messwert und
Darstellung (Krümmung asinh, nichts gekappt). Die Netzfehlerkarte hat vier
Stufen und fragt dieselbe Schnittsuche wie die Reparatur
(`repair.crossings_of`); `nan` sind nur ungeprüfte Dreiecke, eine leere Liste
aus begrenzter Suche ist keine Entwarnung. Die Wandkarte beginnt bei null und
deckelt nur oben; Wand- und Stützkarte nehmen die Rasterweite aus der
Extrusionsbreite. Die Stützkarte endet nach drei Sekunden mit *Dreiecke
verringern* — ein Budget der laufenden Rechnung, keine Vorabschranke (§2.8,
§31). Die Überhanglegende nennt den Grenzwinkel der Karte, nicht 45 Grad. Die
Passungskarte liest nur den aktuellen Prüfbericht: Informationsbefunde sind
keine Verletzung, positive Lageproben überschreiben keine offenen Befunde. Die
Formabweichung liest nur vorhandene `SurfacePatch`-Belege.

## Stolperfallen

- **Auflösung ist nicht Herstellbarkeit** (§11.2): Drucker- und
  Materialwechsel ändern keine Merkmale und IDs; `MIN_CYLINDER_DIAMETER` ist
  profilunabhängig (`_too_small_to_make`). Ebene Funktionsflächen hängen an
  der absoluten Auflösung, nicht an der größten Fläche des Körpers.
- **`matching.match`**: Die Vorauswahl verwirft nur räumlich Unmögliches
  (keine Nachbarzahl, keine neue Toleranz); die volle Matrix entfällt nur mit
  Zertifikat, der Solver wird nie in Komponenten zerlegt. Eine Solverantwort
  ist noch keine Identität (Kostenhülle je `_accepted_components`); mehrere
  Ansprüche auf einen Kandidaten sind mehrdeutig, `require_injective` sperrt
  vor Namen- und Erzeugerübernahme. Nichtendliches oder ein ungültiger
  Fingerabdruck lässt alles offen.
- **Erben nur mit Beleg**: `created_by` nur bei eindeutiger Zuordnung; ein Fit
  bleibt `fit` auch unter erzeugtem Namen, ein Vorgabewert wird durch
  Dreiecksnummern nicht zur Messung. Das Fingerabdruckfeld `diameter` ist
  historisch das Rohmaß (`params.diameter`, sonst `params.area`).
- **Maße reisen nur bei belegter Formerhaltung** (`transformed_features`,
  Teilmenge `exact`): Spiegelung kehrt die Händigkeit, achsweise Skalierung
  erhält eine Kreisbohrung nur bei gleicher radialer Dehnung;
  `profile_clamp_y` reist mit, `void.centre`/`size` werden neu gemessen.
- **Träger und Stützen**: Ein Träger entsteht nur aus einem akzeptierten Fit
  an seinen Originaldreiecken, nie aus Artetikett, Mitte oder Vorgabemaß;
  `clipped_patches`/`reindexed_patches` reparieren keine Indizes. Rundmaße
  stützen sich nur auf belegte Mantelpunkte (`_surface_support`) —
  Unterteilung und Nähte liefern keine, getrennte Fächer teilen keine, das
  Originalnetz bleibt. Eine Mantellinie zwischen zwei Facettenfamilien
  verwendet deren flächengewichtete Normalen; die Lesereihenfolge der
  Float32-Dreiecke darf ihre Richtung nicht bestimmen.
  Reichen die Mantellinien eines Kegels nicht aus, darf ein erhaltener
  Kreisrand eigene Stützpunkte belegen (`_circular_rim_points`): mindestens
  vier nicht kollineare Originalrandecken einer zusammenhängenden Kette,
  gemeinsam eben und kreisförmig bis auf die örtliche Schweißtoleranz.
  Sehnenmitten zählen nicht. Der Kreis ersetzt weder den Rangnachweis noch
  die Prüfung der übrigen Haut und ihrer Normalen.
- **Eine Rundform braucht vollen Beleg**: Kugel mit Rang vier und Krümmung in
  zwei Richtungen, Torus und Kegel mit der Normalenprobe, der Kegel mit allen
  Facettenecken; ein Kreis allein bestimmt keinen Kegel (Winkel bleibt
  `fit`). Der Löser rechnet an höchstens `FIT_SOLVER_POINTS` Punkten, geprüft
  wird an allen; unvollständige oder rangdefiziente Ergebnisse gibt es nicht,
  in `fit_torus_samples` gehört keine Facettenkorrektur. `fit_error` ist der
  größte Stützpunktabstand, keine Zusage über Ursprungsmaße.
- **Kreis und Zylinder**: zentriert, QR statt Normalgleichungen, ranglose
  Punkte tragen keinen Kreis, ein regelmäßiges Vieleck beweist keine Absicht.
  Maß aus belegten Konturecken, Mitte aus den Endringen, Achsvorzeichen am
  transformierten Vorgänger; Kreismaß, `fit_error` und Netzband getrennt. Ein
  Stadion hält auch seine schlechteste Ecke. Offene Langlöcher nehmen Radius
  und Achse aus demselben `CylinderFit`; ein nativer Zylinder zählt nur im
  Vertrag von `PARALLEL_AXES` und `SAME_RADIUS`. Eine anhängende Torusfacette
  gehört nicht zum Zylindermaß — geteilt wird an der belegten Torusachse, die
  Toleranz bleibt.
- **Ebenen**: Ob eine Fläche eine ist, sagt `planar_facet` am ganzen Körper,
  nie der Ausschnitt (erst der Suchrand, dann die Ebenenregel); nur die ganze
  Facette ist die Fläche, Dreieckszahl macht keinen Mantelstreifen zur Ebene,
  ein Teilstück zählt je Umrissecke. `inner` verlangt dieselbe Schale und eine
  parallele Außenkontur darüber, die den ganzen Flächenumriss umfasst;
  ein Schriftzug über dessen Mitte genügt nicht. An Rundflächen bestimmen nur gekrümmte Nähte
  die Innenlage. Der Rundungsgang `continues_tangentially` beantwortet nur die
  Langlochfrage.
- **Nachtrennung**: Geteilt wird nur, was jemand liest (`worth_splitting`);
  eine Kerbe schließt nur die kleinste eindeutige Menge freier Dreiecke, die
  über eine Naht unter `CURVATURE_LIMIT` anliegen (`_without_notches`,
  `_candidates_at`), gesucht am Knoten (`_vertex_faces_index` — trimeshs
  `vertex_faces` schleift bei einem entarteten Dreieck je Ecke); kein Feld in
  Netzgröße je Fleck; `_ThroughBounds` nur je Körper, nie persistent.
- **Der Merkmalscache hat zwei Schranken** (`CACHE_LIMIT`,
  `CACHE_INDEX_LIMIT`); ein Eintrag über der Gewichtsgrenze bleibt, sonst wäre
  der Cache aus.
- **Langloch und Durchblick**: Flanken gehen im Langloch auf
  (`SWALLOWED_BY_A_SLOT`); ungültige Gewindekandidaten unterdrücken nichts.
  `UPRIGHT_TO_AXIS` misst gegen die Achse, `TANGENT_TO_THE_ARC` gegen den
  Radius. Hindurch sieht man nur mit freien Ringen (`THROUGH_RINGS`) und ohne
  angrenzende Fläche in ganzer Länge (`_faces_beside`, wie
  `brep.features._axis_covered`).
- **Im Ausschnitt**: Der angeklickte Punkt bestimmt die Luftkammer, ihre ganze
  Grenze liegt im Radius; keine verschobene oder neu vernetzte Ersatzform.
  Eine Hohlraumkette braucht alle Abschnitte und vollständige Ringe; eine
  unvollständige Nachbarhöhlung verwirft eine Bohrung nur als mögliches
  Kettenglied. Ein Muster kommt erst, wenn sein Feld im Radius liegt.
- **Bekannte Durchgangswände über dem lokalen Suchbudget** dürfen ihre zur
  Achse senkrechten Dreiecke samt vollständigem Originalnachbarring nachmessen.
  Die gewöhnliche Fit- und Randprüfung bleibt; nur ein am ganzen Original
  erneut belegter Durchgang wird veröffentlicht. Sacklöcher, fehlende Ränder
  und übrige Merkmale brauchen weiterhin ihren vollständigen Suchkontext.
- **Rohrwände** rechnen mit dem Querversatz; am Langloch zählt der fernere
  Endmittelpunkt.
- **Verlorene, erzeugte oder geschlossene Merkmale** (`perceive.orphaned`,
  `generated_lost`, `referenced_lost`, `mended`) führen zu Körper und Schritt,
  ohne Karte.
