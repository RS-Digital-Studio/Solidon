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
- [x] `LLMBackend`, Schlüssel im Schlüsselbund, lokal über Ollama — kein
      Hersteller-SDK, der Transport ist austauschbar, deshalb läuft die ganze
      Schicht in der Suite ohne Netz
- [x] Kontextaufbau nach §26.1
- [x] Werkzeuge nach §26.2 einschließlich `ask_user` und `find_part` — die Ops
      kommen aus dem Register, `find_part` antwortet bis P5 ehrlich, dass die
      Bibliothek leer ist
- [x] Vorschlag = eine Transaktion, Differenzansicht, Übernahme
- [x] Chat-Transaktions-Kopplung (§26.3), verworfene Beiträge ausgegraut
- [x] Herkunftsvermerke (§26.4)
- [x] Agenten-Suite mit 15 Anfragen zu Säule C, davon 3 mehrdeutig —
      `tests/agent_cases.py`. Ohne Modell prüft die Suite, was die Schicht
      garantiert (Kontext, eine Transaktion, Rückfrage kommt an, Schemaprüfung
      vor der Rechnung); die Quote gegen ein echtes Modell misst
      `tools/run_agent_suite.py` und braucht einen Schlüssel
- [x] Regelsammlung §39 als Daten mit Version und Änderungsverlauf; jede
      Transaktion hält die Version fest
- [x] Dateiformat 2: der Chat liegt im Projekt, mit Umstellungsschritt und
      Beispieldatei je Version

## P5 — Bausteinbibliothek
- [x] `@register_part`, `PartFn`, `PartResult` — dazu Version und
      Änderungsverlauf je Baustein, und die Angabe, ob er Material wegnimmt
- [x] Normteiltabelle als Daten, nicht im Code — `data/standards.toml`
- [x] Dreizehn Bausteine (§24.1) mit Parameterbereichstests — der Test läuft
      über das Register, ein neuer Baustein ist ab der Deklaration abgedeckt
- [x] `to_scad()` je Baustein — als Ausgabeformat, ehrlich beschriftet: die
      Werte stehen zum Nachlesen darin, der Körper ist das exakte Netz
- [x] Katalog mit automatisch gerenderten Vorschaubildern (§24.3) — als SVG aus
      dem Baustein selbst, ohne 3D-Kontext und ohne neue Abhängigkeit
- [x] `parts_version` in der Projektdatei, Änderungsverlauf je Baustein (§24.4)
- [x] Beim Öffnen: geänderte benutzte Bausteine namentlich melden
- [x] Eigene Bausteine aus dem Nutzerordner (§24.5), im Katalog gekennzeichnet
- [x] Test: eigener Baustein reist nicht mit der Projektdatei
- [x] Nachweis: kein Kernpfad benötigt OpenSCAD — `tests/test_parts.py` baut
      alle dreizehn gegen manifold3d durch

## P6 — Säule A
- [x] Agent erzeugt Op-Listen aus Bausteinen und Parametern — dazu die
      Primitive aus §25 (`create_box`, `create_cylinder`, `create_sphere`),
      ohne die eine leere Szene keinen Anfang hat, und `at_feature`, um einen
      Baustein an ein erkanntes Merkmal zu setzen
- [x] OpenSCAD als Rückfallebene mit Quelltextprüfung (§32) — `include`, `use`,
      `import` und `surface` nur relativ und unterhalb des Arbeitsordners,
      eigener Ordner je Lauf, Zeitlimit, getrimmte Umgebung. Der Nachweis ist,
      dass abgewiesener Quelltext **keinen Prozess startet**
- [x] Messung: Bausteinnutzung, Parameternutzung — fünfzehn Anfragen zu Säule A
      in `tests/agent_cases.py`, damit dreißig insgesamt (§35); die Quote gegen
      ein echtes Modell zählt `tools/run_agent_suite.py --pillar A`
- [x] **Weg 2 aus §2.2 als Ende-zu-Ende-Test** — `tests/test_way_two.py`

## P7 — Slicer-Rückkopplung und Kalibrierung
- [x] G-Code auswerten (§28.1) als Gegenprobe zur internen Schätzung — Druckzeit,
      Material, Schichtzahl und das **gemessene** Stützvolumen aus den
      Typ-Kommentaren und der E-Achse. Was nicht in der Datei steht, bleibt
      unbekannt statt null
- [x] Abweichung über 15 % erscheint als Befund im Prüfbericht — und die
      Schätzung wird dabei nicht ersetzt, beide bleiben stehen (§28.2)
- [x] Herkunft der Kennzahlen im Bericht ausgewiesen (intern / G-Code)
- [x] Toleranz-Testkörper und Varianten-Generator (§28.3) — Passungsleiter,
      Wandstärkenleiter und Überhangfächer als Bausteine mit eigener Gruppe;
      der Varianten-Generator dreht einen Projektparameter durch und ordnet die
      Ausführungen an, ohne den Stapel anzufassen
- [x] Materialprofile kalibrierbar, Durchschlag auf bestehende Projekte — die
      Werte landen im Nutzerprofil, die mitgelieferten Startwerte bleiben
      unberührt, und weil Toleranzen Verweise sind, rechnen alte Projekte danach
      mit den neuen Werten

## P8 — Erste Veröffentlichung
- [x] Name entschieden, überall durchgezogen — alles Namensbezogene steht in
      `app/branding.py`
- [~] CI-Bauläufe, Signierung Windows, AppImage/Flatpak — `.github/workflows/`
      baut Windows und Linux, erst nachdem die Suite auf allen drei Plattformen
      grün ist; die Signierung überspringt sich ohne Zertifikat. **Ungeprüft**,
      weil dieses Repository noch nicht auf einem CI-Dienst liegt; AppImage und
      Flatpak fehlen, das Linux-Paket ist bisher der PyInstaller-Ordner
- [x] Erstinbetriebnahme (§38) — Sprache, Drucker, Material, externe Programme;
      überspringbar, nachholbar, endet beim ersten Import
- [x] Fehlerberichtsdialog mit Container-Anhang — legt einen Ordner an,
      verschickt nichts, und sagt beim Anhängen der Projektdatei, dass die
      Geometrie mitreist
- [x] Drei Beispielprojekte = die drei Hauptwege — erzeugt von
      `tools/make_examples.py`, geprüft von `tests/test_examples.py`, sichtbar
      auf dem Startbildschirm
- [~] Doku, Website, Lizenzhinweise — README mit Erwartungsmanagement, den drei
      Wegen, Paketierung und einem Supportkanal; Lizenzhinweise vollständig.
      **Eine Website gibt es nicht**, und die Adresse in `core/updates.py` ist
      bisher ein Platzhalter
- [x] Update-Hinweis beim Start — fragt eine Versionsdatei, lädt nichts, und ist
      aus, bis ihn jemand einschaltet

## P9 — Säule B und Farbe
- [x] `MeshBackend`, ComfyUI lokal
- [x] Reparaturkette für generierte Meshes
- [x] Materialslots, Attributerhalt über Boolesche Ops und Voxelstufe
- [x] Textur → Slots mit Startwert, 3MF-Export mit Farbgruppen
- [x] **Weg 3 aus §2.2 als Ende-zu-Ende-Test**

Anmerkungen zu P9:

* **Erzeugtes wird Quelle, nicht Operation.** Ein Generator ist keine Funktion —
  dieselbe Anfrage liefert nach einem Modellwechsel etwas anderes. Die Bytes
  liegen deshalb im Projekt wie eine gezogene Datei, und der Stack darüber ist
  der gewöhnliche (`load`, dann `repair`). Prompt und Startwert stehen in der
  Quelle; dafür ist das Dateiformat auf 3 gestiegen.
* **Die Reparaturkette steht im Stack**, nicht im Backend. Sie läuft ohne
  Nachfrage, ist aber ein eigener Schritt — sichtbar im Bericht und
  zurücknehmbar.
* **Beim Schnitt gibt nur her, wer bleibt.** Bei einer Differenz überträgt der
  abgezogene Körper seine Farbe nicht: die Bohrungswand ist eine neue Fläche,
  keine Haut des Bohrers.
* **Die eigene 3MF-Hälfte.** trimesh liest 3MF-Geometrie, gibt aber ein
  einheitliches Grau zurück — Schreiben *und* Lesen der Materialgruppen liegen
  darum in `app/core/export/threemf.py`.
* Die mitgelieferten ComfyUI-Arbeitsabläufe (`app/core/backends/data/*.json`)
  sind ein Startpunkt für Hunyuan3D. Wer andere Knoten installiert hat, ersetzt
  die Datei — Quelltext ist dafür nicht nötig.

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
