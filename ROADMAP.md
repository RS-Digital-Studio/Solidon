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
- [x] `tests/data/` nach §34 anlegen, `README.md` mit Erwartungswerten — der
      Rest kam mit den Bausteinen aus P2/P3 nach, siehe „Referenzkorpus und
      Passungen vervollständigt"
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
- [x] Lizenzentscheidung getroffen, Name entschieden (§37.1) — **Solidon**,
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
- [~] Leistungsziele §31 für die Schichtanalyse — **zwei von dreien offen**,
      gemessen in `tests/test_performance.py`. Die Orientierungssuche (16,5 s)
      liegt im Ziel; die Wandstärkenkarte steht bei 3,08 s im Hintergrund und
      damit knapp über den drei Sekunden aus §31 — der Assert dort greift erst
      bei acht, hält also nur die Regression auf, nicht das Ziel. Die
      Schichtanalyse steht bei 1,05 s auf 328 000 Dreiecken, wo §31 für 200 000
      dreihundert Millisekunden nennt. Die Zahlen und die vier Änderungen, die
      dorthin führten, stehen unter „Leistung (§31) — Stand nach der
      Durchsicht". Was übrig ist, ist der Polygonaufbau in GEOS und braucht
      einen kompilierten Kern, keine weitere Python-Idee

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
- [x] **Druckeinstellungen in der Anwendung** (§29) — `PrintSettings` hält
      Schichten, Wände, Füllung, Temperaturen, Kühlung, Geschwindigkeiten,
      Stützen, Haftung, Rückzug und Filament samt Farbe; aufgelöst aus
      Qualitätsstufe, Material und Drucker. Der Dialog zeigt vorn acht Werte,
      dahinter alles nach Gebieten
- [x] **Hinweg zum Slicer** (§29) — `export/handover.py` schreibt das Profil,
      ruft den Slicer im Konsolenmodus und liest den G-Code zurück. Drei
      Familien über `export/slicer_keys.py`: PrusaSlicer und SuperSlicer als
      eigenständige ini, Orca/Bambu/Elegoo als Prozess-JSON auf ein
      Systemprofil gelegt, CuraEngine über `-s`
- [x] **Einstellungen aus der Geometrie** (§29) — `slice/advise.py` schließt
      aus Schichtanalyse, Material und Maschine auf Stützen, Plattenhaftung,
      Mindestschichtzeit, Linienbreite und Außenwandtempo. Jeder Vorschlag mit
      Begründung, übernommen wird auf Klick. Was kein Wert behebt, wird ein
      Befund statt eines Vorschlags
- [x] **Maschinen- und Prozessprofil des Slicers wählbar** (§29) —
      `export/slicer_profiles.py` liest den Bestand des installierten Slicers,
      löst die Erbkette der Verträglichkeit auf und ordnet über `printer_model`,
      Düse und `default_print_profile` selbst zu. Die Auswahl steht im Dialog
      für den Fall, dass jemand abweichen will; gelesen wird im Hintergrund
- [x] **Volumenstrom als Grenze** (§29) — `max_flow` je Material, gegen
      Schichthöhe mal Bahnbreite mal Tempo geprüft. Darüber Düse heißer,
      und wo die Maschine am Anschlag ist, stattdessen langsamer. Die Regel
      rechnet gegen den Stand *nach* den übrigen Vorschlägen, und die Zahl
      reist als `filament_max_volumetric_speed` zum Slicer mit
- [x] **Druckeinstellungen im Projekt** (§29) — `format_version` 4 mit
      Migration; `None` heißt „noch nichts entschieden", nicht „alles null".
      Beispieldatei `example_v4.p3d` eingecheckt
- [x] **Druckdatei speichern** — was der Slicer schreibt, lag im Arbeitsordner
      und verschwand mit ihm. Jetzt speicherbar, mit Ordner und Name des
      Projekts als Vorschlag
- [x] **Vorschläge einzeln wählbar** — vorbelegt angehakt, aber abwählbar;
      alles-oder-nichts hieße, für einen unpassenden Vorschlag die übrigen
      mit aufzugeben
- [x] **Nur die gewählte Plattenhaftung bekommt Maße** — Skirt, Brim und Raft
      sind Maße ihrer Art, keine Schalter. Vorher lief unter jedem Teil ein
      Raft mit, auch bei eingestelltem Skirt
- [x] **3MF als Baugruppe schreiben** (§20, §29) — `threemf.write_assembly`
      legt mehrere Körper in eine Datei, ein `object` je Teil. Der Slicer
      bekommt damit einen Druckauftrag statt einer Handvoll Teile, über deren
      Zusammengehörigkeit er selbst entscheiden müsste
- [x] **Farbgruppen als Extruderzuordnung** (§20) — `merge_slots` legt die
      Materialslots aller Teile über Name und Farbe zusammen; die Reihenfolge
      des Ergebnisses ist die Extruderbelegung. Ohne das fragte der Slicer
      nach drei Filamenten für einen einfarbigen Druck aus drei Teilen
- [x] **Gegenprobe statt einmaliger Prüfung** (§28.2) — `handover.verify`
      liest die Konfigurationskommentare der erzeugten Datei und meldet, was
      der Slicer anders übernommen hat. Damit prüft sich jeder Slicer selbst,
      auch einer, den beim Bauen der Tabelle niemand vorliegen hatte
- [x] **Jeder Wert in das Profil, in das er gehört** (§29) — die Orca-Familie
      führt Prozess und Filament getrennt und übergeht einen Wert im falschen
      Profil stillschweigend. Achtzehn taten das: beide Düsen- und beide
      Betttemperaturen, die ganze Kühlung, alle Filamentwerte und der Rückzug.
      Sie standen im Prozessprofil und kamen nie an — gedruckt wurde mit dem,
      was zuletzt im Slicer stand. `slicer_keys.Entry` trägt jetzt die
      Profilart, `handover` schreibt zwei Dateien und lädt das Filament über
      `--load-filaments`. Der Rückzug geht als `filament_*`-Entsprechung, damit
      Solidon nicht ins Maschinenprofil hineinredet — das passt auch zur
      Herkunft, denn er kommt aus dem Material. `test_every_orca_setting_sits_in_the_profile_it_claims`
      prüft die Zuordnung gegen den Bestand eines installierten Slicers und
      wäre am alten Stand mit achtzehn Verstößen rot gewesen
- [x] **Filamentprofile des Slicers lesen** (§29) — `slicer_profiles` kennt
      jetzt auch `filament/`, löst mit `resolve_values` die Erbkette auf (beim
      transluzenten Elegoo-PETG 55 Werte aus vier Dateien, wo die oberste drei
      nennt) und wählt über `match_filament` die Grundausführung des
      eingestellten Materials vor. Der Dialog zeigt sie zur Auswahl, `handover`
      legt die Solidon-Werte darauf. Gelesen werden Filamente nur auf
      Verlangen: sie vervielfachen den Bestand, 5962 gegen 3887.
      `profile_differences` meldet, wo Solidons Tabelle und der Hersteller
      auseinandergehen — 240/80 °C gegen 255/70 °C beim transluzenten PETG —,
      übernimmt aber nichts davon
- [x] **Die Stellschrauben, die für Passungen zählen** (§29) — `wall_generator`,
      `precise_outer_wall`, `ironing`, Brückentempo und zwei Beschleunigungen,
      mit Vorgaben je Qualitätsstufe. Dazu drei Regeln in `advise.py`:
      schmalste Stelle unter drei Linienbreiten schaltet auf Arachne (mit
      fester Linienbreite bleibt dort eine Lücke, die nur Lückenfüllung
      schließt — der Bruch eines 1,1-mm-Federarms), Passungen holen die genaue
      Außenwand und bremsen auf 2000 mm/s², Überhänge deckeln das Brückentempo
      auf das der Außenwand. Elefantenfuß und Lochkorrektur blieben draußen:
      für den ersten gibt es `compensate_elephant_foot` in der Geometrie, die
      zweite hat bisher gar keinen Anwender — beides zu übergeben hieße,
      doppelt zu rechnen
- [x] **Einstellungen je Teil** (§29) — `AssemblyPart.settings` trägt, was nur
      für ein Teil gilt, und `write_assembly` schreibt dafür
      `model_settings.config`. `advise.for_part` entscheidet die Plattenhaftung
      je Teil aus Bounding-Box und einem Schnitt 0,2 mm über dem Boden: ein
      Körper auf drei schmalen Armen hat eine große Bounding-Box und kaum Halt.
      Damit bekommt die Streuscheibe ihren Brim und keiner der zwölf Behälter.
      Nebenbei kamen damit auch die **Objektnamen** erstmals im Slicer an — sie
      standen im `name`-Attribut des Standards, das die Orca-Familie selbst nie
      schreibt und folglich nicht liest; eine Baugruppe erschien als
      „Object 1, Object 2"
- [x] **Platten aus Materialgruppen** (§25, §29) — `plates_by_material`
      schlägt ein Filament je Platte vor, `check_adhesion_clearance` rechnet
      den Haftungsrand mit (zwei Körper können Luft haben und ihre Brims
      trotzdem ineinanderlaufen — daran war die erste Deckelplatte des
      Gewürzsets zu eng), und `check_filament_changes` nennt den Preis zweier
      Filamente auf einer Platte, statt ihn zu verbieten: 110 gemeinsame
      Schichten und 220 Wechsel, wenn ein 68-mm-Behälter neben einem
      22-mm-Deckel steht. Die Spülmenge in Gramm bleibt draußen, sie steht im
      Profil des Slicers
- [x] **Das Gewürzset aus Solidon heraus gebaut** — die Probe auf die fünf
      Stufen, gegen das von Hand entstandene Projekt. Plattenvorschlag,
      Profilzuordnung und die Werte stimmten; die Automatik traf sogar die
      bessere Entscheidung als die Handarbeit (Brim gehört unter die
      Deckelbasis mit 282 mm² Standfläche, nicht unter die Streuscheibe mit
      516). Gefunden wurden dabei drei Dinge: das Regal-STL liegt nicht
      zentriert und stand über den Bauraum, `nil` wurde als Abweichung vom
      Herstellerprofil gemeldet statt als Nicht-Aussage, und `arrange_bed`
      kennt den Haftungsrand nicht. Die ersten beiden behoben, das dritte
      unten
- [x] Anordnung und Plattenhaftung zusammenbringen — der Dialog des Anordnens
      öffnet mit dem Abstand, den die Haftung verlangt (zweimal den Rand),
      vorbelegt und änderbar. Die Operation kennt die Druckeinstellung
      weiterhin nicht und soll es nicht; das Fenster kennt beide Seiten.
      **Vorher war das folgenlos**, siehe den nächsten Punkt: die Anordnung
      kam beim Slicer gar nicht an
- [x] Plattenvorschlag angeboten — `arrange_bed` trägt jetzt den Umschalter
      *Nach Filament trennen*, nicht eine zweite Operation daneben. Die
      Plattengrenze gilt der ganzen Szene; sind die Platten aufgebraucht,
      teilt sich die letzte Gruppe die letzte, wie `arrange_on_bed` es
      innerhalb einer Gruppe hält
- [x] Bügeln aus der Passung abgeleitet — `advise` bekam ein `has_fits: bool`,
      obwohl das Dokument die Arten führt. Jetzt reicht der Dialog sie durch,
      und nur `flush` löst den Vorschlag aus: bei Schiebesitz, Presssitz oder
      Gewinde wäre Bügeln verlorene Zeit auf einer Fläche, die nichts berührt
- [x] **PrusaSlicer läuft Ende zu Ende** (2.9.6, am 07.08.2026: 1,01 MB
      G-Code, 22,6 g, 110 min). Beide Funde davor waren unsichtbar, solange
      das Programm fehlte: die Programmsuche ging eine Ebene zu flach für
      `Prusa3D\PrusaSlicer\`, und die Bettform stand von 0 bis 256, während
      Solidon um den Ursprung rechnet — „All objects are outside of the
      print volume", ohne dass irgendwo stand, warum
- [x] **Cura läuft Ende zu Ende** (5.13.0). Die Kette hatte fünf Stufen:
      - [x] Der Aufruf ging an `UltiMaker-Cura.exe`, also an die Oberfläche.
            Die Kommandozeile hat nur `CuraEngine.exe` daneben
      - [x] `CuraEngine` liest **kein 3MF** — die 3MF-Seite sitzt im Frontend.
            Für Cura schreibt die Übergabe STL
      - [x] `fdmprinter.def.json` als Basis reicht, wenn die Werte mitkommen,
            die es ohne Vorgabe lässt. Gefunden durch Zufüttern, bis der
            Rückgabewert 0 war: Bauraum, Düse, `machine_center_is_zero`,
            `roofing_layer_count`, `flooring_layer_count`. `_cura_base()` sucht
            die Datei unter `share/cura/resources/definitions`
      - [x] **Der Lauf fördert — er sagte es nur nicht.** Der Befund
            „8,6 MB Leerfahrten" war eine Fehldeutung des Kopfes: die Datei
            enthält Bahnen mit Vorschub, und `gcode.extrudes()` bestätigt das.
            `Filament used: 0m` und `MINX:2.14748e+06` sind **Vorlagen**, die
            CuraEngine vor dem Rechnen schreibt und das Fenster nachträglich
            ersetzt; von der Kommandozeile aus bleiben sie stehen. Dasselbe
            gilt für `;TIME:6666` — 111 Minuten für jedes Modell, auch für
            einen halb so hohen Würfel. Solidon liest die Länge jetzt aus der
            E-Achse und die Zeit aus der letzten `TIME_ELAPSED`.
      - [x] **Die Werte erreichten den Extruder nicht.** CuraEngine hält zwei
            Ebenen, und das meiste, was einen Druck ausmacht, liest es vom
            Extruder-Zug. Was nur global stand, wurde von der Vorgabe der
            Definition überschrieben. Dazu zwei Einzelfehler: die erste
            Bahnbreite ist dort ein **Anteil** (0,449 mm wurden zu 0,449 %),
            und Beschleunigungswerte gelten erst mit `acceleration_enabled`.

            Gemessen am 20-mm-Würfel gegen PrusaSlicer, dieselben
            Einstellungen:

            | Stand | Filament | Volumen | Zeit |
            |---|---|---|---|
            | vorher | 748 mm | 1,80 cm³ | 111 min (Vorlage) |
            | jetzt | 1998 mm | 4,81 cm³ | 20,9 min |
            | PrusaSlicer | 1410 mm | 3,39 cm³ | 21 min |
            | Handrechnung | — | rund 3,3 cm³ | — |

            Die Zeit trifft jetzt auf die Minute. Was an Material bleibt, ist
            **Curas Rechnung, nicht Solidons Fehler**: mit `infill_pattern=lines`
            statt `grid` kommen 3,70 cm³ heraus, also neun Prozent neben
            PrusaSlicer — der Rest steckt in Curas Gitter-Muster bei 15 %
            Dichte. Nur auf dem Zug zu setzen ist ebenso falsch wie nur global:
            dann fehlen der Zeitrechnung die Geschwindigkeiten (38,4 min).

## P8 — Erste Veröffentlichung
- [x] Name entschieden, überall durchgezogen — alles Namensbezogene steht in
      `app/branding.py`
- [~] CI-Bauläufe, Signierung Windows, AppImage/Flatpak — `.github/workflows/`
      baut Windows und Linux, erst nachdem die Suite auf allen drei Plattformen
      grün ist. Windows wird zu einer Setup-Datei (`packaging/solidon3d.iss`,
      gebaut von `tools/make_installer.py`, das die Werte aus
      `app/branding.py` liest), Linux zu einem tar.gz, weil der
      Artefakt-Upload sonst die Ausführungsrechte verliert; Anwendung und
      Installer werden signiert, der Schritt überspringt sich ohne Zertifikat.
      **Ungeprüft**, weil dieses Repository noch nicht auf einem CI-Dienst
      liegt; AppImage und Flatpak fehlen. Der Grund, der hier stand — es gebe
      kein Anwendungssymbol —, gilt nicht mehr: `app/images/icon/solidon3d.svg`
      ist die Quelle, `tools/make_icon.py` rastert daraus `packaging/solidon3d.ico`
      und `website/icon.svg`, und Installer wie exe tragen es. Offen sind allein
      die beiden Linux-Formate
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
      Die Adresse in `core/updates.py` steht seit der Subdomain-Entscheidung.
      **Hochgeladen seit dem 08.08.2026**: netcup Webhosting samt Domain
      bestellt, 86 Dateien nach `solidon3d.de/httpdocs`, Auslieferung per
      Host-Header geprüft (Startseite, `en/`, Handbuch, `version.json` als
      JSON — alle 200). Impressum, Datenschutz und Widerruf tragen echte
      Angaben statt Platzhaltern. **Seit dem 08.08.2026 auch verschlüsselt**:
      Let's Encrypt für `solidon3d.de` und `www.solidon3d.de` (ein Zertifikat,
      beide Namen im SAN, bis 06.11.2026), HTTP antwortet für beide mit 301 auf
      HTTPS. Die DNS-Propagation ist durch — beide A-Records auf 188.68.47.33,
      Zone bei netcup.

      Ein Umweg war dabei zu vermeiden: Plesk hatte ein **Platzhalter**-
      zertifikat angeboten, und nur dafür verlangt Let's Encrypt die
      DNS-Challenge samt TXT-Eintrag. Für die zwei Namen genügt HTTP-01, und
      das läuft ohne jeden Eintrag. Eine Datei `_acme-challenge.txt` im
      Webspace hilft dabei nicht — eine DNS-Challenge wird im DNS abgefragt.

      Offen: Postfach `support@solidon3d.de` samt SPF/DMARC und der
      Auftragsverarbeitungsvertrag im CCP. Der Zahlungsdienstleister in den AGB
      ist seit dem 08.08.2026 eingetragen (Paddle); Entwurf bleiben die
      Rechtstexte nur noch bis zur fachlichen Prüfung
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
- [x] Trennebene über die Schichtanalyse suchen (§22.3), dann konvexe Zerlegung
- [x] Schnittflächen verschließen, Slots übertragen
- [x] Passstifte mit kalibriertem Spiel, Passungspaare automatisch
- [x] Anordnen und Explosionsansicht
- [x] `oversized.stl` ohne Eingriff druckbar zerlegt

Anmerkungen zu P10:

* **Was eine Trennebene gut macht, ist nicht ihre Größe.** Bewertet werden drei
  Dinge: eine Kontur statt fünf dünner Brücken, ein prismatischer Verlauf (der
  Querschnitt ändert sich über einen Millimeter kaum) und Ausgewogenheit. Die
  Konturzahl wiegt am schwersten — eine Naht, die in mehrere Stege zerfällt,
  ist schlimmer als jede Unwucht.
* **Die konvexe Zerlegung liefert einen Hinweis, kein Ergebnis.** Ihre Hüllen
  nähern den Körper an; ein aus Näherungen zusammengeklebtes Teil wäre ein
  genähertes Teil. Übernommen wird nur die *Position*, geschnitten wird exakt
  mit einer Ebene. Sie wird erst gefragt, wenn keine der abgetasteten Ebenen
  überzeugt.
* **Ein Fund unterwegs:** `_plane_segments` in der Schichtanalyse rechnete den
  Layer-Index aus `heights[1] - heights[0]` — richtig für gleichmäßige
  Schichten, still falsch für die ungleichmäßigen Höhen der Ebenensuche. Jetzt
  über `searchsorted`; die Schichtanalyse ist der Sonderfall.
* **Auto Split ist ein Ablauf, kein einzelner Op.** Pro Schnitt eine
  `split_pinned`-Operation, damit jede Trennebene eine Zahl bleibt, die man
  danach ändern kann. Die Passungspaare entstehen im Ablauf, weil Passungen im
  Dokument leben und die Auswertung eine reine Funktion bleibt (§15.1).
* Die Explosionsansicht verschiebt nur Punkte auf dem Weg in die Anzeige. Was
  der Stack sagt und was exportiert wird, bleibt unberührt.

## Gegen echte Modelle geprüft

68 Modelle aus einem privaten Druckordner (106 MB, STL und 3MF, von der
Torschloss-Adapterkappe bis zur Community-Katze mit 13,4 Millionen Dreiecken)
durch die ganze Kette. `tools/run_model_suite.py` macht denselben Lauf mit
einem Bericht statt Zusicherungen; `tests/test_real_models.py` hält die Funde
fest und überspringt sich, wo der Ordner fehlt.

**Alle 68 laufen durch.** Drei Dinge kamen trotzdem heraus:

* Ein Modell mit 13,4 Millionen Dreiecken brauchte 100 Sekunden und **sagte
  nichts dazu**. Es wird nicht abgelehnt — die Grenze dafür liegt bei 20
  Millionen — aber ab 500 000 sagt die Eingangsstufe jetzt, dass Analysekarten
  und Merkmalserkennung ab hier ablehnen und dass Dezimieren hilft.
* Sechs von 68 sind nicht geschlossen. Das ist bei Community-Modellen normal
  und wird korrekt gemeldet.
* Die Kollisionsprüfung verglich nur Hüllquader. Ein Stab, der frei in einer
  Nut steht, war damit eine Kollision — bei jeder Baugruppe, die ineinander
  greift. Jetzt zweistufig: Boxen als Vorfilter, danach der Kern. Ein leerer
  Schnitt ist dabei die Antwort, nicht der Fehlschlag, den die Rückfallkette
  daraus macht.

## Referenzkorpus und Passungen vervollständigt

Der Korpus aus §34 ist jetzt komplett: `broken_selfint.stl` (zwei Würfel, die
sich durchdringen), `colored.3mf` (zwei Materialgruppen, mit der eigenen
3MF-Hälfte geschrieben) und `assembly_fit.p3d` (Platte, Deckel, Passungspaar).
Beim letzten sind die Zahlen die Lehre: 6 mm Bohrung wird 6,2 wegen der
Kompensation, PETG will 0,25 Spiel, also ist der Stift 5,95 — und in einem
anderen Material meldet sich die Passung von selbst.

Dabei kam heraus, dass **`flush` als Passungsart nie geprüft wurde**: angenommen,
abgespeichert und stillschweigend übersprungen. Jetzt wird der Abstand der
zweiten Fläche von der Ebene der ersten gemessen — die Zahl, die man mit einem
Haarlineal über die Baugruppe findet. Zwei Flächen, die nicht parallel stehen,
sind ein anderer Fehler und werden als solcher gemeldet.

**Zur Paketgröße:** 749 MB im Ordner, **255 MB gepackt** — das ist die Zahl, die
jemand herunterlädt, und sie liegt im Rahmen vergleichbarer Anwendungen. VTK von
Hand zu beschneiden würde davon vielleicht 50 MB sparen und dafür Abstürze in
selten benutzten Pfaden riskieren, die erst beim Nutzer auffallen. Bewusst
gelassen.

## Durchsicht nach P12 — was noch offen ist

**Vollständigkeit gegen §25.** Der Abgleich der Kategorienliste mit dem
Register hat neun Operationen aufgedeckt, die der Plan nennt und die es nicht
gab — die Kategorien „Netz" und „Beschriftung" waren leer, und der
Variantengenerator war gebaut, getestet und von keiner Oberfläche erreichbar.
Alle neun sind jetzt da: Spiegeln, Dezimieren, Glätten, Neu vernetzen,
Aushöhlen mit Entlüftung, Elefantenfuß ausgleichen, Senken, Bohrung
verschließen, Text aufbringen, Zeichnung extrudieren (SVG und DXF) — dazu der
Weg zum Variantengenerator.

Das ist zugleich die Antwort auf „je mehr in der App statt außen": Beschriftung
und Umriss-Extrusion sind die zwei häufigsten Gründe, ein zweites Programm zu
öffnen. Beide brauchen jetzt keines mehr.

**Behoben in dieser Runde**

* Anordnen und Kollisionsprüfung liefen auf einer leeren Eingabeliste — sie
  sind `consumes=0, produces=VARIABLE`, bekamen von der Oberfläche aber keine
  Objekte. Die Regel steht jetzt einmal im Register (`takes_whole_scene`).
* Die Suite las die echten Nutzerverzeichnisse. Ein kalibriertes Material auf
  dem Entwicklerrechner änderte, was die Tests sehen — und ein Testlauf ließ
  Kalibrierungen im Profilordner zurück.
* Der Signierschritt der CI hätte nie ausgelöst: `env` einer Schrittdefinition
  ist in deren eigenem `if` nicht lesbar. Jetzt auf Job-Ebene.
* Die CI installierte kein `brep` — die B-Rep-Tests hätten sich dort still
  übersprungen und der Kern wäre nie geprüft worden.
* Die Paketierung sah OCP und V-HACD nicht: beide werden absichtlich erst in
  der Funktion importiert, und PyInstaller liest nur Importe auf Modulebene.
  Ein gebautes Paket hätte stillschweigend keine Verrundungen gehabt.

**Bewusst offen**

* **Schichtanalyse 1,7 s statt 300 ms** (§31). Was übrig ist, sind Polygonaufbau
  und Mengenoperationen in GEOS. Das braucht einen kompilierten Kern; der Wert
  ist festgehalten, ein Rückschritt fällt auf.
* **CI nie gelaufen.** Es gibt kein Remote — die Datei ist geprüft (YAML
  geparst, Bedingungen nachgerechnet), aber nicht ausgeführt. Beim ersten Push
  auf einen Server ist damit zu rechnen, dass Kleinigkeiten auftauchen.
  *Überholt am 02.08.2026: das Repository liegt auf GitHub, die CI ist
  gelaufen — siehe „Der erste echte CI-Lauf". Der Satz bleibt stehen, weil er
  richtig vorhergesagt hat, was dann passierte: es waren vier Kleinigkeiten.
  Offen ist allein der `workflow_dispatch`-Lauf über alle drei Plattformen.*
* **Keine Website** (§37.3). Marketing, kein Programmteil; kommt, wenn es
  etwas zu veröffentlichen gibt.
* **Der Slicer bleibt außen** (§22.5, §28). Ein eigener G-Code-Generator wäre
  fünfzehn Jahre fremde Arbeit schlechter nachgebaut; die Schichtanalyse sucht
  und bewertet, die Druckdatei kommt weiter aus dem Slicer.

## Leistung (§31) — Stand nach der Durchsicht

Gemessen auf einer Kugel mit 328 000 Dreiecken (§31 nennt seine Ziele für
200 000), Werte in `tests/.performance.json`:

| Messung | §31 | vorher | jetzt |
|---|---|---|---|
| Schichtanalyse, 0,2 mm | 300 ms | 2,35 s | **1,05 s** |
| Wandstärkenkarte | 3 s, im Hintergrund | 8,18 s, im Vordergrund | **3,08 s, im Hintergrund** |
| Orientierungssuche, 200 Lagen | 20 s | 32,2 s | **16,5 s** |
| Feature-Erkennung | 1 s | 0,44 s | 0,44 s |
| Auswertung aus dem Cache | 1 s | 0,3 ms | 0,3 ms |

Vier Änderungen. Drei nach dem Muster **nicht rechnen, was niemand liest**, eine
nach **das Vorhandene benutzen**:

* Die Wandkarte hat ihr Raster Schicht für Schicht geschnitten und dabei alle
  328 000 Dreiecke dreihundertmal durchlaufen. Jetzt ein Durchgang über alle
  Höhen — von 8,2 s auf 3,1 s, und damit im Ziel.
* Die Orientierungssuche liest aus jeder Schicht genau eine Zahl. Sie fragt
  jetzt `detail="support"` an, und die Strukturbreiten entfallen: 32 s → 16,5 s,
  ebenfalls im Ziel.
* Die Suche nach der kleinsten Strukturbreite hört auf, sobald eine Schicht
  dicker ist als alles, wovor §22.2 warnt. Ob eine Wand vier oder neun
  Millimeter hat, fragt kein Bericht — die Suche danach kostete mehr als der
  Rest der Schichtanalyse zusammen.

* **GEOS gibt die GIL frei.** Das Messen der Schichten läuft jetzt auf so vielen
  Threads, wie die Maschine hat: 1,73 s → 1,05 s. Gemessen, nicht vermutet —
  0,81 s auf einem Thread gegen 0,15 s auf acht.

Dieselbe Idee auf den Polygonaufbau angewandt war **langsamer** (0,758 s gegen
0,714 s): einzelne Polygone zu bauen hält die GIL, anders als die vektorisierten
Prädikate beim Messen. Die Änderung ist wieder draußen, die Messung steht als
Kommentar an der Stelle — damit sie niemand nochmal versucht.

Offen bleibt die Schichtanalyse selbst: 1,05 s statt 300 ms, also rund 650 ms
für die Größe, die §31 nennt. Was übrig ist, ist der Polygonaufbau in GEOS; das
zu schließen braucht einen kompilierten Kern, keine weitere Python-Idee.

## P11 — Gehosteter Backend
- [–] **Bewusst nicht gebaut.** §27 knüpft diese Phase an nachweisbare
  Nachfrage; die gibt es nicht. Ein Dienst ohne Nutzer wäre Arbeit auf Vorrat,
  dazu ein Server, eine Abrechnung und eine Datenschutzzusage, die alle
  gepflegt werden müssten.

Was stattdessen sichergestellt ist: Die Schnittstelle steht schon so, dass ein
gehosteter Dienst sie ohne Änderung erfüllen könnte. `MeshBackend` kennt genau
`text_to_mesh` und `image_to_mesh` (§27) — kein Nutzercode, keine Dateipfade,
kein Zustand. Dass eine zweite Umsetzung daneben passt, ist keine Behauptung:
`ScriptedMeshBackend` ist genau das und trägt die ganze Weg-3-Abnahme.

Der Auslöser für diese Phase wäre: Nutzer, die erzeugen wollen und keine
Grafikkarte dafür haben, und die das auch sagen. Dann nach §27 — Text oder Bild
rein, Mesh raus, Eingaben nach Auslieferung löschen, Serverstandort EU.

## P12 — B-Rep-Kern
- [x] Zweiter Kern, `kind` im Objekt, Übergang B-Rep → Mesh
- [x] Fasen und Verrundungen, STEP rundreisefähig

Anmerkungen zu P12:

* **Ein `Solid` erfüllt dasselbe `Mesh`-Protokoll wie alles andere.** Ansicht,
  Prüfbericht, Schichtanalyse und Export arbeiten damit unverändert weiter.
  Wo der Kern es exakt weiß, antwortet er aber exakt: Volumen und Fläche kommen
  aus OpenCASCADE, nicht aus den Dreiecken — bei einer Verrundung ist der
  Unterschied nicht akademisch.
* **`kind` folgt dem Körper, nicht der Behauptung.** Die Auswertung setzt es
  nach jeder Operation aus dem tatsächlichen Objekt. Eine Netz-Operation auf
  einem exakten Körper bekommt die Vernetzung und liefert ein Netz zurück —
  und der Objektbaum sagt das dann auch.
* **Der Rückweg besteht nicht, aber ein Undo schon.** Die Umwandlung ist eine
  Operation im Stack; sie zurückzunehmen holt den exakten Körper zurück, weil
  neu gerechnet und nicht geflickt wird.
* **Merkmale kommen aus der Topologie**, nicht aus Clustern und Zylinderfits
  (§30). Eine Zylinderfläche wird nur dann als Bohrung gemeldet, wenn sie eine
  volle Umdrehung beschreibt — eine Verrundung ist auch ein Zylinder.
* **Kein Rückfallketten-Ersatz.** Die Kette aus §17.2 gibt es, weil Netze sich
  darüber uneinig sind, was innen ist. Zwei B-Rep-Körper sind das nicht; hier
  ist ein Fehlschlag ein echter Fehler und kein Anlass für einen gröberen
  Versuch.
* OpenCASCADE ist optional (`pip install -e ".[brep]"`). Ohne den Kern sagen
  die betroffenen Operationen das in einem Satz, alles andere bleibt unberührt.

## Aus dem Modellordner abgeleitet

Nicht aus dem Plan, sondern aus dem, was 68 echte Modelle zeigen. Zwei Dinge
kamen vor, für die man bisher aus Solidon heraus musste:

* **Prüfstück erzeugen** (`test_piece`). Ein Würfel um die Stelle, die man
  ausprobieren will, herausgeschnitten — nicht nachgebaut. Ausgeschnitten
  bleibt es die echte Geometrie mit der echten Toleranz; nachgebaut wäre es
  eine zweite Konstruktion, die anders druckt als das Teil, für das sie steht.
  Gemessen an einer gebohrten Platte: 20 × 20 × 8 mm, 2975 von 31 775 mm³,
  geschlossen, auf dem Bett.
* **Beschriftung in zwei Farben, auf beiden Wegen.** `label_text` bekam einen
  Materialslot — die Buchstaben tragen ihn in die Vereinigung, der
  Attributübergang aus P9 bringt ihn heraus, und der 3MF-Export macht daraus
  den Farbwechsel in *einer* Datei. Daneben `create_label`, das den Schriftzug
  als eigenes Objekt anlegt: für den Drucker, an dem von Hand gewechselt wird,
  und für Lettern zum Aufkleben. Welcher Weg besser ist, entscheidet der
  Drucker, also gibt es beide.

**Dabei aufgefallen — zwei Fehler, die still waren**

* **Die Rückfallkette hielt „nichts" für „gescheitert".** Für eine Differenz,
  die jemand wollte, ist ein leeres Ergebnis der Hinweis, dass der Kern
  aufgegeben hat, und die nächste Stufe ist richtig. Für einen Schnitt kann es
  die Antwort sein: die Körper treffen sich nicht. Das Prüfstück über einer
  Bohrung war damit kein Nutzerhinweis, sondern eine `BooleanFailedError` nach
  vier Stufen. `boolean(..., allow_empty=True)` sagt es jetzt einmal; die
  Stelle in der Kollisionsprüfung, die den Kern deshalb direkt fragt, hatte
  denselben Grund.
* **Die konvexe Zerlegung lief nie.** Der Aufruf übergab ein `randomizeSeed`,
  das dieses V-HACD nicht kennt; der `TypeError` wurde als „Modul fehlt"
  gelesen, die Funktion gab eine leere Liste zurück, und der Test übersprang
  sich mit „optionale Abhängigkeit". Damit war der Hinweispfad der
  Trennebenensuche seit P10 tot — hinter einer grünen Suite. Der Aufruf stimmt
  jetzt (das L zerfällt in vier Stücke), der Test überspringt sich nicht mehr,
  und weil dieses V-HACD keinen Zufallsregler hat und nachgemessen
  deterministisch ist, ist die `seed`-Kette durch sechs Signaturen ersatzlos
  weg statt weiter mitgeschleppt.

## Eine Szene ist nicht ein Material

Der dritte Fund aus dem Modellordner, und der einzige, bei dem bisher etwas
**falsch** gerechnet wurde statt nur zu fehlen: Baugruppen mit einer TPU-
Dichtung in einem PETG-Gehäuse. Toleranz, Schwund und Elefantenfuß kamen für
beide Körper aus dem Projektmaterial.

`SceneObject.material` trägt das jetzt am Körper, `profiles.for_object` löst es
auf, und `set_material` setzt es als Operation im Stack — damit gilt §11 weiter:
kein verstecktes Attribut, rücknehmbar, im Projekt gespeichert.

Was daran hängt:

* **Passungen.** `auto:` heißt „das, worin das hier gedruckt wird", und das sind
  bei zwei Körpern zwei Antworten. Wo sie sich unterscheiden, gewinnt der
  größere Wert — bei Spiel der weitere Spalt, bei Presssitz die *kleinere*
  Pressung, weil die Werte negativ sind. Eine Regel für beides, und beide Male
  die, deren Fehlschlag ein brauchbares Teil übrig lässt: was lose sitzt, kann
  man kleben; ein Gehäuse, das beim Fügen gerissen ist, ist Ausschuss. Ein
  ausgeschriebenes `auto:petg` bleibt, was dasteht — das hat jemand mit Absicht
  hingeschrieben.
* **Elefantenfuß.** TPU quetscht 0,25 mm breit, PETG 0,2. Auf einer Dichtung
  ist das der Unterschied zwischen dichten und nicht dichten.
* **Passstifte** nehmen das Spiel des geteilten Körpers, nicht das des Projekts.
* **Steckbrief und Objektbaum** nennen ein abweichendes Material; ein
  übereinstimmendes nicht, sonst steht es an jedem Körper und niemand liest es.
* **Cache.** Das Material steht im Objekt-Eintrag; ohne das käme nach einem
  Neustart der Körper mit dem alten Material zurück.

## Deckel aus der Öffnung — und ein Fehler, der darunter lag

Die vierte Funktion aus dem Modellordner: eine Schachtel ist da, ein Deckel
fehlt. Von Hand heißt das den Hohlraum abmessen, ihn eine Kleinigkeit kleiner
neu zeichnen und am Drucker erfahren, um wie viel die Kleinigkeit falsch war.

`create_lid` misst nicht, es schneidet: ein Querschnitt durch die Wand an der
Öffnung gibt die Außenkontur und den Hohlraum darin, die Platte ist die gefüllte
Außenkontur, der Kragen der Hohlraum minus dem Spiel aus dem Materialprofil
(§12). Damit entscheidet über den Deckel dieselbe Zahl wie über jede andere
Passung, und eine Kalibrierung nach §28.3 erreicht auch Deckel, die vorher
entstanden sind. Ein geteilter Kasten bekommt einen Kragen je Fach — das ist,
was den Deckel am Verdrehen hindert.

Nachgemessen an einem Gehäuse 60 × 40 × 30 mit 3 mm Wand: Kragen 53,10 × 33,10
(Hohlraum 54 × 34 minus zweimal 0,45), Deckel geschlossen, gemeinsames Volumen
mit dem Gehäuse **0,0 mm³** — er geht hinein.

**Der Fehler darunter.** Der erste Versuch bekam an jeder Höhe „hier schneidet
nichts". Der Grund lag nicht im Deckel, sondern in der Schichtanalyse: beim
Verschachteln der Ringe wurde gefragt, ob ein Punkt der *Außenkontur* eines
Teils in einem anderen liegt. Bei einer Schachtel ist die Außenkontur das äußere
Rechteck, und dessen Mitte liegt im Hohlraum — Wand und Hohlraum erklärten sich
gegenseitig zum Loch, beide kamen ungerade heraus, und ein Schnitt, den man
sehen kann, kam als `None` zurück.

Betroffen war **jede Schicht jedes hohlen Körpers**, und damit Wandkarte,
Überhänge und Stützvolumen. Der vorhandene Korpus hat es verdeckt, weil seine
Bohrungen außermittig sitzen: eine mittige Bohrung in einer Platte reicht schon.
Gefragt wird jetzt nach einem Punkt des Teils selbst, nicht seiner Hülle; drei
Tests halten den Fall fest.

**Dazu:** eine Berührung ist keine Überschneidung. Deckel auf dem Rand, Teil auf
der Platte, zwei Hälften eines Schnitts — der Durchschnitt ist ein flaches,
geschlossenes Blatt ohne Inhalt, und trimesh teilt beim Schwerpunkt durch dessen
Null. `boolean.shared_volume` beantwortet das einmal für alle, und die
Kollisionsprüfung benutzt es.

**Und ein zweiter Fall, den der erste Fix freigelegt hat.** Wo vorher früh
`None` zurückkam, werden jetzt Polygone gebaut — und drei Modelle des Korpus
haben eine Tasche, die genau bis an die Außenwand reicht. Das Loch trifft die
Außenkontur in einem Punkt, GEOS baut das Polygon klaglos und wirft bei der
nächsten Operation darüber eine `TopologyException` mit einer Koordinate und
sonst nichts. Geheilt wird jetzt dort, wo es entsteht (`buffer(0)`, weil eine
Fläche gesucht ist). Der Korpus läuft wieder **68 von 68** durch.

Die Prüfung im heißen Pfad kostet nichts Nennenswertes: Schichtanalyse 1076 ms
gegen 1062 ms, Wandkarte 3331 gegen 3226 — für Zahlen, die vorher für jeden
hohlen Körper gar nicht erst entstanden sind.

## Aus der Struktur des Modellordners

Die Runde vorher kam aus den Modellen. Diese kommt aus den *Dateinamen und
Ordnern*: `Versuch 1` neben `Versuch 2`, `Clippy_Filament-Clip_x10`,
`Wasserfall_1_Koerper` bis `_4_TPU-Liner`, `deckel_dreh` neben
`gewuerzbehaelter_body`. Was jemand in einen Dateinamen schreibt, ist das, wofür
das Programm keinen Platz hat.

### 3MF wurde falsch gelesen

22 der 3MF im Ordner nutzen die Produktions-Erweiterung: die Objekte liegen in
eigenen Dateien unter `3D/Objects/`, das Build verweist über Komponenten darauf.
trimesh löst eine solche Komponente auf die **ganze Datei** auf statt auf das
eine Objekt, das sie nennt. Nachgemessen:

| Datei | Dreiecke echt | gelesen | Faktor |
|---|---|---|---|
| Pool-Fountain_Nozzle_horizontal | 290 120 | 580 240 | 2,0 |
| Scraper_with_Magnets | 53 800 | 107 600 | 2,0 |
| Cat_Phone_Stand_Kawaii | 787 836 | 13 393 212 | **17,0** |

Kein Tempoproblem, sondern ein falsches Ergebnis: die Düse hat zwei Körper
(21,68 und 30,37 cm³), gelesen wurden vier — jeder deckungsgleich verdoppelt.
Volumen 104,11 statt 52,05 cm³, und damit Materialschätzung und Druckzeit
doppelt.

*Nachgemessen und dabei eine eigene Behauptung zurückgenommen:* die
Wasserdichtheit ist davon **nicht** betroffen. Zwei deckungsgleiche, aber nicht
verschweißte Kopien sind je für sich geschlossen, also bleibt die Datei dicht.
Dass die Düse als „nicht geschlossen" gemeldet wird, liegt an einem ihrer beiden
echten Körper — vorher wie nachher richtig.

Jetzt liest ein eigener Geometrieleser das Format — im 3MF-Modul, wo das übrige
3MF-Wissen schon steht. Dieselbe Katze: 787 836 Dreiecke in **2,6 s** statt
13,4 Millionen in 44,8 s.

### Ein 3MF ist eine Baugruppe

Auch richtig gelesen verschmolz alles zu einem Körper. `Wasserfall_.3mf` sind
vier Teile — Körper, Deckel, Tülle, TPU-Liner —, `Taschentuchbox` sind 21. Genau
die Aufteilung, die das Material pro Körper und die Platte pro Teil braucht. Die
Namen holt der Leser aus `Metadata/model_settings.config`, weil das die einzige
Stelle ist, an der sie stehen; Farbgruppen liest er je Körper, wo der alte Leser
aufgab, sobald eine Datei mehr als einen enthielt.

Zwei Folgeänderungen: `takes_whole_scene` wird deklariert statt aus
`(consumes=0, produces=VARIABLE)` geschlossen, und `OperationDraft.produces`
sagt dem Stapel, wie viele Objekte eine Datei mitbringt — er vergibt die IDs,
bevor die Datei gelesen ist.

### Stückzahl

„x10" im Dateinamen ist eine Zahl, die keiner mehr ändern kann. „Objekt
duplizieren" hat jetzt eine Anzahl bis hundert: ein Schritt mit einer Zahl statt
neun gleicher Schritte im Stapel. Eine Operation sagt dazu im Register, in
welchem Parameter ihre Ausgabezahl steht (`produces_from`); ein Ausdruck (§13)
geht dort nicht, weil die IDs vor der Auflösung vergeben werden, und wird mit
genau diesem Satz abgelehnt.

### Drehdeckel — und das Gewinde, das nicht griff

`deckel_dreh` neben `gewuerzbehaelter_body`, `kartuschen_deckel` neben
`kartuschen_kaefig`: Schraubdeckel. Der Gewinde-Baustein kann nur M2 bis M8, ein
Glashals mit 40 mm und grober Steigung war unerreichbar. `screw_lid` setzt den
Hals auf die Öffnung und macht den Deckel dazu — beide aus einer Operation, weil
sie eine Entscheidung sind.

**Dabei kam heraus, dass das Gewindepaar der Bausteinbibliothek nie gegriffen
hat.** Die Mutter wurde auf den Außendurchmesser gebohrt statt auf den Kern:
damit bleibt nichts stehen, woran der Kamm der Schraube sich hält. Gemessen an
M6: Schraubenkamm r = 2,925, Mutterbohrung beginnt bei r = 3,075 — 150 µm Luft,
die Schraube fällt durch. Jede Hälfte war für sich richtig, wasserdicht und
maßhaltig; nur das Paar war es nicht, und getestet wurde jede Hälfte für sich.

Jetzt wird das Innengewinde vom Kern plus Spiel geschnitten. M6 nachgemessen:
Schraube 2,375–2,925, Mutter 2,525–3,075 — 0,15 mm auf beiden Flanken, genau das
Spiel aus dem Parameter. Der Drehdeckel rechnet nach derselben Regel: Hals
18,34–20,00, Deckel 18,465–20,125. Die 0,55 der Rippentiefe heißt jetzt
`RIDGE_SHARE` und steht an einer Stelle, weil drei Rechnungen sich darauf
verlassen — und zwei davon, die verschiedene Zahlen benutzen, sind ein Paar, das
nicht zusammenpasst, ohne dass es einer der beiden Hälften anzusehen ist.

## Auswahl, Ort und Änderbarkeit

Aus einer Frage entstanden: „kann man einzelne Flächen auswählen und dort eine
Operation ansetzen, oder wie fügt man Operationen zu einem Objekt hinzu?" Beim
Nachsehen war die Antwort unbefriedigend — das Fundament stand, aber drei Drähte
waren nicht angeschlossen.

**Der Klick kam nie am Dialog an.** Merkmale werden seit P3 erkannt, stehen im
Objektbaum und sind im Fenster anklickbar; `applies_to` sagt, welche Operation
sich für welches Merkmal anbietet. Der Dialog danach öffnete trotzdem mit
Vorgabewerten. Wer in die gerade angeklickte Fläche bohren wollte, las deren
Koordinaten von der Analysekarte ab und tippte sie ein.

`scene.placement.values_for` ist die Verbindung, und sie liegt im Kern, weil die
Regel auf der Kommandozeile und für den Agenten dieselbe sein muss. Was ein
Merkmal beiträgt, ist der Ort und die Richtung — **nicht die Größe**: eine Senkung
nimmt den Kopfdurchmesser der Schraube, nicht den der Bohrung, auf der sie sitzt,
und eine hilfsbereit eingetragene 5,2 wäre dort eine falsche Zahl, die aussieht
wie eine gemessene. Eine Fläche, die schräg steht, nennt keine Achse: ein
gerundeter Wert, von dem niemand erfährt, ist schlimmer als keiner.

**Die Deckel-Ops nahmen die Fläche nicht.** Sie deklarierten `applies_to=["face"]`
und rechneten mit der Oberkante — eine seitliche Fläche auswählen und einen
Drehdeckel erzeugen arbeitete trotzdem oben. Jetzt haben sie einen Parameter
`An Fläche`; die Auswahl trägt ihn ein, und die Operation liest die Fläche selbst,
damit sie prüfen kann: eine, die nicht waagerecht liegt, wird zurückgewiesen
statt als Höhe gelesen zu werden.

**Eine Operation war nicht änderbar.** Nur Projekt-Parameter (§13) ließen sich
drehen; die Zahlen einer Operation nicht. Eine Bohrung zwei Millimeter zu
versetzen hieß: zurücknehmen und neu bohren. `History.change_params` macht daraus
eine Änderung — Doppelklick auf den Schritt im Verlauf öffnet denselben
erzeugten Dialog auf den Werten, die in der Datei stehen. Neu gerechnet wird nur
der Zweig darunter, der Rest kommt aus dem Cache (§15).

Zwei Dinge daran sind bewusst eng: zurückgenommene Transaktionen fallen weg wie
beim Anwenden, weil es keine Zweige gibt (§15.4). Und eine Änderung, die die
*Anzahl* der Objekte ändert, während spätere Schritte damit arbeiten, wird
abgelehnt — die IDs der neuen Körper sind nicht die alten, und ein Fehler am
Ende des Stapels über eine Zahl am Anfang ist einer, den niemand mit dem
verbindet, was er getan hat.

Der Dialog kennt jetzt Startwerte, und dieselbe Zeile trägt beides: den Klick auf
eine Fläche und das erneute Öffnen einer Operation. Ein zweiter Dialog für den
zweiten Fall wäre eine zweite Stelle, an der ein Parameter fehlen kann.

*Nebenbei zum dritten Mal in die gleiche Falle getreten:* ein Test, der ein
lebendes `MainWindow` etwas fehlschlagen lässt, hängt — das Fenster antwortet auf
`session.failed` mit einem modalen Meldungsfenster. Steht jetzt im Kopf der
Testdatei.

## Tiefes Review

Geleitet von den Mustern, die diese Sitzung dreimal gezeigt hat: eine
Fehlerbehandlung, die einen echten Fehler als erwarteten Sonderfall verbucht;
ein Test, der den Pfad nie betritt; ein Paar, dessen Hälften einzeln stimmen;
eine Behauptung im Kommentar, die keiner nachgemessen hat. Fünf Funde.

**Ein zyklisches 3MF hängte die Anwendung auf.** Die Tiefengrenze bremst jeden
*Pfad* bei 32 — bei zwei Komponenten je Objekt sind das 2³² Pfade, alle 32 tief
und keiner wiederholt. Eine Datei von 500 Byte, und der Import kommt nie zurück.
Was hilft, ist ein Objekt nicht zu betreten, das auf dem Weg dorthin schon liegt:
0,001 s statt unendlich (§32 — eine Grenze sagt etwas, sie hängt nicht).

**Der Planer vergab 5 Millionen Objekt-IDs in 1,1 Sekunden.** Die Stückzahl
deklariert `maximum=100`, geprüft wird das aber erst, wo die Szene gerechnet
wird — und der Stapel vergibt die IDs vorher. Jetzt prüft er gegen dieselbe
Deklaration, also gegen eine Wahrheit statt gegen zwei.

**Eine nach unten zeigende Fläche war eine Öffnung.** „Waagerecht" war zu
großzügig: die Innendecke eines Hohlraums ist auch waagerecht. Als Öffnungshöhe
gewählt baute sie einen Deckel *im* Kasten, bei 26,9 von 30 mm, und keiner der
Schritte danach merkte etwas — ein Schnitt unter dieser Ebene trifft die Wand.
`faces_up` verlangt jetzt, dass sie nach oben zeigt.

**Die Fehlerbehandlung, die den V-HACD-Fehler verschluckt hat, hatte neun
Geschwister.** `PROGRAMMING_ERRORS` in `core/errors.py` benennt die drei Typen,
die heißen „der Code ist falsch", und neun Handler lassen sie durch, statt sie
als Umgebungsfehler zu verbuchen. Zwei Tests halten beide Hälften der Regel:
ein `TypeError` kommt durch, ein `RuntimeError` bleibt gefangen.

**Die Verwaisungsprüfung hat ihren eigenen Fall vorhergesagt.** Im Kommentar von
`references` stand: „Operations carry coordinates, not feature ids; when one of
them starts to reference a feature it is listed here too." Seit P5 tun sie es —
jeder eingesetzte Baustein trägt `at_feature`, achtzehn Operationen deklarieren
eine, und keine wurde je geprüft. Eine Datei, deren `hole_1` weg war, bekam
nicht die Frage aus §21.3, sondern blieb an der Operation mit einem Fehler
stehen. Welche Parameter zählen, ist jetzt deklariert (`kind="feature"` stand
seit P0 im Vertrag und hatte keinen Nutzer); wird ein Verweis fallen gelassen,
verliert die Operation nur den Namen und nicht ihre Geometrie.

**Zwei eigene Behauptungen zurückgenommen:** `values_for` liegt nicht im Kern,
„weil CLI und Agent dieselbe Regel brauchen" — sie benutzen es nicht. Es liegt
dort, weil es eine Regel über Geometrie und Parameter ist, prüfbar ohne Qt; der
Agent arbeitet aus dem Steckbrief, und **deshalb steht die Position jedes
Merkmals jetzt darin**. Vorher nannte der Steckbrief Durchmesser und Achse einer
Bohrung und nicht, wo sie ist — für „setze ein Teil an hole_1" reicht der Name,
für „bohre daneben" nicht. Und `record_solvers` behauptete, die notierte
Rückfallstufe lasse eine Datei gleich rechnen; die Auswertung liest sie nie —
gleich rechnet sie, weil die Kette deterministisch ist.

Korpus danach: **68 von 68**, 1681 Tests grün.

## Ein echtes Modell als Prüfstein

Ein heruntergeladener Eiffelturm, 15,6 MB, 312 970 Dreiecke, Ordner und Datei
chinesisch benannt. Vier Funde, jeder davon von der Datei selbst gestellt.

**Die CLI stürzte am Dateinamen ab.** `print` auf einer Windows-Konsole encodiert
nach cp1252, und `埃菲尔铁塔18cm.stl` gibt es dort nicht — der Import lief durch
und der Lauf endete im `UnicodeEncodeError` auf der Zeile, die den Erfolg meldet.
Deutsche Umlaute überleben cp1252, deshalb ist das eine ganze Phase lang niemandem
aufgefallen. Jetzt sprechen beide Ströme UTF-8 mit `backslashreplace`.

**Der Export verstümmelte den Namen.** `safe_name` schickte den ganzen Namen durch
ASCII: aus `埃菲尔铁塔18cm` wurde `18cm`, aus `Соединитель` wurde `teil`. Unsicher
ist eine kurze Liste — Pfadtrenner, Doppelpunkt, was Windows reserviert —, und der
reguläre Ausdruck hielt sich mit `\w` unter `re.UNICODE` längst daran. Die
ASCII-Zeile war es, die zerstörte. `Boîtier` behält jetzt auch seinen Zirkumflex.

**Die Kommandozeile konnte gar nicht exportieren.** Laden, reparieren,
beschreiben — und das Ergebnis blieb im Projekt. Der Schreiber aus §29 stand seit
P2 und war von außen nicht erreichbar. `solidon3d export` gibt es jetzt, mit
Objektauswahl, Namensschema und der Vorabprüfung vor dem ersten Byte.

**Und die Undichtigkeit war keine.** Der Turm hatte genau drei offene Kanten über
drei Punkte — kollinear bis auf die letzte Stelle, 3,853 + 1,927 = 5,780. Kein
Loch, sondern eine **T-Verbindung**: die lange Kante wurde beim Bauen der
Nachbarfläche geteilt und die Fläche auf der anderen Seite nie informiert.
`trimesh.repair.fill_holes` lehnt das zu Recht ab — ein Dreieck über drei
kollineare Punkte hat keine Fläche. `stitch_t_junctions` gibt stattdessen der
anderen Fläche den fehlenden Punkt: eine Fläche wird zu zweien, keine Geometrie
bewegt sich, das Volumen bleibt auf vier Stellen gleich. Ergebnis am Modell:
14 Teile → 2, Randkanten 12 → 0, wasserdicht.

Befund zum Modell selbst: 0 Inseln, keine Schicht unter Düsenbreite, längste
freie Spanne 8,33 mm bei z=69,1 — die Zusage „ohne Stützen" hält. Die zwölf
gelöschten Teile waren Splitter mit Volumen null; das dreizehnte, eine
freistehende Spitze von 3,3 × 3,3 × 25,2 mm, ist absichtlich da und blieb.

## Aus der Frage nach der Veröffentlichung

Der Anlass war keine technische: „wie weit sind wir weg, was fehlt, ist es gut
genug." Die Antwort auf die letzte Frage war das Problem — die Suite war grün,
und trotzdem war das, was ein Fremder als Erstes sieht, nicht vorführbar.

**Die Zusatzprogramme waren da und wurden nicht gefunden.** `shutil.which`
kennt nur den PATH, und Windows-Installationsprogramme tragen dort nichts ein:
OpenSCAD unter `C:\Program Files\OpenSCAD` und ein installierter Slicer galten
als fehlend, mit dem Angebot, sie ein zweites Mal zu installieren. Gesucht wird
jetzt an vier Stellen, und Dienste werden gefragt statt gesucht — ComfyUI
startet Solidon ohnehin nie, es redet über HTTP mit ihm. Wo alles das nichts
findet, gibt es den Weg, der immer geht: den Ort selbst angeben.

**201 von 325 Parametern hatten keinen Hilfetext.** Ein Zahlenfeld mit einer
Beschriftung darüber ist keine Erklärung. Alle 325 tragen jetzt einen Satz, und
wo möglich sagt er, was passiert, wenn man die Zahl falsch wählt. Ein Test im
Registerkonsistenzlauf hält das fest — auch gegen Texte, die nur den Titel
wiederholen.

**Es gab kein Handbuch.** Jetzt achtzehn Seiten, die Referenz davon erzeugt.

**Die Beispiele zeigten acht von zweiundsechzig Operationen** — und führten
dabei zwei Dinge vor, die nicht stimmten: vier Warnungen ohne Anlass und eine
Reparatur, die nicht reparierte. Jetzt sieben Projekte, und beim Bauen kamen
vier Fehler heraus, die jede Auswertung betreffen:

* Der **Mittelpunkt einer Fläche** war das Mittel über die Dreiecksschwerpunkte
  und hing damit an der Vernetzung. Eine Bohrung zog ihn um 16,8 mm zum Loch,
  und die Zuordnung hielt die Fläche danach für eine andere.
* Auf einem erzeugten Netz galten **181 Facetten als Flächen**, weil der Anteil
  an der größten Fläche nur bei einem konstruierten Teil filtert. Danach war
  jede Zuordnung mehrdeutig und die Auswertung hielt an — Weg 3 kam nach der
  Reparatur nicht weiter.
* **Mehrdeutig war jeder Kandidat, der überhaupt in Frage kam**: die Marge stand
  als `max(bester * 1,25, Annahmeschwelle)` da und war damit wirkungslos.
* **`match()` bekam nie sein `old_centre`.** Der Parameter steht seit P3 in der
  Signatur. Ohne ihn verlor *Auf dem Bett anordnen* jedes Merkmal jedes Objekts.

Dazu zwei Meldungen, die das Gegenteil dessen sagten, was passiert war: eine
geschlossene offene Kante als Warnung, und acht verwaiste Merkmale für ein
Prüfstück, das absichtlich 22 mm aus einem 70er Gehäuse schneidet.

**Bewusst offen, weil es niemand von hier aus erledigen kann**

* **Kein Remote, keine CI.** Die Datei ist geprüft, nie gelaufen.
* **Keine Website**, und die Adresse in `core/updates.py` ist ein Platzhalter.
* **Kein Zertifikat**, also SmartScreen beim ersten Start.
* **Kein Vertriebsweg** — kein Lizenzschlüssel, keine Testphase, kein
  Zahlungsanbieter, keine Rechtstexte.
* **Kein einziger fremder Nutzer.** 1797 Tests sagen, dass der Code tut, was
  gemeint war. Sie sagen nichts darüber, ob jemand anders die App bedienen kann.

---

## P13 — Skizzen und tiefere Konstruktion

Beschlossen am 31.07.2026, Bauplan v10 (§30.1, §40): **die Veröffentlichung
wartet auf diese Phase** — der Launch führt die Skizzen als Kernargument. Das
Ziel dahinter: so wenig Fremdprogramme wie möglich; das fremde CAD vor dem
Import ist der größte verbliebene Grund, Solidon zu verlassen. Der Slicer
bleibt bewusst außen (§22.5), OpenSCAD bleibt Rückfallebene. Die
Veröffentlichungsreste aus P8 (Remote/CI, Zertifikat, Vertrieb, Betatest)
laufen parallel und stehen weiter oben unter „Bewusst offen".

- [x] Lizenzprüfung der Solver-Wege — kürzer als gedacht: scipy ist seit dem
      `geom`-Extra deklariert und steht mit BSD-3 in der Freigabeliste; der
      eigene Solver braucht **keine neue Abhängigkeit**. CadQuery/build123d
      damit gegenstandslos; SolveSpace und py-slvs waren GPL und nie im Rennen
- [x] `core/sketch`: Datenmodell als Verträge in `core/types.py` (§9) —
      alle Freiheitsgrade sind Punktkoordinaten, `targets` sind Punktindizes
      über die flache Punktliste; ohne Qt
- [x] 2D-Solver (`core/sketch/solver.py`): deterministisch, ohne Zufall;
      unterbestimmt zählt Freiheitsgrade im Ergebnis, überbestimmt und
      widersprüchlich werfen `SketchConflictError` mit benanntem Paar —
      Duplikate findet die Ranganalyse, Widersprüche der Restfehler
- [x] Maße als Ausdrücke der Parametergrammatik (§13) — `@width` und
      `=@width/2 + 5` laufen durch denselben Auswerter wie überall, kein
      `eval`; alles außerhalb der Grammatik wird abgelehnt
- [x] Grundformen (`core/sketch/shapes.py`): Rechteck, Langloch, Kreis,
      Vieleck als Skizzen mit Bedingungen, nie als rohe Punktlisten — und der
      eigene Solver hat das eigene Langloch abgelehnt: der erste
      Bedingungssatz war in der symmetrischen Lage linear abhängig. Die
      Disziplin gilt auch für die eigenen Formen
- [x] Sechs Skizzen-Ops gegen den B-Rep-Kern (`sketch_extrude`,
      `sketch_pocket` mit Flächen-Klick und durchgehend, `sketch_revolve`,
      `sketch_sweep`, `sketch_loft`) — der Umriss reist als exakte Kurve
      (`core/sketch/profile.py`, `core/brep/profiles.py`); jede Op steht
      gegen eine geschlossene Formel: der Torus trifft Pappus, der Kreis Pi
- [x] Formgebungs-Ops: exakte Schale (oben offen), Formschräge und der
      exakte Gewindebolzen als echter helikaler Sweep — erst kürzen, dann
      vereinigen, sonst scheitert die Boolesche Stufe; Fase und Verrundung
      ziehen in die neue Kategorie Formgebung um
- [x] Die gezeichnete Skizze reist als Parameterwert (`kind="sketch"`,
      JSON-Text in `core/sketch/serialize.py`) und ersetzt in
      `sketch_extrude`, `sketch_pocket`, `sketch_revolve` und `sketch_sweep`
      die Grundform — §15 gilt unverändert: kein verstecktes Attribut,
      Bearbeiten ist `change_params`. Der Text wird gelesen wie jede fremde
      Eingabe (auch `true` und `NaN` sind keine Koordinaten), und der
      Cache-Schlüssel der Auswertung kennt die Projektparameter, die ein
      Maßausdruck im Text liest — sonst überlebte der alte Körper die
      Parameteränderung im Cache. Der Agent bekommt den Parameter nicht
      (§26: Grundformen statt roher Punktlisten) — das Tool-Schema bietet
      ihn nicht an, und die Sitzung lehnt ihn auch geraten ab
- [x] Grafischer Skizzeneditor (Zeichnen, Bedingungen über Werkzeugleiste
      und Kontextmenü), offscreen testbar — `app/ui/sketch_editor.py`,
      angebunden über das `kind="sketch"`-Feld jedes Operationsdialogs;
      die Ebene kommt weiter aus dem Flächenparameter der Op. Die offene
      Frage von damals ist beantwortet, wie der Punkt es nahelegte: kein
      Befund an der Op — die Freiheitsgrade stehen live in der Statuszeile
      des Editors, und das Feld fasst sie zusammen
- [x] Agenten-Suite von 30 auf 33 Fälle: Sechseck-Sockel, Deckel mit Tasche,
      Handlauf-Bogen — und der Trichter dreht sich um: was den
      OpenSCAD-Rückfall brauchte, kann `sketch_loft` jetzt im Haus. Die
      Quote gegen ein echtes Modell misst weiter `tools/run_agent_suite.py`
      (kostet Geld, läuft auf Zuruf)
- [x] Ende-zu-Ende: Gehäuse mit passendem Deckel von leerer Szene bis 3MF
      (`tests/test_sketch_end_to_end.py`) — und der Weg fand zwei stille
      Fehler: `create_lid` fraß im Stapel das Gehäuse (die Op-Tests riefen
      die Funktion immer direkt auf), und die Hüllquader von OpenCASCADE
      schlagen die gespeicherte Vernetzung mitsamt Durchhang auf — die
      Schale fand auf einem gehashten Körper keine Oberseite mehr
- [x] Leistungsziel §31: 200 Bedingungen unter 100 ms — **90 ms** Ende zu
      Ende, gemessen in `test_performance.py`. Zwei Entscheidungen tragen
      den Wert: jede Bedingung bringt ihre **analytische Ableitung** mit
      (numerische Differenzen kosten eine Auswertung je Variable), und der
      Trust-Region-Schritt läuft über `lsmr` statt einer dichten SVD je
      Iteration (700 ms → 90 ms, nachgemessen). Nebeneffekt: die exakte
      Jacobimatrix macht die Ranganalyse verlässlich, an der die Erkennung
      überbestimmter Skizzen hängt

## Website

Entschieden am 31.07.2026: statische Seite auf einem Webspace, Subdomain
`solidon3d.rs-digital.org` — dort liegen auch die `version.json` (§37.2,
`core/updates.py`) und der Installer. Die Quelldateien liegen in `website/`,
die Schrittliste für DNS und Upload in `website/README.md`. Impressum und
Datenschutz sind Entwürfe und vor der Veröffentlichung zu prüfen.

**Berichtigt am 06.08.2026: die Domain war erfunden.** Hier stand bis dahin
`solidon3d.rsdigital.de`, und die Adresse reiste von hier aus in
`branding.py`, `updates.py` und `version.json`. Diese Domain gibt es nicht
und gab es nie — es gibt genau eine, `rs-digital.org`, die primäre Domain des
Google Workspace. Der Vermerk weiter unten, es stünden „zwei Schreibweisen
nebeneinander, bewusst so entschieden oder zu vereinheitlichen", war die
richtige Beobachtung mit der falschen Erklärung: es waren nicht zwei
Schreibweisen einer Sache, sondern eine echte Adresse und eine angenommene.
Dass eine Annahme als „entschieden" in die Roadmap kam, ist der eigentliche
Fehler — Regel 21 gilt auch für Adressen.

**Entschieden am 08.08.2026: eine eigene Domain, `solidon3d.de`.** Damit
entfällt die Subdomain und mit ihr der teuerste Teil der Einrichtung. Die
Zone von `rs-digital.org` liegt in Google Cloud DNS, während Squarespace die
Registrierung hält — beide Häuser verweisen für einen freien Record
aufeinander, und einen A-Eintrag hätte dort niemand setzen können, ohne die
Workspace-Mail zu gefährden. Die eigene Domain wird beim Webspace-Anbieter
registriert und dort verwaltet: kein TXT-Token für eine externe Domain, kein
A-Record in fremder Zone, keine Subdomain mit eigenem Dokumentenstamm in
Plesk. `rs-digital.org` bleibt Firmendomain und trägt die Geschäftspost,
unberührt.

**Und die Support-Adresse zieht mit: `support@solidon3d.de`.** Der offene
Punkt stand in `branding.py` — Produktseite und Support lagen seit der
Umbenennung auf verschiedenen Domains, und wer eine Setup-Datei von der einen
Adresse lädt und im Programm eine Adresse der anderen findet, hat zwei Namen
vor sich und keinen Grund zu glauben, dass sie zusammengehören. Jetzt ist es
ein Name: Website, Download, `version.json`, Update-Hinweis, Über-Dialog,
Fehlerbericht, Impressum und beide Startseiten stehen unter `solidon3d.de`.
Die Schrittliste in `website/README.md` ist entsprechend neu geschrieben; sie
nennt jetzt auch SPF und DMARC für die neue Zone, die auf der Firmendomain
seit jeher fehlen.

## Aus der Frage nach dem Handbuch

Anlass war eine Feststellung, keine Fehlermeldung: „Wir wollen Geld dafür."
Das Handbuch hatte achtzehn Seiten, kein einziges Bild, und seine sieben
geschriebenen Seiten erklärten Begriffe statt Handgriffe. Wer Solidon zum
ersten Mal öffnete, fand nichts, was ihn vom Startbildschirm bis zur
exportierten Datei führt.

**Jetzt fünfundzwanzig Seiten, zwanzig Abbildungen, drei Ausgabewege.** Fünf
neue Kapitel: die ersten fünfzehn Minuten Klick für Klick, das Fenster, die
Bausteine, „Wenn etwas nicht geht" mit zehn Anfängerfällen, und ein Wörterbuch
mit dreißig Begriffen — „wasserdicht", „Elefantenfuß" und „Insel" kennt
niemand, der nicht schon drinsteckt.

**Keine Abbildung wird von Hand gepflegt.** Schemata entstehen als SVG aus
`core/drawing`, Bausteine und Op-Ergebnisse werden aus der echten Geometrie
projiziert, die fünf Bildschirmfotos nimmt `tools/make_figures.py` auf. Weil
die Beschriftungen Text bleiben, ist das englische Handbuch bis in die Bilder
hinein übersetzt.

Was dabei zutage kam:

* **Das Passungsbild zeigte 0,20 mm, im Materialprofil stehen 0,25.**
  Ausgerechnet die Abbildung, die erklärt, dass Toleranzen nicht abgetippt
  werden, hatte eine abgetippte Toleranz. Die Zahlen in den Zeichnungen kommen
  jetzt aus den Profilen — dasselbe galt für Elefantenfuß und Wandstärke.
* **Ein Körper aus achtundzwanzig Dreiecken ist ohne Kantenlinien ein grauer
  Fleck.** Die Projektion zeichnet jetzt Feature- und Silhouettenkanten und
  lässt abgewandte Flächen weg; das halbiert nebenbei die Dateigröße. Dazu ein
  Aufheller von hinten, sonst läuft jede abgewandte Fläche ins Schwarze.
* **Der feste Dreiviertelwinkel verdeckt bei einer Mutternfalle das Sechskant.**
  Die Kamera steht jetzt je Abbildung.
* **`QT_QPA_PLATFORM=offscreen` hat auf dieser Maschine null Schriftfamilien.**
  Jede Prüfung an einem Bild und jede Aufnahme läuft deshalb unter der echten
  Plattform. Unter `offscreen` wären alle Beschriftungen leere Kästchen —
  einmal fast übersehen, weil die Bilder als Bilder plausibel aussahen.
* **`QWidget.grab` erfasst keinen OpenGL-Inhalt.** Das Hauptfenster kam zweimal
  mit schwarzer Bildmitte zurück, bis es über den Bildschirm gegriffen wurde.
* **Im PDF passte das ganze Handbuch auf zwei Seiten.** `QTextDocument` rechnet
  in Pixeln; bei 1200 dpi ist eine Zwölf-Pixel-Schrift auf A4 ein Staubkorn.
  Bei 96 dpi sind es achtundzwanzig Seiten. Und weil `QTextDocument` kein
  `max-width` kennt, stand jedes Bildschirmfoto zur Hälfte außerhalb der Seite.
* **Beide Sprachen schrieben in denselben Bilderordner.** Der englische Lauf
  überschrieb die deutschen Zeichnungen, und die deutsche Seite zeigte
  englische Bilder.
* **Die Anker des Inhaltsverzeichnisses griffen ins Leere**, weil
  `core.markup` Überschriften eine Stufe nach unten rückt. Ein Test hat es
  gefunden, kein Auge — im Browser sieht ein toter Anker aus wie ein lebender.

Beim Aufnehmen des Bildes vom Prüfbericht fiel auf, dass über vier Befunden
„Keine Befunde" stand: gezählt wurde nur, was aus der Auswertung kam, nicht was
über `add_findings` dazukam. Behoben — gezählt wird jetzt, was in der Liste
steht. Ein Bild von der eigenen Oberfläche zwingt dazu, sie anzusehen.

**Offen: die Orientierungssuche reißt ihr Budget.** `orient_200` braucht auf
dieser Maschine 23,6 s, das Ziel aus §31 sind 20 s; zwei Läufe hintereinander
lieferten 23606 und 23654 ms, es ist also kein Rauschen. Der Docstring des
Tests nennt „etwa 16" — der Wert wurde einmal erreicht und gilt nicht mehr.
Betroffen ist `core/slice/orientation.py`, zuletzt inhaltlich geändert in
a8c6565; dazwischen liegt nur die Übersetzungsrunde, die keine Laufzeit kostet.
Nicht in derselben Runde angefasst: das ist Profiling-Arbeit an der
Orientierungssuche und gehört nicht ins Handbuch.

---

## Aus der Übersetzungsrunde

`app/`, `tests/` und `tools/` sind vollständig auf deutsche Docstrings und
Kommentare umgestellt — 2224 Bausteine, in Paketen committet. Der Nachsatz aus
`AGENTS.md`, es werde nur übersetzt, was ohnehin angefasst wird, ist damit
erledigt und dort gestrichen.

**Die Sprachregel stand an elf Stellen falsch.** Bauplan §4.1, der
Sitzungsstart-Hook und neun Agentenbeschreibungen sagten weiter „Docstrings und
Kommentare englisch" — zwei Sitzungen lang, während genau das Gegenteil
geschah. Alle nachgezogen. Der Bauplan war die gefährlichste davon: er ist die
Instanz, die bei Widerspruch gewinnt, hätte die Arbeit also formal für falsch
erklärt. Die Zeile über Commit-Nachrichten stand aus demselben Grund falsch —
sie sind seit dem ersten Commit deutsch.

**`ruff` und `mypy` fangen keine ungültige Escape-Sequenz.** Beim Übersetzen
von `export/writer.py` wurde aus `` ``\\w`` `` im Docstring ein `` ``\w`` ``.
Beide Werkzeuge liefen grün darüber; vier Tests fielen um, weil sie die Datei
mit `ast.parse` lesen und `filterwarnings = ["error"]` aus der SyntaxWarning
einen Fehler macht. Ein grünes `ruff check` heißt nicht, dass die Datei
fehlerfrei parst.

**Docstrings werden über die AST-Position ersetzt, nicht über Textsuche.** Der
Wortlaut wiederholt sich zu oft; adressiert wird über Funktions- und
Klassennamen, und bei einem Namen, den es zweimal gibt, bricht das Werkzeug ab,
statt zu raten. Die Einrückung braucht keine Sorgfalt — `ruff format`
normalisiert Docstrings ohnehin.

---

## P14 — Die Oberfläche einlösen

Durchsicht der gesamten Bedienung: 29 Dateien unter `app/ui/`, das Register mit
seinen 70 Operationen, die Einstellungen und die Verdrahtung zur Sitzung.
Achtundzwanzig Funde, und keiner davon eine Geschmacksfrage — jeder ist
entweder ein Versprechen, das der Code nicht einlöst, oder eine Stelle im
Bauplan, die noch keinen Nutzer hat.

Sie haben fünf Ursachen. Wer die fünf behebt, behebt die achtundzwanzig; wer
die achtundzwanzig einzeln behebt, baut sie in einem halben Jahr wieder ein.

### Woran es liegt

**1 — Das Dokument kennt nur Operationen.** Alles, was keine Op ist, steht
außerhalb von Transaktion und Undo: Parameter, Passungen, Druckeinstellungen,
Drucker und Material. `History.apply` lehnt eine Transaktion ohne Operationen
sogar ausdrücklich ab. Die Folgen sind die schwersten Funde der Durchsicht:

* Ein Wert in der Parameterleiste wird direkt ins Dokument geschrieben
  (`main_window.py:1397`). Kein Undo — Strg+Z nimmt stattdessen die letzte
  *Operation* zurück. Kein `_dirty` — der Titel zeigt kein `*`, und weil
  `closeEvent` nur `if self.session.modified` sichert, ist die Änderung beim
  Schließen weg.
* `agent/apply.py` hat für genau dieses Problem eine Lösung — der Vorschlag
  trägt `previous_parameters` und `previous_fits` mit, und `apply.undo()`
  spielt sie zurück. **Nur ruft die Oberfläche `apply.undo()` nie auf.** Sie
  ruft `history.undo()`, und das kennt nur Operationen. Ein Strg+Z nach einem
  angenommenen Vorschlag nimmt dessen Operationen zurück und lässt seine
  Parameter und Passungen stehen. Das ist ein Verstoß gegen Regel 16, und die
  Tests decken ihn zu, weil sie `apply.undo()` direkt aufrufen statt über den
  Weg, den ein Mensch nimmt.
* Der Drucker eines Projekts wird in `new_project` gesetzt und danach nie
  wieder (`project.py:129`). Es gibt keinen Weg, ihn zu ändern — wer ein
  Beispielprojekt oder eine fremde Datei öffnet, arbeitet dauerhaft gegen
  einen fremden Bauraum. Bett, Anordnen, Kollisionsprüfung und Auto Split
  hängen alle daran.

**2 — Die Oberfläche kennt den Zustand nicht, den sie zeigt.** In
`main_window.py` steht kein einziges `setEnabled`. Alle 70 Operationen sehen
bei leerer Szene benutzbar aus; wer eine anklickt, bekommt eine modale
Sackgasse („Bitte zuerst ein Objekt auswählen"). `undo_action` und
`redo_action` werden in Attribute gelegt und nie wieder angefasst. Dieselbe
Blindheit an drei weiteren Stellen: `show_error` gibt die gewählte Handlung
zurück und **keiner der neun Aufrufer wertet sie aus** — wer auf *Reparieren
und erneut versuchen* klickt, schließt einen Dialog; der Menühinweis zu
*Beenden* verspricht eine Rückfrage, die `closeEvent` nie stellt; und
`recovery_candidates()` für namenlose Projekte hat keinen Aufrufer, die
Sicherung nach einem Absturz vor dem ersten Speichern wird also nie angeboten.

**3 — Die Oberfläche rechnet selbst.** Die Analysekarte liegt vorbildlich in
einem Thread. Vier andere Rechnungen nicht: der Schnittschieber sendet
`valueChanged` fortlaufend und löst pro Pixel einen booleschen `cut()` je
Körper im Qt-Hauptthread aus; `_slice_of` schneidet synchron und hängt damit
an Strg+P und an der G-Code-Gegenprobe; der Bausteinkatalog rendert beim
Öffnen alle Vorschauen nacheinander ohne Wartezeiger; ein Agentenzug dauert
zehn bis sechzig Sekunden und hat keinen Abbrechen-Knopf. Dazu die Wurzel:
**die Anzeige-Dezimierung aus §18.9 gibt es nicht.** §31 nennt 500 000
Dreiecke als Schwelle; der Viewport zeichnet immer das volle Netz.

**4 — Einstellungen haben keinen Ort.** Es gibt keinen Einstellungsdialog.
Thema und Navigation liegen unter *Ansicht*, Sprache, Drucker und Material
unter *Hilfe → Erste Schritte*. Wer den Drucker unter „Hilfe" sucht, hat
geraten. Drei deklarierte Einstellungen sind deshalb tot: `display_unit` wird
nirgends gelesen (§19.3 Zoll gibt es nicht), `diff_palette` wird gespeichert,
aber beim Start nie an den Viewport gegeben (die Alternative für
Farbfehlsichtige ist unerreichbar), und `check_for_updates` lässt sich nur
durch Handbearbeitung von `settings.json` einschalten. Die Sprache wirkt erst
nach einem Neustart, und niemand sagt das.

**5 — Gestufte Tiefe ist gedacht, nicht gebaut.** `collapsible()` in
`panels.py` heißt so, baut aber nur eine Überschrift ohne Umschalter — die
drei Abschnitte links klappen nicht ein, obwohl §2.5 das verlangt. „Weitere
Einstellungen" ist eine `QGroupBox(checkable=True, checked=False)`, und die
graut ihre Kinder aus, statt sie wegzuklappen. In den Druckeinstellungen ist
deshalb das größte Element des Dialogs — das Register mit 48 Feldern —
standardmäßig graue tote Fläche mit `stretch=1`. Das Häkchen liest sich
außerdem wie ein Schalter, der etwas bewirkt.

### Entscheidungen vor dem Code

**E1 — Die Transaktion trägt auch, was keine Operation ist.** `Transaction`
bekommt ein Feld `changes: DocumentChange | None` mit je einer Vorher- und
einer Nachher-Seite für Parameter, Passungen, Druckeinstellungen, Drucker und
Material. `History.apply` nimmt sie entgegen und darf dann ohne Operationen
auskommen; `undo` und `redo` spielen sie mit zurück und vor. Das ist keine
Bauplanänderung: §15.5 nennt die Transaktion „die Einheit, auf die sich
Verlauf, Differenzansicht und Chatverlauf beziehen" und beschränkt sie
nirgends auf Operationen. Es ist eine Formatänderung — also `format_version`
hoch, Migration, alte Beispieldatei einchecken, nach der Checkliste in
`AGENTS.md`. `Proposal.previous_parameters` und `apply.undo()` entfallen
danach: der Agent baut eine `DocumentChange` wie jeder andere Aufrufer, und es
gibt genau einen Weg zurück statt zwei.

**E2 — Löschen ist eine Operation, die nichts erzeugt.** `delete_object` mit
`consumes=1, produces=0`. Nachgesehen statt vermutet: die Auswertungsschleife
trägt das bereits — `evaluate.py:206` entfernt jedes Eingangsobjekt, das nicht
wieder herauskommt, und die Ausgabeschleife läuft dann null Mal. `History`
vergibt für `produces=0` eine leere Ausgabeliste, und eine spätere Operation
auf dem gelöschten Körper wird beim Anlegen abgelehnt, weil er nicht mehr in
`_known_objects()` steht. Kein neuer Mechanismus, keine Ausnahme von Regel 3 —
die Op ändert kein Objekt, sie gibt keines zurück.

**E3 — Sichtbarkeit und Isolieren sind Ansicht, nicht Dokument.** §18.8
verlangt beides im Objektbaum. Sie kommen trotzdem *nicht* in den Stapel: was
ausgeblendet ist, ändert nichts an dem, was gerechnet, exportiert und gedruckt
wird, und ein Verlauf, in dem jeder Lidschlag steht, ist als Verlauf nichts
mehr wert. Das Fenster führt eine Menge ausgeblendeter Kennungen, der Viewport
liest sie neben `entry.visible`, der Baum zeigt sie mit Symbol **und** Wort
(Regel 18). Das bestehende Feld `ObjectEntry.visible` bleibt, was es ist: die
Vorgabe aus der Auswertung, die eine Op eines Tages setzen darf.

**E4 — Der Drucker wird über E1 gewechselt, nicht über eine Op.** Er ist
Projektkontext wie die Druckeinstellungen (§12 `"scene": {"printer", "material"}`),
kein Schritt im Stapel. Als `DocumentChange` ist er rücknehmbar, steht im
Verlauf und löst eine Neuauswertung aus — Toleranzen sind Verweise (§12), also
ändert sich Geometrie, und das muss im Verlauf stehen.

**E5 — Die Menüleiste bekommt eine zweite Ebene, das Register nicht.** Heute
sind es siebzehn Menüs: vier von Hand und dreizehn aus den Kategorien.
`category` bleibt, wie der Bauplan sie in §25 festlegt; die Oberfläche legt
eine Zuordnungstabelle Kategorie → Menügruppe darüber und macht aus den
dreizehn fünf mit Untermenüs (*Objekt*, *Erzeugen*, *Ändern*, *Bausteine*,
*Druckvorbereitung*). Neun Menüs insgesamt. Eine Tabelle in der Oberfläche ist
chirurgisch; die Kategorien umzusortieren wäre eine Bauplanänderung für ein
Anzeigeproblem.

**E6 — Fehlerhandlungen laufen über einen Vermittler.** `show_error` bekommt
eine Zuordnung `dict[str, Callable]`. Das Hauptfenster stellt die allgemeinen
(`report_error`, `open_settings`, `show_locations`, `scale_to_fit`,
`split_model`, `use_voxel_stage`), der Aufrufer ergänzt das, was nur er kann
(`retry`). Eine Handlung ohne Handler wird nicht angeboten — lieber ein Knopf
weniger als einer, der nichts tut. Ein Test über alle `Action`-Konstanten
hält das fest.

**E7 — Die Anzeige-Dezimierung ist die Antwort auf drei Wartezeit-Funde.**
Erst sie, dann die Threads: ein Schnittschieber auf einem für die Anzeige
dezimierten Netz ist bereits erträglich, und ein Thread um eine Rechnung, die
zehnmal zu groß ist, verschiebt das Problem nur. §18.9, Schwelle aus §31.

### Etappen

Sieben Einheiten, jede für sich committierbar, jede mit grüner Suite am Ende.
Die Reihenfolge ist keine Vorliebe: Etappe 1 trägt 2 und 5, und die
Dezimierung aus 7 macht die Arbeit in 4 billiger, ist aber keine Voraussetzung
dafür.

#### Etappe 1 — Was keine Operation ist, wird trotzdem zurückgenommen

Fundament (E1). Ohne sie sind vier weitere Funde nicht sauber zu beheben.

- [x] `DocumentState` und `DocumentChange` in `core/types.py`, beide Seiten;
      `change_for()` baut sie aus dem heutigen Stand, damit kein Aufrufer die
      Vorher-Seite selbst zusammensucht
- [x] `Transaction.changes`, `History.apply(..., changes=)`, leere Draft-Liste
      erlaubt, sobald Änderungen dabei sind
- [x] `History.undo`/`redo` spielen Änderungen mit — eine Funktion `restore()`
      für beide Richtungen
- [x] Format 4 → 5, Migration `_add_transaction_changes`, `example_v5.p3d`
      eingecheckt (sie zeigt eine Transaktion, die nur aus einer Änderung
      besteht)
- [x] `agent/apply.accept` baut eine `DocumentChange`; `apply.undo` und
      `Proposal.previous_parameters`/`previous_fits` entfallen
- [x] Parameterleiste: Änderung als Transaktion mit Titel „Parameter *name*",
      `_dirty` folgt daraus; die Rückfrage aus §15.4 gilt hier wie im Menü
- [x] ~~`set_print_settings` wird eine Transaktion~~ — **zurückgenommen beim
      Bauen.** Der Punkt stand aus Symmetrie im Plan, nicht aus einem Befund:
      `set_print_settings` setzt `_dirty` längst korrekt, es war nie etwas
      kaputt. Und die Einstellungen ändern nichts an dem, was die Auswertung
      rechnet — sie reisen zum Slicer. Damit gilt hier dieselbe Grenze wie bei
      der Sichtbarkeit in E3: in den Verlauf kommt, was die Auswertung
      beeinflusst. Drucker und Material tun das (Bauraum, Toleranzverweise),
      die Druckeinstellungen nicht.

*Abnahme erfüllt:* Strg+Z nach einer Parameteränderung stellt den alten Wert
her; ein Undo eines *neu angelegten* Parameters entfernt ihn, statt eine Null
zu hinterlassen; Strg+Z nach einem angenommenen Agentenvorschlag stellt
Parameter **und** Passungen wieder her — geprüft über `History.undo`, also
über den Weg, den auch das Fenster nimmt. `example_v1` bis `v5` öffnen und
rechnen. Suite: 2106 grün, rot bleibt allein die bekannte Orientierungssuche.

#### Etappe 2 — Der Objektbaum, wie §18.8 ihn beschreibt

- [x] `delete_object` nach der Op-Checkliste (E2), Kürzel `Entf`, Test
- [x] Sichtbarkeit je Objekt (E3) — Symbol und Wort, im Baum und im Kontextmenü
- [x] Isolieren (§18.8): alles außer der Auswahl ausblenden, ein zweiter Aufruf
      hebt es auf
- [x] Herkunft im Baum: aus welcher Operation und Transaktion ein Körper kommt
- [x] Mehrfachauswahl (`ExtendedSelection`), in **Klickreihenfolge** geführt —
      „A minus B" ist nicht „B minus A", und die Reihenfolge im Baum weiß
      davon nichts
- [x] `OperationDialog` gibt Namen aus und Kennungen weiter, kein freies
      Textfeld mehr

**Drei Funde beim Bauen, keiner davon aus der Durchsicht:**

**Die drei Booleschen mit zwei Eingängen waren über das Menü nicht
ausführbar.** `inputs_for` gab immer genau ein Objekt zurück, `union_objects`
und die beiden anderen erwarten zwei — der Stapel lehnte mit „erwartet eine
andere Anzahl an Objekten" ab. Aufgefallen ist es erst, als die
Mehrfachauswahl die Frage stellte, welches denn das zweite sei.

**Der Stapel hielt tote Objekte für lebendig.** `_known_objects()` sammelte
jede je vergebene Nummer statt der Körper, die am Ende übrig sind. Für das
Entfernen fiel es auf; es galt aber längst für jede Vereinigung: eine
Operation auf einem verbrauchten Körper wurde angenommen und scheiterte erst
beim Rechnen. Jetzt rechnet der Stapel dieselbe Bilanz wie die Auswertung.
Nebenbei ist damit die Behauptung in E2 berichtigt — sie stimmte aus dem
falschen Grund.

**Die Quellenauswahl war mit Körpern gefüllt.** `kind="source"` und
`kind="object"` teilten sich eine Liste, und Objekte standen darin. Wer
*Modell laden* im Verlauf wieder öffnete, bekam Körper angeboten, wo eine
Datei gemeint war. Beide haben jetzt ihre eigene Liste, und ein gespeicherter
Wert, den keine davon kennt, wird angezeigt statt ersetzt.

*Abnahme erfüllt:* Importieren, entfernen, Strg+Z — der Körper ist wieder da.
Zwei Körper anklicken und abziehen, ohne etwas zu tippen. Ausblenden,
Isolieren und Herkunft in `tests/test_ui.py`; ein Test hält fest, dass eine
parameterlose Operation ohne Dialog läuft (Regel 19).

#### Etappe 3 — Die Oberfläche liest ihren eigenen Zustand

- [x] Menüeinträge aktivieren und deaktivieren nach Auswahl und Szenenstand;
      Undo und Redo folgen `history.can_undo`/`can_redo`. Damit entfallen die
      drei modalen Sackgassen. **Die Werkzeugzeile bleibt anklickbar** — sie
      schaltet Ansichten, und ihre Leisten melden inline, was fehlt
      („Wählen Sie zuerst ein Objekt", in der Leiste statt in einem Fenster).
      Ein ausgegrauter Schnittknopf bei leerer Szene wäre Strenge ohne Nutzen
- [x] Fehlerhandlungen verdrahten (E6): sieben Handler im Fenster, und
      `handlers_of()` findet sie vom Dialog aus über das Elternfenster — damit
      zeigen auch Druckeinstellungen und Variantendialog wirksame Knöpfe, ohne
      sie durchzureichen
- [x] Beim Beenden, bei *Neu* und beim Öffnen nach ungesicherten Änderungen
      fragen — drei Knöpfe (Speichern, Verwerfen, Abbrechen), kein „Wirklich?".
      Wer im Dateidialog abbricht, hat nicht gespeichert, und dann wird auch
      nichts verworfen
- [x] Menühinweis zu *Beenden* stimmt danach wieder
- [x] Wiederherstellung für namenlose Projekte — über `find_recovery(None)`,
      nicht über `recovery_candidates()`: `autosave_path(None)` ist ein fester
      Pfad, es kann also nur eine geben. Die zweite, schlechtere Antwort auf
      dieselbe Frage ist entfernt. `Session.recover()` lässt den Pfad leer,
      damit ein „Speichern" nicht die Sicherung überschreibt, und
      `save_project` räumt sie auf

**Was beim Bauen dazukam:** `offered_actions()` ist eine eigene Funktion
geworden, weil sie sich sonst nicht prüfen ließe — ein Test, der dafür den
Dialog aufmacht, hängt am modalen Fenster. Genau das ist beim Schreiben
passiert, und es steht seit der letzten Durchsicht im Kopf von
`tests/test_ui.py`.

Drei Handlungen sind bewusst nicht verdrahtet und werden deshalb auch nicht
angeboten: `use_voxel_stage` (die Rückfallstufe ist kein Parameter, den ein
Dialog setzen kann), `choose` (dafür fragt der Kern über `ctx.ask`, bevor er
wirft) und `choose_printer` — das kommt mit Etappe 5. Ein Test hält fest, dass
jede `Action`-Konstante entweder einen Handler hat oder in dieser Liste steht.

*Abnahme erfüllt:* Bei leerer Szene ist keine Operation anklickbar, die einen
Körper braucht; „Vereinigen" wird erst mit dem zweiten gewählten Körper aktiv;
jeder gezeigte Knopf im Fehlerdialog führt etwas aus; Schließen mit
ungesicherter Änderung fragt. Suite: 2122 grün.

#### Etappe 4 — Nichts rechnet mehr im Hauptthread

- [x] Schnitt- und Explosionsschieber entprellt (120 ms). Der Schnitt bleibt
      im Hauptthread: die Entprellung macht aus dreißig Rechnungen je Zug eine,
      und das reicht. Ein Arbeiter dafür wäre ein zweiter Weg, auf dem
      Geometrie in die Ansicht kommt — die Dezimierung aus Etappe 7 löst den
      Rest an der Wurzel
- [x] `_slice_of` asynchron, mit Meldung in der Statusleiste. Der Druckdialog
      erzwingt sie nicht mehr, sondern nimmt sie, wenn sie vorliegt — genau
      das, was sein Docstring seit jeher behauptet hat
- [x] Bausteinvorschauen nacheinander im Leerlauf, eine je Durchlauf der
      Ereignisschleife; die Liste ist sofort lesbar
- [x] Abbrechen für den Agentenzug — mit **eigenem** Abbruchsignal, denn
      Auswertung und Agent laufen unabhängig, und ein abgebrochener Vorschlag
      darf keine laufende Berechnung mitreißen. Der Balken läuft ohne Ende:
      wie viele Schritte ein Zug braucht, steht vorher nicht fest, und eine
      geratene Prozentzahl wird geglaubt
- [x] `wait_for_idle` schließt Eingaben aus (`ExcludeUserInputEvents`) statt
      alle Ereignisse zu verarbeiten. Die Signale der Arbeiter müssen
      durchkommen, ein Menüklick mitten im Warten nicht

*Abnahme erfüllt:* Kein Weg mehr über 2 s ohne Fortschritt und Abbrechen. Zwei
Tests mussten nachziehen, weil sie das synchrone Verhalten festhielten — beide
warten jetzt auf das, worauf auch ein Mensch wartet.

#### Etappe 5 — Einstellungen an einem Ort

- [x] Dialog *Bearbeiten → Einstellungen* (Strg+Komma), getrennt in zwei
      Gruppen: was die Anwendung betrifft und was für **neue** Projekte gilt.
      Der Unterschied stand vorher nirgends und ist der Grund, warum Drucker
      und Material unter „Hilfe" gelandet waren
- [x] `display_unit` bekommt Leser: Statusleiste, Objektbaum und die Maße der
      Auswahl. Dazu `format_volume()` im Kern — in Zoll sind Kubikzentimeter
      keine Antwort, und der Unterschied ist zu groß, um ihn zu übergehen
- [x] `diff_palette` und alles andere Gespeicherte beim Start anwenden;
      `_apply_settings()` ist die eine Stelle dafür, vorher waren es zwei und
      zwei Werte kamen in keiner davon vor
- [x] Der Sprachwechsel sagt, dass er auf den nächsten Start wartet — der
      Katalog wird beim Start installiert, und Texte, die schon auf dem
      Bildschirm stehen, wechseln nicht mit
- [x] Drucker und Material des offenen Projekts wechselbar (E4) — im
      Druckeinstellungs-Dialog, wo sie vorher als Beschriftung standen. Als
      Transaktion, also rücknehmbar, und die Vorgaben des Dialogs lösen sich
      sofort neu auf
- [x] *Erste Schritte* verweist auf den Dialog

*Abnahme erfüllt:* Auf Zoll umgeschaltet zeigt die Statusleiste 0,7874 für
einen 20-mm-Würfel, und das Netz bleibt bei 20; ein Projekt lässt sich auf
einen anderen Drucker umstellen, das Profil folgt, und ein Undo nimmt es
zurück. Suite: 2129 grün.

#### Etappe 6 — Entdeckbarkeit

- [x] Menügruppen (E5) — neun Menüs statt siebzehn: *Objekt*, *Erzeugen*,
      *Ändern*, *Bausteine*, *Vorbereiten*. Eine Gruppe aus einer Kategorie
      steht flach, sonst bekommt jede Kategorie ihr Untermenü. Eine Kategorie,
      die diese Tabelle nicht kennt, bekommt weiter ihr eigenes Menü — sie
      soll auftauchen, nicht verschwinden
- [x] Befehlspalette nimmt Datei-, Ansichts- und Werkzeugbefehle auf;
      `ToolStrip.tool_titles()` und `strip_title()` haben ihren Aufrufer
- [x] `Escape` schließt das offene Werkzeug
- [x] *Ansicht → Alles einpassen* auf `Home`; dazu bekommt der erste Körper
      einer leeren Szene die Kamera von selbst
- [x] Tastaturnavigation im Viewport nach §19.2: Zoom auf den Standardkürzeln,
      Durchblättern der Körper auf Strg+Tab und Strg+Umschalt+Tab, reihum
- [x] Symbole für die vier Knöpfe der oberen Werkzeugleiste

**Zwei Funde beim Bauen:**

**Die Menügruppen wären nie übersetzt worden.** Der Abgleich der Sprachdateien
liest literale `tr("…")`-Aufrufe; ein `tr(variable)` sieht er nicht. Die Titel
sind jetzt mit `_()` markiert — dieselbe Falle wartet auf jeden, der Texte in
einer Tabelle sammelt (Regel 20).

**Menüs brauchen einen Besitzer auf der Python-Seite.** PySide gibt für ein
Menü bei jedem Zugriff einen neuen Wrapper, und wird einer eingesammelt, nimmt
er das C++-Objekt mit. Solange nur die Leiste die Menüs kannte, ging das gut;
mit der zweiten Ebene wurde daraus ein Absturz. Das Fenster hält seine Menüs
jetzt selbst.

*Abnahme erfüllt:* Neun Menüs in der Leiste, jede Operation weiter erreichbar
(der Test sucht rekursiv), jeder Fenster-Befehl in der Palette.

#### Etappe 7 — Gestufte Tiefe und Anzeigeleistung

- [x] `collapsible()` klappt wirklich ein — ein Knopf mit dem Titel darauf,
      damit die ganze Zeile die Fläche ist, die man trifft, und der gedrückte
      Zustand die zweite Kodierung (Regel 18)
- [x] „Weitere Einstellungen" klappt weg statt auszugrauen — in `op_dialog.py`.
      **Im Druckeinstellungs-Dialog war der Fund nur halb richtig:** das
      Register verschwand längst, sein Rahmen behielt aber den Dehnungsfaktor
      und damit den ganzen freien Raum. Ein leerer Kasten statt grauer Felder;
      jetzt bekommt er zugeklappt auch keinen Platz mehr
- [x] Anzeige-Dezimierung ab 500 000 Dreiecken auf 200 000 (§18.9, §31). Sie
      erreicht weder Kern noch Export. Ein Körper mit einer Analysekarte wird
      **nicht** dezimiert: die Karte trägt einen Wert je Dreieck des Originals
- [x] Nachkommastellen aus dem erklärten Wertebereich: was ganz unter einem
      Millimeter liegt, bekommt drei. Eine Toleranz von 0,075 wurde beim
      Öffnen sonst zu 0,08 — eine stille Änderung an einer gemessenen Zahl
- [x] Chat mehrzeilig; Eingabe sendet, Umschalt und Eingabe macht den Absatz.
      Die Vorschlagszeile nennt bis zu drei Operationen beim Namen und zählt
      erst darüber

*Abnahme erfüllt:* Kein Dialog zeigt graue Felder oder leere Rahmen, die
niemand ausgeschaltet hat. Suite: 2136 grün.

### Was nicht dazugehört

* **Live-Vorschau im Operationsdialog.** Wäre die größte Einzelverbesserung
  gegenüber Fusion und Blender und ist deshalb kein Nebenher — eigene Phase,
  nach P14. Der bestehende Weg (anwenden, ansehen, Doppelklick im Verlauf,
  korrigieren) trägt bis dahin. *Eingelöst — siehe „Die zwei bekannten
  Lücken" unten.*
* **Linke Maustaste dreht als Vorgabe.** Bambu Studio, OrcaSlicer und
  PrusaSlicer tun das; §2.9 gibt Cura vor. Die Vorgabe zu wechseln wäre eine
  Bauplanänderung und bleibt eine Entscheidung für sich — **als viertes
  Wahlschema ist es gebaut** (`orbit`), und dabei fiel auf, dass der
  Menühinweis der Vorgabe seit jeher das Gegenteil dessen beschrieb, was sie
  tut: „links drehen, rechts schieben" ist Bambu, nicht Cura.

### Die Aufräumrunde

Drei Kleinigkeiten, die in der Durchsicht als „echt, aber klein" standen:

- [x] **Verlauf zeigt, was ein Redo zurückholt.** Zurückgenommene
      Transaktionen verschwanden spurlos; ob es noch etwas
      wiederherzustellen gab, verriet allein der Zustand des Menüeintrags.
      Sie stehen jetzt unten, durchgestrichen und ausgegraut — wie ein
      verworfener Chatbeitrag und aus demselben Grund (§26.3)
- [x] **Filterzeile im Prüfbericht**, Text und Schweregrad unabhängig
      voneinander. Die Zählung darüber bleibt die des ganzen Berichts: ein
      Filter, der auch die Zusammenfassung filtert, verschweigt, dass es noch
      etwas anderes gibt
- [x] **Einträge aus „Zuletzt geöffnet" entfernen** — über das Kontextmenü.
      Die Datei bleibt, wo sie ist

## Durchsicht: Politur, die man auf jedem Bild sieht

Anlass war die Frage nach Bedienfreundlichkeit, Logik und dem Stand gegen die
Mitbewerber. Der Befund zur Sache: die Alleinstellung — verstehen, beraten,
anpassen, übergeben in einem Programm — trägt; gegen Tinkercad zählt die
Druckintelligenz, gegen Fusion und FreeCAD die Druckfrage, die dort niemand
beantwortet, gegen die Text-to-CAD-Dienste die eine rücknehmbare Transaktion
je Vorschlag und der Betrieb ohne Cloud. Die zwei echten Lücken sind bekannt
und bleiben es: Skizzeneditor (P13) und Live-Vorschau im Op-Dialog (eigene
Phase). Was die Durchsicht fand, war Politur — sechs Funde, alle behoben:

- [x] **Auf jedem zweiten Dialog stand „Cancel".** Qt beschriftet seine
      Standardknöpfe selbst, und niemand hatte den qtbase-Katalog geladen —
      der Sprachtest sah es nicht, weil es keine eigene Zeichenkette ist.
      Geprüft wird jetzt am echten Artefakt, einer QDialogButtonBox
- [x] **Der Prüfbericht schnitt seine Sätze mitten im Wort ab** — genau die
      Sätze, für die §2.7 geschrieben wurde, hinter einer horizontalen
      Bildlaufleiste. Jetzt Umbruch statt Abschneiden
- [x] **„OK" sagte nicht, was es tut.** Der Bestätigen-Knopf jedes
      Operationsdialogs heißt jetzt wie die Operation — „Bohrung setzen"
      statt „OK", aus dem Register, also übersetzt
- [x] **Der Katalog zeigte zweieinhalb von dreizehn Bausteinen.** Jetzt ein
      Kachelraster; die Gruppenüberschrift nimmt die ganze Zeile, die
      Pfeiltasten laufen in beide Richtungen
- [x] **Das Handbuch war vom Startbildschirm aus unsichtbar** — 25 Seiten
      für die ersten fünfzehn Minuten, erreichbar nur über das Hilfemenü
      eines Fensters, das ein neuer Nutzer noch nie gesehen hat
- [x] **Die Handbuchbilder zeigten die Oberfläche von vor der Bedienrunde**
      — Siebzehn-Menü-Leiste mit Überlauf, ausgegraute Gruppen. Neu
      aufgenommen; `make_figures` wechselt jetzt auch Qts Knopfsprache mit,
      und wer die Oberfläche sichtbar ändert, nimmt die Bilder neu auf

## Die zweite Bedienrunde — was das Fenster versprach und nicht hielt

Anlass wie bei der ersten: die Frage nach Bedienfreundlichkeit, Logik und dem
Stand gegen die Mitbewerber. Die erste Runde hat die Struktur gerichtet, diese
fand die Versprechen, die noch offen waren — das größte stand sogar gedruckt
im eigenen Handbuch. Acht Funde, alle behoben:

* **„Datei → Exportieren" gab es nicht.** Das Handbuch beschreibt den Schritt
  wörtlich („*Datei → Exportieren*, dann 3MF…"), jeder der drei Hauptwege aus
  §2.2 endet mit ihm — aber der Schreiber aus §29 stand seit P2 im Kern, und
  der einzige Weg des Fensters zu einer Datei führte über einen installierten
  Slicer (Strg+P). Dieselbe Lücke hatte die Kommandozeile, bis der Eiffelturm
  sie fand. Jetzt: *Exportieren …* (Strg+E) — die Auswahl oder alles, ein 3MF
  als **eine** Baugruppe (§20), sonst eine Datei je Körper nach dem
  Namensschema; die Prüfung davor meldet in den Prüfbericht (§29).
* **Einen Parameter anlegen konnte nur der Agent.** §2.3 verspricht, dass
  ohne KI alles außer dem Chat funktioniert — Weg 2 lebt von benannten Maßen,
  und wer keinen Schlüssel hatte, konnte keines vergeben. Jetzt: Knopf in der
  Leiste, Eintrag unter *Bearbeiten*, Dialog mit Inline-Prüfung (Name,
  Grammatik, Zyklen — §13); die Änderung reist als `DocumentChange`, ein Undo
  entfernt den Parameter statt ihn zu nullen. Der leere Zustand der Leiste
  sagt jetzt außerdem, wozu sie da ist.
* **Auto Split rechnete im Hauptthread**, mit Wartezeiger — die
  Trennebenensuche schneidet jede Kandidatenebene durch das ganze Netz und
  braucht an einem großen Körper Minuten. `apply_split` ist in Suche und
  Anwendung geteilt; die Suche läuft im Arbeiter mit endlosem Balken und
  Abbrechen (das Ergebnis wird verworfen, wie beim Agentenzug), das Anwenden
  bleibt im Thread des Dokuments.
* **Drei Einträge waren modale Sackgassen auf leerer Szene.** *Automatisch
  teilen*, *Varianten erzeugen* und der neue Export folgen jetzt derselben
  Regel wie die siebzig Operationseinträge: ausgegraut, solange ihnen fehlt,
  was sie brauchen.
* **Die Update-Prüfung blockierte den Start.** Ihr Docstring sagte „niemand
  wartet auf sie" — das Fenster wartete bis zu vier Sekunden auf einen
  Server, dessen Adresse bis heute ein Platzhalter ist. Jetzt ein Arbeiter.
* **Schließen während der Schichtanalyse war ein Absturz beim Beenden.**
  `closeEvent` wartete auf den Karten-Arbeiter, nicht auf den
  Schicht-Arbeiter; `wait_for_idle` kannte den Split-Arbeiter nicht. Beide
  Lücken zu.
* **Der Prüfbericht wollte einen Doppelklick.** §18.4 sagt „Klick auf eine
  Warnung fährt die Kamera hin", `itemActivated` heißt aber Doppelklick oder
  Eingabetaste. Der Einfachklick tut es jetzt auch.
* **Im Katalog stand noch „OK".** Der Politur-Fund („OK sagt nicht, was es
  tut") war in jedem Operationsdialog behoben und im Bausteinkatalog nicht —
  der Knopf heißt jetzt *Einfügen*.

Der Befund zur Lage bleibt der der ersten Runde: die Alleinstellung —
verstehen, beraten, anpassen, übergeben in einem Programm, ohne Cloud, jeder
Vorschlag eine rücknehmbare Transaktion — trägt. Die zwei bekannten Lücken
(Skizzeneditor P13, Live-Vorschau im Op-Dialog) bleiben die zwei bekannten
Lücken. Die Handbuchbilder sind nach dieser Runde neu aufzunehmen — Menüs,
Parameterleiste und Katalog haben sich sichtbar geändert.

## Die zwei bekannten Lücken sind zu

Beide Runden nannten dieselben zwei Lücken gegen Fusion und Shapr3D — jetzt
sind sie gebaut, und beide auf den Wegen, die schon dalagen:

* **Die Live-Vorschau im Operationsdialog** ist dieselbe Differenzansicht
  wie beim Agentenvorschlag, nur früher: `preview_scene` verallgemeinert
  die Vorschau-Rechnung des Agenten (Kopie, Entwurfsqualität, Cache trägt
  die alten Schritte), `valuesChanged` am erzeugten Dialog entprellt auf
  300 ms, und die erste Vorschau läuft beim Öffnen — die Vorgaben sind
  schon eine Aussage. Auch das Wiederöffnen im Verlauf zeigt live, als
  geänderte Operation gerechnet, nicht als neuer Schritt (§15.4). Eine
  angehaltene Kette zeigt nichts statt einer leeren Differenz — die sähe
  aus wie „keine Änderung", und das wäre gelogen. Rückfragen stellt die
  Vorschau nie: was eine Antwort braucht, bekommt sie beim Anwenden.
* **Der grafische Skizzeneditor** (§30.1 Stufe zwei) zeichnet Punkt,
  Linie, Kreis und Bogen, fängt auf vorhandene Punkte (der Fang wird eine
  Deckungs-Bedingung, keine kopierte Zahl), setzt alle neun Bedingungen
  über Werkzeugleiste **und** Kontextmenü — angeboten nur, was zur
  Auswahl passt —, und Maße sind Ausdrücke der Grammatik mit
  Inline-Prüfung. Der Solver läuft nach jedem Schritt: die
  Freiheitsgrade stehen live in der Statuszeile, ein Konflikt nennt sein
  Paar und lässt die letzte gültige Lage stehen (§15.3). Grundformen
  kommen aus `shapes` mit verschobenen Zielen. Der Editor liest und
  schreibt den Text der Skizzen-Ops — es gibt keinen zweiten
  Skizzenbegriff, `change_params` und der Cache gelten unverändert.

**Zwei Funde nebenbei, beide älter als diese Runde:**

* **Das Handbuch behauptete „kein CAD-Ersatz — es gibt keine Skizzen und
  keine Zwangsbedingungen."** Seit P13 falsch, und der Launch soll die
  Skizzen als Kernargument führen. Die Seite sagt jetzt, was da ist.
* **Ein ersetzter Arbeiter wurde dem Speicherbereiniger überlassen.**
  „Eine neuere Anfrage ersetzt die wartende" hieß bei Analysekarte und
  Schichtanalyse: die Referenz überschreiben — und ein laufender QThread
  ohne Referenz wird mitsamt C++-Objekt zerstört. Das ist der Absturz
  ohne Zeile, der die Suite heute zweimal sporadisch riss
  (`Windows fatal exception: access violation`, „Garbage-collecting").
  Ersetzte Arbeiter bleiben jetzt referenziert, bis sie ausgelaufen sind
  (`_retire`, `_previews`-Pool), und ein Stresstest hält das Muster fest.

## Aus der Analyse für Neulinge und Kunden

Anlass war die Frage, wie die Anwendung auf Neulinge und zahlende Kunden
wirkt. Der Befund: die Onboarding-Substanz trägt — Startbildschirm mit
Beispielen, Handbuch-Knopf, überspringbarer Erststart, Fehler als Vorschlag.
Die verbliebenen Lücken lagen fast alle **vor dem ersten Start und neben der
App**: beim Kaufweg, beim Vertrauen und beim Erwartungsmanagement der KI.
Behoben in dieser Runde:

* **Es gab keinen Weg, Kunde zu werden.** Kein Preis, kein Kontakt — der
  einzige angebotene Weg („Adresse im Impressum") führte auf einen
  Platzhalter. Jetzt: **eine Support-Adresse** als Konstante
  in `app/branding.py`, gelesen von Über-Dialog, Fehlerbericht-Dialog,
  README, Impressum und beiden Startseiten. Der Fehlerbericht sagt jetzt
  auch, wohin der abgelegte Ordner kann — er verschickt weiter nichts.
* **Kaufmodell auf der Website** (Entscheidung Robert, Preis delegiert):
  14 Tage kostenlos testen, dann Einmalkauf — **49 € zur Einführung, später
  79 €**, alle 1.x-Updates inklusive. Einordnung: Plasticity als nächster
  Vergleich (Indie-CAD, Einmalkauf) liegt bei 149 $, Shapr3D bei ~299 €/Jahr,
  Fusion weit darüber, die Hobby-Konkurrenz bei null. Eine 1.0 einer neuen
  Marke ohne Nutzerbasis startet darunter; „wir verbessern uns weiter" ist
  als 1.x-Zusage eingelöst, und der Einführungspreis belohnt die, die früh
  einsteigen.
* **Das Kernversprechen war beim Auspacken leer.** Der Erste-Schritte-Dialog
  bekam den Chat-Zugang (Zustandszeile + Knopf zum Schlüsseldialog), den
  sein Docstring seit jeher versprach; das Fenster weckt den Chat danach
  ohne Neustart. Der einzige Weg dorthin war vorher ein Knopf in einem
  Panel, das ein neuer Nutzer noch nie gesehen hat.
* **Der Satz aus §27 fällt jetzt bei der Einrichtung.** Wacht der Chat über
  Ollama auf, fragt ein Arbeiter die installierten Modelle ab
  (`llm.ollama_size_warning`): unter 7 Milliarden Parametern oder gar nicht
  installiert gibt es einen Satz im Chat-Panel — einmal, bei der
  Einrichtung, nicht bei jedem Start. Ein Server, der nicht antwortet,
  bleibt Schweigen statt Warnung.
* **Ein Anwendungssymbol existiert.** Gestaltete SVG-Quelle
  (`app/images/icon/solidon3d.svg`: isometrischer Körper, Bohrung,
  Schichtlinien, Markenfarbe), gerastert von `tools/make_icon.py` zu
  `packaging/solidon3d.ico` (DIB + 256er-PNG, ohne neue Abhängigkeit) und
  `website/icon.svg`; das Fenster rastert die Quelle zur Laufzeit
  (`icons.application_icon`). Eingebunden in Spec, Installer-Skript und
  alle Website-Köpfe. Damit ist die Vorbedingung für AppImage/Flatpak da.
* **Die Website sagt jetzt, was die KI kostet und braucht.** Weg 3 nennt
  ComfyUI und Grafikkarte, die Systemvoraussetzungen nennen die 14B/10-GB-
  Wahrheit für den lokalen Chat und die laufenden API-Kosten beim eigenen
  Schlüssel — Kunden verzeihen Kosten, die vorher dastanden. Dazu das erste
  Bildschirmfoto auf der Startseite; eines, das fertig danebenlag.

**Weiterhin offen, weil es niemand von hier aus erledigen kann:** das
Postfach support@solidon3d.de anlegen; Anschrift ins Impressum; Zertifikat
gegen SmartScreen; CI nie gelaufen; Zahlungsanbieter und
Lizenzschlüssel-Mechanik für Testphase und Kauf; ein Betatest mit fremden
Nutzern — 2100 Tests sagen, dass der Code tut, was gemeint war, nicht, dass
ein Fremder ihn bedienen kann. Anzumerken: die Web-Domain ist
solidon3d.rsdigital.de, die Mail-Domain rs-digital.org — zwei Schreibweisen
nebeneinander, bewusst so entschieden oder zu vereinheitlichen.
*Aufgelöst am 06.08.2026: die erste Domain existierte nicht. Alles läuft
jetzt über `solidon3d.rs-digital.org`, siehe „Website".* — *Und am 08.08.2026
endgültig: eigene Domain `solidon3d.de`, Support `support@solidon3d.de`. Aus
zwei Domains ist wieder eine geworden, diesmal die des Produkts.*

## Der erste echte CI-Lauf

Am 02.08.2026 ging das Repository auf GitHub (privat, `RS-Digital-Studio/
Solidon`), und die CI lief zum ersten Mal wirklich — mit vier Funden, von
denen keiner auf dieser Maschine sichtbar war:

* **Ein frisches Environment zieht trimesh 5.0.0**, und der Major-Sprung
  riss mypy (die neuen Annotationen geben für `concatenate` den Obertyp
  `Geometry`) und mehrere Tests. Die Engführung auf `Trimesh` lebt jetzt an
  einer Stelle (`mesh.concatenated`); trimesh ist unter 5 gepinnt.
  **Offen: die trimesh-5-Migration als eigener Durchgang** — venv anheben,
  Suite durchmessen, dann den Pin lösen. Nicht nebenbei machen: der erste
  Lauf zeigte auf Windows drei zusätzliche rote Tests und eine abgerissene
  pytest-Ausgabe.
* **„C:/…" ist auf POSIX ein Ordnername.** Die Absolutpfad-Prüfung der
  Projektdatei (Regel 12) urteilte mit dem Plattform-`Path` und ließ
  Laufwerkspfade auf dem Mac durch — und `..\` mit Backslash gleich mit.
  Jetzt urteilt `PureWindowsPath` über beide Konventionen, die Fälle sind
  Testfälle.
* **Die Runner haben kein libEGL.** PySide6 lädt es auch offscreen; ein
  apt-Schritt stellt die Qt-Systembibliotheken in beiden Jobs bereit.
* **Die Leistungstests messen auf geteilten Runnern nur Streuung.** §31
  meint eine Referenzmaschine; die CI läuft `-m "not performance"`, das
  Budget prüft der lokale Lauf.

## Die Beispiele wurden Touren

Der Anlass war ein Satz aus der Neulingsperspektive: „Ich wüsste nicht, was
ich machen soll." §37.2 nennt die Beispiele Doku — sie waren aber fertige
Projekte: das Ergebnis sichtbar, der Auftrag unsichtbar, und alles Wissen
über das Warum steckte in Docstrings von `tools/make_examples.py`, wo kein
Nutzer je liest.

Jetzt öffnet sich jedes der sieben Beispiele mit einer Tour im rechten
Bereich (dritter Reiter neben Prüfbericht und Chat): Schritt für Schritt,
und die Tour erkennt am Dokument und am Verlauf, wann ein Schritt getan
ist — Durchmesser gedreht, Strg+Z, Strg+Y, Baustein gesetzt. Undo und Redo
sind damit das Lehrmittel, nicht nur ein Menüeintrag. Drei Entscheidungen
dabei:

* **Ein Angebot, keine Sperre.** „Weiter" schaltet jeden Schritt auch ohne
  Erkennung, „Tour beenden" steht immer daneben (Regel 19). Erledigt trägt
  einen Haken, der aktuelle Schritt Pfeil und Fettschrift (Regel 18).
* **Die Schritte leben im Kern** (`app/core/tour.py`, ohne Qt), die
  Erkennung ist eine Funktion auf Dokument und Verlauf. `tests/test_tour.py`
  spielt jede Tour als Drehbuch durch — driftet sie gegen
  `tools/make_examples.py`, wird genau das rot.
* **Der Warnungssprung zum Prüfbericht lässt der aktiven Tour den Reiter.**
  Sonst risse die Anleitung genau dann ab, wenn das Beispiel planmäßig
  Befunde erzeugt (Weg 1: die Reparatur).

**Die neuen Tests fanden einen alten Absturz.** Die Suite riss sporadisch
Tests *nach* den Tour-Tests ohne eine Zeile Traceback ab (Exit 127, kein
Faulthandler-Dump). Eingekreist über Wegwerf-Sonden mit Etappenmeldungen:
`Session._on_thread_done` läuft als Slot des `finished`-Signals seines
eigenen Arbeiters und überschrieb dort die letzte Referenz — der
PySide-Wrapper starb mitsamt C++-QThread, während Qt die Zustellung noch auf
dem Stapel hatte. Ausgelöst hat es erst die Tour: ihre Tests fahren schnelle
Ketten (ändern, Undo, Redo) auf einem schweren Dokument, jede davon ersetzt
einen laufenden Arbeiter. Der Fix hält den ausgelaufenen Arbeiter fest, bis
ihn der nächste ablöst — dasselbe Muster wie `_retired` im Hauptfenster.
Sechzehn Läufe des vorher zu etwa der Hälfte roten Testpaars sind seither
grün. **Anzusehen bleibt:** `_on_agent_done` und der Split-Arbeiter lassen
ihre Referenz genauso los; dort hämmert nur niemand.

Nebenbefund, behoben: die Transaktionstitel der Beispiele („Bohrung setzen",
„Anordnen") standen als deutsche Zeichenketten in den Projektdateien und
blieben auch in der englischen Oberfläche deutsch — die englischen Tourtexte
zitierten sie deshalb deutsch. Jetzt reist ein Titel aus dem Code als
Message-ID (Formatversion 6, `title_translatable`) und löst sich erst bei
der Anzeige auf; was ein Nutzer selbst benannt hat, bleibt wörtlich, und
ältere Dateien bleiben es auch — welcher alte Titel aus dem Code kam, steht
nirgends, ein Katalogabgleich wäre geraten. Die Beispiele sind neu gebaut,
die englischen Tourtexte zitieren die englischen Titel („Drill a bore",
„Arrange"), und die Extraktion sammelt die Titel der Beispiel-Bauer über
`EXTRA_SOURCES` mit ein. Im zweiten Durchgang vergibt auch die Oberfläche
ihre Titel über `_()` („Direkt bewegt", „Bemalen", „Modell laden", „STEP
laden", „Zeichnung extrudieren", „Drucker und Material") — nur die
zusammengesetzten Parameter-Titel (`Parameter {name}`) bleiben wörtlich:
eine Message-ID kennt keine Platzhalter, und der Nutzername im Titel gehört
ohnehin nicht übersetzt.

## Ein frischer Klon war rot, ohne dass sich Code geändert hatte

Ein am 2026-08-06 neu geklontes Arbeitsverzeichnis, Umgebung frisch aufgebaut:
**16 Tests rot, `mypy` gar nicht erst durchgelaufen** — bei einem Stand, der
auf der Maschine daneben grün war. Kein Fehler lag im eigenen Code.

Die Ursache ist eine einzige. Alle Abhängigkeiten in `pyproject.toml` haben
offene Untergrenzen, also zog `pip` überall das Neueste; **numpy 2.5 hat
`arr.shape = ...` als veraltet markiert**, VTK 9.6 und scikit-image 0.26
benutzen es noch, und `filterwarnings = ["error"]` macht aus jeder solchen
Warnung einen Fehler. Zwölf Tests fielen direkt darüber.

**Die Voxelstufe der Booleschen Kette fiel als Folgeschaden komplett aus.**
`trimesh.voxel.ops` ruft `skimage.marching_cubes`, dort löste dieselbe Warnung
aus, damit war Stufe 4 tot — und weil die Kette danach zu Ende ist, kam
`BooleanFailedError` heraus: „auf allen Stufen gescheitert" für eine Operation,
an der nichts falsch war. Vier Tests, alle mit `voxel` im Namen.

**Der `mypy`-Abbruch traf auch die CI, unabhängig von dieser Maschine.**
`numpy/__init__.pyi` benutzt die `type`-Anweisung (PEP 695), und geprüft wurde
gegen Zielversion 3.11 — Abbruch mit `errors prevented further checking`, also
keine einzige Projektdatei geprüft. `python_version` ist die Zielversion der
Prüfung, nicht der Interpreter; der CI-Lauf auf 3.11 landet im gleichen
Abbruch. Das Tor war vermutlich rot, seit numpy 2.5 erschien.

**Was den Sprung überlebt hat, ist die eigentliche Nachricht.** manifold3d
ging von 2.5 auf 3.5.2 — der Geometriekern, zwei Hauptversionen — ohne eine
einzige Beanstandung. Ebenso `pytest` 8→9, `ruff` 0.6→0.16 (zehn Nebenversionen
ohne neue Regelverstöße), `PySide6` 6.7→6.11, `lxml` 5→6, `svg.path` 6→7. Und
`mypy` 2.3 mit `strict = true` und den neuen strengeren Vorgaben
(`local-partial-types`, `strict-bytes`) findet in 184 Dateien nichts.

### Was daraus wurde

* **Python-Untergrenze auf 3.13**, an allen sieben Stellen zugleich:
  `requires-python`, `ruff target-version`, `mypy python_version`, beide
  CI-Jobs, `CLAUDE.md` und der Sitzungsstart-Hook. Das löst den Stub-Konflikt
  an der Wurzel, statt numpy zu deckeln — eine Obergrenze hätte das Projekt
  auf einer alten Fassung festgehalten.
* **Die Fremdwarnung eng ausgeklammert**, auf `vtkmodules.*` und `skimage.*`
  begrenzt und mit Entfernungsbedingung kommentiert. Der eigene Kern kommt
  ohne die Zuweisung aus, geprüft — es wird also nichts Eigenes verdeckt.
* **`constraints.txt`**, der Versionssatz, gegen den die Suite grün ist. Suite
  und Paketierung bauen dagegen, ebenso der Erstaufbau in `README.md` und
  `CLAUDE.md`. Ohne ihn installiert jeder Klon etwas anderes, und genau das
  ist hier passiert.
* **Ein wöchentlicher CI-Job „Neueste Fassungen"** löst bewusst ohne
  Constraints auf und protokolliert, was er installiert. Wird er rot, während
  die Suite grün bleibt, liegt es an einer neuen Fassung — die Frühwarnung, die
  hier gefehlt hat. Nur Ubuntu, nur montags: private Minuten sind gezählt.
* Nebenprodukt der Zielversion: `ruff` verlangte mit `py313` drei
  Umschreibungen auf PEP-695-Generics (`op_params`, `validate`, `_by_title`).
  Die modulweiten `TypeVar` und ihre Importe sind damit weg.

### Anzusehen

**manifold3d 3.x bringt vier Dinge, die auf offene Stellen hier passen.** Der
Kern läuft schon darauf, benutzt wird davon noch nichts:

* `ExecutionContext` (3.5) trägt Fortschritt und Abbruch **in** die Boolesche
  Operation. Heute reicht `app/core/geom/` `ctx.cancelled` an genau einer
  Stelle weiter (`prepare_ops.py:725`) — eine laufende Boolesche Op ist nicht
  abbrechbar, obwohl §2.8 das verlangt.
* Plattformübergreifend deterministisches Rechnen in doppelter Genauigkeit
  (3.5) — trifft Regel 6 und die Determinismus-Testart, bei Windows, macOS und
  Linux-Runnern im Spiel.
* Strahlschnitt über Kernel12 (3.5) — genau der Bereich der letzten Funde zum
  Anklicken von Flächen.
* `MinkowskiSum`/`MinkowskiDifference` (3.4) — echte Offsets für Passungsspiel
  und Dichtnuten, statt sie nachzubauen. Die Release-Notiz warnt selbst: bei
  komplexen Netzen langsam und speicherhungrig.

**`MeshIO` ist in manifold3d 3.4 aus der öffentlichen API verschwunden**;
Netz-Ein-/Ausgabe soll über trimesh laufen. Hier unkritisch, sonst wären die
Geometrietests nicht grün — aber es ist eine Stelle, die bei einer künftigen
Umstellung zu prüfen ist.

**trimesh 5.0 ist am 2026-08-01 erschienen** und bleibt gepinnt (`<5`). Der
Sprung ist weiter eine eigene Migration, und die Voxelkette über
`trimesh.voxel.ops` ist gerade die empfindlichste Stelle daran.

## P15 — Konstruieren und zeigen

Der Vergleich mit SindriCAD, Meshy und dem, was 3Druck als Stand der Software
meldet: zweiundzwanzig Lücken, davon vier abgelehnt. Solidon lag bei
Druckintelligenz und Dokumentlogik deutlich vorn und bei Konstruktions-
werkzeugen, Bediensprache und Darstellung deutlich zurück. Das Konzept steht in
`.claude/konzept-p15-konstruieren-und-zeigen.md` und ist vollständig abgearbeitet.

**Die Grenzen kamen zuerst, nicht zuletzt.** Sieben prüfbare Obergrenzen in
`tests/test_interface_limits.py` — höchstens neun Menüs, zwölf Zeilen je Menü,
acht Umschalter, acht Felder auf der Vorderseite eines Dialogs, genau ein
Menüeintrag je Operation. Sie wurden **vor** dem Wachstum eingezogen; installiert
man sie danach, sind sie kein Riegel mehr, sondern eine Bestandsaufnahme. Der
erste Lauf fand sofort ein Menü mit 23 Zeilen und eine Kategorie ohne Symbol.

**Was dazukam.** Umgebungsverdeckung und Körperkanten in der Ansicht; die
Druckplatte mit gefülltem Grund, Maßstab und Kontaktschatten; der Skizzenmodus
ohne Dialog, mit Bauraumgrenze, Referenzmaß, Splines, Skizzenmustern und der
angeklickten Fläche als Ebene; Texturen als echte Geometrie, flach und
umlaufend; Gitterfüllungen; Muster, Press/Pull und Thicken; zwei
Kürzelbelegungen und eine erzeugte Kürzelübersicht; mehrere Generierungs-
versuche; und die MCP-Schnittstelle, mit der ein zweites Programm dieselben
Operationen aufruft wie die Menüs.

**Vier Dinge wurden begründet nicht gebaut** und stehen mit ihrem Grund im
Konzept: Text als Skizzenkontur (die Zeichensatz-Abhängigkeit macht aus einer
Projektdatei eine, die auf einem anderen Rechner anders aussieht),
`offset_face` (dieselbe Operation wie `push_face` unter zweitem Namen),
assoziative Skizzenmuster (sie verlangten einen zweiten Abhängigkeitsgraphen
neben dem Op-Stack) und vier parallele Generierungsläufe (hier läuft ComfyUI auf
derselben Grafikkarte, an der jemand sitzt).

### Was die Arbeit gelehrt hat

**Messen schlägt begründen.** Der Radius der Umgebungsverdeckung stand zuerst
auf acht Millimetern, mit einer plausibel klingenden Begründung — die Messreihe
zeigte ihn als schwächsten Wert der ganzen Reihe. Genommen sind zwei, und auch
das nicht der rechnerisch beste Wert: bei einem Millimeter streifen ebene
Flächen sichtbar, was die Zahl allein nicht sagt. Man muss hinsehen.

**Ein Bild prüft, was ein Review nicht sieht.** Der doppelte ViewCube fiel erst
im neu aufgenommenen Handbuchbild auf. Der Kontaktschatten brauchte sechs
Anläufe, und die drei ersten sahen im Code richtig aus.

**Ein negatives Volumen erklärt eine Voxelstufe.** Die Zylinder-Umlaufung der
Texturen spiegelte: die Determinante der Abbildung war negativ, das gebogene
Feld hatte −420 mm³, und die Boolesche Vereinigung floh auf Stufe 4 — 45
Sekunden statt 0,4, der Körper zwei Zehntel zu groß. Wer eine langsame Boolesche
Operation sieht, misst zuerst das Volumen ihrer Eingänge.

**Der eigene Test findet den eigenen Irrtum.** Die Zahl der Operationen war um
sechzehn falsch, weil ohne geladenes Register gemessen; die erste Fassung der
Grenzprüfung zählte Registerkategorien statt Menüs und hätte damit die Lösung
für das Problem gehalten.

## Live gegen Fusion und den ElegooSlicer

Am 05.08.2026 lief die Anwendung gegen die beiden Programme, die auf dieser
Maschine tatsächlich neben ihr stehen: **Autodesk Fusion 2704.1.36** als Maßstab
fürs Konstruieren, **ElegooSlicer 1.5.3.4** als Empfänger des Ergebnisses.
Fünfzehn Funde, alle gemessen; das Konzept mit Zahlen, Ursachen und Reihenfolge
steht in `.claude/konzept-live-durchsicht-2026-08.md`.

**Drei Dinge tragen besser, als das Repository sie darstellt.** Der STEP-Weg ist
in beide Richtungen bitgenau — Volumen und Fläche stimmen auf fünfzehn Stellen
mit Fusion überein, die Bohrung im zurückgeladenen Fusion-Körper wird erkannt.
Die Slicer-Übergabe meldet gegen 1.5.3.4 — eine Fassung neuer als die, gegen die
die Tabelle gebaut wurde — **null** übergangene Einstellungen; die Profilzuordnung
trifft ohne Zutun aus 9849 gelesenen Profilen. Und der ganze Weg läuft aus dem
Fenster heraus: Strg+P, Slicen, 0,8 Sekunden, Druckdatei.

**Was zu tun war**, nach Gewicht — abgearbeitet in den drei Paketen darunter,
mit Ausnahme der fehlenden Passung:

- [x] **Der Hüllquader eines exakten Körpers kommt aus seinen Dreiecken.**
      `Solid.bounds` gibt `mesh.bounds` zurück; der Fehler ist konstant 0,025 mm
      (halbe `DEFLECTION`), bei Ø 6 wie bei Ø 120. Fusion misst denselben Körper
      mit 25,00 mm Radius, Solidon mit 24,9755. Daran hängen Maßanzeige,
      Bauraumprüfung, Anordnung, Haftungsrand, `advise.for_part` und jede
      Passungsprüfung — ein Zehntel der Materialtoleranz, verloren vor dem ersten
      Druck. Fix: `BRepBndLib` statt Tessellation
- [x] **Die angeklickte Fläche ist die Mitte des Werkzeugs, nicht sein Anfang.**
      Klick auf eine 20-mm-Platte, Bohrung Tiefe 10 → 5 mm tief; Tiefe 0 („bohrt
      durch") → 10 mm und **kein Durchbruch**; Magnettasche → gar nichts. In
      Fusion ist der Klickpunkt die Mündung. Eigene Runde mit Formatversion und
      Migration, sie ändert bestehende Dateien
- [x] **Eine Operation, die nichts abgetragen hat, schweigt.** Die Magnettasche
      neben dem Körper erzeugt keinen Befund, keine Ausnahme, keinen Hinweis —
      unterhalb dessen, was Regel 17 überhaupt erfasst. Volumen vorher/nachher
      vergleichen, sonst Befund mit Vorschlag
- [x] **Solidons Anordnung erreicht den Slicer nicht.** Zwei Läufe, einmal in
      Modell- und einmal in Bettkoordinaten, ergeben denselben G-Code — der
      Slicer ordnet neu an. Mit `--arrange 0` und Bettkoordinaten kommt die
      Anordnung auf ein Zehntel an. Damit ist die ganze Plattenlogik für den
      Slicer-Weg heute folgenlos, und der offene Punkt zum Haftungsrand hätte
      einen Abstand berechnet, der nie ankommt
- [x] **`filament_cost = 0` überschreibt die 30 €/kg des Herstellers.** „0 heißt
      unbekannt, nicht kostenlos" steht im eigenen Docstring — geschrieben wird
      es trotzdem. Systematisch geprüft: der einzige Fall dieser Art
- [x] **Keine Operation legt eine Passung an.** `create_lid` baute den Deckel mit
      0,25 mm Spiel aus dem Materialprofil und trug keinen `Fit` ein; damit
      griffen genaue Außenwand, gebremste Beschleunigung und Bügeln nie. Der
      Deckelablauf legt sie jetzt an (`core/lid_flow.py`), über ein `fits`-Feld
      an `OpResult` — nachgetragen und nicht mitgegeben, weil erst der Verlauf
      die Objekt-IDs vergibt
- [x] **Die Gegenprobe vergleicht nur das Stützvolumen.** Live: 12 g / 46 min
      geschätzt gegen 10,0 g / 37 min gemessen — −17 % und −20 %, und kein Wort
      im Prüfbericht. `gcode.compare` kennt die 15-%-Schwelle und wird an genau
      einer Stelle gerufen
- [x] **`arrange_bed` ohne Eingaben hält die Auswertung an**, statt nichts zu
      tun. Der Test dazu prüft die Positionen und nicht `result.complete` — und
      deckt den Abbruch damit zu
- [x] **Im Viewport lässt sich nichts anklicken.** Links wählt nichts aus, rechts
      öffnet kein Menü; Rad und Rechtsziehen bewegen die Kamera. Ursache:
      gepickt wird mit `vtkPointPicker`, und der trifft Eckpunkte, keine Flächen.
      Daran hängen Auswahl, Kontextmenü am Merkmal (§18.5), Messen, Bemalen und
      die Flächenübernahme in Dialoge
- [x] **Ein Zylinder trägt einundfünfzig Flächenmerkmale**, in Fusion sind es
      drei. Facetten gehören zusammengefasst, bevor IDs vergeben werden — mit
      dem Zuordnungstest zusammen, nicht nebenbei
- [x] **Ein Rundstab meldet sich als Bohrung.** `brep/features.py` macht aus
      jeder geschlossenen Zylinderfläche ein `hole`, ohne die Materialseite zu
      prüfen. `boss` gehört zuerst in Bauplan §4.2
- [x] **Die Skizzenleiste liegt unter den Bereichen links und rechts** — verdeckt
      sind die *ersten* Werkzeuge, also Linie und Rechteck. Kein Platzproblem:
      bei 1296 wie bei 1900 Pixel. Die Kürzel selbst stimmen, `R` zeichnet ein
      Rechteck und die Skizze meldet sich als bestimmt
- [x] **Der Ersteinrichtungsdialog fragt den gefundenen Slicer nicht.** Er meldet
      „Slicer gefunden" und schlägt im selben Fenster den allgemeinen 220er und
      PLA vor, während der Profilbestand den Centauri Carbon 2 kennt
- [x] **Der Objektname reist nicht ins STEP** — in Fusion heißt das Teil
      „Körper1". Fürs 3MF war das schon einmal ein Fund und ist behoben
- [x] **Von der Aushöhlung zum Deckel fehlt ein Schritt.** `hollow_object`
      schließt den Hohlraum, `create_lid` verlangt eine Öffnung; der Weg zur Dose
      führt über zwei Zylinder und eine Differenz

## Paket 2 der Durchsicht: die Platte kommt an

Aus dem Konzept zur Live-Durchsicht war das der zweite Satz Arbeiten — und der
mit der unangenehmsten Voraussetzung: bevor irgendetwas an der Anordnung
verbessert werden konnte, musste sie den Slicer überhaupt erreichen.

**Sie erreichte ihn nicht.** Zwei Läufe derselben Szene, einmal in Modell- und
einmal in Bettkoordinaten, ergaben denselben G-Code — die Orca-Familie ordnet
in der Vorgabe immer neu an. Damit war alles folgenlos, was Solidon über die
Platte weiß: `arrange_bed`, der Haftungsrand aus `check_adhesion_clearance`,
`plates_by_material`, die Plattennummer am Objekt.

Drei Teile, alle am installierten ElegooSlicer 1.5.3.4 gemessen:

- [x] **Die Platzierung reist im 3MF mit.** Über die Matrix am `<item>` des
      Standards, nicht über die Punkte: die Geometrie in der Datei bleibt die
      des Dokuments, und wer sie als Modell liest, bekommt das Modell. Dass
      Orca diese Matrix wirklich liest, ist gemessen — mit ihr und
      `--arrange 0` stehen drei Teile im G-Code auf **0,00 mm** genau dort, wo
      das Dokument sie hat. Der verbleibende Versatz von 1,5 mm in Y ist der
      `extruder_offset` der Maschine, den der Slicer selbst einrechnet.
- [x] **`--arrange 0`, aber nur wenn die Anordnung eine ist.**
      `writer.arrangement_holds` prüft in der Aufsicht: kein Teil über einem
      anderen, keines außerhalb des Betts. Sonst bleibt es beim Anordnen des
      Slicers — zwei Teile übereinander wären schlimmer als eine verworfene
      Anordnung. Getragen wird die Entscheidung durch bis zum Aufruf, und die
      Datei bekommt ihre Platzierung nur dann.
- [x] **Der Abstand kennt die Haftung.** Der Dialog des Anordnens öffnet mit
      dem doppelten Haftungsrand als Abstand, wenn der größer ist als die
      Vorgabe der Operation.

Dazu zwei Funde, die auf dem Weg lagen:

- [x] **`arrange_bed` ohne Eingaben hielt die ganze Auswertung an.** Der Stapel
      plante einen Ausgang, die Operation lieferte ohne Eingaben keinen, und
      alles nach diesem Schritt wurde nicht mehr gerechnet. Der Test dazu
      verglich Positionen statt `result.complete` und deckte den Abbruch zu —
      eine abgebrochene Auswertung bewegt auch nichts.
- [x] **Die Platzierung gehört nicht in jede Datei.** Beim Export einer 3MF
      bleibt sie weg: ein von Hand geöffneter Slicer ordnet ohnehin neu an, und
      eine zurückgelesene Platte läge sonst um den halben Bauraum verschoben im
      nächsten Dokument. Zwei Zwecke, zwei Dateien — `place_on_bed` sagt welche.

## Paket 3 und 4 der Durchsicht — und die Bohrung, die daneben lag

Der Rest des Konzepts, in drei Runden. Paket 3 waren die Stellen, an denen
Solidon gegen Fusion nachweisbar falsch lag; Paket 4 die, an denen es zwar
rechnete, aber nichts sagte. A2 stand bewusst außerhalb, weil es als einzige
Änderung bestehende Projektdateien anders rechnen lässt.

- [x] **Der Hüllquader eines exakten Körpers kam aus den Dreiecken.** Der
      B-Rep-Kern hat einen Körper und meldete trotzdem die Ausdehnung seiner
      Vernetzung — konstant 0,025 mm zu groß gegen Fusion. `BRepBndLib`
      `AddOptimal_s` mit `SetGap(0)` fragt die Fläche selbst, und die
      Abweichung ist null.
- [x] **Eine Boolesche Operation ohne Wirkung meldet das.** Eine Magnettasche
      neben dem Teil war vorher nicht von einer im Teil zu unterscheiden:
      kein Fehler, kein Befund, ein Verlaufseintrag über nichts.
      `boolean.without_effect` vergleicht das Volumen und gibt eine Warnung
      zurück — Regel 17 verlangt einen Handlungsvorschlag, und der stille
      Fehlschlag stand darunter.
- [x] **Der Objektname reist ins STEP.** Fusion zeigte jeden Import als
      „Open CASCADE STEP translator". Der Name geht jetzt über
      `write.step.product.name` mit, gesetzt *vor* dem Transfer — danach
      gesetzt wirkt er nicht.
- [x] **Der Viewport traf, was angeklickt wurde.** Drei Ursachen
      hintereinander: pyvistas `enable_point_picking` scheiterte still an
      einem fehlenden `_parent`, ein `vtkPointPicker` trifft nur Eckpunkte,
      und ein Merkmal ohne vorher gewähltes Objekt hat niemanden. Jetzt ein
      `vtkCellPicker` im eigenen Interaktionsstil, Objekt vor Merkmal.
- [x] **Die Skizzenleiste lag unter den eingeklappten Bereichen.** Die
      Überlagerung kennt ihre Ränder und sagt sie dem Widget.
- [x] **Ein Rundstab war eine Bohrung.** Der B-Rep-Kern nannte jede
      zylindrische Fläche `hole`, auch die außen liegende. Die Orientierung
      der Fläche unterscheidet sie — `TopAbs_REVERSED` heißt hohl.
- [x] **Der Bericht schwieg über zwanzig Prozent.** Schätzung und G-Code
      liefen auseinander, ohne dass es jemand erfuhr; jetzt vergleicht
      `_compare_totals` Zeit und Material und meldet die Abweichung.
- [x] **Der Drucker kommt aus dem Slicer.** Beim ersten Start stand „Slicer
      gefunden" neben einem vorgeschlagenen 220er, während der Bestand des
      Slicers die eingestellte Maschine kannte.
- [x] **Die Position einer Bohrung ist ihre Mündung** (§25, Formatversion 7).
      `drill` legte den Zylinder mittig auf die Position — und ein Klick
      liefert eine Oberfläche. „Null bohrt durch das ganze Teil" tat das
      dadurch nicht. Der Parameter `anchor` unterscheidet `mouth` von
      `centre`; die Richtung ins Material folgt aus der Hälfte des
      Hüllquaders, damit auch eine von unten angeklickte Fläche stimmt.
      Migration 6 → 7 trägt alten Dateien `centre` ein, `drilled_v6.p3d`
      beweist an einem Volumen, dass sie weiter rechnen wie zuvor.
- [x] **Drei Bausteine bauten über ihrem Ursprung.** `magnet_pocket`,
      `keyhole` und `cable_gland` trugen an der angeklickten Fläche 0,0, 0,0
      und 0,2 mm³ ab. Die anderen dreizehn hielten die Konvention. Jetzt alle:
      Bibliotheksversion 2, Änderungseintrag `MOUTH_AT_ORIGIN`, und ein Test,
      der jeden abziehenden Baustein auf eine Platte setzt und misst, ob sie
      leichter wird.

- [x] **Ein Zylinder hatte einundfünfzig Flächen.** Jeder Mantelstreifen war
      3,4 Prozent der größten Fläche und galt damit als eben — die
      Zylindererkennung, die es längst gab, sah ihn nie. Die Trennlinie steht
      jetzt an der Naht zwischen zwei Dreiecken: koplanar ist dieselbe Fläche,
      ein deutlicher Knick eine Kante, alles unter dreißig Grad dazwischen eine
      Rundung. Zylinder mit Bohrung: vier Merkmale statt einundfünfzig, und ein
      Achteck-Prisma behält seine acht Seiten.
- [x] **Der Weg zur Dose war ein Umweg.** *Aushöhlen* endete immer bei einem
      geschlossenen Hohlraum, *Deckel erzeugen* verlangt eine Öffnung. Der
      Schalter „Oben öffnen" nimmt die Decke weg — das Werkzeug ist der oberste
      Querschnitt des Hohlraums, nach oben durchgezogen. Die Entlüftung
      entfällt dabei: eine offene Dose ist ihre eigene.

### Was die Arbeit gelehrt hat

**Eine Konvention, die nirgends geprüft wird, ist keine.** Dreizehn von
sechzehn Bausteinen bauten unter ihrem Ursprung, drei nicht — und niemand
konnte es sehen, weil kein Test die Wirkung maß, sondern nur Wasserdichtheit
und Wandstärke. Der neue Test prüft nichts Geometrisches, sondern eine
Erwartung: was Material wegnehmen soll, muss weniger Material hinterlassen.

**Eine Migration, die rechnen müsste, rechnet meistens falsch.** Die halbe
Tiefe auf die Position zu addieren hätte die Richtung ins Material gebraucht,
und die steckt in der Geometrie, nicht in der Datei. Ein Parameter, der die
alte Bedeutung festhält, ist ehrlicher als eine Umrechnung, die rät.

## Das Audit vom 06.08.2026 — und was unter dem Code lag

Anlass war eine Durchsicht der ganzen Anwendung. Der Befund zur Sache ist
kurz: der Code ist in Ordnung. Kein `eval`, kein `shell=True`, keine
GPL-Abhängigkeit, kein absoluter Pfad in einer Projektdatei, **kein einziges
TODO oder FIXME** in achtundfünfzigtausend Zeilen, Migrationen v1 bis v7
lückenlos mit eingecheckter Beispieldatei, keine feste Zeichenkette in der
Oberfläche. Vier von fünf Funden lagen deshalb nicht im Code, sondern
darunter.

- [x] **Die Umgebung fuhr Python 3.11, das Projekt verlangt 3.13.** Die `.venv`
      war am 27.07. mit 3.11.9 angelegt, `requires-python` stand längst auf
      3.13, und auf der Maschine gab es kein 3.13. Solange kein 3.12-Feature im
      Code stand, fiel das nicht auf; mit den ersten PEP-695-Typparametern
      (087e321) brach der Import der Anwendung, und damit starben pytest, mypy,
      die Kommandozeile und das Fenster. **`ruff` blieb grün** — es bringt einen
      eigenen Parser mit `target-version` mit und sieht den Interpreter nie an.
      3.13.14 installiert, Umgebung gegen `constraints.txt` neu aufgebaut; dabei
      kamen auch `pypdf` und die sechs Fassungen nach, die von der Datei
      abwichen.
- [x] **Das Tor konnte still durchfallen.** `mypy` meldete „1 error ... errors
      prevented further checking" und prüfte dabei **null** Projektdateien —
      dieselbe Mechanik wie beim numpy-2.5-Vorfall zwei Tage zuvor, nur mit
      anderer Ursache. Zweimal in einer Woche, und nichts im Repository
      unterschied einen Abbruch von einem grünen Lauf.
      `tests/test_toolchain.py` prüft jetzt den laufenden Interpreter gegen
      `requires-python` und die Zielversionen von mypy und ruff gegen dieselbe
      Angabe. Danach: 190 Dateien geprüft statt keiner.
- [x] **Zwei Arbeiter räumten das Feld ihres Nachfolgers.** Das Muster stand
      fünfmal richtig im Haus — mit Kommentar, warum ein Lambda hier nicht geht
      — und zweimal falsch. Siehe Commit; die Regel steht jetzt in
      `.claude/rules/oberflaeche.md`, und ein Test sucht das falsche Muster im
      Quelltext der ganzen Oberfläche.
- [x] **Eine Webseite durfte am offenen Dokument arbeiten.** Bindung und
      Absenderadresse halten keinen Browser auf: der läuft auf diesem Rechner.
      `origin_allowed` kam dazu, die zweite Auflage heißt jetzt „dreimal
      geprüft".
- [x] **Die Zonen setzten sich gegenseitig, bis der Stapel überlief.** Fiel
      erst auf, als die Suite wieder lief — `tests/test_overlay.py` starb beim
      ersten Test, reproduzierbar. Kein reines Testartefakt: `resizeEvent` geht
      denselben Weg, und am Fensterrand zu ziehen ist derselbe Fall.

Stand danach: 2949 Tests grün, `ruff`, `ruff format` und `mypy` grün.

### Was das Audit gelernt hat

**Ein grüner Lauf sagt nur etwas, wenn er auf dem Richtigen lief.** Drei der
vier Werkzeuge des Tors sagten „in Ordnung", während zwei davon gar nichts
prüften und das dritte auf einer Interpreterversion lief, die das Projekt nicht
mehr unterstützt. Was das Tor über sich selbst behauptet, gehört genauso
geprüft wie das, was es über den Code behauptet.

**Eine Lehre, die nur an der Fundstelle gezogen wird, ist halb gezogen.** Der
Absturz durch die verlorene Arbeiter-Referenz war dreimal in `session.py`
behoben, einmal bei der Update-Abfrage, einmal bei der Analysekarte — jedes Mal
mit ausführlichem Kommentar. Zwei Stellen daneben machten weiter den alten
Fehler, und niemand konnte es sehen, weil nichts danach suchte. Dieselbe
Erkenntnis wie bei den drei Bausteinen über ihrem Ursprung, eine Etage höher.

### Offen aus dem Audit

- [x] **Die englischen Docstrings sind übersetzt.** Es waren 56 in `app/`
      über 27 Dateien, dazu acht in `tests/` und `tools/` — fast alles
      einzeilige Attribut-Beschreibungen, die die Sprachprüfung nicht sieht,
      weil sie den Bezeichnern gilt. Erledigt in „Die letzten englischen
      Docstrings zogen nach" (5709245); der Suchlauf, der sie gefunden hat,
      findet jetzt nichts mehr.

## Durchsicht: was außerhalb der Anwendung läuft (07.08.2026)

Anlass war eine einfache Frage — läuft die Erzeugung, läuft der Chat? — gegen
eine echte Installation statt gegen die Suite. Von den vier externen Programmen
waren zwei in Ordnung, eines fehlte, und eines lief, während das, was Solidon
ihm schickte, nie gegen etwas Laufendes gehalten worden war.

- [x] **Die Graphen riefen Knoten, die es nirgends gibt.** Beide mitgelieferten
      Workflows nannten `Hy3DModelLoader`, `Hy3DGenerateMesh` und
      `Hy3DExportMesh` — Namen aus einem anderen Wrapper als dem installierten.
      ComfyUI wies sie beim Abschicken ab. `text_to_mesh` hängte zusätzlich
      einen `CLIPTextEncode` an einen Kern ohne Texteingang: Hunyuan3D kann
      kein Text-zu-3D, Text wird erst zu einem Bild. Beide Graphen laufen jetzt
      gegen `ComfyUI-Hunyuan3d-2-1`, mit SDXL und Freistellen davor.
- [x] **Ein gelungener Auftrag meldete, er habe nichts geliefert.** Die
      3D-Vorschau gibt den Pfad als blanken String zurück, `_download` verlangte
      einen Eintrag mit Feldern und übersprang ihn — die Datei lag auf der
      Platte, die Meldung sagte „kein Modell geliefert".
- [x] **Das empfohlene Modell schrieb seine Aufrufe hin, statt sie zu tun.**
      `qwen2.5-coder:14b` traf null von fünf Anfragen, weil es die Aufrufe als
      Fließtext ausgibt. Vorgabe ist jetzt `llama3.1:8b` (5/5), und
      `tools/check_local_model.py` hält die Messung nachfahrbar.
- [x] **Ollama fehlte ganz.** Installiert, Vorgabemodell geladen, Chat verifiziert:
      Kaltstart 31 s, warme Antwort 2,4 s.
- [x] **OpenSCAD und der Slicer waren in Ordnung.** OpenSCAD rendert,
      ElegooSlicer wird als Orca-Variante erkannt.

Gegengeprüft gegen die Installation: `text_to_mesh` 67 s auf 1,28 Mio Dreiecke,
`image_to_mesh` 40 s auf 550 Tsd, beide wasserdicht und über `read_mesh`
einlesbar. Stand danach: 2967 Tests grün, `ruff`, `ruff format` und `mypy` grün.

### Was diese Durchsicht gelernt hat

**Eine Datendatei ist Code, den niemand testet.** Die beiden Workflow-Graphen
lagen seit ihrer Entstehung im Repository, waren von der Suite abgedeckt — sie
prüfte, dass es gültiges JSON mit `class_type` und einem Platzhalter ist — und
hätten auf keiner Maschine der Welt funktioniert. Was nur gegen sich selbst
geprüft wird, ist nicht geprüft.

**Groß genug heißt nicht werkzeugfähig.** Die Modellwarnung misst
Parameterzahl, weil §27 das so sagt, und 14,8 Milliarden liegen weit über der
Grenze. Die Eigenschaft, an der die ganze Agentenschicht hängt, misst sie
nicht — und Ollamas eigene Fähigkeitsangabe auch nicht.

### Nachgezogen, gleiche Sitzung

- [x] **Die Graphen hängen nicht mehr an konkreten Modellnamen.** Sie nennen
      Rollen (`{model:image}`, `{model:shape}`, `{model:shape_vae}`), und
      `/object_info` sagt, was der Eingang zur Auswahl stellt. Die
      Ausschlussmuster sind der Kern: der Formkern liegt unter denselben
      Checkpoints wie die Bildmodelle. Passt kein Muster, wird genommen was da
      ist; fehlt die Datei ganz, sagt die Meldung genau das.
- [x] **Die Werkzeugprobe hat jetzt ein Feld, das sie prüfen kann.** Dahinter
      lag der größere Mangel: das lokale Modell ließ sich überhaupt nicht
      einstellen. „Zugang zum Sprachmodell" trägt jetzt beide Wege aus §27.
- [x] **Die letzten englischen Docstrings sind übersetzt** — 56 Stellen in 27
      Dateien unter `app/`, acht in `tests/` und `tools/`. Der Punkt oben aus
      dem Audit ist damit erledigt.

### Aus Kundensicht durchgegangen

Nicht der Code, sondern was jemand liest. Zwei Funde, beide auf demselben Weg:

- [x] **Fällt ComfyUI weg, stand dort ein Windows-Fehlercode.** Falscher Titel,
      roher Fremdtext als Grund, „Abbrechen" als einziger Vorschlag.
- [x] **Und selbst der gute Text kam nicht an.** Der Erzeugen-Dialog zeigte nur
      `problem.title`; Grund und Ausweg fielen still unter den Tisch.
- [x] **„Es ist kein Schlüssel hinterlegt"** stand im Zugangsdialog, während
      der Chat über das lokale Modell lief — es liest sich wie „geht nicht".

Dazu eine Lehre mit eigenem Wächter: **einen Fehlertext formatiert niemand
nach.** Ein `{platzhalter}` in `detail` oder `title` bleibt wörtlich stehen,
weil `show_details` den Text zeigt, wie er ist, und die `values` als eigene
Zeilen darunterhängt. In der Oberfläche ist derselbe Platzhalter richtig, dort
steht ein `.format` dahinter. `tests/test_errors.py` sucht im ganzen Kern
danach.

## Jeder Workflow einzeln durchgefahren (07.08.2026)

Nicht die Suite, sondern jeder Weg mit echten Läufen. Was dabei herauskam:

| Bereich | Umfang | Ergebnis |
|---|---|---|
| Operationsregister | alle 76, je ein Lauf | 62 durch, 12 begründete Ablehnungen, **2 Funde** |
| Bausteine | alle 18 über ihren Parameterbereich, 7–23 Proben je | alle sauber, jede Ablehnung begründet |
| Export | STL, 3MF, OBJ, PLY, STEP | vier rund und zurücklesbar; STEP lehnt Netze richtig ab |
| Schichtanalyse | 0,1 / 0,2 / 0,3 mm | 55 ms bei 0,2 mm — weit im Budget aus §31 |
| Oberfläche | Aufbau, Projekt laden, schließen | 0,47 s, **9 Menüs** (die Grenze), sauber zu |
| Handbuch | `manual.as_markdown()` | 102 730 Zeichen, 109 Abschnitte, 0,02 s |
| Erstinbetriebnahme | `tools.survey()` | alle vier Programme gefunden |
| Schnittstelle nach außen | `origin_allowed` in acht Fällen | hält, auch gegen `evil.localhost.attacker.com` |
| Auto Split | 300-mm-Körper auf 256er Bett | Befund, dann verstiftet in zwei geschlossene Körper |

Die beiden Funde waren derselbe, und er betraf **jede** Operation: Im
Prüfbericht stand die Entwicklernotiz statt des Satzes — `malformed target ''`
und eine halbe Seite roher OpenSCAD-Ausgabe, während „Das Ziel muss ein
Merkmal eines Objekts benennen" in `values` lag. Behoben, indem nur ein
übersetztes Detail nach vorn darf.

**Was dabei auffiel und keiner Änderung bedurfte:** die Ablehnungen. „Dieser
Körper ist schon geschlossen — eine zweite Haut darüber", „Der Körper ist auf
dieser Höhe massiv", „Die Wand ist für diese Steigung zu dünn". Zwölfmal
sagte das Programm genau, warum es nicht weitermacht. Das ist der Teil, den
ein Durchlauf wie dieser sonst nicht sichtbar macht.

## Die Wege einmal von Hand gefahren (07.08.2026)

Nicht die Suite, sondern die Anwendung: Weg 1 und 2 über die Kommandozeile,
die Übergabe an den echten ElegooSlicer, der Agent gegen ein lokales Modell,
dazu der Korpus mit seinen kaputten Dateien. Sechs Funde, alle auf dem
geradesten Weg, den es gibt.

- [x] **„Ein Objekt steht über den Bauraum hinaus"** bei einem 8 mm hohen Teil
      auf einem 256er Drucker. Es stand nicht hinaus, es lag halb unter der
      Platte — ein heruntergeladenes STL ist um den Ursprung zentriert. Der
      Satz schickt zum Skalieren, nötig war ein Aufsetzen.
- [x] **„Ein Merkmal hat keinen Nachfolger mehr"** als Warnung nach jedem
      Aushöhlen mit offener Decke. §21.3 knüpft das Melden an einen Verweis;
      ohne Verweis ist es eine Feststellung.
- [x] **`import` ohne `--unit` stürzte mit einem Stapelabzug ab**, sobald
      niemand antworten kann — in einer Pipe, einem Skript, auf einem
      Bauserver.
- [x] **`new --material PETG` legte eine kaputte Datei an.** Der Fehler kam
      erst beim nächsten Befehl. Die Falle ist eingebaut: `profiles` zeigt den
      Titel `PETG`, die Kennung ist `petg`.
- [x] **Die Slicer-Übergabe verlangte nur eines der zwei nötigen Profile.**
      Ohne Prozessprofil lehnt die Orca-Familie Solidons Prozessdatei ab.
      Mit beiden läuft der ganze Weg bis zu den G-Code-Kennzahlen.
- [x] **`tools/run_agent_suite.py` lief überhaupt nicht** — kein
      `load_operations()`, also leeres Register. Derselbe fehlende Aufruf in
      `check_local_model.py` hat die Modellwahl vom Vortag verdorben: gemessen
      wurde mit sieben Werkzeugen, der Agent bietet dreiundachtzig an.

### Was diese Begehung gelernt hat

**Ein leeres Register wirft keinen Fehler, es liefert nur weniger.** Beide
Werkzeuge außerhalb von Anwendung und CLI hatten denselben fehlenden Aufruf;
eines starb daran sichtbar, das andere lieferte still eine Zahl, die eine
Entscheidung getragen hat.

**Der Normalfall bekommt die schlechtesten Meldungen.** Beide Warnungstexte
oben standen nicht bei einem Fehler, sondern nach einer gelungenen Handlung —
und je häufiger eine Warnung zu Unrecht steht, desto weniger wert ist der
Platz, an dem die echten stehen.

### Nachgezogen

- [x] **Der flaky Beispieltest war rtree**, das in fremden Speicher greift —
      eine Zugriffsverletzung in etwa jedem zwanzigsten Lauf, im Stapel
      `rtree/index.py:832`. `mesh.on_surface` fragt jetzt für alle drei
      Aufrufer und wiederholt einmal an einer Kopie des Netzes. Vorher 1 von
      20 rot, danach 0 von 40.
- [x] **Der Fortschritt trägt die verstrichene Zeit** und, wer wartet, seine
      Position in der Warteschlange.
- [x] **Die Agenten-Suite läuft und steht bei 8/33** (qwen3:14b, volles
      Register). Die eine Zahl, die §40 nicht als Quote führt, sondern als
      Regel, ist erreicht: **3/3 bei Mehrdeutigkeit gefragt**. Schwach bleibt
      „Baustein statt eigener Geometrie" mit 0/13.
- [x] **Eine Operation ohne Eingangsobjekt** stürzte mit einem `IndexError`
      ab, statt anzuhalten — `example_v1.p3d` ließ sich damit gar nicht öffnen.

### Offen

- [ ] **Diese Maschine rechnet sporadisch falsch — es ist keine Bibliothek.**
      Der Verdacht lag zuerst auf `rtree`; **das war falsch**, und die
      Korrektur ist der eigentliche Ertrag. Weiter eingegrenzt, jede Variante
      im eigenen Prozess:

      | Aufbau | Ergebnis |
      |---|---|
      | fertige Zahlenfelder + Trimesh, `rtree` geladen | 30/30 |
      | XML lesen + `np.array`, `rtree` geladen | 29/30 |
      | dasselbe, **`rtree` gesperrt** | 27/30 |
      | `np.array` über reine Python-Zeichenketten, **ohne XML** | 39/40 |
      | `np.fromiter` über Pythons eigenes `int()` | 57/60 |
      | reine Gleitkommaarbeit über SIMD | 40/40 |
      | reine Python-Arithmetik auf 32 Kernen | 72/72 |

      Damit fallen alle Verdächtigen der Reihe nach aus: nicht `rtree` (ohne
      es bleibt es rot, mit ihm und fertigen Feldern grün), nicht der
      XML-Leser (`lxml` verhält sich gleich, und ohne XML bleibt es rot),
      nicht NumPys Parser (Pythons `int()` ist genauso betroffen). Was übrig
      bleibt, ist die Kombination aus **vielen Speicherobjekten und ihrer
      Umwandlung** — und einmal kam dabei still eine falsche Summe heraus:
      `9.599.875.422` statt `9.599.880.000`, ohne jede Ausnahme.

      Die Maschine: i9-13900K (Raptor Lake, die Familie mit dem bekannten
      Instabilitätsproblem), 2×32 GB DDR5 auf 4800 MHz, zwei unerwartete
      Neustarts (14.07. und 20.07.2026), nie eine Speicherdiagnose gelaufen.

      **Am 08.08.2026 nachgemessen, und zwei Angaben oben stimmten nicht:**

      - **Es gibt einen WHEA-Eintrag.** 03.06.2026, ID 19: „Behobener
        Hardwarefehler, gemeldet von Komponente Prozessorkern, Fehlerquelle
        Corrected Machine Check, Fehlertyp **Translation Lookaside Buffer
        Error**, APIC-ID 40." Das zeigt auf die **CPU**, nicht auf den
        Speicher — und es ist genau das Fehlerbild, für das Raptor Lake
        bekannt ist. Er steht zudem *nach* dem BIOS vom 01.04.2026. Weiter
        zurück als der 29.04.2026 reicht das Protokoll nicht; ältere Einträge
        sind rotiert.
      - **Der Microcode ist nicht 0x12F, sondern 0x133** (Registry,
        `Update Revision`), also neuer als notiert.
      - **Der Rechenfehler ließ sich heute nicht reproduzieren.** 300 Runden
        derselben Bauart (17,7 MB XML, 200 000 Punkte und Dreiecke, `rtree`
        geladen): null Ausnahmen, null stille Abweichungen. Bei der gemessenen
        Rate von eins zu dreißig wären rund zehn Fehlschläge zu erwarten
        gewesen; dass keiner kam, ist mit 0,004 % Wahrscheinlichkeit
        Zufall. Das heißt nicht „behoben" — es heißt, dass die Bedingung
        fehlt, unter der er auftrat.

      **Nächster Schritt ist keiner am Code.** Wegen des TLB-Befunds zuerst
      die CPU: Intel Processor Diagnostic Tool, und bei Auffälligkeiten die
      verlängerte Garantie für 13./14. Generation. Der Speichertest bleibt
      daneben richtig, ist aber nicht mehr der erste Verdacht. Die zwei
      Pflaster (`mesh.on_surface`, `threemf._numbers_from`) bleiben: einmal
      wiederholen, beim zweiten Fehlschlag durchlassen. Sie sind gegen ein
      Symptom gebaut, nicht gegen eine Ursache — und wenn die Maschine der
      Grund ist, sind sie genau richtig, denn dagegen hilft kein Code.
- [x] **Der Agent greift nicht zu den Bausteinen (0/13) — es war das
      Kontextfenster.** Am 08.08.2026 gefunden, und es macht die ganze
      Untersuchung darunter zur Vorgeschichte: **Ollama schneidet den Prompt
      stillschweigend ab.** Sein Vorgabefenster ist 4096 Token, Solidon setzte
      `num_ctx` nicht, und allein die 84 Werkzeugschemata sind rund 99 000
      Zeichen — gemessen 21 162 Token. Was nicht hineinpasste, fiel weg, und
      mit ihm der Systemprompt samt der vier Vorrangregeln. Das Modell war
      nicht ungehorsam; es hat den Auftrag nie gesehen.

      Gemessen mit `qwen3:14b` an drei Anfragen, für die ein Baustein die
      richtige Antwort ist:

      | Fenster | verarbeitet | je Frage | Baustein |
      |---|---|---|---|
      | 4096 (Vorgabe) | 2 050, Rest weg | 30,1 s | 0 von 3 |
      | 8 192 | 4 098, Rest weg | 34,1 s | 0 von 3 |
      | 16 384 | 8 194, Rest weg | 36,1 s | 0 von 3 |
      | **32 768** | **21 162, ganz** | **21,2 s** | **3 von 3** |

      Das volle Fenster ist nicht nur richtiger, sondern **schneller** — ein
      Modell, das den Auftrag kennt, rät nicht herum. Es kostet Speicher: mit
      32 768 belegt `qwen3:14b` 14 GB und bleibt zu 100 % auf der Karte.
      `OLLAMA_CONTEXT_TOKENS` in `backends/llm.py` hält Wert und Messreihe.

      **Die volle Suite dazu, und sie hat zwei Seiten.** 33 Anfragen,
      `qwen3:14b`, gegen den Stand vor der Änderung:

      | Maß | vorher | nachher |
      |---|---|---|
      | gut beantwortet | 8/33 | **17/33** |
      | Baustein statt eigener Geometrie | **0/13** | **6/13** |
      | bei Mehrdeutigkeit gefragt (§40) | **3/3** | **1/3** |
      | Hauptmaße als Parameter | — | 2/3 |
      | Zeitüberschreitungen | 17 (mit 30b) | 2 |

      Die Gesamtquote verdoppelt sich, der gemeldete Befund ist weg — und
      **eine Zahl ist gefallen, und zwar die, die §40 als Regel führt.** Von
      den drei mehrdeutigen Anfragen fragt nur noch `join_what`;
      `which_hole` („Mach das Loch größer" bei vier Bohrungen) und
      `how_much_thinner` („Mach das Teil dünner") raten stattdessen —
      `which_hole` mit zwanzig Aufrufen von `drill_hole` und `plug_hole`
      hintereinander.

      Das ist die Kehrseite desselben Fundes: Wer alle vierundachtzig
      Werkzeuge sieht, findet immer eines, das plausibel aussieht. Vorher war
      die Auswahl beschnitten, und `ask_user` blieb übrig — die 3/3 waren
      also kein Gehorsam, sondern Mangel an Alternativen. Es bleibt
      trotzdem ein Verstoß gegen Regel 21 und gegen ein Abnahmekriterium.

      **Behoben im Systemprompt, Version 2.** „Fragen vor Raten" stand als
      vierte von vier Gewohnheiten — anleitend, nicht verhindernd. Davor steht
      jetzt eine Vorbedingung mit drei Prüfungen, von denen jede einzelne für
      eine Rückfrage genügt: Ziel eindeutig (ein Merkmal, das mehrfach
      vorkommt, und keines ausgewählt), Maß genannt (ein Vergleich ist kein
      Maß), Bezug vorhanden (mehr Objekte genannt als im Steckbrief). Dazu der
      Satz gegen das Herumprobieren — `which_hole` hatte zwanzig Aufrufe
      hintereinander abgesetzt: „Trifft eine der drei zu, rufe ask_user auf und
      sonst nichts."

      Die drei Prüfungen sind allgemein formuliert und nicht als Sonderfälle
      der drei Testanfragen. Auf die Suite hin zu optimieren hieße, sie als
      Maßstab zu verlieren.

      | Maß | vor `num_ctx` | Prompt v1 | **Prompt v2** |
      |---|---|---|---|
      | gut beantwortet | 8/33 | 17/33 | **22/33** |
      | Baustein statt eigener Geometrie | 0/13 | 6/13 | **8/13** |
      | bei Mehrdeutigkeit gefragt (§40) | 3/3 | 1/3 | **3/3** |
      | Hauptmaße als Parameter | — | 2/3 | 2/3 |
      | Schritte im Mittel | — | 4,1 | 4,4 |

      Kein Maß ist gefallen, also bleibt die Änderung — die Rücknahmeregel aus
      `AGENTS.md` greift nicht. Gewonnen haben `on_bed`, `orient` (vorher
      Zeitüberschreitung) und `split`.

      **Nachgesehen bei den zwei, die als verloren dastanden** — und eine der
      beiden Aussagen war falsch:

      - `handrail_bend` fiel nur unter Prompt 2 und wählt seither wieder
        `sketch_sweep` mit `shape=circle, length=12, bend_radius=60,
        bend_angle=90`. Das ist richtig; bei einem Kreis ist `length` das
        Querschnittsmaß. Und der Ausrutscher davor war geometrisch nicht
        einmal falsch: `sketch_revolve` hat einen Winkel und einen
        Achsabstand, ein Ø12-Kreis bei 54 mm und 90° ergibt denselben Bogen.
        Der Fall akzeptiert nur `sketch_sweep`, was vertretbar ist.
      - `pocket_plate` war **nie gewonnen** — es stand schon vorher rot, und
        die Ursache lag nicht bei der Op-Wahl. Ein Mitschnitt des Zuges zeigte
        sie: `create_box` erzeugt ein Netz, `sketch_pocket` scheitert daran
        viermal, und die einzige Auskunft lautete „Die Auswertung hält bei
        dieser Operation an". Der Grund stand die ganze Zeit im Prüfbericht —
        „Der gewählte Körper ist ein Netz" — und kam nur nicht an. Das Modell
        drehte deshalb an den Zahlen statt am Körpertyp.

      Behoben an zwei Stellen. `checks.check` reicht die Befunde der
      anhaltenden Operation durch. Und die Antwort ans Modell nimmt die
      `values` mit: die Fehlertexte des Kerns tragen keine Platzhalter, „Der
      Wert liegt unter dem zulässigen Mindestwert" ist der ganze Satz, und was
      er meint, stand daneben. Der Feldname gehört dabei ausdrücklich dazu —
      ohne ihn korrigierte das Modell dreimal die Tiefe, während `corners` die
      Grenze riss.

      Danach fährt derselbe Fall so: `create_brep_box` beim ersten Versuch
      exakt, `corners=0` → „field=corners, minimum=3" → korrigiert, ein
      Objektname statt einer ID → „missing=['deckel']" → korrigiert, und
      `sketch_pocket` läuft. Vier Schritte statt fünf, und jede Meldung führt
      zu einer gezielten Korrektur statt zu einem neuen Versuch.

      **Wogegen gemessen wurde**, weil es sonst später niemand zuordnen kann:
      der Stand vor `b8829c3` und `ecf4544`. Beide ändern Kontextaufbau,
      Werkzeuge und Steckbrief — also genau das, was diese Messung als
      Umgebung hatte. Wer die Zahlen fortschreibt, misst neu.

      **Das ändert eine Angabe, die dem Kunden gemacht wird.** Beide
      Startseiten und der Hinweis im Modelldialog nannten „rund 10 GB
      Grafikspeicher" — das galt für das Modell allein (9,3 GB). Mit dem
      Kontextfenster kommt der Schlüssel-Wert-Zwischenspeicher dazu, gemessen
      14 GB für das Modell und 15,7 GB belegt insgesamt. Die
      Systemvoraussetzung steht deshalb jetzt bei **16 GB**, in beiden
      Sprachen. Eine Karte mit zwölf würde auf die CPU auslagern — also genau
      die Zeitüberschreitungen zurückholen, die oben als Ausstattungsfrage
      standen.

      **Was daraus für die Vorgeschichte folgt:** Jede Zahl unten entstand
      unter abgeschnittenem Prompt. Die Werkzeugmengen-Tabelle misst nicht,
      wie gut ein Modell mit vielen Werkzeugen umgeht, sondern **ab wann sie
      nicht mehr ins Fenster passen** — bei zehn taten sie es, bei
      dreiundachtzig nicht. Und der Modellvergleich (`qwen3:30b-a3b` fünf von
      fünf gegen `qwen3:14b` in Prosa) verglich zwei Modelle, von denen
      keines den Systemprompt vollständig bekam. Er gehört wiederholt, bevor
      jemand daraus eine Anschaffung ableitet.

      <details><summary>Die Untersuchung, die zur falschen Fährte führte</summary>

      Nachgemessen wurde die Werkzeugmenge, mit demselben Fall und
      demselben Modell (`qwen3:14b`):

      | Angebot | wall_holder | magnet_lid | spacer |
      |---|---|---|---|
      | 10 Werkzeuge | `find_part` | `find_part` | `find_part` |
      | 25 Werkzeuge | `create_box` … | `create_from_scad` | `create_brep_cylinder` ×4 |
      | 83 Werkzeuge | `sketch_sweep` … | Prosa | Prosa |

      Bei zehn Werkzeugen folgt das Modell der Vorrangregel dreimal von drei —
      `find_part` ist genau der erste Schritt, den „Bausteine vor Primitiven"
      verlangt. Bei fünfundzwanzig bricht sie, bei dreiundachtzig antwortet es
      gar nicht mehr strukturiert. Der Systemprompt wird also gelesen und
      verstanden; was fehlt, ist die Fähigkeit, ihn unter voller Werkzeuglast
      in Aufrufe zu übersetzen.

      Damit ist es keine Regelfrage mehr. Und auch keine Bauplanfrage: §26.2
      schreibt „alle Ops aus dem Register" vor, und **das kann bleiben** —
      `qwen3:30b-a3b` trifft mit allen dreiundachtzig Werkzeugen fünf von
      fünf, wo `qwen3:14b` in Prosa fällt. Eine Auswahl nach `applies_to`
      wäre also nicht nötig, und sie wäre auch das, was §2 für die Oberfläche
      ausschließt.

      Nur nützt das auf **dieser** Maschine nichts: Das Modell belegt 19 GB,
      die Karte hat 16, es läuft zu einem Viertel auf der CPU — und die volle
      Suite endete bei 4/33, davon **17 Zeitüberschreitungen**. Gemessen wurde
      damit die Wartezeit, nicht die Fähigkeit. `qwen3:14b` passt in den
      Speicher und bleibt mit 8/33 die bessere Wahl, also auch die Vorgabe.

      | Modell | Werkzeugtest | Suite | Anmerkung |
      |---|---|---|---|
      | `qwen3:14b` | 4/5 | **8/33** | 9,3 GB, passt in den Speicher |
      | `qwen3:30b-a3b` | **5/5** | 4/33 | 19 GB, 17 Zeitüberschreitungen |

      Beide erfüllen die eine Zahl, die §40 als Regel führt: 3/3 bei
      Mehrdeutigkeit gefragt.

      Offen bleibt damit nicht die Regel, sondern die Ausstattung — und
      nebenbei ein Wert: `llm.TIMEOUT_SECONDS` steht auf 120, und ein lokales
      Modell mit CPU-Anteil braucht bei vollem Kontext länger. Ihn pauschal
      hochzusetzen verlängert aber die Wartezeit im Chat für alle; das will
      eigens entschieden werden.

      </details>

      Der Wert daneben hat sich damit auch geklärt: `llm.TIMEOUT_SECONDS`
      bleibt bei 120. Mit vollem Fenster antwortet `qwen3:14b` in 21 Sekunden
      und vollständig auf der Karte — die Zeitüberschreitungen kamen vom
      CPU-Anteil eines Modells, das nicht hineinpasste, nicht von der Grenze.

## Jeden Weg einzeln durchgespielt (07.08.2026, zweiter Durchgang)

Nicht über die Kommandozeile wie beim ersten Mal, sondern über die Verträge
selbst: Weg 1 gegen alle vierzehn Korpusdateien, Weg 2 über neunundfünfzig
Operationen mit ihren Vorgabewerten, Weg 3 gegen Werkzeugschemata,
Transaktionsregel und Quelltextprüfung. Vier Funde, und der größte davon
betrifft jede Fehlermeldung der Anwendung.

- [x] **Dreizehn von vierzehn Korpusdateien bekamen eine Bauraumwarnung.**
      `_message_for` unterschied längst drei Fälle — unter der Platte, neben
      der Platte, größer als der Bauraum —, die Schwere nicht. Damit warnte
      fast jede geladene Datei, denn ein heruntergeladenes Teil ist um den
      Ursprung zentriert. Die Trennlinie ist jetzt, ob das Teil nach dem
      Verschieben hineinpasst: dann ist es ein Hinweis. Über den Korpus
      gemessen bleibt eine Warnung übrig — `oversized.stl`, die einzige, auf
      die sie zutrifft.
- [x] **Jede Ausnahme nannte ihre Art und verschwieg ihren Grund.**
      `AppError.__init__` übergab nur den Titel an `Exception`. Der ist je
      Klasse gleich: über jedem `ValidationError` stand „Ein Wert liegt
      außerhalb des zulässigen Bereichs", ob es um eine Wandstärke ging oder
      um ein fehlendes `@` vor einem Parameternamen. Die Oberfläche liest
      beide Felder einzeln und merkte nichts; Protokoll und Traceback zeigten
      allein diesen Satz.
- [x] **Der Titel für Grammatikfehler war der falsche.** Bei einem unlesbaren
      Ausdruck liegt nichts außerhalb eines Bereichs.
- [x] **Der Steckbrief bot dem Agenten `-1.11022e-16` als Ort an.** Ein
      zentrierter Quader landet rechnerisch knapp neben null. Der Agent hat
      keine andere Quelle als diesen Text und liest die Zahl als Wert, der
      etwas bedeutet. Nebenbei wurde der Steckbrief um 64 Zeichen kürzer —
      bei jedem Aufruf.

### Was dieser Durchgang gelernt hat

**Eine Warnung, die fast immer dasteht, ist keine Warnung mehr.** Dasselbe
Muster wie beim ersten Durchgang, nur an anderer Stelle: der Platz, an dem die
echten Warnungen stehen, verliert seinen Wert mit jeder unberechtigten.

**Was die Oberfläche richtig zeigt, kann anderswo falsch ankommen.** Die drei
Fehlertext-Funde lagen alle daran, dass `title` und `detail` in der Oberfläche
getrennt gelesen werden und überall sonst nicht. Ein Fehlerpfad ist erst
geprüft, wenn er auch außerhalb des Dialogs gelesen wurde.

**Nicht jeder rote Befund ist ein Fund.** Vier Alarme dieses Durchgangs waren
Fehler im Prüfskript: eine Op, die anders heißt, ein Parameter, der `@`
braucht, eine Quelle, die zweimal eingetragen werden will, und eine
Sicherheitsprüfung, die ein Ergebnis zurückgibt statt zu werfen. Die
Quelltextprüfung nach §32 lehnt absolute Pfade, Schritte nach oben, URLs und
sogar `import(variable)` zuverlässig ab.

## Puppenhaus: beide Wege an einem Stück (07.08.2026)

Ein Puppenhaus für ein Kind — Architektur gezeichnet, Einrichtung erzeugt.
Gebaut wurde live in der Anwendung über Menüeinträge, Zeichenfläche und
Dialoge, nicht über die Session-API: was zwischen Menü und Geometrie liegt,
lief damit mit.

### Was trägt

- **Der Zeichenmodus trägt.** Rechteck 180 × 120 eingesetzt, elf
  Zwangsbedingungen, „Bestimmt — alle Freiheitsgrade sind vergeben", Fertig,
  Dialog, Körper. Boden 86,4 cm³ auf den Millimeter.
- **Speichern und Öffnen tragen.** Titel wechselt, `modified` wird falsch,
  Volumen vor und nach dem Neustart identisch bis auf drei Nachkommastellen.
- **Die Generierung trägt.** Vier Möbel über `ComfyBackend`, 16 bis 51
  Sekunden je Stück, alle vier angekommen.

### Was nicht trägt

- [x] **Vierzehn Werkzeuge in einer Zeile, jedes zweite Wort abgeschnitten.**
      Gemessen 1165 px nötig, 70 px je Knopf zugeteilt, 1800 px vorhanden.
      Behoben mit Zeichen statt Beschriftung.
- [x] **Objektbaum elf Pixel hoch, nötig hundertdrei.** `fit_to_rows` bemisst
      die Liste, nicht die Karte. Der Verlauf ebenso.
- [x] **Die Wiederherstellung fragte mit Ja und Nein** und verschwieg, wie alt
      die Sicherung ist.
- [x] **Aushöhlen macht aus einem exakten Körper ein Netz.** Danach lehnte
      „Tasche schneiden" ab: „braucht einen B-Rep-Körper; hier liegt ein
      Netz." Der Fehler kam erst drei Schritte später, und der Satz stand
      neben einer Operation, die nichts dafür konnte. Die Auswertung sagt es
      jetzt sofort (`evaluate.exact_became_mesh`) — an einer Stelle, und
      damit für **jede** Netz-Operation auf einem exakten Körper, nicht nur
      fürs Aushöhlen.
- [x] **`scale_object` deckelt bei Faktor 100, Weg 3 braucht mehr.** Was aus
      ComfyUI kommt, ist auf einen Einheitswürfel normiert: die vier Möbel
      maßen 0,6 bis 2,0 mm. Der Schrank hätte 141,7 gebraucht und blieb
      1,3 mm groß. Beides ist beantwortet: `fit_to_size` nimmt das Zielmaß
      statt eines Faktors und steht in der Generierungskette (`load`,
      `fit_to_size`, `repair`) — und der Faktor selbst reicht jetzt von einem
      Tausendstel bis Tausend. Hundert war willkürlich; tausend deckt den Weg
      vom Einheitswürfel bis an jeden Bauraum ab.
- [x] **Was ComfyUI liefert, ist nirgends wasserdicht.** Alle vier Möbel kamen
      offen an, mit 625 000 bis 1 229 000 Dreiecken. Sie kamen **geschlossen**
      an und wurden es hier nicht mehr: Verschweißen und Entarten messen
      absolut, und auf einem Einheitswürfel lag nicht der Doppelpunkt unter
      der Toleranz, sondern die halbe Lehne. Erst auf Maß, dann bereinigen —
      alle vier bleiben dicht und behalten 99,9 % ihrer Dreiecke.

## Gewürzdeckel: der Fehler saß im Deckel, nicht im Becher (07.08.2026)

Fotos vom gedruckten Deckel zeigten das Innere voller Fäden. Nachgemessen mit
Solidons Schichtanalyse und mit dem ElegooSlicer, beide am selben Teil.

### Der Befund

`deckel_basis.stl` hat bei **z = 13,10 einen Überhang von 845,6 mm²** auf einer
einzigen Schicht — vier Fünftel des gesamten Überhangs des Teils. Die
Lochplatte sitzt auf einem Vollzylinder, dessen Bohrung bei z = 13 endet: sie
fängt über der ganzen Gewindebohrung in der Luft an.

Der ElegooSlicer bestätigt es aus seiner Sicht. Auf dieser Höhe fährt er
**4909 Segmente `Bridge` und 12552 `Overhang wall`**.

Das ist derselbe Fehlertyp, den die Spezifikation als Nr. 5 führt — die
waagerechte Ringschulter im Becher, dort mit 2328 Brückensegmenten gemessen
und mit einem 45-Grad-Kegel behoben. Am Deckel wurde er nie gesucht, und er
ist **doppelt so groß**. Der Becher selbst ist sauber: höchstens 3,7 mm² je
Schicht.

Nicht die Ursache war dagegen das Profil (Nr. 6): der G-Code trägt
`print_settings_id = Gewuerzset @ECC2`, das eigene Profil wird geladen.

### Was eine Fase davon einfängt

Gemessen an vier Varianten: eine Hohlkehle unter der Platte halbiert es auf
404,8 mm², mehr gibt die Geometrie nicht her — die Platte muss über den
Behälterhals spannen, und der ist Ø 28 bis 35. Ein Trichter *in* der Platte
misst zwar besser, zerstört sie aber (23 % Volumenverlust). Offen bleibt damit
die konstruktive Frage, nicht die Diagnose.

### Zusammenspiel mit dem ElegooSlicer

- [ ] **`machine_profile` und `base_process` müssen Pfade sein, nicht Namen.**
      Der Docstring von `SlicerSetup` sagt das Gegenteil: „Namen aus dem
      Bestand des Slicers, keine Pfade — sie reisen so auch in eine
      Projektdatei, ohne gegen Regel 12 zu verstoßen." Mit Namen bricht der
      Lauf ab (`can not find setting file`), und das geschriebene Prozessprofil
      hat 42 Schlüssel ohne `inherits` und ohne `compatible_printers`. Mit
      Pfaden sind es 62 mit beidem, und der Lauf endet mit Rückgabe 0.
      Beides zugleich geht nicht: die Datei braucht den Namen, der Aufruf den
      Pfad. Die Auflösung gehört zwischen beide — heute fehlt sie.
- [x] Gefunden werden die Profile einwandfrei: 3887 Stück, die im Slicer
      eingestellte Maschine erkannt, sieben passende Prozesse dazu.
- [x] Der Rücklauf stimmt: Solidon liest seinen eigenen G-Code mit 10,38 g,
      72 min, 110 Schichten, 0,2 mm — und `extrudes()` sagt ja.

## Vollständige Verifikation des Gewürzsets (07.08.2026)

Alle vier Teile durch alle drei Ebenen: Solidons Schichtanalyse, die Übergabe
an den ElegooSlicer über Solidons eigenen Weg, und der zurückgelesene G-Code.

| Teil | Überhang schlimmste Schicht | Übergabe | G-Code |
|---|---|---|---|
| Deckelbasis | **845,6 mm² bei z 13,10** | ok | 10,38 g · 72 min |
| Streuscheibe | 0,0 mm² | ok | 2,46 g · 13 min |
| Behälter | 3,7 mm² | ok | 24,26 g · 97 min |
| Wandregal | 3253,6 mm² bei z 46,10 | ok | 139,32 g · 493 min |

Die Gegenprobe (`handover.verify`) meldet bei allen vier **null Abweichungen**:
der Slicer übernimmt jeden Wert, den Solidon schreibt. Alle vier fördern
Material.

### Der Unterschied zwischen Deckel und Regal

Beide melden einen 90-Grad-Überhang, und beim Regal ist er viermal so groß —
gemessen nachgeprüft: bei z 46,00 springt die Fläche in zwei Hundertsteln
Millimeter um 250 %, und dort liegen vier Dreiecke mit der Normalen genau nach
unten. Trotzdem fährt der Slicer dort nur **108 Brückensegmente**, am Deckel
aber **4909**.

Der Grund ist nicht die Geometrie, sondern was darunter liegt. Im Regal steht
Füllung (`Sparse infill` über die ganzen Schichten darunter), und die trägt.
Unter der Lochplatte des Deckels ist die Gewindebohrung — ein echter
Hohlraum, in dem nichts steht.

**Das ist eine Grenze von Solidons Schichtanalyse, die man kennen muss:** sie
misst die Geometrie und weiß nichts von der Füllung, die der Slicer später
hineinlegt. Ein gemeldeter Überhang über gefülltem Volumen ist deshalb kein
Befund, einer über einem Hohlraum schon. Wer die Zahl allein liest, hält das
Regal für schlimmer als den Deckel — und es ist umgekehrt.

### Und von Hand, über beide Oberflächen

Derselbe Deckel noch einmal, aber über die Bedienung statt über die Verträge:
Modell einfügen, Druckeinstellungen öffnen, Slicen drücken.

- **Modell einfügen** über `session.import_model`: ein Körper, 40 × 40 × 22 mm,
  9,12 cm³, geschlossen. Ein Befund, und der stimmt („Doppelte Punkte wurden
  verschweißt").
- **Die Profilsuche braucht 1,3 s** und läuft in einem Arbeiter-Thread; solange
  steht der Hinweis „Automatisch zugeordnet …" im Dialog. Danach: 1001
  Maschinen, 7 passende Prozesse, 42 Filamente — jede Liste **von selbst
  richtig vorbelegt** (Centauri Carbon 2 · 0.20mm Standard · Elegoo PETG),
  und alle drei tragen Pfade, die es gibt.
- **Der Dialog misst 561 × 867 px und braucht genau so viel** — nichts
  abgeschnitten.
- **Slicen** endet nach einer Sekunde mit „Druckzeit: 73 min · Material:
  10.6 g · Schichten: 110" in der Statuszeile. Der G-Code ist da (4657 KB),
  fördert Material, und von vier Befunden ist keiner eine Warnung.

Der Weg über die Oberfläche war nie vom Namen-gegen-Pfad-Fehler betroffen: der
Dialog legt `str(entry.path)` in die Auswahl, also von jeher die Datei. Wen es
traf, war jeder andere Aufrufer — die Kommandozeile, ein Skript, der Agent.

## Aus Kundensicht vollständig nachgefahren (08.08.2026)

Zehn Bedienläufe am echten Programm, **im Vollbild** (2560 × 1369 px), über den
Qt-Ereignisweg und den VTK-Interactor. Ergebnis:
**`konzept-kundensicht-2026-08.md`** im Projektwurzelverzeichnis.

Durchgegangen: Erstinbetriebnahme mit frischem Nutzerverzeichnis · alle neun
Menüs mit 127 Einträgen · alle 77 Operationen, davon 72 Dialoge einzeln
vermessen · Viewport mit Auswahl, Merkmalen, Kontextmenü, beiden Messarten ·
alle sieben Analysekarten · Schichtenvorschau · alle sechs Zonen · Katalog ·
Skizzeneditor · sieben weitere Dialoge · Druckeinstellungen mit Profilsuche ·
Export in vier Formate und zurück · Handbuch · Auto Split · Rückgängig ·
Übersetzungskatalog · alle 14 Fehlerklassen.

### Die drei Befunde, aus denen die Arbeit folgt

1. **Die Karten wachsen nicht mit dem Fenster.** Im Vollbild bei 1188 px
   verfügbarer Höhe: Objektbaum 321 px statt 751 (Rollbalken, während unter
   der Karte 300 px leer bleiben), Prüfbericht 316 px mit Rollbalken bei
   **fünf** Befunden, Chat 170 px, Tour schneidet jeden Schritt ab. Zwei
   Ursachen: der feste Zeilendeckel `MAX_ROWS = 12` (`panels.py:981`, gesetzt
   über `setFixedHeight`) und `natural_height` (`overlay.py:160`), das für
   umbrechende Listen mit `sizeHintForRow` rechnet — ein zweizeiliger Befund
   gilt ihm als einer.
2. **Eine Parameteränderung kostet 9–15 s statt der 2 s aus §31.** Gemessen an
   `dose-mit-deckel.p3d`, sieben Ops: `hoehe` 40 → 60 braucht 14,75 s, 60 → 45
   dann 9,49 s, 45 → 40 nur 0,75 s — der letzte Wert lag im Cache. Jeder
   **neue** Wert kostet also zweistellig, und genau die sind es, um die es beim
   Drehen an einem Maß geht. Ohne Fremdlast gemessen (1 % CPU).
3. **Der Prozess stirbt gelegentlich.** Einmal in zehn Läufen: rtree-Zugriffs-
   verletzung, unmittelbar danach `SystemError: setobject.c:2676` beim
   Set-Zugriff in `features.py:261`, dann Segfault. Der Wiederholversuch in
   `mesh.py:180` heilt den Aufruf, nicht den Speicher.

### Weiteres

- Das Kontextmenü im Bild bietet zwei Einträge („Ausblenden", „Alles andere
  ausblenden") — §18.5 sieht dort `applies_to` vor.
- „Bohrung setzen" öffnet auf X/Y/Z = 0,00. Bei `weg1-halterung` liegt der
  Ursprung im Teil und es greift; bei `dose-mit-deckel` liegt er **65 mm
  daneben**, und die Operation meldet „Der Schnitt hat nichts abgetragen".
  Sobald „Auf dem Bett anordnen" gelaufen ist, ist das der Normalfall.
- Im Druckeinstellungs-Dialog ist die Spalte „Grund" in jeder Zeile
  abgeschnitten (561 px Dialogbreite auf 2560 px Bildschirm).
- `dose-mit-deckel.p3d` öffnet mit zwei Warnungen, darunter eine wirkungslose
  Boolesche, die keine Tour erklärt.
- STEP steht im Exportdialog und scheitert bei Netzen — mit vorbildlicher
  Meldung, aber erst nach der Formatwahl.
- Erstes Öffnen in einer Sitzung: 7,9–8,3 s; jedes weitere 0,2–0,4 s. Das sind
  die nachgeladenen Bibliotheken, nicht die Auswertung.
- Sechs von 77 Operationen tragen ein Tastenkürzel.

### Was trägt

Erstinbetriebnahme vollständig und vorbelegt, alle vier externen Programme
richtig erkannt · 77 Operationen, alle in Menüs, 72 Dialoge fehlerfrei, keiner
über 427 px · **der Viewport nimmt Klicks an** (`obj_2` und `face_7`, Baum
folgt) — der Fund aus `konzept-bedienung.md` ist erledigt · **beide Messarten
tragen** (Abstand 48,91 mm, Wandstärke 2,0 mm; eine erste Gegenmessung war ein
Klick daneben) · sieben Analysekarten je 1,4–1,5 s bei 3 s Budget ·
Schichtenvorschau 2,67 s · Auto Split 1,77 s · Druckeinstellungen belegen
Maschine, Prozess und Filament von selbst richtig vor (1001 / 7 / 42 Einträge)
· STL, 3MF und OBJ schreiben und lesen zurück · 1986 Übersetzungen, keine
leer, kein Registertext ohne englische Entsprechung · alle 14 Fehlerklassen
mit Handlungsvorschlag · Rückgängig stellt den Stapel wieder her.

### Nachgezogen, gleiche Sitzung

- [x] **Acht Sekunden auf ein leeres Fenster.** Das erste Öffnen einer Sitzung
      dauert 7,9–8,3 s, und in dieser Zeit stand die Ansicht leer: kein
      Objektbaum, kein Körper, und als einzige Auskunft ein 180 px breiter
      Balken unten rechts — an der Stelle, an der beim Warten niemand hinsieht.
      Jetzt liegt `LoadingVeil` (`app/ui/loading.py`) über der Ansicht: das
      Anwendungssymbol wird gedruckt wie auf dem Ladebildschirm, darunter
      Fortschrittslinie, Prozentzahl, laufender Operationstitel und
      *Abbrechen*. Drei Kodierungen für dieselbe Zahl (Regel 18). Sie kommt
      erst nach 200 ms, sie liegt **unter** den schwebenden Karten, und sie
      kommt nur, wenn kein Körper im Bild steht — §2.8 lässt die letzte
      gültige Darstellung stehen. Das Zeichnen des halb gedruckten Zeichens
      teilt sie sich mit `splash.py` (`icons.paint_printed_mark`).
- [x] **Der Themenwechsel aus dem Einstellungsdialog erreichte die Karten
      nicht.** `action_theme` zog `_apply_card_style` nach, `_apply_settings`
      nicht — über den Dialog gewechselt, behielten die schwebenden Zonen die
      Farben des alten Themas.

### Behoben, am selben Tag

Alle Punkte bis auf die Tastenkürzel, jeder mit Test und am laufenden Fenster
nachgemessen. Der Nachtrag in `konzept-kundensicht-2026-08.md` führt die
Zahlen; die wichtigsten:

- **Die Karten wachsen mit.** `MAX_ROWS` ist kein Deckel mehr, sondern eine
  Rückfallzahl: die Überlagerung teilt den Raum nach Bedarf zu (`_share_room`).
  `rows_height` fragt `visualRect` statt `sizeHintForRow`, `natural_height`
  achtet auf Rollbereiche und gesetzte Mindesthöhen. Prüfbericht 316 → 322 px
  ohne Rollbalken, Objektbaum 321 → 873 bei 871 Bedarf, Chat 170 → 334,
  Tour zeigt 139 von 139 statt von 152.
- **Eine Parameteränderung kostet 1,47 s statt 8,3.** Die Ursache lag nicht in
  der Auswertung, sondern in der Slot-Übertragung: sie suchte für jedes der
  vierzigtausend Dreiecke den Abstand zu jeder Quelle, auch zu einer
  Beschriftung aus sechshundert. Der Vorfilter in `geom.attributes` ist exakt
  — dreiunddreißig Aufrufe über vier Beispiele, kein einziges abweichendes
  Dreieck.
- **Dasselbe löste zwei weitere Funde.** Erstes Öffnen 8,0 → 1,55 s. Und die
  rtree-Anfragen je Auswertung fielen von 113168 auf 1180: sechzig
  Auswertungen hintereinander ohne einen Fehlgriff, wo etwa drei zu erwarten
  gewesen wären.
- **Das Kontextmenü am Merkmal** las den Durchmesser als Art des Merkmals.
  Jetzt stehen dort die Operationen aus `applies_to`; am ganzen Körper wird
  über zwölf Einträgen nach Kategorie gruppiert (`MENU_GROUPS` ist dafür nach
  `labels.py` gewandert).
- **„Bohrung setzen"** öffnet auf der obersten Fläche des gewählten Körpers
  statt auf dem Ursprung (`values_for_object`).
- **Kleineres:** die Spalte „Grund" im Druckdialog bricht um statt abzubrechen,
  STEP steht nur im Exportdialog, wenn ein Körper es tragen kann, und die
  Einpressbuchse im Dose-Beispiel sitzt auf dem Boden statt über dem Hohlraum
  — von acht Beispielen warnt nur noch das, dessen Zweck das Warnen ist.

**Eine Regression dabei, gemeldet und behoben:** Die erste Fassung der
Raumzuteilung las die Höhen, die sie gerade selbst gesetzt hatte, und die
linke Spalte lief bei jeder Aktion auf und ab — neunhundertfünf
Geometriewechsel für ein Aufklappen. Gerechnet wird jetzt nur mit dem
verfügbaren Raum und dem Bedarf, und eine Animation, die schon dorthin
unterwegs ist, wird nicht neu gestartet. Gemessen: eine Bewegung je Aktion.

**Offen:** die Tastenkürzel. Sechs in der Vorgabe ist eine Entscheidung und
keine Lücke — welche Operationen eine Taste verdienen, ist eine Design-Frage.

---

## Handbuch, Website und Rechtstexte durchgesehen (08.08.2026)

Anlass war eine Frage, keine Fehlermeldung: „Ist die Doku vollständig,
seriös, aktuell?" Geprüft wurden Handbuch, Website, README, Bauplan, die
Konzeptpapiere und die Roadmap — gegen den Code, nicht gegen die Erinnerung.

### Was falsch war und jetzt stimmt

- **Die Startseite trug „Formwerk".** In vier Seiten, jeweils Zeile 15, als
  `Form<span>werk</span>` — deshalb hat der Umbenennungs-Commit sie nicht
  gefunden, und deshalb findet keine Suche nach dem Namen sie. Der Name war
  gefallen, weil eine Wort-/Bildmarke „3D FORMWERK" für „Entwurf von
  3D-Modellen für den 3D-Druck" bestandskräftig wurde.
- **Drei der sieben Analysekarten hießen im Handbuch anders als im
  Programm.** „Dicke der ersten Schicht", „Abstand zum Bauraumrand" und
  „Materialverteilung" gibt es nicht; die drei heißen Netzfehler,
  Feature-Zuordnung und Passungen.
- **Die Toleranzleiter stand unter einem Menüeintrag, den es nicht gibt**
  („Passungsleiter" statt „Toleranz-Testkörper"), mit einem Bereich, den die
  Vorgaben nicht ergeben (0,10–0,40 statt 0,10–0,25 mm).
- **252 Zahlen im deutschen Handbuch schrieben einen Punkt.** Die erzeugte
  Referenz formatierte mit `:g`, neben einer Anwendung, die „2,40 mm" zeigt.
  `format_decimal` entscheidet das jetzt nach der Sprache.
- **Zwanzig Zeichnungen hatten weißen Grund** in einer Seite, die dem
  Systemthema folgt. Die dunkle Fassung gab es die ganze Zeit —
  `make_manual` rief nur `svg(key, "light")`.
- **Der Bauplan verbot den eigenen Namen.** §37.1 führte „kein ‚3D' im
  Namen" als Kriterium, und die Anwendung heißt Solidon3D. Das Kriterium ist
  gefallen, mit Begründung.
- **`.wrap` stand auf 62rem.** Auf 1920 × 1080 blieben 464 px Rand je Seite,
  der Hero-Text nutzte 32 % der Breite, und das Bildschirmfoto lag unter der
  Falz. Jetzt 76rem und ab 68rem zwei Spalten.
- **Der README beschrieb das Handbuch von vorgestern** („achtzehn Seiten:
  sieben geschriebene, elf erzeugte" statt 33 aus 18 und 15).
- **Die Bildschirmfotos zeigten behobene Fehler** — fünf UI-Commits lagen
  zwischen Aufnahme und heute. Dabei fiel auf, dass die Prüfbericht-Karte
  weiterhin nicht wächst, wenn Befunde **nach** der Auswertung dazukommen:
  ein `QListWidget` meldet sein Wachstum nicht, und die Karte hängt in
  keinem Layout, das es weiterreichen könnte (`contentGrew` → `reflow`).

### Neu

- **`EULA.md`, `AGB.md`, `WIDERRUF.md`.** Die Seite nennt seit ihrer
  Entstehung 49 €; es gab weder Endnutzer-Lizenzvertrag noch AGB noch
  Widerrufsbelehrung — die letzten beiden sind bei einem Verkauf an
  Verbraucher Pflicht. `tools/make_legal.py` macht daraus die Website-Seiten
  und die Lizenzseite des Installers, der bis dahin die Urheberrechtsnotiz
  zeigte. Der Entwurfshinweis hängt an den Platzhaltern und verschwindet von
  selbst, sobald sie ersetzt sind; `tests/test_legal.py` lässt keine Seite
  durch, die einen trägt und schweigt.
- **Auszeichnung für beide Startseiten und das Handbuch**: canonical,
  hreflang, Open Graph, JSON-LD. Geteilt wurden sie bis hierhin als nackte
  Links.

### Offen

- [x] **Der Zahlungsdienstleister ist entschieden: Paddle.** Als *Merchant of
      Record* wird er selbst Vertragspartner des Kaufs und trägt die
      Umsatzsteuer — § 4 der AGB war auf genau diesen Fall geschrieben und
      nennt ihn jetzt beim Namen: Paddle.com Market Limited, 30 Old Bailey,
      London EC4M 7AU (Companies House 08172165; die Anschrift hat am
      07.07.2026 gewechselt, die alte in Mora Street steht noch überall im
      Netz). Die Datenschutzerklärung hat dazu einen eigenen Abschnitt
      bekommen: sie schwieg zum Kauf, obwohl dort die einzigen
      personenbezogenen Daten anfallen, die es überhaupt gibt — samt dem
      Angemessenheitsbeschluss für das Vereinigte Königreich.
- **Die Rechtstexte fachlich prüfen lassen.** Sie sind sorgfältige Entwürfe
  und keine Rechtsberatung. Der Entwurfshinweis hing bis hierhin am
  Platzhalter, und mit Paddle wäre er gefallen: ein ungeprüfter Vertrag hätte
  ohne jeden Vorbehalt dagestanden. Er hängt jetzt an
  `make_legal.REVIEW_PENDING` und fällt erst, wenn die Prüfung stattgefunden
  hat — `tests/test_legal.py` hält das fest.

  **Was der Prüfung vorzulegen ist**, gesammelt statt „einmal drübersehen":

  1. **Die Rolle zieht weiter als § 4.** Ist Paddle Merchant of Record, ist
     Paddle der Verkäufer — und §§ 3, 5, 6 und 7 der AGB sind auf einen
     Direktvertrag geschrieben („Der Vertrag kommt zustande, wenn **wir** die
     Bestellung annehmen"). Zu klären, welche Teile für die Softwarenutzung
     bleiben und welche Paddles Bedingungen überlassen werden.
  2. **Paddles Rückgaberegel nennt sieben Tage** für digitale Inhalte, die
     Widerrufsbelehrung vierzehn. Beides kann nebeneinander richtig sein —
     nachgeprüft ist es nicht.
  3. **§ 356 Abs. 5 BGB im Bestellvorgang.** Die Belehrung wirkt nur, wenn
     Zustimmung *und* Kenntnisnahme dort abgefragt und auf dauerhaftem
     Datenträger bestätigt werden. Paddles Checkout kennt den Fall (Art. 16
     lit. m der Verbraucherrechte-Richtlinie); dass er für diesen Shop
     eingeschaltet und deutsch formuliert ist, muss beim Einrichten geprüft
     werden.
  4. **Der Testlauf von vierzehn Tagen** steht neben dem Widerrufsrecht und
     soll es nicht ersetzen — § 6 sagt das ausdrücklich, und genau dieser Satz
     gehört gelesen.

### Dritter Durchgang, gleicher Tag

Nochmal durchgesehen, diesmal gegen den Stand nach der Überarbeitung der
Startseite. Acht Funde, alle behoben:

- **Der Markenname stand mit Lücke da.** `.brand` ist ein Flex-Container mit
  `gap`, und in einem Flex-Container wird jeder Textknoten ein eigenes
  Element — „Solidon" und `<span>3D</span>` waren zwei davon. In der
  Kopfzeile stand deshalb „Solidon 3D", gegen Fenstertitel, Domain und
  `branding.py`. Der Abstand gehört an das Symbol, nicht zwischen die Silben.
- **„14 Tage Widerrufsrecht" widersprach der eigenen Belehrung.** Bei
  digitalen Inhalten erlischt es vorzeitig, wenn der Käufer der sofortigen
  Ausführung zustimmt — die Zusage stand ohne diesen Vorbehalt auf der Seite,
  die den Preis nennt.
- **Der Lizenzvertrag war strenger als das Programm.** §4 sagte, nach der
  Frist brauche man einen Schlüssel zum Weiterarbeiten. Die Grenze in
  `app/core/activation` verläuft anders: was liest, bleibt frei — Solidon
  ist danach ein vollständiger Betrachter der eigenen Projekte.
- **Die englische Seite verlinkte unangekündigt auf deutsche Verträge.**
  Jetzt steht der Hinweis oben auf allen drei Seiten, auf Englisch.
- **Zwei Konzepte sagten „Entwurf", während die ROADMAP sie abhakte** — P15
  und die Live-Durchsicht gegen Fusion.
- **Das Veröffentlichungskonzept nannte `app/core/licence/`**; gebaut wurde
  `app/core/activation/`.
- **Zwei Handbuch-PDFs unter dem alten Markennamen** lagen im
  Releases-Ordner. Entfernt.
- **Ein Repository-Pfad stand im Endnutzervertrag.** Der Käufer sieht
  `app/core/knowledge/parts/` nie; jetzt stehen dort Mutternfalle, Gewinde
  und Filmscharnier.

**Geprüft und in Ordnung:** alle 77 Operationen mit Erklärsatz, jeder
Parameter mit Beschreibung, kein englischer Rest, keine Vorgabe außerhalb
ihres Bereichs · das Register vollständig übersetzt · zehn Kontrastpaare in
beiden Themen über WCAG AA · `prefers-reduced-motion` schaltet alles ab ·
die sechs Zahlen der Startseite testgedeckt · beide PDFs mit richtigem
Deckblatt.

**Weiterhin offen und nicht von hier zu lösen:** die fachliche Prüfung der
Rechtstexte — was ihr vorzulegen ist, steht oben unter „Offen" als vier
benannte Fragen. Die beiden anderen Punkte, die hier standen, sind seit dem
08.08.2026 erledigt: die vier Grenzstellen rufen `require()`, ein
abgelaufener Testlauf sperrt die schreibende Seite (siehe „Die Lizenzgrenze
greift" weiter unten), und der Zahlungsdienstleister steht mit vollständiger
Firmierung in den AGB.

## Die Lizenzgrenze greift (08.08.2026)

V4, V4b und V4c aus dem Veröffentlichungskonzept in einem Zug; der Stand je
Paket steht in `.claude/konzept-veroeffentlichung-1.0.md` §9.

- **V4 — die Grenze im Datenpfad.** `History.apply`, `write_plan`,
  `write_assembly`, `slice_model` und `AgentSession.propose` rufen
  `activation.require()`; was liest, bleibt frei. Fall für Fall in
  `tests/test_licence_boundary.py`. Dazu `integrity.py` (H4): beim ersten
  Zustandsabruf werden die vier Grenzdateien gegen das signierte Manifest
  geprüft — in der Entwicklung prüft es nichts, der Schlüssel dafür entsteht
  je Bau.
- **Der echte öffentliche Schlüssel steht in `key.py`.** Der private Teil
  liegt außerhalb des Repositorys (§8: Passwortmanager und Papier); der
  Rundlauf erzeugen→prüfen ist gegen den eingebauten Schlüssel belegt.
- **V4b — die Oberfläche.** Schreibende Einträge grauen mit Grund im
  Hinweistext aus, der Chat sagt es in einer Zeile mit Freischalten-Knopf,
  Statuszeile unter drei Resttagen, „Lizenziert für …" im Über-Dialog, ein
  Satz zum Testlauf in der Ersteinrichtung.
- **V4c — kompilierte Auslieferung, am Paket belegt.**
  `tools/build_licence_module.py` übersetzt das Prüfmodul mit Cython und
  signiert das Manifest mit einem je Bau frischen Paar; die Spec nimmt die
  Erweiterungen statt des Bytecodes und legt die vier Grenzdateien als
  Quelltext, `build.yml` ruft das Werkzeug vor dem Paketieren
  (`tests/test_licence_build.py` hält Spec, Werkzeug und CI zusammen).
  Ein vollständiger lokaler PyInstaller-Bau hat es bewiesen: kein
  `activation`-Python im Ordner oder PYZ, das Manifest deckt die vier
  Grenzdateien, die Anwendung startet aus dem Paket — und mit einem von
  Hand veränderten `writer.py` startet sie gesperrt (kein Testlaufmarker
  entsteht). Der Compiler steckt übrigens in Visual Studio 18; setuptools
  findet ihn dort nicht von allein — der Weg über `vcvars64.bat` steht im
  Docstring des Werkzeugs.

## Gizmo und Direktmanipulation durchgesehen (08.08.2026)

Anlass war die Frage, ob §18.11 hält, was der Bauplan verspricht. Die
Antwort: die Zerlegung eines Zugs in Operationen war richtig und getestet —
aber das Widget darüber hatte einen Lebenszyklus, den kein Test je angefasst
hat. Die Gizmo-Tests prüften reine Funktionen: Beschriftung, Größe,
Zerlegung. Das Widget selbst, sein Anhängen und Abnehmen, prüfte niemand.

### Was falsch war und jetzt stimmt

- **Der Gizmo ließ sich einschalten, aber nie abschalten.** `set_gizmo` rief
  `Off()` auf einem `AffineWidget3D` — eine Methode, die es dort nicht gibt
  (die API hat `remove()`, `disable()`, `enable()`). Der `AttributeError`
  verschwand in Qts Slot-Behandlung: der Griff blieb stehen, obwohl der
  Schalter aus war, und mit ihm Beschriftung und Flächenscheibe.
- **Nach jedem Zug hing der Griff an einem toten Actor.** Ein Zug erzeugt
  Operationen, die Auswertung baut alle Actors neu — und niemand hängte den
  Griff um. Schlimmer: pyvistas Widget merkt sich die Matrix über Züge
  hinweg, der zweite Zug hätte den ersten also noch einmal angewandt. Jetzt
  wird der Griff nach jedem Loslassen und bei jedem Szenenaufbau frisch
  angehängt — mit leerer Matrix, am aktuellen Actor.
- **Ein Zug unter der Fangschwelle hinterließ ein Bild ohne Szene.** 0,4 mm
  bei 1 mm Raster ergibt zu Recht keine Operation — aber das Widget hatte
  den Körper im Bild längst verschoben, und nichts stellte ihn zurück.
- **Der Griff folgte der Auswahl nicht.** Wer bei aktivem Gizmo ein anderes
  Objekt oder eine Fläche wählte, behielt den Griff am vorigen Ziel; das
  Versprechen „gewählte Fläche bekommt den Griff auf die Fläche" galt nur im
  Moment des Einschaltens. Jetzt wandert er mit — und eine leere Szene nimmt
  den Griff weg, aber nicht die Entscheidung, dass einer gewünscht ist.
- **Das Handbuch kannte weder Bewegen noch Bemalen.** Achtzehn Seiten, und
  die zwei Werkzeuge der Leiste, die das Modell wirklich ändern, kamen in
  keiner vor — „Hinsehen" beschreibt ausdrücklich nur die fünf, die nichts
  ändern. Neue Seite „Bewegen und Bemalen" dazwischen: Griff, Fang,
  Flächenzug, was der Griff absichtlich nicht kann, Pinsel und
  Filamentwechsel. Beide Sprachen, Website und PDFs neu erzeugt.

### Offen, mit Absicht festgehalten

- **Skalieren am Griff gibt es nicht.** §18.11 nennt es; pyvistas Widget
  kann nur Verschieben und Drehen. Der Weg über *Skalieren* und *Auf Maß
  bringen* deckt den Bedarf, das Handbuch sagt das jetzt ehrlich — aber es
  bleibt eine Abweichung vom Bauplan, keine Erfüllung.
- **Zahleneingabe während des Ziehens fehlt.** §18.11 verspricht sie; heute
  gibt es Zahlen nur vorher (Dialog) oder nachher (Verlauf). Wäre der
  nächste Schritt, wenn die Direktmanipulation wieder drankommt.
- **Die Achsbuchstaben wandern beim Ziehen nicht mit.** Sie sitzen nach
  jedem Zug wieder richtig (das Neuanhängen nimmt sie mit), aber während
  des Zugs bleiben sie stehen. Kosmetisch, nicht falsch.

### Nachgezogen, gleiche Sitzung

Die drei offenen Punkte der Gizmo-Durchsicht sind keine mehr, und beim
Abarbeiten kam ein vierter Fund dazu:

- **Skalieren am Griff gibt es jetzt** — ein Würfel auf der Raumdiagonale,
  beschriftet mit S, Interaktion pyvistas Widget nachgebaut
  (`app/ui/scale_widget.py`). Ziehen skaliert live um die Mitte, das
  Loslassen wird eine `scale_object`-Operation, der Faktor ist gegen
  Ausrutscher eingespannt. Achsweise bleibt Sache des Dialogs.
- **Zahleneingabe während des Ziehens gibt es jetzt** — die Zahl zum Zug
  steht über dem Bild, die erste Ziffer übernimmt den Zug, die
  Eingabetaste wendet genau den getippten Wert an (ohne Fang), Esc
  verwirft. Gilt für Pfeile, Ringe, Flächengriff und Würfel.
- **Die Achsbuchstaben reisen mit** — die Beschriftung hängt an einem
  lebenden PolyData, jedes Move-Ereignis versetzt die Punkte um die
  Matrix des Zugs.
- **Der vierte Fund:** pyvistas Widget stellt beim Loslassen *seinen*
  Trackball-Stil wieder her, nicht unseren — nach dem ersten Zug waren
  Auswahl-Klick, Kontextmenü und das Navigationsschema weg, und kein Test
  sah es, weil keiner je einen Zug zu Ende fuhr. Jetzt holt jedes
  Zugende den eigenen Stil zurück.

Handbuchseite „Bewegen und Bemalen" entsprechend fortgeschrieben, beide
Sprachen, Website und PDFs neu erzeugt. §18.11 ist damit vollständig:
Verschieben, Drehen, Skalieren, Raster- und Winkelfang, Zahleneingabe
während des Ziehens — und der Fang auf Fläche und Bohrungsachse über
`align_to_feature`, wie seit P3.

## Der Schatten im Viewport durchgesehen (08.08.2026)

Anlass war ein Satz ohne Fehlermeldung: „irgendwie sieht das komisch aus."
Nachgemessen an der laufenden Anwendung, mit Kamerastellungen statt mit
Eindrücken — und der Eindruck stimmte, aus einem Grund, den kein Test hätte
finden können, weil keiner die Kamera kannte.

### Was falsch war und jetzt stimmt

- **Der Schatten fiel auf den Betrachter zu.** `SHADOW_DIRECTION` war eine
  feste Weltrichtung (0,35 / 0,45), begründet mit „nach hinten rechts, weil
  die Standardansicht von vorn links kommt — so tritt der Schatten hinter dem
  Teil hervor statt davor, wo er die Sicht auf die Vorderkante nähme". Kein
  Teil dieses Satzes stimmte. Gemessen als Anteil an der Blickrichtung:
  Startansicht **−0,81** (also 0,81 nach vorn), eigene Iso +0,11. Jetzt in
  jeder Ansicht +0,95.
- **Der Grund lag tiefer als die Zahl.** Die Anwendung setzt kein eigenes
  Licht; pyvistas Lichtsatz hängt an der Kamera. Ein Körper ist damit in jeder
  Ansicht von vorn beleuchtet — und eine feste Weltrichtung für den Schatten
  passt deshalb zu **keinem** Blickwinkel, nicht nur zu einem falschen. Die
  Richtung folgt jetzt der Kamera (`shadow_direction`), nachgezogen bei jedem
  Ansichtswechsel und am Ende jeder Drehung. Der Beobachter hängt am
  Interactor und nicht am Interaktionsstil: den tauscht jeder Schemawechsel
  aus, und der Orientierungswürfel dreht an ihm vorbei.
- **Die Anwendung startete nicht in ihrer eigenen Ansicht.** `VIEW_DIRECTIONS`
  führt eine Iso-Vorgabe (1, −1, 0,8), gesetzt hat sie niemand — beim Start
  stand die Kamera auf pyvistas (1, 1, 1). Wer „Isometrisch" im Menü wählte,
  sprang also aus einer Ansicht in eine andere, obwohl er die zu sehen
  glaubte, in der er stand. Das war zugleich die Ursache dafür, dass die
  Richtung der Konstante gegen die falsche Ansicht gedacht war.
- **Der Umriss kostete zu viel und zu oft.** Er lief als Triangulierung über
  jeden Punkt des Anzeigenetzes, je Körper und Szenenaufbau, im
  Qt-Hauptthread: 5,2 ms bei dreitausend Dreiecken, 129 bei
  zweiundachtzigtausend, 528 bei dreihundertsiebenundzwanzigtausend. Jetzt
  steht die konvexe Hülle einmal je Körper, und ein Ansichtswechsel projiziert
  nur noch daraus.

| Körper | vorher | Aufbau | Ansichtswechsel | Abweichung |
|---|---|---|---|---|
| Quader, 3 072 Dreiecke | 5,2 ms | 1,8 ms | 0,65 ms | 0,000 mm |
| Kugel, 20 480 | 31,6 ms | 19,3 ms | 10,9 ms | 0,023 mm |
| Kugel, 81 920 | 128,8 ms | 21,7 ms | 11,2 ms | 0,028 mm |
| Kugel, 327 680 | 528,4 ms | 30,1 ms | 12,1 ms | 0,045 mm |

Der erste Anlauf war dabei ein Rückschritt und wurde als solcher gemessen: bei
einer feinen Kugel liegt **jeder** Punkt auf der Hülle, und die Rechnung kostete
59 ms statt 33. Die Hülle hat deshalb einen Kostendeckel
(`SHADOW_HULL_POINTS`) — eine Stichprobe, dazu die äußersten Punkte in
vierzehn Hauptrichtungen, damit ein kantiger Körper seine Ecken behält. Ein
Quader kommt dabei exakt heraus, eine Kugel auf fünf Hundertstel Millimeter.

### Was geprüft war und stimmte

- **Der Schatten löscht das Bettraster nicht aus.** Der erste Eindruck sagte
  das Gegenteil; nachgemessen an der Streuung im Bild (3,50 im Schatten gegen
  4,89 daneben, bei 0,35 Deckkraft) scheint es korrekt gedämpft durch.

### Die beiden offenen Punkte sind zu

- [x] **Steht ein Körper auf einem anderen, löst sich sein Schatten ab.** Er
      wurde immer auf die Platte geworfen, nie auf den Körper darunter. Ein
      Turm auf einer 12 mm hohen Platte hatte einen Schatten, der erst neben
      ihr auftauchte — ein Fleck ohne Verbindung zu dem, was ihn wirft.
      `_shadow_catchers` sucht jetzt zu jedem Körper die Flächen unter ihm, und
      `shadow_points` misst die Höhe ab der auffangenden Fläche statt ab null.
- [x] **Außerhalb der Platte fiel er ins Nichts.** Bei aufgezogener Explosion
      oder einem Körper weit vom Ursprung lag der dunkle Umriss auf blankem
      Hintergrund, ohne Fläche darunter. Der Schnitt gegen den Plattenrand ist
      gebaut (`clip_polygon`, Sutherland-Hodgman) und trägt beide Punkte: jedes
      Schattenstück wird am Umriss seiner Fläche beschnitten. Damit verdeckt
      eine Grundplatte genau den Teil des Plattenschattens, der sonst doppelt
      läge — die beiden Stücke überlappen sich nirgends sichtbar.

Der Umriss ist dabei von `delaunay_2d` auf die ebene konvexe Hülle
umgestellt (`outline_of`): beschneiden lässt sich ein Rand, keine Menge von
Dreiecken — und die Hülle ist zugleich billiger.

## Drei Meldungen aus der Bedienung (08.08.2026)

Robert meldete drei Dinge aus dem laufenden Gebrauch: die linke Spalte sei
beim Einklappen „recht buggy, wird abgeschnitten, zeigt die Hälfte", die
Schichtanalyse hänge an einer texturierten Fläche sehr, und auf dem
Startbildschirm stehe eine Menüleiste, deren meiste Einträge dort nichts tun.
Alle drei sind zu, und jede hatte einen messbaren Grund.

- **Die linke Spalte rechnete sich um zweihundert Pixel zu kurz.**
  `natural_height` zog für jede sichtbare Liste deren *rohe* Qt-Wunschhöhe ab
  — pauschal 192 Pixel, egal wie hoch die Liste wirklich ist. Die Listen der
  Spalte stehen aber per `fit_to_rows` auf festen Höhen weit darunter, und
  das Layout rechnet mit der geklemmten Zahl. Offscreen nachgemessen: die
  Zone bekam 159 Pixel für 371 Pixel Inhalt — Parameter und Verlauf hingen
  unterhalb der Kartenkante, und genau das sah man als „zeigt die Hälfte".
  Solange die Spalte voller ist als das Fenster hoch, deckelt `room` den
  Fehler zu; er wurde sichtbar, sobald Einklappen den Inhalt unter die
  Fensterhöhe brachte. Abgezogen wird jetzt der geklemmte Beitrag. Dazu
  wächst die Rundeck-Maske während der Bewegung mit statt erst am Ziel —
  eine unterwegs ersetzte Animation ließ sie sonst dauerhaft zu klein stehen,
  denn `stop()` sendet kein `finished`.
- **Die Schichtanalyse stand an der Textur aus drei Gründen zugleich.**
  Gemessen an einer 60×40-Platte mit feinem Rändel (46 000 Dreiecke, 2 898
  Ringe je Schicht in der Texturzone):
  1. `_polygon_from` stellte die Verschachtelungsfrage — wer ist Loch von
     wem — als n² einzelne `contains`-Aufrufe: 16,8 Millionen Stück, 63 von
     66 Sekunden des ganzen Laufs. Über `STRtree` sind es dieselben Paare in
     Millisekunden; `slice_body` fiel von 37 auf 4 Sekunden, bei
     unveränderten Kennzahlen. Der Fall steht als Budget in
     `test_performance.py`: viele Konturen sind der Härtefall, nicht viele
     Dreiecke.
  2. Jeder Schieberschritt startete einen **weiteren** Arbeiter, solange der
     erste noch rechnete — dreißig Schritte, dreißig parallele Läufe.
     `_slice_of` führt jetzt eine Warteschlange je Schlüssel: ein Arbeiter je
     Körper, wer das Ergebnis will, stellt sich an, die Schichtansicht nur
     einmal. Ein abgelöster Arbeiter wird beim Eintreffen verworfen, und eine
     neue Auswertung löst den laufenden ab — sein Schlüssel (Objekt und
     Dreieckszahl) überlebt eine Verschiebung, sein Ergebnis nicht.
  3. Der Viewport schnitt bei jedem Schritt die Körper an der neuen Höhe —
     ein echter `cut()` mit Deckel, an der Rändelplatte rund eine Sekunde,
     im Qt-Hauptthread, und zeichnete dazu je Ring einen eigenen
     `add_lines`-Actor, an einer Rändelschicht 2 898 Stück. Beim Fahren
     folgen jetzt nur noch die Konturen (ein Actor je Rolle); der
     Körperschnitt kommt nach 200 ms Ruhe (`LAYER_REBUILD_DELAY_MS`), bis
     dahin bleibt die letzte Darstellung stehen (§2.8).
- **Der Startbildschirm zeigt nur noch Menüs, die dort etwas tun.**
  Bearbeiten, die Operationsgruppen und Ansicht setzen eine offene Szene
  voraus und verschwinden mit ihr (§2.6); Datei und Hilfe bleiben, denn
  Öffnen, Beenden, Handbuch und Freischalten sind genau dort sinnvoll. Die
  Kürzel bleiben gültig — Qt registriert sie am Fenster, nicht an der
  Sichtbarkeit des Menüs.

## Agent und Chat vertiefen (08.08.2026) — Konzept steht

Aus einer vollständigen Gegenüberstellung von Ist (`app/core/agent/`,
`app/ui/chat.py`, Backends) und Soll (Bauplan, diese Liste):
**`konzept-agent-vertiefung.md`** im Projektwurzelverzeichnis. Der Befund in
einem Satz: der Unterbau ist richtig, aber der Agent arbeitet halbblind
(keine Feature-IDs nach einer Op, keine Passungen, keine Analysen, keine
Ansichten nach §23), erreicht die Hebel der Menüs nicht (Druckeinstellungen,
Projektdrucker, Grundform-Skizzen nach §30.1), und der Nutzer sieht von
alldem nur einen endlosen Balken.

Sechs Schritte, jeder einzeln lieferbar, Abnahmekriterien je Schritt im
Konzept:

- [x] **0 — Messgrundlage:** Suite-Basislinie mit vollem Fenster steht
      (17/33, gemessen von der parallelen Durchsicht — siehe oben), die
      `invalid`-Kennzahl zählt jetzt wirklich (Vorschlag führt `tool_calls`
      und `invalid_calls`, der Läufer weist die Quote aus), das stabile
      Präfix aus Systemprompt und Werkzeugschemata liegt per `cache_control`
      im Zwischenspeicher, `max_tokens` ist ein Parameter (8192) und das
      Zugbudget deckelt jede Antwort.
- [x] **1 — Wahrnehmung Text:** Op-Ergebnisse nennen die neuen Merkmale mit
      IDs, `read_digest` liest den Steckbrief der Arbeitskopie mitten im
      Zug, der Steckbrief führt Passungen (mit Verletzt-Zustand),
      Druckeinstellungen, Quellen und den Verlauf mit den gesetzten Werten,
      `read_standard` schlägt die Normteiltabelle nach, und ein gedeckelter
      Chatverlauf sagt, wie viele ältere Beiträge fehlen. Beide neuen
      Werkzeuge auch über die Fernsteuerung.

      **Zwei Kernfehler dabei freigelegt, beide zu.** Ein gebohrtes Loch
      wurde nie ein Merkmal: sortiert sich die neue Bohrung in der Erkennung
      vor die bestehenden, rutschen deren Nummern, und in `apply_mapping`
      überschrieb das unzugeordnete neue Merkmal einen Überlebenden — eines
      von beiden verschwand wortlos aus der Szene. Unzugeordnete Merkmale
      bekommen jetzt eine frische ID, verwaiste Namen bleiben gesperrt. Und
      der zweite lag darunter, kaschiert von der stillen Wiederverwendung:
      nach einer 25°-Drehung liest die Erkennung Zylinderachsen mal als
      `+v`, mal als `-v`, und der vorzeichenempfindliche Vergleich in `cost`
      verwaiste die Hälfte der Löcher. Eine Bohrungsachse ist eine Linie,
      keine Richtung — verglichen wird jetzt das Minimum beider Vorzeichen;
      Flächennormalen behalten ihres, innen ist nicht außen
      (`tests/test_matching.py` hält beide Fälle fest).
- [x] **2 — Sichtbarkeit:** Die Sitzung meldet je Schritt, was läuft
      (Rückruf wie `ask`, kein Qt im Kern), die Statuszeile zeigt
      „Schritt 3/8 — Bohrung setzen" statt nur „Der Agent denkt nach.";
      die Entscheidungszeile nennt Schritte, Token und die Rückfragen samt
      Antworten (aufklappbar), eine erreichte Grenze steht ausgeschrieben
      da. §2.6 ist eingelöst: jede Werkzeugbeschreibung trägt ihren
      Menüort (die Zuordnung Kategorie → Menü lebt dafür im Register,
      die Oberfläche leitet weiter), Prompt-Version 3 verlangt, ihn bei
      Wie-Fragen zu nennen. Die Suite-Messung der Promptänderung steht
      gesammelt mit den neuen Fällen aus Schritt 3 an.
- [x] **3 — Handlungsraum:** `read_analysis` liest Druckbarkeit (Überhang,
      Inseln, Brücken, Stützvolumen), Zeit- und Materialschätzung,
      Einstellungsrat und Orientierungssuche — Herkunft je Antwort
      ausgewiesen (Regel 14), harter Dreiecksdeckel statt Zeitgewalt, die
      Orientierungssuche mit festem Startwert und kleiner Kandidatenzahl.
      `set_print_target` wechselt Drucker/Material als `DocumentChange` in
      der einen Transaktion — Undo stellt beide wieder her. **Eine
      Konzeptkorrektur dabei:** `set_print_setting` wird nicht gebaut —
      Einstellungen reisen nicht in Transaktionen (§15.5), und §28.2 sagt
      „Übernommen wird auf Klick"; der Agent liest die `advise`-Vorschläge
      und nennt sie samt Grund (Begründung in Konzept 5.1 und §26.2). Die
      Suite wächst auf **39 Fälle** (nachsehen statt raten, Druckziel,
      Menüort — gemessen über `proposal.readings`), §35 und die
      Testarten-Tabellen sind fortgeschrieben.
- [x] **4 — Augen und Autopilot:** Die gerenderten Ansichten aus §23
      erreichen den Agenten — zwei beschriftete PNG (schräg oben, von
      oben), offscreen gerendert von der Oberfläche (`app/ui/snapshots.py`;
      der Kern rastert nicht, seine Projektion ist SVG — Konzept 3.5
      entsprechend korrigiert). Nur ein Backend mit `supports_images`
      bekommt sie; Ollama bleibt fest ohne, bis ein Vision-Modell gemessen
      ist. Die automatische Übernahme (§26.5) läuft unter vier Bedingungen
      (`agent_apply.auto_acceptable`: nur umkehrbare Ops, kein
      `create_from_scad`, keine Warnungen, keine Rückfrage/kein Abbruch),
      die Leiste wird zur Übernommen-Leiste mit Rückgängig-Knopf, und die
      Einstellung `auto_accept_reversible` (Vorgabe: an) schaltet sie ab.
- [x] **5 — Grundform-Skizzen:** aufgelöst statt gebaut — der Weg
      existierte seit P13. Die Ist-Aufnahme sah die `sketch`-Sperre und
      übersah die Grundform-Parameter daneben; die vier Skizzenfälle waren
      nie strukturell ungewinnbar. Was fehlte, war der Beweis, und der
      steht jetzt als Test: die geratene Punktliste wird abgelehnt und
      zählt als ungültig, dieselbe Op läuft über `shape` durch, und jede
      erwartete Op bietet die Formen an (Konzept 5.3 trägt die Korrektur
      samt Lehre: eine Aussage ohne §-Beleg ist eine Vermutung, auch die
      eigene).

Begleitend: die doppelt implementierten Zusatzwerkzeuge aus
`main_window.run_remote` auf eine gemeinsame Werkzeuglogik zusammenziehen,
bevor Schritt 3 neue Werkzeuge anlegt. Bewusst nicht im Handlungsraum:
Export/Slicer-Start und Redo — Begründung in Konzept-Abschnitt 5.4.

**Die Nachher-Messung (08.08.2026, 39 Anfragen, `qwen3:14b`, volles
Fenster)** — gegen die Basislinie vom Mittag:

| Maß | vorher (33 Fälle) | nachher (39 Fälle) |
|---|---|---|
| gut beantwortet | 17/33 (52 %) | **28/39 (72 %)** — auf den 33 alten Fällen 25/33 (76 %) |
| bei Mehrdeutigkeit gefragt (§40) | **1/3** | **3/3** — die Kehrseite des Kontextfenster-Fundes ist geheilt |
| schemagültig im ersten Versuch | nie gemessen | **156/160 = 98 %** (Ziel 95 %, erstmals gemessen, erfüllt) |
| Baustein statt eigener Geometrie | 6/13 | 7/13 |
| Hauptmaße als Parameter | 2/3 | 2/3 |
| Zeitüberschreitungen | 2 | 1 |

Prompt-Version 3, die vollständige Werkzeugliste (86 Schemata samt
Menüort) und der größere Steckbrief passen weiter ins 32768er-Fenster —
die Quote wäre sonst eingebrochen statt gestiegen. Zwei der vier
Skizzenfälle (`hex_base`, `handrail_bend`) sind jetzt gewonnen,
`how_long` und `core_hole` wurden wirklich **nachgesehen** (gemessen über
`proposal.readings`), und `switch_material` setzt das Druckziel um.

Was `qwen3:14b` liegen lässt, hat ein Muster: die reinen
Auskunftsfälle verführen es zum Handeln (`where_menu` bohrte viermal,
statt den Menüort zu nennen; `printable` ordnete an, statt zu
analysieren). Das ist Stoff für die Regelsammlung oder den Prompt —
eine Regeländerung mit Messung vorher/nachher, nicht für heute
nebenbei. Gegen Anthropic ist die Suite noch nicht gefahren (kein
Schlüssel hinterlegt); der Lauf steht aus, sobald einer da ist.

## Die Agent-Vertiefung durchgesehen und behoben (09.08.2026)

Zwei Reviewer über die zwölf Commits, gegen die 22 Regeln und den Bauplan —
über vierzig Funde, alle behoben oder begründet vertagt. Die vier schweren:

- **Der Rückgängig-Knopf der Übernommen-Leiste nahm die falsche Transaktion
  zurück.** `History.undo` kennt nur „die oberste"; lag inzwischen etwas
  anderes obenauf, zerstörte der Knopf fremde Arbeit und ließ die
  versprochene stehen — und die Leiste überlebte sogar den Projektwechsel.
  Sie hängt jetzt am Dokument (`_refresh_applied_bar`), der Knopf prüft
  selbst und sagt sonst an, statt zu löschen.
- **VTK rendert nie wieder im Arbeiter-Thread.** Die Ansichten entstehen in
  `propose_async` im Hauptthread, der Arbeiter liest nur Bytes — die
  Absturzfamilie aus dem Projektgedächtnis bekommt keinen dritten Fall.
- **Ein Zug aus Druckziel und Rücknahme war unannehmbar.** Die
  Misch-Schranke kannte `print_target` nicht; jetzt tragen alle drei
  Stellen dieselbe Bedingung (`Proposal.creates_something`).
- **Der genannte Menüort stimmte für 72 von 77 Operationen nicht** — es
  fehlten die Untermenü-Ebenen. `menu_path` im Register baut den vollen
  Weg, und ein Test hält ihn Ebene für Ebene an der wirklich gebauten
  Leiste fest.

Dazu die Auskunftsfunde (Herkunftszeile je Analyseart statt einer für alle,
die Kurzsuche rechnet auf derselben Skala wie die Op, Profil zieht beim
Druckzielwechsel mit, unbekannte Objekt-IDs werden benannt und gezählt),
die Fernsteuerung trägt jetzt bei allen schreibenden Zusatzwerkzeugen den
Herkunftsvermerk und behauptet keinen Erfolg mehr, den es nicht gab, die
Orientierungssuche ist dort abgelehnt, bis sie einen Arbeiter hat (5,3 s im
Hauptthread, gemessen), reine Auskunftszüge bekommen keine
Übernehmen/Verwerfen-Leiste über „Keine Änderung" mehr, und drei
Zusicherungen der Tests waren offscreen Tautologien (`isVisible` →
`isVisibleTo`). Ein gemeinsamer Topf in `new_feature_lines` verschluckte
neue Merkmale auf einem zweiten Körper — je Objekt verglichen, mit Test.

Vertagt mit Begründung: die Orientierungssuche der Fernsteuerung in einen
Arbeiter legen; die englischen Bestands-Docstrings in fünf berührten
Dateien (nicht aus diesem Diff — CLAUDE.md verspricht mehr, als der
Bestand hält, eine der beiden Seiten gehört nachgezogen).

## Der Erzeugen-Einstieg, aufgeräumt (09.08.2026)

Roberts Beobachtung aus der Bedienung: das Zeichnen liegt zu tief, und im
Menü stehen zu viele ähnliche Einträge. Beides behoben:

- **„Zeichnen" steht jetzt oben neben „Modell einfügen".** Die
  Hauptwege-Tabelle nannte die Werkzeugzeile seit je als Ort für Weg 2 —
  belegt war er nie. Der Knopf startet den Skizzenmodus ohne festgelegte
  Operation; bei „Fertig" fragt ein Dialog, was aus der Skizze wird (die
  fünf Arten aus dem Register, mit der Zeichnung vor Augen statt vorab aus
  fünf Menüeinträgen). „Zurück zum Zeichnen" vernichtet nichts — es öffnet
  den Modus mit derselben Zeichnung wieder. Die fünf Menüeinträge bleiben
  als Direktwege.
- **Die Mesh/B-Rep-Zwillinge sind zusammengelegt.** „Quader anlegen" und
  „Exakten Quader anlegen" waren zwei Einträge für einen Quader (Zylinder
  ebenso). Jetzt: ein Eintrag, „Exakt (B-Rep)" als Umschalter hinten im
  Dialog, die Parameter gefiltert auf das Schema des gewählten Kerns, die
  Live-Vorschau wechselt mit. `MENU_TWINS` im Register hält die Zuordnung —
  auch `menu_path` und damit der Menüort, den der Agent nennt, sagen den
  Umschalter dazu. Beide Ops bleiben im Register, in der Palette und im
  Verlauf. Die Zusicherung „genau ein Menüeintrag je Operation" heißt jetzt
  „höchstens einer, und jede bleibt erreichbar" (Grenzen-Tabelle in
  `.claude/rules/oberflaeche.md` nachgezogen).

## Nachgesehen, was davon stimmt (09.08.2026)

Die Oberfläche von Hand durchgefahren — Werkzeugzeile, freies Zeichnen samt
Rückweg, beide Zwillingsdialoge, Weg 1 von der Datei bis zur Schichtanalyse —
und dabei drei Stellen gefunden, an denen der Bau seinem eigenen Text
hinterherhinkte:

- **„Gefiltert auf das Schema des gewählten Kerns" galt für die Werte, nicht
  für die Felder.** Bezugspunkt (Quader) und Segmentzahl (Zylinder) standen
  weiter da, wenn „Exakt" angekreuzt war — in derselben aufgeklappten Gruppe
  wie der Umschalter, also genau dort, wo jeder vorbeikommt, der ihn sucht.
  Auf „Ecke" gestellt kam ein mittiger Quader, ohne einen Ton dazu.
  `OperationDialog.switch_variant` blendet die Zeile jetzt aus und tauscht die
  Beschreibung mit (die des Netz-Quaders nennt eine Wahl, die es exakt nicht
  gibt).
- **Die Skizzenleiste sagte „die Operation öffnet auf der Skizze"**, auch beim
  freien Zeichnen, wo keine gewählt ist. Beide Texte — Leiste und Statuszeile
  — unterscheiden die zwei Wege jetzt.

Was die Durchsicht **bestätigt** hat: die vier Funde vom 05.08. sind zu.
`Solid.bounds` misst 40 × 30 × 10 und Ø 6 wie Ø 120 auf neun Stellen exakt
(`AddOptimal_s`), die Slicer-Übergabe schickt `--arrange 0`, `drill` verankert
am Mund der Bohrung, und gepickt wird mit `vtkCellPicker`. Die Suite läuft
grün (3393), Lint und Typprüfung ebenso; der Abriss im Lauf am Stück ist
weiter der bekannte native, kein Testfehler.

## Alle Operationen und die fremden Programme aus Kundensicht (09.08.2026)

Jede der 77 registrierten Operationen einmal so gefahren, wie ein Kunde sie
startet: Menüeintrag, Dialog mit seiner Vorbelegung, bestätigen — 92 Läufe
über den echten Stapel, die kritischen davon noch einmal durch die laufende
Oberfläche. Dazu die vier fremden Programme mit den Installationen dieser
Maschine.

**73 Läufe liefen vollständig durch, 19 hielten an** — fünfzehn davon zu Recht
und mit einem Satz, der weiterhilft („Der gewählte Körper ist ein Netz. Exakte
Körper kommen aus einer STEP-Datei …"). Was übrig bleibt:

- [x] **Neu vernetzen zerstört das Netz und meldet, die Form sei unverändert.**
      Aus 12 Dreiecken werden 36 864, und der Quader ist danach nicht mehr
      geschlossen und zerfällt in drei Komponenten: `remesh` baut das Ergebnis
      von `subdivide_to_size` mit `process=False` zusammen, die Punkte werden
      also nie verschweißt. Der einzige Befund lautet „Das Netz wurde feiner
      unterteilt; die Form ist unverändert" — geprüft hat das niemand.
      Die Folge ist gemessen: die nächste Differenz fällt auf die Voxelstufe,
      und aus 40 × 30 × 10 werden 40,18 × 30,39 × 10,20. Wer danach eine
      Passung baut, baut sie um bis zu vier Zehntel daneben.
- [x] **`split_plane` legt ein leeres Objekt an, wenn die Ebene nicht
      schneidet.** Der Dialog belegt `position = 0.0` vor, der Quader steht auf
      z = 0 — bestätigen ergibt „Quader A" mit 0 mm³ und null Dreiecken im
      Objektbaum, ohne einen Ton. Der Zwilling `split_pinned` hält bei
      derselben Lage mit „Diese Ebene teilt das Objekt nicht" an. Zwei
      Operationen, eine Lage, gegensätzliche Antwort.
- [x] **`create_from_scad` umgeht die Aufbereitung der Eingangsstufe.** Was
      OpenSCAD liefert, ist ein STL mit doppelten Punkten; über `load` wird es
      verschweißt und gemeldet („Doppelte Punkte wurden verschweißt"), über
      diesen Weg nicht. Ein Ø-12-Zylinder kommt als **252 lose Dreiecke** in
      die Szene, nicht geschlossen. Aufgefangen wird das erst von der
      Rückfallkette der nächsten Booleschen („gelang erst nach dem
      Verschweißen"); wer stattdessen exportiert, exportiert den Scherbenhaufen.
- [x] **`plug_hole` auf einem Körper ohne Bohrung tut nichts und sagt nichts.**
      Dieselbe Lage bei den Bausteinen meldet „Die Vereinigung hat nichts
      hinzugefügt — Position prüfen". Auch `repair` an einem gesunden Netz
      bleibt stumm.
- [x] **Sieben Operationen für exakte Körper sind bei einem Netz anklickbar.**
      Verrunden, Fase, Formschräge, Exakt aushöhlen, Fläche versetzen, In ein
      Netz umwandeln, Tasche schneiden. `_refresh_actions` fragt nur, wie viele
      Objekte gewählt sind, nie welcher Bauart sie sind — dabei steht
      `SceneObject.kind` daneben. Der Kunde füllt den Dialog aus und erfährt
      danach, dass die Operation hier nie ging.
- [x] **Leerer OpenSCAD-Quelltext meldet einen Übersetzungsfehler.** „OpenSCAD
      konnte den Quelltext nicht übersetzen" für ein leeres Feld; die
      Beschriftungs-Operationen sagen an derselben Stelle „Ohne Text gibt es
      nichts anzulegen".

### Die fremden Programme, alle vier real aufgerufen

| Programm | Stand |
|---|---|
| OpenSCAD 2021.01 | gefunden, Quelltextprüfung greift, Rendern in 0,2 s — aber siehe oben |
| PrusaSlicer 2.9.6 | Ende zu Ende: 21,0 min · 4,17 g · 1367 mm, mit 3MF wie mit STL |
| ElegooSlicer 1.5.3.4 | Ende zu Ende: 21,6 min · 4,88 g · 100 Schichten — **nur mit Pfaden** |
| CuraEngine 5.13.0 | **scheitert immer** über Solidons eigenen Weg |
| Ollama qwen3:14b | Chat Ende zu Ende in 71 s, Vorschlag als eine Transaktion |
| ComfyUI | nicht gestartet; `reachable()` meldet es sauber, nichts hängt |

- [x] **CuraEngine bekommt ein 3MF und kann keines lesen.** Der
      Druckeinstellungs-Dialog schreibt über `write_assembly` immer eine
      3MF-Baugruppe, unabhängig von `setup.flavour`, und `slice_model` reicht
      sie unverändert weiter. Derselbe Würfel als STL läuft durch (20,9 min,
      1998 mm). Der Roadmap-Punkt „Für Cura schreibt die Übergabe STL" aus der
      Cura-Kette ist damit nicht mehr erfüllt — die Umstellung auf die
      Baugruppe hat ihn überfahren. Die Tests decken es nicht ab: sie prüfen
      `slice_model` nur gegen Attrappen.
- [x] Der offene Punkt „`machine_profile` muss ein Pfad sein" ist bestätigt und
      erklärt den ganzen Rest: mit Namen endet der Lauf in
      `Slic3r::CLI::run found error`, mit Pfaden aus der Profilsuche läuft er.
      Die Oberfläche gibt Pfade, deshalb trifft es nur, wer die Verträge direkt
      benutzt.

### Und was das Modell beim Chatten anrichtet

Die Anfrage „Quader 30 × 20 × 10 und ein 5-mm-Loch mittig durch" ergab drei
Schritte, zwei Operationen, eine Transaktion — und ein Loch **an der Ecke**.
`create_box` legt den Quader um den Ursprung (−15 … 15), das Modell rechnete
mit einer Ecke im Ursprung und schickte `x = 15, y = 10`. Abgetragen wurden
53 statt 212 mm³, also ein Viertel. Danach schrieb der Agent: „Das Loch ist
durchgehend und mittig positioniert."

- [x] **Keine Prüfung schlägt an, wenn ein Schnittwerkzeug den Körper nur
      streift.** `checks.check` meldete zwei verwaiste Merkmale und sonst
      nichts. Bei der Vereinigung gibt es den Fall längst („hat nichts
      hinzugefügt"); bei der Differenz fehlt er.
- [x] **Der Steckbrief nennt keine Grenzen des Hüllquaders**, nur Flächenmitten
      — aus `face_5 bei (−15, 0, 5)` muss das Modell selbst schließen, wo die
      Mitte liegt. Ein Satz „liegt von … bis …" je Objekt kostet nichts.
      Danach die Agenten-Suite, vorher und nachher, wie es die Regel verlangt.

## Das Zeichnen im Handbuch und auf der Website (09.08.2026)

Auf die Frage, ob das Zeichnen sauber und detailliert beschrieben ist, war die
Antwort nein. Zwanzig geschriebene Seiten, und der Skizzeneditor kam in keiner
vor: ein Halbsatz auf Seite eins und die sechs Skizzen-Ops in der erzeugten
Referenz, die sagen, was aus einer fertigen Zeichnung wird — nicht, wie eine
entsteht. Auf der Website zwei Zeilen, ein Listenpunkt unter „Was sonst noch
drinsteckt". Behoben, und dabei fünf Stellen gefunden, an denen die Unterlagen
dem Programm widersprachen:

- **Das englische Handbuch behauptete auf Seite eins das Gegenteil.** „no CAD
  replacement — there are no sketches and no constraints" stand weiter mitten
  im Satz über den Slicer; auf Deutsch war er längst berichtigt, im Katalog
  nicht. Ein Kapitel später beschreibt dasselbe Handbuch die Bedingungen.
- **„Das Fenster" kannte nur eine Werkzeugleiste.** Der neue Absatz machte
  daraus eine Zeile mit „links hinsehen, rechts ändern" — das neu aufgenommene
  Bild zeigte zwei Leisten: oben Neu, Öffnen, Speichern, *Zeichnen*, unter dem
  Modell Schnitt, Messen, Bewegen, Analyse, Schichten, Explosion, Bemalen. Dem
  Fensterschema fehlte die zweite ganz, deshalb stand sie in keinem Text.
- **„Weg 2 — selbst konstruieren" nannte Grundkörper und Bausteine**, und die
  Abbildung der drei Wege ebenso. Die Skizzen sind das Kernargument des
  Launches.
- **Die Statuszeile des Editors hatte keinen Singular.** „1 Freiheitsgrade
  frei" — aufgefallen, weil es sonst mit dem ersten Handbuchbild gedruckt
  worden wäre.
- **Drei Absätze druckten ihre eigenen Sternchen.** `**fett mit *kursiv*
  darin**` setzt `markup._STRONG` nicht um (das Muster lässt kein Sternchen im
  Inneren zu), und der Umsetzer schweigt dazu. `test_no_page_prints_its_own_markup`
  prüft es jetzt in **beiden** Sprachen — die englische Fassung ist ein
  Katalogeintrag, den kein Umsetzer korrigiert.

Neu: Kapitel „Zeichnen" vor den drei Wegen, mit drei Abbildungen — dem
aufgenommenen Skizzenmodus, dem Schema aus Werkzeugen, Bedingungsliste und
Statuszeile, und demselben Umriss als drei Körpern. Das Bildschirmfoto kam
zweimal untauglich aus dem Werkzeug, bevor es taugte: ein Lochkreis legte acht
Maßzahlen übereinander und füllte die Liste mit neun mal „Abstand 2,00", und
die 40-mm-Grundform lag als Briefmarke in der Bildmitte.

Auf der Website ist daraus der zweite Block im Funktionen-Abschnitt geworden,
gleich hinter dem Agenten, mit demselben Bildschirmfoto. Der Listenpunkt ist
weg.

### Und dann alles behoben (09.08.2026)

Neun Punkte, sechs Commits, 3417 grüne Tests. Was dabei über die Meldung
hinausging:

- **Neu vernetzen teilt jetzt gleichmäßig.** `subdivide_to_size` war die
  falsche Wahl, nicht ein Fehler in seiner Anwendung: es teilt jede Fläche
  nach *ihren* Kanten und lässt an der Naht zwischen zwei verschieden oft
  geteilten Flächen einen Punkt auf einer Kante liegen, die ihn nicht kennt.
  Verschweißen behebt die Komponenten, nicht die 192 offenen Kanten.
  `trimesh.remesh.subdivide` in Schritten bis zur Zielkantenlänge lässt keine
  solche Naht entstehen; der Preis sind Dreiecke, wo es schon fein genug war.
  Decke bei acht Millionen, sonst frisst eine kleine Kantenlänge den Speicher.
- **Zwei Slicer-Funde statt einem.** Dass Cura ein STL braucht, war der
  gesuchte; beim Nachmessen fiel der zweite auf, und er war der stillere:
  die Bettverschiebung galt für alle drei Familien, obwohl nur die
  Orca-Familie von der Ecke misst. Cura druckte 128 mm daneben, ohne zu
  klagen. **Wer eine Übergabe prüft, misst die Position im G-Code** — ein
  Lauf mit Rückgabe 0 sagt nichts darüber, wo das Teil landet.
- **Der Agentenfund brauchte drei Änderungen, nicht eine.** Ein Befund für das
  streifende Werkzeug, seine Durchreichung in `checks.PASSED_THROUGH` — und
  die Lage des Körpers im Steckbrief. Die ersten beiden allein hätten dem
  Modell gesagt, dass etwas falsch ist; erst die dritte sagt ihm, was.
  Nachgefahren mit qwen3:14b: dieselbe Anfrage ergibt jetzt x=0, y=0 und
  5804,21 mm³ gegen die Handrechnung 5803,65.
- **Was die Oberfläche ausgraut, sagt jetzt warum.** Ausgrauen allein ist die
  halbe Antwort — der Nutzer sieht, dass es nicht geht, und sucht den Grund
  bei sich.

Offen bleibt eine Messung: die Agenten-Suite vorher und nachher gegen die
Steckbrief-Erweiterung. Sie kostet Geld und rund anderthalb Stunden je Lauf und
läuft auf Ansage, nicht nebenbei.

Der zehnte Fund kam erst beim Nachmessen: **die Rastnase wurde nie ein Körper
mit ihrem Träger.** Sie steht mit 6 mal 1 mm auf der Fläche auf, und zwei
Volumen, die sich nur in einer Fläche berühren, brechen jede boolesche
Operation — wasserdicht, aber zwei Komponenten, nach der nächsten Bohrung drei.
Die breiteren Bausteine fielen nie auf, weil manifold sie verschmolz. Additive
Bausteine sinken jetzt in der Platzierung um den Überlappungswert ein.

**Bilanz des Reihendurchlaufs, vorher und nachher** (92 Läufe über 77
Operationen, jeweils mit der Vorbelegung des Dialogs):

| | vorher | nachher |
|---|---|---|
| Ergebnis nicht geschlossen oder Volumen ≤ 0 | 2 | **0** |
| Ergebnis in mehreren Komponenten | 2 | **0** |
| ohne Wirkung und ohne ein Wort dazu | 7 | **0** |
| angehalten | 19 | 20 (An Ebene teilen hält jetzt an, statt ein leeres Objekt anzulegen) |

Suite 3423 grün, Lint und Typprüfung ebenso.
