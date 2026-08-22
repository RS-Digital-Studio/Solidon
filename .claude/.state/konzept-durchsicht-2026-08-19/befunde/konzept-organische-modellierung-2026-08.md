# Sondierung: konzept-organische-modellierung-2026-08.md

**Titel:** Konzept — Organische Modellierung (P16)
**Stand laut Dokument:** Stand 13.08.2026 — entschieden. (Übergabenotiz: „Übergabenotiz — Stand 13.08.2026", darin Nachträge „14.08.2026"; Dateiname trägt 2026-08)
**Zweck:** Konzept und Umsetzungsplan für Phase P16 „Organische Modellierung" — fünf Fähigkeiten (Sculpting-Pinsel, Subdivision, Symmetrie, Displacement, Posing), die dafür nötige Neufassung von Regel 2, die Design-Entscheidungen A–N und die Positionierung des erweiterten Kundenkreises.

**Alterung:** 4/5 — Das Dokument ist zur Hälfte ein laufendes Arbeitsprotokoll: Paketstände, Testzahlen, Messwerte in Millisekunden, Zeilennummern in Quelldateien, Operationszahlen für die Website und eine Liste offener Punkte. All das ändert sich mit jedem Commit — mehrere Stellen widersprechen einander bereits innerhalb des Dokuments (drei gegen vier Displacement-Projektionen, „keiner begonnen" gegen „durch", Kategorie organic geplant gegen verworfen, §7.4 gegen den Schlussabsatz). Die konzeptionellen Teile (Regel 2, Entscheidungen A–N, Positionierung §17) altern dagegen langsam; die Aussagen über manifold3d, trimesh und die Wettbewerber altern mit deren Fassungen.

## Gliederung

- Konzept — Organische Modellierung (P16)
- Inhalt
- §1 Auftrag und Abgrenzung der Frage
- §2 Ist-Zustand — verifiziert, nicht vermutet
- §3 Der eigentliche Konflikt
- §4 Design-Entscheidungen
- §5 Regel 2 — alt und neu
- §6 Was sich am Bauplan ändert
- §7 Die fünf Fähigkeiten
- §8 Oberfläche
- §9 Dateiformat
- §10 Leistung — neue Zeilen für §31
- §11 Agentenschicht
- §12 Druckbarkeit — die Kopplung, um die es eigentlich geht
- §13 Nicht-Ziele
- §14 Risiken und Rückfalloptionen
- §15 Umsetzungsplan
- §16 Abnahme
- §17 Positionierung — nach der Entscheidung
- §18 Was die Erweiterung außerhalb des Codes kostet
- Übergabenotiz — Stand 13.08.2026

## Extern prüfbare Behauptungen (19)

- **[hoch/api] manifold3d (Python-Bindings)** — manifold3d bietet warp_batch(f), level_set(f, bounds, edge), refine(n), refine_to_length(l), smooth_out(min_sharp_angle), calculate_curvature(g, m), mirror(normal), set_properties(n, f)  
  _Ort:_ §2.4 Tabelle
- **[hoch/api] manifold3d warp_batch** — warp_batch „does not change the topology" — Vertices verschieben ja, neue erzeugen nein (Zitat aus der Dokumentation)  
  _Ort:_ §2.4
- **[hoch/api] manifold3d warp_batch** — warp_batch prüft Selbstdurchdringung nicht: „It is easy to create a function that warps a geometrically valid object into one which overlaps, but that is not checked here"  
  _Ort:_ §2.4, Entscheidung L, §14 R6
- **[mittel/funktionsumfang] manifold3d** — manifold3d nimmt kein Netz an, das kein Volumen ist — liefert bei fehlerhaftem Eingangsnetz ein leeres Manifold  
  _Ort:_ Entscheidung E
- **[hoch/api] manifold3d smooth_out** — smooth_out leitet Tangenten aus der Dreiecksgeometrie ab und fasst je zwei koplanare Dreiecke zu einem Viereck zusammen, dessen Diagonale beim Verfeinern übersprungen wird — bricht bei CAD-Netzen  
  _Ort:_ §7.2
- **[hoch/api] manifold3d calculate_normals / smooth_by_normals** — calculate_normals(0, angle) + smooth_by_normals(0) + refine_to_length(l) hält die Form exakt und kennt keine Vierecke  
  _Ort:_ §7.2
- **[hoch/api] manifold3d level_set** — level_set ruft eine Python-Funktion je Rasterpunkt auf; mit zwei interpolierten Abstandsfeldern 25 Sekunden statt 240 ms  
  _Ort:_ Entscheidung N
- **[mittel/api] scikit-image (skimage.measure.marching_cubes)** — Marching Cubes über scikit-image auf dem vektorisierten Feld liefert dieselbe Isofläche in 200 ms  
  _Ort:_ Entscheidung N
- **[mittel/api] trimesh voxelized()** — trimesh voxelized().fill() plus Distanztransformation liefert acht Prozent zu viel Volumen (markiert jede berührte Zelle, misst ab Zellmitte)  
  _Ort:_ Entscheidung N, Tabelle
- **[hoch/api] trimesh / rtree** — Trimesh.contains erzeugt eine Zugriffsverletzung in rtree nach etwa 75 000 Punkten  
  _Ort:_ Entscheidung N, Tabelle
- **[mittel/api] scipy cKDTree (workers-Parameter)** — KD-Baum-Abfrage mit workers=-1 bringt Faktor 6,3 — 1,5 statt 9,6 Sekunden  
  _Ort:_ Entscheidung N
- **[hoch/api] imageio / scikit-image** — imageio kommt bereits mit scikit-image mit — keine neue Abhängigkeit nötig  
  _Ort:_ Übergabenotiz, P16.7
- **[hoch/marktlage] ZBrush / Blender / Nomad Sculpt** — ZBrush, Blender und Nomad haben zwanzig Jahre, Hunderte Werkzeuge und geübte Nutzer; Solidon stellt sechs Pinsel dagegen  
  _Ort:_ §17, §13
- **[hoch/funktionsumfang] ZBrush / Blender** — Sculpting-Programme wissen nichts über Drucker: keine Wandstärkenprüfung unter Düsenbreite, kein Überhang, kein Bauraum, keine Teilung mit Verstiftung; ZBrush/Blender arbeiten destruktiv, Anbauteile nur mühsam, laufen aber ohne Konto und Netz  
  _Ort:_ §17 und Vergleichstabelle
- **[hoch/marktlage] Markt der 3D-Druck- und Sculpting-Programme** — Solidon ist nach P16 das einzige Programm, in dem Formen und Druckprüfung in einem Fenster stehen  
  _Ort:_ §17
- **[hoch/funktionsumfang] Meshy / Hyper3D Rodin** — Meshy/Rodin erzeugen Figuren nur per Prompt, ohne Wandstärke-, Überhang- oder Bauraumprüfung, nicht reproduzierbar aus der Datei, nicht ohne Konto und Netz nutzbar  
  _Ort:_ §17 Vergleichstabelle
- **[mittel/funktionsumfang] Slicer-Programme (allgemein)** — Der Slicer meldet Probleme zu spät und sagt „Stützen an 340 Stellen" statt Wandstärke beim Formen  
  _Ort:_ §17
- **[niedrig/funktionsumfang] ComfyUI** — Die Generierung über ComfyUI (§27) bleibt unverändert und steht neben diesem Konzept  
  _Ort:_ §1
- **[niedrig/api] V-HACD** — Die technische Ablehnung des nicht-planaren Schnitts beruht auf der V-HACD-Näherung  
  _Ort:_ §18, letzte Tabellenzeile

## Intern prüfbare Behauptungen (15)

- **[hoch]** P16.1 ist umgesetzt: Regel 2 neu gefasst, tests/test_gesture_ops.py mit 26 Tests grün; Befund B13 im Meshy-Konzept mit Datum zurückgenommen  
  _Prüfen:_ AGENTS.md Regel 2 lesen; pytest tests/test_gesture_ops.py -q; konzept-meshy-hyper3d-2026-08.md nach B13 durchsuchen  
  _Ort:_ Kopfkasten; §15 P16.1; §17/§18; Übergabenotiz
- **[hoch]** Zeilengenaue Verweise auf den Bestand: sketch_editor.py:1434, mesh_ops.py:93 / 102–137 / 76, paint.py:87 und 134–151, registry/params.py:229, hashing.py:9–11 und :65  
  _Prüfen:_ Zeilennummern in den genannten Dateien nachschlagen — sie veralten bei jeder Bearbeitung  
  _Ort:_ §2.1–§2.3, §3, §7.1
- **[hoch]** Messwerte §2.5 (Kugel 65 538 Vertices / 131 072 Dreiecke): ein Strich 7,4 ms, 100 sequenziell 747 ms, 100 akkumuliert 57 ms, 1 000 akkumuliert 252 ms, 5 000 akkumuliert 586 ms, level_set 240 ms, refine(2) 204 ms — Gewinn Faktor ~60  
  _Prüfen:_ pytest -q -m performance und die Messskripte aus P16.2 erneut fahren; hardware- und fassungsabhängig  
  _Ort:_ §2.5, Entscheidung C
- **[hoch]** Leistungstabelle §10: Vorschau 0,7 ms bei 1,31 Mio. Dreiecken, 1 000 Striche 96 ms, Subdivision 1 778 ms, gleichmäßig vernetzen 1 480 ms, weich verschmelzen 1 607 ms; fünf Tests plus einer für Entscheidung C in tests/test_performance.py  
  _Prüfen:_ pytest -q -m performance; gegen Bauplan §31 und die 25-%-Regressionsschwelle halten  
  _Ort:_ §10
- **[mittel]** R1-Messung an dense_1m.stl (1 310 720 Dreiecke, 3 932 160 Vertices): KD-Baum 786 ms je Sitzung, ein Strich trifft 10 595 Vertices, Vollkopie 28,4 ms gegen 0,7 ms  
  _Prüfen:_ tests/test_performance.py, test_a_brush_stroke_stays_inside_a_frame; Existenz von tests/data/dense_1m.stl prüfen  
  _Ort:_ §10, §14 R1
- **[mittel]** generated_figure.stl liefert direkt ein leeres Manifold; nach GENERATED_REPAIR 3 368 Dreiecke wasserdicht, nach refine(8) 215 552  
  _Prüfen:_ Reparaturkette gegen tests/data/generated_figure.stl fahren und Dreieckszahlen vergleichen  
  _Ort:_ Entscheidung E
- **[mittel]** P16.3-Zahlen: plate_holes verliert mit smooth_out 31 322 → 25 832 mm³ und bekommt 2 772 Nullkanten; Ikosaeder 29 270 → 33 436 mm³ bei 33 510 möglichen; Kantenstreuung 2,224 vor und nach remesh_mesh; 3 260 416 Dreiecke gegen 30 648 bei Streuung 0,41  
  _Prüfen:_ pytest tests/test_subdivision.py -q; Kennzahlen im Test nachlesen  
  _Ort:_ §7.2
- **[hoch]** Sechs neue Ops geplant (sculpt_strokes, subdivide_surface, displace_image, pose_armature, blend_union, remesh_uniform); die Kategorie organic entsteht am Ende ausdrücklich NICHT — die „acht Operationen" bleiben bei mesh, boolean, surface  
  _Prüfen:_ Kategorien der Ops im Register (app/core/registry/) prüfen; ROADMAP.md unter P16  
  _Ort:_ Entscheidung M, §7.2, Schluss der Übergabenotiz
- **[hoch]** Operationszahl auf beiden Websprachen von 77 auf 79 nachgezogen  
  _Prüfen:_ Ops im Register zählen und mit website/ sowie Handbuchtexten vergleichen  
  _Ort:_ Übergabenotiz P16.3
- **[hoch]** Alle Pakete P16.1 bis P16.11 sind fertig; offen ist einzig die Agenten-Regelsammlung aus P16.10, weil sie den bezahlten Suite-Lauf vorher/nachher braucht  
  _Prüfen:_ ROADMAP.md unter P16; knowledge/data/rules.toml auf Sculpting-Regel und Versionsstand prüfen  
  _Ort:_ §15 Tabelle, Übergabenotiz „Was noch offen ist"
- **[hoch]** Abnahme §16: sieben von acht Punkten erfüllt, offen nur Punkt 7 (Agenten-Suite); Weg 4 läuft laut tests/test_way_four.py in 0,24 Sekunden vom Grundkörper zum druckfertigen 3MF  
  _Prüfen:_ pytest tests/test_way_four.py -q; §16-Liste Punkt für Punkt durchgehen  
  _Ort:_ §16, Übergabenotiz
- **[mittel]** Testzahlen je Datei: test_gesture_ops 26, test_subdivision 15, test_blend 10, test_sculpt 26 (+5), test_sculpt_session 19, test_displace 17, test_pose 16, test_pose_session 14, test_gathered 13, test_base_mesh 4  
  _Prüfen:_ Je Datei pytest <datei> -q und Testzahl vergleichen  
  _Ort:_ §15 Tabelle, Übergabenotiz
- **[hoch]** Voller Tor-Lauf: 3553 pytest-Tests plus 16 Leistungstests, ruff check, ruff format --check, mypy alle grün; ein Lauf in einem Rutsch stürzt wegen eines vorbestehenden VTK-Problems ab  
  _Prüfen:_ /pruefen bzw. die vier Befehle aus CLAUDE.md; Gesamttestzahl vergleichen  
  _Ort:_ Übergabenotiz
- **[hoch]** Dateiformat steht auf Version 8, Migration v7→v8, example_v8.p3d eingecheckt, Auslagerung von Sammelwerten ab 2 000 über app/core/scene/gathered.py; Einbacken als Parameter an sculpt_strokes mit der einzigen Nachfrage im Programm  
  _Prüfen:_ format_version im Projektcode; pytest tests/test_gathered.py -q; Existenz von tests/data/example_v8.p3d; HistoryPanel.bakeRequested im UI  
  _Ort:_ §9, Entscheidung D, Übergabenotiz P16.9
- **[hoch]** P16.11: vier von fünf Bedingungen für ein brauchbares Basisnetz erfüllt (elf Schritte, eine Komponente, Euler zwei); Käfigmodellierung bleibt nachgeordnet. Offen an den Bauplan zurückgegeben: §25 kennt die neuen Operationen nicht, §6 sieht Änderungen an §2.5, §9, §12, §25, §31, §42 und ein neues §44 vor  
  _Prüfen:_ pytest tests/test_base_mesh.py -q; 3d-agent-bauplan.md §25, §31, §42 und auf ein §44 hin durchsuchen  
  _Ort:_ Entscheidung H2, §6, §15, Schluss der Übergabenotiz