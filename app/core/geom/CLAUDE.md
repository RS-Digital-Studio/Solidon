# `app/core/geom/` — wo Geometrie entsteht

Geometrie nur hier (Regel 2), gegen `manifold3d`/`trimesh`, in Millimetern.
Eingaben bleiben unverändert; `OpResult.outputs` sind neue Objekte.
Regeln: `.claude/rules/operationen.md`, `kern.md`, `dateiformat.md`,
`schichtanalyse.md`, `wartezeit.md`. Herleitungen/Messwerte:
`konzepte/begruendungen/karte-app-core-geom.md`.

## Plattformgleich gerechnet

Gleich auf jeder Maschine sind Grundrechenarten, `sqrt`, `np.cross`, Normen
über eine Achse, `math.hypot`/`math.fsum` und NumPys paarweise Summe; was
plattformabhängig ist, sagt `kern.md`. Die Werkzeuge:

| Frage | Helfer |
|---|---|
| Skalarprodukt, je Zeile zweier Felder | `units.dot3`, `mesh.row_dots` |
| Lage vieler Punkte entlang einer Richtung | `transform.along` |
| Punkte, Richtungen, Netze bewegen | `transform.moved_points`, `turned`, `mesh.shift_body` |
| 4x4-Matrizen zusammensetzen (`a @ b`) | `transform.composed` |
| affine Matrix ohne LAPACK invertieren | `transform.inverse_affine` |
| kürzeste Drehung zwischen zwei Richtungen | `transform.rotation_between` |
| Winkelfunktionen | `units.exact_cos`/`exact_sin`, `exact_*_degrees`, `circle_point` |
| Arkusfunktionen | `units.exact_atan2`, `exact_acos_degrees`, `mesh.stable_arccos`, `stable_arctan2` |
| Sinus und Kosinus vieler Winkel | `mesh.stable_sin_cos`, `periodic_sin_cos` |
| Ausgleichsebene, symmetrische 3x3-Eigenwerte | `units.plane_fit`, `units.symmetric_eigen3` |
| Mitte einer Punktwolke | `units.exact_centre` |
| Normalen und Flächen je Dreieck, Eckennormalen | `mesh.stable_normals`, `mesh.stable_areas` (einzelne Dreiecke), `mesh.stable_vertex_normals` |
| Summen, deren Gleichstand eine Lage entscheidet | `mesh.IntegerGrid` |
| Spatprodukte, eingeschlossenes Volumen mit Vorzeichen | `mesh.triple_products`, `mesh.signed_volume` (körpernah) |
| Nur eine Haut? | `mesh.shell_thickness`, `only_a_skin` |
| Zufall (Stufe 3 der Kette) | `Generator.random` aus den Rohbits, nie `normal` |
| Drehkörper, Kreispunkte | `lathe.cylinder`, `annulus`, `revolve`, `circle_points` |

Kantenwerkzeuge rechnen Längen über `_length`, kleine Systeme über
`_solved3`/`_least_squares3` statt LAPACK, die Kugel über `_icosphere`.

## Absolute Transformationen

`translate_object`/`rotate_object`: mindestens ein Eingang, dieselbe Gruppe
zurück. `mode="relative"` erhält Altschritte, `absolute` speichert Ziele.
`reference_point`: Bodenmitte, Hüllmitte, Ecke oder Merkmal des ersten
Eingangs (`reference_feature` ist Featurefeld). Absolute Drehung: Ausgang
`SceneObject.frame`, Weltachsen X→Y→Z, positive Achsskalierung normalisiert.
Unbekannte/gespiegelte/gescherte Rahmen verlangen relatives Drehen mit
Handlungsvorschlag. Gruppen drehen starr um den gemeinsamen Bezugspunkt.

## Die Boolesche Rückfallkette (§17.2)

Stufen und Vermerke: `boolean.py`, `operationen.md`; erzwungen in
`tests/test_boolean.py`. `_parts_united_first` vereinigt durchdringende oder
verschachtelte Eingangsteile; beim Schließen alter Höhlung auch Flächenkontakt
(`merge_face_contacts=True`). Exakt: `prepare_ops._exact_closing_base`/
`_exact_closing_chain`. Vorfrage `repair.parts_that_cross`: Hüllquaderpaare
(`box_pairs.BoxTree`, `box_pairs_between`) mit `intersections.crossing_pairs`;
dessen Docstring nennt Rundungsgrenzen/Ursprung. Nicht Vereinbares bleibt.
`_meets_the_shells` prüft Werkzeugtreffer an selbstkreuzenden Schalen
(`repair.self_crossing_shells`).

`attributes.in_source_layout`/`prepare_ops._without_scars` erhalten nach jeder
Stufe bitgleich übernommene Dreiecksecken und deren Eingangsfolge, ohne
Wirkung den Eingang selbst. Regel/Messfall:
`operationen.md`, „Boolesches geht durch die Rückfallkette“.

- **Native Stufen** übergeben `Mesh64` und lesen Status und Volumen vor der
  Rückvernetzung; flächiger Kontakt ergibt ein leeres Netz, ob das gilt, sagt
  `allow_empty`. Kontaktreste entscheidet `kernel_jobs.native_contact` an der
  Float64-Grenze `gamma(8) * max|Koordinate| * Oberfläche` je Komponente —
  keine Drucktoleranz; `EPS_GEOM` ist kein Mindestvolumen. Verbleibende Schalen
  werden angefügt, nie neu vereinigt (das füllte Hohlräume).
- **Qualität und Abbruch reichen durch**, auch Werkzeugvereinigung,
  Eckanschluss und erneute B-Rep-Erkennung; keine Hochstufung des Entwurfs.
- **Nur exakte Eingänge** gehen über `brep.edit.boolean`; ist ein Netz
  beteiligt, gilt die Kette. Beide prüfen leere und wirkungslose Ergebnisse;
  `body_split` ist das eine Urteil über einen zerfallenden Körper.
- **Wer mit `trimesh` an einer Ebene teilt und danach verschweißt**
  (`section._apply`, `faces._draft_tools`), legt vorher auf die Ebene, was
  trimesh zu ihr zählt (`section.settled_on_plane`), sonst bliebe der Körper
  offen.
- `kernel_jobs.slice_sections` liefert direkte Schichtschnitte als Ringfelder
  über `kernel_process.run`; Aufbau und Schnitt sind gemeinsam abbrechbar.
- Eine Änderung am gemeinsamen Kern entwertet den Ergebnis-Cache
  (`paths.results_cache_dir()`, §38).
- Nach Vereinigung prüft `prepare_ops.union_bore_findings` Bohrungsräume
  **aller Eingänge**: verbleibende Luft und ganze alte Mündungen samt
  koplanaren Deckeln. `filled`, `enclosed`, `blind`, `partial` sind gemessen;
  `unchecked` ersetzt fehlenden Nachweis. Merkmalverlust beweist nichts.

## Die Karte

`__init__.py` trägt nur den Paketdocstring.

**Grundlage** — `mesh.py` (die Hülle um den Kern, §9; `read_mesh`,
`unique_edges`, `edge_table`; `MeshData.held_bytes`/`lean` für den Cache; `python_values` für Millionen Werte als
Python-Zahlen, stückweise; `on_surface` über einen Index, den hält, wer
denselben Körper mehrmals fragt — `prepare.surface_index_of`;
`ray_hits_batch`, dessen Index nur wählt, welche Paare rechnen, nie ihren
Wert; `lifted_caps`, Zwilling von `brep.edit.collared`) · `boolean.py` ·
`attributes.py` (Slots durch eine Operation, §20; `transfer`, `with_slots`,
`carry_refined_units`) · `lathe.py` · `enclosure.py` (Verschachtelung ohne
`rtree`) · `intersections.py` (Selbstdurchdringung als Feld, für Karte,
Bereichstest und Formschritt) · `box_pairs.py` (Hüllquaderpaare zwischen zwei
Dreiecksmengen) · `repair.py` (unten) · `deviation.py` (Grenzen ausgefüllter
Originaldreiecke zu einem belegten `SurfacePatch`, Budget je Dreieck; keine
neue Einpassung, Geometrie oder Cache) · `contours.py` (`section_of`,
`offset_section`: ungültige Konturen werden nicht still repariert, Spiel gibt
der Aufrufer)

**Hilfsprozess** — `kernel_jobs.py`: GIL-Aufrufe (`manifold3d`, `csgraph`,
die Voxelstufe `voxel`) mit reinen Feldern; `JOBS` Einstieg, `serve` Helfer, `pack`/`copied` geteilter
Speicher. `_opened`: nur ENOMEM und Windows 8/14/1450/1455 werden
`MemoryError`; ENOSPC bleibt Transfer-`OSError` und pausiert den Helfer.
`kernel_process.py`: bitgleiches `run`, Vorrat, Abbruch/Tod/Rückfall,
`warm_up`, `shutdown`; `NOT_A_KERNEL_FAILURE` schützt breite Fänge.
Vertrag: `kern.md`; Startplätze, Stoppreste und Abbau: Begründungen,
„Hilfsprozess: Startplätze und Abbau“.

**Bewegen und Ausrichten** — `transform.py` (`moved_object` führt Körper,
Merkmale und Teilträger gemeinsam; ein Teil einer nativen Fläche folgt nur
belegt, sonst entfällt er, statt zu wachsen; `apply` vermerkt jede starre Bewegung ohne
Spiegelung am Netz, `perceive.features.note_movement`) · `ops.py` („Transformation“,
`place_on_bed`, `place_group_on_bed` ohne vorberechneten Versatz;
`repair_object` gibt einen heilen Eingang unverändert zurück) · `align.py` ·
`orient.py` (Kandidatenlagen, Stützraum `Orientation.support`; Stapel auf bis
zu `PROJECTION_WORKERS` Arbeitern, Folge und Bits eines Fadens)

**Körper erzeugen und formen** — `primitive_ops.py` (Netzzwillinge der
exakten Grundkörper, `primitive_local_tool()` für Op und Vorschau) ·
`blend.py` · `displace.py` · `lattice.py` · `texture_ops.py`
(`tool_in_outline()`, *Merkmal ändern* am Muster nimmt dasselbe
`flat_tool()`; eben heißt
`faces.FLAT_ENOUGH_FOR_A_TOOL`, nicht `EPS_GEOM`) · `texture.py` ·
`sculpt.py`, `pose.py` (Sammelparameter-Ops; `SculptPreview` rechnet die
Formsitzung Zug für Zug bitgleich zur Op, Fassung je Zug `Stroke.brush`,
Folgeetappe nur im Gebiet; `pose.Skin` beugt) · `sketch_solid.py` (Umriss zu
Netz ohne B-Rep) · `field_ops.py` (Schnittfeld: Raster
`sketch.shapes.grid_centres`, Ursprung fest, Ränder am ganzen Werkzeugumriss,
Kompensation nur Kreis und Langloch; am Netz gibt `_named_bores` nur benannte
Bohrungen aus) · `seal.py`, `seal_ops.py` (`match_opening` nur eindeutig, sonst
`ctx.ask`; Abstand und Überdeckung sind keine Dichtheit) ·
`profile_clamp_ops.py` (vier Rollen in einem Rahmen, Schale mit `lift`; der
Ersatzweg prüft Geometrie, nie Metadaten)

**Wandungen** — `chamber_ops.py` (*Kammer ändern*; `rims_of`, `flat_cap`) ·
`closure_ops.py` (*Verschluss ändern*: Spiel und Drehweg, Werkzeuge aus dem
Flankenumriss) · `hollow.py` (Aushöhlen mit Entlüftungen) · `lid.py`
(`screw_lid`, `exact_opening`, `collar_hits_wall`; `_short_side` ohne
GEOS-Rechteckecken, macOS/arm64) · `lid_hinge.py` (Deckelscharnier: Achse,
Kragenraum, Augen; *Stift für Bohrung*) · `bore_pin.py` (Kopf und
Gewinde des passenden Stifts) · `container_ops.py` (Behälter, Deckel,
Einsätze; Entwurf in `core/lid_flow.py`) · `counter_form_ops.py` (Taschen aus
dem Schatten der Teile)

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
`_shells_apart`; große Vergleichsnetze durchlaufen zuerst die bestehende
koplanare Entlastung aus `mesh_ops._exactly_flattened`, mit unveränderten
Eingängen und denselben Dichtheits-/Volumenprüfungen) · `mesh_ops.py` · `colour_ops.py` ·
`paint.py` (`feature_triangles`, auch für Wulst, Kehle, Gewinde) ·
`label_ops.py` (Schriften in `data/fonts/`, Satz über `glyphs.py`;
*Auf beiden Seiten* setzt die Rückseite am ersten äußeren Austritt entgegen
der Richtung, `opposite_side`; negative Innenhäute und die belegte, nicht
offene Höhlung (`MeshData.cavity_open`) werden übersprungen, auch wenn eine
Entlüftung die Häute verbindet) · `label_layout.py` (Schrift auf Bogen und
Rundung, Radius aus `measured_radius`)

## Stolperfallen

**Merkmalshandlungen** (Regeln in `operationen.md`):

- `_shell_prints` gruppiert Schalen einmal; Abbruch zwischen Blöcken und Ergebnissen.

- Hohlraumwerkzeuge entscheiden Richtung und Gültigkeit über das körpernahe
  `signed_volume`; Schwerpunkt und Trägheit werden dafür nicht berechnet.
  `_bore_end_rims` prüft alle Mündungsränder gemeinsam über
  `_shares_in_material`, mit denselben Proben und unveränderten Bodenregeln.
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
- `DrillParams`/`PlugParams`: `LARGEST_THREAD`; Sehnen: `shapes.turn_segments`.
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
- **Langloch durch getrennte Körper**: `_through_bore_depth` schneidet durch
  die Trägerhülle. `_slot_has_multiple_bodies` zählt negative Innenhäute nicht
  zusätzlich. `_slot_in_separate_carrier` trennt einen vollständig belegten
  Träger ab; Nachbarn bleiben getrennt, Stifte werden nur im bisherigen
  Bohrungshohlraum gekürzt. Verbindender Versatz/Verkleinerung verlangt vorher
  Zerlegung. `hole_has_separate_contents` gibt ausschließlich diesen Zug frei:
  eigener Träger innen frei, Kontaktprüfung am Träger und seinen Nachbarn
  (`_near_the_carrier`). Angeschlossene Naben/Speichen bleiben gesperrt (RM-320).
  Menü und Ausführung teilen den abbrechbaren Beleg; nur fertige Belege werden
  gemerkt. `repair.material_part_families` ordnet negative Innenhäute positiven
  Materialkörpern zu; negative Wurzel, gleiche Eltern-/Kindvorzeichen oder
  unklarer Strahl erlauben keine Freigabe.
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
Reparaturdiagnose bestehen. Auto Split lässt Kontaktkandidaten aus und nennt
den Grund, falls keine verwendbare Lage bleibt.
Die reine Schnittansicht darf die unveränderte Berührung zeigen.

**Reparatur** (`repair.py`):

- `repair()` übernimmt eine Bereinigung nur, wenn offene plus verzweigte
  Kanten nicht zunehmen (`_tears_it_further`). `weld` verschweißt die Suppe
  auf `EPS_GEOM` (`_read_soup`), dann an Rändern (`_joined_at_the_rims`), je
  Flächenblatt (`_sheets`, `_pseudo_angle`), nie schlechter (`_damage`).
  Entfernt wird nach Fläche (`remove_small_components`), Volumen
  (`remove_hollow_shells`), auf Wunsch Einschluss (`remove_inner_shells`).
- Gefüllt wird als Band (`_band_between`, `_wall_between_rims`), Fläche mit
  Löchern (`_bridged_holes`), glatteste Triangulierung (`_smoothest_fill`),
  über Ohren (`_loop_triangles`), zuletzt als Fächer — **nie eine Fläche auf
  eine Kante, die schon zwei trägt**; Slot und Farbe vom Rand, eine Fläche
  ohne Dicke bleibt offen (`_flat_fills`).
- `separate_touching_sheets` trennt Berührkanten, Rest mit anderer Paarung;
  Falten glättet `smooth_folds` nur mit *Überschneidungen auflösen* (RM-550).
- Die Schnittsuche läuft einmal je Netz (`crossings_of`); ihr Budget zählt
  genaue Paarprüfungen, am offenen Netz und über `MAP_LIMIT_TRIANGLES` nur der
  Sockel. Vereinigt werden nur verschiedene Schalen und Überlagerungen
  (`_crossing_shape`); behoben ist nur eine vollständig geprüfte direkte
  Vereinigung. Die Lochfüllung des Imports schaltet diese Diagnose nicht zu.
- Außen gilt je Verschachtelungsbaum (`turn_shells_outward`), Vorzeichen nur
  aus `mesh.signed_volume`/`_shell_volumes`. `_Shells.inside` verlangt ganzes
  Umschließen; Schalen im Material werden gemeldet. `parts_inside_parts`
  zählt nur belegte Materialtiefe. `material_part_families` verlangt auch an
  negativen Häuten eindeutig alternierende Elternketten mit positiver Wurzel;
  positive Hohlrauminseln bleiben eigene Familien. Aufrufer belegen
  Dichtheit/Kontaktfreiheit; `None` gibt nichts frei. `material_part_count`
  zählt erst nach Vorbeleg.

**Anordnen und Ausrichten**:

- `centre_slender` verbessert anschließend die freie Mittellage schlanker
  Körper auf derselben Platte; `knowledge.print_settings.is_slender` gilt
  auch im Druckrat. Migrierte alte Schritte behalten ihre bisherige Lage.
- Die schnelle FDM-Ausrichtung nimmt die erste passende Lage, die
  `slice.orientation.standing_check` am Original trägt. Ohne stehende Lage
  sagt `NoStandingOrientationError` vor jeder Bewegung ab; Resin braucht
  diese Düsenprüfung nicht. Der Standprüfer ist derselbe wie bei Auto Split;
  `orient.no_footing` und `FeatureContinuation` erklären die Begründungen.
- `arrange_on_bed` packt in der Ecke, `_into_the_middle` zentriert nur freie
  Flächen (`occupied`, `arrange.narrow_margin`). Erste angefangene Platte mit
  Platz, sonst neue; leere nehmen auch Übergröße (`settle`). `_fits_alone`
  prüft Zusatzplatten wie `first_free_spot`. `orient_for_print` ordnet mit an
  (`arrange=True`, auch Altschritte ohne Migration, Entscheidung Robert);
  Abstand: `export.writer.clearance_margin`. `by_material` trennt bei mehr
  Filamenten als Düsen (Entscheidung Robert).
- Gemeinsamer Druckbereich: `core/build_area.py`. Ein Körper meldet die
  Transformationsmatrix, mehrere bewegen Merkmale selbst; nie beides.
  Erkennung liest je Körper den Netzbewegungsvermerk. `SearchResult.transform`
  trägt die ganze Bewegung samt B-Rep; `fits` prüft Fläche, `oversize` Maße.
- `back_onto_bed` (`keep_on_bed`): die Vorgabe ist aus, den Haken setzt der
  Zug (`MainWindow._on_transform_dragged`); geprüft wird der Eingang, bewegt
  nur in XY, die Matrix trägt beides, von sich aus kein Plattenwechsel.
  Die Platte wechselt nur, wenn der Schritt sie nennt (`translate_object`,
  `plate` ab eins wie im Plattenwähler, null bleibt); gehalten wird dann um
  die Körper der Zielplatte.
- `placed_at_free_spot` (`free_spot` an `load`, `load_step` und
  `fit_to_size`, §17.1): einmal über `first_free_spot` — Grenzquader, je
  Platte die Stelle nächst der Mitte (`_nearest_the_middle`), leer oder voll
  über `arrange_on_bed` —, dann festgehalten (`spot_*` aus `spot_param`);
  Beim Import zählen alle tatsächlich benutzten Spulen je Kandidatenplatte
  gegen die Düsen; `slot_identity` aus der Übergabe bestimmt ihre Identität.
  Unbenutzte Deklarationen zählen nicht, Baugruppen bleiben zusammen. Die
  Gruppierung gespeicherter Anordnungen bleibt unverändert.
  Der Import nutzt vorhandene passende Platten samt Lücken und ergänzt danach
  eine neue, auch über zwölf; nur ein begrenzter Anordnungsauftrag setzt
  `MAX_PLATES`. Ohne Verschiebung gibt es keinen Befund. Abstand
  `ARRANGE_SPACING`; Weg 3 legt am fertigen Maß, nach der Reparatur.

**Kanten und Flächen**:

- Eine Netzrundung wird nur zwischen genau zwei belegten Ebenen entfernt
  oder geändert (`edges._around` über `perceive.features.planes_beside`; eine
  Wand in `NEARLY_FLAT_ANGLE` zählt als Ebene); `sharp_corner` schneidet die
  Nachbarebenen, nie über den Radius; `reround` bekommt das volle `MeshData`.
- Fehlt eine genannte Kante oder trifft ein Schlüssel mehrere, hält der ganze
  Schritt an; eine Gruppe überspringt, was nicht `workable` ist. Ob eine
  Rundung passt, fragen beide Kerne vorher gleich (`contact_band_limit`).
- Exakte Gruppen: `_group_that_fits` bindet über
  `brep.edit.native_edges_of_segments`, `_on_a_solid` rundet über
  `brep.edit.fillet_group`; Regeln `kanten.md`.
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
  als Befund, ohne Tabelle je Familie; `glyphs.font_file` lehnt fehlende
  Datei oder Schnitt ab.
- `MeshData.cavity` (samt `cavity_open`) folgt `transform.apply` und verfällt
  bei jeder anderen Geometrieänderung; ohne sie tragen Innenschalen oder die
  Entlüftung (`_cavity_mesh`), nie ein Hüllquader. Kein Reparaturweg begründet
  einen Messnachweis (`measure.body_overlap`).

Kreis-/Merkmalsmuster und Spiegelungen: `transform.pattern_centre` speichert
bei drei leeren Koordinaten einmal die Körpermitte als `answered`. Explizite
Punkte bleiben fest, Teilangaben sind Fehler; lineare Muster lesen nichts.
Alte Spiegelungen behalten `follow_anchor`, explizite Punkte haben Vorrang.

`slice._chain.orientation_scores` und NumPy-Rückfall verwenden gleiche
Grundoperationen/IntegerGrid-Raster und liefern je Richtung bitgleiche Werte.
Der Reserveplatz prüft Stand vor Bauraumpassung. Eigenkreuzungen prüfen alle
koplanaren Überlagerungen; gemeinsame Kanten und widerlegte Kollinearität
ersparen nur bereits entschiedene Restfragen.
