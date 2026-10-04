# Begründungen zu `app/core/brep/CLAUDE.md`

> Stand 27.09.2026. Aus der Karte verschoben, als sie auf Module, Einstiege
> und die einzuhaltenden Verträge verdichtet wurde. Die Karte steht dort;
> hier stehen die ausführlichen Beschreibungen, Messwerte und Anlässe ihres
> Tages — wörtlich, gegliedert nach den Überschriften der Karte. Die Absätze
> stammen aus der letzten gesicherten Fassung vor der Verdichtung (`main`);
> „Früher unter …“ nennt den Abschnitt, in dem ein Absatz dort stand.
>
> In der Karte zusammengelegt: „Vom Netz zum exakten Körper“ steht jetzt unter
> „Die Einbahnstraße — und die Umwandlung daneben“, „Optional heißt: er meldet
> sich ab“ unter „OpenCASCADE 8 in der Bindung“, „Was er einbringt“ im Kopf.
> Die Abschnitte über Gewinde, Kanten und Rundungen haben neue Überschriften;
> ihre früheren stehen jeweils darunter. „Grenzen“ steht im Kopf und in der
> Tabellenzeile von `edit.py`. Die Abschnitte ab „Eigentum an der nativen
> Form“ stehen in der Karte unter „Stolperfallen“.

## Vorspann

Boundary Representation über OpenCASCADE, **neben** dem Mesh-Kern, nicht an
seiner Stelle (§30).

*Früher unter „Was er einbringt“.*

Was ein Netz nicht geben kann: echte Kanten — und damit Fasen und
Verrundungen, die rund sind statt facettiert, präzise Boolesche Operationen
ohne Tessellations-Artefakte, und STEP hinein wie hinaus.

*Früher unter „Grenzen“.*

- **Kein zweiter Wahrheitsbegriff.** Weicht B-Rep vom Mesh-Kern ab, ist das
  ein Befund, kein „beide haben recht".

## Die Karte

| Datei | Rolle |
|---|---|
| `kernel.py` | Der `Solid` und sein Weg ins Netz. `available()`, `BRepUnavailable`. `boolean_builder` ist der eine Weg zu einer Booleschen: schützt beide Eingänge (`SetNonDestructive`) und rechnet auf allen Kernen (`SetRunParallel`, Ergebnis bitgleich zum seriellen). Je Körper gemerkt: Volumen, Fläche, Hüllquader, Geschlossenheit (`is_closed`: eine Schale und keine freie Kante), Flächennachbarn (`face_neighbours`); eine reine Verschiebung reicht den Hüllquader weiter. `listed` liest eine OCCT-Liste ohne ihre langsame Iteration; `nearest_distance` ist die eine Abstandsfrage, große Fragen auf allen Kernen (`PARALLEL_DISTANCE_PAIRS`) |
| `profiles.py` | Vom Skizzenumriss zum exakten Körper (§30.1) — das größte Modul hier; `helical_thread` näht Kern und Gang eines Gewindes ohne Boolesche Operation; `face_of`, `offset_face`, `face_boolean`, `face_rotated` und `prism` sind die exakte Seite der Querschnitte, aus denen Profilklemmen und Dichtnuten bauen (`knowledge/parts/section.py`); `shrunk_faces` versetzt eine Fläche nach innen und darf dabei zerfallen (Deckelkragen), `upward` richtet eine ebene Fläche nach oben; `round_cord` zieht die runde Dichtschnur als Rohrsweep mit runden Ecken am exakten Weg entlang; `shell_open_at` höhlt mit gewählten offenen Flächen aus, nach innen oder außen (`MakeThickSolidByJoin`, P6.3) und gibt `None` statt eines Körpers zurück, der nicht gültig, geschlossen und verändert ist — OpenCASCADE scheitert dort ohne Ausnahme; `top_faces_of` nennt die Flächen, die *Oben öffnen* meint |
| `ops.py` | Die B-Rep-Operationen im Register (§25, §10) — **ohne** Verrunden und Fase, die stehen in `geom/edge_ops.py`. `mesh_to_exact` (P4.0, Kategorie `mesh`) ist die Umwandlung vom Netz; `brep_to_mesh` die Gegenrichtung. Seit P2.8 die fünf exakten Grundkörper (`create_brep_box` mit `anchor`, `_cylinder`, `_cone`, `_sphere`, `_torus` — sichtbar, wo der Kern da ist; `edit.sphere` und `edit.cone` daneben zu `box`, `cylinder`, `torus`); `drill_brep_hole` und `shell_exact` bleiben registriert und versteckt, weil `prepare_ops.drill_hole` und `hollow_object` sie am exakten Körper selbst rufen |
| `edit.py` | Einen Körper formen |
| `features.py` | Merkmale aus der Topologie (§30, §21); „durchgehend?" fragt eine Bohrung erst nach dem Gewinde (`_ThroughQuestion`), damit dessen Fußstreifen nicht mitgefragt werden |
| `thread.py` | Gewinde an importierter Geometrie: Kantenzüge nach Bogenlänge, Achse eingepasst (Zylinder oder Kegel, analytische Jacobi-Matrix), Vorschub und Händigkeit aus der Wendelregression, Gangzahl aus der Periodizität (§21.1, P2.5) |
| `canonical.py` | Geprüfte Ebenen-, Zylinder-, Kegel-, Kugel- und Ringträger mit wirklichen Flächengrenzen (§30, §21). Ein Kandidat des Erkenners ist nie der Beweis: Belegt wird über alle rationalen Bézier-Koeffizienten; der Kegel (`ConeSurface`, `_cone_matches`) auch bis in die Spitze (`_apart_from_the_apex` halbiert dorthin); versagt der Erkenner an einer großen gespiegelten Ebene, ist die Ebene durch die Pole der Kandidat (`_pole_plane`). `_axial_limits` misst die Achsspanne für Zylinder und Kegel gleich. `horizontal_area` summiert die ebenen Flächen einer Höhe in einer Richtung — die exakte Seite der gezählten Organizer-Flächen (P2.7) |
| `properties.py` | Volumen und Fläche nativ auf dem knotenzerlegten Verbund mit Leiter, Python-Randintegral als Rückfall je Fläche (§30, §11). Extrusionen und Drehflächen teilt `_trimmed_grid` über getrimmte Sichten — `ShapeUpgrade_SplitSurface` schneidet sie in der Richtung ihrer Kurve nicht. `estimated_volume` ist ein grobes Volumen für Plausibilitätsfragen und wird nie veröffentlicht |
| `section.py` | Der exakte Ebenenschnitt für die Skizzenprojektion (P3.5): Kreise und Bögen als solche, alles andere als Kurve durch Punkte der echten Schnittlinie. `horizontal_regions` gibt den waagerechten Querschnitt als Flächen — Materialstück, gefüllter Umriss, Löcher —, aus denen `geom.lid` den exakten Deckel baut |
| `lettering.py` | Schrift als exakte Flächen (P2.8): die Glyphenpfade als Strecken und Bézier-Kurven, gefüllt nach der Füllregel der Schrift (nonzero), zu Prismen aufgezogen — `label_text` nimmt sie für einen exakten Körper |
| `step.py` | STEP hinein und hinaus: `read_assembly` löst eine Baugruppe über XCAF in Körper mit Weltlage, Namen und Flächenfarben auf, `write_bodies` schreibt Körper mit Namen und Farben; `read`/`write` für einen Körper; eine dichte Schale ohne Körper (Flächenmodell) wird beim Einlesen zum Körper, eine offene meldet `load_step` |
| `from_mesh.py` | Vom Dreiecksnetz zum exakten Körper ohne Verlauf (P4.0): Bereiche, Ränder, Ecken, Kanten, Flächen, Nähen, beidseitige Messung — siehe „Vom Netz zum exakten Körper" |

*Früher unter „Grenzen“.*

- **Verrunden und Fasen wohnen nicht mehr hier** (10.09.2026). Die zwei
  Operationen stehen in `geom/edge_ops.py` und nehmen beide Körperarten an;
  was dieser Kern beisteuert, ist `edit.fillet`/`edit.chamfer` — die exakte
  Hälfte, gerufen über eine Verzweigung nach `SceneObject.kind`. Der Grund
  für den Umzug ist die Karte selbst: Eine Operation, die auch Netze rechnet,
  ist keine B-Rep-Operation.

## Die Einbahnstraße — und die Umwandlung daneben

```
B-Rep  ──────>  Mesh      jederzeit (brep_to_mesh, jede Netzoperation)
B-Rep  <──╳───  Mesh      kein Rückweg: die alten Kanten sind verloren
B-Rep  <·······  Mesh      Umwandlung (mesh_to_exact, P4.0): erkannt, nicht zurückgerechnet
```

**Ein Rückweg existiert nicht.** Ein Netz hat die Kanten verloren, aus denen
es gebaut wurde; das Gegenteil zu behaupten ergäbe einen Körper, dessen
„exakte" Verrundung ein Vieleck ist. **Die Umwandlung ist etwas anderes**: Sie
nimmt die Flächen, die die Erkennung im Netz findet, und baut daraus einen
neuen Körper — ohne Konstruktionsverlauf, mit gemessener Abweichung, und was
auf keiner erkannten Fläche liegt, bleibt Dreieck. Siehe den nächsten
Abschnitt.

*Früher unter „Eigentum an der nativen Form“.*

`ops.converted_finding` meldet jede absichtliche Vernetzung eines exakten
Körpers, auch beim Wulst. Weitere Netzbearbeitung bleibt möglich; verloren
geht die exakte Geometrie, und Rückgängig stellt sie wieder her.

*Früher unter „Vom Netz zum exakten Körper (P4.0)“.*

`from_mesh.convert` in sieben Stufen; `ops.mesh_to_exact` macht daraus die
Operation mit Absagen und Befunden.

| Stufe | Funktion | Was sie hält |
|---|---|---|
| Bereiche | `surface_regions`, `regularized` | Träger aus den `SurfacePatch` der Erkennung, keine eigene Einpassung; ein Dreieck nur, wenn alle Ecken in der Toleranz liegen **und** seine Normale höchstens `FACET_TILT` kippt; Ebenen mit der Genauigkeit einer `float32`-Ebene (`PLANAR_SPAN`); danach Achsen, Radien und Berührungen abgeglichen, jede Änderung gegen die Toleranz geprüft |
| Ränder | `boundaries` | Halbkanten zu Ketten zwischen Ecken; geschlossene Ketten mit fester Anfangsecke |
| Ecken | `_vertex_positions`, `snapped` | Gauß-Newton mit rangaufdeckender Pseudoinversen (`SNAP_RCOND`); nie weiter als `CORNER_REACH` mal die Toleranz, sonst die Ebenen allein, sonst bleibt die Ecke |
| Kanten | `_plan`, `structural_curve`, `intersection_curve` | zuerst aus der Gestalt der Träger (Kreis, Gerade), dann `GeomAPI_IntSS` (Kegelschnitte exakt), zuletzt B-Spline durch Punkte; zwei Durchgänge, dazwischen die Ecken auf ihre Kurven (`_on_curves`, Gauß-Newton) |
| Flächen | `_checked_face` | je Bereich eine Fläche mit **eigenen** Kanten (`Inside=False`, `ShapeFix_Face`, `SameParameter`), geprüft gegen Fläche und Probe des Bereichs |
| Körper | `_shells`, `_assembled`, `_broken_after_sewing` | genäht je Netzkomponente; ist der Körper ungültig, werden die Flächen einzeln geprüft und ihre Bereiche als Dreiecke neu gebaut (`_demoted`) |
| Messung | `_mesh_to_body`, `body_to_mesh`, `source_deviation` | beidseitig an Stichproben auf den **exakten** Flächen; innere Wände (nicht verschmolzene Nähte) zählen eigens |

Der Körper trägt das Netz, aus dem er stammt (`Solid.converted_from`, nur im
Speicher, nur am unveränderten Ergebnis); die Karte „Formabweichung" misst
damit gegen das Netz statt gegen seine eigene Darstellung
(`geom.deviation.HasSourceDeviation`). Die Regeln dazu stehen in den
Docstrings der Konstanten `CORNER_REACH`, `SNAP_RCOND`, `PLANAR_SPAN`,
`FACET_TILT`, `MAX_FREEFORM_FACES` — jede mit dem Modell, an dem sie gemessen
wurde.

## Eigentum an der nativen Form

`Solid` übernimmt beim Eintritt eine eigene Kopie von Topologie und Geometrie
ohne fremde Triangulation (`BRepBuilderAPI_Copy`, `copyGeom=True`,
`copyMesh=False`). Seine veröffentlichte `shape` sowie die Flächen-/Kanten-
Handles werden intern nur gelesen. Ein `frozen`-Dataclass allein schützt
keinen OCCT-Handle gegen native Mutationen.

Auch der STEP-Transfer arbeitet mit `copy_shape` auf einer privaten Form.
Der native Schreiber kann Prüfkennzeichen gültiger Rundflächen verändern;
ein Export lässt deshalb sämtliche ursprünglichen Shape-Kennzeichen erhalten.

Tessellation arbeitet auf einer weiteren privaten Arbeitsform. Sie schreibt
nie an die Shape eines Szene- oder Cache-Eintrags. Die Dreieckzuordnung läuft
über `ModifiedShape(original_face)` der Kopie und die ursprüngliche
Flächenkarte, nicht über eine angenommene gleiche Besuchsreihenfolge.
`brep_to_mesh` ruft diesen Weg direkt auf; ein zusätzlicher Qualitäts-Solid
wäre vor der Mesherkopie redundant.

Boolesche Operationen werden durch `kernel.boolean_builder` leer angelegt:
NonDestructive und gegebenenfalls Fuzzy-Toleranz stehen **vor** dem ersten
Build. Der Zwei-Shape-Konstruktor rechnet bereits und wird nicht benutzt.
Fillet, Chamfer, Defeaturing, Shell, Draft, ShapeFix und Press/Pull erhalten private
Eingabeformen einschließlich der daraus gewählten Flächen/Kanten. Ein neuer
Ergebnis-Solid trennt anschließend auch die vom Builder geteilten Unterformen.
`unround` wählt die Rundungsfläche bereits auf seiner Arbeitskopie. So bleibt
auch beim darauf aufbauenden `reround` die ursprüngliche NURBS-Geometrie
einschließlich Polgrad, Knoten und Randkurven unverändert.

Exakte Bounds bleiben eine Float64-Antwort aus `AddOptimal` ohne Triangulation
und Formtoleranz; Zeichenwege sollen dafür keinen nativen Aufruf je Frame
auslösen. Ein Bounds-Cache ersetzt keinen Eigentumsvertrag.

`edit.transformed_with_faces` erhält exakte Geometrie auch bei Maßstab,
Spiegelung und Scherung. Ähnlichkeiten verwenden `gp_Trsf`, allgemeine affine
Matrizen `gp_GTrsf`: `gp_Trsf.SetValues` orthogonalisiert sonst die Eingabe.
Die Matrix muss endlich, affin und numerisch umkehrbar sein. Körperzahl,
Geschlossenheit und native Gültigkeit müssen nach dem Schritt weiter stimmen.
**Eine starre Bewegung beweist sich über die Partnerschaft der Formen**
(`IsPartner`: dieselbe Topologie und Geometrie, anders gelegt — mehr tut der
Builder dort nicht), nicht über ein Integral: Zwei Volumenintegrale je
Verschieben kosteten an einem STEP-Gewinde 27 s (Review 21.09.2026). Maßstab,
Spiegelung und die allgemeine affine Abbildung bauen die Flächen neu — eine
Lage trägt keinen Maßstab —, und dort belegt das mit der Determinante skalierte
Volumen weiterhin, dass nichts verloren ging. Eine Identität baut nichts neu.

Die Flächenzuordnung verkettet `ModifiedShape` des Transformationsbuilders mit
der tatsächlichen Kopie des Ergebnis-Solids. `Solid._copied_faces` hält dafür
ein unveränderliches Indextupel außerhalb des Caches; eine neue Qualität startet
weiter mit kaltem Cache. **Kanten gehen denselben Weg**: `copy_shape` liefert
neben der Flächen- auch die Kantenabbildung aus demselben `ModifiedShape`
(`Solid._copied_edges`, Indexraum `edges()`), bijektiv geprüft — eine
Kopierprimitive, kein zweiter Kopierweg und keine angenommene
Besuchsreihenfolge; der Test mit rückwärts eingehängten Teilkörpern deckt beide.
`faces_of_triangles` ist die geprüfte inverse Zuordnung
zu `triangles_of_face` und weist negative oder fremde Dreiecksindices zurück.
Weder Besuchsreihenfolge noch alte Dreiecksindices ersetzen diese Zuordnung.
Die Kantenabbildung entsteht mit der Flächenabbildung in derselben Kopie —
gemessen 0,1 ms je Körper; sie träge zu bauen hieße, den Kopierbuilder und
damit die Quellform am Ergebnis festzuhalten.

**Was ein Körper über seine Flächen weiß, weiß er einmal.** `Solid.surface(i)`
ist der geprüfte Träger der Fläche `i` (`canonical.describe`),
`Solid.face_properties(i)` ihre Fläche und Mitte, `Solid.face_index(face)`
die Nummer eines nackten Handles aus einer Nachbarkarte — alle drei Memos im
`_cache` des Körpers. Erkennung, Nahtzusammenführung, Langloch, Flächenauswahl
und Versetzen fragen dort, statt dieselbe Fläche je Frage neu zu beschreiben
und zu integrieren: `features_of` an `m6_nurbs.step` fiel von 19,6 s auf
0,9 s (Review 21.09.2026). Eine Kopie beginnt kalt, sie hat andere Flächen;
und ein Memo am Eingang ist keine Änderung an ihm — es hält, was `volume`
und `faces()` seit je halten.

`profiles.push_faces` und `edit.unround` nehmen mit `selected_faces` eine
ausdrückliche Auswahl vollständiger aktueller nativer Flächen an. Der
Operationsaufrufer belegt die vollständige Dreiecksabdeckung am tatsächlichen
Eingabekörper; `Solid.checked_face_indices` prüft die nichtleere Indexmenge,
ohne dessen Cache zu füllen. Die private Arbeitskopie übernimmt die Auswahl
über ihre wirkliche `_copied_faces`-Abbildung. Beim Versetzen zählt die eigene
Normale jeder gewählten Ebene. Beim Entfernen ist genau eine Zylinderfläche
mit dem bisherigen Radius zulässig. Leere oder unpassende Auswahlen lösen
keine Ersatzsuche aus; nur `None` benutzt den bisherigen Lage-/Richtungsweg.
Abbruch wird bei der Auswahl, vor und nach den nativen Builds sowie nach
der letzten Ergebniskopie geprüft;
Eingabeform und Eingabecache bleiben auch dann erhalten. Der anschließende
Radiuswechsel über `reround` nimmt dieselbe `selected_faces`-Auswahl an und
belegt beide Übergänge selbst: `_unround` gibt neben dem Körper den Index der
scharfen Ersatzkante zurück, den `_sharp_edge_after` aus der Historie des
Defeaturing-Builders liest — `Modified(Wand)` der zwei ebenen Wände quer zur
Rundungsachse (`units.UPRIGHT_TO_AXIS`) teilen sich im Ergebnis genau eine
Kante, und die ist es. Deckel und Boden gehören nicht dazu, über alle vier
Nachbarn ist der Schnitt leer; die nächste Kante zur alten Mitte traf dort
zufällig dieselbe und ist kein Beleg. Ohne genau zwei Wände — eine Rundung
zwischen Deckel und Zylindermantel — sagt `reround` mit
`edges.NOT_BETWEEN_TWO_PLANES` ab, demselben Satz wie am Netz, statt eine
Kante zu raten. Ohne ausdrückliche Auswahl bleibt die Suche über Lage und
Radius bestehen.

Filamentzuweisungen liegen unveränderlich in `Solid.face_slots`, je nativer
Fläche. Jede private Kopie führt sie über `_copied_faces` nach; jede neue
Tessellation bildet daraus die Slots ihrer tatsächlich erzeugten Dreiecke.
`with_triangle_slots` übernimmt nur widerspruchsfreie ganze Flächen. Bei
reinen Attributänderungen bleiben die vorhandenen Merkmalsdreiecke in ihrer
Reihenfolge erhalten; deren native Flächenkarte wird auf die private Kopie
umgeschrieben. Ein Qualitätswechsel beginnt weiterhin mit kaltem Cache.
Auch `to_mesh(deflection=...)` und die bewusste Operation `brep_to_mesh`
verwenden diese Attributzuordnung.

`carried_face_slots` führt Attribute durch Folgeoperationen allein anhand
nativer Identität und belegter Builder-Ersetzungen nach. Transformationen
reichen `ModifiedShape`, ShapeFix seine `ShapeBuild_ReShape`-Ersetzung weiter.
Bei mehreren Eingängen gilt die erste passende Quelle mit Attributen;
Abzugswerkzeuge sind keine Farbquelle. Neue Flächen erhalten Slot null.
`keep_filament_boundaries` bewahrt beim Vereinigen gleichartiger Flächen die
Kanten zwischen verschiedenen Slots. Widersprüchliche Nachfahren werden
abgewiesen, niemals über Mehrheit oder Besuchsreihenfolge aufgelöst.
Projektdateien speichern weiterhin Quellen und Filamentoperationen; die
native Zuordnung wird beim Öffnen aus demselben Verlauf neu aufgebaut.

Die Wandschranke vor Fillet und Chamfer prüft die echten Trägerflächen der
gewählten Kanten. `triangles_of_face` ordnet ihnen die Werte der Wandkarte zu;
eine nur am Endpunkt berührende Stirnfläche begrenzt keine quer dazu laufende
Rundung. Jede Trägerfläche braucht eine belegte Probe; fehlt sie am Rasterrand,
misst `geom.measure.wall_thickness` dieselben Dreiecksschwerpunkte per Strahl.
So bleibt der Schutz vor einem nativen Absturz an dünnen Wänden bestehen,
ohne eine entfernte Grundplatte zum Radiuslimit aller Kanten zu machen.

## Merkmale aus der Topologie

*Früher unter „Eigentum an der nativen Form“.*

`canonical.describe` ist die gemeinsame Trägerauskunft für Erkennung,
Nachbarschaft, Langloch und die Flächenauswahl in `edit`/`profiles`. Eine
`PlaneSurface` trägt die Normale der ursprünglichen Fläche; eine
`CylinderSurface` trägt echte axiale Längen, Winkelabdeckung und Materialseite.
NURBS-Parameter werden nie als Winkel oder Länge ausgegeben. Die gerichtete
Innenprobe liegt innerhalb der wirklichen Trimmkontur, auch bei Innenlöchern.

`canonical.surface_sample` liefert diese orientierte Innenprobe auch für
Kugelabschnitte. Ihre Materialseite folgt Hautnormale und Kugelradiale,
nicht der Lage des Kugelzentrums im gesamten Körper. Das Zentrum eines
Kugelmerkmals ist der Trägerursprung; der Flächenschwerpunkt bleibt die
Auswahlmitte kugeliger Eckverrundungen. Native Radien werden erst angezeigt
gerundet, nie bei ihrer Veröffentlichung.

`SphereSurface` prüft auch rationale Kugelträger. Der Kandidat entsteht auf
einer privaten, lokal verschobenen Fläche. Die homogene Kugelgleichung über
allen Bézier-Koeffizienten belegt ihn innerhalb von `EPS_GEOM`; Status und
Abstand des Recognizers allein reichen nicht. Materialseite und Auswahl
stammen weiter aus der ursprünglichen getrimmten Fläche. Offset-Kugeln ohne
vollständigen zusätzlichen Normalennachweis bleiben unklassifiziert.

`TorusSurface` liest native Ringe und prüft rationale Ringträger. Der Kandidat
kommt aus derselben `fit_torus_samples`-Rechnung wie am Netz, hier mit echten
Flächenpunkten und Ableitungen. Erst die homogene Torusgleichung über sämtlichen
Bézier-Koeffizienten begrenzt die Abweichung auf `EPS_GEOM`; eine gute Stichprobe
allein genügt nicht. Zerlegung, periodische Trimmungen, Polprüfung und
Arbeitsgrenzen teilen Ebene, Zylinder, Kugel und Ring. Offset-Ringe ohne diesen
vollständigen Nachweis bleiben unklassifiziert.

Kanonische Kandidaten verwenden ausschließlich `EPS_GEOM` als numerische
Geometriegrenze. Jeder Versuch bekommt einen frischen OCCT-Recognizer;
Status und endliches `GetGap` werden geprüft. Zusätzlich werden alle
rationalen Bézier-Knotenspannen gegen Ebene beziehungsweise Kreiszylinder
begrenzt geprüft. Ein örtlicher Ausschlag zwischen Punktproben kann so nicht
durch einen günstigen gemeldeten Gap verschwinden. Das ist weder ein globaler
Hausdorff-Nachweis noch eine Fertigungsunsicherheit. Ungeklärte Träger bleiben
unklassifiziert; Erkennung ersetzt niemals die gespeicherte Form.

Periodische U- und V-Trimmungen werden an ihrer Naht in Intervalle der
Trägerperiode geteilt. Eine gültige Trimmung außerhalb des nominellen
Parameterintervalls wird weder abgeschnitten noch verworfen. Die zusätzliche
Bézier-Prüfung arbeitet auch dort ausschließlich mit privaten Kopien.

Offset-Flächen verwenden denselben Kandidatenweg für ihre private Basis.
Die natürliche Parameternormale bestimmt die signierte Verschiebung; die
Orientierung der ursprünglichen Fläche bestimmt weiterhin die Materialseite.
Neben der Lage wird der Normalenfehler aus rationalen Bézier-Ableitungen
begrenzt: Lagefehler plus Offsetbetrag mal Normalenfehler bleibt innerhalb
von `EPS_GEOM`. GetGap am Offset allein reicht nicht. Die zusätzlichen
Koeffizientenprodukte teilen Abbruch und Arbeitsgrenze der Basisprüfung.
OCCT fasst konstruktiv geschachtelte Offsets zusammen; verbleibende
Offset-Basen bleiben ohne rekursive Suche unklassifiziert.
`kernel.untrimmed_surface` ist die gemeinsame lesende Auskunft unter
rechteckigen Trägerhüllen. Sie erhält die Geometrie und begrenzt die Hülltiefe;
die tatsächlichen UV-Grenzen stammen immer vom ursprünglichen Face/Adaptor.

Die NURBS-Hülle von `AddOptimal` enthält auch ohne Formtoleranz einen internen
Zuschlag. Für axiale Endlagen werden deshalb tatsächliche Abstände der
begrenzten Fläche zu äußeren Messebenen verwendet. Winkel kommen aus den
projizierten ursprünglichen Randkurven, einschließlich Nahtübergängen.
Alle Hilfsformen bleiben privat. `ctx.cancelled` reicht von jedem
Operationsaufrufer durch `features_of`, Trägerprüfung und Nachbarwege bis zu
den Python-Koeffizientenschleifen und der gemeinsamen Maßintegration;
`OperationCancelled` bleibt dabei unverändert erhalten.

`Feature.measure_sources` begleitet jedes tatsächlich gelesene native Maß.
Vollständige native Restflächen ersetzen nur ihre Fläche und Mitte durch
native Integrale; Teilflächen erhalten die ausdrücklich gekennzeichneten
Messquellen des Netzwegs. Ein offenes Langloch kommt über den Netzweg und
bekommt danach, was seine endgültigen nativen Träger belegen
(`perceive.slots.native_open_slot_measures`, P1.5): Durchmesser, Achse und
Bogenmitte aus dem nativen Zylinder, die Richtung aus den nativen Flanken;
Mündung, Weg und Länge bleiben `fit`. Körperart und `provenance` sind
dafür keine Ersatzangaben.

`features_of` erhält die einmal gelesenen analytischen Träger als
`SurfacePatch` mit ihren tatsächlichen Tessellierungsdreiecken. Nach der
semantischen Zusammenfassung bekommen Langloch, Ring und Luftkammer jeweils
nur ihre ausgewählten Teilflächen. Native Belege ersetzen dort überlappende
Netzfits; unbekannte Reststücke erhalten keinen erfundenen Träger.
Kugelzentrum und Zylinderachse kommen aus der Originalfläche, auch wenn das
Merkmal zur Auswahl einen anderen Flächenschwerpunkt trägt. Kegel erhalten
die native Spitze und die gerichtete Nappe mit dem Halbwinkel im Bogenmaß.
Die Nappe und der weite Rand folgen gemeinsam den signierten Radien an den
tatsächlichen V-Trimmgrenzen. Jenseits der Spitze kehrt sich die Richtung um;
der veröffentlichte Durchmesser bleibt positiv. Eine Trimmung über beide
Nappen erhält weder ein eindeutiges Kegelmerkmal noch einen gerichteten
Kegelträger. Sie bleibt über die vorhandene Restflächenerkennung auswählbar,
ohne die native Form zu teilen oder einen neuen Träger einzupassen.
Ein gerundeter Spitzenparameter darf nur innerhalb seiner arithmetischen
Endpunktklammer auf null zurückgeführt werden, wenn der ursprüngliche
degenerierte Rand tatsächlich den Spitzenknoten trägt. Ein kleiner echter
Übertritt bleibt auch unterhalb von `EPS_GEOM` eine uneindeutige Doppelnappe.

Native Ringstücke mit gleichen Achsen, Mitten, Radien und Materialseiten
bilden ein Merkmal, auch wenn ein Durchbruch sie trennt (RM-226 Nachtrag
04.10.2026). Bis dahin verband der exakte Kern nur angrenzende Stücke, das Netz
legte Ringflecken schon nach ihrer Mitte zusammen (`_merged_tori`): An
`pegboard-gs-100-v2` teilen zwei Durchbrüche die Kehle am Grund der Mulde in
zwei Bögen; die 3MF des Herstellers trug einen Ring über beide (589 Dreiecke),
der exakte Kern zwei (241 und 246). Angeglichen wurde der exakte Kern, weil ein
Ring sein Träger ist: Wulst und Kehle bauen für Versetzen, Verdoppeln und
Drehen den vollen Ring aus Achse, Mitte und Radien, nicht aus den gewählten
Flächen. Die Gegenrichtung — auch am Netz nur Anstoßendes verbinden — wurde
gemessen und verworfen: Im Erkennungszensus über `F:\3D Dateien` teilte sie an
acht Netzen ganze Ringe in zwei oder vier Stücke (`parametric-laptop-riser`,
ein Teil des Mini-Golf-Satzes, je zwei Teile von `elegoo_grease_tool` und
`Elegoo_erster_Druck`, beide 3MF von gs-100) und las an drei weiteren Teilen
des Mini-Golf-Satzes Rundflächen als Ringpaare. Freie gerundete Seiten
verwenden `detect_curved_faces` und damit dieselbe Glättungs- und
Innenseitenauskunft wie Netze. Deckt die Auswahl ganze native Flächen ab,
kommen Fläche und Mitte aus ihren exakten Integralen; teilweise ausgewählte
Flächen behalten die tessellierte Messung. Quellen und ihre Trimmkurven werden
dabei nie geändert.

Planare Merkmalsnormalen folgen der Orientierung der B-Rep-Fläche:
`TopAbs_REVERSED` kehrt die Trägerebenennormale um. Damit verwenden
Auswahlrahmen, Taschen und Ziehen dieselbe nach außen gerichtete Normale.

Zylindrische Innenwände und Zapfen unterscheiden sich durch die gemeinsame
Wirkung von Flächenorientierung und Händigkeit (`Cylinder.Position().Direct()`).
Auch ein gültiges Kreisprisma kann einen indirekten Zylinder tragen;
`TopAbs_REVERSED` allein ist deshalb kein Nachweis für eine Bohrung.

`features._describe` beschreibt analytische Kegel über `GeomAbs_Cone`.
Die V-Grenzen bestimmen den wirklich weitesten axialen Umfang; Achse und
Mittelpunkt liegen auf der Kegelachse. Flächenorientierung und
`Cone.Position().Direct()` unterscheiden gemeinsam die Senkung vom massiven
Kegel, auch nach einer Spiegelung. Eine unvollständige U-Spanne markiert `partial`.
Durchmesser und Winkel bleiben Werte des exakten Körpers ohne Anzeigerundung.

`features._void_features` liest geschlossene Luftkammern über Körper- und
Schalenzugehörigkeit. Eine invertierte Außenschale wird nicht zum Innenraum.
Ein Sacklangloch braucht eine wirkliche Mündung nach außen; eine Schnitttiefe
unterhalb der Körperhöhe belegt sie nicht. Ein vollständig innenliegender
Langlochmantel gehört mit seinen beiden Abschlüssen zur Luftkammer.
Die positive Messform entsteht aus einer privaten Innenschalenkopie;
weitere Materialkörper werden davon abgezogen. Materialinseln zählen deshalb
nicht zum Luftvolumen, ihre Oberflächen gehören aber zur vollständigen
Luftgrenze. Kammern in solchen Inseln bleiben eigene Merkmale. Derselbe
Luftraum wird bei mehreren Nachweisen anhand seiner tatsächlichen
Quellflächen nur einmal veröffentlicht.

Die Kopier- und Boolesch-Historie muss jede Ergebnisfläche auf eine
ursprüngliche Fläche zurückführen. Erst danach entstehen über
`triangles_of_face` die auswählbaren Dreiecke. Native Handles oder Builder
werden nicht gespeichert. `void.centre` und `void.size` bleiben Welt-AABB-
Werte, keine Volumenschwerpunkte. Der gemeinsame Nachschritt
`perceive.features.voids_instead_of_phantom_bores` verdrängt primitive
Einzelmerkmale auf derselben Luftgrenze. Verschieben und Entfernen benutzen
weiter ihre vorhandenen, ausdrücklich ausgewiesenen Netzoperationen.

**Ein Langloch ist vier Flächen und ein Merkmal.** `features._slots_instead_of_half_bores`
setzt sie nach dem Beschreiben wieder zusammen — die einzige Ausnahme von „eine
Fläche, ein Merkmal" in dieser Datei, und dieselbe Aussage wie
`perceive.slots` am Netz. Erkannt wird topologisch: zwei angeschnittene
Zylinderflächen mit gleichem Radius und paralleler Achse, beide ins Loch
gewölbt, die sich **genau zwei** ebene Nachbarn teilen — und diese zwei Ebenen
grenzen an **beide** Bögen. Damit ist eine Tasche mit verrundeten Ecken keines:
Zwei benachbarte Ecken teilen eine Wand, nicht zwei. Die Toleranzen und die
Abgrenzung stehen in `.claude/rules/operationen.md`.

**Und seine Mündungsfase gehört dazu** (`_mouth_chamfers_folded`, P1.5,
20.09.2026): Ein Teilkegel, der genau ein Langloch berührt, und die
schrägen Ebenen, die an ihn und an den Mantel desselben Langlochs grenzen,
gehen im Langloch auf — dieselbe Zugehörigkeit wie am Netz
(`perceive.features._partial_cones_folded`), mit erhaltenen Trägern: Kegel
mit Spitze und Halbwinkel, Ebene mit Normale. Die Maße bleiben die Nennmaße
ohne Fase. Ein Kegelstück zwischen zwei Langlöchern bleibt, was es ist.

**Ein Mantel, den die Naht in zwei Flächen teilt, ist ein Merkmal**
(`_seam_split_cylinders_joined`): zwei zylindrische Nachbarflächen mit
derselben Achslinie, demselben Radius und derselben Materialseite werden
vor dem Langlochpass zusammengeführt, und der gemeinsame Umfang entscheidet
wie an einer Fläche. Die Umfangsschwelle ist seither die des Netzes,
`perceive.features.FULL_TURN_SPAN` (300 Grad, gelesen über `_full_turn`); eine Bohrung unter der
vollen Umdrehung trägt `partial`, und was das bedeutet, entscheidet die
Nachbarschaft (`perceive.relations`), nicht der Winkel.

**Unter dem Mindestbogen ist eine Rundform eine Kante** — dieselbe Zahl wie am
Netz (`perceive.features.MIN_ROUND_ARC`, fünf Grad, RM-210). Torus- und
Kegelstücke fragt `_describe` am nativen Umfang (V- bzw. U-Spanne); ein
Zylinderstück erst nach der Nahtzusammenführung (`_short_arcs_dropped`, und
die Nahtgruppe selbst), damit ein schmaler Rest neben einem Mantel dort
mitzählt. Was nicht benannt wird, lesen die Restflächen wie am Netz.

Der Mittelpunkt einer Bohrung oder eines Zapfens liegt **auf der Achse, in
der Mitte der V-Spanne** des Mantels — nicht im Flächenschwerpunkt, der bei
einem schräg beschnittenen Mantel radial und axial daneben liegt und den
Schneidzylinder von `edit.resize_bore` aus der Achse schob. Ob ein Loch
durchgeht (`through`), sagen die Nachbarflächen des Mantels: Reicht eine in
die Mündung — über die Achse (Boden, Bohrerspitze, Kalotte) oder über einen
der zwei Ringe darin, dieselben wie im Netzweg (`THROUGH_RINGS`) —, ist es
ein Sackloch; der Abstand wird gemessen, nicht geschnitten, weil eine
Kegelspitze im Schnitt ein entarteter Punkt ist. Die Ringe kamen am
22.09.2026 dazu: Die Aufweitung Ø 9 einer gesenkten Durchgangsbohrung Ø 5
hat über ihrer Achse nichts und endet doch am Übergangskegel — am Netz hieß
sie Sackloch, hier durchgehend (Kreuzbefund Paket C).

Die exakte Bohrung verwendet das Material des Zielkörpers über einen trägen
`knowledge.profiles.for_object`-Import. Freie Normalen, Aufweitungen und
Übergänge übernehmen das validierte Profil aus `geom.prepare.drill_outline`;
`edit.bore_profile` rotiert es analytisch. Mesh und B-Rep teilen damit Maße
und Mündungsbezug, ohne exakte Kreise zu tessellieren.

`revolved_bore_tool` und `clipped_bore_tool` bauen das gemeinsame Werkzeug
für eine Bohrungsänderung mit Einlauf. Der Schnitt an den tatsächlichen
Randebenen erfolgt über analytische Halbräume; auch schräge Mündungen und
Böden bleiben exakt. Beim vorherigen Schließen wird das alte radiale Profil
verwendet. Ein Zylinder mit dem größten Senkungsradius würde tiefer liegende
Nachbarhohlräume füllen, die nie zum gewählten Einlauf gehörten.

**Ein Langloch wird nicht rotiert, sondern aufgezogen.** Der Umriss aus
`geom.prepare.slot_profile` wird über `profiles.extrude` zum Prisma, und zwar
**vom Boden zur Mündung**: `extrude` verlangt eine positive Höhe, und ein
Rahmen mit umgekehrter Normale wäre linkshändig — derselbe `slot_angle` drehte
darin in die andere Richtung als im Netz-Kern. Dieselbe Ebene, dieselbe Höhe,
nur ein anderer Ursprung. `_bore_span` in `ops.py` beantwortet Rahmen,
Werkzeuglänge und Mündungslage für beide Bauarten; `edit.slot_bore` zieht eine
bereits erkannte Bohrung nachträglich auseinander. Die Enden bleiben in beiden
Fällen echte Zylinderflächen — gemessen trifft der exakte Kern das analytische
Volumen auf die sechste Stelle, wo der Netz-Kern seine Bögen abtastet.

Offene Randbohrungen und Langlöcher ergänzt `features_of` über dieselbe
Wandprüfung wie der Mesh-Kern (§21.1). `edit.slot_bore` vereinigt nach dem
Schnitt koplanare Flanken, damit Nachziehen ohne neue Breitenzugabe das
Merkmal erhält. `edit.fill_bore` schließt den ganzen Langlochumriss und
begrenzt bei einer Randöffnung den Füllkörper an ihrer Außenwand.

Splines aus Skizzen übernehmen die kubischen Kontrollpunkte aus
`sketch.profile.spline_controls`; sie werden nicht neu interpoliert.
Der Draht erhält eine exakte Bézier-Kante je Stück, damit Flächen- und
Volumenintegrale auch an den inneren Kurvenknoten stimmen.

## Gewinde: erzeugt, gelesen, genäht

*Früher im Kopf der Karte.*

`ops.thread_exact` benennt die Händigkeit seiner Wendel mit `handedness="right"`.
Der Nachweis liegt im Erzeuger `profiles.threaded_rod`: Auf der Zylinderfläche
steigen Winkel und Höhe gemeinsam. Die Angabe gehört zum erzeugten Merkmal,
nicht zu einer Vorgabe für erkannte Importformen; Spiegelungen führen sie nach.

`thread_exact` übergibt sein Gewinde an `features_of(known_threads=…)`: Die
Flächen, die es benennt, werden dort weder gelesen noch beschrieben — was
auf ihnen entstünde, verdrängte das Gewinde ohnehin als Phantom.

*Früher unter „Eigentum an der nativen Form“.*

`thread_exact` benennt sein Außengewinde als erzeugtes `thread_1` mit den
unveränderten Werten für Durchmesser, Steigung und bewendelte Länge. Der
Mittelpunkt liegt bei halber Länge, die Achse zeigt in der Vorgabelage
nach +Z. Sie muss es nicht: Der Bolzen erbt seit dem 09.09.2026 dieselben
sieben Lagefelder wie Quader und Zylinder
(`geom.primitive_ops.PositionedPrimitiveParams`), und `placement_transform`
wirkt vor der Merkmalserkennung — das Gewinde wandert also mit. Ohne die
Felder bekäme er als einziger Erzeuger des Menüs *Erzeugen* keinen Griff
an seiner Vorschau. Das Merkmal
trägt die wirklichen Manteldreiecke; planare Anschnitte bleiben getrennte
Flächen. Es verwendet denselben Gewindevertrag wie die Bausteine, ohne die
exakten Operationswerte für die Anzeige zu runden.

*Früher im Kopf der Karte.*

**Und ein Bolzen ohne Gang ist keiner** (P2.5, B3): `threaded_rod` lieferte an
neun von 23 Rasterlängen — jeder halbzahligen Umlaufzahl — den nackten Kern
zurück, gültig, geschlossen, ein Stück, ohne Meldung; `thread_exact` mit Länge
2,5 und Steigung 1 erzeugte einen glatten Bolzen. Seit RM-195 wird der Bolzen
genäht statt vereinigt; `_is_sound_rod(at_least=)` verlangt über dem Kern
mindestens den halben Gang nach Pappus (`_ridge_volume`) und fragt dafür das
grobe Volumen (`properties.estimated_volume`), nie das veröffentlichte. Was
den Gang verliert, gilt nicht als gelungen, und am Ende steht die Absage mit
Vorschlägen. `tests/test_exact_thread_features.py` hält Pappus an vier Längen
auf 10⁻⁸ — auch an denen, die früher den Gang verloren.

*Früher unter „Ein Gewinde wird genäht, nicht vereinigt (P2.7)“.*

`profiles.helical_thread` baut Kern und Gang eines Gewindes als **einen**
Körper, ohne Boolesche Operation dazwischen: Flanken, Kamm und Fußstreifen
sind Regelflächen zwischen je zwei Helices (`BRepFill.Face`), die sich ihre
Kanten teilen; die Enden schließen zwei Rampen von der Achse zur Fußhelix und
je eine ebene Fläche bei Winkel null. Genäht (`BRepBuilderAPI_Sewing`, keine
freie Kante), orientiert (`OrientClosedSolid`), danach auf Länge geschnitten
— mit einem Quader, dessen Boden und Deckel als Ebenen die BSpline-Flächen
treffen: Der Mantel eines Schnittzylinders umhüllte jede Gangfläche, und die
Boolesche prüfte jede gegen ihn (1,4 statt 0,74 s am M3 × 0,5 × 60). Gemessen: 44 Flächen in dreißig Millisekunden, gültig,
Volumen der Analytik (Pappus je Umlauf) auf 5·10⁻¹⁰, STEP-Rundreise auf
10⁻¹⁴. Die Helix ist dabei eine BSpline-Näherung ihrer Linie auf dem
Zylinder, und wie genau, sagt `_HELIX_PRECISION`: Mit OCCTs Vorgabe von
10⁻⁵ mm lagen die Flanken Mikrometer neben der Schraubfläche (Pappus auf
2·10⁻⁷, die Hülle eines M10-Bolzens 3 µm neben der Achse); ein Hundertstel
von `EPS_GEOM` kostet keine messbare Bauzeit. Der Grund fürs Nähen steht im
Docstring: Die Vereinigung von Kern und gesweeptem Gang verschluckt den Gang
still (Bericht P2.7, B1), und die Fuzzy-Stufe, die ihn rettet, ist je Größe
eine andere — an einer Rasterfahrt über sechs Größen und drei Längen fand
sich für zwei Fälle gar keine. **Seit RM-195 (21.09.2026) geht auch
`threaded_rod` — der Erzeuger *Gewindebolzen* — diesen Weg**, mit seinem
ISO-nahen Profil aus `thread_ridge` (Fuß 0,75 p, Tiefe 0,6134 p, Flanken so
steil wie beim Sweep mit seinem Sockel `_THREAD_FOOT_SEAT` unter dem Kern):
M6 × 1, L 12 in 0,3 s statt 15, M10 × 1,5, L 12 in 0,3 s statt 27. Die
Sekunden des Sweep-Wegs steckten nicht in der Vereinigung (0,3 s), sondern
in den Volumenintegralen seiner Prüfstufen, und die Sweep-Flächen (Grad 9,
C⁰ an jedem Knoten) hielten kein Integral auf 10⁻⁹. `_checked_rod` bleibt
die letzte Absage; `_sewn` bleibt als geprüfter Baustein, und
`_fuzzy_boolean` zieht nur noch die gezeichneten Löcher von Durchzug und Bahn
ab — mit dem Satz seines Aufrufers, nie mit einem über ein Gewinde. Wer ein
neues Gewinde baut, nimmt das Nähen: `helical_thread(starts=, taper=)` näht
auch mehrgängige (der Vorschub ist `starts · pitch`, je Gang ein Profil eine
Teilung höher) und kegelige Gewinde (jeder Profilpunkt auf einem Kegel statt
einem Zylinder); `tests/data/make_thread_corpus.py` baut so die
Referenzkörper `dreigaengig`, `innen_zweigaengig` und `konisch`.

*Früher unter „Ein Gewinde wird an den Kanten gelesen, nicht an Dreiecken (P2.5)“.*

`thread.read_thread` misst ein importiertes Gewinde ohne Erzeugerwissen:
Jede Kante, die weder Strecke noch Kreis noch eben ist, wird nach
**Bogenlänge** abgetastet (`GCPnts_UniformAbscissa`) — der Kurvenparameter
einer B-Spline ist kein Winkel und kommt in keiner Rechnung vor. **Grob
entscheiden, fein messen:** Ebenheit und Verkettung sehen `SAMPLES_COARSE`
Punkte je Kante; erst die Züge, die übrig bleiben, bekommen
`SAMPLES_PER_TURN` Punkte je Umlauf, den Umlauf aus dem Radius einer
Einpassung an die groben Punkte. Ein fester Abstand von 0,05 mm tastete
231 Kanten einer verrundeten Lochplatte mit 83 000 Punkten ab, bevor die
Ebenheit alle aussortierte (749 ms für eine Absage, jetzt 97 ms; die
Korpuswerte bis 10⁻⁴ an der Steigung dieselben). Kanten,
die einen Vertex teilen und dort tangential anschließen, werden ein Zug;
über bloße Nachbarschaft wurden Kamm, beide Fußwendeln und die Stirnkurven
ein Zug mit 36 „Umläufen“. Die Achse ist der Zylinder durch die Punkte
(kleinste Quadrate, gestartet aus der SVD und den Achsen der
Zylinderflächen des Körpers — bestätigt einer davon die Achse, ist sie
`native`, sonst `fit`); in einer rechtshändigen Basis liefert die
Regression `z = z0 + L·θ/2π` den Vorschub, sein Vorzeichen die Händigkeit
und das Residuum die Wendelabweichung (`uncertainty`). Stücke derselben
Wendel — gleicher Radius, gleiche Phase — zählen zusammen, gruppiert mit
`RADIUS_TOLERANCE` und `PHASE_TOLERANCE` auf dem Kreis, nicht über `round`
(Regel 6: zwei Phasen 0,00499 und 0,00501 fielen in zwei Gruppen, und der
Körper galt als „nur 0,60 Umläufe belegt“). Ob überhaupt eine volle
Umdrehung belegt ist, sagen die Züge **um dieselbe Achslinie** wie der
längste zusammen: Zwölf Stücke einer halbierten Wendel belegen sie, zwei
Bögen um verschiedene Achsen nicht. Die Gangzahl ist die
Periodizität **aller** Wendeln (Kamm- wie Fußkanten) unter einer
Verschiebung um 1/n des Vorschubs — die Kammphasen allein zählten den
zweigängigen Körper als eingängig; die Regel steht einmal, in
`helix.starts_from_periodicity`, und der Kantenleser am Netz fragt dieselbe.
Die Materialseite kommt aus den orientierten Normalen der Flächen am Zug,
die Gangtiefe aus Kamm- und Fußradius gegen `helix.MEASURED_GROOVE_RANGE`
(dasselbe Fenster wie am Netz; beides träge importiert, damit `brep` keine
eifrige Kante zur Wahrnehmung bekommt). Unter einer vollen Umdrehung, bei
schlechter Wendel oder ohne Rille gibt es einen **Grund** fürs Protokoll
und nie eine geratene Steigung.

**Kegelige Gewinde** (P2.5-Rest): Wächst der Radius der Wendeln längs der
Achse (`_is_tapered`), passt `fit_cone_axis` einen Kegel statt eines
Zylinders ein, `measure_winding(tapered=True)` misst den Radius an der
Kegelfläche, und Kamm, Fuß und Nenndurchmesser gelten in der Mitte der
Gewindelänge. `ThreadReading.taper` ist der halbe Kegelwinkel mit Vorzeichen
(die weite Seite in Achsrichtung positiv), das Merkmal trägt ihn als
`taper` in Grad. Ändern, Entfernen (`prepare_ops._thread_frame`) und das
Gegenstück aus der Bibliothek (`counterpart`) sagen an einem kegeligen —
und das Gegenstück auch an einem mehrgängigen — Gewinde mit Grund ab, statt
es mit Zylindern zu ersetzen. **Und die Punktfolge eines Zugs beginnt an
seinem freien Ende** (`_ordered_points`): Die Sortierung über die übrigen
Stücke fragte während `list.sort` eine leere Liste, und ein zweigängiges
Innengewinde galt deshalb nicht als Gewinde.

`thread_features` macht daraus das Merkmal im Vertrag des Netzwegs —
`diameter` bleibt der Nenndurchmesser (außen Kamm, innen Grund) — mit
`lead`, `starts`, `handedness`, `crest_radius`, `root_radius`, `depth`,
`turns` und `uncertainty`, alle `native`; seine Dreiecke sind die aller
Flächen, die die Züge tragen. `features_of` ruft es nach den nativen
Flächen und verdrängt damit die Zapfen und Kegel auf der Wendel — dieselbe
Regel wie am Netz (`perceive.features.without_phantoms_on`), nicht kopiert.
Ein Körper trägt so höchstens ein Gewinde; der Netzweg (`find_helices`)
ist der gewollte Zwilling, und `tests/test_thread_import.py` lässt beide
auf dieselbe Frage antworten. Die Referenzkörper baut
`tests/data/make_thread_corpus.py` aus Konstruktionsmaßen.

## Kanten, Rundungen, Flächen

*Früher unter „Eine Kante hat einen Schlüssel, keine Nummer“.*

`edge_key` (RM-147 E4) beschreibt eine Kante über **Mittelpunkt und
Richtung**, gerundet auf ein Hundertstel beziehungsweise drei Stellen — die
Richtung ohne Vorzeichen, denn dieselbe Kante läuft je nach beschreibender
Fläche in beide Richtungen. Ein nativer Handle gehört dem Lauf, der ihn
erzeugt hat, und ein Index in `solid.edges()` verschiebt sich, sobald davor
etwas anderes passiert; beides in einer Projektdatei hieße, beim nächsten
Öffnen eine andere Kante zu verrunden. `named_edges` löst die Schlüssel wieder
auf, `fillet` und `chamfer` nehmen sie als `keys`, und die Auswahl `named`
sagt im Register, dass sie gelten. Eine Kante, die es nicht mehr gibt, ist ein
Satz an den Kunden — und ein anderer als „zu dieser Auswahl gehört keine
Kante".

**Innerhalb eines Aufrufs ist die Nummer dagegen der Beleg.** `fillet` und
`chamfer` nehmen mit `selected_edges` Indizes in `solid.edges()` des
Eingabe-Solids an — am aktuellen Eigentümer bestimmt, über
`Solid.checked_edge_indices` **vor** der Kopie geprüft und über
`_copied_edges` auf die Arbeitskopie geführt (`_edges_for`). Eine
ausdrückliche Auswahl geht vor `keys` und vor der Gruppe und fällt nie auf
sie zurück; eine Naht oder Nullkante darunter ist „zu dieser Auswahl gehört
keine Kante". So verrundet der Radiuswechsel genau die Kante, die die
Builder-Historie belegt hat, ohne gerundeten Schlüssel dazwischen — der
Index reist nie in eine Projektdatei, dafür bleibt es beim Schlüssel.
Denselben Weg nimmt die Kantenbindung der Auswertung (P1.4c.4b): Sie
bestimmt die Indizes über `native_edge_indices` — echte Mitgliedschaft in
der Kantenkarte des Solids, nicht die Position in `edges_of`, die Nähte
und Nullkanten auslässt — und gibt sie als `selected_edges` weiter.

`edge_points` gibt dieselbe Kante als **Punktfolge**, abgetastet nach
Abweichung (`DEFLECTION`, dieselbe Zahl wie die Tessellation). Mitte und
Richtung genügen für eine Auswahl nach Lage und nicht für einen Zeiger: Der
Schwerpunkt eines Bogens liegt neben ihm, beim Kreis einer Zylinderkante sogar
auf der Achse — also im Material. Eine Strecke kommt mit zwei Punkten zurück,
ein Kreis mit so vielen, wie die Abweichung verlangt. Die Ansicht projiziert
sie und misst im Bild (`ui/render/edges.nearest_polyline`).

*Früher im Kopf der Karte.*

**Verrunden mit Verlauf** (P6.1, `edit.fillet(law=)`): OpenCASCADE nimmt kein
eigenes Radiusgesetz an — `Add(Law_Function, E)` und `SetRadius(Law_Function,
…)` werfen in `Build` (OCCT 8.0.1), `SetLaw` setzt den Builder auf den
unveränderten Körper zurück, und `Add(R1, R2, E)` ist trotz der Doku nicht
linear. Getragen wird der Verlauf deshalb als dicht abgetastete Tabelle, **je
Kante der Kontur** (`SetRadius(UandR, IC, IinC)` gilt nur der Kante `IinC`):
`_contour_pieces` läuft die Kontur über gemeinsame Knoten ab, `_loop_start_on`
sucht den Anfang eines Rings an den Kurven, `geom.edges.samples_along` tastet
ab. Das Gesetz des Kerns nach dem Bau weicht höchstens 10⁻⁴ mm ab.

*Früher unter „Eine Rundung wegnehmen heißt, ihre Fläche zu streichen“.*

`unround` gibt `BRepAlgoAPI_Defeaturing` die Rundungsfläche, und der Kern
verlängert die Nachbarn selbst. Gemessen an einem Quader mit vier Rundungen zu
R = 3: 23884,115 mm³ nach dem Wegnehmen einer, analytisch 23845,487 + 1,9314·20
— dieselbe Zahl auf vier Stellen, in 18 ms. `reround` ist das plus einer neuen
Verrundung an der zurückgekommenen Kante — belegt über die Builder-Historie
(`_sharp_edge_after`, oben unter „Eigentum an der nativen Form"), nicht über
die nächste Kante zur alten Mitte: Von vier gleichen Rundungen bekommt genau
die gewählte den neuen Radius, auch wenn die genannte Mitte auf eine andere
zeigt (gemessen 20.09.2026, 24000 − 20·(1 − π/4)·(3·9 + 4)).

**Gesucht wird die Fläche über Radius und Lage**, und die Lage über den Abstand
zur **begrenzten Zylinderfläche** (`BRepExtrema_DistShapeShape`). Die unendliche
Achse unterscheidet keine getrennten Rundungen gleicher Achse und gleichen
Radius. `gp_Cylinder.Location()` hilft ebenso wenig: Die Parametrisierung
wählt irgendeinen Punkt auf der Achse, auch weit neben dem Merkmalsschwerpunkt.
Der Flächenabstand berücksichtigt dagegen die tatsächliche Ausdehnung und
bleibt von diesem Ursprung unabhängig. Der ungerundete Radius aus der exakten
Merkmalsauskunft muss zuvor innerhalb von `is_close` passen; eine breite
Radiustoleranz könnte an einer dünnen Wand die gegenüberliegende Seite wählen.
Ist der Abstand nicht bestimmbar,
bricht die Zuordnung ab, statt eine andere Fläche zu bearbeiten.

Mindestens halbe Zylinderwände tragen `radial=True`. `radial_rounding` baut
den Zwischenkörper aus einer privaten Kopie der begrenzten Mantelfläche und
prüft die gesamte Volumenänderung mit `geom.edges.validate_radial_change`.
`BRepLib.OrientClosedSolid` richtet dabei die Materialseite der privaten
Builder-Ausgabe vor ihrer Übernahme in `Solid` aus. Ein nicht orientierbarer
oder ungültiger Zwischenkörper bleibt ein Geometriefehler mit Handlungsvorschlag.
Veröffentlichte Körper werden weder umorientiert noch durch einen Absolutbetrag
ihres Volumens still berichtigt.
Innen und außen ergeben sich aus Flächenorientierung und Händigkeit des
Zylinderrahmens gemeinsam. Die Achse eines offenen Rings kann auf beiden
Seiten außerhalb des Materials liegen und genügt für diese Unterscheidung
nicht. Eine solche Wand hat keine scharfe Ersatzkante; ihr Radius ist der
Bearbeitungsweg.

**Und `push_faces` nimmt einen Ort entgegen.** Ohne ihn bewegte es jede Fläche,
deren Normale in die gegebene Richtung zeigt — an einer Treppe alle Stufen
(24000,0 statt 21000,0, Befund Robert 10.09.2026). Die Richtung bleibt der
Vorfilter, die Stelle entscheidet.

*Früher im Kopf der Karte.*

**Formschräge** (P6.4, `profiles.draft_faces`): gewählte Flächen oder alle
ebenen in Entformungsrichtung, dazu `_tangent_chain` (ebene und zylindrische
Flächen in Richtung, tangential angeschlossen); ein Ergebnis, das
`BRepCheck_Analyzer` ablehnt, ist eine Absage mit dem Satz des Netzes
(`faces.DRAFT_CUTS_THROUGH`). `ShapeFix_Shape` wird bewusst nicht benutzt: Es
macht den Körper zweier sich durchschneidender Wände formal gültig und zählt
die fehlende Wand negativ. `canonical.outward_normal` ist die eine
Flächennormale für Fase (`edit._faces_at_edge`) und Tangentenkette.

## Ein Loch lässt sich hier auch wieder schließen

*Früher unter „Ein Loch lässt sich hier auch wieder schließen (10.09.2026)“.*

`fill_bore` ist das Gegenstück zum Bohren, `cut_bore` das zum Merkmal statt zur
Fläche: eine freie Achse, die **Mitte** als Bezug — dieselben zwei Zahlen, die
`resize_bore` liest. Beide bauen ihren Zylinder über `_centred_bore`; der
Unterschied ist ein `gain` auf den Radius, und der ist keine Feinheit: Beim
Füllen ist er nötig, weil der gemessene Durchmesser von einem Vieleck stammt
und dessen Flanken innerhalb des Umkreises liegen, beim Schneiden wäre er ein
Maßfehler. In der Länge bleiben beide exakt — die Mündungen liegen in ebenen
Flächen, die OpenCASCADE ohne Sehnenfehler tesselliert, und eine Zugabe dort
ließe beim Füllen einen Zapfen stehen, den am exakten Körper nichts wieder
abschneidet.

Damit ist die letzte Absage gefallen, die den exakten Kern vom Netz-Kern
trennte: Bis dahin lehnten `slot_hole` und `resize_hole` das Versetzen eines
Lochs mit einem Satz ab. Gemessen an einer exakten Platte 60 × 40 × 10, Bohrung
Ø 8 von (−20 | −10) nach (0 | 0): geschlossen, Volumen davor und danach
23497,345 — dieselbe Zahl. Das Langloch daneben nimmt 1467,57 mm³ weg, den
analytischen Wert auf fünf Stellen.

**Und seit P2.4 bleibt der Körper auch beim Versetzen, Verdoppeln, Drehen
und Entfernen exakt** (20.09.2026): `geom.prepare_ops` ruft für Bohrung und
Langloch dieselben zwei Primitive — `fill_bore` an der alten, `cut_bore` oder
`slot_bore` an der neuen Stelle — und erkennt danach nativ. `unified` legt
die Nähte einer Booleschen wieder zusammen (der Deckel eines Füllkörpers
zerteilte die Platte in Ring und Scheibe: zehn Flächen statt sechs), mit
erhaltenen Filamentgrenzen; `fill_bore` und `slot_bore` rufen es. Gemessen:
Versetzen, Drehen um 90° und Entfernen treffen das analytische Volumen auf
die neunte Stelle, ein STEP-Umlauf verliert nichts
(`tests/test_exact_feature_ops.py`). Eine gesenkte Bohrung geht als Kette:
`revolved_bore_tool` und `clipped_bore_tool` bauen Stopfen und Werkzeug aus
den Einlaufprofilen von `geom.prepare_ops` — dieselben, mit denen
`resize_hole` den Einlauf ändert —, verschoben oder gedreht; ein gekippter
Kegel geht als B-Spline-Fläche durch STEP und hält dabei die siebte Stelle.
**Und ein Materialmerkmal hat einen Körper aus seinen Flächen**
(`solid_from_faces`): Randkanten zu Drähten verbunden
(`ShapeAnalysis_FreeBounds`), je Ring ein ebener Deckel, genäht und zum
Körper geschlossen — aus privaten Kopien der Flächen. Geschlossen ist, was
keine freie Kante hat; das `Closed()`-Flag setzt Sewing nicht, und an einer
Kuppe stand es auf falsch bei gültigem Körper (20.09.2026). Ein Ring, der in
keiner Ebene liegt, gibt keinen Körper: dann wird nichts geraten — außer der
Aufrufer füllt einen Hohlraum (`fan_caps`): Dann ist der Deckel die Fläche um
den Ring, fortgesetzt (`_continued_cap`, RM-248) — eine Fläche auf dem
Träger der einen Nachbarfläche, begrenzt vom Lochdraht (`_cap_on_carrier`),
oder eine Füllung mit dem Randdraht und Stützpunkten aus
`geom.mouth_cap` an den Flächen um den Rand (`_filled_cap`, `_faces_near`) —,
und erst wo beides nicht trägt oder das
Nähen damit scheitert, der Fächer vom Mittelpunkt (`_fan_cap`). Als
Werkzeug bekommt ein solcher Hohlraumkörper an seinen offenen Mündungen einen
Kragen (`collared`, das Prisma seines Deckels) — so schneidet
`geom.prepare_ops._exact_own_cut` ein versetztes Langloch samt Fasen und eine
Magnettasche samt Haltelippe. Was die
Erkennung am Kegel nicht nennt — Höhe und schmalen Radius —, liest
`cone_extent` aus dem Parameterbereich der nativen Fläche (ein Punkt liegt
bei `Location + v·cos(w)·Achse` mit dem Radius `RefRadius + v·sin(w)`, `w` der
halbe Öffnungswinkel), und
`_oriented_cone` baut daraus den exakten Kegelstumpf an freier Achse — das
Werkzeug, mit dem `geom/prepare_ops` einen Kegel kippt und eine Senkung
schneidet. `convex_hull` näht die Hülle des Netz-Zwillings zu einem exakten
Vielflächner — der exakte Kern hat keine eigene —, an dem ein Stopfen aus
Zahlen beschnitten wird, wie am Netz an `prepare.shell`. `void_body` macht
aus den ganz gewählten Schalen eines Einschlusses seine Luft — die größte
Schale als Körper ohne die Inseln, dieselbe Bauart wie in
`features._void_features`.

*Früher unter „Ein Wulst ist ein Ring, den man wegnehmen und wieder aufsetzen kann (P2.6)“.*

`torus` baut den vollen Ring um eine Achse durch einen Punkt — das Werkzeug
eines Torusmerkmals, vereinigt für den Wulst, abgezogen für die Kehle.
`defeatured` gibt `BRepAlgoAPI_Defeaturing` die Ringflächen und lässt den
Kern die Nachbarn verlängern, wie `unround` bei der Rundung; gemessen am
Schaft Ø 20 × 40 mit Wulst und Kehle R 10 / r 3 bleibt der Zylinder mit
seinem Volumen auf 10⁻¹⁶. Was der Kern nicht wegnehmen kann — den Ring, der
der ganze Körper ist, oder ein Torusstück ohne heilbare Nachbarn —, gibt er
unverändert zurück, und `defeatured` antwortet `None` statt mit demselben
Körper. Gearbeitet wird an einer privaten Kopie mit Builder-Historie, damit
Filamentgrenzen mitkommen (§21.2). Wer damit ein Gewinde wegnehmen will,
bekommt denselben Körper zurück: Die Gangflächen haben keine Nachbarn, die
sich zum Kern schließen — das Gewinde geht seinen eigenen Weg über
Hüllzylinder, Füllzylinder und das Bausteingewinde (`geom/prepare_ops`,
`_remove_thread`/`_resize_thread`).

## Bahn und Übergang

*Früher unter „Eine Bahn ist kein Bogen“.*

`sweep_path` (RM-147 E3) führt einen Querschnitt entlang einer gezeichneten
Bahn und benutzt dafür **`MakePipeShell`** mit `RightCorner`, nicht
`MakePipe`: An einer scharfen Ecke hört `MakePipe` auf zu bauen — gemessen an
einer Bahn aus 40 mm hoch und 30 mm quer ein Körper von 3141 mm³ statt 5497,
also genau das erste Segment, und ohne ein Wort dazu. `MakeSolid()` schließt
die Schale danach zu einem Körper; ohne diesen Schritt wäre das Ergebnis hohl,
und das fiele erst beim Schneiden oder Exportieren auf.

Innenkonturen folgen einzeln derselben Bahn und werden mit derselben
Booleschen Differenz wie beim Loft vom Außenkörper abgezogen. `MakePipeShell`
übernimmt nur den Außendraht; Löcher einer Profilfläche übernimmt es nicht.

Die Anfangstangente der ersten gerichteten Drahtkante muss senkrecht zum
XY-Querschnitt verlaufen. Geprüft wird die exakte Kurvenableitung, damit
Bögen und Splines nicht nach ihrer Sehne beurteilt werden. Schräger oder
entarteter Beginn hält vor dem Körperaufbau mit einem Handlungsvorschlag an.

**Gültig heißt nicht selbstschnittfrei.** Eine Bahn, die enger biegt, als der
Querschnitt breit ist, oder deren Stücke sich zu nahe kommen, ergibt einen
Körper, den `BRepCheck_Analyzer` durchlässt. `intersects_itself` fragt
`BRepAlgoAPI_Check` mit Selbstschnittprüfung; die Skizzen-Operationen rufen es
für jede gezeichnete Bahn und jedes Übergangswerkzeug eines Schnitts (P6.5).

**Und `IsDone` heißt nicht gültig.** `is_sound` fragt `BRepCheck_Analyzer`
am Ergebnis. Gemessen an `carpet-corner-clip.step` (zwei Teile, aus
F:\3D Dateien): Eine Ringnut in der Bohrung Ø9 meldete Erfolg, das Volumen
sank um genau das Werkzeug, und der Körper war ungültig — die Luft der
Bohrung galt danach als innen. Die Schnitte mit Werkzeug liefern ein solches
Ergebnis nicht aus, sondern rechnen am Netz weiter und sagen es
(`sketch.exact_cut_unsound`). *Tasche schneiden* gab an derselben Stelle
denselben ungültigen Körper still zurück; seit RM-227 nimmt sie denselben
Rückweg.

`loft(..., compatible=False)` schaltet die Eckenzuordnung von OpenCASCADE ab
(`ThruSections.CheckCompatibility`). Nur wer die Zuordnung selbst entschieden
hat, nimmt das — der Übergangsschnitt, wenn zwei Zuordnungen gleich nah waren
und gefragt wurde; bei Gleichstand wählte der Kern sonst nach der letzten
Stelle einer Summe. Die Vorgabe bleibt `True`, der Erzeuger rechnet wie bisher.

## Eine STEP-Datei ist eine Baugruppe

*Früher unter „Eine STEP-Datei ist eine Baugruppe (P7.4)“.*

`step.read_assembly` liest über XCAF (`STEPCAFControl_Reader`, `ReadStream`)
und löst **jede Komponenteninstanz in einen eigenen Körper** auf: Form in
Weltlage, Name, Farbe je Fläche, eine Kennung (`StepBody.key`, der Pfad der
Vorkommen, „1.3.2“, bei einem Teil mit mehreren Körpern „1.3#2“) und die
Kennung des eingesetzten Teils (`geometry`). Lebende Instanzbeziehungen
entstehen nicht — zwei Bolzen desselben Teils sind danach zwei unabhängige
Körper. `step.read` bleibt der Leser vor P7.4 (`OneShape`, ein Körper) für
gespeicherte Schritte ohne Auswahl und für den gemeldeten Rückfall.

**Welcher Name gilt:** Instanz → Referenz (Teil) → Form (Körpername). Ein Teil
mit mehreren Körpern nennt jeden beim eigenen Namen, weil Instanz und Referenz
dort die Gruppe nennen; ohne ihn „Teil n“. Gleichnamige bekommen den nächsten
unterscheidenden Vorkommensnamen in Klammern, danach Nummern; namenlos heißt
ein einzelner Körper wie seine Datei, sonst „Körper n“. Was kein Mensch
vergeben hat, zählt nicht (`usable_name`): OCCTs Übersetzername, die
NAUO-Nummer einer unbenannten Instanz, XCAF-Typwörter.

**Welche Farbe gilt, je Fläche:** Instanz (von der äußersten Baugruppe nach
innen, je Ebene SHUO vor der Farbe des Vorkommens) → Referenz (im Teil:
Fläche → Schale → Körper → Teil) → Form (`XCAFDoc_ColorTool.GetColor` an der
Form). Oberflächenfarbe vor allgemeiner, Kantenfarben zählen nicht. OCCTs
eigene Darstellung (`XCAFPrs`) ließe eine Flächenfarbe des Teils über der
Instanzfarbe stehen; hier meint eine Farbe am Vorkommen das ganze Vorkommen.
**Der Farbraum ist sRGB**: OCCT hält Farben linear (`COLOUR_RGB 0,627` kam als
`0,3515` an), zurück über `Quantity_TOC_sRGB`, gerundet auf `#rrggbb`. Die
Farbnamen der Datei werden nicht übernommen — Fusion nennt ein eingefärbtes
Creme „ABS (Black)“.

**Eine starre Instanzlage bleibt eine Lage** (`TopLoc_Location`, die Form
teilt ihre `TShape` mit dem Teil). **Eine Spiegelung wird eingerechnet**
(`BRepBuilderAPI_Transform`), weil eine Lage mit negativer Determinante
Normalen umkehrt; die Flächenzuordnung geht über `ModifiedShape`. Geschlossene
Schalen ohne Körper werden Körper, offene Schalen und lose Flächen eines Teils
ein offener Körper; Teile nur aus Kanten oder Punkten zählt `skipped`.

Drei Fallen der Bindung, alle gemessen:

- **`label.FindAttribute(guid, TDataStd_Name())` stürzt nativ ab** — der
  Handle-Ausgabeparameter gibt das Python-Objekt frei. Namen liest
  `_name_of` über `TDF_AttributeIterator`. Dasselbe Muster lässt
  `SetSHUO(labels, XCAFDoc_GraphNode())` ein leeres Label zurückgeben.

- **Körpernamen eines Teils brauchen `read.stepcaf.subshapes.name`**, und
  der Schlüssel existiert erst nach `STEPCAFControl_Controller.Init` —
  vorher gibt `SetIVal` still `False` zurück (`_prepare_translator`).

- **`TCollection_ExtendedString(text)` liest UTF-8 Byte für Byte**; ein Name
  braucht `TCollection_ExtendedString(text, True)`.

Gelesen und geschrieben wird **ein XCAF-Dokument zur Zeit** (`_XCAF`): Die
Dokumente hängen an der einen `XCAFApp_Application` des Prozesses, und der
Einleseplan im Arbeiter darf der Auswertung eines zweiten Imports nicht
begegnen. Die Maße für Auswahl und Bett kommen aus den Grenzen des Teils,
einmal je Teil gemessen und in die Lage gebracht (`StepBody.box`, genau bei
einer reinen Verschiebung) — `AddOptimal` je Instanz kostete an tausend
gerundeten Teilen 8 s.

**Hinaus geht es denselben Weg** (`write_bodies`): XCAF, der Name wörtlich im
PRODUCT (der alte Weg über `write.step.product.name` hängte „ 1“ an), Farben
je Fläche, die Wurzellage eingerechnet (mit Lage fand `AddSubShape` keine
Fläche), Nicht-ASCII nach ISO 10303-21 kodiert (`escaped`). Die Rundreise gibt
dieselben Körper, Namen und Farben zurück.

`load_step` (`ingest/step_ops.py`) überträgt die Merkmale weiterer Instanzen
desselben Teils statt neu zu suchen, unter Beleg an der Form — dieselbe `TShape`, starre Lage,
gleiche Flächenzahl, nur Merkmale aus ganzen nativen Flächen mit Formmaßen —,
und ordnet die Dreiecke je nativer Fläche neu zu: `BRepMesh` trianguliert
dieselbe Fläche an anderer Lage mit anderen Diagonalen. Die Regeln dazu
stehen in `.claude/rules/dateiformat.md`.

## OpenCASCADE 8 in der Bindung

*Früher unter „Optional heißt: er meldet sich ab“.*

Fehlt OpenCASCADE, ist `available()` falsch und `BRepUnavailable` die Antwort
— die Anwendung läuft weiter, die betroffenen Operationen sind es, die
verschwinden. **Kein Absturz, kein Stacktrace, ein Satz mit Weg nach vorn.**
Jeder Code hier prüft das, bevor er den Kern anfasst.

Seit OCP 8.0.1 (05.09.2026) heißen fünf Dinge anders, und der Kern verlangt
diese Fassung (`pyproject.toml`, `brep`-Extra). Das gilt auch für den einen
Nutzer außerhalb dieses Verzeichnisses, `app/core/sketch/profile.py`:

| Vorher (OCP 7.9) | Jetzt |
|---|---|
| `OCP.TopTools.TopTools_IndexedMapOfShape` | `OCP.collections.IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher` |
| `TopTools_IndexedDataMapOfShapeListOfShape` | `OCP.collections.IndexedDataMap_TopoDS_Shape_List_TopoDS_Shape_TopTools_ShapeMapHasher` |
| `TopTools_ListOfShape` | `OCP.collections.List_TopoDS_Shape` |
| `TopoDS.Face_s(shape)`, `Edge_s`, `Wire_s` | `TopoDS.Face(shape)` — `TopoDS` ist ein Namensraum, kein `_s` |
| `Bnd_Box.Get()` | `kernel.box_limits(box)` — `Get` liefert eine ungebundene `Limits`-Struktur |
| `OCP.TColgp.TColgp_Array1OfPnt`, `TColgp_Array1OfPnt2d` | `OCP.collections.Array1_gp_Pnt`, `Array1_gp_Pnt2d` — `OCP.TColgp` ist ein leeres Modul |
| `OCP.GCE2d.GCE2d_MakeSegment`, `GCE2d_MakeArcOfCircle` | `OCP.GC.GC_MakeSegment2d`, `GC_MakeArcOfCircle2d` — `OCP.GCE2d` ist ein leeres Modul |

Die übrigen statischen Aufrufe (`TopExp.MapShapes_s`, `BRep_Tool.Triangulation_s`,
`BRepGProp.VolumeProperties_s`, `BRepBndLib.AddOptimal_s`) tragen ihr `_s`
weiter. Wer einen neuen Sammlungstyp braucht, sucht ihn in `OCP.collections`
über `dir()` — die Namen folgen dem C++-Template, nicht dem alten Typedef.
**Und ein leeres Modul importiert ohne Fehler**: `from OCP.GCE2d import …`
scheitert erst am Namen, und zwar erst, wenn die Zeile läuft — bei der
Skizze war das die Selbstschnittprüfung, die `tests/test_brep.py` nie
aufrief. Deshalb hält dort jetzt ein Test jeden `from OCP.…`-Import der
Anwendung gegen die installierte Bindung.

## Masseeigenschaften

*Früher unter „Eigentum an der nativen Form“.*

`properties.py` liefert unveränderliche `MassProperties` für Körpermaße und
Merkmalsauskunft gemeinsam — **nativ mit Knotenzerlegung, Python als
Rückfall** (21.09.2026). Analytische Flächen bleiben im nativen Standardweg.
Jede andere Fläche geht als **knotenzerlegter Verbund** privater Kopien in
die native Integration: Spline-Flächen an ihren eigenen Knoten geteilt, eine
Extrusion an denen ihrer Basiskurve, ein Drehkörper ebenso, Offset- und
Trimmhüllen unter sich gelesen. Der Grund ist der Zackenkörper in
`tests/test_brep.py`: Die native Gauß-Quadratur übersieht auf der ganzen
Fläche eine 10⁻⁵ breite Spanne und meldet dazu 10⁻¹⁶ Fehler; je Spanne
getrennt trifft sie exakt. Und die Extrusion eines rationalen Kreises maß
ungeteilt 1,2 Prozent daneben, bei gemeldetem Fehler 2·10⁻¹⁶.
**Die Leiter 1/2/4** — jede Spanne ganz, halbiert, geviertelt — verlangt
von zwei Stufen Einigkeit in Masse und Schwerpunkt auf
`INTEGRAL_RELATIVE_ERROR`; die Trägheit muss nur endlich sein, niemand liest
sie (die Forderung nach 10⁻⁹ an ihr schickte die erste Fläche des M10 für
5 s in den Python-Weg). Ohne Spannen genügt die erste Stufe. Erst wenn die
Leiter nicht zusammenkommt, integriert der Python-Rückfall entlang der
ursprünglichen Randkurven — derselbe Weg, tausendmal langsamer. **Und beim
Volumen nur für die Flächen, die wandern** (`_mixed_volume`, Durchsicht
0.5.1): Die Leiter schreibt ihre Stufen je Fläche mit (`_volume_ladder`);
wer am meisten wandert, geht zuerst den langsamen Weg, bis Fehler und
Uneinigkeit der übrigen — ohne Vorzeichen summiert — unter der Grenze liegen.
An der Lochplatte `pegboard-gs-100-v2.step` schließt der Parameterrand einer
von 49 Flächen nicht (Lücke 5,7·10⁻⁴); dafür rechnete der Rückfall alle 49,
24 s nach dem Laden und nach jedem Schritt, jetzt 1,5 s bei derselben Zahl
(5·10⁻¹⁴). Erst wenn auch das nicht hält, integriert der Rückfall alle.
Zwei Dinge daran sind gemessen, nicht angenommen: Die Teilflächen tragen die
ursprünglichen Trimmkurven, an den Knotenlinien geschnitten, **ohne**
`BuildCurves3d` und `SameParameter` — beides verschob die Ränder um bis zu
8·10⁻⁶ mm, und jede feinere Stufe integrierte ein anderes Gebiet. Und der
**Bezugspunkt des Kegelvolumens ist fest** (die Hüllmitte, wie im
Python-Weg; `BRepGProp_Vinert` je Fläche statt `VolumeProperties` am
Verbund): OCCT wählt sonst den groben Schwerpunkt der übergebenen Form, der
mit jeder Teilung wandert, und an einem Körper mit Nähten innerhalb seiner
Toleranz hängt das Volumen daran (M10-Bolzen des alten Korpus, 3,5 µm
Kantentoleranz: 10⁻⁷ zwischen den Stufen).
Was die Leiter nicht zusammenbringt, sind Körper, deren Nähte unter ihrer
Toleranz offen stehen — die Sweep-plus-Fuzzy-Bolzen des alten
`threaded_rod` (Grad 9, C⁰ an jedem Knoten): Dort gaben zwei exakte
Integrationswege dieselbe Fläche um 10⁻⁸ verschieden an, und kein dritter
konnte entscheiden; das Volumen solcher Körper ist unterhalb dieser Grenze
nicht definiert, und der Rückfall zertifiziert dort einen Wert, der nicht
besser ist. Der genähte Bolzen (RM-195) kommt bei 10⁻¹⁵ zusammen.
Der Python-Rückfall verschiebt eine private Arbeitsfläche vor der Auswertung
in den gemeinsamen lokalen Bezugsrahmen — derselbe Rahmen, in dem auch der
Verbund rechnet (`BRepTools_Modifier`, nicht der Transformationsbuilder, den
`edit.transformed` als Vertrag führt). Dadurch entstehen bereits die
rationalen Ableitungen ohne Verlust durch große Weltkoordinaten. Originale
Trimmparameter, Normalenorientierung und Fehlerschranken bleiben erhalten;
nur der fertige Schwerpunkt wird in Weltkoordinaten zurückgeführt.
Das gilt auch für ihre BSpline-Trimmkurven: unabhängige polynomiale
Green-Integrale prüfen Fläche und Schwerpunkt bei ungleichmäßigen Knoten und
Innenlöchern. Jeder native Weg prüft seinen gemeldeten Integrationsfehler
sowie endliche, nicht negative Maße; Schwerpunkt und berechnete Trägheit
müssen ebenfalls endlich sein. Native Ausnahmen tragen denselben Rückweg.
NURBS-Volumen und Schwerpunkt entstehen über den Divergenzsatz auf den
ursprünglichen Flächen; eine leere Form hat Volumen null, und ob das ein
Befund ist, entscheidet der Aufrufer. Der native GK-Weg (`VolumePropertiesGK`)
lässt innere V-Knotenspannen aus — gemessen 6·10⁻⁸ am STEP-Gewinde bei
ehrlich gemeldetem Fehler —, terminiert aber, auch mit Schwerpunktrechnung
(74 ms am Korpus; die Behauptung, er könne hängen, war nicht zu belegen).
Volumenträgheit wird ausdrücklich als nicht berechnet geführt und ist keine
öffentliche Körperauskunft.
Eine Offset- oder Trimmhülle ändert die nötigen Integrationsspannen ihrer
NURBS-Basis nicht. `properties` liest diese Basis über die gemeinsame native
Trimmhüllenauskunft, nutzt ihre Knoten für Unterteilung und Randintegration
und integriert weiterhin die ursprüngliche Offsetfläche. Ein kleiner nativer
Fehlerwert ersetzt auch dort keinen Nachweis über die Knotenspannen.
Schräg verlaufende Trimmränder werden an ihren tatsächlichen Schnitten mit
U- und V-Knoten zerlegt; auch die äußere Randintegration muss jede schmale
Spanne sehen. Periodische Basisknoten werden in das wirkliche Trimmintervall
verschoben, ohne die veröffentlichte Parametrisierung zu verändern.
Alle Beiträge teilen einen Ursprung und berücksichtigen gerichtete innere
Wände sowie gemeinsame Flächen mehrerer Körper.

Transformationswege reichen ihren optionalen `CancelToken` über
`Solid._properties` bis in die Integrationsrechnung. Er wird vor der Arbeit,
an Flächen-/Knotengrenzen und an jedem UV-Quadraturpunkt geprüft. Auch ein
Cachetreffer muss einen bereits verlangten Abbruch beachten; vor dem Speichern
einer vollständigen Kennzahl wird erneut geprüft. `OperationCancelled` bleibt
über native Fehler- und Integrationsrückfälle unverändert erhalten. Der Token
gehört dem Aufruf und wird weder an der Form noch im Cache gespeichert.
Ein einzelner nativer OCCT-Aufruf wird vor und nach seinem Lauf geprüft;
die Python-Quadratur braucht keinen Abschluss einer ganzen Fläche abzuwarten.

NURBS-Flächen werden zunächst auf privaten Kopien an Knotenspannen unterteilt.
Fläche und Schwerpunkt müssen gemeinsam konvergieren, die Flächenträgheit
endlich sein. `ShapeFix_ComposeShell` braucht einen expliziten
`ShapeBuild_ReShape`-Kontext; die Teilflächen werden **nicht** nachgezogen
(siehe oben), und ob die Zerlegung vollständig ist, belegt die Leiter.
Konvergieren schwierige Trimmungen dort nicht, integriert
der gemeinsame Rückfall entlang ihrer ursprünglichen UV-Randkurven. Der
Umlaufsinn innerer Drähte zieht Löcher ab; native Ableitungen, Knotenspannen,
innere und äußere Quadraturfehler sowie ein begrenztes Auswertungsbudget
bestimmen den Nachweis. Scheitert er, wird keine geratene Kennzahl gecacht.
Die veröffentlichte Form und ihre Triangulation werden dabei nie geändert.
Die Knoten der gerichteten Trimmkurven kommen aus `LKnots`: `GetTKnots` lässt
sie in OCCT 8 an analytischen Trägerflächen aus, selbst wenn ihre Randkurve
eine BSpline ist. Rechengenauigkeit und feste Arbeitsgrenze sind unabhängig;
viele Trimmkurvenabschnitte erhöhen den Bedarf schon ohne Verfeinerung.
Innere V-Knoten werden mit den gerichteten UV-Randkurven nativ geschnitten
(`Geom2dInt_GInter`); die resultierenden Kurvenparameter teilen auch sehr
schmale Flächenabschnitte ausdrücklich ab. Die Konditionierung über den
nativen Hüllquader setzt kein bereits verlässlich gerechnetes Maß voraus.
