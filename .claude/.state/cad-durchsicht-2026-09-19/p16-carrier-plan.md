# P1.6 — Teilträger an Veröffentlichung und Nachführung anschließen

Lesende Vorbereitung vom 20.09.2026 während des eingefrorenen Entwicklungstors.
Grundlage: `p16-deviation-plan.md`, danach `p16-contract.md`, die aktuellen
Karten von `perceive/` und `brep/` sowie der tatsächliche Aufrufweg. Es wurden
keine Produkt- oder Testdateien geändert und keine Tests ausgeführt. Dieser
Plan ergänzt die Herkunft und Zuordnung der Daten; Extremwertrechnung und
Oberfläche stehen in den getrennten P1.6-Notizen.

## 1. Kleiner gemeinsamer Vertrag

`Feature.surface_patches` wird das letzte optionale Feld, Vorgabe `()`.
Ein `SurfacePatch` ist unveränderliches abgeleitetes Datum: Trägerart, wirklich
verwendete Trägerparameter, ursprüngliche Dreiecksindizes und tatsächliche
Quelle. Kein eigener Featurebezeichner, keine OCCT-Handles, Fitobjekte,
Builder, NumPy-Felder, Nachbarschaften oder Messpunktwolken darin speichern.

Die physisch nötigen Zahlen sind:

| Art | Nötiger Trägerinhalt, unabhängig von semantischen Anzeigemaßen |
|---|---|
| `plane` | Ebenenpunkt und normierte Normale |
| `cylinder` | Ein wirklicher Punkt der Achse, normierte Achse, Radius |
| `cone` | Tatsächliche Spitze, gerichtete Achse Spitze → belegte Nappe, positiver Halbwinkel mit festgelegter Einheit |
| `sphere` | Kugelmittelpunkt und Radius |
| `torus` | Ringmittelpunkt, Achse, großer Ringradius und Rohrradius |

Bezeichnungen der zentralen Datenfelder legt Root vor der Umsetzung fest.
Die Trägerzahlen bleiben float64; keine Anzeige- oder Sortierrundung übernehmen.
Insbesondere `ConeFit.apex` direkt erhalten. Eine Rückrechnung aus dem
veröffentlichten großen Durchmesser und Auswahlmittelpunkt ist unnötig.

Die Quelle verwendet die vorhandenen Begriffe: `fit` für tatsächlich
eingepasste Rundträger, `native` für gelesene beziehungsweise nachgewiesene
Originalträger und `facets` für eine am vorhandenen Netz belegte Ebene.
`parameter` allein belegt keine Oberfläche. `Feature.measure_sources` bleibt
die Quelle seiner einzelnen semantischen Maße; beispielsweise kann ein Slot
ein gefittetes Gesamtmaß und native Teilflächen besitzen.

Patchindizes sind eindeutige, nichtnegative ganze Dreiecksindizes, keine
nativen Flächennummern. Sie sind eine Teilmenge des enthaltenden Features und
beziehen sich auf genau dessen heutigen Körper. Leere, unvollständige oder
ungültige Träger erlauben keinen Nullwert. Widersprechende Träger auf einem
Dreieck bleiben mehrdeutig; weder kleinster Abstand noch zuerst gelesener
Träger löst diesen Konflikt. Identische weitergereichte Daten dürfen ohne
neue Einpassung dedupliziert werden; fast gleiche Radien nicht mitteln.

## 2. Mesh: Erst am endgültigen Veröffentlichungspunkt anhängen

Alle folgenden Funktionen liegen in `app/core/perceive/features.py`.
Die vorhandenen Fit-/Erkennungstore bleiben unverändert. Ein Träger entsteht
nicht schon an jedem spekulativen Kandidaten in `_fitted` oder `_surface_support`.

| Funktion | Verwendete vorhandene Lösung | Kleiner Anschluss |
|---|---|---|
| `detect_holes` | endgültiger `CylinderFit`, zugehöriger `patch` | Zylinder aus genau diesem Fit und denselben Originalindizes |
| `detect_pins` | endgültiger `CylinderFit` | wie Bohrung |
| `detect_fillets` | die veröffentlichte Auswahl `radial or fitted` | den tatsächlich gewählten Zylinder erhalten, nicht den vorherigen Kandidaten |
| `detect_cones` | akzeptierter `ConeFit` einschließlich `apex` | Spitze, Achse, Halbwinkel und Patch vor dem Weglassen der Spitze aus den bisherigen Featureparametern sichern |
| `detect_spheres` | akzeptierter `SphereFit` | tatsächliches Zentrum, Radius und Patch |
| `detect_tori` | akzeptierter `TorusFit` | `centre`, `axis`, `ring_radius`, `tube_radius`, Patch; `diameter` ist der große Ringdurchmesser, nicht der Außendurchmesser |
| `detect_faces` | Eintrag aus `_planar_face_entries`, erste Flächennormale, ungerundete `_facet_centre` | diese vorhandene Ebenenauskunft mit den wirklichen Facettenindizes erhalten |

`_merged_cylinders`, `_merged_cones` und `_merged_tori` prüfen bereits einen
gemeinsamen Fit und geben bei Erfolg diesen mit dem vereinigten Patch zurück.
Die Veröffentlichung übernimmt ihn. Sie darf nicht zusätzlich die verworfenen
Einzelfits als konkurrierende Träger speichern. `_split_off_fillets`,
`_cylinder_beside_a_torus`, `_without_thread_turns` und die Klassifikationsfilter
brauchen keinen neuen Datenspeicher: Ihr endgültiges Ergebnis erreicht die
genannten Hersteller ohnehin.

Bei Ebenen ist der vorhandene Nachweis präzise abzugrenzen:
`_planar_face_entries` liest zusammenhängende `body.facets`, die vorhandene
Planaritätsklassifikation und die Gleichrichtung aller Normalen zur ersten
Normale innerhalb `EPS_ANGLE`. Ein ausdrücklicher Abstandstest aller Ecken
zu einer Ebene steht dort noch nicht. Für einen belegten Ebenenträger ist
die kleine Ergänzung ein gemeinsamer Eckentest gegen den bereits gewählten
Punkt und die Normale, mit der bestehenden numerischen Ebenengrenze. Kein
neuer Best-Fit der Ebene und keine Lockerung der Featureerkennung. Besteht
dieser zusätzliche Trägernachweis nicht, bleibt das semantische Feature
erhalten, sein Ebenenträger aber unbekannt. Die Karte berechnet auch bei
akzeptierten Ebenen den wirklichen Dreiecksabstand und setzt ihn nicht null.

`detect_curved_faces` hat nur Restfläche, Schwerpunkt und gemittelte Normale.
Daraus wird kein neuer analytischer Träger. Ebenso haben `detect_edge_loops`
und der äußere Rand einer allgemeinen `void`-Form allein keine Rundlösung.
Eine Ablehnung durch `_shapes_on_a_freeform` entfernt auch deren Träger;
keine versteckte Sammlung verworfener Kugel-/Torusfits für die Karte behalten.

## 3. Slots, Fasen, Innenräume: Geometrische Teile erhalten

### Geschlossenes Langloch — `app/core/perceive/slots.py`

`Slot` ist bereits das kleine Zwischenresultat von `find_slots` und
`slots_from_stadiums`. Es braucht ebenfalls das optionale Patchtupel; damit
`slots_instead_of_half_bores` beim Löschen der Einzelmerkmale keine Geometrie
verliert. Die bestehende Flächendeckung bestimmt weiter, welche Merkmale
verschluckt werden; keine Zuordnung über die Nummer eines Fillets ergänzen.

`_slot_from` hat zwei tatsächlich verschiedene Zweige:

- Beim direkten Bogenpaar liegen `fit_a/patch_a` und `fit_b/patch_b` bereits
  vor. Ihre getrennten Zylinder übernehmen. Der gemittelte semantische Radius
  und die gemittelte Slotachse ersetzen diese beiden Lösungen nicht.
- `_corners_are_flanks` prüft derzeit nur den Abstand der Flankenecken zu
  den beiden Seitenlagen. Das ist noch kein gemeinsamer Normalen-/Ebenenbeweis.
  Vorhandene passende Ebenenpatches aus den verschluckten Flächen erhalten;
  sonst denselben kleinen Ebenennachweis an den bereits gesammelten
  `flank_indices/flank_corners` benutzen. Fremde geneigte Streifen nicht als
  Ebene bezeichnen, nur weil ihr Abstand in den Slotbereich fällt.
- Im Rückfallzweig wird schon jetzt einmal `fit_stadium` am ganzen Mantel
  gerechnet und in `_Reach.stadiums` wiederverwendet. Der akzeptierte
  **StadiumFit** ist dann die maßgebliche Lösung; keine erneute Einpassung
  und keine Übernahme der dabei ersetzten, verunreinigten Bogenkandidaten.

`slots_from_stadiums` und dieser Rückfallzweig benötigen denselben kleinen
Zerleger der vorhandenen Stadionlösung. Bei Mittelpunkt `c`, Achse `a`,
Längsrichtung `d`, Reise `L` und Radius `r` sind die Endzylinder an
`c ± L*d/2` und die Seitenebenen an `c ± r*cross(a,d)` gegeben. Zuordnen
lässt sich ein ganzes Originaldreieck nur, wenn seine drei Ecken im selben
eindeutigen Trägerbereich des vorhandenen Stadionrahmens liegen. Die linearen
Bereichsbedingungen gelten dann auch im Dreiecksinneren. Eine Facette, die
den Übergang überspannt, bleibt unbekannt; kein Schwerpunktentscheid,
Nächstträger-Minimum oder neues Aufteilen des Netzes. Die Flächenindizes des
Slotfeatures bleiben dabei vollständig, auch wenn einzelne Träger fehlen.

### Offenes Langloch — derselbe vorhandene Weg

`open_slots_instead_of_fillets` erhält einen fertigen `CylinderFit` und
benutzt `_open_slot_shell` für den ganzen vorhandenen offenen Mantel.
Die Flutung führt **bereits `arc_faces`**, gibt aber nur
`(selected, rim, has_flanks)` zurück. Die Bogenindizes zusätzlich zurückgeben
ist die wichtigste kleine Ergänzung: Es gibt bereits einen Nachweis, der
bisher vor der Veröffentlichung verloren geht. Den gewählten Zylinder nur
diesem Bogenanteil zuordnen. Hinzugefundene Bogenfacetten mitnehmen; ebene
Tangententeile getrennt über vorhandene Flächenpatches beziehungsweise den
gemeinsamen Ebenennachweis führen.

`_open_slot_candidates` kennt `on_arc` und `tangent` bereits. Es braucht
keinen zweiten Radiusfit und keine neue Ganzkörpermaske je Bogen. Der
Rückgabevertrag des Flutungshelfers und die vorhandene Aufrufstelle reichen.

Der native Aufrufer benutzt für diese **semantische** offene Slotentscheidung
ebenfalls einen Mesh-Zylinderfit. Schon vorhandene native Träger desselben
Originalflächenanteils bleiben dabei die stärkere tatsächliche Auskunft:
sie vor dem Verschlucken mitnehmen, den Fitträger nur für unbedeckte,
wirklich geprüfte Anteile ergänzen. Diese eindeutige Zuordnung erfolgt beim
Hersteller aus der bekannten Topologie, nicht als kleinster Abstand in der
Karte. Unterschiedliche konkurrierende Meshfits nicht still überlagern.

### Weitere semantische Zusammenfassung — `perceive/features.py`

| Funktion | Regel für Teilträger |
|---|---|
| `_partial_cones_folded` | Mit den Kegeldreiecken auch deren vorhandenen Kegelpatch an den Slot hängen, bevor das Kegelmerkmal gelöscht wird. Slotmaße bleiben wie bisher ohne Fase. |
| `voids_instead_of_phantom_bores` | Die anerkannten geometrischen Teile bleiben gültig, nur die Benennung als Öffnung war falsch. Vor dem Löschen ihre Patchindizes exakt mit der jeweiligen Innenraumhülle schneiden und am `void` erhalten. Die Mehrheitsregel darf keinen fremden Dreiecksanteil mitnehmen. |
| `_threads_instead_of_phantoms` | Verworfene vermeintliche Kugeln/Zylinder/Kegel auf einer Wendel nicht zu Trägern des Gewindes erklären. Die helikale Fläche wird hierdurch nicht zylindrisch; ohne eigenen belegten Träger bleibt sie unbekannt. |
| Rollen, `partial`, `recess`, Erzeuger, Umbenennung | Vorhandenes `replace` erhält die unveränderten Träger automatisch. Diese semantischen Felder ändern keine Oberfläche. |

## 4. Native Veröffentlichung — `app/core/brep/features.py`

`features_of` liest bereits **einmal** je Originalfläche
`describe_surface(face, cancelled=...)` in die temporäre Tabelle `surfaces`.
Sie ist eine native Flächenauskunft, keine zweite Sammlung semantischer IDs.
Diese vorhandene Auskunft wiederverwenden. `_describe` kann neben Art und
Featureparametern den kleinen Trägerwert zurückgeben; danach ordnet der
Hersteller genau `solid.triangles_of_face(index)` zu. Kein weiterer
Recognizer, keine Probetessellation und kein Refitting.

| Bereits gelesene Fläche | Richtige Daten und Fallstrick |
|---|---|
| `PlaneSurface` | Punkt aus der wirklichen Ebene, `surface.normal`; auch beschnittene Ebenen mit Innenringen tragen denselben Träger. |
| `CylinderSurface` | Achsenpunkt aus `cylinder.Location()`/Achse, Radius. Bei einer nativen Verrundung ist Feature-`centre` teils der **Flächenschwerpunkt**, also gerade kein Achsenpunkt. |
| `GeomAbs_Cone` im bestehenden `_describe`-Zweig | Bereits gelesene `gp_Cone`: Spitze aus Ursprung, signiertem Halbwinkel und Referenzradius; äquivalent `location - axis*RefRadius/tan(SemiAngle)`. Nappenrichtung an der tatsächlich verwendeten Winkel-/Trimmauskunft erhalten. Nicht den gerundeten Auswahlumfang rückwärts interpretieren. |
| `SphereSurface` | `sphere.Location()` und Radius. Bei einer kugeligen Eckverrundung ist Feature-`centre` wiederum nur die Auswahlmitte. |
| `TorusSurface` | `torus.Location()`, Achse, großer und kleiner Radius. Die vorhandene kanonische NURBS-Prüfung liefert bereits denselben Nachweis. |

Der vorhandene kanonische Typverbund enthält Ebene/Zylinder/Kugel/Torus,
noch keinen NURBS-Kegel. P1.6 ergänzt nicht still einen neuen kanonischen
Erkenner: Ein unbewiesener NURBS-Kegel bleibt unbekannt.

Weitere native Anschlüsse:

- `_slots_instead_of_half_bores` → `_one_slot`: beide ursprünglichen
  Zylinderflächen und die durch `_flanks_of_a_slot` belegten Ebenen separat
  übernehmen. Die vorhandene `surface_of`-Tabelle und tatsächlichen nativen
  Flächennummern reichen auch dann, wenn eine kleine Einzelfläche zuvor kein
  eigenes semantisches Feature erhielt. Ihre Nummern **erst** über
  `triangles_of_face` in Anzeigedreiecke abbilden.
- `_joined_tori`: Das Zusammenfassen vereinigt die einzelnen ursprünglichen
  Trägerpatches. Der topologische Vergleich innerhalb `EPS_GEOM` rechtfertigt
  keine Mittelung oder Ersetzung aller Teilflächen durch die Parameter des
  ersten Torus.
- Gemeinsamer offener Slotweg: native Teile wie in Abschnitt 3 erhalten.
- Rest-`curved_face`: Exakte Fläche und Schwerpunkt aus nativen Integralen
  beweisen keinen analytischen Träger. Nur vorhandene Träger aus `surfaces`
  für ihre wirklichen Dreiecksanteile übernehmen; freie NURBS bleiben ohne.
- `_void_features` und gemeinsame Innenraumzusammenfassung: bekannte
  Originalträger auch auf Materialinseln erhalten. Die bestehende Tabelle
  darf bereits anerkannte native Flächen liefern, ohne nachträglich eine
  Bohrung daraus zu machen. AABB-Mitte des Innenraums ist kein Trägerzentrum.

Abbruch reicht bis in die neuen Schleifen und die native Zuordnung.
Keine neue Form, Reparatur oder Triangulierung außerhalb des ohnehin
zuständigen Solidwegs; native Ausgangsbytes bleiben unverändert.

## 5. Lokale Nummerierung und Auswahl

`app/core/perceive/local.py::_part` ändert nur die Vertexnummerierung des
privaten Ausschnitts. Die Reihenfolge seiner Dreiecke entspricht `indices`.
`_recognise_region` bildet heute `Feature.face_indices` über
`indices[list(feature.face_indices)]` zurück. **Jeden SurfacePatch mit genau
derselben Abbildung nachführen**, vorher auch negative, boolesche, gebrochene
und außerhalb liegende Indizes zurückweisen. Trägerkoordinaten bleiben im
Weltbezug; der Ausschnitt verschiebt seine Eckpunkte nicht.

Danach gelten die vorhandenen Abschlussprüfungen: abgeschnittene Rundung,
fremde Kammer, unvollständige Innenraumhülle und über den Radius fortgesetzte
Merkmale werden nicht mit einer scheinbar vollständigen Karte veröffentlicht.
`unfinished` ist Diagnose, keine zusätzliche Trägersammlung des Szenenobjekts.

Die dortige vollständige `detect_voids(mesh)`-Auskunft besitzt bereits
globale Indizes: **nicht ein zweites Mal abbilden**. Vor dem Entfernen
überdeckter lokaler Rund-/Ebenenmerkmale die oben beschriebene gemeinsame
Innenraumübernahme benutzen. Inseln zählen zur vollständigen Hülle.

`_numbered` wählt bei identischem `(kind, sortierte Dreiecke)` bereits das
vollständige Ergebnis mit kleinerem Suchradius. Dessen ganze Trägerauskunft
erhalten, keine Fits mehrerer Suchläufe mitteln. `features_in_region`,
`detect_known`, Rollenänderung und `local_search_radius` brauchen darüber
hinaus keine neue Geometrie. Der bestehende zusätzliche Zylinderaufruf zur
Durchgangsentscheidung ersetzt keine bereits veröffentlichten Fitmaße und
ist kein Anlass für einen weiteren Trägerfit.

## 6. Transformation, neue Topologie und erzeugte Namen

| Datei/Funktion | Nötiger Anschluss |
|---|---|
| `perceive/matching.py::moved_features`, `transformed_features` | Einen gemeinsamen reinen Trägertransform verwenden und pro öffentlichem Weg genau einmal anwenden. `transformed_features` darf die bereits bewegten Patchorte/-radien nicht nochmals bewegen oder skalieren. |
| `matching.apply_mapping`, `inherit_originators` | Das **neue** geometrische Ergebnis liefert Träger und Indizes; alter Name/Erzeuger wird wie bisher über `replace` erhalten. Keine alten Patches aus `previous` an neue Dreiecke hängen. Das gerichtete Kegelmodell folgt nicht der richtungslosen semantischen Achsnormalisierung von Loch/Slot. |
| `geom/transform.py::moved_object` | Beim Mesh bleibt die Dreiecksreihenfolge erhalten. Beim Solid zusätzlich jeden Patch über `faces_of_triangles` → vollständige alte native Fläche → `face_map` → neue `triangles_of_face` abbilden. Die bereits bestehende Vollständigkeitsprüfung des Gesamtfeatures allein beweist nicht die Vollständigkeit jedes Teilpatches. |
| `scene/evaluate.py::_carried_along`, `_inherited_features` | Nur wirklich unverändert mitgetragene Merkmale bewegen; bereits im Ergebnisraum veröffentlichte Patches nicht ein zweites Mal transformieren. |
| `scene/evaluate.py::_with_features`, `visible_faces`-Übernahme | Bei eindeutiger Zuordnung eines erzeugten Namens zur neuen Erkennung **deren aktuelle Patches zusammen mit deren Dreiecken** übernehmen, bevor der technische Doppelname entfernt wird. Deklarierte Parametervorgaben bleiben bestehen, sind aber nicht die Trägerquelle. |

Ein nach einer Topologieänderung nicht wiedererkanntes deklariertes Merkmal
darf seinen Namen behalten, aber keine alte Trägerzuordnung zur neuen Haut.
Beim vorhandenen `blind`/`recognised=False`-Zweig daher alte Patches leeren,
sofern keine ausdrücklich belegte geometrische Weitergabe vorliegt. Eine
gleiche Dreieckzahl oder unveränderte semantische ID ist kein solcher Beleg.

Formerhaltung am **einzelnen Träger** prüfen, nicht am semantischen
`Feature.kind="fillet"/"slot"/"void"` raten:

- Starre Abbildung einschließlich Spiegelung sowie gleichförmige Skalierung
  bewahren alle fünf Arten. Radien skalieren mit positivem Längenfaktor;
  Punkte und gerichtete Kegelnappen folgen der wirklichen linearen Abbildung.
- Ebenen folgen jeder invertierbaren affinen Abbildung: Punkt gewöhnlich,
  Normale invers-transponiert.
- Der vorhandene Kreis-Erhaltungsnachweis in `transformed_features` für
  Loch/Zapfen liefert eine wiederverwendbare ausreichende Prüfung für
  Zylinder: gleiche radiale Skalen und Orthogonalität zur abgebildeten Achse.
  Dieselbe nachgewiesene axialsymmetrische Abbildung erhält einen Kreiskegel;
  seine Tangente des Halbwinkels skaliert radial/axial, seine Spitze direkt.
- Kugel/Torus außerhalb einer Ähnlichkeitsabbildung sowie nicht belegte
  Zylinder-/Kegelabbildungen verwerfen. Ein ellipsenförmiger Mantel bekommt
  keinen alten Kreisradius. Keine neue allgemeine Quadrikerkennung in P1.6.

Bei nativer Retessellierung ist eine echte Teilmenge einer Originalfläche
ohne zusätzlichen Nachweis nicht übertragbar. Den betreffenden Patch
verwerfen, nicht auf die ganze Fläche aufblasen oder nach Dreiecknummer
übernehmen. Der bestehende Operationsfehler für eine unvollständige
semantische Flächenauswahl bleibt unverändert. Qualitäten und STEP-Neuimport
publizieren wie bisher neu an der tatsächlichen Tessellation.

Zusätzlich durch die vollständige Suche nach `face_indices=` gefunden:

- `geom/prepare_ops.py::_place_oriented_feature`: Beim neu platzierten Kopieren einer Höhlung wird
  `face_indices=()` gesetzt. Dort auch alte Patchindizes leeren; der
  anschließende reguläre Erkennungsweg weist die neue Haut zu. Reine
  Arbeitsfeatures für Randkonturen dürfen keine neue Kartenauskunft erfinden.
  Werden vorhandene Bodenebenen in `_bore_floor` vereinigt, die ursprünglichen
  Ebenenpatches der Teile mitnehmen, statt nur `parts[0]` zu verbreitern.
- `organizer/build.py::_patch` und `build_organizer`: tatsächliche planare
  Dreiecke werden in einer vorgegebenen Ebene ausgewählt. Den gemeinsamen
  Ebenennachweis verwenden und bei der Bodenübernahme neben den Patchindizes
  auch das Trägerdatum übernehmen.
- `knowledge/parts/profile_clamps.py::_features`,
  `knowledge/parts/seals.py::_surface` für `kind="face"`,
  `geom/seal_ops.py::_named_floor`: bereits wirkliche ebene End-/Nutflächen
  auswählen; denselben kleinen Punkt-/Normalennachweis verwenden. Allgemeine
  `curved_face`-Sitze und reine Bausteindeklarationen bleiben ohne Träger.
- `brep/ops.py::thread_exact` und `perceive/helix.py`: Gewindemantel,
  Umfangsmaße und Wendelindizes begründen keinen Kreis-/Kegelträger. Keine
  pauschale Befüllung aller `Feature(...)`-Konstruktoren nach Artetikett.

## 7. Speicher-, Index- und Abbruchbudgets

Vorhandene Grenzen nicht erhöhen und keine Laufzeitbehauptung daraus machen:

| Vorhandener Ort | Aktuelle Grenze | Ergänzung |
|---|---|---|
| `local.FEATURE_LIMIT_TRIANGLES` | 1.000.000 Originaldreiecke für globale Erkennung | unverändert; die Karte startet deshalb keine Vollerkennung |
| `local.LOCAL_FACE_LIMIT` | 50.000 lokale Fitdreiecke | Patchzuordnung höchstens an diesen bereits ausgewählten Dreiecken; keine Ausweitung des Suchgebiets |
| `local.SCAN_BLOCK` | 65.536 Dreiecke | globale Auswahl-/Validierungsläufe weiter blockweise abbrechbar |
| `features.FIT_SCAN_BLOCK` | 16.384 | für nötige Eckentests/Bereichszuordnung vorhandenes Arbeitsblockmuster übernehmen |
| `features.CACHE_LIMIT`, `CACHE_INDEX_LIMIT` | 256 Einträge und 12.000.000 gespeicherte Featureindizes | `_CACHE_INDICES` zusätzlich mit gespeicherten Patchindizes belasten; Grenzen unverändert |
| `scene.evaluate.FEATURE_LIMIT_COUNT` | 1.000 semantische Merkmale für Zuordnung | Patches sind keine neuen Matchobjekte und vergrößern die Zuordnungsmatrix nicht |
| `scene.cache.ResultCache` | 20.000.000 Dreiecke als Kostengrenze | aktuelle `CachedResult.cost` zählt nur Körper/Höhlung, **keine Merkmalsindizes**; zusätzlichen Patchspeicher dort konservativ mitbelasten oder eine vorhandene Eintragskostenrechnung entsprechend präzisieren |
| `scene.cache.DiskCache` | 2 GiB Ablagebudget | zusätzlicher JSON-Inhalt zählt über den bestehenden Bytehaushalt; dies ist kein Decoder-Allokationsbudget |

Ein primitiv erkannter Patch kann genau dasselbe unveränderliche Indextupel
wie sein Feature referenzieren. Zusammensetzungen halten kleine Tupel pro
wirklichem Teilträger; keine zweite Kopie von Eckpunkten/Normalen. Für eine
einfache konservative Kostenzählung sind Featurelänge plus Summe aller
Patchlängen ausreichend, auch wenn ein Tupel physisch geteilt wird. Innerhalb
eines Features sollen gültig zugewiesene Teilpatches disjunkt sein; bekannte
Konflikte nicht durch wiederholte Kopien vergrößern.

Kein Feld der Form `Anzahl_Patches × Anzahl_Körperdreiecke`, kein vollständiger
Körperdurchlauf pro Langlochbogen. Vorhandene Patch-/Flankenauswahl wiederverwenden,
Koordinaten nur blockweise daraus lesen. Ein globales Besitzer-/Konfliktfeld
je Karte ist Sache des vorhandenen Kartenrechners, nicht jedes Herstellers.

`scene/cache.py::_feature_to_data/_feature_from_data` serialisiert die fünf
Artvarianten ausdrücklich, nur endliche Zahlen und ganze Indizes. Vor einer
zusätzlichen NumPy-Allokation Anzahl, Indexbereich und Zugehörigkeit zum
Feature prüfen; ungültiger Cache führt zur vorhandenen Neuberechnung, nicht
zu einem Teilträger mit Ersatzachse. Dreiecksanzahl kommt vom ohnehin
geladenen Cachekörper, nicht von einer zweiten Tessellierung. Die inneren
Vektoren beim Lesen wieder in denselben unveränderlichen Tupeltyp bringen:
`evaluate._inherited_features` vergleicht alle Featurefelder, und eine
JSON-Liste im neuen Feld würde eine sonst unveränderte Weitergabe verdecken.
Cacheversion ist im gelesenen Stand 18;
Root erhöht die dann aktuelle Version. Keine Projektformatmigration allein
für diese abgeleiteten Daten und kein paralleler Trägercache.

Neue Schleifen prüfen den vorhandenen Abbruch vor Beginn und zwischen
Arbeitsblöcken; `OperationCancelled` unverändert durchreichen. Weder halb
zugeordnete Features noch abgebrochene Cacheeinträge veröffentlichen.

## 8. Kleiner vollständiger Umsetzungsschnitt und Abnahme

1. Root legt Datensatzfelder, Quellen und Validierung in `types.py` fest.
   Zwei gemeinsame Datenoperationen genügen: Patchzuordnung beschneiden/
   neu indizieren und einen bewiesenen Träger transformieren. Kein neues
   Erkennungsframework. Rechenhelfer bleiben unter `perceive`, die native
   Beschreibung unter `brep`; `types.py` importiert keinen Geometriekern.
2. Mesh-/Slothersteller sowie native `_describe` und die semantischen
   Zusammenfassungen anschließen; danach lokale Rückabbildung.
3. Matching, native Retessellierung, erzeugte Namen und Cache anschließen.
   Die aufgeführten tatsächlichen Ebenenhersteller benutzen denselben
   Ebenennachweis; reine Vorgabehersteller bleiben bewusst leer.
4. Erst danach liest der P1.6-Kartenrechner ausschließlich diese Daten.

Enge fachliche Gegenproben vor dem späteren Gesamttor:

- Echte Erkennung aller vier Rundarten und Ebene; gespeicherte Trägerzahlen
  stimmen mit **der tatsächlich zurückgegebenen Fitlösung** überein.
  Anschließend die Fitter/Recognizer sperren: Kartenlesen ruft sie nicht auf.
- Langloch mit zwei Bogenradien, Seitenflächen und angehängter Kegelfase:
  Einzelträger bleiben verschieden, Gesamtmaße unverändert. Direkter Slot,
  Stadionrückfall und offener Slot einschließlich neu hinzugenommener
  Bogenfacetten sind getrennte Wege. Nahtüberspannende Dreiecke bleiben unbekannt.
- Native Zylinderverrundung und Kugel-Eckverrundung, deren Auswahlmitte vom
  Trägerzentrum abweicht; derselbe Körper in draft/fine und nach STEP-Laden.
- Innenraum mit Kugelinsel und zwei getrennten Kammern; nur Originalhaut
  und richtige Inselanteile erhalten, keine Phantombohrung wiederbeleben.
- Lokaler Ausschnitt mit geänderter Vertexnummerierung, Rückabbildung auf
  nicht zusammenhängende globale Dreiecksnummern, Radius-/fremde-Kammer-Gegenfälle.
- Benannter Baustein: neu erkannter technischer Doppelname verschwindet,
  seine aktuellen Träger bleiben am benannten Merkmal. Ohne tatsächlichen
  Nachweis bleibt die Deklaration unbekannt.
- Translation/Rotation/Spiegelung/einheitliche Skalierung genau einmal;
  erhaltene affine Ebene und axialsymmetrischer Zylinder/Kegel; elliptische
  Verzerrung entwertet Rundträger. Native Retessellierung ordnet über Faces,
  niemals über alte Dreiecknummern oder Auswahlmittelpunkte zu.
- Warmer/kalter Ergebnis- und Erkennungscache, Speichern/Öffnen und Undo/Redo;
  dieselben Träger und Quellen, richtige Originalarrays. Ungültige Indizes,
  NaN/Inf, Nullachsen, widersprüchliche Überdeckung, Abbruch und bewusst
  kleines Indexbudget werden funktional geprüft, ohne Zeitgrenzen.

Passende bestehende Testfamilien: `test_round_surface_measurements.py`,
`test_cylinder_facets.py`, `test_slot_features.py`,
`test_geometry_review_regressions.py`, `test_brep_surfaces.py`,
`test_brep_canonical_surfaces.py`, `test_brep_voids.py`,
`test_local_detection.py`, `test_matching.py`, `test_evaluation.py` und
`test_cache.py`; dazu ein kleiner reiner Trägervertragstest. Keine Fensterdatei
oder Leistungsprüfung aus diesem Vorbereitungs- oder Entwicklungsschnitt.

Offen zur Zuteilung bleibt der zentrale Datensatz-/Transform-/Cachevertrag.
Die konkrete Extremwertrechnung samt Zahlenbereich/Zeugenpunkt sowie UI-
Anschluss gehören zu den anderen P1.6-Teilen, nicht in die Fitveröffentlichung.
