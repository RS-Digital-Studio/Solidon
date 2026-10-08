# `app/core/knowledge/parts/` — die Bausteinbibliothek

Geprüfte, parametrische Teile, die der Agent und der Nutzer zusammensetzen
(§24). Regeln: `.claude/rules/bausteine.md`; Schritte für einen neuen Baustein:
Checkliste in `AGENTS.md`, Skill `neuer-baustein`. Herleitungen:
`konzepte/begruendungen/karte-app-core-knowledge-parts.md`.

**Dieses Verzeichnis steht unter MIT** (`LICENSE` hier, der Grund aus §36 im
Paketdocstring). Wer hier Code hinzufügt, prüft, dass er unter MIT stehen darf.

## Die Karte

| Datei | Rolle |
|---|---|
| `fasteners.py` · `mechanics.py` · `mounting.py` · `structure.py` | Die Gruppen Verbindungen (Schrauben, Muttern, Senkungen), Mechanik (Scharniere, Gewinde), Halterungen, Struktur (versteifen, hindurchführen, anbinden); jede zählt ihre Bausteine im Docstring auf |
| `closures.py` · `rods.py` · `channels.py` · `panels.py` | Die Bausteine aus dem Dateiaudit (RM-184): Bajonett und Rastdrehscheibe als Paar je über `kind` (Hälften aus denselben Maßen, gemeinsamer Rahmen in `bayonet_frame`/`detent_frame`, Ringsektoren aus Ring und `wedge`); Steckhülse und Zwei- bis Vierwegeverbinder (`rod_connector`, Vorlage, Knoten eine halbe Wand größer als die Aufnahmen); Schlauchtülle (abtragender Durchgang durch die Trägerwand, die Tülle als `host_add`) und Kanalnaht (Hülse außen oder Einlage innen mit Rampe, die Einlage nennt ihre Verengung als Befund); Raumboden, Raumwand und Fensterscheibe als Nut-und-Feder-Platten (Vorlagen, Bezug in `panels.py`) |
| `holders.py` | Die Halter-Vorlage (RM-399): U-Form, rund, Gabel, Ablage (L/Z) — je Form ein Baustein, gemeinsame Rückwand mit Schlüsselloch (zwei, wo die Breite reicht, sonst eines mittig), Schraublaschen, Lochwand-Haken oder Klemme aus `keyhole`, `screw_hole` und `pegboard_hook` (`_assembled`) |
| `containers.py` | Organizer-Wanne, Teilungswand, Rand, separater Steckfuß; ebene Merkmalsflächen am Netz gezählt (`facets`), exakt als Integral (`native`, `brep.canonical.horizontal_area`); die Wanne rundet `shapes.rounded_box` |
| `profile_clamps.py` | Klemmschale und wechselbare Einlage mit gezeichneter Gegen- bzw. Sitzkontur; der Vierkörperweg liegt in `geom/profile_clamp_ops.py` |
| `seals.py` | Dichtnut und separate rechteckige/runde Dichtung aus einem Skizzenweg (`geom/seal.py`: `Section`, `round_cord`); ebene Flächen exakt (`native`) |
| `testbodies.py` | Prüfkörper der Kalibrierung (§28.3), Toleranzleiter als Verbund (`build.compound`) |
| `registry.py` | `register_part`, `PARTS`, `LIBRARY_VERSION`, `changed_since()` |
| `builtin.py` | Lädt die Gruppen einmal (`bootstrap.load_operations()` ruft `builtin.load()`); der Paketimport registriert nichts |
| `ops.py` | **Jeder Baustein wird zusätzlich eine Operation** (§24.1, §10) |
| `build.py` | Gemeinsamer Boden: Vereinigen, Abziehen, Schneiden, `threaded`, Verbund, `form_of` — je Kern |
| `shapes.py` | Kleine Formen; `building`/`building_exact` wählen den Kern, `mesh_only` benennt Netzstellen; `rounded_box` (Sehnen nach `MAX_FACET_SAG`, exakt vier Viertelkreise, Eckmitten aus `rounded_corners`) |
| `section.py` | Querschnitte mit zwei Auswertern: `manifold3d.CrossSection` fürs Netz und die Prüfungen, eine ebene exakte Fläche für die Geometrie |
| `exact.py` | Die exakten Zwillinge aus `shapes`/`build`: `Solid` mit demselben Rahmen, Vereinigung mit Körperzahlprüfung und Stufenleiter auf Kopien |
| `range_check.py` | Der Bereichstest in der Anwendung: Selbstdurchdringung über `geom.intersections`, Wandstärke über `geom.mesh.ray_hits_batch`, ohne VTK |
| `range_proof.py` | Der Bereichsnachweis: Abdruck je Baustein gegen `data/part_ranges.toml` (`tools/check_part_ranges.py`) |
| `preview.py` | Vorschaubilder — gerendert, nicht von Hand gepflegt |
| `scad.py` | Export als OpenSCAD-Quelltext; schreibt, führt nichts aus |
| `recipe.py` | Ein eigener Baustein als **Rezept**: Daten statt Programm (§24.5) |
| `shared.py` · `shared_texts.py` | Der geschlossene Prüfvertrag lokaler Bausteindateien (Form, Mengen, Ops, Payloads, `MAX_EXPOSED`) · seine übersetzbaren Prüfgründe |
| `part_file.py` | Import und Export lokaler Bausteindateien (`PartFileIO`) |
| `user.py` | Eigene Bausteine aus dem Nutzerverzeichnis |
| `check.py` | Was beim Öffnen eines Projekts zu sagen ist (§24.4) |

## Gebaut als Formbeschreibung — gerechnet je Kern

Ein Baustein sagt nur, **was** er ist; den Kern wählt der Aufrufer
(`shapes.building(kernel)`, Regel in `bausteine.md`). Drei Grenzen:

- **Wer ein Netz direkt anfasst, sagt es** (`shapes.mesh_only`). Am Netz
  rechnen noch die Erzeuger außer den Vorlagen (`create_*`, der Organizer in `organizer/build.py`,
  die Dichtung aus `geom/seal_ops.py`) und sagen es; die Paritätstabelle
  (`tests/test_exact_body_parity.py`, `KEEP` statt `MESH`) ist die Abnahme je
  Gruppe.
- **Ein Gewinde ist exakt ein genähter Körper**; der nackte Gang
  (`shapes.thread_body`) bleibt eine Netzform. Am Netz bekommen Kern und Gang
  je Umlauf `shapes.turn_segments` Sehnen (ein Vielfaches von `SEGMENTS`).
- **Der Senkkopf bleibt exakt ein Verbund** aus Kegel und Gang (tangential,
  vereinigt ungültig aus STEP); ein lösbares Teil liegt ohnehin als Verbund am
  Träger (`exact.compound`, Gegenstück zu `ops._concatenated_with_slots`).

## Stolperfallen

- `shapes.cylinder`, `box` und `moved` verschieben über `transform.moved`;
  `rounded_box` und `thread_body` verwenden die exakten Winkelfunktionen.
  Auch reine Verschiebungen über `trimesh` können BLAS aufrufen. Die
  Sehnenzahl der Ecke wird am tatsächlichen Pfeilmaß geprüft.

### Merkmale und Maße

- **Nutfedern** unterscheiden benannte Herstellerquerschnitte von älteren
  unbestätigten Größen. `ProfileSlot.taper_to_slot` verjüngt den Kopf über die
  volle Kammertiefe auf Halsbreite; eine kleinere Kopfhöhe schneidet dieselbe
  Form kürzer. Alte Größen bleiben maßgleich, die Projektmigration ergänzt
  ihre frühere Vorgabe bei fehlendem `size`. Passungsprüfungen verwenden
  unabhängige Herstellermaße und zusätzlich den Montageweg am STEP-Modell.

- **Vorgegebene Zahlen** tragen `build` ungerundet als `parameter`; gemessene
  Flächen und Mitten übergeben ihre Quelle (`face`), gemischt je Parameter;
  Umbenennen im Rezept behält die Quelle. Einen `SurfacePatch` bekommen ebene
  Anschluss- und Dichtflächen erst, wenn alle Dreiecksecken auf ihrer Ebene
  liegen; gerundete Kontaktbänder und Vorgabemaße behaupten keinen Träger.
- **Ein Gewinde hat jedes Maß**: eine Tabellengröße oder `fasteners.CUSTOM_SIZE`
  mit Durchmesser und Steigung (`thread_measure`, null ist
  `standards.regular_pitch`); an einer Bohrung ohne Tabellengröße wählt
  `custom_thread_for` das Maß, dessen Kernloch sie ist; eine Tabellengröße ab
  ihrem gedruckten Gangfuß, solange die Bohrung dem Gang die halbe Tiefe lässt
  (`units.THREAD_MIN_GRIP_SHARE`), und ein eigenes Maß innerhalb von
  `standards.THREAD_SIZE_REACH` neben einer Größe wird diese — dieselbe Grenze
  wie beim Gegenstück (`standards.thread_size_near`).
  Ohne tragenden Kern oder unter `FINEST_PITCH` lehnt es ab und erklärt es (`thread_problem`,
  `_thread_reason`); bohrt es seine Bohrung auf oder bleibt nach außen zu wenig
  Wand, sagt es das (`thread_at_hole` über `PartSpec.at_hole_check`, Strahlen
  am Träger in `_wall_around`, Mündung und Richtung aus `ops._mouth_frame`).
  Schraubenloch, Mutternfalle, Schraube und
  Mutter nehmen `CUSTOM_SIZE` mit Nenndurchmesser (`_screw_of`, `_nut_of`,
  `_washer_of`, Befund `parts.derived_size`), die Mutternfalle auch an einer
  Bohrung über der Tabelle (`custom_nut_for`); die Einpressbuchse nimmt
  Bohrung und Länge. Der Netzkern eines Gewindes überdeckt den Gang auch in
  der Sehnenmitte (`build._core_segments`), der Gang läuft über ganze Umläufe;
  ein Langloch hat Sehnen nach `MAX_FACET_SAG` (`shapes.slot_segments`).
- **`build.thread`** beschreibt rechtsgängig (`handedness="right"`, Winkel und
  Höhe wachsen gemeinsam); Innenwerkzeug, Schraube, Mutter ändern den Drehsinn
  nie, Spiegelungen führen ihn nach, ein Importgewinde bekommt keine Vorgabe;
  in `measure_sources` steht er als `parameter`.
- **Ein Baustein gibt seinem Wirt dessen Merkmale ohne die alten Dreiecke
  zurück** (`ops._merged_features`); ohne Partner in der neuen Erkennung steht
  ein Merkmal ohne Dreiecke im Baum, nie mit falschen.
- **Schraubenbohrung, Senkkegel und Kopfzone** sind getrennte Merkmale
  (`countersink_1` als `cone` mit Öffnungswinkel und Innenraummarke,
  `head_room_1` als Kopfzone); Kopfzylinder und Kegel teilen ihren ganzen
  Stirnrand, ohne Überstand (ein Ringsims trennte die Hohlraumkette).
- **Ein lösbares Teil** (`separate_from_host`) setzt `leaves_separate_parts`;
  über den Träger urteilt die Operation (`ops._host_split`), das Spiel zum
  Sitz baut der Baustein selbst (`fasteners.printed_screw`, `printed_nut`,
  `_printed_screw_countersink`). Schräg zur Fläche gesetzt öffnet ein
  abtragender Baustein bis über ihre Ebene (`ops._opened_to_the_face`), und
  eine erklärte Haltelippe prüft `ops._lip_on_a_slant`; die Regeln in
  `bausteine.md`.
- **Material**: `profiles.for_object` gibt beim Einsetzen das Material des
  Ziels, auch für `build_with_profile`; `grip_from_profile` kennzeichnet
  Übermaß, eine konstruktive Verengung misst gegen ihr Maß (Kabelclip).
  Unmögliches wird mit Vorschlag abgewiesen, Messwinkel nie still gekappt;
  Innen- und Außengewinde teilen den Flankenverlauf samt Spiel. Die
  Federwarnung nimmt `snap_arm_length` wie der Aufbau; eine Filmscharnierfolie
  ist dünner als ihre Flügel (`feasible` und Bauweg).
- **Die Spaltprüfung** nimmt alle Komponentenpaare und den echten
  Flächenabstand samt Kanteninnerem; der Körperaufbau bleibt vom
  Bereichsbericht getrennt.

### Gezeichnete Maße, Profilklemme, Einlage

- **`ops._built_part(..., parameters=...)`** ist der Bauweg für Operation und
  Platzierung: `kind="sketch"`-Maße werden in einer Wertkopie aufgelöst, bevor
  `PartFn` oder `build_with_profile` sie sehen (die Op gibt
  `ctx.scene.parameters`, `placement_tool`/`placement_tools` denselben
  Kontext); der Skizzentext bleibt, fehlender Kontext ist ein erklärter
  Ausdrucksfehler, nie ein Nullmaß.
- **Profilklemme und Einlage** verlangen eine gezeichnete Sitz- bzw.
  Gegenkontur und liefern genau `front` und `back`. Die Kontur ist ein
  zusammenhängender Querschnitt ohne Löcher, Versätze sind Normalabstände
  (`geom.contours`); montiert wird im gedrehten Teilungsrahmen — jeder Schnitt
  parallel zur Öffnung trifft genau ein Intervall. Schalen öffnen seitlich,
  Einlagen gehen axial von der Bundseite ein; Bund und hinterer Freiraum
  gehören zur Einlage. Die Schale sitzt bei null, der Bundfreiraum ist Lage und
  kommt als `lift` von `build_shell` und `seat_probes`, gesetzt vom Klemmenpaar
  in `geom/profile_clamp_ops.py`.
- **Aufnahmen** begrenzen Rand und Schalenwand; `play` liest das eigene
  Material, `grip_from_profile` bindet die Verengung der Einlage an ihr
  Pressmaß; ein einzelner Part nimmt kein zweites Material — nur der gemeinsame
  Erzeuger kennt beide.

### Rezepte und Dateien

- **Rezept** (Regel 13, `bausteine.md`): `recipe.draft` ist der Gegenweg zu
  `capture`, `Session.open_draft` merkt sich die Herkunft. Ein Ausschnitt trägt
  keine Auftragseinstellungen; Abhängigkeiten sammelt der Container transitiv,
  Namenskonflikte bekommen freie Namen, vorhandene Fassungen bleiben.
- **Format v2**: flache `dependencies` (v1 migriert, Quelldaten bleiben);
  höchstens 32 Beilagen und 64 expandierte Operationen, kreisfrei, jede durch
  denselben Prüfer; ein privates Register löst eingebettete Fassungen, ohne
  lokale zu ersetzen.
- **`PartFileIO`**, ohne Netz: Import und Export bauen das Rezept einmal ganz;
  Modellbytes reisen begrenzt, relativ, gegen SHA-256 geprüft; Unbekanntes,
  absolute oder übergeordnete Pfade und widersprüchliche Payloads werden
  abgewiesen. `ImportedOrigin` kommt aus Prüfsumme und UTC-Zeit, nie aus Pfad;
  `load_all()`/`replace()` stellen die fremde Quelle wieder her; ein
  gleichnamiger eigener Baustein wird nie still ersetzt. Ablehnungen nennen
  ihren Grund ohne fremde Kennungen oder Dateiinhalt.
- **Atomar**: erst ganz in eine Tempdatei des Zielordners, dann veröffentlicht
  (Import ohne Überschreiben, Ersetzen per Replace); Katalog und Register
  entstehen vorher isoliert, übernommen wird nur vorwärts; Tempreste räumt eine
  Namensraum-, Besitzer- und Altersgrenze. **Entfernen** (nur `recipe`,
  `imported`) geht über einen Quarantänenamen (nicht festgeschrieben
  zurückgelegt, sonst aufgeräumt), wiederhergestellt ohne Überschreiben; offene
  Dokumente bleiben unberührt.

### Bereichstest und Versionen

- **Der Bereichstest zählt das kartesische Produkt vor jedem Bau**
  (`range_check.corner_count`, über `MAX_CORNERS` eine Absage mit Anzahl);
  Stichproben ersetzen den Vertrag nicht, `recipe.capture` begrenzt die Felder
  (`shared.MAX_EXPOSED`), der Dialog zeigt die Prüfmenge. Jede Phase einer Ecke
  gehört in ihren Bericht; nur eine erklärte Ablehnung beim Bau ist ein
  Ausschluss, ein Prüffehler weder das noch ein Verlust des Berichts; Abbruch
  ist ein eigener Weg. Zyklische Speicherbereinigung nur im Hauptthread, nie an
  fremden Qt-Objekten.
- **Zwei Versionen, die leicht zu verwechseln sind**: `LIBRARY_VERSION`
  (`registry.py`) beschreibt die Bibliothek und steigt mit jeder Maßänderung;
  `parts_version` im Dokument hält fest, wogegen gebaut wurde. `check.py`
  vergleicht beim Öffnen. „`parts_version` erhöhen" in `AGENTS.md` meint die
  Konstante der Bibliothek. Die Wahl beim Öffnen (§24.4, Regel in
  `bausteine.md`): `recipe.for_container`, `adopt`, `KEEP_SAVED_PARTS`,
  `check.keep_saved`; Befunde nennen Katalogtitel (`_titles`).
- **Stände**: Rezepte bilden ihren Inhaltsabdruck, lokale `.py` beim Laden; die
  Operationen tragen ihn als `cache_version`, und das Auswerten liest nie eine
  neu geschriebene, noch nicht geladene Fassung.

### Ort, Tiefe und eigenständige Teile

- **Freie Platzierung** speichert `x/y/z` und `nx/ny/nz` (drei Nullen: alte
  `axis`; `at_feature` geht vor), Rahmen aus `sketch.planes.frame_of`;
  `placement_tool` liefert gedreht, eingesenkt, gespiegelt, mit dem Material
  des Ziels.
- **Randprüfung**: `ops._over_the_rim` nimmt in beiden Kernen
  `ctx.cancelled`; `ray_hits_batch` kann einen Teilstand liefern. Direkt
  danach folgt `raise_if_cancelled`, bevor daraus ein Befund wird. Der
  Werkzeugumriss enthält die Mündung samt Senkung und Fase, auch wenn nur
  Werkzeugkanten die Mündungsebene schneiden. Bei einem gewählten ebenen
  Träger zählt seine eigene Fläche; eine Wand hinter dem Rand deckt ihn nicht.
  Ein Lagevorschlag kommt nur nach Prüfung des vollständigen Werkzeugumrisses
  gegen das Flächenpolygon samt Aussparungen (`_rim_placement_suggestion`).
  Die Bohrung, in der ein Baustein sitzt, ermittelt `_seated_bore` einmal je
  Kern; Randprüfung (`bore=`, `_inside_the_bore`) und `_in_a_wider_bore` lesen
  sie (Regel in `bausteine.md`).
- **Namensräume**: Trägt ein eigener Baustein `nx`, `ny` oder `nz` als Maß,
  verschiebt `build_params` alle drei nach `surface_` (`normal_fields`);
  Ortsfelder kollidierender Rezeptmaße bekommen `placement_`
  (`placement_fields`); Rezeptmaße werden nie umbenannt. Stände vor 16 hebt
  `normalise_legacy_placement()` nach der Rezeptaufnahme über, samt Undo-Seiten
  und alter Ortsvorgabe; frische Dokumente nie. Jedes erzeugte Schema bekommt
  eigene Dataclass-Felder — ein geteiltes `Field` benennt sich beim nächsten
  Klassenbau um.
- **`depth_field`** sagt, welches Feld die Eindringtiefe ist (§18.5; warum der
  Name nicht reicht, im Docstring); wer ein auftragendes `depth` baut,
  deklariert es über `ParamSpec.subtractive_on` (`cuts`, `cuts_by_parameter`).
- **`standalone`** erzeugt zusätzlich `create_<name>` ohne Eingang
  (`creation_name()`), `insert_<name>` bleibt lesbar; Erzeuger übernehmen die
  freie Normale und sinken ohne Träger nicht ein. **`template`** (nur mit
  `standalone`) lässt den Erzeuger *Maße als Parameter anlegen* anbieten wie
  einen Grundkörper (`offers_naming`, Regel in `grenzen.md`) und baut ihn wie einen
  Grundkörper exakt, wo der Kern da ist (`ops._creates_exactly`). Die Toleranzleiter erklärt
  zwei Leisten, der Bereichstest prüft Teilezahl und Abstand.
- **`host_add`** ergänzt tragendes Material vor dem Schnitt, mit demselben
  Parametersatz und Rahmen in einer Operation; der Fertigungstest belegt den
  echten Trägeraufbau, der Solver nennt die tiefste Stufe. Die Katalogvorschau
  zeigt die geschnittene Geometrie; SCAD schreibt
  `<name>_host_add()`/`<name>_host_cut()` samt Folge.
