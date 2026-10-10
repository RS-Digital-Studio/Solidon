# Referenzkorpus

Feste Eingangsdaten für die Abnahmekriterien (Bauplan §34). Ohne festen
Datensatz sind sie nicht prüfbar.

**Regeln:** ausschließlich selbst erzeugte Geometrie oder eindeutig frei
lizenzierte Modelle — der Korpus wird mit veröffentlicht. Jede Datei bekommt
hier eine Zeile: was sie enthält, welche Kennzahlen erwartet werden, welcher
Test sie benutzt. Neue Fehlerbilder aus der Praxis werden als Datei
aufgenommen, nicht als Sonderfall im Code.

---

`profile_slot_motedis.json`: Eigene Querschnittsmessungen aus den verlinkten Hersteller-STEP-Dateien für Motedis 2020 B-Typ/Nut 6 und 3030 B-Typ/Nut 8; Steg 1,5/2,2 mm, Kammer 4,0/6,8 mm und lichte Breiten über der Tiefe. `test_parts.py` prüft die Nutfeder in beiden Kernen gegen diese unabhängigen Maße. Eine physische Passungsprobe ist damit nicht behauptet.

`comfyui/object_info.json`: ComfyUIs eigene Beschreibung (`/object_info`) aller Knoten, die `app/core/backends/data/image_to_mesh.json` und `text_to_image.json` ansprechen, samt ComfyUI-Version und Modul je Knoten — erzeugt mit `tools/comfy_node_info.py` im Python von ComfyUI, ohne Server und ohne Grafikkarte. Die Auswahllisten der Modelldateien zeigen den Bestand der erzeugenden Maschine und tragen nichts zur Prüfung bei. `test_mesh_backend.py` prüft beide Abläufe dagegen: jeder Eingang gesetzt, keiner unbekannt, Verbindungstypen, Auswahl und Grenzen, eingebaute Knoten.

## Projektdateien

| Datei | Inhalt | Erwartung | Test |
|---|---|---|---|
| `projects/flat_lid_v19.json` | Eigene synthetische Vorlage im historischen Format 19: offene Schachtel 60 × 40 × 30 mm, Wand 3 mm, flacher Deckel mit Parameter `collar=0`, noch ohne Passung | Als Projektcontainer öffnen: Migration auf 20 ergänzt bedingte Passung; Parameterwechsel auf 4 mm aktiviert sie, Save/Load und Undo/Redo erhalten die Zuordnung | `test_lid_flow.py` |
| `projects/example_v1.p3d` | Format 1 mit Parametern, Ausdruck, Passung, Quelle mit Lizenz, Agenten-Transaktion, Bericht und Vorschaubild | öffnet, zwei Ops (`rename_object`, `duplicate_object`), `half` trägt `=@width/2`, Passung trägt `auto:petg` | `test_project.py::test_the_checked_in_example_still_opens` |
| `projects/slender_arrangement_v42.p3d` | Historische Anordnung einer Platte 120 × 120 × 4 mm und einer Stange 8 × 8 × 122 mm, Format 42 | Migration und Undo behalten die alte Lage; neue Anordnung darf die Stange zur freien Mitte verschieben | `test_project.py` |
| `projects/example_v43.p3d` | Format 43 mit gespeicherter Wahl für die Mittellage schlanker Teile | Öffnen und Speichern erhalten den Parameter und die vollständige Migrationskette | `test_project.py` |
| `projects/example_v44.p3d` | Format 44: Stücknummern, Profilnutfeder-Größe und Drehmitte der Muster gespeichert | Öffnet über 44 → 45 mit unveränderten Schritten | `test_project.py` |
| `projects/example_v45.p3d` | Format 45 mit Revisionsherkunft der Schritte | Aktuelles Format, öffnet ohne Migration | `test_project.py` |

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
Die Bolzen entstehen genäht (`profiles.threaded_rod` über `helical_thread`:
je Umlauf zwei Flanken und ein Fußstreifen, 41 Flächen am M6), ebenso die
mehrgängigen und der kegelige (`sewn_rod`, `internal_multi_start`); die zwei
Sweep-Körper `zweigaengig` und `gegen_naht` weiter mit der Fuzzy-Vereinigung
des Skripts.

| Datei | Inhalt | Erwartung | Test |
|---|---|---|---|
| `threads/m6_rechts.step` | `profiles.threaded_rod(6, 1, 12)` | rechts, außen, p 1, L 1, n 1, Ø 6, Tiefe 0,6134, Länge 12, Achse z; Basis aller Ableitungen | `test_thread_import.py` |
| `threads/m10_rechts.step` | `threaded_rod(10, 1.5, 20)` | p 1,5, Ø 10, Tiefe 0,9201, Länge 20 | `test_thread_import.py` |
| `threads/m8_innen.step` | Block 20 × 20 × 10 minus `threaded_rod(8.2, 1.25, 10)` | innen, p 1,25, Nenn-Ø 8,2 (der Grund-Ø), Tiefe 0,7668, Länge 10 | `test_thread_import.py` |
| `threads/zweigaengig.step` | Kern Ø 6,92 plus zwei Helix-Gänge, Vorschub 2 | n 2, L 2, p 1, Ø 8, Tiefe 0,54, Länge 12 | `test_thread_import.py` |
| `threads/gegen_naht.step` | Zylinder Ø 6,02 mit einem 0,02 mm dünnen Gang | kein Gewinde: Gangtiefe außerhalb `GROOVE_RANGE` | `test_thread_import.py` |
| `threads/dreigaengig.step` | `sewn_rod(10, 1, 12, starts=3)`: drei Gänge in einem Umlauf | n 3, L 3, p 1, Ø 10, Tiefe 0,6134, Länge 12 | `test_thread_import.py` |
| `threads/innen_zweigaengig.step` | Block minus genähter zweigängiger Bolzen Ø 10 mit 0,2 Spiel (`internal_multi_start(10, 1.25, 2, 12, 0.2)`) | innen, n 2, L 2,5, p 1,25, Nenn-Ø 10,2, Tiefe 0,7668, Länge 12; gespiegelt links | `test_thread_import.py` |
| `threads/konisch.step` | `sewn_rod(10, 1.5, 12, taper=atan(1/32))`: kegeliges Rohrgewinde 1:16, Kamm Ø 10 auf z = 0 | Kegelwinkel atan(1/32), Maße in der Mitte (z = 6, Kammradius 5 + 6/32), p 1,5; umgedreht negativer Winkel | `test_thread_import.py` |

```
.venv\Scripts\python.exe tests/data/make_thread_corpus.py            # alle
.venv\Scripts\python.exe tests/data/make_thread_corpus.py m6_rechts  # einen
.venv\Scripts\python.exe tests/data/make_thread_corpus.py --check    # Datei gegen Erzeuger
```

`--check` baut jeden Körper neu und vergleicht Flächenzahl, Volumen und
Oberfläche mit der Datei (auf 1e-6): Am 20.09.2026 lagen Datei und Erzeuger
an M10 um 0,09 mm³ auseinander, weil der Erzeuger nach dem Korpus noch
viermal geändert wurde. `test_thread_import.py::test_the_corpus_matches_its_generator`
fährt den Vergleich je Lauf für jeden genähten Körper (je unter zwei
Sekunden); die zwei Sweep-Körper prüft der Aufruf von Hand vor einem Release.

## Baugruppen (STEP)

`step/*.step` erzeugt `make_step_assembly_corpus.py` über OCCTs
XCAF-Schreiber aus Konstruktionsmaßen; die Sollwerte stehen als Konstanten im
Erzeuger (`PLATE`, `BOLT`, `BRACKET_VOLUME`, `HOUSING` …), `--check`
vergleicht den XCAF-Baum der Datei mit dem Erzeuger.

| Datei | Inhalt | Erwartung | Test |
|---|---|---|---|
| `step/instances.step` | drei Instanzen eines Bolzens mit Namen und Lage (eine gedreht, eine mit eigener Farbe), eine Platte mit Teil- und Flächenfarbe | drei Körper dort, wo die Datei sie hinstellt; Instanzfarbe vor Teilfarbe, Flächenfarbe vor Körperfarbe, im sRGB der Datei | `test_step_assembly.py`, `test_step_assembly_ui.py` |
| `step/nested.step` | eine Unterbaugruppe zweimal eingesetzt, eine Farbe nur für ein tieferes Vorkommen (SHUO), eine gespiegelte Instanz | die Farbe färbt nur dieses Vorkommen; gleiche Namen unterscheidet das Vorkommen darüber; die Spiegelung ist ein gültiger Körper | `test_step_assembly.py` |
| `step/multibody.step` | ein Teil mit drei Körpern, zwei benannt und gefärbt, einer ohne beides | jeder Körper trägt seinen eigenen Namen | `test_step_assembly.py` |
| `step/unnamed.step` | eine Baugruppe ohne einen einzigen Namen und ohne Farbe | die Körper werden nummeriert, ein einzelner nimmt den Dateinamen | `test_step_assembly.py` |
| `step/inch.step` | ein Teil in Zoll | kommt in Millimetern an und nennt seine Einheit | `test_step_assembly.py` |
| `step/surfaces.step` | eine geschlossene Schale ohne Körper, eine offene Schale, ein Teil nur aus einer Kante | die geschlossene Schale wird ein Körper, die offene bleibt offen, die Kante bleibt draußen — und die Befunde sagen es | `test_step_assembly.py` |

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
| `refine_guard_case.json` | Eine Ringverfeinerung aus der Review-Sonde H (Paket stapel): 65 Punkte eines Zylinderstücks, Startwert eines Rings, skaliert auf Einheitsgröße | Der echte Löser antwortet knapp am Budget (hier nach 97 Auswertungen, je Maschine bis rund 105); ohne Abstände sagt der Stapel „vergeblich“, mit Abständen nichts | `test_refine.py` |
| `repair_features.json` | Eigener Würfel 100 × 100 × 100 mm mit separatem Zylinder Ø4 × 3 mm bei x=70; reguläre Merkmalsänderung auf Ø3 vor der Reparatur | Kleine Teile entfernen lässt einen Würfel mit 1.000.000 mm³ und sechs gültigen Flächen zurück; der entfernte erzeugte Zapfen bleibt auch bei Cache, Wiederöffnung und Undo/Redo verschwunden beziehungsweise wiederherstellbar | `test_repair.py` |
| `meshes/cubes_touching_edge.glb` | Zwei Würfel 10 mm, die sich an einer senkrechten Kante berühren, mit gemeinsamen Ecken (GLB, wie aus ComfyUI) | Eine Kante mit vier Flächen; die Reparatur verdoppelt sie: geschlossen, 24 Dreiecke, 2000 mm³ (RM-550) | `test_repair.py` |
| `meshes/generated_fell_apart.glb` | Ausschnitt aus einem zerfallenen Rohnetz von TRELLIS.2 (ComfyUI, Weg aus Text „a small toy rocket with three fins“, Startwert 8, Bild von FLUX.2 [klein] 4B, 08.10.2026): die 3 000 Dreiecke um die Mitte der Kanten mit mehr als zwei Flächen, Koordinaten wie geliefert | 61 solche Kanten, keine trennbar; `generate.fell_apart` sagt zerfallen (RM-550) | `test_way_three.py` |
| `meshes/generated_skin.npz` | Rohnetz von TRELLIS.2 (Weg aus Text „a small toy rocket with three fins“, Startwert 14, Bild von FLUX.2 [klein] 4B, 08.10.2026), geschlossen ausgedünnt mit `manifold3d` `simplify` auf 0,03 mm bei Arbeitsgröße (199 992 → 50 236 Dreiecke, Dicke 0,2615 → 0,2614 mm), Ecken `float32`, Dreiecke `int32`: eine Haut, bei der Außen- und Innenhülle zusammenhängen | `generate.skin_thickness` misst 0,26 mm; der Dialog sagt „nur eine Haut“ gegen die dünnste Wand des Profils (RM-577) | `test_way_three.py`, `test_generate_ui.py` |
| `meshes/generated_touching.glb` | Ausschnitt aus einem heilen Rohnetz desselben Laufs, Startwert 11: die 3 000 Dreiecke um die Kanten, an denen sich zwei Stücke berühren | Vier solche Kanten, alle trennbar; `generate.fell_apart` sagt heil (RM-550) | `test_way_three.py` |
| `meshes/generated_other_pairing.glb` | Ausschnitt aus dem Rohnetz des Bildwegs mit Startwert 8 (Eingangsbild von FLUX.2 [klein] 4B): die 400 Dreiecke um die eine Berührkante, deren Fächer die geometrisch bessere Paarung nicht trennt | Erste Paarung trennt 8 von 9 Kanten, die andere die letzte; danach keine Kante mit mehr als zwei Flächen und kein neuer Rand (RM-550) | `test_repair.py` |
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
| `meshes/plate_counterbored.stl` | Platte 60 × 40 × 10 mm, eine Stufenbohrung: Durchgang Ø 5,5 mm, Ansenkung Ø 10 mm, 5 mm tief (Sitz einer Zylinderkopfschraube M5) | Kette aus zwei Bohrungen; *Stift für Bohrung* baut einen Zylinderkopf Ø 10 minus Spiel, um das halbe Spiel über der Stufe, oben bündig | `test_bore_pin.py` |
| `meshes/sphere_socket.stl` | Block 40 × 40 × 15 mm mit eingefräster Kalotte R 8 mm | die Kugel als **Pfanne** (§41) — Ø 15,94 (die Icosphere ist einbeschrieben), Mittelpunkt auf z = 7,5 und damit auf der Oberfläche, `recess` wahr, Rückstand 0,0003. Vor dem 22.08.2026 kamen hier nur die sechs Blockflächen heraus | `test_features.py` |
| `meshes/ball_in_socket.stl` | Platte 30 × 30 × 12 mm mit Kugelpfanne Ø 12 (Mitte 3 mm unter der Oberseite), darin lose eine Kugel Ø 10 — das Kugelgelenk zum Drucken in einem Stück | zwei Teile, 10 038,06 und 522,47 mm³; Pfanne und Kugel als `sphere`, die Pfanne mit `recess`. Ändern, Versetzen und Entfernen der Pfanne und Versetzen der Kugel sagen ab, statt die Kugel abzuschneiden oder mit der Platte zu verschmelzen (Review G, F1) | `test_slot_features.py` |
| `meshes/shallow_sphere_cap_icosphere.stl`, `meshes/shallow_sphere_cap_uv.stl` | echte kreisrunde 5°-Kalotte R 80 mm, einmal als Icosphere und einmal als UV-Gitter | bleibt bei verschiedener Triangulierung, starrer Transformation und Skalierung eine bestimmte Kugelfläche; Radius etwa 80 mm | `test_sphere_fit_quality.py` |
| `meshes/indeterminate_sphere_cap.stl` | kreisrunde 2°-Kalotte R 80 mm, nur 0,049 mm hoch | kein sicher lokalisiertes Kugelmerkmal: Die zentrierte Normalenauskunft verstärkt Eingangsabweichungen um den Faktor 6615 | `test_sphere_fit_quality.py` |
| `meshes/ambiguous_sphere_ribbon.stl` | schmaler Ausschnitt einer exakten Kugel R 80 mm, 40° lang und 4° breit | kein sicher bearbeitbares Kugelmerkmal: Nur eine Krümmungsrichtung ist ausreichend belegt | `test_sphere_fit_quality.py` |
| `meshes/near_sphere_ellipsoid.stl` | Icosphere R 8 mm, in einer Achse um 4 % gestreckt | keine Kugel; der auf den Radius bezogene Rückstand von 0,0101 täuscht nur deshalb Güte vor, weil er die örtliche Ausdehnung des Flecks nicht berücksichtigt | `test_sphere_fit_quality.py` |
| `meshes/torus_ring.stl` | Torus, Ringradius 20 mm, Röhrenradius 5 mm | `diameter` (Ring) Ø 40, `tube_diameter` Ø 10, Achse z, Rückstand 0,005. Die Einpassung liest beide Radien aus den Rändern des Flecks und setzt damit einen **ganzen** Ring voraus — ein Torusstück, wie eine Verrundung es ist, misst sie noch nicht | `test_features.py` |
| `meshes/pocket_with_pin.stl` | Block 20 × 20 × 12, von unten eine Ringnut: Tasche Ø 6,12, darin ein Zapfen Ø 5,44 bis z = 7,68 (Maße der Kundentasche, RM-535) | Volumen 4 752,72 mm³; erkannt `hole_1` Ø 6,12 und `pin_1` Ø 5,44, beide Tiefe 7,68. Die Tasche sagt beim Versetzen ab (`HOLE_HOLDS_A_PIN`), der Zapfen 0,5 mm in die Wand verliert 3,85 mm³ | `test_feature_moves_keep_shape.py`, `test_ui.py` |
| `meshes/cup_on_stem.stl` | Becher Ø 30 × 18 auf einem Fuß Ø 16 × 6, innen Ø 28 mit Deckelfalz Ø 29,2 (nach dem Minitopf, RM-535) | Volumen 3 381,12 mm³; die Außenwand ist `pin_2` Ø 30, Tiefe 18; starr versetzt bleibt das Volumen auf 0,05 mm³ | `test_feature_moves_keep_shape.py` |
| `meshes/pin_with_end_chamfers.stl` | Stift Ø 33,8 × 40, Fasen 5 mm an beiden Enden, Sackloch Ø 23,8 von unten bis z = 22,1 (Stift der Kundensitzung, RM-535) | Volumen 23 598,57 mm³; `hole_1` Ø 23,8 Tiefe 22,1, `pin_1` Ø 33,8, zwei Kegel Ø 33,8; die untere Fase ohne das Sackloch unter den Merkmalen versetzt füllte dessen Mündung (+2 224 mm³) | `test_feature_moves_keep_shape.py` |
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
| `meshes/parts_enclosing_air.stl` | 13 nicht vereinigte Schalen (`make_corpus.parts_enclosing_air`): Rahmen aus vier überlappenden Balken mit Fenster, ein schräger Balken hindurch, Ring aus sechs Zylindern um einen Luftkern, ein Zylinder ganz in einem Balken, ein umgekehrter Quader als Hohlraum im anderen | nach dem Einlesen dicht, 13 Komponenten, `Manifold` gültig; jede Schicht gleich `Manifold.slice` (rel. 1e-6), die erste gleich der Vereinigung der vier Balken (RM-485) | `test_slice.py`, `test_slice_core.py` |
| `meshes/colored.3mf` | zwei Würfel in Slot 1 und 2, mit der eigenen 3MF-Hälfte geschrieben | zwei Materialgruppen „Rot" und „Schwarz", je Dreieck zugeordnet; Rundweg durch `threemf.read` | `test_corpus.py` |
| `projects/assembly_fit.p3d` | Platte mit 6-mm-Bohrung, Deckel mit 5,95-mm-Stift, dazu ein Passungspaar `auto:petg`; **gespeichert liegen beide Grundkörper auf z = 0 und durchdringen sich** — die Einbaulage auf der Stiftschulter stellt `test_corpus.py` als regulären Schritt her | roh meldet die Datei `fit.collision` (in PLA dazu `fit.mesh_uncertain`); in der Einbaulage hält die Passung mit PETG und meldet sich mit einem anderen Material — die Bohrung folgt dem Druckmaterial, die Toleranz dem, was im Paar steht | `test_corpus.py` |
| `meshes/oversized.stl` | 400 × 80 × 40 mm: zwei dicke Enden, schlanke Mitte | passt auf keinen Bauraum; der Auto Split findet die Trennebene in der Mitte (Querschnitt 1200 mm², eine Kontur) und macht daraus zwei wasserdichte Teile | `test_autosplit.py` |
| `meshes/island_tower.stl` | Säule 10 × 10 × 30 mm, daneben ein Block 10 × 10 × 10 auf z 20–30, oben durch einen Steg 30 × 10 × 5 verbunden (`make_corpus.island_tower`) | 4500 mm³; der Block ist eine Insel, die in jeder Lage Stützen braucht; die Suche über 200 Lagen braucht nicht mehr Stützvolumen als die Heuristik; die Zahlen ohne Schichten gleichen der vollen Analyse bitgenau | `test_orientation_search.py`, `test_slice.py`, `test_performance.py`, `test_analysis_ui.py` |
| `meshes/bridge_two_end_supports.ply` | zwei Stützen 3 × 3 × 10 mm an den Enden, darüber ein Steg 36 × 3 × 2 mm; 396 mm³ | größte Brückenweite 30 mm (die freie Länge), nicht der Inkreis von 3 mm — auch gedreht, verschoben und mit Rückwand; übersetzter Kern und GEOS-Weg gleich | `test_slice.py`, `test_slice_core.py` |
| `meshes/dovetail_vertex_plane.ply` | Quader 40 × 20 × 20 mm mit angesetztem Keil, dessen Spitze auf z = 9,5 liegt; 16 125 mm³ | der Schnitt auf z = 9,5 ist der Quaderquerschnitt von 800 mm² auf beiden Wegen, keine Scheininsel darüber | `test_slice_core.py` |
| `meshes/openscad_ascii.stl` | von OpenSCAD 2021.01 geschriebene ASCII-STL, Hüllquader 24 × 16 × 8 mm — ganze Zahlen ohne Dezimalpunkt, `-0` in einer Normale | der ASCII-Zweig liest sie, obwohl die binäre Längenrechnung grob danebenliegt; 144 Dreiecke, verschweißt geschlossen, 2847,26 mm³ | `test_ingest.py` |

`meshes/dense_1m.stl` (1,31 Mio. Dreiecke, Leistungsmessung nach §31) wird
**nicht eingecheckt** — 60 MB im Repository wären unverhältnismäßig. Der
Leistungstest erzeugt sie beim ersten Lauf; die Messwerte landen in
`tests/.performance.json` und bleiben lokal, weil sie von der Maschine abhängen.

Damit ist der Korpus aus §34 vollständig, bis auf `legacy_v1.p3d` — die
Altformate liegen unter `projects/example_v<N>.p3d`, eine Datei je
Formatversion von 1 bis zur vorletzten (`projects/example_v*.p3d`), dazu die
Sonderfälle mit eigenem Inhalt (`drilled_v6`, `split_v10`, `scad_v12`,
`painted_v13`, `circle_v18`, `generated_glb_v24`, `matching_answers_v26`,
`sketch_v30` — Skizzen aus der Zeit vor Ellipse und Kurvenbedingungen —,
`further_model_v37` — ein zweites Modell an seinen Dateikoordinaten, vor der
freien Stelle —, `slot_angle_frame_v38` — Langlochwinkel im Rahmen vor
`prepare.slot_frame`), und werden von `test_project.py` durch die Migrationskette
geschickt; eine neue Formatversion bringt ihre Beispieldatei mit (AGENTS.md,
Checkliste Dateiformat).

Weitere Sonderfälle, je mit eigenem Test:

| Datei | Inhalt | Erwartung | Test |
|---|---|---|---|
| `projects/material_fits_v29.p3d` | vier Passungen im Format 29 | nach der Migration `auto:` für `deckel`, `stift_2` und `stift_3`, `auto:pla` für das von Hand gesetzte `von_hand` | `test_project.py` |
| `projects/step_assembly_v32.p3d` | ein STEP-Ladeschritt ohne `bodies` | bleibt ein Körper `gehaeuse` mit drei Volumenkörpern, Volumen aus `HOUSING` des Baugruppenerzeugers | `test_step_assembly.py` |
| `projects/recognition_v33.p3d` | ein Projekt vor den gespeicherten Erkennungsantworten | die Migration ändert nur `format_version`; kein Schritt trägt eine `recognition-answer:`-Zuordnung | `test_project.py` |
| `projects/print_settings_v33.p3d` | Druckeinstellungen, wie 0.5.0 sie schrieb: Fein, Außenwand 30 mm/s, gewählt `shell.wall_count` und `infill.density` | öffnet mit genau diesen Werten, nichts als angenommen markiert | `test_manufacturer.py` |
| `projects/repair_v34.p3d` | ein Reparaturschritt ohne `self_intersections` | rechnet wie gespeichert (`self_intersections: False`), der Befund bietet das Auflösen an | `test_project.py` |
| `projects/edge_groups_v36.p3d` | zwei Quader 40 × 30 × 20 mm mit Querbohrung Ø 6, einer als Netz, einer exakt, beide R 1 an „waagerecht“ | die Migration setzt `rings_by_plane: False`, die Mündungen werden wie gespeichert mitgerundet; der exakte Körper rechnet auf die Stelle genau wie beim Schreiben gemessen | `test_project.py` |
| `projects/slot_angle_frame_v38.p3d` | zwei Platten 80 × 60 × 10 mm, Netz und exakt; je eine Bohrung Ø 6 0,03° neben Z, zum Langloch gezogen (Winkel −40°), und eine Bohrung mit Haken *Langloch* 0,05° neben Z (Winkel 160°), geschrieben vom Stand vor `prepare.slot_frame` | alle vier Langlöcher liegen entlang +Y (auf 0,5°); die Migration bewahrt Winkel und Achse einschließlich Parameterausdrücken und setzt `measured_frame`; beide Kerne rechnen bei jeder Auswertung anhand der aktuellen Werte um | `test_project.py` |
| `projects/sculpt_mirror_v39.p3d` | eine Kugel Ø 30, um 40 mm nach +X verschoben, ein Formzug bei x = 55 mit Symmetrie X, geschrieben vom Stand vor der Körpermitte | die Migration setzt `mirror_at_body: False`, der Zwilling trifft wie gespeichert nichts; mit Haken trifft er die andere Seite | `test_project.py` |
| `projects/sculpt_brush_v40.p3d` | eine 4-mm-Platte mit einem Abtragzug, der die Unterseite mitnahm (Unterkante z = −0,498), und einem Zug mit Symmetrie Y, geschrieben vom Stand vor dem Vorderseitenfilter | die Migration setzt `front_only` und `mirror_once` auf `False`, die Platte rechnet wie gespeichert; mit den Schaltern von heute bleibt die Unterseite auf dem Bett | `test_project.py` |
| `projects/slot_tool_v40.p3d` | elf Netzklötze 60 × 100 × 60 mm, je ein Langloch Ø 6 auf 20 mm bei 30° durch die Wand +X (einer durch −X, einer durch +Y) und genau ein Folgeschritt: Zug auf 0°, Kürzen, Verbreitern, Verschmälern, Drehen, Versetzen, Verdoppeln, Muster, Entfernen; geschrieben vom Stand vor RM-325 (`38006b338`) | die Migration setzt an den sieben Langlochhandlungen `legacy_slot_tool`, alle elf Körper rechnen wie beim Schreiben gemessen (`SAVED_SLOT_TOOL_RESULT`); ohne den Marker rechnen fünf an ±X anders; eine Änderung am Schritt rechnet wie heute | `test_project.py` |
| `projects/cut_away_face_v41.p3d` | ein Quader 40 × 30 × 20 mm (Netz), *Abschneiden* an der Oberseite (*An Fläche*, −2 mm) und danach 20° um X bei z = 9, geschrieben vom Stand vor dem Feld *Ebene* | die Migration setzt beim ersten Schnitt `plane = "at_face"`, der zweite bleibt an der Achse mit Kippachse X; 10 800 mm³, 28 Dreiecke, Abdruck `0e0416967210692d` bitgleich zum Schreiben | `test_project.py` |
| `projects/gestures_v48.p3d` | Kugel Ø 40 (auf 1,5 mm angeglichen) mit 24 Pinselproben in vier Gesten und Symmetrie X, Stab 12 × 12 × 60 mm mit zwei Knochen nur oben, gebeugt, Klotz 40 × 20 × 20 mm mit dünnem Arm an einer Seite und drei Spiegelzügen; geschrieben vom Stand vor RM-560/561 (`3d900b428`) | die Migration setzt `mirror_fitted` und `fixed_rest` auf `False`, die Züge bleiben Pinselfassung 1; Kugel 32 742,854319 mm³, Stab 8 584,334036 mm³ mit dem Fuß bei z = 1,019238, Klotz 16 508,448935 mm³ wie beim Schreiben; mit festem Rumpf bleibt der Fuß auf dem Bett, mit angepasster Spiegelmitte rechnet der Klotz anders | `test_project.py` |
| `projects/sketch_solver_v49.p3d` | Platte 5 hoch aus vier schief gezeichneten Linien mit Deckung, die untere waagerecht, die rechte 80° zur unteren — unterbestimmt, gespeichert sind die gezeichneten Punkte; geschrieben vom Stand vor RM-541 (`78d39dec9`) | die Migration schreibt `"solver": 1` in den Skizzentext; gerechnet wie mit dem Löser von 0.5.3 2 656,656241 mm³, linke untere Ecke bei (0,030846 | −0,011202); derselbe Text mit dem heutigen Löser rechnet anders (2 626,81 mm³) | `test_project.py` |
| `projects/pin_for_bore_v46.p3d` | `plate_countersunk.stl` mit *Stift für Bohrung* an `hole_1` (Netz) und ein exakter Quader 30 × 30 × 12 mm mit Stufenbohrung Ø 5,5/10 × 5 und Stift an der engen Bohrung, geschrieben vom Stand vor RM-536 (`63d7a7826`) | die Migration setzt an beiden Stiften `shape = plain_pin`; beide rechnen wie beim Schreiben gemessen (107,4601 und 162,6896 mm³, `SAVED_PIN_RESULT`); mit der Form von heute bekommt der erste einen Senkkopf | `test_bore_pin.py` |
| `projects/generated_chain_before_rm676_v49.p3d` | eine Erzeugung aus offener Schale und losem Krümel mit der Kette `load`, `fit_to_size` (100 mm, freie Stelle), `repair`, `place_on_bed`; geschrieben vom Stand vor RM-676 (`a9e4d3f64`) | die Kette bleibt, wie sie ist; 63 238,1004 mm³, Kante 39,84 mm, Lage bei −50/−50 und dieselben Befunde wie beim Schreiben (`SAVED_EARLIER_CHAIN`); *Größe ändern* bleibt am Maßschritt 2 | `test_way_three.py` |

## Analytische Schnitt-Gegenproben

`test_slice.py` ergänzt `parts_enclosing_air.stl` um ein invertiertes Rohr
(Radien 4/10 mm, Höhe 20 mm, 48 Segmente): allein, neben getrenntem oder
überlappendem Material, mit unabhängiger Insel im Loch sowie als eingeschlossene
Luft. Geprüft werden Vollschnitt und Kontaktband über alle drei Schnittwege.
Eine insgesamt invertierte Hohlkugel (Radien 7/10 mm, zwei getrennte Wände)
belegt den konservativen Verschachtelungsweg bei uneindeutiger Herkunft.
Ein Würfel mit freistehendem doppelseitigem Dreieck belegt, dass Zweipunktzyklen
in Cython und NumPy entfallen, ohne die übrige Schnittfläche zu verlieren.
Alle diese Gegenproben werden im Test konstruiert; Kundenmodelle sind nicht kopiert.

## Daneben

| Datei | Inhalt | Test |
|---|---|---|
| `meshes/same_layer_rounding.wkt` | Zwei analytische 10-mm-Quadrate mit beinahe gerader Oberkante auf beiden Seiten der Vereinfachungsgrenze; minimale Fassung einer Schnittfolge aus dem eigenen Beispiel „Aushöhlen und Teilen“ | Schichtvergleich bleibt bei 0,00000002 mm Konturabweichung gleich, obwohl die Vereinfachung verschieden viele Ecken behält | `test_slice.py` |
| `LICENSE` | MIT für den ganzen Korpus, weil er mit veröffentlicht wird | — |
| `make_corpus.py` · `make_recognition_corpus.py` · `make_thread_corpus.py` · `make_step_assembly_corpus.py` | die Erzeuger der Netze, der Erkennungskörper, der Gewinde und der Baugruppen | `test_thread_import.py` und `test_step_assembly.py` vergleichen Datei und Erzeuger |
| `ci_core_durations.json` · `ci_window_durations.json` | Sekunden je Testdatei der Kernsuite bzw. je Fensterdatei, mit Ersatzwert und Herkunft; erzeugt von `tools/ci_shards.py` aus JUnit-Berichten, verteilen nur | `test_ci_runner.py`, `test_packaging.py` |
| `check_subject.php` | prüft `encode_subject()` aus `website/api/support.php` gegen RFC 2047 | `test_support.py` |
| `brep_cylinder_orientation.json` | Block 20 × 20 × 20 mm mit Kreisprofil Ø 2 × 4 in beiden Extrusionsrichtungen, dazu ein Kegel r 2/4 × 4 | Zapfen und Sackloch Ø 2, Tiefe 4, auch als NURBS; die Materialseite des Kegels übersteht die Spiegelung | `test_brep_trimmed_cylinder_centres.py` |
| `filament_catalogue_v0.json` | Filamentlager im ersten Format: zweimal „Weiß“, PLA, ohne Kennung | die Migration vergibt zwei verschiedene Kennungen und erfindet keine Mengen | `test_filament_inventory.py` |
| `text_patterns.json` | je Satzmuster (Fachwort, Semikolon, „Nur …:“) die Kundentexte, die es heute noch treffen (RM-509), sortiert; die Zahl je Muster steht in `MUSTER_BESTAND` | ein neues Vorkommen und ein überarbeitetes, das noch gelistet ist, machen den Wächter rot | `test_wording.py` |
| `translated_semicolons.json` | je Sprache die deutschen Quelltexte ohne Semikolon, deren Übersetzung heute eines trägt (Review P2 N5), sortiert; die Zahl je Sprache steht in `UEBERSETZT_BESTAND` | ein neues Vorkommen und ein überarbeitetes, das noch gelistet ist, machen den Wächter rot | `test_wording.py` |
| `text_lengths/*.json` | je Textart die Kundentexte, die heute über ihrer Längengrenze liegen (RM-509), sortiert; die Zahl je Art steht in `FROZEN_COUNTS` | ein neuer Text über der Grenze, ein gekürzter, der noch gelistet ist, und eine wachsende Liste machen den Wächter rot | `test_text_length.py` |
| `creators_before_rm562.json` | Hülle, Volumen und Merkmalsmitten der 22 Erzeuger, die vor RM-562 eigenständig waren, in fünf Lagen, gemessen am Ausgangsstand `3d900b428` (Review B) | ein altes Projekt mit einem dieser Schritte rechnet gleich, auch die Flächenkennungen der frei gesetzten Rohrschelle | `test_parts.py` |
| `organizer_layouts.json` | die fünf Besteckkorb-Vorlagen als Aufteilung mit Außenmaßen und Sollmaßen der Fächer | je sechs Fächer und fünf Wände in den Sollmaßen; jede Vorlage baut geschlossen mit exakter Hülle | `test_organizer_layout.py`, `test_organizer_build.py` |
| `profile_clamp_reference.json` | Zahlenreferenz für vier Profilklemmteile: Ø 16, Spline, Ellipse 47 × 32, Tiefe 40, Wand 4, Spiele | Schale und Einlage montieren frei in Achsrichtung; die Konturen werden an diesen Maßen abgetastet | `test_profile_clamps.py`, `test_profile_sampling.py` |
| `superslicer_3mf_keys.json` | gemessener Schlüsselbestand des 3MF-Lesers von SuperSlicer 2.5.59.13: bekannt und unbekannt je Schlüssel der Prusa-Beilage | jede Zeile, die SuperSlicer nach `slicer_keys.for_program` bekommt, ist bekannt (RM-459) | `test_export.py` |
| `slicer_values.json` | Aufzählungswerte aus Prusa-/SuperSlicer-Hilfe, Cura-Definitionen und Rundreisen durch die fünf Orca-Programme | jede geschriebene Aufzählungszeile gegen den Bestand des Programms (RM-480, RM-461) | `test_print_settings.py` |
| `recipes/historical_box_v1.json` | ein gespeicherter Quader-Baustein aus der ersten Dokumentfassung (Format 1) | migriert, öffnet und exportiert | `test_part_file.py` |
| `projects/auto_split_unnumbered_v42.p3d` | Leiste 600 × 30 × 20 mm, zwei zusammenhängende Schnitte bei X −100/+100 ohne Nummern; letzter Schnitt gelöscht und im Undo enthalten | Format 43 → 44 nummeriert aktive Stücke, Undo/Redo und Speichern erhalten Geometrie und Namen | `test_project.py` |
| `projects/revision_titles_v44.p3d` | Quader und versetzte Kugel mit den Schrittnamen Rumpf, Kopf und Kopf setzen, ohne gespeicherte Revisionsherkunft | Format 44 → 45 erhält Geometrie und Titel; fehlende Herkunft wird nicht geraten | `test_project.py` |
| `projects/lid_top_edge_v46.p3d` | Kasten 60 × 40 × 30 mit Deckel bei `z = 0` (damals „Oberkante“, danach auf 3 mm Stärke geändert), Dose Ø 40 mit Drehdeckel bei `z = 0`, Kasten 40 mm unter dem Bett mit Deckel bei `z = −10`; geschrieben vom Stand vor RM-526 (`65e3ec97b`) | Format 46 → 47 leert beide Nullen, auch in den Fassungen der Änderung, die negative Höhe bleibt; alle sechs Körper rechnen wie gespeichert (`SAVED_LID_RESULT`), ohne Migration hielte der Deckel am Kasten an | `test_project.py` |
| `linux/paket-0.2.1-abhaengigkeiten.json` | die Bibliotheksabhängigkeiten je Datei des Linux-Pakets 0.2.1 | das Linux-Paket lässt keine Abhängigkeit offen | `test_packaging.py` |
| `spacemouse/compact-2026-09-02.jsonl` | eine ausgedünnte Aufzeichnung der SpaceMouse Compact in Phasen zu vier Sekunden, mit Kopfzeile | beide Tasten sind benannt; dieselbe Aufnahme ergibt zweimal dieselbe Kamera | `test_spacemouse.py` |
