# `app/core/brep/` — der zweite Konstruktionskern

Boundary Representation über OpenCASCADE, **neben** dem Mesh-Kern, nicht an
seiner Stelle (§30): echte Kanten, runde Fasen und Verrundungen, Boolesche ohne
Tessellationsartefakte, STEP hinein und hinaus. Weicht B-Rep vom Mesh-Kern ab,
ist das ein Befund, kein zweiter Wahrheitsbegriff. Regeln:
`.claude/rules/operationen.md`, `kern.md`. Herleitungen:
`konzepte/begruendungen/karte-app-core-brep.md`.

## Die Karte

| Datei | Rolle |
|---|---|
| `kernel.py` | `Solid` und sein Weg ins Netz (ohne Dreiecke ohne Fläche, `_tessellated_body`), `available()`, `boolean_builder` (`SetRunParallel`, bitgleich), Merker je Körper (Volumen, Hüllquader, `is_closed`, `face_neighbours`), `nearest_distance`, `untrimmed_surface` |
| `profiles.py` | Vom Skizzenumriss zum Körper (§30.1): Gewinde, Formschräge, Bahn, Übergang, Querschnitte für Profilklemmen und Dichtnuten (`face_of`, `offset_face`, `face_boolean`, `prism`), `round_cord`, `shell_open_at`, `top_faces_of` |
| `ops.py` | Die Operationen (§25, §10): `mesh_to_exact`, `brep_to_mesh`, `thread_exact`, `create_brep_box` …; `drill_brep_hole`, `shell_exact` versteckt, `prepare_ops.drill_hole` und `hollow_object` rufen sie |
| `edit.py` | Einen Körper formen: Kanten, Bohrungen, Rundungen, Flächen, Lage; `fuse_solids` vereinigt berührende Volumenkörper mit nativer Flächenhistorie; `fillet_group` rundet eine belegte Gruppe und lässt je Kontur aus, was OpenCASCADE nicht baut (`GroupFillet`, Suche `_GroupSearch`, Kandidat `_group_candidate`, Ortung `_RoundsOf`); `fillet`/`chamfer` als exakte Hälfte von `geom/edge_ops.py` |
| `features.py` | Merkmale aus der Topologie (§21), `features_of`; „durchgehend?" erst nach dem Gewinde (`_ThroughQuestion`); Muster mit der Netzsuche `perceive.patterns` an der Tessellierung |
| `canonical.py` | Geprüfte Träger mit wirklichen Grenzen (`surface_sample`, `horizontal_area`); Kegel bis in die Spitze (`_apart_from_the_apex`), gespiegelte Ebene über die Pole (`_pole_plane`) |
| `thread.py` | Gewinde an importierter Geometrie (§21.1) |
| `properties.py` | Volumen, Fläche, Schwerpunkt (§11); `estimated_volume` nur zur Plausibilität, nie veröffentlicht |
| `section.py` | Exakter Ebenenschnitt der Skizzenprojektion; `horizontal_regions` für `geom.lid` |
| `lettering.py` | Schrift als exakte Flächen, nonzero gefüllt (`glyph_contours`, `letter_faces`, `letters`; gerufen von der Operation `label_text`) |
| `step.py` | STEP hinein und hinaus |
| `from_mesh.py` | Vom Dreiecksnetz zum exakten Körper ohne Verlauf |

## Die Einbahnstraße — und die Umwandlung daneben

```
B-Rep  ──────>  Mesh      jederzeit (brep_to_mesh, jede Netzoperation)
B-Rep  <──╳───  Mesh      kein Rückweg: die alten Kanten sind verloren
B-Rep  <·······  Mesh      Umwandlung (mesh_to_exact): erkannt, nicht zurückgerechnet
```

**Ein Rückweg existiert nicht** — die „exakte" Verrundung wäre ein Vieleck.
**Die Umwandlung** baut aus den erkannten Flächen einen neuen Körper, ohne
Verlauf, mit gemessener Abweichung; der Rest bleibt Dreieck. Einen exakten
Eingang reicht sie unverändert durch, mit Hinweis (`brep.already_exact`):
Gespeicherte Verläufe, deren Schritt davor heute exakt bleibt, rechnen weiter.
`ops.converted_finding` meldet jede absichtliche Vernetzung.

`from_mesh.convert`: Stufen von `surface_regions` bis `source_deviation` im
Moduldocstring, Grenzen an `CORNER_REACH`, `SNAP_RCOND`, `PLANAR_SPAN`,
`FACET_TILT`, `MAX_FREEFORM_FACES`; ungültige Flächen fallen über `_demoted`
ins Dreieck. `Solid.converted_from` hält das Quellnetz nur im Speicher, nur am
unveränderten Ergebnis (`HasSourceDeviation`).

## Stolperfallen

### Eigentum an der nativen Form

- **`Solid` kopiert beim Eintritt** ohne Triangulation (`BRepBuilderAPI_Copy`,
  `copyMesh=False`); `shape` und Handles nur lesen, `frozen` schützt keinen
  OCCT-Handle. Builder, STEP-Transfer (`copy_shape`) und Tessellation arbeiten
  privat, samt gewählter Flächen und Kanten; ein neuer `Solid` trennt geteilte
  Unterformen; `unround` wählt auf der Kopie.
- **`boolean_builder` legt leer an**: NonDestructive und Fuzzy vor dem ersten
  Build; der Zwei-Shape-Konstruktor rechnet sofort.
- **Zuordnung nur über belegte Historie**, nie Besuchsreihenfolge oder alte
  Dreiecksnummern: `ModifiedShape`; `_copied_faces`/`_copied_edges` aus
  **einer** Kopierprimitive, bijektiv, sofort gebaut; `faces_of_triangles`
  kehrt `triangles_of_face` geprüft um. Verschweißt wird je Körper
  (`_welded_per_solid`): Berührende Körper bleiben zwei Schalen. Nur wo eine
  Operation flächigen Kontakt ausdrücklich auflösen muss, vereinigt
  `fuse_solids` die nativen Körper — das Ergebnis bleibt ein Körper — und
  erhält dabei belegte Flächen- und Filamenthistorie.
- **`transformed_with_faces`** bleibt bei Maßstab, Spiegelung, Scherung exakt
  (`gp_GTrsf`; `gp_Trsf.SetValues` orthogonalisiert); Matrix endlich, affin,
  umkehrbar; Körperzahl, Geschlossenheit, Gültigkeit halten. Rauschen bis
  `_SIMILARITY_NOISE` legt `_nearest_similarity` auf die Ähnlichkeit. Starr
  belegt `IsPartner`, kein Integral und keine Gültigkeitsprüfung, auch an
  offenen Hüllen; sonst das skalierte Volumen, ohne Volumen die Fläche; eine
  Identität baut nichts.
- **Was ein Körper über seine Flächen weiß, weiß er einmal** (`Solid.surface`,
  `face_properties`, `face_index`); Kopie und neue Qualität beginnen kalt.
  Grenzen aus `AddOptimal`, kein nativer Aufruf je Frame — ein Cache ersetzt
  keinen Eigentumsvertrag.
- **`selected_faces`** (`push_faces`, `unround`, `reround`): ganze aktuelle
  Flächen, Abdeckung belegt der Aufrufer, `checked_face_indices` prüft ohne
  Cache; Versetzen je Ebenennormale, Entfernen genau ein Zylinder mit altem
  Radius. Unpassend sucht keinen Ersatz, nur `None` den alten Lageweg. Abbruch
  an jedem nativen Schritt lässt Eingabe und Cache stehen.
- **Filamentslots** je nativer Fläche (`face_slots`) reisen über
  `_copied_faces`, auch in `to_mesh(deflection=)`; `with_triangle_slots` nimmt
  nur widerspruchsfreie ganze Flächen, kopiert die Form nicht und teilt Merker
  und Dreiecke (`_recoloured`, RM-557: ein Filament rechnet nichts neu); eine
  eigene Kopie für einen Arbeiter ist `detached`. `carried_face_slots` folgt nur belegten Ersetzungen (`ModifiedShape`,
  `ShapeBuild_ReShape`): erste Quelle, Abzugswerkzeuge färben nie, neue Flächen
  Slot null, Widerspruch wird abgewiesen; `keep_filament_boundaries` hält
  Slotgrenzen. Die Zuordnung entsteht beim Öffnen aus dem Verlauf.
- **Die Wandschranke vor Fillet und Chamfer** misst die Trägerflächen der
  Kanten, am Rasterrand per `geom.measure.wall_thickness`; eine nur am Endpunkt
  berührende Fläche begrenzt nichts.

### Merkmale aus der Topologie

- **`canonical.describe` ist die eine Trägerauskunft.** Ein Kandidat gilt erst
  mit frischem Recognizer, Status, endlichem `GetGap` und der Gleichung über
  **alle** rationalen Bézier-Koeffizienten, nur mit `EPS_GEOM`. Ungeklärtes,
  Offsets ohne Normalennachweis und geschachtelte bleiben unklassifiziert;
  periodische Trimmungen werden geteilt, nie abgeschnitten; NURBS-Parameter
  sind nie Winkel oder Länge; die Innenprobe liegt in der Trimmkontur.
- **Maße von der Originalfläche**: Achse, Kugelzentrum, Kegelspitze und Nappe
  (Halbwinkel im Bogenmaß, über beide Nappen getrimmt kein Kegel,
  Spitzenparameter nur in der Endpunktklammer auf null), Endlagen über Abstände
  (`AddOptimal` hat Zuschlag; am Zylinder, sobald ein Rand weder Mantellinie
  noch Querkreis ist, `canonical._rims_on_grid`), Winkel aus den Randkurven, Radien nur angezeigt
  gerundet. Kugel: Materialseite aus Hautnormale und Radiale; `centre` ist
  auch an einer Eckrundung der Mittelpunkt ihrer Trägerkugel.
- **Orientierung**: `TopAbs_REVERSED` dreht die Ebenennormale; Bohrung gegen
  Zapfen, Senkung gegen Kegel sagen Orientierung **und** `Position().Direct()`
  zusammen. Unvollständige U-Spanne heißt `partial`.
- **`SurfacePatch`** trägt echte Tessellierungsdreiecke; Langloch, Ring und
  Kammer bekommen nur ihre Teilflächen, native Belege verdrängen Netzfits,
  Reste bekommen keinen erfundenen Träger. `measure_sources` nennt jedes native
  Maß; ganze Restflächen integrieren Fläche und Mitte, Teilflächen behalten den
  Netzweg, das offene Langloch bekommt seine Träger nachträglich
  (`slots.native_open_slot_measures`). Ringstücke desselben Trägers sind ein
  Merkmal, auch über einen Durchbruch, wie am Netz (`_joined_tori`,
  `perceive.features._merged_tori`); freie Rundungen über `detect_curved_faces`.
- **Luftkammern** (`_void_features`): Eine invertierte Außenschale ist kein
  Innenraum, ein Sacklangloch braucht eine echte Mündung, ein ganz innerer
  Langlochmantel samt Abschlüssen gehört zur Kammer; Inseln zählen nicht zum
  Volumen, ihre Flächen zur Grenze, ihre Kammern sind eigene; jeder Luftraum
  einmal; `void.centre`/`size` sind Welt-AABB. Keine Handles oder Builder im
  Merkmal; `voids_instead_of_phantom_bores` verdrängt Phantome.
- **Langloch** (Regel in `operationen.md`): Der Mantel ist geschlossen — keine
  Nachbarfläche der vier setzt ihn längs der Achse fort
  (`_continues_the_mantle`). Ein von der Naht geteilter Mantel
  wird vorher zusammengeführt (`_seam_split_cylinders_joined`; der Umfang einer
  Bohrung ist `perceive.features.FULL_TURN_SPAN`, gelesen über `_full_turn`). Die Mündungsfase gehört dazu (`_mouth_chamfers_folded`,
  Nennmaße ohne Fase); auf schräger Fläche macht OpenCASCADE ihre Bögen zu
  BSplines — was `partial_cone_patch` als Kegelstück liest, trägt die Fase.
  `MIN_ROUND_ARC` fragt `_describe` am nativen Umfang, einen Zylinder erst nach
  der Nahtzusammenführung (`_short_arcs_dropped`). Tiefe und Mitte über beide
  Bögen, auf die Achse des ersten gelegt (`_one_slot`), wie am Netz.
- **Bohrung**: Mitte auf der Achse in der Mitte der V-Spanne. Nicht
  durchgehend, wenn eine Nachbarfläche über die Achse oder einen der
  `THROUGH_RINGS` in die Mündung reicht — gemessen, nicht geschnitten.
- **Zylindrische Rundung**: `centre` ist dieselbe begrenzte Achsmitte wie im
  Netzfit, auch bei zusammengeführten Teilflächen. Der Flächenschwerpunkt
  dient nur der Materialseitenprobe. Kugelige Eckrundungen tragen die
  Trägerkugelmitte ohne erfundene Achse; Ecke ist eine Kugel ab
  `perceive.features.CORNER_NEIGHBOURS` verrundeten Nachbarn ihres Radius
  (`rounds_the_corner`), dieselbe Frage wie am Netz. Zu große Zylinder nimmt
  `_oversized_rounds_dropped` heraus (Regel: `operationen.md`, Frage
  `perceive.features.cylinder_fits_in_the_body`).
  Werkzeuge: Material über trägen `profiles.for_object`, Profil aus
  `geom.prepare.drill_outline`, analytisch rotiert;
  `revolved_bore_tool`/`clipped_bore_tool` schneiden an den echten Randebenen
  und schließen mit dem alten Radialprofil. Bei einer Nullnormalen teilt
  `_bore_span` die Außenrichtung über
  `geom.prepare.drill_outward_axis_from_bounds` mit der Platzierungsvorschau.
- **Ein Langloch wird vom Boden zur Mündung aufgezogen** (`profiles.extrude`,
  sonst dreht `slot_angle` andersherum; `_bore_span`). `slot_bore` vereinigt
  koplanare Flanken, `fill_bore` endet an einer Randöffnung an der Außenwand.
- **Getrennte Träger**: `edit.separated_solids` gibt private Teilkörper mit
  ursprünglichen Flächenslots und der durch die Kopierhistorie belegten
  Zuordnung ihrer nativen Flächen zurück. Der Langlochzug bearbeitet nur
  seinen vollständigen Träger und setzt Nachbarn anschließend ohne Vereinigung
  zum Verbund zusammen.

### Gewinde: erzeugt, gelesen, genäht

- **`thread_exact`** benennt `thread_1` mit unveränderten Werten und
  `handedness="right"` (nie für Importe, Spiegelungen führen nach), erbt die
  sieben Lagefelder (`PositionedPrimitiveParams`) und nimmt seine Flächen aus
  der Erkennung (`features_of(known_threads=…)`).
- **Ein Bolzen ohne Gang ist keiner**: `_is_sound_rod(at_least=)` verlangt den
  halben Gang nach Pappus am groben `estimated_volume`, sonst Absage.
- **Genäht, nicht vereinigt**: `helical_thread` (auch `threaded_rod`) baut
  **einen** Körper ohne Boolesche (Gründe an `_HELIX_PRECISION`);
  `_fuzzy_boolean` nie über ein Gewinde. Neue Gewinde werden genäht, auch
  mehrgängige und kegelige (`starts=`, `taper=`).
- **Gelesen an den Kanten** (`read_thread`, Verfahren im Moduldocstring):
  gruppiert mit `RADIUS_TOLERANCE`/`PHASE_TOLERANCE`, nie über `round`
  (Regel 6); Gangzahl einmal in `helix.starts_from_periodicity`, Rille gegen
  `helix.MEASURED_GROOVE_RANGE`, beide träge importiert. Ohne volle Umdrehung,
  Wendel oder Rille ein Grund, nie eine geratene Steigung; ein Zug beginnt am
  freien Ende (`_ordered_points`).
- **Kegelig** (`_is_tapered`; `ThreadReading.taper` halber Winkel mit
  Vorzeichen, am Merkmal `taper` in Grad): Ändern, Entfernen und `counterpart`
  sagen ab, das Gegenstück auch an mehrgängigen.
- **`thread_features`** gibt die Felder des Netzvertrags, alle `native`
  (`diameter` ist das Nennmaß), und verdrängt Phantome; ein Gewinde je Körper,
  Zwilling `find_helices` (`tests/test_thread_import.py`).

### Kanten, Rundungen, Flächen

- **Eine Kante hat einen Schlüssel, keine Nummer**: `edge_key` (Mitte und
  vorzeichenlose Richtung, gerundet) darf in die Projektdatei; `named_edges`
  löst ihn, `fillet`/`chamfer` nehmen `keys`. Eine verschwundene Kante hat
  ihren eigenen Satz. **Im Aufruf ist die Nummer der Beleg**: `selected_edges`
  (`checked_edge_indices`, `_edges_for`) geht vor `keys`, ohne Rückfall; die
  Auswertung bindet über `native_edge_indices`, nie über `edges_of`.
  `edge_points` gibt die Kante nach `DEFLECTION` als Punktfolge.
- **`native_edges_of_segments` belegt je Strecke** (`native_edges_of_chains`
  fasst je Zug zusammen): Netzknoten und Dreiecksnachbarn führen über
  `face_sources` zu genau zwei nativen Flächen; mehrere gemeinsame Kanten
  entscheidet der Sehnenverlauf, projizierte Intervalle belegen die
  vollständige Abdeckung je native Kante. `None` heißt unbekannt, auch bei
  einem Knick innerhalb einer C0-Fläche. Abbruch reist mit.
- **`fillet_group`** nimmt eine von `geom.edge_ops` belegte Gruppe konstanter
  Radien und gibt `GroupFillet` zurück (Körper, ausgelassene und zu dünn
  getragene Kanten, dünnste Wand). Konturen liest `_RoundsOf` aus dem Builder;
  `_edge_walls` misst die Wand je Kontur einmal; `_GroupSearch` baut jede
  Kombination höchstens einmal auf frischer Form (`_group_candidate`, Prüfungen
  wie `_built`, Volumen zuletzt) und meldet Fortschritt. Reihenfolge und
  Grenzen: `operationen.md`. Eine ausdrücklich gewählte Kante und ein
  veränderlicher Radius bleiben beim strikten `fillet`.
- **Verrunden mit Verlauf** (`fillet(law=)`): `SetLaw` setzt den Builder
  zurück, `Add(R1, R2, E)` ist nicht linear — eine Tabelle je Kante.
- **Eine Rundung wegnehmen heißt, ihre Fläche zu streichen** (`unround`,
  `BRepAlgoAPI_Defeaturing`). `reround` belegt die Kante über die Historie
  (`_sharp_edge_after`, zwei Wände quer zur Achse, `UPRIGHT_TO_AXIS`), nie über
  die alte Mitte, sonst `edges.NOT_BETWEEN_TWO_PLANES`. Ohne Auswahl sucht
  `_cylinder_at` über den Radius (`is_close`) und den Abstand zur
  **begrenzten** Fläche, nie über die Achse; unbestimmbar heißt Abbruch.
  Beim kantengestützten Radiuswechsel liefert `reround_with_created_triangles`
  die Fläche aus `BRepFilletAPI_MakeFillet.Generated(sharp_edge)` über
  `_copied_faces` als Ausgabedreiecke; `prepare_ops._exact_fillet` führt den
  Namen nur bei genau einem Feature-Treffer fort. Der Flächenschwerpunkt darf
  bei einer großen Radiusänderung nicht als Identitätsbeleg dienen. Der radiale
  Weg verfolgt den eindeutigen Zylinder mit Sollradius und gleicher Achse auf
  der versetzten Haut und ordnet ihn über `Modified`/`Generated` der
  Booleschen Operation den Ausgabedreiecken zu; ohne eindeutigen Flächenbeleg
  gibt es keine explizite Fortführung.
- **Radiale Wände** (`radial=True`): `radial_rounding` auf privater Kopie,
  `validate_radial_change`, `OrientClosedSolid` vor der Übernahme;
  Veröffentlichtes wird nie umorientiert oder über einen Betrag berichtigt.
  Innen und außen sagen Orientierung und Händigkeit, nie die Achse.
- **`push_faces` nimmt einen Ort**: Die Richtung ist Vorfilter, die Stelle
  entscheidet.
- **Formschräge** (`draft_faces`): gewählte oder alle ebenen Flächen in
  Entformungsrichtung plus `_tangent_chain`; ungültig heißt
  `faces.DRAFT_CUTS_THROUGH`, nie `ShapeFix_Shape`, neben liegender Rundung
  `DRAFT_BESIDE_A_ROUND`, neben stehender freier Fläche `DRAFT_BESIDE_A_FREE_FACE`
  (beide aus `_tangent_chain`). `outward_normal` gilt für
  Fase (`_faces_at_edge`) und Kette.

### Ein Loch lässt sich hier auch wieder schließen

- **`fill_bore`/`cut_bore`** über `_centred_bore`; nur Füllen bekommt `gain`
  auf den Radius, die Länge bleibt exakt. `unified` legt Nähte mit
  Filamentgrenzen zusammen. Verliert die Vereinigung des Stopfens Material
  (am Zwilling, über dem Sehnenfehler der Stopfenflächen), sagt `fill_bore` ab
  (`FILL_DID_NOT_HOLD`).
- **`solid_from_faces`**: **Geschlossen heißt keine freie Kante** — `Closed()`
  setzt Sewing nicht. Ein Ring außerhalb einer Ebene gibt keinen Körper, außer
  mit `fan_caps`: die fortgesetzte Fläche (`_continued_cap`), zuletzt der
  Fächer (`_fan_cap`); als Werkzeug mit Kragen (`collared`).
- **`cone_extent`**/`_oriented_cone` bauen den Kegelstumpf an freier Achse;
  `convex_hull` näht die Hülle des Netzzwillings, `faceted` ein geschlossenes
  Netz aus Facetten (um eine Rundung gebogene Schrift, RM-184), `void_body`
  die Luft ganz gewählter Schalen. **Wulst**: `torus` als Werkzeug, `defeatured` als Rückweg
  auf einer Kopie mit Historie (§21.2), `None`, wo es nicht geht; ein Gewinde
  nicht (`_remove_thread`).

### Bahn und Übergang

- **`sweep_path`**: `MakePipeShell` mit `RightCorner`, nie `MakePipe` (hört an
  einer Ecke still auf), dann `MakeSolid()`; Innenkonturen einzeln abgezogen;
  Anfangstangente senkrecht zum Querschnitt, sonst Absage.
- **Gültig heißt nicht selbstschnittfrei** (`intersects_itself` je Bahn und
  Übergangswerkzeug), **`IsDone` nicht gültig** (`is_sound`; die Schnitte mit
  Werkzeug rechnen dann am Netz, `sketch.exact_cut_unsound`).
- **`loft(..., compatible=False)`** nur, wer die Ecken selbst zugeordnet hat.

### Eine STEP-Datei ist eine Baugruppe

- **`read_assembly`** (XCAF): je Instanz ein Körper mit Weltlage, Name,
  Flächenfarben, `StepBody.key` („1.3.2", mehrere Körper „1.3#2"); keine
  lebenden Instanzen. Name und Farbe (Instanz → Referenz → Form, sRGB) sagt ihr
  Docstring (`usable_name`). `read` bleibt für alte Schritte und den Rückfall.
  Starr bleibt `TopLoc_Location`, Spiegelung wird eingerechnet; Grenzen je Teil
  einmal (`StepBody.box`); **ein XCAF-Dokument zur Zeit** (`_XCAF`).
- **Fallen der Bindung**: `label.FindAttribute(guid, TDataStd_Name())` stürzt
  nativ ab (`_name_of` über `TDF_AttributeIterator`; `SetSHUO` mit
  `XCAFDoc_GraphNode()` gibt ein leeres Label); `read.stepcaf.subshapes.name`
  gibt es erst nach `STEPCAFControl_Controller.Init` (`_prepare_translator`);
  UTF-8 braucht `TCollection_ExtendedString(text, True)`.
- **Hinaus** `write_bodies` (Regel in `dateiformat.md`), Wurzellage
  eingerechnet, `escaped`.

### OpenCASCADE 8 in der Bindung

OCP 8 (`pyproject.toml`, `brep`-Extra), auch für `app/core/sketch/profile.py`.
Fehlt es, ist `available()` falsch und `BRepUnavailable` ein Satz mit Weg nach
vorn — kein Absturz; jeder Code hier prüft das zuerst. Sammlungstypen in
`OCP.collections`; `TopoDS.Face(shape)` statt `Face_s`; `Bnd_Box` über
`box_limits`; `OCP.TColgp` und `OCP.GCE2d` sind leer und scheitern erst am
Namen —
`tests/test_brep.py::test_every_opencascade_import_in_the_application_resolves`.
Trimmkurvenknoten aus `LKnots` (`GetTKnots` lässt sie an analytischen Trägern
aus); `ShapeUpgrade_SplitSurface` teilt Extrusionen und Drehflächen nicht in
Kurvenrichtung (`_trimmed_grid`); `ShapeFix_ComposeShell` braucht einen
`ShapeBuild_ReShape`-Kontext; `VolumePropertiesGK` lässt innere V-Knotenspannen
aus.

### Masseeigenschaften

Nativ auf dem knotenzerlegten Verbund (Leiter 1/2/4, Einigung auf
`INTEGRAL_RELATIVE_ERROR`), Python-Randintegral als Rückfall, beim Volumen nur
für wandernde Flächen (`_mixed_volume`). Teilflächen ohne
`BuildCurves3d`/`SameParameter`, das Kegelvolumen mit festem Bezugspunkt
(`BRepGProp_Vinert` je Fläche). Offsets integrieren die Originalfläche über den
Knoten ihrer Basis; alle Beiträge teilen einen Ursprung. Jeder Weg prüft Fehler
und endliche Maße, Gescheitertes wird nicht gecacht, Form und Triangulation
bleiben; Volumenträgheit gilt als nicht berechnet. `CancelToken` und
`ctx.cancelled` reisen bis in jeden Quadraturpunkt, werden nie gespeichert,
gelten auch am Cachetreffer; `OperationCancelled` bleibt erhalten.
