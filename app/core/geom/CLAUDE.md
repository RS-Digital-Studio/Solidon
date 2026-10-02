# `app/core/geom/` — wo Geometrie entsteht

Die einzige Stelle, an der Geometrie entsteht oder sich ändert (Regel 2),
gerechnet gegen `manifold3d` und `trimesh` — in Millimetern, ohne
Toleranzkonstante, nie an einer Eingabe: `OpResult.outputs` sind neue Objekte.

Die Regeln: `.claude/rules/operationen.md` (Register, Rückfallkette,
Merkmalshandlungen, Muster, Aushöhlen, Auto Split), `kern.md`
(plattformgleich, teure Aufrufe), `dateiformat.md` (Verschweißen),
`schichtanalyse.md` (Panel und Kantenweg), `wartezeit.md` (grobe Vorschau).
Ausführliches, Messwerte und Anlässe unter denselben Überschriften:
`konzepte/begruendungen/karte-app-core-geom.md`.

## Plattformgleich gerechnet

Gleich auf jeder Maschine sind Grundrechenarten, `sqrt`, `np.cross`, Normen
über eine Achse, `math.hypot`/`math.fsum` und NumPys paarweise Summe; was
plattformabhängig ist, sagt `kern.md`. Die Werkzeuge:

| Frage | Helfer |
|---|---|
| Skalarprodukt zweier Raumvektoren | `units.dot3` |
| Lage vieler Punkte entlang einer Richtung | `transform.along` |
| Punkte bewegen, Richtungen drehen | `transform.moved_points`, `transform.turned` |
| 4x4-Matrizen zusammensetzen (`a @ b`) | `transform.composed` |
| kürzeste Drehung zwischen zwei Richtungen | `transform.rotation_between` |
| Winkelfunktionen | `units.exact_cos`/`exact_sin`, `exact_cos_degrees`, `circle_point` |
| Arkuskosinus (Knickwinkel, Bogenspanne) | `mesh.stable_arccos` |
| Ausgleichsebene, symmetrische 3x3-Eigenwerte | `units.plane_fit`, `units.symmetric_eigen3` |
| Mitte einer Punktwolke | `units.exact_centre` |
| Normalen und Flächen je Dreieck, Eckennormalen | `mesh.stable_normals`, `mesh.stable_areas` (einzelne Dreiecke), `mesh.stable_vertex_normals` |
| Summen, deren Gleichstand eine Lage entscheidet | `mesh.IntegerGrid` |
| Spatprodukte, eingeschlossenes Volumen mit Vorzeichen | `mesh.triple_products`, `mesh.signed_volume` (körpernah) |
| Zufall (Stufe 3 der Kette) | `Generator.random` aus den Rohbits, nie `normal` |
| Drehkörper, Kreispunkte | `lathe.cylinder`, `annulus`, `revolve`, `circle_points` |

Kantenwerkzeuge rechnen Längen über `_length`, kleine Systeme über
`_solved3`/`_least_squares3` statt LAPACK, die Kugel über `_icosphere`.

## Die Boolesche Rückfallkette (§17.2)

Der Normalweg dieses Gebiets; Stufen und Vermerke stehen im Docstring von
`boolean.py` und in `operationen.md`, `tests/test_boolean.py` erzwingt jede.
Ineinandersteckende Teile eines Szeneneingangs gehen vereinigt hinein
(`_parts_united_first`). Bei Vereinigungen werden weitere Szeneneingänge mit
Objektkennung geprüft; ausdrücklich interne Werkzeuge (`None`) gehen
unverändert an den Solver, weil ihre Teilstücke konstruktionsbedingt
überlappen können. Nur beim Schließen einer alten Höhlung vereinigt
`merge_face_contacts=True` zusätzlich flächig berührende Schalen — an jeder
schließenden Vereinigung, auch für Ketten, Abschnitte, Wulst und Musterzellen;
am exakten Kern dasselbe über `prepare_ops._exact_closing_base` (Ketten:
`_exact_closing_chain`). Kanten- und Eckkontakt bleiben getrennt. Der Vereinigungsmodus gehört zum
Booleschen Cache-Schlüssel. Für die Vorfrage erkennt
`parts_that_cross(include_face_contacts=True)` Flächenkontakt auch bei
unterschiedlich unterteilten Netzen; eine gemeinsame Kante zählt nur innerhalb
der lokalen Rundungsgrenze als gemeinsamer Punkt, nicht mit der breiteren
`EPS_GEOM`-Toleranz. Die Endpunkte beider Randkanten werden direkt gegen die
jeweils andere Linie geprüft; die ganze Schnittstrecke muss von beiden Kanten
getragen werden. Die Vorauswahl verwendet nur die Projektionsüberdeckung,
  weil eine kurze Kante die Richtungsrundung beim Verlängern stark verstärken
  kann. Der direkte Punkt-zu-Linie-Nachweis berücksichtigt deshalb die
  koordinatenweise halbe ULP jedes Endpunkts und den Verlängerungsfaktor. Die
  Rundungsgrenze wird mit dem Betrag der orthogonalen Projektionsmatrix auf
  jede Residualachse fortgepflanzt; x-Rundung kann so auch y-Abstand erklären.
  Die drei Komponenten werden in fester Reihenfolge summiert, ohne `einsum`.
Projektionen ziehen vorher einen gemeinsamen Ursprung ab, damit lokale
Vektorprodukte unabhängig von der Weltlage bleiben; die separate ULP-Grenze
  bildet die Genauigkeit der gespeicherten Koordinaten ab.

Das Paarbudget von `parts_that_cross` begrenzt nur optionale Befunde. Vor
`boolean()` und beim exakten Schließen verlangt der Aufrufer mit
`max_pairs=None, require_complete=True` die vollständige Prüfung; die
Teilegrenze bleibt ein sicherer Abbruch. Die Suche prüft den Abbruch während
der Achsenauswahl und nach jedem Kandidatenblock.

**Nach jeder gelungenen Stufe bekommt das Ergebnis die Darstellung seiner
Eingänge zurück** (`attributes.in_source_layout`): Ein bitgleich übernommenes
Dreieck beginnt an der Ecke seines Vorbilds, übernommene Ecken stehen in der
Reihenfolge des Eingangs; Dreiecksfolge und Koordinaten bleiben die des Kerns.
`prepare_ops._without_scars` legt ebenso zurück. Die Regel steht in
`operationen.md`, der Messfall in `konzepte/begruendungen/regel-operationen.md`
unter „Boolesches geht durch die Rückfallkette“.

- **Native Stufen** übergeben `Mesh64` und lesen Status und Volumen vor der
  Rückvernetzung; flächiger Kontakt ergibt ein leeres Netz, ob das gilt, sagt
  `allow_empty`. Kontaktreste entscheidet `kernel_jobs.native_contact` an der
  Float64-Grenze `gamma(8) * max|Koordinate| * Oberfläche` je Komponente —
  keine Drucktoleranz; `EPS_GEOM` ist kein Mindestvolumen. Verbleibende Schalen
  werden angefügt, nie neu vereinigt (das füllte Hohlräume).
- **`ctx.quality` und `ctx.cancelled` reichen durch jeden Teilschritt**, auch
  Werkzeugvereinigung und Eckanschluss; nichts stuft den Entwurf hoch. Eine
  erneute B-Rep-Erkennung nimmt dasselbe Token, nie ein eigenes.
- **Nur exakte Eingänge** gehen über `brep.edit.boolean`; ist ein Netz
  beteiligt, gilt die Kette. Beide prüfen leere und wirkungslose Ergebnisse;
  `body_split` ist das eine Urteil über einen zerfallenden Körper.
- **Wer mit `trimesh` an einer Ebene teilt und danach verschweißt**
  (`section._apply`, `faces._draft_tools`), legt vorher auf die Ebene, was
  trimesh zu ihr zählt (`section.settled_on_plane`): Ecke und Schnittkopie
  stünden sonst bis 1e-8 mm auseinander, und das Verschweißen über gerundete
  Koordinaten verfehlte sie — der Körper bliebe offen.
- Eine Änderung am gemeinsamen Kern entwertet den Ergebnis-Cache
  (`paths.results_cache_dir()`, §38).

## Die Karte

`__init__.py` trägt nur den Paketdocstring.

**Grundlage** — `mesh.py` (die Hülle um den Kern, §9; `read_mesh`,
`unique_edges`, `edge_table`; `python_values` für Millionen Werte als
Python-Zahlen, stückweise; `on_surface` über einen Index, den hält, wer
denselben Körper mehrmals fragt — `prepare.surface_index_of`;
`ray_hits_batch`, dessen Index nur wählt, welche Paare rechnen, nie ihren
Wert; `lifted_caps`, Zwilling von `brep.edit.collared`) · `boolean.py` ·
`attributes.py` (Slots durch eine Operation, §20; `transfer`, `with_slots`,
`carry_refined_units`) · `lathe.py` · `enclosure.py` (Verschachtelung ohne
`rtree`) · `intersections.py` (Selbstdurchdringung als Feld, für Karte,
Bereichstest und Formschritt) · `repair.py` (unten) · `deviation.py` (Grenzen ausgefüllter
Originaldreiecke zu einem belegten `SurfacePatch`, Budget je Dreieck; keine
neue Einpassung, Geometrie oder Cache) · `contours.py` (`section_of`,
`offset_section`: ungültige Konturen werden nicht still repariert, Spiel gibt
der Aufrufer)

**Der Netzkern im Hilfsprozess** — `kernel_jobs.py` führt lange GIL-haltende
Aufrufe (`manifold3d`, `csgraph`) als reine Rechnung mit Feldern hinein/heraus;
`JOBS` ist der einzige Auftragseinstieg, `serve` die Helferseite,
`pack`/`copied` der gemeinsame Speicher. `_opened` ordnet nur ENOMEM und
die Windows-Speichercodes 8/14/1450/1455 als `MemoryError` ein; ENOSPC bleibt
ein Transfer-`OSError` für den bestehenden Absage-/lokalen Rückfallweg.
`kernel_process.py`: bitgleiches `run` hier/im Helfer, Vorrat, Abbruch, Tod,
Rückfall, `warm_up`, `shutdown`; `NOT_A_KERNEL_FAILURE` schützt breite Fänge.
Ein Start reserviert unter dem Poolschloss einen Platz; der gesamte Bestand
behält ihn bis zum bestätigten Prozessende. Stoppreste bleiben sichtbar und erneut
aufräumbar; die nächste Anfrage sammelt einen inzwischen toten Rest regulär
ein. Lebende Reste sperren Starts und lokale Rückfälle, auch beim nächsten
`run` nach Vorabstart, mit dem vorhandenen Fehlerbericht-Ausweg. Bleibende
Start-/Helferabsagen überstehen das Einsammeln. `shutdown`
gibt auch bei Fehler seine Wartenden frei, nimmt offene Starts mit und trennt
alte Reservierungen/Rückgaben/Absagen vom neuen Bestand; Regel: `kern.md`.

**Bewegen und Ausrichten** — `transform.py` (`moved_object` führt Körper,
Merkmale und Teilträger gemeinsam; ein unbelegter Ausschnitt einer nativen
Fläche entfällt, statt zu wachsen; `apply` vermerkt jede starre Bewegung ohne
Spiegelung am Netz, `perceive.features.note_movement`) · `ops.py` („Transformation“,
`place_on_bed`, `place_group_on_bed` ohne vorberechneten Versatz;
`repair_object` gibt einen heilen Eingang unverändert zurück) · `align.py` ·
`orient.py` (Kandidatenlagen, Stützraum `Orientation.support`; Stapel auf bis
zu `PROJECTION_WORKERS` Arbeitern, Folge und Bits eines Fadens)

**Körper erzeugen und formen** — `primitive_ops.py` (Netzzwillinge der
exakten Grundkörper, `primitive_local_tool()` für Op und Vorschau) ·
`blend.py` · `displace.py` · `lattice.py` · `texture_ops.py`
(`tool_in_outline()`; *Merkmal ändern* am Muster nimmt dasselbe
`flat_tool()`; eben heißt
`faces.FLAT_ENOUGH_FOR_A_TOOL`, nicht `EPS_GEOM`) · `texture.py` ·
`sculpt.py`, `pose.py` (Sammelparameter-Ops) · `sketch_solid.py` (Umriss zu
Netz ohne B-Rep) · `field_ops.py` (Schnittfeld: Raster
`sketch.shapes.grid_centres`, Ursprung fest, Ränder am ganzen Werkzeugumriss,
Kompensation nur Kreis und Langloch; am Netz gibt `_named_bores` nur benannte
Bohrungen aus) · `seal.py`, `seal_ops.py` (`match_opening` nur eindeutig, sonst
`ctx.ask`; Abstand und Überdeckung sind keine Dichtheit) ·
`profile_clamp_ops.py` (vier Rollen in einem Rahmen, Schale mit `lift`; der
Ersatzweg prüft Geometrie, nie Metadaten)

**Wandungen** — `hollow.py` (Aushöhlen mit Entlüftungen) · `lid.py`
(`screw_lid`, `exact_opening`, `collar_hits_wall`; `_short_side` ohne
GEOS-Rechteckecken, die auf macOS/arm64 durch null teilen)

**Druckvorbereitung** — `prepare.py`, `prepare_ops.py` (Bohrungen, Teilen,
Anordnen, Kollisionen, §18.6; Merkmalshandlungen, `pattern_feature`; die
Nullnormalenrichtung am BRep teilt `drill_outward_axis_from_bounds` mit
`brep.ops._bore_span`, die Netzrichtung prüft die Materialsäule) ·
`mouth_cap.py` (Deckel einer gekrümmten Mündung als Höhenfeld, `None` ohne
glatte Fläche) · `autosplit.py` (schneiden, bis es passt) · `symmetry.py`
(`mirror_plane`) · `pins.py` (Passstifte, `first_pin`)

**Kanten und Flächen** — `edge_ops.py`, `face_ops.py` (der Körper wählt den
Kern) · `edges.py` (Züge mit `edge_key` wie in `brep.edit`; `choose` für die Gruppen
nach Lage beider Kerne, `edges_in_kernel`, `EDGE_SELECTION_REJECTED`,
`RadiusLaw`, `ChamferShape`, `sharp_corner`; Werkzeug je Stück als Prisma, am
gebogenen Zug durch die Knoten, `_swept_tool`; `contact_band_limits` je Kante
für die Gruppe, die auslässt, was nicht trägt, `too_narrow_finding`) ·
`faces.py` (Prisma aus dem eigenen Umriss, Versatz je Knoten;
`pushed_features`)

**Messen, Schneiden, Netz, Text** — `measure.py` (§18.3; Fang, `surface_gap`,
`body_overlap`) · `section.py` (§18.2; Schnittkontakte siehe Stolperfallen) ·
`difference.py` (§18.7; eine
ungeschnittene Seite folgt aus der Volumenbilanz, auch mit Hohlräumen,
`_shells_apart`) · `mesh_ops.py` · `colour_ops.py` ·
`paint.py` (`feature_triangles`, auch für Wulst, Kehle, Gewinde) ·
`label_ops.py` (Schriften in `data/fonts/`; Matplotlib gehört zum Extra `geom`;
*Auf beiden Seiten* setzt die Rückseite am ersten Austritt entgegen der
Richtung, `opposite_side`)

## Stolperfallen

**Merkmalshandlungen** (Regeln in `operationen.md`):

- **Eine Kette geht als Ganzes**: Werkzeug aus allen Abschnitten von
  `cavity_chain_at`; die gerundete Mündungskante reist über
  `mouth_blends=True` (`_cavity_plug`, `_paired_cavity_body`,
  `_past_curved_mouths`, `_bore_end_rims`). `remove_feature` fragt
  (`sections`) und schließt erst den ganzen Hohlraum (`_section_closed`,
  `_cavity_tool`, `_chain_plug`); Übergang oder Boden sagt `_stands_alone`,
  nie die Ringzahl.
- **`entrance_mode`**: `keep` ändert einen Abschnitt und meldet die übrigen,
  `follow` nimmt den Einlauf mit, den `bore_entrance` für Op und Panel gleich
  belegt. Alle radialen Profile wachsen gleich. `resize_hole` schließt mit
  `_section_closed(extend_inner=False)`, das Entfernen mit `True`;
  `_cavity_floor` belegt den vorhandenen Boden.
- **Verengung**: eigenes Profil als letzter Abschnitt ihrer Seite
  (`_EntranceSection.narrowing`, `_narrowing_outline`, `_narrowing_radii`,
  `resize.narrowing_swallowed`), ihr Werkzeug reicht in den Abschnitt davor,
  exakt über die eigenen Flächen (`_exact_chain_own_cavity`). Die Senkung auf
  ihrer Bohrung schneidet `_resize_chain_countersink` aus denselben Profilen.
- **Ein Schritt statt zwei**: Lage und Einlauf über `_moved_after_resizing`
  (`PLACE_BOUND_FINDINGS`); exakt trägt der Neuschnitt die übrige Topologie
  (`_exact_rest_carried`). Ob ein Wert die Bohrung ändert, sagen
  `bore_is_unchanged` und `bore_depth_is_unchanged` für Op und Fenster.
- **Maße und Nachprüfung**: `_with_nominal_bore` hält bekannte Maße nur, wenn
  alle Wandpunkte im Sehnenband liegen; `voxel` und `jittered` behaupten
  keine. Über `FEATURE_LIMIT_TRIANGLES` prüft `detect_known` im Radius des
  Werkzeugs, nie mit größerer Toleranz. Nachbarbefunde messen am Werkzeug und
  melden eine dünne Wand nur, wenn sie dünner wird.
- **Platzieren**: `frame_of()`, der Nullvektor bewahrt die alte Semantik; das
  Bohrwerkzeug reicht exakt bis zur Tiefe und wandert in die Welt (`drill`,
  `resize_bore`, `slot_bore`: `_in_world`, Lage entlang der Achse über
  `_heights`), ein Ende in einer Fläche mit Luft dahinter reicht um die Zugabe
  hinaus (`_open_ends`), Kappen auf gemessenen Randebenen legt `_onto_planes`
  genau darauf. `feature_placement_geometry()` schließt Ketten gemeinsam,
  `local_text_body()` trägt jeden Formparameter. Ein Ring ohne gemessene Achse
  hat keine Lage (`FEATURE_WITHOUT_AXIS`); beim Platzieren fallen alte
  Dreiecks- und Trägerbezüge gemeinsam.
- **Durchgang im Langlochzug** (`slot_hole`): Ein einzelner Körper wird über
  seine Hülle geschnitten (`_through_bore_depth`); negative Innenhäute zählen
  am Netz nicht als weitere Körper (`_slot_has_multiple_bodies`). Bei mehreren Körpern
  gilt die vor dem Schließen gemessene Tiefe des ausgewählten Merkmals. Andere
  Körper werden innerhalb dieser Schnitttiefe mitgeschnitten; Material dahinter
  bleibt stehen. `hole_has_separate_contents` gibt nur für diesen Zug eine
  Bohrung mit getrennten Körpern frei, deren eigener Träger innen frei ist;
  eine vollständige Kontaktprüfung schließt auch geometrisch angeschlossene
  Naben aus. `repair.material_part_families` belegt positive Materialkörper
  samt direkt zugeordneten negativen Innenhäuten; die eigene Bohrung wird am
  ganzen Träger geprüft. Eine negative Wurzel, gleiche Vorzeichen an Eltern
  und Kind oder ein unklarer Strahl geben nichts frei. Menü und Ausführung
  teilen den gemerkten, abbrechbaren Beleg; Abbruch vor der Ablage setzt ihn nicht.
  Verbundene Naben und Speichen bleiben gesperrt, auch wenn weitere Körper im
  Objekt stehen (RM-320).
- **Altwinkel** (`measured_frame`, Migration 38 → 39): `slot_angle` bleibt als
  Ausdruck im Schritt; `bore_shape` und `slot_hole` rechnen ihn in jeder
  Auswertung mit der dann aktuellen Achse um, auch wenn deren Komponenten
  Parameter sind. `prepare.slot_frame` hält den Rahmen im Messrauschen neben
  einer Hauptachse stabil. Nicht als Antwort zurückschreiben: Erst Griff oder
  Merkmalfenster können den Marker bei einer Richtungsänderung im heutigen
  Rahmen löschen; Längen- und Positionsänderungen behalten ihn.
- **Innen oder außen** fragt `mesh.on_surface` über die Normale des nächsten
  Dreiecks — nie `trimesh.contains` oder die Parität von
  `ray_hit_distances`. Ein Langlochumriss (`prepare.slot_profile`)
  normalisiert seinen Winkel auf eine halbe Umdrehung; zerlegte Teile
  nummeriert `_loose_parts` nach gerundetem Volumenverhältnis, dann nach Lage.
- **Muster am importierten Zylinder**: Vor dem Schließen legt
  `_aligned_facets` die Mantelecken auf die achsparallelen Facettengeraden aus
  `patterns.cylinder_facet_lines`, die Stopfen und Neuzeichnen danach am
  selben Körper lesen; Ecken liegen im Schnitt zweier Facetten, wo auch der
  Stopfen wechselt, und er endet in der Stirnfläche (`Frame.ends`). Grenze ist
  das float32-Raster (`patterns.facet_tolerance`), abgelehnt meldet
  `pattern.facets_unaligned`. Plattformgleich, abbrechbar, nur quer zur
  Achse; IDs und Slots bleiben, nur bitgleich unberührte Dreiecke behalten
  ihre Verfeinerungsherkunft, ein alter Innenraumbeleg verfällt.

**Schnitte** (`section.py`): Eine Ebene, die erst im Schnitt verzweigte Kanten
erzeugt, wird vor den Verbindern abgesagt (`check_cut_contact`): Schnittfläche
und Modellwand treffen sich längs einer Linie. `CutContactError` zeigt zum
Verschieben auf das Lagefeld. `split_at_plane` prüft beide Hälften, `cut_away`
nur die behaltene. War der Eingang schon offen, bleibt seine eigene
Reparaturdiagnose bestehen. Auto Split lässt Kontaktkandidaten bei Konturzahl
und Vorauswahl aus und nennt den Grund, falls keine verwendbare Lage bleibt.
Die reine Schnittansicht darf die unveränderte Berührung zeigen.

**Reparatur** (`repair.py`):

- `repair()` übernimmt eine Bereinigung nur, wenn offene plus verzweigte
  Kanten nicht zunehmen (`_tears_it_further`). Verschweißt wird überall mit
  `weld`: Suppe zuerst auf `EPS_GEOM` (`_read_soup`), dann nur an Rändern
  (`_joined_at_the_rims`), je Flächenblatt (`_sheets`, `_pseudo_angle`), nie
  zum Schlechteren (`_damage`). `remove_small_components` misst Fläche,
  `remove_hollow_shells` Volumen.
- Gefüllt wird als Band (`_band_between`, `_wall_between_rims`), Fläche mit
  Löchern (`_bridged_holes`), glatteste Triangulierung (`_smoothest_fill`),
  über Ohren (`_loop_triangles`), zuletzt als Fächer — **nie eine Fläche auf
  eine Kante, die schon zwei trägt**; Slot und Farbe vom Rand, eine Fläche
  ohne Dicke bleibt offen (`_flat_fills`).
- Die Schnittsuche läuft einmal je Netz (`crossings_of`); ihr Budget zählt
  genaue Paarprüfungen, am offenen Netz und über `MAP_LIMIT_TRIANGLES` nur der
  Sockel. Vereinigt werden nur verschiedene Schalen und Überlagerungen
  (`_crossing_shape`); behoben ist nur eine vollständig geprüfte direkte
  Vereinigung. Die Lochfüllung des Imports schaltet diese Diagnose nicht zu.
- Außen gilt je Verschachtelungsbaum (`turn_shells_outward`); jedes
  entscheidende Vorzeichen kommt aus `mesh.signed_volume` oder
  `_shell_volumes`, nie aus `enclosed_volume`. Umschlossen heißt ganz darin
  (`_Shells.inside`); eine Schale im Material wird gemeldet, nicht geraten.
  `has_nested_parts` teilt diese Materialtiefe mit `parts_inside_parts`, gibt
  aber `None` bei unentschiedenen Strahlen zurück. `material_part_families`
  befragt auch negative Häute und verlangt vollständig entschiedene,
  alternierende Elternketten mit positiven Wurzeln. Eine positive Insel im
  Hohlraum bleibt eine eigene Familie. Dichtheit und Kontaktfreiheit belegt
  der Aufrufer; `None` gibt keine Familie frei.
  `material_part_count` zählt Familien nach vollständigem Vorbeleg.
  Beide optionalen Abbruchtoken
  reichen durch `_Shells` bis in Gitterzertifikat und genaue Kreuzungssuche;
  Diagnose und boolesche Familien behalten ihre Standardschnittstelle.

**Anordnen und Ausrichten**:

- Die schnelle FDM-Ausrichtung nimmt die erste passende Lage, die
  `slice.orientation.standing_check` am Original trägt. Ohne stehende Lage
  sagt `NoStandingOrientationError` vor jeder Bewegung ab; Resin braucht
  diese Düsenprüfung nicht. Der Standprüfer ist derselbe wie bei Auto Split.
- **Gepackt wird in der Ecke, gelegt in der Mitte** (`arrange_on_bed`,
  `_into_the_middle` nur auf freier Fläche, `arrange.narrow_margin`;
  `occupied` verhindert das Zentrieren). Jeder Körper kommt auf die erste
  angefangene Platte mit Platz, erst dann auf eine neue; eine leere nimmt ihn
  auch zu groß (`settle`). Ob eine Platte mehr hilft, fragt `_fits_alone` die
  Anordnung selbst, wie `first_free_spot`. `orient_for_print` legt mit an
  (`arrange`, `True` auch für gespeicherte Aufträge, ohne Migration —
  Entscheidung Robert), Abstand aus `export.writer.clearance_margin`; nach
  Filament getrennt wird, wo mehr Filamente als Düsen liegen (`by_material`,
  Entscheidung Robert).
- Anordnung, Bauraumprüfung und Orientierung teilen den Druckbereichsvertrag
  aus `core/build_area.py`. Ein Körper: die Op meldet ihre Matrix; mehrere:
  sie bewegt die Merkmale selbst — nie beides; die Erkennung findet die
  Matrix je Körper dann am Bewegungsvermerk des Netzes. `SearchResult.transform` trägt
  die ganze Bewegung samt B-Rep; `fits` entscheidet über die Fläche,
  `oversize` nur über Maße.
- `back_onto_bed` (`keep_on_bed`): die Vorgabe ist aus, den Haken setzt der
  Zug (`MainWindow._on_transform_dragged`); geprüft wird der Eingang, bewegt
  nur in XY, die Matrix trägt beides, von sich aus kein Plattenwechsel.
  Die Platte wechselt nur, wenn der Schritt sie nennt (`translate_object`,
  `plate` ab eins wie im Plattenwähler, null bleibt); gehalten wird dann um
  die Körper der Zielplatte.
- `placed_at_free_spot` (`free_spot` an `load`, `load_step` und
  `fit_to_size`, §17.1 Schritt 6): einmal über `first_free_spot` gerechnet —
  ein Quader aus den Grenzen, Platte für Platte über `arrange_on_bed` mit
  `occupied` (`standing_in`) —, dann als Antwort festgehalten (`spot_*`,
  Felder aus `spot_param`); `arrange.no_free_spot`, wo keine Platte Platz
  hat, ohne Verschiebung kein Befund. Abstand `ARRANGE_SPACING` wie *Auf dem
  Bett anordnen*; Weg 3 legt am fertigen Maß und setzt nach der Reparatur auf.

**Kanten und Flächen**:

- Eine Netzrundung wird nur zwischen genau zwei belegten Ebenen entfernt
  oder geändert (`edges._around` über `perceive.features.planes_beside`; eine
  Wand in `NEARLY_FLAT_ANGLE` zählt als Ebene); `sharp_corner` schneidet die
  Nachbarebenen, nie über den Radius; `reround` bekommt das volle `MeshData`.
- Fehlt eine genannte Kante oder trifft ein Schlüssel mehrere, hält der ganze
  Schritt an; eine Gruppe überspringt, was nicht `workable` ist. Ob eine
  Rundung passt, fragen beide Kerne vorher gleich (`contact_band_limit`).
- Exakte Gruppen: `brep.edit.native_edges_of_chains` (BRep-Karte).
  Nach Breitenfilter neu belegen; ohne Kante absagen. „Zu schmal“ nur gemessen.
  Alle Auslassungen auch bei Fehlern als `Finding.outline` mit Konturpunkt
  `location` erhalten.
- `_arc_steps` folgt `MAX_FACET_SAG` und `MAX_FACET_ANGLE` wie OpenCASCADE.
  Eckknoten aus `MeshEdge.node_indices`, ein Knoten ohne Körper bekommt keine
  Haube (`_corner_hull`). Den Überstand bekommt, was abgezogen wird, nicht was
  außen liegt. Wulststücke gehen einzeln in die Kette.
- Die Formschräge ergänzt unbeanspruchte Wände (`_walls_no_feature_claims`,
  `MOST_WALLS_TO_GUESS` — wer anhebt, prüft die Ränder) und hält ein offenes
  Netz vorher an (`_must_be_closed`). Exakt binden `push_face` und Rundungen
  an vollständige Originalflächen (`Solid.complete_faces_of_triangles`), nie
  über Mittelpunktnähe.

**Slots, Netz, Text, Innenraum**:

- Slotänderungen erhalten Geometrie, Merkmale und `MeshData.cavity`;
  `validate_full_faces` weist Teilflächen zurück. Slots folgen erhaltenen
  Eingangsflächen — gleiche Dreieckszahl beweist nichts. Ein Materialwechsel
  löst nur inkompatible Bindungen, globale Spulenbindungen bleiben.
- Die Differenzansicht überspringt nur identische Netze gleicher Farbe
  (`Difference.recoloured`, `retriangulated` — nie an einer unvollständigen);
  ab wann eine Änderung zählt, sagt `Profile.smallest_printable_volume`.
- **Zwei Dezimierungen, zwei Zusagen**: `decimate` misst, `decimate_for_display`
  nicht (§31); `decimate_mesh(method="fast")` nimmt den Anzeigeweg mit Befund
  `mesh.simplified_unmeasured` (Entscheidung Robert). *Kanten verfeinern*
  erbt Slots über `face_id` und hinterlässt den Ursprung
  (`mesh.remember_refined_units`, weitergereicht bis `to_bytes`).
- Schriften: nur, was mitreist (`BUNDLED_FONT_LICENCES`);
  `FONT_STYLES_AVAILABLE` je Familie; `stroke_width` gegen `narrowest_bead`
  als Befund, ohne Tabelle je Familie; `font_properties` prüft die Familie
  der gefundenen Datei, denn matplotlib fällt still zurück.
- `MeshData.cavity` folgt `transform.apply` und verfällt bei jeder anderen
  Geometrieänderung; ohne sie tragen Innenschalen oder die Entlüftung
  (`_cavity_mesh`), nie ein Hüllquader. Kein Reparaturweg begründet einen
  Messnachweis (`measure.body_overlap`).
