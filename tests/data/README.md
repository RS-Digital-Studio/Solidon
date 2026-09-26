# Referenzkorpus

Feste Eingangsdaten für die Abnahmekriterien (Bauplan §34). Ohne festen
Datensatz sind sie nicht prüfbar.

**Regeln:** ausschließlich selbst erzeugte Geometrie oder eindeutig frei
lizenzierte Modelle — der Korpus wird mit veröffentlicht. Jede Datei bekommt
hier eine Zeile: was sie enthält, welche Kennzahlen erwartet werden, welcher
Test sie benutzt. Neue Fehlerbilder aus der Praxis werden als Datei
aufgenommen, nicht als Sonderfall im Code.

---

## Projektdateien

| Datei | Inhalt | Erwartung | Test |
|---|---|---|---|
| `projects/flat_lid_v19.json` | Eigene synthetische Vorlage im historischen Format 19: offene Schachtel 60 × 40 × 30 mm, Wand 3 mm, flacher Deckel mit Parameter `collar=0`, noch ohne Passung | Als Projektcontainer öffnen: Migration auf 20 ergänzt bedingte Passung; Parameterwechsel auf 4 mm aktiviert sie, Save/Load und Undo/Redo erhalten die Zuordnung | `test_lid_flow.py` |
| `projects/example_v1.p3d` | Format 1 mit Parametern, Ausdruck, Passung, Quelle mit Lizenz, Agenten-Transaktion, Bericht und Vorschaubild | öffnet, zwei Ops (`rename_object`, `duplicate_object`), `half` trägt `=@width/2`, Passung trägt `auto:petg` | `test_project.py::test_the_checked_in_example_still_opens` |

Je Formatversion bleibt eine Beispieldatei liegen (§16.2). Sie wird nie
nachträglich verändert — sie ist der Beweis, dass die Migrationskette
funktioniert.

Neu erzeugen (nur bei einer neuen Formatversion, die alte Datei bleibt):

```
python -c "from app.core.bootstrap import load_operations; load_operations(); from tests.test_project import build_example_project; from app.core.scene.project import save; from pathlib import Path; save(build_example_project(), Path('tests/data/projects/example_v2.p3d'))"
```

## Gewinde (STEP)

`threads/` erzeugt `make_thread_corpus.py` — aus Konstruktionsmaßen, als
STEP, ohne Erzeugerauskunft im Körper. Die Sollwerte stehen in
`test_thread_import.py`; Toleranzen: Teilung 1e-4, Radien 1e-3, Achse 1e-6.
Die drei Bolzen entstehen seit RM-195 genäht (`profiles.threaded_rod` über
`helical_thread`: je Umlauf zwei Flanken und ein Fußstreifen, 41 Flächen am
M6), die zwei Sweep-Körper weiter mit der Fuzzy-Vereinigung des Skripts.

| Datei | Inhalt | Erwartung | Test |
|---|---|---|---|
| `threads/m6_rechts.step` | `profiles.threaded_rod(6, 1, 12)` | rechts, außen, p 1, L 1, n 1, Ø 6, Tiefe 0,6134, Länge 12, Achse z; Basis aller Ableitungen | `test_thread_import.py` |
| `threads/m10_rechts.step` | `threaded_rod(10, 1.5, 20)` | p 1,5, Ø 10, Tiefe 0,9201, Länge 20 | `test_thread_import.py` |
| `threads/m8_innen.step` | Block 20 × 20 × 10 minus `threaded_rod(8.2, 1.25, 10)` | innen, p 1,25, Nenn-Ø 8,2 (der Grund-Ø), Tiefe 0,7668, Länge 10 | `test_thread_import.py` |
| `threads/zweigaengig.step` | Kern Ø 6,92 plus zwei Helix-Gänge, Vorschub 2 | n 2, L 2, p 1, Ø 8, Tiefe 0,54, Länge 12 | `test_thread_import.py` |
| `threads/gegen_naht.step` | Zylinder Ø 6,02 mit einem 0,02 mm dünnen Gang | kein Gewinde: Gangtiefe außerhalb `GROOVE_RANGE` | `test_thread_import.py` |

```
.venv\Scripts\python.exe tests/data/make_thread_corpus.py            # alle fünf
.venv\Scripts\python.exe tests/data/make_thread_corpus.py m6_rechts  # einen
.venv\Scripts\python.exe tests/data/make_thread_corpus.py --check    # Datei gegen Erzeuger
```

`--check` baut jeden Körper neu und vergleicht Flächenzahl, Volumen und
Oberfläche mit der Datei (auf 1e-6): Am 20.09.2026 lagen Datei und Erzeuger
an M10 um 0,09 mm³ auseinander, weil der Erzeuger nach dem Korpus noch
viermal geändert wurde. `test_thread_import.py::test_the_corpus_matches_its_generator`
fährt den Vergleich je Lauf für die drei Bolzen (je unter zwei Sekunden); die
zwei Sweep-Körper prüft der Aufruf von Hand vor einem Release.

## Geometrie

Die STL-Dateien erzeugt `make_corpus.py`, die analytischen
`recognition_*.npz` erzeugt `make_recognition_corpus.py` — selbst erzeugte
Geometrie, keine fremden Lizenzen. Die NPZ enthalten ausschließlich Zahlenfelder;
sie sind keine Kopien der privat geprüften Kundendateien.
Neu erzeugen nur, wenn eine Datei sich ändern muss:

```
python tests/data/make_corpus.py
```

| Datei | Inhalt | Erwartung | Test |
|---|---|---|---|
| `local_detection.json` | Eigene analytische Beschreibung eines Zylinders Ø200 × 20 mm mit Sackbohrung Ø6, Tiefe 5 mm; dichte Variante mit 1.054.720 Dreiecken | Vollständige Bohrungswand mit 2048 Originaldreiecken, echter Blindboden; begrenzte Suchräume, Skalierung, gespeicherte Erkennung plus Änderung, warmes und kaltes Replay sowie Undo/Redo behalten Maße und Zuordnung | `test_local_detection.py` |
| `repair_features.json` | Eigener Würfel 100 × 100 × 100 mm mit separatem Zylinder Ø4 × 3 mm bei x=70; reguläre Merkmalsänderung auf Ø3 vor der Reparatur | Kleine Teile entfernen lässt einen Würfel mit 1.000.000 mm³ und sechs gültigen Flächen zurück; der entfernte erzeugte Zapfen bleibt auch bei Cache, Wiederöffnung und Undo/Redo verschwunden beziehungsweise wiederherstellbar | `test_repair_features.py` |
| `meshes/recognition_spice_base.npz` | Eigener Ring Ø40/32,8 × 3,4 mm mit drei radialen Mulden R1,1 | Keine Stadionöffnung; Kreisfit bleibt bei Verschiebung um 100 Millionen Millimeter Ø32,8; zwölf lokale Instanzen behalten ihre Merkmalsflächen | `test_recognition_regressions.py` |
| `meshes/recognition_waterfall.npz` | Eigene Wand 60 × 12 × 30 mm mit unterer Lippe 60 × 28 × 3 mm | Die Außenwand bei y=−6 bleibt außen, obwohl die Lippe weiter vorn liegt | `test_recognition_regressions.py` |
| `meshes/recognition_bayonet_lid.npz` | Eigene Scheibe Ø80 × 3 mm mit drei Quadern 6 × 3,8 mm auf der Oberseite | Drei ebene Kontaktflächen à 22,8 mm² bei z=3,5 trotz großer Scheibe | `test_recognition_regressions.py` |
| `meshes/recognition_bayonet_cage.npz` | Eigene Schachtel 80 × 80 × 20 mm mit 4-mm-Wänden und drei 5-mm-Tunneln | Je drei Böden und Dächer à 20 mm² bei z=8/12 bleiben auswählbar | `test_recognition_regressions.py` |
| `meshes/recognition_short_thread.npz` | Eigene geschlossene Radialwendeln: außen Ø34 über vier Windungen, innen Ø34,9 über drei; Steigung 3,5 mm, Gangtiefe 1,4 mm; beide Netze in getrennten Zahlenfeldern | Je ein richtig gerichtetes Gewinde mit gemessener Steigung und Durchmesser, auch schräg gedreht und verschoben | `test_recognition_regressions.py` |
| `meshes/cube_clean.stl` | Würfel 20 mm, in Millimeter gespeichert | 12 Dreiecke, roh 36 Punkte, nach dem Verschweißen 8 Punkte und wasserdicht, Volumen 8000 mm³; Einheit **eindeutig mm**, keine Rückfrage | `test_ingest.py` |
| `meshes/dense_cylinder.stl` | Zylinder Ø 5 × 40 mm mit 360 Mantelsegmenten und dicht triangulierten Kappen | 1440 Dreiecke, wasserdicht, eine Komponente; „Dreiecke verringern“ erreicht aus 1152 als Ziel ein geschlossenes Ergebnis innerhalb der vorhandenen Abweichungsgrenze, auch wenn der erste Vereinfacher keine einzige Kante zusammenzieht | `test_subdivision.py` |
| `meshes/bracket_inch.stl` | Platte 4 × 2 × 0,25 **Zoll** | Einheit **mehrdeutig** (cm/in) → Rückfrage; mit `in` → 101,6 × 50,8 × 6,35 mm | `test_ingest.py` |
| `meshes/plate_cm.stl` | Platte 8 × 5 × 0,5 **Zentimeter** | Einheit **mehrdeutig** (cm/in) → Rückfrage; mit `cm` → 80 × 50 × 5 mm | `test_ingest.py` |
| `meshes/plate_holes.stl` | Platte 80 × 50 × 8 mm mit vier Bohrungen Ø 5,2 mm | Schnitt bleibt geschlossen trotz Löchern; ab P3 Feature-Erkennung | `test_section.py` |
| `meshes/plate_coarse_slots.stl` | Eigene Platte 70 × 24 × 2 mm mit zwei Langlöchern, Breite 3,8 mm, Länge 7,6 und 24,8 mm; acht Segmente je Halbkreis | Zwei durchgehende Langlöcher mit vollständiger Wandzuordnung, auch gedreht und verschoben; keine zusätzlichen Hohlkehlen an den Öffnungen | `test_slot_features.py::test_coarse_slot_walls_keep_their_whole_opening` |
| `meshes/plate_chamfered_mouths.stl` | Eigene Platte 60 × 40 × 8 mm (z −4 bis 4, mit manifold3d gebaut, 64 Segmente je Kreis): Sackloch Ø 9 von unten bei (−15 | 0), 6 mm tief, mit 0,6-mm-Fase an der Mündung; durchgehendes Langloch Breite 6, Länge 18 bei (12 | 0) mit 0,8-mm-Fasen oben und unten | Die Mündung hinter der Fase findet ihre Trägerfläche (`placement.seat_of`): Unterseite beim Sackloch, Oberseite beim Langloch — nicht die Oberseite über dem Sacklochboden, die dort keine Öffnung hat; die Mitte bleibt die gemessene | `test_surface_placement.py::test_a_chamfered_mouth_still_finds_its_carrier_face` |
| `meshes/open_cylinder_clip.stl` | Eigener offener Clip: Innenradius 12 mm, Außenradius 16 mm, Höhe 17 mm, Bogen 184° mit 72 Segmenten | Innenradius ändern, verkleinern und erneut vergrößern; Außenradius und Höhe bleiben fest, ein geschlossener Körper | `test_radial_rounding.py`, `test_cylinder_measurements.py` |
| `meshes/open_cylinder_clip_cap_nodes.stl` | Derselbe Clip mit zusätzlichen Innenknoten in beiden ebenen Deckeln | Radiusänderung trianguliert ungültig gewordene Deckeldiagonalen neu; Randebenen, Volumen und ein geschlossener Körper bleiben belegt | `test_radial_rounding.py::test_radial_changes_retriangulate_the_planar_caps_when_needed` |
| `meshes/plate_holes_twin.stl` | Platte mit zwei gleichen Bohrungen 8 mm auseinander | ab P3: wird als **mehrdeutig** gemeldet statt geraten (§21.2) | noch offen |
| `meshes/plate_countersunk.stl` | Platte 60 × 40 × 8 mm, eine Bohrung Ø 5,2 mm mit 90°-Senkung auf Ø 10 mm | die Bohrung wird erkannt, obwohl der Kegel an ihrer Wand hängt (Ø 5,19, Tiefe 5,6 mm — die des Zylinders, nicht der Platte); vor dem 22.08.2026 kam **nichts** heraus, weil Kegel- und Bohrungswand ein Fleck waren | `test_features.py` |
| `meshes/plate_countersunk_blind.stl` | dieselbe Platte, aber die Bohrung endet **vor** der Unterseite: Ø 5,2 mm auf 6 mm Tiefe, dieselbe 90°-Senkung auf Ø 10 mm | die Gegenprobe zur Datei darüber — Zylinder 3,6 mm **plus** Senkung 2,4 mm sind 6 von 8 mm, das Loch ist also **nicht** durchgehend. Ohne sie wäre jede Reparatur grün, die „Senkung dran, also geht es durch" sagt | `test_features.py` |
| `meshes/sphere_socket.stl` | Block 40 × 40 × 15 mm mit eingefräster Kalotte R 8 mm | die Kugel als **Pfanne** (§41) — Ø 15,94 (die Icosphere ist einbeschrieben), Mittelpunkt auf z = 7,5 und damit auf der Oberfläche, `recess` wahr, Rückstand 0,0003. Vor dem 22.08.2026 kamen hier nur die sechs Blockflächen heraus | `test_features.py` |
| `meshes/shallow_sphere_cap_icosphere.stl`, `meshes/shallow_sphere_cap_uv.stl` | echte kreisrunde 5°-Kalotte R 80 mm, einmal als Icosphere und einmal als UV-Gitter | bleibt bei verschiedener Triangulierung, starrer Transformation und Skalierung eine bestimmte Kugelfläche; Radius etwa 80 mm | `test_sphere_fit_quality.py` |
| `meshes/indeterminate_sphere_cap.stl` | kreisrunde 2°-Kalotte R 80 mm, nur 0,049 mm hoch | kein sicher lokalisiertes Kugelmerkmal: Die zentrierte Normalenauskunft verstärkt Eingangsabweichungen um den Faktor 6615 | `test_sphere_fit_quality.py` |
| `meshes/ambiguous_sphere_ribbon.stl` | schmaler Ausschnitt einer exakten Kugel R 80 mm, 40° lang und 4° breit | kein sicher bearbeitbares Kugelmerkmal: Nur eine Krümmungsrichtung ist ausreichend belegt | `test_sphere_fit_quality.py` |
| `meshes/near_sphere_ellipsoid.stl` | Icosphere R 8 mm, in einer Achse um 4 % gestreckt | keine Kugel; der auf den Radius bezogene Rückstand von 0,0101 täuscht nur deshalb Güte vor, weil er die örtliche Ausdehnung des Flecks nicht berücksichtigt | `test_sphere_fit_quality.py` |
| `meshes/torus_ring.stl` | Torus, Ringradius 20 mm, Röhrenradius 5 mm | `diameter` (Ring) Ø 40, `tube_diameter` Ø 10, Achse z, Rückstand 0,005. Die Einpassung liest beide Radien aus den Rändern des Flecks und setzt damit einen **ganzen** Ring voraus — ein Torusstück, wie eine Verrundung es ist, misst sie noch nicht | `test_features.py` |
| `meshes/post_with_fillet.stl` | Säule Ø 12 auf einer Platte, der Fuß mit R 3 ausgerundet | das Alltagsteil, an dem bis zum 22.08.2026 **nichts** erkannt wurde: Eine Verrundung schließt tangential an, also trennt kein Knick sie ab, und Mantel und Kehle lagen in einem Fleck. Heraus kamen sieben ebene Flächen. Heute Zapfen Ø 12,00 und Torus mit Ring Ø 17,99 / Röhre Ø 5,99; die Krümmungskarte zeigt 3,0 mm und 6,0 nebeneinander | `test_features.py`, `test_maps.py`, `test_cylinder_measurements.py` |
| `meshes/block_with_rounded_edge.stl` | Quader 40 × 30 × 20 mm, **eine** Kante mit R 3 ausgerundet | bis zum 23.08.2026 ein `pin` mit **Ø 28,92** — fast so breit wie das Teil. Zwei ebene Facetten von 1110 und 510 mm² galten als gekrümmt, weil sie die Rundung berühren, und hängten sich ihrem Fleck an; die Kreiseinpassung gewichtet quadratisch. Heute ein **`fillet`** mit R 2,999 und sechs Flächen — kein Zapfen mehr: §14 nennt einen Zapfen das, womit man eine Bohrung paart, und mit einer Kantenverrundung paart niemand etwas. Volumen 23942 mm³ | `test_features.py` |
| `meshes/plate_chamfer_and_taper.stl` | Platte 50 × 30 × 10 mm: links Bohrung Ø 6 mit Fase auf Ø 9, rechts ein konischer Zapfen | die zwei Kegelarten, die dem Korpus fehlten — §21.1 nennt drei, vorhanden war nur die Senkung. Fase `recess` wahr Ø 9,00, Verjüngung `recess` falsch Ø 10,00. Die **Fase** legte zwei Fehler frei: Die Bohrungswand zerfiel in vier Flecken (vier Bohrungen für ein Loch), und der Zapfen daneben machte aus der 10 mm dicken Platte eine 25 mm dicke, worauf die Bohrung als Sackloch galt | `test_features.py` |
| `meshes/degenerate.stl` | Würfel plus Nullflächen-Dreieck, Nadel und Dublette | 15 Dreiecke roh, nach der Eingangsstufe weniger; Befund `ingest.degenerate_removed` | `test_ingest.py` |
| `meshes/broken_open.stl` | Würfel ohne drei Dreiecke | nicht wasserdicht, Befund `ingest.not_watertight` (Warnung) | `test_ingest.py` |
| `meshes/partially_open.stl` | unterteilter Würfel ohne Decke und mit einem fehlenden Bodendreieck | selbst erzeugt, keine fremde Lizenz; 19 offene Kanten vor der Reparatur, 16 danach — der Bericht nennt **3 von 19 geschlossen** und den Rest, statt Vollzug zu behaupten | `test_geometry_review.py`, `test_ui.py` |
| `meshes/two_components.stl` | Würfel plus winziges Bruchstück daneben | zwei Komponenten, Befunde `ingest.multiple_components` und `ingest.small_components`; **nichts wird gelöscht** | `test_ingest.py` |
| `meshes/clean_figure.stl` | eine Figur ohne Fehler: Rumpf, Kopf, zwei Arme, zwei Beine aus Grundformen vereinigt — derselbe Aufbau, den P16.11 dem Käfigeditor entgegenhält | geschlossen, ein Körper, Euler-Charakteristik 2; 738 Dreiecke, 58 x 18 x 82 mm, steht auf z = 0; mittlere Kantenlänge 2,8 mm — zum Formen vorher gleichmäßig vernetzen; seit dem 22.08.2026 wird der **Kopf** als Kugel erkannt (Ø 17,7 auf z = 73) | `test_sculpt.py` |
| `meshes/generated_figure.stl` | drei verschmolzene Kugeln mit den Fehlern eines Generators: fünf einzelne fehlende Dreiecke, ein Fünftel verdrehte Normalen, ein loser Splitter | nach der Kette aus `GENERATED_REPAIR` **geschlossen**, ein Körper; die Merkmalserkennung findet keine Flächen (alle unter `MIN_FACE_AREA`), seit dem 22.08.2026 aber **genau die drei Kugeln**, aus denen die Datei gebaut ist — Ø 19,9, Ø 11,9 und Ø 8,0, Rückstände unter 0,0005 | `test_examples.py`, `test_features.py` |
| `meshes/broken_selfint.stl` | zwei Würfel, die sich durchdringen, ohne verschnitten zu sein | 24 Dreiecke; die Rückfallkette löst es derzeit schon auf Stufe 1 — die Datei hält fest, dass das so bleibt | `test_corpus.py` |
| `meshes/crossing_and_apart.stl` | zwei Würfel zu 20 mm, die sich durchdringen, dazu ein dritter daneben | drei Teile, Befund `ingest.multiple_components` mit *Überschneidungen auflösen*; danach zwei Teile, 14 272 + 8 000 mm³, und der Satz über drei Teile fällt (KUNDE-13) | `test_repair.py` |
| `meshes/colored.3mf` | zwei Würfel in Slot 1 und 2, mit der eigenen 3MF-Hälfte geschrieben | zwei Materialgruppen „Rot" und „Schwarz", je Dreieck zugeordnet; Rundweg durch `threemf.read` | `test_corpus.py` |
| `projects/assembly_fit.p3d` | Platte mit 6-mm-Bohrung, Deckel mit 5,95-mm-Stift, dazu ein Passungspaar `auto:petg`; **gespeichert liegen beide Grundkörper auf z = 0 und durchdringen sich** — die Einbaulage auf der Stiftschulter stellt `test_corpus.py` als regulären Schritt her | roh meldet die Datei `fit.collision` (in PLA dazu `fit.mesh_uncertain`); in der Einbaulage hält die Passung mit PETG und meldet sich mit einem anderen Material — die Bohrung folgt dem Druckmaterial, die Toleranz dem, was im Paar steht | `test_corpus.py` |
| `meshes/oversized.stl` | 400 × 80 × 40 mm: zwei dicke Enden, schlanke Mitte | passt auf keinen Bauraum; der Auto Split findet die Trennebene in der Mitte (Querschnitt 1200 mm², eine Kontur) und macht daraus zwei wasserdichte Teile | `test_autosplit.py` |

`meshes/dense_1m.stl` (1,31 Mio. Dreiecke, Leistungsmessung nach §31) wird
**nicht eingecheckt** — 60 MB im Repository wären unverhältnismäßig. Der
Leistungstest erzeugt sie beim ersten Lauf; die Messwerte landen in
`tests/.performance.json` und bleiben lokal, weil sie von der Maschine abhängen.

Damit ist der Korpus aus §34 vollständig, bis auf `legacy_v1.p3d` — die
Altformate liegen unter `projects/example_v<N>.p3d`, eine Datei je
Formatversion von 1 bis zur vorletzten, dazu die Sonderfälle mit eigenem
Inhalt (`drilled_v6`, `split_v10`, `scad_v12`, `painted_v13`, `circle_v18`,
`generated_glb_v24`, `matching_answers_v26`, `sketch_v30` — Skizzen aus der
Zeit vor Ellipse und Kurvenbedingungen), und werden von
`test_project.py` durch die Migrationskette geschickt; eine neue
Formatversion bringt ihre Beispieldatei mit (AGENTS.md, Checkliste
Dateiformat).
