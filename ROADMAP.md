# ROADMAP — Arbeitsliste

Abzuarbeiten von oben nach unten. Jeder Punkt ist so geschnitten, dass danach
die Suite grün sein kann. Details stehen im Bauplan (§-Verweise), Regeln in
`AGENTS.md`.

Legende: `[ ]` offen · `[~]` in Arbeit · `[x]` fertig und Suite grün

---

## P0 — Skelett

### Grundgerüst
- [x] Repository, Paketstruktur nach §8, `pyproject.toml`, Werkzeuge
- [x] Test: `core` ohne installiertes Qt importierbar
- [x] Test: keine deutschen Stämme in Bezeichnern (§4.1)
- [x] `core/types.py` — Verträge aus §9 vollständig, noch ohne Umsetzung
- [x] `core/errors.py` — Hierarchie aus §33.1, jede Ausnahme mit `suggestions`
- [x] `core/units.py` — `EPS_GEOM`, `EPS_DISPLAY`, `EPS_MATCH` (§11.2)
- [x] Startsatz Druckerprofile als Datentabelle (§38)
- [x] Protokollierung nach §33.2

### Register
- [x] `@register_op` mit allen Feldern aus §10
- [x] Erzeugung: Menü, Kontextmenü, Palette, CLI, Tool-Schema, Doku
- [x] Registerkonsistenztest (§35)

### Szene und Auswertung
- [x] `Scene`, `SceneObject`, `Parameter`, `Fit`, `Transaction`
- [x] Op-DAG mit `in`/`out`, lineare Darstellung
- [x] Auswertung als reine Funktion (§15.1), Test: zweimal = identisch
- [x] Objektzahländerung hält an statt zu raten (§15.2)
- [x] Undo/Redo auf Transaktionsebene (§15.5)
- [x] Abbruch ohne halb angewandte Ops (§15.6)
- [x] Cache über Op-Hash, RAM-Grenze, Plattencache — der Mesh-Codec des
      Plattencaches kommt mit dem Geometriekern (P2)

### Parameter
- [x] Ausdrucksgrammatik und eigener Auswerter — **kein `eval`** (§13, §32)
- [x] Zyklenerkennung
- [x] Test: alles außerhalb der Grammatik wird abgelehnt

### Projektdatei
- [x] Container `.p3d` nach §16.1
- [x] `format_version`, Migrationsgerüst, erste Beispieldatei
- [x] Prüfsummen, keine absoluten Pfade
- [x] Autosave und Absturzwiederherstellung (§38)

### Eingangsstufe
- [x] Op `load` mit den sechs Schritten aus §17.1
- [x] Einheitenheuristik mit Rückfrage über `ctx.ask`
- [x] Import-Obergrenzen mit klarer Meldung (§32)

### Testkorpus
- [~] `tests/data/` nach §34 anlegen, `README.md` mit Erwartungswerten — sechs
      Meshes und eine Projektdatei stehen; die übrigen brauchen Bausteine aus
      P2/P3 und sind in der README namentlich vermerkt
- [x] Alle Dateien selbst erzeugt oder frei lizenziert (`make_corpus.py`)

### Oberfläche
- [x] Grundfenster nach §2.5, drei Zonen, rechter Bereich ausblendbar
- [x] Viewport (Grundnavigation, drei Schemata §2.9)
- [x] Objektbaum, Parameterleiste, Verlauf
- [x] Statusleiste mit Maßen, Auswahl, Fortschritt, Abbrechen
- [x] Startbildschirm mit Ablagefeld und zuletzt geöffneten Projekten (§2.3)
- [x] Ziehen und Ablegen auf Fenster, Viewport, Objektbaum
- [x] Übersetzungsgerüst, deutsche und englische Fassung

### CLI
- [x] Befehle aus dem Register, `ask` als Abfrage, `progress` als Zeile

### Abschluss P0
- [x] Lizenzprüfung gegen Freigabeliste (§36) — `tests/test_licences.py`,
      Freigabeliste in `app/core/knowledge/data/licences.toml`,
      Drittlizenzen in `THIRD-PARTY-NOTICES.md`
- [x] Lizenzentscheidung getroffen, Name entschieden (§37.1) — **Formwerk**,
      proprietär (RS Digital, 2026), Bausteinbibliothek und Testkorpus MIT;
      alles Namensbezogene steht in `app/branding.py`
- [x] Alle Abnahmekriterien P0 aus §40 grün — `tests/test_acceptance_p0.py`
      (das Kontextmenü am Merkmal ist mit P3 belegt, Objekt-Kontextmenü steht)

---

## P1 — Sehen und Messen
- [x] Darstellungsmodi, Schattierung, Kameravoreinstellungen (§18.1)
- [x] Schnittebene **mit Capping**, Bildvergleichstest (§18.2) — der Nachweis
      läuft über Geometrie statt Pixel: die geschnittene Hälfte ist wasserdicht
      und hat genau das halbe Volumen, was ein Bild nicht unterscheiden könnte
- [x] Messwerkzeuge, Durchmesser über Feature, Bemaßungen (§18.3) — Abstand mit
      Fang auf Punkte und Kanten, Wandstärke über eigenen Raycast, Bemaßungen
      bleiben stehen; der **Durchmesser** wird mit P3 nicht gemessen, sondern am
      ausgewählten Merkmal abgelesen und in der Statusleiste gezeigt
- [x] Gizmo und Snapping — jede Manipulation erzeugt eine Op (§18.10); die
      Transformations-Ops aus P2 sind dafür vorgezogen, ein Zug wird zerlegt
      und als **eine Transaktion** eingetragen. Fang auf Fläche und Bohrungsachse
      kam mit P3 als Op `align_to_feature` (`core/geom/align.py`)
- [x] Paletten und Alternativkodierung, Test auf Farbunabhängigkeit (§19.1)
- [x] Tastaturnavigation, Befehlspalette (§19.2)
- [x] Helles und dunkles Thema, HiDPI (§19.3)
- [x] Leistungsziele Viewport (§31) — `tests/test_performance.py` misst gegen
      die absoluten Ziele und gegen den letzten Lauf auf derselben Maschine
      (Regressionsschwelle 25 %); die Bildrate im Viewport selbst misst VTK,
      nicht die Suite

## P2 — Operationen manuell
- [x] Reparatur-Ops gegen `broken_open`, `degenerate` — Löcher in Dreiecksgröße
      werden geschlossen, eine fehlende Wand wird ehrlich als offen gemeldet
- [x] Transformationen, Ausrichten (in P1 vorgezogen), druckoptimal orientieren
      als Normalen-Heuristik — der Befund weist sie als solche aus
- [x] Boolesche Ops mit Rückfallkette §17.2, Stufe und Startwert in der Op —
      alle vier Stufen einzeln erzwungen und geprüft
- [x] Bohrungs-Ops, Schneiden, Anordnen, Kollisionsprüfung
- [x] Export nach §29 einschließlich Namensschema und Exportprüfung
- [x] Orientierung vorerst als Normalen-Heuristik, in P3 ersetzt
- [x] Fehlerdarstellung als Vorschlag (§2.7) für alle Geometriefehler — jede
      Ausnahme trägt Vorschläge, die Oberfläche zeigt sie als Knöpfe
- [x] **Weg 1 aus §2.2 als Ende-zu-Ende-Test** — `tests/test_way_one.py`

## P3 — Wahrnehmung und Schichtanalyse
- [x] Feature-Erkennung (§21.1) gegen `plate_holes`
- [x] Provenienz-IDs und Zuordnung, `plate_holes_twin` als mehrdeutig — die
      Transformations-Ops melden ihre Bewegung (`OpResult.transform`), die
      Zuordnung nimmt die alten Merkmale erst mit und vergleicht dann; ohne das
      verlor jede Drehung alle Namen. Nachweis: zehn Ops hintereinander
- [x] Verwaisungsdialog über `ctx.ask`, Prüfung beim Öffnen — `core/scene/orphans.py`
      prüft beim Öffnen jeden Merkmalsverweis einmal, schreibt die Antwort in die
      Datei und fragt sie darum nicht bei jedem Lauf erneut
- [x] Steckbrief (§23)
- [x] Analysekarten (§18.4), Klick auf Warnung fährt die Kamera hin — sieben Karten
      in `core/perceive/maps.py`, Legende mit Zahlenbereich und Herkunft
- [x] Feature-Overlay mit Kontextmenü (`applies_to`) — Beschriftungen im Viewport,
      Merkmale als Kinder im Objektbaum, Kontextmenü aus dem Register. Das
      Hervorheben beim Überfahren braucht echte Mauszeiger-Ereignisse und fehlt
      noch; Anklicken und Auswählen stehen
- [x] Passungen anlegen und prüfen (§14)

### Schichtanalyse (§22)
- [x] `core/slice`: Ebene-Mesh-Schnitt, Konturverkettung — mit Shapely statt
      Clipper2, gleiche Aufgabe, schon in der Freigabeliste
- [x] Kennzahlen je Schicht: Fläche, Überhang, Inseln, Brückenweite, Minimalbreite
- [x] Test gegen analytisch bekannte Körper (Würfel, Zylinder, Kegel) auf 1 %
- [x] `island_tower.stl` wird erkannt
- [x] Orientierungssuche über hunderte Kandidaten, mit Startwert, abbrechbar
- [x] Analysekarten Überhang und Stützbedarf auf echte Werte umstellen — der
      Stützbedarf entscheidet über die Schichtanalyse, nicht über eine
      Normalenregel; die Säulenhöhe kommt aus demselben Raster wie die Wandstärke
- [x] Schichtenvorschau im Viewport (§18.10), ehrlich beschriftet
- [x] Herkunft jeder Kennzahl ausweisen (`internal`), nie mit G-Code vermischt —
      Legende und Prüfbericht weisen sie aus
- [~] Leistungsziele §31 für die Schichtanalyse — **nicht erreicht**, gemessen in
      `tests/test_performance.py`. Der Schnitt läuft jetzt über eine
      Dreiecks-Einsortierung nach Höhe statt Ebene für Ebene über das ganze Netz
      (7,6 s → 2,3 s bei 328 000 Dreiecken), das Ziel sind 300 ms bei 200 000.
      Es fehlt rund das Fünffache; die Zeit steckt in den Shapely-Aufrufen
      (Erosion für die Minimalbreite, Polygonaufbau) und ist ohne kompilierten
      Kern nicht zu holen. Gleiches Bild bei der Orientierungssuche (32 s statt
      20 s, weil sie nichts anderes tut als schneiden) und bei der Karte
      Wandstärke (8 s statt 3 s, und im Vordergrund statt im Hintergrund)

## P4 — Agent auf Säule C
- [ ] `LLMBackend`, Schlüssel im Schlüsselbund, lokal über Ollama
- [ ] Kontextaufbau nach §26.1
- [ ] Werkzeuge nach §26.2 einschließlich `ask_user` und `find_part`
- [ ] Vorschlag = eine Transaktion, Differenzansicht, Übernahme
- [ ] Chat-Transaktions-Kopplung (§26.3), verworfene Beiträge ausgegraut
- [ ] Herkunftsvermerke (§26.4)
- [ ] Agenten-Suite mit 15 Anfragen zu Säule C, davon 3 mehrdeutig

## P5 — Bausteinbibliothek
- [ ] `@register_part`, `PartFn`, `PartResult`
- [ ] Normteiltabelle als Daten, nicht im Code
- [ ] Dreizehn Bausteine (§24.1) mit Parameterbereichstests
- [ ] `to_scad()` je Baustein
- [ ] Katalog mit automatisch gerenderten Vorschaubildern (§24.3)
- [ ] `parts_version` in der Projektdatei, Änderungsverlauf je Baustein (§24.4)
- [ ] Beim Öffnen: geänderte benutzte Bausteine namentlich melden
- [ ] Eigene Bausteine aus dem Nutzerordner (§24.5), im Katalog gekennzeichnet
- [ ] Test: eigener Baustein reist nicht mit der Projektdatei
- [ ] Nachweis: kein Kernpfad benötigt OpenSCAD

## P6 — Säule A
- [ ] Agent erzeugt Op-Listen aus Bausteinen und Parametern
- [ ] OpenSCAD als Rückfallebene mit Quelltextprüfung (§32)
- [ ] Messung: Bausteinnutzung, Parameternutzung
- [ ] **Weg 2 aus §2.2 als Ende-zu-Ende-Test**

## P7 — Slicer-Rückkopplung und Kalibrierung
- [ ] G-Code auswerten (§28.1) als Gegenprobe zur internen Schätzung
- [ ] Abweichung über 15 % erscheint als Befund im Prüfbericht
- [ ] Herkunft der Kennzahlen im Bericht ausgewiesen (intern / G-Code)
- [ ] Toleranz-Testkörper und Varianten-Generator (§28.3)
- [ ] Materialprofile kalibrierbar, Durchschlag auf bestehende Projekte

## P8 — Erste Veröffentlichung
- [ ] Name entschieden, überall durchgezogen
- [ ] CI-Bauläufe, Signierung Windows, AppImage/Flatpak
- [ ] Erstinbetriebnahme (§38)
- [ ] Fehlerberichtsdialog mit Container-Anhang
- [ ] Drei Beispielprojekte = die drei Hauptwege
- [ ] Doku, Website, Lizenzhinweise
- [ ] Update-Hinweis beim Start

## P9 — Säule B und Farbe
- [ ] `MeshBackend`, ComfyUI lokal
- [ ] Reparaturkette für generierte Meshes
- [ ] Materialslots, Attributerhalt über Boolesche Ops und Voxelstufe
- [ ] Textur → Slots mit Startwert, 3MF-Export mit Farbgruppen
- [ ] **Weg 3 aus §2.2 als Ende-zu-Ende-Test**

## P10 — Auto Split mit Verstiftung
- [ ] Trennebene über die Schichtanalyse suchen (§22.3), dann konvexe Zerlegung
- [ ] Schnittflächen verschließen, Slots übertragen
- [ ] Passstifte mit kalibriertem Spiel, Passungspaare automatisch
- [ ] Anordnen und Explosionsansicht
- [ ] `oversized.stl` ohne Eingriff druckbar zerlegt

## P11 — Gehosteter Backend
- [ ] nur bei nachweisbarer Nachfrage, Umfang nach §27

## P12 — B-Rep-Kern
- [ ] Zweiter Kern, `kind` im Objekt, Übergang B-Rep → Mesh
- [ ] Fasen und Verrundungen, STEP rundreisefähig
