# ROADMAP — Arbeitsliste

Abzuarbeiten von oben nach unten. Jeder Punkt ist so geschnitten, dass danach
die Suite grün sein kann. Details stehen im Bauplan (§-Verweise), Regeln in
`AGENTS.md`.

Legende: `[ ]` offen · `[~]` in Arbeit · `[x]` fertig und Suite grün

---

## Was offen ist

Die offenen Punkte stehen weit auseinander: ein paar in den Phasen, die meisten
in den Durchsichten der letzten Tage. Dazwischen liegen tausende Zeilen ohne
einen einzigen — die sind Geschichte, kein Rückstand. (Keine Zahl in diesem
Absatz: Sie stünde neben einer Tabelle, die sie schon nennt, und wäre die
Erste, die driftet.)

Diese Übersicht ist die Abkürzung, nicht die Quelle. Der Punkt selbst steht mit
seiner Begründung an seinem Ort, und dort wird er auch geändert; hier steht nur,
dass es ihn gibt und worauf er wartet. **Ein Register, dem man nicht glaubt, ist
schlechter als keines** — deshalb hält `tests/test_roadmap.py` beides zusammen:
Wer einen Punkt abhakt oder einen neuen aufmacht, ohne hier nachzuziehen,
bekommt einen roten Lauf.

| Punkt | steht unter | wartet auf |
|---|---|---|
| Leistungsziele §31 der Schichtanalyse | P3 — Wahrnehmung und Schichtanalyse | die Entscheidung, ob `_chain` mit ausgeliefert wird; der kompilierte Kern steht und bringt 1,34× — was jetzt oben liegt, ist `_plane_segments` |
| CI-Bauläufe, Signierung, AppImage/Flatpak | P8 — Erste Veröffentlichung | die beiden Linux-Formate; die Signierung braucht ein Zertifikat |
| Doku, Website, Lizenzhinweise | P8 — Erste Veröffentlichung | Postfach `support@`, DMARC und den AVV im CCP |
| Sichtbarkeit | Gegen das Wettbewerbsfeld gehalten (11.08.2026) | keine Entwicklungsaufgabe — bleibt bewusst stehen |
| macOS ausliefern | Gegen das Wettbewerbsfeld gehalten (11.08.2026) | Apple-Zertifikat und Notarisierung; der Paketierschritt steht |
| G-Code an die Maschine senden (B3) | Gegen das Wettbewerbsfeld gehalten (11.08.2026) | eine Bauplanentscheidung, nicht auf Code |
| DMARC fehlt | Die Demo bis 30.10.2026 (12.08.2026) | einen TXT-Eintrag im CCP |
| CI grün sehen und die Artefakte holen | Die Demo bis 30.10.2026 (12.08.2026) | den Segfault in `test_chat_ui.py` auf den Linux-Runnern |
| Auf einem fremden Rechner installieren | Die Demo bis 30.10.2026 (12.08.2026) | eine gebaute Datei — hängt an der CI |
| Download-Kasten mit Datei und Prüfsumme | Die Demo bis 30.10.2026 (12.08.2026) | dieselbe Datei |
| Hochladen | Die Demo bis 30.10.2026 (12.08.2026) | den Stand nach dem Bau; live steht noch eine ältere `version.json` |
| Den helikalen Gang überall schließen | Die Durchsicht vom 13.08.2026 — Auswahl und Zeichnen | `SetTransitionMode` oder das Gewinde als Rotationskörper |
| Der eine übersprungene Test | Die Durchsicht vom 13.08.2026 — Auswahl und Zeichnen | VTKs Zustand über mehrere Fenster hinweg |
| P16.10 — die Regel in der Sammlung | P16 — Organische Modellierung | eine Entscheidung; sie kostet zwei Agenten-Suite-Läufe und Geld |
| Der Absturz in einer einzelnen Datei | Ein Umgebungsartefakt, das keines war (14.08.2026) | viele Läufe je Messpunkt — bei einer Rate um zwanzig Prozent sagt ein einzelner nichts |
| Ein dritter Absturz in `test_operation_ui.py` | Ein Umgebungsartefakt, das keines war (14.08.2026) | einen Lauf unter Valgrind — das Bild sagt „doppelt freigegeben", wer, sagt nur ein Werkzeug |
| Die Suite gegen Sonnet 5 | Die Konzepte nachrecherchiert (19.08.2026) | zwei Läufe über den Schlüssel des Nutzers; bis dahin ist die Quote eine Annahme |
| D4 — ViewCube und Ansichtsleiste, wieder offen | Die Konzepte nachrecherchiert (19.08.2026) | eine Entscheidung: Würfel zurück, Leiste bauen oder beides lassen |
| Die Rückfallebene ohne Grafikkarte (B1 im Erzeugen-Konzept) | Die Konzepte nachrecherchiert (19.08.2026) | eine Entscheidung über den Dienst — sie kostet Geld, nicht Tage |

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
      Merkmale als Kinder im Objektbaum, Kontextmenü aus dem Register.
      Anklicken und Auswählen stehen.

      **Die Begründung hier war überholt** (nachgesehen am 14.08.2026): Die
      Mauszeiger-Ereignisse fehlen nicht mehr. `viewport._note_pointer`,
      `_look_under_pointer` und `_forget_pointer` stehen, mit einem
      entprellenden Zeitgeber und Suche über den Tiefenpuffer statt über einen
      Aktor-Pick. Was das Überfahren **zeigt**, ist allerdings der Mauszeiger
      („feature" statt „select") und keine Hervorhebung am Merkmal selbst.
      Das ist keine halbe Umsetzung, sondern eine andere: Ein Umfärben je
      Zeigerbewegung ginge über den Aktor, und genau den meidet die Stelle aus
      Kostengründen. Wer die Hervorhebung will, bekommt sie über
      `highlighted_faces` — dieselbe Bahn, die die Auswahl seit dem 13.08.
      benutzt — und bezahlt sie mit einem Aktor-Update je Ruhepause.
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

      **Nachgemessen am 14.08.2026**, und eine der Zahlen oben ist überholt:
      die Wandstärkenkarte steht nicht mehr bei 3,08 s, sondern bei **4,30 s**
      — auch allein gefahren, ohne Leistungsdatei davor. Die Orientierungssuche
      liegt mit 14,8 s im Ziel, die Schichtanalyse bei 1,07 s.

      **Dabei fiel eine verwaiste Messmarke auf, und sie ist verworfen.**
      `subdivide_surface` meldete das 3,54-fache seines Bestwerts (1 956 ms
      gegen 537 ms) und riss damit die Regressionsschwelle — isoliert genauso
      wie im vollen Lauf. Es war keine Verlangsamung: Commit `43afb51` hat am
      13.08. den *Messgegenstand* getauscht („der Leistungstest aus P16.2 maß
      ein Verfahren, das es nicht mehr gibt") und dort schon notiert, was
      seither herauskommt — 1 778 ms und 1 480 ms von 3 000. Die alte Marke
      stand unter demselben Namen weiter in `tests/.performance.json`, und der
      Wächter verglich zwei verschiedene Rechnungen miteinander. Der Docstring
      von `measure()` sagt den Fix wörtlich vorher: „die Marke fällt mit einer
      Begründung im Commit, nicht stillschweigend beim nächsten Lauf" — genau
      das war unterblieben. Marke gestrichen, der nächste Lauf setzt sie neu.
      Die Datei ist gitignored, also gilt das für diese Maschine; wer den Test
      anderswo laufen lässt, fängt ohnehin bei null an

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
      Zone bei netcup. **Seit dem 16.08.2026 sechssprachig**: Startseite,
      Funktionen, KI-Modelle und Handbuch (Seite und PDF) auch auf es, fr,
      it und pt, Sprachwechsler als Aufklappmenü, Regelsammlung mit Fassungen
      je Handbuchsprache, Bildschirmfotos neu mit der aktuellen
      Werkzeugleiste. Hochgeladen am 18.08.2026 (297 Dateien), Stichproben
      über alle sechs Sprachen samt Bildern per HTTPS geprüft — alle 200,
      die README bleibt unten (404).

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

### Die Regressionsschwelle schlägt an, ohne dass etwas langsamer wurde

Gemessen am 14.08.2026, fünf Läufe von `pytest tests/test_slice.py
tests/test_performance.py -p no:randomly` allein auf der Maschine: **zwei von
fünf rot**, und zwar nicht am selben Test — einmal `sketch_solve_200` (125 ms
gegen den Bestwert 94 ms, Faktor 1,33), einmal `blending`. Beide Male war es die
25-%-Schwelle, kein absoluter Zielwert und keine echte Verlangsamung.

**Der Docstring von `measure` beschreibt die Ursache selbst**, und er hat sie
nur halb behoben: Er nennt achtunddreißig Prozent Unterschied allein aus der
Aufrufreihenfolge — `sketch_solve_200` braucht allein 114 ms und hinter
`test_slice.py` 162 — bei einer Schwelle von fünfundzwanzig. Das Merken des
**besten** Werts statt des letzten behebt das Anheben der Marke; dass ein Lauf
unter Fremdlast rot wird, „obwohl nichts langsamer wurde", steht dort als
Problem und bleibt ungelöst. Ein gespeicherter Bestwert kennt den Kontext
nicht, in dem er entstand.

**Der Code ist absichtlich unverändert.** Die naheliegende Reparatur — bei
Überschreitung einmal nachmessen und den besseren Wert nehmen — führt `work()`
zweimal aus, und mindestens ein Aufruf hängt an einem Zwischenspeicher
(`evaluate_cached`). Ein zweiter Durchgang wäre dort schneller, weil er den
Cache trifft, und aus einem roten Test würde ein **falsch grüner**. Das ist
schlimmer als der Zustand jetzt. Zwei Wege ohne dieses Risiko: den
Regressionsvergleich aussetzen, sobald andere Testdateien im Lauf sind (die
absoluten Schranken bleiben und prüfen weiter), oder den Bestwert je
Aufrufkontext getrennt halten. Beides ändert das Verhalten des Tors und gehört
angesagt, nicht nebenbei gemacht.

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

### Der kompilierte Kern, nachgerechnet (14.08.2026)

Der Satz darüber stand zwei Phasen lang als Vermutung. Er stimmt — aber erst
die Gegenprobe zeigt, *warum*, und sie hat unterwegs zwei andere Annahmen
umgeworfen. Alle Zahlen auf einer Maschine, die rund dreimal langsamer ist als
die, auf der die Tabelle oben entstand; verglichen wird deshalb nur
untereinander.

**Was die Zeit wirklich kostet.** Warm gemessen liegt der Polygonaufbau bei
1078 ms gegen 455 ms für das Sammeln der Segmente — GEOS ist also tatsächlich
die größere Hälfte. Threads helfen dort nicht, sie schaden: Faktor 0,75 auf
vier Kernen, weil `polygonize` den Interpreter-Lock hält.

**Die billigere Erklärung, geprüft und verworfen.** `polygonize` löst ein
schwereres Problem als wir haben: Es nodet beliebig kreuzende Linien, während
unsere Segmente aus Dreiecken mit exakt geteilten Ecken kommen und paarweise
zusammenpassen. Die Ringe selbst zu verketten ist damit ein Durchlauf in O(n)
ohne eine einzige Fließkommaentscheidung. In Python gemessen: **1215 ms** —
also nicht schneller als GEOS, das mehr tut. Vektorisiert über alle Schichten
(Halbkanten, Zyklenzerlegung, Zeigerverdopplung) waren es **540 ms**, wieder
dieselbe Größenordnung. Drei Wege, ein Ergebnis: Python ist hier an der Decke,
und zwar nicht am Verfahren, sondern am Interpreter.

**Übersetzt sind es 11 ms** — Faktor 54 auf dieselben Zeilen. Daraus ist
`app/core/slice/_chain.pyx` geworden, gebaut mit `tools/build_slice_core.py`.
Gemessen am selben Körper, beide Wege im selben Prozess:

| Vorgang | über GEOS | übersetzt | Faktor |
|---|---|---|---|
| `slice_body`, 328 000 Dreiecke, 0,2 mm | 2732 ms | 2041 ms | **1,34** |
| Orientierungssuche, 200 Lagen | 48,2 s | 35,8 s | **1,35** |
| Wandstärkenkarte | 5074 ms | 4602 ms | 1,10 |

**Das Modul ist optional, und das ist keine Bequemlichkeit.** Fehlt es, nimmt
`_rings_from` den Weg über GEOS — gemessen 2732 ms gegen 2789 ms vor der
ganzen Änderung, also unverändert. Ein Klon ohne Compiler wird dadurch nicht
langsamer als vorher, er wird nur nicht schneller.

**Robuster, aber ausdrücklich nicht genauer — und das war ein Fehlschlag
unterwegs.** Der GEOS-Weg rundet die Enden auf sechs Nachkommastellen, damit
sie zusammenfinden; genau dort meldete ein Behälter mit drei Fächern einmal
9 463 mm² Überhang, den es nicht gab. Die Verkettung *braucht* das nicht: Sie
kennt die Kante, auf der ein Punkt liegt, und die ist für beide
Nachbardreiecke dieselbe ganze Zahl.

Der erste Anlauf hat daraus den Schluss gezogen, dann eben nicht zu runden.
Das kostete `test_evaluation.py`: `compensate_elephant_foot` zieht den
Querschnitt mit `buffer` ein, extrudiert die Differenz und schneidet sie ab —
und eine Boolesche Operation macht aus einer Abweichung in der **neunten**
Stelle eine andere Topologie. Am ausgehöhlten Quader kamen 17 erkannte
Merkmale heraus statt 14, darunter ein Stift, den es nicht gibt, und die
Mehrdeutigkeit, an der die Auswertung anhalten sollte, verschwand.

Also rundet die Verkettung genauso. **Der übersetzte Weg ist der schnellere,
nicht der genauere**, und was die Kante bringt, ist die Ringschließung, die
nicht mehr davon abhängt, dass die Rundung zwei Enden zusammenführt.

Bemerkenswert ist, wie knapp das durchgerutscht wäre: `tests/test_slice_core.py`
gab es schon und es war grün — es verglich Flächen und Löcher auf `rel=1e-6`.
Es vergleicht jetzt die **Punkte** und die Flächen auf `1e-12`; übrig bleibt
eine Abweichung von einer letzten Stelle, weil GEOS sich den Anfangspunkt
eines geschlossenen Rings selbst sucht und die Flächenformel dadurch in
anderer Reihenfolge summiert.

**Was jetzt die größte Position ist**, ist nicht mehr der Polygonaufbau,
sondern `_plane_segments` mit 893 ms — das Sammeln der Schnittsegmente in
numpy. Wer §31 weiter schließen will, misst dort weiter, nicht bei GEOS.

### Drei fremde Bibliotheken, geprüft (14.08.2026)

Anlass war die Frage, ob C- oder C++-Bibliotheken auf Dauer mehr Spielraum
geben. Die Lizenzen waren nie das Problem — die Freigabeliste lässt MIT, Boost
und MPL zu —, die Auslieferung schon:

* **CoACD** (MIT, `abi3`-Wheels für alle drei Plattformen) sollte V-HACD in
  `convex_parts` ablösen. **Verworfen, gemessen.** Auto Split nimmt von der
  Zerlegung eine einzige Zahl, die Stelle der Einschnürung, und dort trifft
  V-HACD näher (Abweichung 7,2 gegen 9,2 an der Hantel). Dazu ist CoACD in der
  genauen Einstellung zwei- bis fünfzigmal langsamer — 32,3 s gegen 0,66 s an
  `plate_holes.stl` —, und grob eingestellt liefert es nur noch ein Stück,
  also gar keinen Hinweis. Es gibt keine Einstellung, in der es gleichzeitig
  schnell und aussagekräftig ist. Damit ist das „prüfen" in Bauplan §36
  beantwortet.
* **pyclipr** (Clipper2, Boost) hat **kein Linux-Wheel**. Es einzubauen hieße,
  eine C++-Bauumgebung in die CI zu holen — genau das, was eine fremde
  Bibliothek ersparen sollte.
* **libigl** (MPL-2.0) liefert nur bis cp312 und **nicht für Windows**. Das
  Projekt verlangt Python ≥ 3.13 und zielt auf Windows; es ist damit heute
  nicht installierbar, unabhängig davon, ob es fachlich passte.

Das Muster taugt als Regel: Bei einer nativen Abhängigkeit entscheidet nicht
die Lizenz und nicht der Funktionsumfang, sondern ob es Räder für Windows,
macOS und Linux in der Python-Fassung dieses Projekts gibt. Alles andere ist
eine Bauumgebung, die jemand pflegen muss.

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

- [x] **Zwei Anzeigen sprachen allein über Farbe** (Regel 18). In der
      Schichtanalyse lagen Insel und Überhang beide auf Strichstärke 3 — zwei
      gleich dicke Ringe übereinander, unterschieden allein durch die Farbe,
      und ausgerechnet bei den zwei Rollen, die eine Handlung nach sich ziehen.
      `LAYER_WIDTHS` gibt jeder ihre eigene Stärke, und die Schichtleiste trägt
      jetzt eine Legende, deren Strich so lang ist wie der Ring im Bild dick.
      Die Legende der Differenzansicht war ganz in der Farbe von „Hinzugefügt"
      gezeichnet — auch das Wort „Entfernt": eine Legende, die Farben erklären
      soll und beide gleich färbt, sagt das Falsche. Und die Schriftfarbe auf
      einem Farbfeld hing an einer festen Luminanzschwelle von 0,35, die über
      den mittleren Tönen von Viridis auf die schlechtere der beiden kippte
      (3,47 und 2,56); verglichen werden jetzt die zwei Kontraste.
- [x] **Objektbaum und Verlauf waren stumme Kästen**, und eine Suche ohne
      Treffer sagte an keiner der drei Stellen, dass nichts gefunden wurde. Ein
      neues Projekt beginnt in genau diesen Karten; die Parameterleiste daneben
      sagte seit jeher, wozu sie da ist. Befehlspalette und Bausteinkatalog
      nennen den Suchbegriff jetzt in einer nicht wählbaren Zeile, der
      Prüfbericht in einem Feld über der Liste — dort wird über `setHidden`
      gefiltert, ein Eintrag darin wäre beim nächsten Filtern im Weg.
- [x] **Kein ausgegrauter Menüeintrag nannte seinen Grund.** `_kind_hint` stieg
      sofort aus, wenn eine Operation kein `requires_kind` trägt — und das
      haben sieben von 84. Auf der leeren Szene stand damit bei jedem
      gesperrten Eintrag sein Beschreibungssatz: was er täte, wenn er könnte.
      Die Werkzeugzeile daneben sagte es im selben Augenblick richtig.
      `_reason_locked` nennt den Grund jetzt in der Reihenfolge, in der ein
      Nutzer ihn behebt: erst etwas in die Szene, dann etwas auswählen, dann
      die richtige Bauart. Ein Test vergleicht gegen den Beschreibungssatz —
      ein Hinweis, der ihm gleicht, ist keiner.
- [x] **Der Korrekturdialog verlor seine Klappe.** Wer eine Operation aus dem
      Verlauf öffnet, bekommt ihr ganzes Schema als Werte übergeben, und
      `entry.name in given` schob damit jedes Feld auf die Vorderseite — die
      gestufte Tiefe (§2.4) galt genau dann nicht, wenn jemand einen Wert
      nachbessern will. Nach vorn kommt jetzt, was vom Schema-Standard
      abweicht; Sammelwerte (Skizze, Striche, Skelett) bleiben hinten, was auch
      immer drinsteht.
- [x] **Der Knopf am gesperrten Chat führte in den falschen Dialog.** Er hieß
      „Zugang einrichten …" und öffnete die „Zusätzlichen Programme" — dort
      installiert man ein lokales Modell, trägt aber keinen Schlüssel ein. Der
      Dialog mit dem Schlüsselfeld heißt „Chat einrichten", steht im Menü unter
      genau diesem Namen und war vom Chat aus nicht erreichbar: einer der zwei
      Wege aus §27 fehlte. Knopf und Menüeintrag tragen jetzt wörtlich
      denselben Text und damit denselben Katalogeintrag.
- [x] **Eine Warnung erreichte niemanden mehr, sobald die rechte Spalte
      ausgeblendet war.** §2.5 nennt „Warnungen" für die Statusleiste, und dort
      standen sie nie; `_focus_report` steigt bei unsichtbarer Spalte zu Recht
      aus, und danach kam nichts. Der Zähler erscheint jetzt genau dann — bei
      offener Spalte trägt ihr Reiter die Zahl, und zwei Zähler wären einer zu
      viel — und ein Klick holt Spalte und Bericht zurück.
- [x] **„1 × warnings".** „Fehler", „Warnung" und „Hinweis" standen in allen
      fünf Katalogen im Plural, während die deutsche Quelle den Singular führt
      — nach dem Malzeichen steht er. Alle fünf sind gezogen.

- [x] **Was ein Bildschirmleser nicht las.** 44 von 102 fokussierbaren
      Elementen des Hauptfensters hatten keinen Namen — ein Feld ohne Namen
      wird als seine Art angesagt, „Eingabe", „Auswahl", „Schieber". Darunter
      die neun Beispielkacheln des Startbildschirms (das Erste, was jemand
      sieht: neun Mal „Rahmen"), die Wähler aller Leisten, jedes Suchfeld,
      jede Liste, der Schichtenregler. Jetzt trägt jedes bedienbare Element
      einen Namen; durch geht nur, was Qt selbst anlegt — die Aufklappliste
      eines Auswahlfelds trägt den Namen ihres Feldes, ein Reiterfeld wird
      über seine Reiter angesagt. Ein Test hält es bei null.
      Dazu zwei Nachbarn: Der Freischaltdialog war eine Tastenfalle — ein
      mehrzeiliges Feld nimmt den Tabulator als Zeichen, und wer ohne Maus
      arbeitet, kam aus dem Schlüsselfeld nicht mehr heraus. Und die
      Reiterleiste der rechten Spalte zeigte den Tastaturfokus mit null
      Bildpunkten Unterschied; sie bekommt eine gestrichelte Marke, denn der
      aktive Reiter trägt schon Akzentkante, Fläche und Fettschrift.

- [x] **Der Installationsdialog antwortete mit „Das hat nicht geklappt."** —
      und zeigte davor die rohe Befehlszeile und jede Zeile, die pip oder
      winget von sich geben, im Statuslabel. Wer das liest, weiß danach
      weniger als vorher. Der Kern gab bei einem Fehlschlag gar keinen Grund
      zurück, nur `installed=False`; er nennt jetzt einen, und zwar für alle
      drei Fälle — die Paketverwaltung ließ sich nicht starten, sie hat
      abgebrochen, oder sie meldete Erfolg und das Programm ist trotzdem nicht
      da. Der Rückgabewert steht bei den Einzelheiten statt im Satz: Dort
      gehört er hin, und ein Satz ohne Platzhalter übersetzt sich in fünf
      Sprachen leichter. Die rohe Ausgabe sammelt der Dialog und bietet sie
      hinter „Details anzeigen" an (§33.2).

- [x] **Zwei Sätze ohne Warum.** „Die Boolesche Operation ist
      fehlgeschlagen." stand noch in `profiles.py` — die zweite Stelle in
      `edit.py` war längst vorbildlich. Der Fall ist eng genug für einen
      richtigen Satz: Diese Verknüpfung fügt den Kern eines Gewindes mit
      seinem Gang zusammen, und was dort scheitert, scheitert an Flächen, die
      sich berühren statt zu überlappen. Der Ausweg ist ein anderes Maß, keine
      Reparatur — die gröbere Stufe versucht `_joined_rod` schon selbst.
      „Zwei Bedingungen widersprechen sich." nannte das Paar nicht, obwohl der
      Kern es seit jeher kennt und sogar anbietet, die eine oder die andere zu
      entfernen. Bei vierzehn Einträgen in der Liste durfte man suchen, welche
      zwei gemeint sind. Die Zeichenfläche merkt sich das Paar jetzt, und die
      Liste rechts schreibt beide an — mit einem Zeichen und nicht nur mit
      Farbe, denn eine Bedingungsliste wird auch ausgedruckt (Regel 18).
      Den Satz selbst baut die Oberfläche und nicht der Kern: Dort liegen die
      Beschriftungen, und der Kern führt seine Werte grundsätzlich über
      `values` statt über Platzhalter.

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

      **Diese Zahlen sind überholt** — beide entstanden unter einem Prompt, den
      Ollama bei 4096 Token abgeschnitten hat. Der Stand nach dem Fund und
      Systemprompt v2 ist **22/33 und 8/13**; er steht im Punkt „Der Agent
      greift nicht zu den Bausteinen" unten in diesem Abschnitt. Wer hier
      aufhört zu lesen, nimmt den falschen Wert mit.
- [x] **Eine Operation ohne Eingangsobjekt** stürzte mit einem `IndexError`
      ab, statt anzuhalten — `example_v1.p3d` ließ sich damit gar nicht öffnen.

### Zwei Spuren, die hier enden

- [x] **Die Hardware-Spur wird nicht weiter verfolgt** (entschieden am
      14.08.2026). Die Messreihen bleiben stehen, weil sie eine Reihe von
      Verdächtigen ausschließen und niemand sie zweimal aufstellen soll. Was
      nicht bleibt, ist der offene Punkt: Es wird keine Speicherdiagnose und
      kein Prozessortest gefahren. Ein Testlauf, der rot wird, heißt damit
      wieder „Fehler im Code" — und der flackernde Rändel-Test verliert seine
      Erklärung und wird zur Fehlersuche wie jede andere.

      **Was das kostet, steht dazu:** Die beiden Pflaster in
      `mesh.on_surface` und `threemf._numbers_from` — einmal wiederholen, beim
      zweiten Fehlschlag durchlassen — bleiben im Code, ohne dass eine Ursache
      dahinter nachgewiesen ist. Sie fangen einen Fehlschlag, den niemand mehr
      erklärt. Wer sie anfasst, weiß damit, dass er eine Stütze wegnimmt und
      nicht eine Redundanz.

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

      **Und der letzte Datenpunkt spricht gegen die Spur, nicht für sie.**
      Dass 300 Runden derselben Bauart nichts fanden, wo zehn Fehlschläge zu
      erwarten waren, heißt: Die Bedingung, unter der der Rechenfehler auftrat,
      ist keine Eigenschaft der Maschine, sonst wäre sie reproduzierbar
      gewesen. Damit endet die Spur — nicht weil sie widerlegt ist, sondern
      weil sie nichts mehr vorhersagt.
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

- [x] **`machine_profile` und `base_process` müssen Pfade sein, nicht Namen —
      die Auflösung dazwischen steht.** Die Anforderungen ziehen auseinander:
      In die Projektdatei gehört der **Name** (ein Pfad dort verstößt gegen
      Regel 12), der Slicer nimmt nur die **Datei**. `handover.profile_file`
      löst beides auf und wird an allen vier Stellen benutzt — Maschine,
      Prozess, Filament und im Profilschreiber.

      **Am 14.08.2026 am echten Bestand nachgemessen:** ElegooSlicer, 3887
      gefundene Profile, `profile_file("0.12mm Fine @Afinia H+1(HS)", …)`
      liefert die existierende Datei unter `resources/profiles/…`. Fünf Tests
      in `tests/test_print_settings.py` halten Name, Pfad, falsche Art und den
      leeren Fall fest. Der Punkt stand offen, weil ihn niemand abgehakt hat —
      nicht, weil etwas fehlte.
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

## Das Zeichnen-Kapitel Satz für Satz gegen den Code (09.08.2026)

Zweiter Durchgang, auf die Bitte, alles gründlicher durchzugehen. Jede
Behauptung des neuen Kapitels gegen die Stelle im Code, die sie beschreibt —
und dabei kam heraus, dass zwei der Abweichungen keine Textfehler waren,
sondern Fehler im Editor. Vier Funde, alle behoben:

- **Strg+Z lag im Skizzenmodus beim Verlauf.** Das Kürzel hing am
  `SketchEditorDialog`, und den Dialog gibt es nur auf einem der beiden Wege.
  Im Skizzenmodus des Fensters nahm Strg+Z damit die letzte **Operation**
  zurück, während vor dem Nutzer eine Zeichenfläche stand. Jetzt bringt das
  Panel das Kürzel mit, und `_update_actions` graut Rückgängig/Wiederholen im
  Modus aus — beide Hälften nötig, denn bei zwei aktiven Belegungen derselben
  Taste feuert Qt keine (dieselbe Falle wie bei R und C).
- **Der Weg über das Operationsfeld war ärmer als der Skizzenmodus.** Kein
  Bauraumrand, keine Fläche des Körpers in der Ebenenwahl, und *Projizieren*
  antwortete „Es gibt keinen Körper, aus dem sich projizieren ließe" — an
  einem Modell, das im Fenster stand. Der Docstring von `SketchPanel`
  verspricht seit je, dass keiner der beiden Wege ein Werkzeug bekommt, das
  der andere nicht hat. `Surroundings` (Bauraum, Zeichenebenen,
  Projektionsvorlagen) trägt die drei Angaben jetzt zusammen,
  `MainWindow._sketch_surroundings()` ist die eine Quelle, und der
  Operationsdialog reicht sie an sein Skizzenfeld durch.
- **Der dritte Weg, einen Spline zu schließen, stand nur im Kommentar.**
  „Doppelklick, Eingabetaste oder ein zweiter Klick auf denselben Punkt" — den
  letzten gab es nicht: der Klick hängte einen weiteren, deckungsgleichen
  Punkt an die Kurve, still und ohne Ton. Wer den Griff aus einem CAD
  mitbringt, holte sich einen doppelten Punkt. `_on_last_pending` prüft jetzt
  in Bildschirmpunkten, mit derselben Toleranz wie der Fang.
- **Der README nannte die Seitenzahl des Handbuchs** — „dreiunddreißig
  Seiten: achtzehn geschriebene" — und lag zum dritten Mal daneben (der
  zweite Fall steht oben unter „Handbuch, Website und Rechtstexte
  durchgesehen"). Die Zahlen sind heraus, die Aussage bleibt: eine erzeugte
  Seite pro Kategorie. Was gezählt werden kann, zählt das Programm; der
  Vorspann der erzeugten Handbuchseite nennt die Zahl.

Und was im Kapitel schlicht **fehlte**, weil der Editor mehr kann, als beim
Schreiben in Erinnerung war: zoomen und schieben, das Ziehen eines Punktes mit
nachziehendem Solver, **Strg zum Sammeln** (ohne das kommt niemand auf
*Parallel*, das zwei Linien braucht), die zwei Bedeutungen von `Entf` je nach
Fokus, die zählende Klickreihenfolge. Dazu zwei zu grob formulierte Stellen:
das Maßfeld gilt nur für Linie und Kreis, nicht „nach dem ersten Klick"
allgemein, und bei einer angeklickten Fläche entscheidet deren Neigung über
die Schichtrichtung — nicht die Unterscheidung liegend/stehend.

Aus dem Vorschlag wurde derselbe Tag noch eine Umsetzung:

- [x] **Der Skizzeneditor kannte kein Einpassen.** Der Maßstab stand fest auf
      4 Punkte je Millimeter, und niemand rührte ihn an; eine geöffnete Skizze
      von 300 mm lag zur Hälfte außerhalb, der Bauraumrahmen von 220 × 220 beim
      Start gar nicht im Bild — ausgerechnet der, der die früheste Warnung
      tragen soll (E1). `fit_view` passt jetzt ein: eine vorhandene Zeichnung
      gibt das Maß (ragt sie über die Platte, kommt der Rahmen von selbst mit),
      ein leeres Blatt zeigt den Bauraum. Als Vorgabe **und** als Knopf mit
      `Pos1`, weil man sich verzoomt.

      Zwei Dinge kamen erst beim Nachmessen heraus. **Einmal einpassen genügt
      nicht:** der erste Versuch tat es beim ersten `resizeEvent` und
      verbrauchte sich — das Layout verteilt in mehreren Durchgängen, der erste
      bringt die Mindestgröße, und im Fenster fehlte danach ein Sechstel des
      Bauraums. Die Ansicht hängt jetzt an der Einpassung und zieht mit, bis
      jemand selbst zoomt oder schiebt. Und **der Rand ist an der Beschriftung
      bemessen, nicht an der Geometrie:** die Maßzahlen stehen außerhalb der
      Kontur, bei vierundzwanzig Punkten stand im Handbuchbild „60,0(" am
      rechten Rand.

## Dasselbe noch einmal, gründlicher (09.08.2026)

Der erste Durchgang fuhr jede Operation einmal mit ihren Vorgaben gegen einen
Quader. Das findet, was immer bricht. Dieser fragte weiter: gegen **fünf
Körperarten** (Netz, exakter Körper, importiertes STL, ausgehöhlt, Paar), an
**jeder Parametergrenze** des Schemas, und danach die vier Fragen, die eine
Anwendung beantworten muss — rechnet sie zweimal dasselbe, nimmt ein Undo sie
zurück, übersteht sie das Speichern, läuft die Entwurfsqualität.

712 Läufe. Was dabei herauskam:

- [x] **Neu vernetzen war nach dem letzten Commit für importierte Teile
      unbrauchbar.** Gleichmäßiges Teilen hält das Netz geschlossen und
      zerteilt dabei die winzigen Bohrungsfacetten mit: aus 796 Dreiecken
      wurden 815 104 bei fünf Millimetern, dreizehn Millionen bei einem —
      abgelehnt. Jetzt eine Kette wie bei den booleschen Operationen: erst
      nach Bedarf teilen, gleichmäßig nur, wenn das Netz sonst aufginge. Wer
      die Decke reißt, erfährt die Kantenlänge, die noch geht.
- [x] **Glätten stülpte einen ausgehöhlten Körper um** — minus 19 318 mm³,
      wasserdicht, exportierbar, und jede Kennzahl danach falsch. Und ein
      Vollquader aus zwölf Dreiecken schrumpfte auf sieben Prozent, während
      der Docstring „ohne den Körper zu schrumpfen" versprach.
- [x] **Die Merkmalszuordnung fragte ins Leere.** Sie stand außerhalb des
      Fehler-Fangs der Auswertung: wer keinen Frage-Dialog hat — Kommandozeile,
      Fernsteuerung, Agent —, bekam eine Ausnahme aus `evaluate` und einen
      leeren Prüfbericht statt der zwei Bohrungen, zwischen denen zu wählen war.
- [x] **Der exakte Gewindebolzen hielt nur ein Fünftel seines Schemas.** Ab
      50 mm Durchmesser kam nie ein geschlossener Körper heraus, bei 100 mm und
      1 mm Steigung einer mit null Volumen und null Komponenten, bei 0,25 mm
      Steigung neunzehn Bruchstücke — stumm. M2 mit 1,5 mm Steigung ergab einen
      Faden von 0,16 mm, weil die Kernprüfung nur fragte, ob überhaupt etwas
      übrig bleibt. Beides wird jetzt geprüft, bevor der Körper die Operation
      verlässt.
- [x] **Das OpenSCAD-Zeitlimit kam als `subprocess.TimeoutExpired`** heraus
      statt als Fehler mit Ausweg. `sphere(r = 50, $fn = 2000)` genügt dafür —
      ein Vertipper, kein Angriff.

### Was der Durchgang bestätigt hat

Das ist der andere Teil des Ergebnisses, und der größere:

| Frage | Läufe | Befund |
|---|---|---|
| Wirft je etwas anderes als ein `AppError`? | 712 | keiner |
| Zweite Auswertung gleich der ersten? | 74 | alle |
| Undo stellt den Vorzustand her? | 74 | alle |
| Speichern und Laden ändert nichts? | 74 | alle |
| Entwurfsqualität läuft, wo die feine läuft? | 74 | alle |
| Öffnet jeder Operationsdialog? | 77 | 71, die sechs anderen haben keine Parameter oder sind zu Recht ausgegraut |
| Felder auf der Vorderseite ≤ 8, Titel, Einheit, Erklärung? | 71 Dialoge | vollständig |
| Kommandozeile: alle Operationen, Fehler ohne Stapelabzug? | 77 + 7 Fehlerfälle | vollständig |

Suite 3438 grün (in zwei Portionen — der Abriss im Lauf am Stück ist weiter
der bekannte native, `test_chat_ui.py` läuft allein durch).

**Beobachtung ohne Fix:** `scale_object` mit Faktor 0,001 und `fit_to_size` mit
0,1 mm liefern einen Körper, den man nicht mehr sieht und nicht drucken kann —
mathematisch richtig, verlangt, und ohne ein Wort dazu. Eine Warnung „kleiner
als die Düse" wäre eine Erweiterung, kein Fehler; sie steht hier, damit die
Entscheidung eine ist.

## Der ganze Bestand durch die laufende Oberfläche (09.08.2026)

`tools/run_ui_audit.py` schickt alles, was auf dieser Maschine liegt, durch das
echte Fenster: 14 Projektdateien, 88 Modelle aus den Druckordnern und dem
Korpus, dazu den Weg von der leeren Szene bis zum geschriebenen Paket. Nicht
gegen den Kern — den prüft die Suite —, sondern mit Arbeitsfäden, Signalen und
Viewport, also dort, wo ein Fehler erst auftritt, wenn jemand davorsitzt.

**Ergebnis: 103 Stück, keins gestolpert.** Langsamstes Projekt
`puppenhaus_fertig` mit 7,1 s, langsamstes Modell die gähnende Katze mit 29 s,
der Aufbau von Null in 0,6 s.

Die Befunde sind die erwarteten für heruntergeladenes Fremdmaterial: 208-mal
„unter der Druckplatte" (Hinweis, nicht Warnung — heruntergeladene Teile sind
meist um den Ursprung zentriert), 86-mal verschweißte Punkte, 30-mal entartete
Dreiecke entfernt, 17-mal nicht wasserdicht, zehn Rückfragen nach der Einheit.

### Der eine Fehler, der dabei herauskam

`sketch_pocket` warf einen `ValidationError`, wenn der Körper ein Netz ist.
Dessen Titel lautet „Ein Wert liegt außerhalb des zulässigen Bereichs" — im
Prüfbericht stand damit eine Meldung über Zahlen, wo keine Zahl schuld war.
Für diesen Fall gibt es `NeedsSolidError`; `brep/ops.py` und `export/writer.py`
waren den Weg schon gegangen, diese Stelle war übersehen worden. Die Meldung
nennt jetzt den Ausweg (Regel 17): `shell_exact` statt `hollow_object`.

Sichtbar wurde es an `puppenhaus_fertig` und `puppenhaus_exakt`: dort höhlt
`hollow_object` den exakten Körper aus und gibt ein Netz zurück, worauf die
drei Taschen danach ins Leere laufen und die Auswertung bei Operation 4
stehenbleibt. **Die beiden Projekte sind damit nicht repariert** — ihre
Operationsreihenfolge kann so nicht funktionieren. Sie stehen im Bericht
weiter als `ABBRUCH@op4`, jetzt mit einer Meldung, die sagt, was zu tun wäre.

### Was der Durchgang über das Prüfen gelehrt hat

Sieben Fehler steckten im Prüfwerkzeug, einer in der Anwendung. Vier davon
waren geratene Signaturen (`result.findings` statt `scene.report.findings`,
`write_plan` mit einem Argument zu viel, `completed` — ein Tupel von Op-IDs —
statt der Property `complete`). Die teureren zwei waren Zeitfragen: wer nach
`start_new` nur auf `not busy` wartet, kommt durch, bevor der Arbeitsfaden
angelaufen ist, misst den Stand von vorher und bricht mit dem nächsten Aufruf
die laufende Auswertung ab. Elf von fünfzehn Modellen standen daraufhin als
„0 Objekte" im Bericht — sie luden alle. Im Sekundentakt wiederholt zerlegte
dasselbe Abbrechen den Prozess ohne Ausnahme; das sah lange nach einem
Absturz der Anwendung aus und war einer der Messung.

Der letzte Hänger kostete vier Minuten je Lauf und drei falsche Vermutungen:
`closeEvent` → `_may_discard` → `confirm_unsaved`. Das Fenster fragte beim
Schließen nach ungespeicherten Änderungen, und niemand antwortete. Ein
Stapelabzug hat das in einem Versuch beantwortet, wo Raten es dreimal nicht
tat — `faulthandler` bleibt deshalb über den ganzen Lauf scharf.

---

## Gegen das Wettbewerbsfeld gehalten (11.08.2026)

`konzept-wettbewerb-2026-08.md` zieht auf, was `konzept-sindricad.md` an einem
einzelnen Konkurrenten gemessen hat: sechs Gruppen — parametrisches CAD,
Direktmodellierer, Einsteigerwerkzeuge am Modellkatalog, Mesh-Reparatur,
Slicer, KI —, jeder Bereich der Anwendung dagegen gehalten.

**Der Befund ist nicht, dass etwas fehlt, sondern dass das Falsche vorn
stand.** Führend sind wir beim Anpassen fremder Modelle (Meshmixer
eingestellt, 3D Builder abgekündigt), bei der Druckbarkeit vor dem Slicen und
bei `auto:<material>`. Die Website führte mit Säule A — dem einen Bereich, in
dem Autodesk gerade Foundation-Modelle für editierbares B-Rep auffährt.

### Umgesetzt

- [x] **GLB hinausschreiben** (B4 aus dem SindriCAD-Konzept). Mit Namen und
      Farben: glTF kennt Farben nur an Ecken, deshalb je Materialslot ein
      eigenes Teilnetz — sonst kommt die Grenze zwischen roter Platte und
      blauer Schrift als Verlauf über das halbe Teil an. Die Kommandozeile
      nimmt ihre Formatliste jetzt aus dem Schreiber.
- [x] **Mehrsprachigkeit als Gerüst.** `available_languages()` liest das
      Katalogverzeichnis; Erstlauf, Einstellungen, Einsammler, Handbuch und
      Abbildungen lesen es. Eine neue Sprache ist eine Datei. Der
      Übersetzungstest prüft jede gefundene, nicht mehr nur die englische —
      halb übersetzt einchecken geht damit nicht. Das Dezimaltrennzeichen
      kennt jetzt auch Spanisch, Französisch, Italienisch und Portugiesisch.
- [x] **Modell aus dem Netz** (§16.3). Verweis aus dem Browser ablegen oder
      *Datei → Modell aus dem Netz*, Feld mit der Zwischenablage vorbelegt.
      Beides geht durch `Session.import_payload`, also durch dieselbe
      Operation wie eine Datei von der Platte. Nur http/https, Größengrenze
      beim Lesen statt am `Content-Length`, Herkunft in `Source.origin`. Eine
      Adresse mit HTML dahinter ist eine Modellseite und bekommt genau diesen
      Satz — ausgewertet wird nichts.
- [x] **Texturmuster sichtbar** (B2). Bild und Name je Zeile in der Auswahl,
      gezeichnet aus `pattern_shapes`. Dazu eine Handbuchabbildung mit allen
      achten und ein Abschnitt auf der Startseite.
- [x] **Website.** Weg 1 als Aufmacher, Windows und Linux ausdrücklich mit
      macOS als benannter Lücke (eigene FAQ-Frage), GLB bei den Formaten.

      **Die FAQ-Frage war falsch, und zwar zu unseren Lasten** (am 14.08.2026
      gegen die CI geprüft). Sie sagte „Nein, vorerst nicht … für Windows und
      Linux", während `build.yml` seit je vier Pakete baut: `windows-latest`,
      `ubuntu-latest`, `macos-13` (Intel) und `macos-latest` (Apple Silicon),
      jeweils mit Bundle-Prüfung, `codesign`-Schritt und `ditto`-Archiv. Drei
      andere Stellen derselben Seite — Auszeichnung für Suchmaschinen,
      Zusicherungsliste und Systemvoraussetzungen — nannten den Mac korrekt.
      Eine Seite, die Kunden von einer Plattform abrät, die sie ausliefert,
      kostet mehr als eine Lücke. Beide Sprachen nachgezogen; was tatsächlich
      fehlt, ist allein die Apple-Signatur, und die Systemvoraussetzungen
      sagten das schon vorher richtig.

### Was der Durchgang durch das laufende Fenster gefunden hat

Zwei Zeilen unter der Musterauswahl, die gerade Bilder bekommen hatte, standen
die Werte weiter englisch: „Art: raised", „Auflegen: flat". Über das ganze
Register waren es **sechsundzwanzig** Auswahlwerte. Behoben, und
`tests/test_translations.py` lässt nur noch durch, was sein eigener Name ist
(M4, 6x3, mm, x, DejaVu Sans, gyroid).

Der zweite Fund war ein eigener Fehlbefund: die beworbenen **77 Operationen**
sind richtig. Ein Zähllauf über `walk_packages` kam auf 61, weil die sechzehn
`insert_*`-Operationen der Bausteine erst mit `load_operations()` entstehen.
`tests/test_website.py` prüft die Zahl gegen das Register und hat es gefangen,
bevor die falsche Zahl auf der Seite stand.

### Offen, mit Entscheidung dahinter

- [ ] **Sichtbarkeit.** Solidon ist fertiger als das, worüber geschrieben
      wird, und unbekannt. Keine Entwicklungsaufgabe.
- [ ] **macOS ausliefern.** Die Suite läuft dort bei Tags grün; es fehlen
      Apple-Signatur und die Bereitschaft, eine dritte Plattform zu stützen.
      Die Website sagt es jetzt ausdrücklich, statt es auszulassen.

      **Der Paketierschritt fehlt nicht mehr** (nachgesehen am 14.08.2026):
      `build.yml` baut das Bundle, prüft es auf seine ausführbare Datei,
      signiert mit einer Developer-ID sofern das Secret liegt, packt als zip,
      rechnet die Prüfsumme über `shasum -a 256` und lädt je Architektur ein
      eigenes Artefakt hoch — Intel und Apple Silicon getrennt. Was wirklich
      fehlt, ist enger und benennbar: das **Apple-Zertifikat** und die
      **Notarisierung**. `xcrun notarytool` und `stapler` kommen im Auftrag
      nirgends vor, und ohne sie hält Gatekeeper eine geladene Anwendung auch
      dann an, wenn sie signiert ist.
- [ ] **G-Code an die Maschine senden** (B3). §28 meint mit „Drucker" das
      Zurücklesen; Senden wäre eine Bauplanänderung. Wenn, dann über ein
      offenes Protokoll für viele Maschinen.
- [x] **Weitere Sprachen befüllen.** Erledigt und am 14.08.2026 nachgezählt:
      `app/i18n/locales/` führt fünf Kataloge — `en`, `es`, `fr`, `it`, `pt` —
      mit je **2 426 Einträgen**, keiner leer. Was in einem Katalog wie die
      deutsche Quelle aussieht, sind Eigennamen und Maßangaben (24 bis 48 je
      Sprache: `mm`, `M4`, `6x3`, `DejaVu Sans`, `gyroid`), und die sollen so
      stehen. Die Zahl der Sprachen steht dabei nirgends im Code —
      `available_languages()` zählt das Verzeichnis.
- [x] **Skizze bedienerisch fertig** (B1). Die Ändern-Gruppe stand schon;
      die übrigen Punkte aus `konzept-bedienung.md` Teil 4 sind seither
      nachgekommen — die Stand-Notiz dort führt alle neun als durch, im Code
      nachgeprüft am 13.08.

## Die Demo bis 30.10.2026 (12.08.2026)

Entschieden: eine öffentliche Demo statt eines Testlaufs. Start **20.08.2026**,
Ende **30.10.2026**, kostenlos, vollständig, ohne Schlüssel. Danach fällt am
10.10. die Entscheidung zwischen 1.0 und einer zweiten Runde. Das Konzept mit
allen Abwägungen steht in `.claude/konzept-demo-2026-10.md`; hier steht, was
davon gebaut ist.

### Was der gründliche Durchgang gefunden hat

Der erste Durchgang las die Unterlagen, der zweite sah nach — gegen GitHub,
den Webserver und die Paketierung. Fünf Funde:

- [x] **Die Setup-Datei ließ sich nicht bauen.** PyInstaller baute nach
      `dist/Solidon`, `make_installer.py` suchte `dist/Solidon3D`. Die
      Umbenennung hatte die Paketierung nie erreicht; die CI trug den alten
      Namen an vier weiteren Stellen. Der Name kommt jetzt überall aus
      `app/branding.py`.
- [x] **Das Handbuch im Paket hatte keine Bilder.** `app/images/manual/` stand
      nicht in den `datas` — F1 hätte an jeder Abbildung eine Lücke gezeigt,
      stillschweigend. `tests/test_packaging.py` hält beides fest: kein
      zweiter Ort für den Namen, und jedes Verzeichnis mit Nicht-Python-
      Dateien muss ins Paket.
- [x] **Der Segmentierungsfehler auf dem Ubuntu-Runner.** Seit dem 06.08. starb
      jeder Lauf an derselben Zeile — `HistoryPanel.show_document`,
      `self.list.clear()`. Eine Messung mit zerlegter Suite zeigte, dass der
      Absturz *wandert*: er hing an keinem Test, sondern an den Fenstern, die
      sich über den Lauf ansammelten. Ein `window`-Fixture gibt sein Fenster
      zurück und überlässt es dem Speicherbereiniger; sammelt Python es ein,
      während eine Zustellung läuft, schreibt `clear()` in freigegebenen
      Speicher. Unter Windows behält der Allokator die Seite, unter Linux gibt
      er sie zurück. Die Fixture zerstört Fenster jetzt planmäßig
      (`deleteLater` plus `processEvents`), und `MainWindow.release()` schließt
      dabei den VTK-Interactor — ohne das stirbt der **nächste** Fensteraufbau.
- [x] **Das Repository ist öffentlich** und hieß bis heute `Formwerk`.
      Umbenannt auf `Solidon`; die Sichtbarkeit ist Roberts Entscheidung und
      steht auf öffentlich. Damit ist H5 (kompiliertes Prüfmodul) eine Bremse
      und keine Hürde — H1 hält weiter.

      **Am 14.08.2026 nachgeprüft und zwei Reste nachgezogen**, die die
      Umbenennung nicht erreicht hatte. Die API bestätigt beides —
      `full_name: RS-Digital-Studio/Solidon`, `private: false`, der alte Name
      antwortet mit 301. Aber der lokale `origin` zeigte weiter auf
      `.../Formwerk.git` (GitHub leitet weiter, deshalb fiel es nie auf), und
      der Kopf von `build.yml` begründete die Ein-Plattform-Matrix damit, das
      Repository sei privat und die Minuten gezählt. Öffentliche Repositories
      zahlen für die Standard-Runner nichts; die Begründung war weg, die
      Beschränkung stand noch. Beides steht jetzt richtig da — die Matrix
      selbst bleibt, aber mit dem Grund, den sie wirklich hat (Rückmeldezeit),
      und mit dem Hinweis, was sie kostet: Ein Fehler, der nur unter Windows
      auftritt, fällt sonst erst am Tag der Veröffentlichung auf.
- [ ] **DMARC fehlt** für `solidon3d.de`. SPF und MX stehen (netcup), der
      Eintrag `_dmarc` ist nicht gesetzt. Gehört ins CCP.

### Gebaut

- [x] **Stichtag im Kern.** `store.DEMO_UNTIL` ersetzt die Frist ab dem ersten
      Start; `Activation.deadline` und `.over` sagen der Oberfläche, woran sie
      ist. Der Testlaufmarker verliert damit seine Bedeutung. Zwei Tests halten
      dagegen: einer weckt, wenn der ausgelieferte Stichtag verstrichen ist,
      der andere verbietet einer 1.x-Fassung überhaupt einen Stichtag.
- [x] **Fassung 0.1.0** (am 14.08.2026 von 0.7.0 heruntergesetzt, entschieden
      von Robert). Die Null vorn ist Mechanik: `key.current_major()` liest sie,
      also greift ein 1.x-Kaufschlüssel in der Demo nicht — und der
      Update-Hinweis zeigt später auf die 1.0. Die 7 dahinter war nie
      begründet; die 1 ist der Anfang einer Zählung, die weitergeht.

      **Die Zählregel steht jetzt dabei:** letzte Stelle plus eins je
      ausgeliefertem Bau, vordere Stellen nur bei einer größeren Änderung.
      Sieben Stellen tragen die Zahl, zwei davon von Hand (`app/branding.py`,
      `pyproject.toml`) — und bis heute hielt die beiden nichts zusammen außer
      Aufmerksamkeit. `test_the_version_is_the_same_in_both_places_that_carry_it`
      tut es jetzt.
- [x] **Die Texte.** Statuszeile dauerhaft (nicht erst am vorletzten Tag),
      Über-Dialog, Freischaltdialog, Ersteinrichtung.
- [x] **Der Schluss.** Nach dem Stichtag startet weder Fenster noch
      Kommandozeile; die Meldung nennt das Datum, die Website und den Verbleib
      der eigenen Dateien.
- [x] **Zwei Menüeinträge**: nach einer neuen Fassung sehen (mit Antwort in
      allen drei Fällen) und Rückmeldung schreiben.
- [x] **Rechtstexte.** EULA §4a für die Demo; AGB und Widerruf sagen, dass sie
      ab dem Verkaufsstart gelten.
- [x] **Website.** Beide Startseiten führen die Demo, zwei neue Fragen
      beantworten das Ende.
- [x] **Startseite geteilt** (14.08.2026). Sie war auf **14 Bildschirme**
      gewachsen, und der Preis begann erst bei Bildschirm 11 — der
      Funktionsblock allein war mit 4809 px 36 % der Seite. Funktionen und
      KI-Modelle haben jetzt eigene Seiten (`funktionen.html`,
      `ki-modelle.html` und die englischen), auf der Startseite steht je ein
      Anriss. Gemessen bei 1920×937: **8,0 Bildschirme, Preis ab 4,8**, und der
      Knopf im Aufmacher steht im ersten Bild statt 100 px darunter.
      Nebenbei vier Selbstwidersprüche behoben, die beim Kaufentscheid standen:
      „Drei Wege" über vier Karten, acht gegen neun Beispielprojekte, zwei
      Sie-Formen auf einer Du-Seite, und der Plattform-Absatz wanderte aus dem
      Aufmacher in die Voraussetzungen.
- [x] **Ein Skript auf der Website** (14.08.2026). `site.js` markiert in der
      Sprungliste der Funktionsseite den Block, der gerade gelesen wird — das
      Einzige, was CSS dort nicht kann. Damit fällt die Zusage „kein
      JavaScript"; die tragende bleibt und ist jetzt die geprüfte: **nichts von
      außen**, kein CDN, keine Bibliothek, kein Zählpixel
      (`test_the_page_loads_nothing_from_outside`). Die Bewegung der
      Zeichnungen bleibt CSS.

### Offen bis zum 20.08.

- [ ] **CI grün sehen und die Artefakte holen** — Setup-Datei, tar.gz,
      Prüfsummen. Der Weg über `workflow_dispatch`; Inno Setup liegt auf dem
      Runner, nicht auf dieser Maschine.

      **Am 14.08.2026 nachgesehen, und der Stand ist schlechter als er hier
      klang.** Von **34 Läufen ist genau einer grün** — der vom 02.08., per
      Handstart. Jeder Push seither ist rot, auch der letzte auf `93f0989`.
      Damit gibt es keine Artefakte: `package` hängt an `suite` und wird
      übersprungen, und alle drei Punkte unter diesem hier warten auf einen
      Lauf, den es nicht gibt.

      **Woran er scheitert, steht im Protokoll und ist nicht das, was der
      Abschnitt weiter unten sagt.** Der Hauptblock ist grün — 3 275 Tests,
      10 übersprungen, 1 xfail, in 456 s. Danach laufen die Fensterdateien
      einzeln, und `tests/test_chat_ui.py` stirbt beim achten Test an einem
      Segmentierungsfehler:

      ```
      panels.py:890 show_document ← main_window.py:4389 _show_scene
        ← main_window.py:4340 _on_scene ← session.py:1101 _on_finished
        ← session.py:1164 wait_for_idle
        ← test_chat_ui.py:217 test_a_reversible_proposal_is_applied_without_asking
      ```

      Das ist **nicht** der Test, den „Der Absturz, der die CI eine Woche lang
      rot hielt" als einzigen Rest führt. Dort steht
      `test_the_applied_bar_clears_when_something_newer_is_on_top`, und der ist
      per `skipif` übersprungen — der hier trifft es zusätzlich. Die Stelle ist
      dieselbe wie immer (`self.list.clear()`, die erste Widget-Anweisung des
      Szenenaufbaus), die Kette ist neu: Sie kommt aus `wait_for_idle`, also
      aus dem Ereignispumpen *im laufenden Test* und nicht aus einem Fenster,
      das der Speicherbereiniger schon abgeräumt hat.

      Eine Ursache steht hier bewusst **nicht**: Sie wäre geraten. Der Absturz
      tritt auf Linux auf, diese Maschine ist Windows, und der lokale Lauf
      läuft zudem unter einer anderen Interpreter-Fassung (siehe den
      Rändel-Test weiter unten). Wer ihn angeht, hat die Kette oben und die
      vier gemessenen Irrwege in jenem Abschnitt.

      **Und die Gegenprobe hier stirbt auch** — an einer anderen Stelle und
      mit einem anderen Fehlerbild. `pytest -q -m "not performance"` kam am
      14.08.2026 sechzig Tests weit und ging dann mit einem `Windows fatal
      exception: stack overflow` unter, beim Aufbau des Viewports:

      ```
      pyvistaqt/rwi.py:254 __init__ ← pyvistaqt/plotting.py:231 __init__
        ← viewport.py:1037 __init__
        ← test_analysis_ui.py:1983 test_a_body_too_thin_for_a_hull_still_gets_one
      ```

      **Und die Interpreter-Spur erklärt ihn nicht — gemessen, nicht
      vermutet.** Die Messung, die der Abschnitt unten fordert, ist am
      14.08.2026 gefahren: `.venv-py313` mit **Python 3.13.15** frisch
      aufgebaut, dieselbe Suite. Sie stirbt genauso, nur woanders — der
      Stapelüberlauf steht dann in `main_window.py:790 _build_central`, aus
      `test_sketch_editor.py:826`, bei achtzig Prozent. Anderer Test, andere
      Zeile, gleiches Bild. Ein Absturz, der wandert, hängt an keinem Test und
      an keiner Interpreter-Fassung.

      **Was er stattdessen ist, steht seit dem 13.08. im Kopf von
      `build.yml`:** die Zahl der VTK-Fenster, die ein Prozess nacheinander
      aufbaut. Die CI teilt deshalb auf; der lokale Lauf tat es nicht. Beide
      betroffenen Dateien laufen **allein grün** — `test_sketch_editor.py`
      85 Tests in 3,9 s, `test_analysis_ui.py` 99 in 30 s.

      **Aufgeteilt wie die CI ist diese Maschine grün**, und das ist die Zahl,
      die seit Tagen fehlte: Hauptblock ohne die dreizehn Fensterdateien
      **3 313 Tests in 186 s**, dazu zwölf der dreizehn Dateien einzeln, jede
      grün.

      **Die dreizehnte ist der eigentliche Fund.** `tests/test_ui.py` (190
      Tests) stirbt schon nach fünf, mit einem *anderen* Fehlerbild —
      `access violation` statt Stapelüberlauf —, und zwar an
      `test_saving_and_reopening_keeps_the_stack`. Dreimal reproduziert.
      Derselbe Test **ganz allein** aufgerufen läuft in 0,3 s durch, unter
      3.13 wie unter 3.14. Es sind also wieder die Fenster davor, nur reicht
      hier eine Handvoll, wo andere Dateien neunundneunzig vertragen — dort
      baut jeder Test ein volles Fenster. Die CI kommt darüber hinweg, weil
      `--forked` jedem Test seinen eigenen Prozess gibt; unter Windows gibt es
      das nicht, und deshalb ist `pytest -q` hier nicht der richtige Aufruf.
      Wer das lokale Tor grün sehen will, teilt auf — und für `test_ui.py`
      bleibt die Frage offen, warum fünf Fenster genügen.
- [ ] **Auf einem fremden Rechner installieren** (ohne Python, ohne venv, ohne
      OpenSCAD/Ollama/ComfyUI). Der Punkt, der erfahrungsgemäß mehr findet als
      alle Tests.
- [ ] **Download-Kasten mit echter Datei und Prüfsumme**, dazu der Satz zur
      SmartScreen-Warnung: die Demo geht unsigniert hinaus, weil Azure Trusted
      Signing Nachweise braucht, die keine acht Tage dauern. 0.9.1 trägt sie
      nach.
- [ ] **Hochladen** — Website ohne `README.md`, `version.json` zuletzt.

---

## Das Erzeugen-und-Agent-Konzept abgearbeitet (12.08.2026)

`konzept-erzeugen-agent-oberflaeche-2026-08.md` ist umgesetzt. Zwei Punkte sind
dabei anders ausgefallen als geplant, beide begründet.

- [x] **Gedreht wird um das, was man ansieht.** Der Kamerafokus stand auf dem
      Weltursprung; ein heruntergeladenes Teil liegt fast nie dort und wanderte
      beim Drehen im Bogen durchs Bild. Blickrichtung und Abstand bleiben.
- [x] **Das Freistellmodell durfte nicht verkauft werden.** `RMBG-2.0` steht
      unter CC BY-NC und stand als Vorgabe in beiden Graphen; `INSPYRENET`
      (MIT) tut dasselbe. Ein Test verhindert den nächsten Fall.
- [x] **Hunyuan3D bleibt, mit einem Satz dazu.** Es ist für die EU ausdrücklich
      nicht lizenziert, ein Wechsel braucht aber eine andere Knotensammlung in
      ComfyUI. Solidon liefert keine Gewichte, der Graph nennt Rollen statt
      Dateien — Modulkopf und Handbuch sagen jetzt, was das bedeutet.
- [x] **Dezimieren in der Erzeugen-Kette.** Gemessen: 42 s, 1.588.016 Dreiecke,
      **null Merkmale** — der Agent hatte nichts, worauf er zeigen konnte.
      Oberhalb von 500.000 kommt jetzt eine vierte Transaktion auf 200.000.
- [x] **Das Werkzeugschema für lokale Modelle.** 99 → 79 KB, **ohne ein
      Werkzeug wegzulassen**: nach `applies_to` zu filtern wäre eine
      Betriebsart mit anderem Namen gewesen. Der größte Posten waren nicht die
      Beschreibungen (13 KB), sondern die Parametertexte (36 KB).
- [x] **Was ein lokales Modell leistet, steht an der Chatleiste** — drei von
      fünf Treffern, bis zu zwei Minuten je Aufruf, gemessen mit
      `tools/check_local_model.py`.
- [x] **Anschluss statt Wettlauf.** Wer mit Meshy, Tripo oder Rodin erzeugt,
      bringt das GLB her; druckbar wird es hier. Dazu im Handbuch der Satz,
      dass die MCP-Werkzeuge die Operationen der folgenden Kapitel sind.
- [x] **Karten wachsen mit breiten Fenstern**, anteilig und mit Deckel. Bei
      3413 px war die linke ein Zwölftel des Fensters, und die Maßspalte brach
      mitten in der Zahl ab.

### Was die Sitzung über das Prüfen gelernt hat

**Ein Messgerät, das seinen Gegenstand verändert, misst nichts.** Der
VTK-Screenshot rendert neu und reparierte damit genau den Zustand, den er
zeigen sollte; `QWidget.grab()` lässt den OpenGL-Bereich schwarz. Beide haben
mich stundenlang einen Viewport-Fehler jagen lassen, den es in der laufenden
Anwendung nicht gab: meine Prüfskripte fuhren `processEvents()` statt
`app.exec()`, und ein natives OpenGL-Fenster zeichnet so nur, solange etwas
passiert. Der Beweis war der Stand vom 08.08. — bei mir derselbe Fehler, in
der Anwendung intakt.

**Der eine Schritt, der die Frage beantwortet hätte, war die Anwendung
normal zu starten.** Eine Minute statt eines halben Tages.

**Und das Protokoll sagt, was die Ausnahme verschluckt.** Die Achsenanzeige
fehlte dreimal nacheinander, und jedes Mal stand der Grund als eine Zeile in
`app.log`: die Repräsentation kennt kein `SetViewport`, `add_axes` kennt kein
`shaft_type`, `label_color` setzt es selbst. Ein `except`, das nur
protokolliert, macht solche Fehler unsichtbar — die Anzeige war weg, und im
Fenster stand kein Wort darüber (Regel 17 dem Geist nach).

---

## Die Durchsicht vom 13.08.2026 — Auswahl und Zeichnen

Drei Beobachtungen aus der laufenden Anwendung, alle drei behoben.

- [x] **Gewählt war die Bohrung, hervorgehoben der ganze Körper.** Ein Klick
      auf ein Merkmal wählt zweierlei aus, den Körper und die Stelle; gefärbt
      wurde nur das Erste. Jetzt trägt das Merkmal die Auswahlfarbe auf seinen
      eigenen Dreiecken (`highlighted_faces`), der Körper bleibt grau, und die
      Beschriftung steht auch bei ausgeschalteter Überlagerung da.
- [x] **Zeichnen zeigte nicht, was gleich passiert.** Keine Vorschau am
      Zeiger, kein Rasterfang (Punkte auf -29,75 mm), ein Raster mit fester
      Weite, ein Rad, das auf die Bildmitte zoomte, und eine Statuszeile, die
      nicht sagte, wie man einen Linienzug beendet. Alle fünf behoben; der
      Fang ist an, ein Millimeter, mit Haken an der Ebenenzeile.
- [x] **Zwischen Draufsicht und Seitenansicht lag ein Klappmenü.** Die Ebenen
      heißen jetzt nach der Ansicht, die Achsenbuchstaben folgen ihnen, und
      die Ziffern 1, 2, 3 wechseln direkt.

- [x] **Gedreht wurde um die Kulisse.** Der Drehpunkt kam aus
      `ComputeVisiblePropBounds` — alles Sichtbare, also auch Druckplatte und
      Bauraumrahmen. Bei 250 mm Rahmen und 40 mm Teil lag die Mitte hundert
      Millimeter über dem Modell, und die Kamera rückte bei jedem
      Szenenaufbau mit. Jetzt `_object_bounds()`, dieselbe Quelle wie beim
      Einpassen.
- [x] **`tools/make_figures.py` zeichnete nur, solange etwas passierte.**
      `settle()` fuhr `processEvents`; ein natives OpenGL-Fenster braucht
      einen laufenden Loop. Beides zusammen — Drehpunkt und Werkzeug — hat
      das Hauptfenster zweimal mit leerem Viewport ins Handbuch gebracht.

**Ein Fund, den ich zuerst falsch zugeordnet habe.** Das leere Handbuchbild
sah nach dem bekannten Messproblem aus, und der Abschnitt darüber beschreibt
es. Es war die Anwendung: die Kulisse im Drehpunkt. Wer eine bekannte Ursache
zur Hand hat, prüft sie zuerst — und dann trotzdem die andere.

### Offen aus derselben Durchsicht

- [x] **`test_the_layer_analysis_survives_a_knurled_surface` fiel unter Last —
      und „Last" hieß: vier `pytest`-Läufe gleichzeitig.** Aufgelöst am
      14.08.2026. Der Aufruf `pytest tests/test_slice.py
      tests/test_performance.py -p no:randomly` lieferte `TypeError: cannot
      unpack non-iterable int object` in `analysis.py:377` — an einer Stelle,
      an der `enumerate` über `list[list[int]]` läuft und das gar nicht kann.

      **Derselbe Aufruf, allein auf der Maschine: fünf von fünf grün**, kein
      TypeError, 38 bis 41 Sekunden je Lauf. Was vorher fehlte, war nicht die
      Ursache, sondern die Kontrolle über die Umgebung: Auf diesem Rechner
      liefen vier `pytest`-Aufrufe gegen **dieselbe** `.venv`, dazu ein
      `http.server`. Qt und VTK bauen dabei echte Fenster und GL-Kontexte, und
      mehrere Läufe darüber sind genau die Bedingung, unter der es rot wurde.
      Wer eine Messung an dieser Suite macht, sorgt zuerst dafür, dass sie
      allein läuft — sonst misst er die Nachbarschaft und nennt es einen Bug
      im Kern.

      Damit ist auch die Zuordnung zum „Maschinen-Cluster" hinfällig, und die
      beiden anderen Kandidaten (Interpreter-Fassung, Hardware) sind für dieses
      Fehlerbild nicht mehr nötig. Der Kern bleibt unverändert — an
      `_polygon_from` war nichts zu reparieren, was das Nachmessen an Shapely
      2.1.2 unten schon zeigte.

      **Die Chronologie, weil sie den Umweg erklärt:** Zuerst zweimal
      hintereinander gefahren, erster Lauf rot, zweiter grün — daraus wurde „ist
      nicht einmal unter Last deterministisch" und die Zuordnung zur Hardware.
      Richtig war der erste Teil, falsch der Schluss: Nicht die Maschine
      schwankte, sondern die Zahl der Läufe auf ihr.

      **Und die Zeilenangabe stimmt nicht mehr** (nachgesehen am 14.08.2026):
      `analysis.py:377` ist heute `if not parts: return None`, ohne jedes
      Unpacking. Die Stelle, auf die der Befund zeigt, ist inzwischen Zeile 372
      — `zip(held.tolist(), holder.tolist(), strict=True)` über die Rückgabe
      von `STRtree.query`. **Der Verdacht dort ist ausgeschlossen**, nachgemessen
      gegen Shapely 2.1.2: `query` liefert bei jedem listenartigen Eingang ein
      Feld der Form (2, n), auch bei genau einem Element; eindimensional wird es
      nur bei einer *einzelnen* Geometrie, und `points` ist an dieser Stelle
      immer eine Liste. Beide Unpackings der Funktion können den Fehler nicht
      werfen.

      Der Kern brauchte also keine Änderung, und bekam keine.

- [x] **Entwickelt wurde unter einer Fassung, die nie ausgeliefert wird**
      (gefunden und behoben am 14.08.2026). Nebenbefund der Suche oben, und mit
      ihr nicht verwandt: Diese Maschine hatte ihre `.venv` unter **Python
      3.14.2**, während `pyproject.toml` mypy auf 3.13 stellt und alle drei
      CI-Aufträge `python-version: "3.13"` fahren. Die Paketfassungen waren
      identisch mit `constraints.txt` — aber es waren andere Binaries:
      `shapely/lib` lag als `cp314-win_amd64.pyd`, in der CI als `cp313`. Damit
      lief der ganze Unterbau aus C-Erweiterungen (shapely/GEOS, numpy, scipy,
      trimesh, rtree, manifold3d, VTK, OCCT) lokal in einer Fassung, die weder
      geprüft noch paketiert wird — und jeder grüne Lauf hier sagte etwas über
      eine Umgebung, die kein Kunde bekommt.

      Behoben: Python 3.13.15 installiert, `.venv313` gegen `constraints.txt`
      aufgebaut, cp313 nachgewiesen. Die beiden Umgebungen unterscheiden sich
      danach in genau zwei Paketen, und keines davon ist gepinnt (`pip`,
      `pypdf`).

      **`constraints.txt` allein reicht dafür nicht**, und das ist die Lehre:
      Es pinnt die Fassungen, nicht den Interpreter. Wer eine Umgebung nach der
      Anleitung in `CLAUDE.md` aufbaut, bekommt die gepinnten Fassungen für
      *sein* Python — und wenn das ein anderes ist als in der CI, andere
      Binaries bei identischen Nummern.

### Ein Gewinde, das nur auf einem Betriebssystem schließt (13.08.2026)

`thread_exact` mit **M6 und einem Millimeter Steigung** — das gewöhnlichste
Gewinde überhaupt — kommt unter Windows als geschlossener Bolzen heraus und
auf den Linux-Runnern als offener. Dieselbe Rechnung, andere OCCT-Fassung.

Vier Anläufe, alle gemessen, keiner erfolgreich:

- **ShapeFix** nach der Vereinigung. Näht, was rechnerisch zusammengehört —
  hier nicht genug.
- **Gröbere Fuzzy-Toleranz.** Ein Tausendstel der Steigung: die Boolesche
  Operation gab ganz auf. Deshalb stehen jetzt drei Werte von fein nach grob
  (`ROD_FUZZ_RATIOS`), jeder in seinem eigenen Versuch.
- **Beides zusammen**, in Stufen wie die Boolesche Rückfallkette (§17.2).
- Dabei fiel ein **echter Fehler** auf, der nichts mit der Plattform zu tun
  hat: OCCT ändert seine Argumente, wenn man es nicht verbietet. Die zweite
  Vereinigung rechnete mit Formen, die die erste ausgehöhlt hatte — auf dem
  Runner ein Segmentierungsfehler ohne Zeile, hier ein stilles falsches
  Ergebnis. `SetNonDestructive(True)` steht jetzt in `_fuzzy_boolean`, und
  das gilt für **jede** Boolesche Operation dort, nicht nur fürs Gewinde.

- [ ] **Offen: den helikalen Gang so bauen, dass er überall schließt.** Der
      Verdacht liegt nicht mehr bei der Vereinigung, sondern beim Gang selbst
      (`MakePipeShell`) — dort wäre der nächste Griff `SetTransitionMode`,
      oder das Gewinde als Rotationskörper statt als Sweep. Bis dahin trägt
      `tests/test_sketch_ops.py::test_a_sound_thread_still_goes_through` ein
      `xfail` für Linux, nicht `strict`: sobald eine Fassung es dort kann,
      wird der Lauf grün und die Marke fällt auf. Für die Demo ist die Wirkung
      begrenzt — sie erscheint für Windows, und dort geht es.

### Der Absturz, der die CI eine Woche lang rot hielt (13.08.2026)

Vom 06. bis zum 13.08. starb jeder Lauf auf dem Ubuntu-Runner, und zwar immer
an derselben Anweisung — der ersten Widget-Zeile des Szenenaufbaus
(`show_document`, `self.list.clear()`) —, aber jedes Mal in einem anderen
Test. Ein Absturz, der wandert, hängt an keinem Test.

**Vier Ursachen wurden gefunden und behoben**, jede für sich ein echter Fehler:

- [x] **Die Sitzung überlebt ihr Fenster.** Ein `window`-Fixture gibt sein
      `MainWindow` zurück und überlässt es dem Speicherbereiniger; die
      `Session` daneben lebt weiter und ruft ihr nächstes Ergebnis in Widgets,
      die es nicht mehr gibt. `MainWindow.release()` kappt die Verbindung, die
      Fixture ruft es nach jedem Test.
- [x] **Verzögerte Aufrufe ohne Empfänger.** Fünf `QTimer.singleShot` liefen
      ohne Kontextobjekt weiter, nachdem ihr Widget weg war — im
      Bausteinkatalog sichtbar als `RuntimeError`, anderswo als Absturz.
- [x] **OCCT ändert seine Argumente**, wenn man es nicht verbietet: die zweite
      Boolesche Operation rechnete mit Formen, die die erste ausgehöhlt hatte.
      `SetNonDestructive(True)`.
- [x] **Die Suite prüfte die Sprache des Rechners**, nicht die der Anwendung
      (`QLocale`), und ein Test über deutsche Kommas war grün, ohne dass jemand
      etwas dafür getan hätte.

**Zwei Wege waren falsch** und stehen hier, damit sie niemand wiederholt:
Fenster planmäßig zerstören (`deleteLater` plus `sendPostedEvents`) nimmt VTKs
Zustand mit, und der **nächste** Fensteraufbau stirbt in
`render_window_interactor.initialize`. Und `pytest-xdist` ersetzt eine Grenze
durch eine andere: ein sterbender Worker reißt den ganzen Lauf mit einem
`INTERNALERROR` ab.

**Was den Lauf grün gemacht hat**, ist die Aufteilung: jede Testdatei, die
Fenster baut, bekommt in der CI ihren eigenen Prozess (gesucht, nicht
gepflegt), und die Suite läuft dort unter Xvfb statt unter Qts
Offscreen-Plattform — VTK will einen GL-Kontext.

- [x] **Die fünfte Ursache:** `Session.wait_for_idle` wartete
      auf Auswertung, Trennebenensuche und Vorschau — **nicht auf den
      Agenten**. Ein Vorschlag, der nach dem Testende fertig wurde, stellte
      sein Ergebnis in ein Fenster zu, das der Speicherbereiniger abgeräumt
      hatte. In `test_chat_ui.py` traf es reproduzierbar den zehnten Test,
      nicht den, der den Arbeiter gestartet hatte. Der Kommentar über der
      Zeile sagte die Regel bereits — der Agent stand nur nicht in der Liste.
      Damit fällt auch das `skipif`, das eine Stunde lang dort stand.

**Was am Ende grün ist:** der Hauptblock (3018 Tests) und jede Fensterdatei in
ihrem eigenen Lauf, unter Xvfb, mit `--forked` je Test. Ein einziger Test
bleibt übersprungen —
`test_chat_ui.py::test_the_applied_bar_clears_when_something_newer_is_on_top`
stirbt auf Linux auch im eigenen Fork. Er nimmt dort niemanden mehr mit; unter
Windows, der Plattform der Demo, läuft er.

- [ ] **Offen: dieser eine Test.** Der Verdacht liegt bei VTKs Zustand über
      mehrere Fenster hinweg — dieselbe Wand, an der `deleteLater` und
      `gc.collect()` gescheitert sind. Wer ihn angeht, findet die vier
      gemessenen Irrwege oben und braucht sie nicht zu wiederholen.

---

## P16 — Organische Modellierung

Die Frage war, ob Solidon organische Formen und Figuren nicht nur generieren,
sondern **machen** kann. Die Antwort steht in
`konzept-organische-modellierung-2026-08.md`: ja, und der teure Teil ist nicht
die Technik.

**Der Kundenkreis ist erweitert** (Entscheidung vom 13.08.2026). Figuren
gehören dazu, Posing wird mitgenommen, Käfigmodellierung bekommt einen
Prüfpunkt statt eines Versprechens. Damit fällt die halbe Begründung von
Befund B13 im Meshy-Konzept — sie ist dort mit Datum zurückgenommen, statt
still stehen zu bleiben.

**Was die Recherche zutage gefördert hat**, und was den Zuschnitt der Phase
bestimmt:

*Regel 2 war nie das Hindernis.* Sie verbietet Geometrieänderungen außerhalb
einer Op — sie verlangt nirgends, dass jede Nutzergeste ein eigener Schritt
wird. Diese Gleichsetzung stand nur in der Auslegung, und der Skizzeneditor aus
P13 hat sie längst gebrochen: hunderte Klicks, ein Op-Eintrag, der Skizzentext
als Parameterwert. Der Modulkopf von `sketch/edit.py` nannte das „Regel 2 dem
Geist nach" — der Buchstabe passte damals nicht, und niemand hat ihn
nachgezogen.

*Die Messung hat den Entwurf entschieden, nicht umgekehrt.* Ein Pinselstrich
je `warp_batch` kostet bei 100 Strichen auf 16 000 Vertices bereits 747 ms und
wächst mit dem Produkt aus Strichzahl und Vertexzahl — bei einer echten Figur
wären das Minuten. Alle Striche in **einem** Durchgang über einen KD-Baum:
5 000 Striche auf 65 538 Vertices in 586 ms. Faktor sechzig, und er entscheidet
zwischen „geht nicht" und „geht". Der Preis steht als Entscheidung C im
Konzept: Striche werden dadurch kommutativ, und die Werkzeuge, bei denen das
nicht trägt, laufen in Etappen.

*`manifold3d` bringt alles mit* — `warp_batch`, `level_set`, `refine`,
`smooth_out`, `calculate_curvature`, `mirror`. Nachgesehen, nicht vermutet.
Zwei Eigenschaften bestimmen den Entwurf: `warp` ändert die Topologie nicht
(also keine dynamische Tessellierung, Auflösung ist eine eigene Op davor), und
es prüft keine Selbstdurchdringung (also läuft die Prüfung danach).

### Was daraus folgt

- [x] **P16.1 — Regel 2 neu gefasst.** Eine Op darf beliebig viele Gesten
      sammeln, wenn ihr Ergebnis vollständig aus ihren Parametern folgt.
      `tests/test_gesture_ops.py` prüft fünf Eigenschaften über das ganze
      Register: der Sammelwert geht in den Op-Hash ein, übersteht die runde
      Reise, ist reiner Text, fehlt im Agentenschema (Leitprinzip 5) und steht
      auf der Rückseite des Dialogs. 26 Tests, grün auf dem Bestand — die neue
      Regel ist bewiesen, bevor eine Zeile neuer Geometrie sie braucht.
      `AGENTS.md` und `.claude/rules/operationen.md` nachgezogen.
- [x] **P16.2 — Gemessen, und R1 ist entwarnt.** Die riskante Zahl war die
      Vorschau: ein Strich unter 50 ms. Gemessen an `dense_1m.stl` — 1,31 Mio.
      Dreiecke, das Sechseinhalbfache der Budgetgröße — sind es **0,7 ms**,
      weil ein Strich nur 10 595 von 3 932 160 Vertices trifft. Die
      naheliegende Vollkopie des Vertex-Arrays kostet 28,4 ms, das
      Vierzigfache; `test_a_brush_stroke_stays_inside_a_frame` verhindert sie.
      Daraus folgt der Vorschauweg: Der Pinsel geht **nicht** über den
      Geometriekern, sondern schreibt ins Anzeigenetz; ausgewertet wird beim
      Verlassen der Sitzung. Strichliste (1 000) neu auswerten: 67 ms von 2 s.
      Subdivision: 574 ms von 3 s. Vier Leistungstests, dazu einer, der
      Entscheidung C prüft statt sie zu behaupten.

      **Ein Befund, den niemand bestellt hatte:** `generated_figure.stl` direkt
      zu sculpten ergibt ein *leeres* Manifold. Die Datei trägt absichtlich
      Generatorfehler, und `manifold3d` nimmt kein Netz an, das kein Volumen
      ist. Nach `GENERATED_REPAIR` sind es 3 368 Dreiecke und wasserdicht, nach
      `refine(8)` 215 552. Die Kette für Weg 3 heißt damit vollständig:
      generieren → reparieren → verfeinern → sculpten, und der Editor prüft
      beim Öffnen beides statt an einem leeren Ergebnis zu scheitern.
- [x] **P16.3 — `subdivide_surface`, `remesh_uniform`.** Die Prüffrage des
      Pakets lautete, ob das gleichmäßige Vernetzen in `remesh_mesh` gehört.
      Gemessen an `plate_holes`: **nein, und nicht knapp.** Die Streuung der
      Kantenlängen liegt vor `remesh_mesh` bei 2,224 und danach bei 2,224 — auf
      die vierte Stelle unverändert. Die Operation macht das Netz feiner, nicht
      gleichmäßiger, weil sie jede Kante gleich oft teilt und das Verhältnis
      zwischen der längsten und der kürzesten damit mitnimmt. Bezahlt wird das
      mit 3 260 416 Dreiecken für 1,5 mm Zielkantenlänge; `remesh_uniform`
      kommt auf 30 648 bei einer Streuung von 0,41. **Faktor hundert**, und
      zwei verschiedene Zusagen: die eine teilt nur und verschiebt nie einen
      Punkt, die andere teilt *und* fasst zusammen und sagt, was das gekostet
      hat.

      **Das Fehlerbild, das das Paket gekostet hat.** Der naheliegende Weg für
      `subdivide_surface` — `smooth_out` + `refine_to_length`, so wie ihn das
      Konzept in H1 nennt — bricht bei CAD-Netzen zusammen. `smooth_out` fasst
      je zwei koplanare Dreiecke zu einem Viereck zusammen und überspringt
      beim Verfeinern dessen Diagonale; wo *jede* ebene Fläche aus genau zwei
      Dreiecken besteht, ist das jede Fläche. `plate_holes` verlor damit ein
      Sechstel seines Volumens (31 322 → 25 832 mm³) und bekam 2 772 Kanten
      der Länge null — und meldete sich weiter als wasserdicht, also hätte es
      keine Prüfung danach gefangen. `calculate_normals` + `smooth_by_normals`
      leitet die Tangenten aus den Eckpunktnormalen ab, kennt keine Vierecke
      und hält die Form exakt. Die Kugel wird darüber genauso rund: 33 436 von
      33 510 mm³ möglichen. `tests/test_subdivision.py`, 15 Tests.

      **Zwei Funde nebenbei, beide in bestehendem Code.** Der Vorschlag bei zu
      kleiner Kantenlänge rundete die erreichbare Länge auf zwei Stellen und
      nannte damit bei 0,05 mm exakt die Zahl, die er gerade abgelehnt hatte —
      ein Vorschlag, der die Ablehnung wiederholt, ist keiner (Regel 17). Und
      der Übergang in den exakten Netzkern lief über `Mesh`, das `float32`
      nimmt; `Mesh64` gibt es, und der Kern rechnet in doppelter Genauigkeit
      (Regel 6). Beides behoben.

      **Zwei Abweichungen vom Konzept, mit Ansage.** Die Ops stehen in
      Kategorie `mesh` neben ihren Geschwistern, nicht in einer neuen Kategorie
      `organic` (Entscheidung M): Wer „Neu vernetzen" sucht, findet
      „Gleichmäßig vernetzen" daneben, und zwei Operationen desselben Zwecks in
      zwei Menüs wären eine Zumutung. Über `organic` entscheidet P16.5, wenn
      die vier wirklich neuen Ops dazukommen — `test_interface_limits.py`
      bleibt bis dahin grün, ohne dass eine Grenze angehoben wurde.
      `subdivide_surface` bekommt zwei Parameter statt der drei aus §7.2: Der
      dritte hieß „Iterationen" und ist bei diesem Verfahren wirkungslos, weil
      eine zweite Runde auf einem Netz, das die Zielkantenlänge bereits hat,
      keine neuen Punkte erzeugt und damit nichts interpoliert.
- [x] **P16.4 — `blend_union`.** Zwei Körper mit fließendem Übergang statt
      scharfer Kehle, gerechnet über ein gemeinsames Abstandsfeld. Die einzige
      Operation der Phase, die *parametrisch* organisch ist — und die einzige,
      die an eine Innenkante kommt, wo kein Pinsel hinreicht.

      **Drei verworfene Wege, jeder mit einer Zahl.** `level_set` von
      manifold3d, wie das Konzept es vorsieht, ruft eine Python-Funktion je
      Rasterpunkt auf: mit analytischer Formel brauchbare 0,7 µs, mit zwei
      interpolierten Feldern darin **25 Sekunden**. Marching Cubes auf dem
      vektorisierten Feld liefert dieselbe Isofläche in **200 ms**, ohne den
      Callback dazwischen. Beim Abstandsfeld war der billige Weg
      (`voxelized().fill()` plus Distanztransformation) um eine halbe Zelle zu
      groß — er markiert jede berührte Zelle und misst ab Zellmitte, an einer
      Kugel mit 25 mm Radius **acht Prozent zu viel Volumen**. Der genaue Weg
      über `Trimesh.contains` gab das richtige Vorzeichen und endete nach
      75 000 Rasterpunkten in einer **Zugriffsverletzung in rtree** — genau
      dort, wo die Hausregel lautet, diesen Index weniger zu fragen statt
      öfter.

      Geblieben ist: Abstand über einen KD-Baum auf einer deterministisch
      verdichteten Oberflächenwolke, Vorzeichen über die Normale am nächsten
      Punkt. An derselben Kugel 0,9956 — so gut wie die exakte Abfrage und 24
      mal schneller. `workers=-1` bringt weitere 6,3: **1,5 statt 9,6
      Sekunden** bei identischem Ergebnis, und ein Leistungstest hält den Wert
      fest, damit er nicht unbemerkt wegfällt.

      **Das Fehlerbild dieses Pakets:** Ein achsparalleler Quader mit runden
      Maßen legt seine Flächen genau auf die Rasterpunkte. Dort ist das Feld
      exakt null, Marching Cubes findet keinen Vorzeichenwechsel und spannt
      entartete Dreiecke auf — 793 Bruchstücke statt eines Körpers. Das Raster
      liegt deshalb um 0,37 Zellen versetzt, mit Absicht kein einfacher Bruch.

      Was der Dialog über das Überbrücken sagt, ist gemessen: ab etwa dem
      Dreifachen der Übergangsbreite. Wer schmaler wählt, bekommt einen Befund
      statt zweier Körper, die er für einen hält. Kategorie `boolean` wie bei
      P16.3, aus demselben Grund. 10 Tests, 1 242 ms von 3 000.
- [x] **P16.5 — Sculpting-Kern**, ohne Oberfläche und über das Register schon
      jetzt von der Kommandozeile aus bedienbar. `sculpt_strokes` trägt die
      ganze Sitzung in einem Sammelparameter `kind="strokes"`; die fünf
      Prüfungen aus `tests/test_gesture_ops.py` warten seit P16.1 darauf und
      greifen ohne eine Zeile Anpassung.

      **Die Auswertung ist akkumuliert** — KD-Baum, je Strich eine
      Kugelabfrage, Gewichte summieren, einmal verschieben. Tausend Striche auf
      dem §31-Prüfnetz kosten **96 ms von 2 000**. Der Preis steht als Test da
      und nicht als Fußnote: Striche derselben Etappe sind kommutativ.

      **Robert hat sich für die erzwingbare Etappe entschieden** (13.08.2026).
      `Stroke.cut` setzt eine Grenze an beliebiger Stelle — wer zweimal
      übereinander fahren und dabei das Ergebnis des ersten Zuges treffen will,
      kauft die exakte Reihenfolge stückweise statt für die ganze Sitzung.
      Glätten, Aufblasen und Flachziehen lesen den Zustand vor sich und
      beginnen von selbst eine Etappe. Entscheidung D (Einbacken mit Nachfrage)
      ist bestätigt und gehört in P16.9.

      Sechs Werkzeuge, nicht sechzig. Flachziehen bildet seine Ebene aus dem,
      was der Pinsel greift, nicht aus dem Klickpunkt — eine feste Ebene
      schnitte in den Körper, sobald der Pinsel größer ist als die Wölbung
      darunter. Symmetrie ist eine Eigenschaft der Operation, wird mit der des
      Strichs verodert und spiegelt am **Objektursprung**: Der Schwerpunkt
      wandert beim Formen.

      **`clean_figure.stl` ist im Korpus** (§18) — Rumpf, Kopf, Arme, Beine aus
      Grundformen vereinigt, derselbe Aufbau wie in P16.11. Sie entsteht auf
      dem Weg, den die Anwendung ihren Nutzern anbietet. 26 Tests, davon drei
      über die ganze Kette aus Entscheidung E.
- [x] **P16.6 — Sculpting-Sitzung im Viewport**, mit Pinselring und
      mitlaufender Wandprüfung. Ein Werkzeugmodus und kein Betriebsmodus
      (Entscheidung J): Er gilt für die eine Operation, die gerade entsteht,
      die Szene bleibt die Szene, Escape kommt heraus. Anders als beim
      Skizzenmodus bleibt die Ansicht — geformt wird am Körper.

      **Die Vorschau geht den Weg aus P16.2**: Sie schreibt in das
      Vertex-Array des Anzeigenetzes, statt einen Actor neu zu bauen. Der
      Dokumentzustand ändert sich dabei nicht — er ändert sich bei „Fertig",
      in einer Transaktion. Vier Züge, ein Schritt im Verlauf, ein Undo nimmt
      ihn vollständig zurück (Regel 16). Strg+Z nimmt währenddessen einen
      **Zug** zurück, nicht die Operation davor; Escape beendet wie „Fertig"
      und verwirft nicht.

      **Der Ring liegt in der Szene, nicht am Zeiger** — die Gebietsregel sagt
      warum, und sie hat recht: Ein Zeiger hat feste Punktgröße und behauptete
      beim ersten Zoom eine Größe, die er nicht mehr hat. Flach auf der Fläche
      statt in der Bildebene, mit einem Hilfsvektor aus der schwächsten Achse
      der Normale — ein fester wäre an jeder achsparallelen Fläche entartet.

      **Die Wandprüfung hat eine Zahl gekostet, die niemand geraten hätte.**
      Das Raster der Karte muss feiner sein als die Mindestwandstärke: bei
      2 mm Raster und 1,2 mm Mindestwand meldete sie **null** zu dünne Stellen
      an einer Schale mit 0,8 mm Wand. Eine Prüfung, die immer schweigt, ist
      schlimmer als keine. Sie läuft verzögert nach der Geste und steht als
      Zahl da, nicht nur als Farbe (Regel 18). 19 Tests, offscreen.

      **Nicht offen, sondern gestrichen** — richtiggestellt am 14.08.2026, weil
      es hier zwei Sätze lang wie eine Lücke aussah: Der wählbare Abfall
      (glatt, linear, scharf) aus §7.1 ist im Konzept selbst entfallen und hat
      seinen Platz in der Leiste an „Neu ansetzen" aus Entscheidung C verloren.
      Die Auswertung hat deshalb eine feste Gewichtsfunktion —
      `exp(-4·d²)` in `sculpt._weights` —, und das ist die Entscheidung, nicht
      ihr Rest. Wer den Abfall nachträglich einbaut, reißt die harte Grenze von
      acht Bedienelementen aus `tests/test_interface_limits.py`; er wäre das
      neunte.
- [x] **P16.7 — `displace_image`.** Die Helligkeit eines Graustufenbildes
      wird zur Höhe auf der Oberfläche. Getrennt vom Pinsel, weil es ein
      **Wert** ist und kein Handgriff — und deshalb darf der Agent es setzen:
      Leitprinzip 5 verbietet ihm Koordinaten, nicht Zahlen.

      Kein neues Paket dafür: `imageio` kommt seit je mit scikit-image und
      steht in der Freigabeliste. Abgetastet wird **bilinear** — mit dem
      nächsten Nachbarn bekäme jedes Pixel eine Stufe, und aus einem weichen
      Relief würde eine Treppe mit der Auflösung des Bildes, also genau der
      Vorwurf, den `texture_ops` an Höhenfelder richtet.

      Zwei Prüfungen, die der Bildschirm nicht beantwortet: ob das Netz genug
      Eckpunkte hat (unter einem je zwei Bildpunkten bleibt vom Relief nichts,
      und das Ergebnis wäre nicht falsch, sondern leer) und ob das Relief
      tiefer ist als eine Druckschicht. 17 Tests.

      **Die vierte Projektion steht** (§7.4): auf eine erkannte Fläche, die
      einzige Art, die auf einer schrägen Fläche nicht verzerrt. Fehlt die
      Fläche, hält die Operation an, statt still auf „von oben" auszuweichen —
      das Ergebnis sähe fast richtig aus und läge auf der falschen Ebene. Die
      Kachelung bleibt entfallen, mit Grund: Ein gekacheltes Höhenfeld hat an
      jeder Kachelgrenze eine Kante, die kein Drucker trifft.
- [x] **P16.8 — `pose_armature`, Kern.** Eine Pose, keine Animation. Drei
      Streichungen gegenüber einem Animationsprogramm, alle drei Absicht:
      eine Pose statt einer Bewegung, Vorwärtskinematik statt inverser,
      **gerechnete Gewichte statt gespeicherter**. Die dritte ist die
      interessanteste — gespeicherte Gewichte wären ein zweiter
      Dokumentbegriff neben dem Stapel und beim nächsten Vernetzen darunter
      falsch, ohne dass jemand es merkt.

      Zwei Fallen im Skinning, beide mit Test: Gedreht wird um den Kopf des
      Knochens und nicht um den Weltursprung (sonst fliegt der Arm weg), und
      Eltern kommen vor Kindern, unabhängig von der Reihenfolge in der Datei
      (sonst bleibt der Unterarm stehen, während der Oberarm sich hebt). Ein
      Zyklus im Baum hält an. Der Abstand geht zum **Segment**, nicht zur
      Achse — eine unendliche Achse bände die Fußspitze an den Oberarm.

      `armature` ist der dritte Sammelparameter neben `sketch` und `strokes`;
      `test_gesture_ops.py` prüft ihn seit P16.1 mit, ohne eine Zeile
      Anpassung. 16 Tests.

      **Der Skeletteditor steht** (§7.5): zwei Klicks je Knochen, der nächste
      hängt am vorigen, *Neue Kette* für den zweiten Arm. Er setzt das Skelett
      und lässt die Stellung leer — die Winkel sind Zahlen und gehören in den
      Dialog, wo auch ein Projektparameter stehen darf. Das ist keine Lücke,
      sondern die Arbeitsteilung, die Posing hierher gehören lässt. 14 Tests.
- [x] **P16.9 — Dateiformat 7 → 8**, Migration, Einbacken. Der Bruch ist die
      **Auslagerung großer Sammelwerte**: Eine Sculpting-Sitzung mit
      viertausend Zügen steht sonst als eine Zeile im `project.json`, und die
      Datei lässt sich weder ansehen noch ändern, ohne sie ganz neu zu
      schreiben. Ab 200 000 Zeichen wandert der Wert in eine eigene Datei im
      Container — rund zweitausend Züge, die Größenordnung einer großen
      Skizze.

      **Nur beim Speichern und Laden.** Im Arbeitsspeicher ist ein
      Sammelparameter immer sein Text; sonst müsste jede Auswertung, jeder
      Hash und jeder Vergleich wissen, ob der Wert gerade ausgelagert ist. Die
      Nummer kommt aus den vorhandenen Quellen und nicht aus einem Zähler im
      Dokument — ein Zähler wäre ein Zustand, der beim Rückgängigmachen falsch
      wird.

      Die Migration 7 → 8 ist eine Feststellung und keine Umrechnung. Sie
      prüft den einen Fall, in dem eine alte Datei doch etwas dieser Art
      enthalten könnte: einen Parameterwert, der zufällig wie ein Verweis
      aussieht. Er wäre in Version 8 einer, und das wäre eine Umdeutung — also
      hält sie an. `example_v8.p3d` eingecheckt, `example_v7.p3d` öffnet
      weiter.

      **Das Einbacken** (Entscheidung D, von Robert bestätigt) ist ein
      Parameter an `sculpt_strokes` und keine eigene Operation: Ist `baked`
      gesetzt, kommt das Ergebnis aus der Quelle statt aus der Rechnung, und
      die Züge bleiben als Beleg stehen. Reproduzierbar bleibt es — die Quelle
      reist im Container mit wie jede andere, und eine Quelle *ist* ein
      Parameter, sonst wäre auch `load` keine Operation. 18 Tests.

      **Die Nachfrage steht** — im Kontextmenü des Verlaufs, neben „Parameter
      ändern" und nur an einer Sitzung, die noch gerechnet wird. Sie fragt
      nicht nach Sicherheit, sondern sagt, was danach nicht mehr geht und was
      man dafür bekommt. Die einzige Nachfrage im ganzen Programm. **Dabei mitnehmen:
      ein `title_translatable` für Parameter.** Für Transaktionstitel gibt es
      das Feld seit Fassung 6, für Parameter nicht — ihr Titel kommt aus dem
      Code, verliert beim Speichern aber die Herkunft und steht danach als
      nackter deutscher Text in der Datei. Wer ein Beispielprojekt auf
      Spanisch öffnet, liest deshalb „Breite" statt „Ancho".
      `tools/make_figures.py` löst das für die Handbuchbilder selbst auf
      (`translate_parameter_titles`, mit Begründung im Docstring); in der
      Anwendung geht es nicht, solange die Datei nicht sagt, ob ein Titel aus
      dem Code oder aus der Tastatur des Nutzers stammt. Genau diese
      Unterscheidung ist das Feld — die Migration von 6 hält fest, warum ein
      nachträglicher Abgleich mit dem Katalog der falsche Weg wäre.
- [~] **P16.10 — Weg 4, Handbuch, Website, Beispiel, Regelsammlung.** Die
      Sperre steht; offen ist nur noch, ob eine Regel dazukommt.

      **Handbuch:** ein Kapitel *Formen* mit dem Abschnitt, den `AGENTS.md`
      für jedes Werkzeug mit einer echten Grenze verlangt — wann es *nicht*
      das richtige ist. Aus den drei Wegen werden vier, in fünf Sprachen; der
      Wege-Text wurde fortgeschrieben statt ersetzt, damit jede Sprache die
      Übersetzung bleibt, die jemand geprüft hat.

      **Website:** Weg 4 auf beiden Sprachen, mit derselben Einblendung wie
      Weg 3 und im selben Takt — vier Einblendungen zu vier Zeiten wären
      Unruhe statt Auskunft. Bei reduzierter Bewegung steht der Endzustand.

      **Beispielprojekt** `weg4-figur-formen.p3d` mit Tour. Es legt **keine**
      Pinselzüge: Ein Beispiel, das mit viertausend gespeicherten Zügen
      ankommt, zeigt ein Ergebnis und keinen Weg. Es hört dort auf, wo der
      Nutzer den Pinsel nimmt.

      **Nebenbei behoben:** `tools/make_manual.py` lief seit den vier neuen
      Sprachkatalogen nicht mehr — es fragt `available_languages()` und bekommt
      fünf statt zwei, während die Seitentabelle zwei kennt. Es überspringt
      jetzt, wofür es keine Seite gibt, und sagt welche.

      **Der Agent sculptet nicht — und zwar, weil er es nicht kann.** (K)
      Entscheidung K verlangte eine Regel in der Sammlung; der Kopf von
      `rules.toml` sagt selbst, was dann besser ist: „eine eingehaltene Regel
      ist besser als eine beschriebene". Für Skizzen stand das Muster längst,
      seit §30.1 — zweifach gesperrt, im Schema und im Aufruf.

      Am 14.08.2026 nachgesehen: `GATHERED_KINDS` führte alle drei Arten
      (`sketch`, `strokes`, `armature`), aber nur die **erste** Sperre las die
      Menge. Die zweite in `agent/session.py` prüfte `kind == "sketch"`, und
      ein geratener Pinselstrich lief hindurch und wurde gerechnet. Der
      Kommentar darüber behauptete das Gegenteil. Beide Stellen lesen die
      Menge jetzt; die Ablehnung nennt je Art die Stelle, an die der Nutzer
      gehört. Drei Tests, zehn Katalogeinträge.

      **Bleibt als Entscheidung:** ob *zusätzlich* eine Regel in die Sammlung
      soll. Die Sperre verhindert den Schaden, eine Regel verhindert den
      Fehlversuch — ein Modell, das vorher weiß, dass es nicht modelliert,
      erklärt dem Nutzer gleich den Weg, statt es zu probieren und abgewiesen
      zu werden. Sie kostet zwei Suite-Läufe (`AGENTS.md`, Checkliste
      „Regelsammlung ändern"), je rund anderthalb Stunden, und Geld. Der Lauf
      gehört angesagt und nicht nebenbei gestartet.
- [x] **Die Kategorie `organic` entsteht nicht — gemessen statt entschieden.**
      (14.08.2026) Die Frage war, ob die acht neuen Operationen eine eigene
      Kategorie brauchen, damit man sie findet und benutzt. Statt sie nach
      Gefühl umzusortieren, wurde Weg 4 einmal ganz durchgefahren: Kugel
      anlegen, auswählen, *Formen*, zwei Züge, *Fertig*, Undo.

      **Der Weg trägt.** Die Operation entsteht, der Stapel zeigt sie, ein
      Undo nimmt sie zurück. Was nicht trug, war eine ganz andere Stelle: Der
      erste Schritt endet bei „Das Netz ist für diesen Pinsel zu grob", und
      der Satz ließ den Nutzer mit vier Schritten allein. Behoben mit einem
      Knopf, der die Kantenlänge aus dem Pinselradius rechnet — die Zahl, die
      er sonst hätte raten müssen.

      Damit bleibt die Einordnung, wie sie ist: `mesh`, `boolean`, `surface`.
      Sie war nie das Hindernis, und eine neunte Menügruppe hätte den Bauplan
      geändert, um ein Problem zu lösen, das an anderer Stelle lag. Was den
      Einstieg trägt, steht schon: Handbuchkapitel *Formen*, Weg 4 auf der
      Website, das Beispielprojekt mit Tour, die Befehlspalette.

      **Was auffiel und stehen bleibt:** `mesh` führt neun Operationen, davon
      sieben technische (Dezimieren, Neu vernetzen, Aufdicken) und zwei
      kreative (*Formen*, *Stellung geben*). Wer die zwei sucht, sucht sie
      nicht unter „Netz". Das ist eine Umsortierung wert, sobald jemand sie
      **vermisst** — bis dahin ist es eine Vermutung, und die letzte dieser
      Art hat sich beim Nachmessen als falsch erwiesen.
- [x] **P16.11 — Prüfpunkt Käfigmodellierung: Kriterium steht, und vier von
      fünf Bedingungen sind erfüllt.** `tests/test_base_mesh.py` schreibt fest,
      was „brauchbares Basisnetz" heißt, bevor P16.5 beginnt: ein Körper ohne
      Löcher (Euler-Charakteristik zwei), höchstens fünfzehn Schritte,
      Kantenstreuung nach dem gleichmäßigen Vernetzen unter 0,5, und Maße, die
      Zahlen bleiben. Die fünfte — ob der Pinsel von der groben Form zur Figur
      kommt — braucht P16.5 und steht als Einzige noch offen.

      Gemessen an einer humanoiden Grundfigur aus sechs Primitiven und fünf
      Verschmelzungen: **elf Schritte, eine Komponente, Euler zwei,
      Kantenstreuung im Rahmen.** Das ist der Aufbau, den H2 dem Käfig
      entgegenhält, und er trägt. Der Käfigeditor bleibt damit nachgeordnet —
      die Entscheidung fällt endgültig nach P16.6, aber sie fällt jetzt gegen
      ein festgeschriebenes Kriterium und nicht gegen ein Gefühl.

      **Der Prüfpunkt hat sich sofort bezahlt gemacht.** Sein erster Lauf
      meldete fünf Komponenten statt einer, und die Ursache lag in P16.4: Das
      Vorzeichen des Abstandsfeldes kam aus gemittelten Eckpunktnormalen, die
      an der Deckkante eines Zylinders 45 Grad schräg stehen. Ein Rohr war nach
      dem Verschmelzen acht Millimeter länger als vorher — Volumen und
      Wasserdichtheit stimmten, deshalb sahen die Tests von P16.4 es nicht.
      Flächennormalen statt Punktnormalen, plus ein Test, der die Ausdehnung
      misst.

### Die Grenze, die bleibt

Wir gewinnen kein Sculpting-Rennen, und das ist kein Versäumnis. Sechs Pinsel
gegen ZBrushs Hunderte — wer eine Porträtbüste modelliert, nimmt weiter
Blender. Das Rennen, das Solidon läuft, ist ein anderes: Kein
Sculpting-Programm meldet eine Wand unter der Düsenbreite, während man sie
formt, und kein CAD-Programm formt eine Figur. Nach P16 steht beides in einem
Fenster, und die vier Fähigkeiten, die den Unterschied machen —
Wandstärkenkarte, Überhangkarte, Bauraumprüfung, Teilung mit Verstiftung —
existieren alle und bekommen nur ein neues Anwendungsgebiet.

---

## Die Konzepte gegen den Code gehalten (14.08.2026)

Anlass war eine einzige Frage: *Sind alle Konzepte vollständig abgearbeitet und
aktuell?* Siebzehn Dokumente, jede Statusaussage im Code nachgeschlagen. Die
Antwort war zweigeteilt — inhaltlich fast alles durch, aber **fünf Dokumente
beschrieben einen Stand, den der Code überholt hatte.** Alle fünf sind
nachgezogen.

- [x] **Die Demo-Fortschrittstabelle stand auf zehnmal „offen"**, während sechs
      Pakete gebaut waren (`konzept-demo-2026-10.md` §10). Wer den Stand dort
      statt in dieser Datei las, hielt die Demo für unangefangen. Jetzt mit
      Commit je Paket, und D6 und D9 stehen als „halb" da, weil sie es sind:
      dem einen fehlt der Download-Kasten mit Prüfsumme, dem anderen der
      Stichtag in `.claude/rules/kern.md`.
- [x] **Drei Sätze im organischen Konzept sagten „fehlt"**, während ein
      Nachtrag zwanzig Zeilen weiter „erledigt" sagte — Skeletteditor
      (`app/ui/pose_bar.py`, 14 Tests), Einback-Nachfrage (`bake_sculpt`, vier
      Fälle) und die Zeile „P16.6 bis P16.10: keiner begonnen", die aus dem
      Plan stehengeblieben war. Dazu führte die Restliste die Kategorie
      `organic` als offene Entscheidung, die am selben Tag entschieden wurde.
- [x] **Die Live-Durchsicht trug an vier von fünfzehn Befunden einen
      Erledigt-Vermerk**, obwohl alle fünfzehn erledigt sind. Die neun
      fehlenden sind nachgetragen, jeder mit der Stelle im Code — und zwei
      davon sind **anders** gebaut worden als vorgeschlagen: die Passung
      entsteht in `lid_flow.py` statt in den Ops (Regel 3 verbietet der Op die
      Dokumentänderung), und die neue Merkmalsart heißt `pin`, nicht `boss`.
      Genau solche Abweichungen verschwinden, wenn niemand den Vermerk setzt.
- [x] **Zwei B13-Abschnitte im Meshy-Konzept** mit verschiedenem Status, und
      die Schlusstabelle führte den Befund als abgeschlossen, während der
      eigene Nachtrag ihn auf „offen" gestellt hatte. Am Code entschieden:
      `autosplit.py` holt seine Normale weiter aus `AXIS_NORMALS`, die Suche
      kennt drei Achsen — also offen.
- [x] **Die Agent-Vertiefung verlangte in ihrer Reihenfolge-Tabelle ein
      Werkzeug `set_print_setting`**, das §5.1 desselben Dokuments schon am
      08.08. mit Begründung zurückgenommen hatte. Mit dem Werkzeug fiel auch
      seine Abnahme — sie prüfte, was nicht gebaut werden sollte.

**Was die Durchsicht nebenbei fand**, weil sie Zahlen nachzählte statt sie zu
lesen:

- [x] **„Beispiele — die drei Wege und was darauf bereitliegt"** stand als
      Beschriftung über neun Beispielen auf dem Startbildschirm, und es sind
      seit P16 **vier** Wege. Ein sichtbarer Text, den P16.10 übersehen hat;
      fünf Kataloge ziehen nach, die Wortwahl je Sprache aus dem
      Handbuchtitel *Die vier Wege* übernommen, damit die Oberfläche nicht
      zwei Wörter für dieselbe Sache führt. Der Kommentar in `examples.py`
      war dreifach falsch (vier statt fünf darunter, drei statt vier Wege).
- [x] **Die Fassung stand an zwei Orten und kein Test hielt sie zusammen.**
      `test_the_version_is_the_same_in_both_places_that_carry_it` tut es jetzt.
      Aufgefallen beim Heruntersetzen auf 0.1.0 — bis dahin hing die
      Übereinstimmung an Aufmerksamkeit.
- [x] **Die vier Wegekarten auf der Startseite waren textlastig und ihre
      Zeichnungen klein**, und die Ursache war nicht das Layout: Weg 3 trug
      89 Wörter gegen 25 bei Weg 2, und das Raster streckt jede Karte auf die
      Höhe der längsten. Der zweite Absatz von Weg 3 (Meshy, Tripo, Rodin)
      stand ohnehin doppelt — `ki-modelle.html` führt ihn — und ist dort
      gestrichen. Dazu zwei Spalten statt vier: 578 statt 279 px je Karte,
      533 statt 236 px Bildbreite, **233 statt 103 px Bildhöhe**, gerechnet
      aus `.wrap` 76rem, `gap` 1.25rem und dem Seitenverhältnis 320:140 der
      Vignetten. `align-items: start` nimmt den Streckzwang.

- [x] **Nachgemessen — und die Rechnung hatte recht, die Regel nicht**
      (14.08.2026). Chromium und Playwright liegen in dieser Umgebung bereit;
      gemessen wurde über `file://` bei neun Breiten von 1920 bis 360. Die
      Zahlen oben stimmen auf den Punkt: 578 px je Karte, 533 px Bildbreite,
      234 statt der gerechneten 233 px Höhe — der eine Pixel ist Chromiums
      Rundung. `align-items: start` sieht man im Bild: die vier Karten sind
      438 bis 538 px hoch und keine gestreckt.

      **Der Blick hat trotzdem etwas gefunden, das keine Rechnung zeigt.**
      `repeat(auto-fit, minmax(34rem, 1fr))` nimmt Spalten weg, aber es macht
      die *letzte* nicht schmaler als 34rem. Unter 544 px Fensterbreite stand
      also eine Spalte da, die weiter 544 px maß — und weil `html` und `body`
      `overflow-x: clip` tragen, war da auch nichts zu scrollen: Auf einem
      390er Telefon fehlten die rechten 150 px jeder Wegekarte, auf beiden
      Startseiten. `min(34rem, 100%)` um das Mindestmaß behebt es; breite
      Fenster bleiben unverändert bei zwei Spalten, bei 390 px ist die Karte
      350 px breit und vollständig. Nachgemessen und angesehen.

      `test_no_self_arranging_grid_stops_shrinking_above_phone_width` hält die
      Regel fest — nur für `auto-fit` und `auto-fill`, denn nur die versprechen
      mitzugehen; das Spaltenpaar der Kopfzeile steht in einem
      `@media (min-width: 68rem)` und ist eine Entscheidung, kein Versehen.

      Die Handbuchtabellen sahen in derselben Messung zuerst wie ein zweiter
      Fund aus — sie stehen bei 390 px bis zu 725 px breit da. Sie rollen aber
      in sich (`table { display: block; overflow-x: auto }`), und die Probe
      hatte nur die Kinder eines Rollbereichs nicht ausgenommen. Kein Befund.

### Review des Skizzeneditors — drei Funde, alle behoben (14.08.2026)

Ein Durchgang durch den gesamten uncommitteten Stand (40 Dateien, 959 Zeilen
Code). Zwei der Funde hat die parallele Sitzung noch während des Reviews
aufgegriffen; was hier steht, ist der Stand danach.

- [x] **Der Punktdialog rundete, was er nur anzeigen sollte.** `PointDialog`
      bindet seine Felder auf zwei Dezimalstellen — richtig, denn die Anzeige
      tut das überall (§11.2). Falsch war, dass `edit_point` das Ergebnis
      unbesehen zurückschrieb: Ein projizierter Punkt bei 30,125 mm kam als
      30,13 zurück, einer bei 0,001 mm als 0. **Ansehen war eine Änderung**, und
      Regel 6 sagt, dass nur die Anzeige rundet.

      Behoben mit einem Merker am `valueChanged`-Signal, nicht mit einem
      Zahlenvergleich — und das ist der lehrreiche Teil: Der erste Versuch
      verglich gegen die eigene Rundung und scheiterte an genau dem Wert, um den
      es ging. **Qt rundet 30,125 auf 30,13, Python auf 30,12** (round-half-even
      auf einer Zahl, die binär nicht exakt ist). Ein unangetastetes Feld gibt
      jetzt die genaue Lage zurück, ein angetastetes die Ansage des Nutzers.
      Zwei Tests, vier Werte gemessen.
- [x] **Zwei Wege zu einer Geste, und geprüft war der ungenutzte.** Der Griff
      auf einen vorhandenen Punkt stand im Mausereignis *und* in `place`. Das
      Ereignis kam zuerst und reichte Strg weiter, `place` nicht — also nahm die
      Maus einen anderen Weg als die drei Greif-Tests, die alle `place` rufen.
      Jetzt greift `place` allein und bekommt `extend` herein; ein Test hält
      fest, dass Strg dort ankommt.
- [x] **Beim Punktwerkzeug leuchtete nichts auf, obwohl ein Klick greift** —
      und nach der ersten Behebung leuchteten *zwei* Zeichen: der Punkt und die
      Fangmarke daneben, die eine Stelle zeigte, die der Klick nicht nimmt. Die
      Marke weicht jetzt.

      **Dabei fiel eine Doppelbedeutung auf:** `highlighted` trägt zweierlei —
      den Punkt unter dem Zeiger *und* die Punkte der überfahrenen Bedingung in
      der Liste (`highlight_points`). Die Fangmarke daran zu hängen hätte sie
      von der Maus über einer Liste abhängig gemacht. Der Treffer wird deshalb
      einmal je Mausbewegung gesucht und beiden Verbrauchern **als Argument**
      gegeben; `_note_hover` nimmt jetzt den Punkt statt der Position. Das
      spart zugleich den zweiten Durchlauf über alle Punkte.

### Der Absturz im langen Lauf: die Reihenfolge entscheidet (14.08.2026)

Nebenbefund derselben Sitzung, und er räumt eine Erklärung ab. Drei
Vollläufe, alle drei abgebrochen — und **zwei davon an derselben Stelle**:
`test_leaving_the_sketch_mode_empty_starts_no_operation`, im `MainWindow`-Aufbau,
bei 80 und 81 Prozent. Der erste Lauf brach bei 62 Prozent ohne Traceback ab und
sagte damit nichts.

- [x] **„Der Absturz wandert" gilt nicht mehr.** Er hing bisher am Cluster
      „diese Maschine rechnet sporadisch falsch", dessen Spur am selben Tag
      aufgegeben wurde. Zweimal derselbe Test ist keine Wanderung.
- [x] **Es sind zwei Abstürze, nicht einer.** Das ist der Fund, und er
      entstand aus einem eigenen Fehler: Der erste Reproduzierer wurde für den
      Volllauf-Absturz gehalten und ist ein anderer. Beide gemessen:

      | Aufruf | Fehlerbild | Wo |
      |---|---|---|
      | `pytest -q` (dreimal gefahren) | **Stack overflow** bei 80/81/82 % | jedes Mal `test_leaving_the_sketch_mode_empty_starts_no_operation`, im `MainWindow`-Aufbau |
      | `pytest -q --ignore=tests/test_translations.py` | **Stack overflow** bei 82 % | derselbe Test |
      | `pytest tests/test_translations.py tests/test_ui.py` | **Zugriffsverletzung** bei 22 % | `window`-Fixture von `test_ui.py`, in `render_window_interactor.initialize` |
      | `pytest tests/test_ui.py tests/test_translations.py` | 298 passed | — |
      | `pytest tests/test_ui.py` · `tests/test_sketch_editor.py` | 190 · 73 passed | — |

      **Absturz A — der Stapelüberlauf**, der die Vollläufe nimmt: viermal
      gefahren, **dreimal derselbe Test** (der vierte Lauf brach bei 62 % ohne
      Traceback ab und sagt nichts). Die gerissene Zeile wandert innerhalb des
      Fensteraufbaus — `overlay.py:327`, `overlay.py:333`,
      `main_window.py:790` —, und genau das ist das Bild eines Stapels, der
      schon fast voll ankommt: Es reißt, wo die nächste tiefe C-Rekursion
      liegt, nicht dort, wo die Ursache sitzt. `test_sketch_editor.py` allein
      ist grün, also braucht A einen Vorlauf.

      **Absturz B — die Zugriffsverletzung**, in 90 Sekunden reproduzierbar
      und **von A unabhängig**: Wer `test_translations.py` vor die
      fensterbauenden Dateien stellt, tötet einen späteren Aufbau in
      `render_window_interactor.initialize`; umgekehrte Reihenfolge läuft
      durch. Die Absturzstelle ist wörtlich die, die `conftest.py` als Folge
      eines **zerstörten** Fensters beschreibt — nur baut
      `test_translations.py` überhaupt kein Fenster: kein `MainWindow`, kein
      `build_application`, kein `deleteLater`. Es vergiftet, ohne eines
      anzufassen.
- [x] **A und B sind derselbe Fehler, und er ist behoben** (14.08.2026) — die
      Halbierung war die richtige nächste Frage, nur war die Antwort weder
      „die Kataloge" noch „die Importe von `app/ui/`". Siehe den Abschnitt
      *Ein Umgebungsartefakt, das keines war* weiter unten.

## Trennen, wo man hinzeigt — und vier Wörter weniger (14.08.2026)

Eine vollständige Durchsicht mit einer Frage: Wer das Programm zum ersten Mal
öffnet und ein Teil trennen will, kommt der an? Der lange Bericht steht in
`konzept-durchsicht-2026-08-14.md`; hier die Arbeitsliste.

Vorweg das, was die Recherche über solche Programme sagt, weil es die
Reihenfolge bestimmt hat: **Gelobt wird Einfachheit und sonst nichts**
(Tinkercad wird für seine Oberfläche gelobt und für seinen Umfang kritisiert,
Fusion 360 andersherum). **Gefordert wird das Trennen mit Verbindern** — Cut
Tool mit Plug, Dowel und Snap ist in Bambu Studio, OrcaSlicer, Creality Print
und PrusaSlicer Standard, und diskutiert wird dort nur noch die Dübelform.
Solidon hatte drei Wege zu teilen und keinen, der über das Bild ging.

### Gebaut

- [x] **`split_line` — an einer gezeichneten Linie trennen.** Zwei Klicks auf
      das Teil, die Blickrichtung dazu, fertig ist die Ebene. Siebter
      Umschalter in der Werkzeugzeile (`SplitBar`, `Alt+7` — hier stand bis
      zum 19.08.2026 „achter", das ist `paint`), Verbindung vorgewählt,
      eine Transaktion, ein Undo, und je Stift ein Passungspaar (§14). Die
      Kamera steht nicht im Stapel: Die Blickrichtung wird einmal gelesen,
      und was in die Operation geht, sind Zahlen — sonst gäbe dieselbe Datei
      nach einem Schwenk ein anderes Teil (§11.2).
- [x] **Die Verstiftung kann jetzt schiefe Ebenen.** Das war der eigentliche
      Aufwand. `plan_pins` und `add_pins` rechneten mit einem Achsenbuchstaben,
      weil Auto Split nur achsparallele Ebenen legt; auf einer 45-Grad-Fläche
      steht ein so aufgestellter Stift schief in seiner eigenen Bohrung.
      Beide nehmen jetzt eine `SectionPlane`, gedreht wird mit derselben
      Matrix wie der Schnitt, nur invertiert. Drei Sonderfälle für drei Achsen
      sind dabei weggefallen, statt einen vierten zu bekommen — `upright_normal`
      hat die Eigenschaft, die alles trägt: die dritte Koordinate des gedrehten
      Punktes *ist* der Ebenenabstand, ohne Umrechnung.
- [x] **Auf dem Hauptknopf stand „etzt trenne".** Ein Fehler, der das ganze
      Programm betrifft und den man nur im Bild sieht: Das Stylesheet zeichnet
      `QPushButton:default` halbfett, Qt rechnet die bevorzugte Breite aus der
      normalen Schrift. „Jetzt trennen" sind 77 gegen 89 Bildpunkte, der Knopf
      bekam 104 — in einem Dialog fällt das nie auf, in einer engen Leiste
      immer. `style.make_primary()` setzt jetzt beides; alle sieben Hauptknöpfe
      gehen darüber, ein Test misst gegen die Schrift, mit der gezeichnet wird,
      ein zweiter verbietet `setDefault(True)` außerhalb von `style.py`.
- [x] **Vier Wörter, an denen ein Anfänger hängen bleibt.** *Boolesch* →
      **Verbinden und Abziehen**; *Druckvorbereitung* → **Teilen und Anpassen**
      (es stand als Untermenü unter *Vorbereiten*, zwei Ebenen mit fast
      demselben Wort); *Dezimieren* → **Dreiecke verringern**; *Muster* →
      **Kopien in Reihe oder Kreis** (*Textur aufbringen* hat einen Parameter
      „Muster", und der meint Rändel und Wabe). Bezeichner unverändert, fünf
      Kataloge nachgezogen, Handbuch neu erzeugt.
- [x] **„Automatisch teilen …" ist umgezogen**, von *Bearbeiten* nach
      *Vorbereiten*. Es stand dort, weil es technisch kein Registereintrag ist
      — eine Einteilung nach der Bauart der Funktion, nicht danach, wonach
      jemand sucht. Die vier Wege zu trennen stehen jetzt beieinander.

### Offen, mit Grund

Alle fünf sind inzwischen abgearbeitet — siehe den Abschnitt darunter.

## Die offenen Punkte abgearbeitet (14.08.2026)

Die fünf Punkte, die die Durchsicht offen ließ, plus das, was an Handbuch und
Website nur halb nachgezogen war.

- [x] **Ein Passungspaar entstand auch ohne Stifte.** War die Schnittfläche zu
      schmal, setzte `plan_pins` keinen einzigen und sagte das als Befund — das
      Dokument bekam seine `Fit`-Einträge trotzdem, und beide Seiten zeigten
      auf Merkmale, die es nie gab. Die Passungsprüfung meldete danach eine
      Verletzung an einem Teil, das in Ordnung ist.

      Die Zahl der Paare kommt jetzt aus `fitting_pins()` — derselben Planung,
      die die Operation gleich noch einmal macht, und weil sie deterministisch
      ist, stimmen beide Antworten überein. Damit sie das auch für Auto Split
      kann, führt jeder `Step` das Stück mit, das er geteilt hat: Gerechnet
      wird es nicht in `autosplit.py`, denn `pins.py` importiert das Modul —
      der Aufrufer in `split.py` hat beide.
- [x] **Die Hälften heißen jetzt „… A · Stifte" und „… B · Löcher".** Beim
      Export ist der Dateiname die einzige Auskunft darüber, welches der
      beiden Teile man in der Hand hat. Ein vorhandener Zusatz wird ersetzt
      statt ergänzt, sonst steht dort beim zweiten Teilen
      „Halter A · Stifte A · Stifte"; der Buchstabenpfad bleibt, er zeigt den
      Teilungsbaum. Getrennt wird an „ · " — das Zeichen kommt in Nutzernamen
      praktisch nicht vor, also nimmt das Abschneiden keine fremde Klammer mit.
- [x] **`MENU_TWINS` hängt nicht mehr an B-Rep.** Der Haken „Exakter Körper
      (B-Rep)" stand als feste Zeichenkette in der Oberfläche und
      „(Umschalter „Exakt")" im Menüweg; damit taugte die Zusammenlegung für
      nichts als die zwei Rechenkerne. Die Beschriftungen liegen jetzt in
      `TWIN_TOGGLES`, und wer dort fehlt, bekommt keinen Haken — sein
      Umschalter ist ein Wert im Dialog des Partners.

      Damit ist *An Ebene teilen* dorthin gezogen, wo es hingehört: unter
      *Teilen* (vormals *Teilen und verstiften*), mit der Null im Feld
      *Passstifte* als Umschalter. Aus drei „teilen"-Zeilen nebeneinander sind
      zwei geworden.
- [x] **Verbinder haben eine Form.** Rund, Sechskant, Schwalbenschwanz — als
      Querschnitt des `dowel`-Bausteins, also über den Parameterbereichstest
      mitgeprüft. Rund braucht zwei Stück gegen Verdrehen, die kantigen halten
      einzeln; gemessen wird das im Test als das, was von der Bohrung frei
      bliebe, wenn der Stift verdreht steckte. Die Fase bleibt für alle drei
      dieselbe Rechnung, weil sie über den Umkreis arbeitet. Die Wahl steht in
      der Trennleiste neben der Stiftzahl, nicht hinten in einem Dialog: Wer
      einen Schwalbenschwanz will, will ihn, *bevor* er trennt.
- [x] **Die acht Werkzeuge haben Kürzel**, `Alt+1` bis `Alt+8` in der
      Reihenfolge der Leiste. `Alt` und eine Ziffer mit Grund: Ein Kürzel ohne
      Modifikator feuert auch, während jemand in den Chat tippt, und schluckt
      dort den Buchstaben; die Ziffern allein gehören der Darstellung, `Ctrl`
      und Ziffer den Kameras. Das Kürzel steht im Tooltip und in der Palette —
      und es überlebt jetzt auch das Ausgrauen, das den Tooltip gegen den
      Grund tauscht.
- [x] **Handbuch und Website waren nur halb nachgezogen.** Die aus dem
      Register erzeugte Referenz stimmte von selbst; der *geschriebene* Teil
      nicht. Das Handbuch zählte die Werkzeugzeile weiter mit sieben
      Werkzeugen auf und schickte den Leser nach „Bearbeiten → Automatisch
      teilen" und „Ändern → Teilen und verstiften" — beide Wege gibt es so
      nicht mehr. Nachgezogen in allen fünf Sprachen, nicht nur auf Deutsch
      und Englisch: Kapitel 3 (Werkzeugzeile samt Kürzeln), Kapitel 13 und 14
      (das Trennwerkzeug, die Verbinderformen, die Namen der Hälften). Auf der
      Website hieß der Abschnitt *Auto-Split* und kannte nur die Suche; er
      heißt jetzt *Trennen und Auto-Split* und fängt mit den zwei Klicks an.

### Die Entscheidung, die eine Rechnung nicht überlebt hat

- [x] **Der Schnapper ist gebaut** (14.08.2026). Er stand hier als *bewusst
      offen*, mit drei Gründen — und zwei davon halten einer Messung nicht
      stand. Der eine, der hält, ist genau der, der ihn zum eigenen Baustein
      macht und nicht zu einem Wert in `_profile`.

      **Was stimmte:** Ein Schnapper ist kein Querschnitt. Rund, Sechskant und
      Schwalbenschwanz sind dieselbe Rechnung mit einem anderen Vieleck; der
      Schnapper ist ein Paar aus Federarm und Tasche mit Rastkante. Deshalb
      `snap_connector` als eigener Baustein — der vierzehnte, einer mehr als
      die Erstbestückung in §24.1, und das ist eine Ansage.

      **Was nicht stimmte, erstens: „der Hinterschnitt ist eine
      Überhangfläche, über die der Baustein etwas sagen müsste."** Er ist eine
      Brücke von der Breite des Hakenüberstands — bei einem 6-mm-Verbinder
      0,9 mm. Das legt jeder Drucker, und in der anderen Lage (Naht nach
      unten) gibt es überhaupt keinen Überhang. Ich hatte die Lage nicht
      durchgerechnet, sondern das Wort *Hinterschnitt* gelesen.

      **Und zweitens: „eine Federkraft, die ohne Kalibrierung geraten wäre."**
      Sie wird nicht geraten, sie wird gebaut: zehn zu eins ist das Verhältnis
      aus Länge zu Armstärke, das ein Arm zum Federn braucht, und es stand
      längst als `SNAP_RATIO` im Repository — `snap_fit` benutzt es seit der
      Erstbestückung. Der Baustein setzt die Stärke daraus, statt einen Regler
      dafür anzubieten.

      **Was die Rechnung wirklich begrenzt**, war keiner der drei Gründe: Aus
      zehn zu eins und zwei Außenwänden einer 0,4er Düse (0,8 mm) folgt eine
      Mindestlänge von 8 mm, und die Nahtplanung vergibt `1,5 · Ø` — ein
      Schnapper braucht also eine Naht, die mindestens **5,4 mm** hergibt. Ist
      sie schmaler, wird rund daraus **und der Prüfbericht sagt warum**
      (`split.snap_too_small`, Regel 21). Das ist die ehrliche Grenze, und sie
      ist eine Zahl statt einer Meinung.

      Gemessen: 144 Ecken des Parameterbereichs, alle wasserdicht, einteilig
      und innerhalb ihres Umkreises; der Anschlag beim Auseinanderziehen und
      die Durchfahrt des ausgewichenen Arms als Volumen, über vier Größen.

## Der eigene Änderungssatz im Review (14.08.2026)

Drei Commits, 46 Dateien — durchgesehen wie fremder Code, jeder Fund einzeln
behoben und mit einem Test festgenagelt.

**Zuerst ein Fehler an der Methode selbst.** Ich hielt den Diff gegen `main`
und las dabei fremden Code als meinen: `main` (62ba22a) liegt *hinter* meinem
Ausgangspunkt `051fdb6`, der Vergleich zeigte also auch Änderungen der
Nebensitzung. Wer seinen eigenen Satz prüfen will, vergleicht gegen den Stand,
auf dem er aufgesetzt hat — nicht gegen den Zweig, in den er später geht.

- [x] **Die kantigen Verbinder waren größer, als sie sagten.** `hexagon(width)`
      nimmt die Schlüsselweite, `dovetail(width)` die breite Seite — beide
      bekamen den Durchmesser roh durchgereicht. Bei `diameter = 6` maß der
      Sechskant 6,93 Umkreis und der Schwalbenschwanz 8,49; dessen Ecke allein
      nahm 1,24 mm der 1,6 mm Wandreserve, die die Stiftplanung stehen lassen
      wollte. `_profile()` rechnet jetzt um (√3/2 beim Sechskant, 1/√2 beim
      Schwalbenschwanz), und der Docstring sagt in einem Satz, was `diameter`
      ist: immer der Umkreis. Ein Test misst alle drei Formen gegen ihn.
- [x] **`fitting_pins()` sagte etwas anderes, als es tat.** Ohne Netz gab es
      null zurück, während der Docstring die gewünschte Zahl versprach. Null
      heißt hier „keine Passung eintragen" — bei einem Aufruf ohne
      ausgewerteten Körper wäre das stillschweigend die falsche Antwort statt
      einer offenen Frage. Es gibt jetzt `wanted` zurück: Wer kein Netz
      mitgibt, bekommt, was er wollte, und die Operation korrigiert es beim
      Rechnen.
- [x] **Die Begründung der Kürzel stimmte nicht.** Im Kommentar stand, ein
      Kürzel ohne Modifikator würde auch beim Tippen im Chat feuern. Mit
      `QTest.keyClick` gegen ein fokussiertes `QLineEdit` gemessen: tut es
      nicht, Qt gibt die Taste dem Eingabefeld. Der Grund für `Alt+Ziffer`
      bleibt trotzdem — die nackten Ziffern gehören der Darstellung, `Ctrl`
      und Ziffer den Kameras. Der Kommentar sagt das jetzt, und ein neuer Test
      prüft das ganze Fenster auf doppelt vergebene Kürzel statt nur die
      Werkzeugzeile.
- [x] **`half_names()` schnitt fremde Namensteile ab.** Es trennte am letzten
      „ · " und warf den Rest weg — ein Körper namens „Halter · Version 2"
      hieß nach dem Teilen „Halter A · Stifte". Abgeschnitten wird jetzt nur,
      was hinter dem Trenner steht *und* einer der eigenen Zusätze ist:
      „Stifte" und „Löcher", in der Quelle wie in jedem der fünf Kataloge —
      sonst verlöre ein auf Spanisch geteiltes und auf Deutsch weitergeteiltes
      Projekt die Regel. `_own_notes()` liest die Kataloge einmal
      (`lru_cache`), nicht bei jedem Namen.
- [x] **`split_plane` stapelte den Zusatz.** Die Op ohne Stifte baute ihre
      Namen selbst und kam an `half_names()` vorbei; zweimal geteilt stand
      „… A · Stifte A" da. Beide Ops gehen jetzt durch dieselbe Funktion.
- [x] **Kleinkram, der trotzdem in die Irre führt.** Der Docstring von
      `show_split_line` sprach von einem Kreuz an den Enden, gezeichnet wird
      eine Kugel; die Enden hatten keinen `name`, waren also nicht einzeln
      abräumbar; der B-Rep-Umschaltertext stand zweimal wörtlich in
      `TWIN_TOGGLES`; die Menüsuche für *Automatisch teilen* ging über den
      übersetzten Gruppentitel statt über die Kategorie und hätte in jeder
      anderen Sprache danebengegriffen; und ein Kommentar sprach noch von
      „drei anderen Wegen", wo es inzwischen vier sind.

### Was der Volllauf sagt

3357 bestanden, 10 übersprungen, 1 erwartet fehlgeschlagen; die Fensterdateien
Datei für Datei grün. `ruff`, `ruff format` und `mypy` sauber.

**Zwei Dateien brechen in diesem Container ab, beide ohne Zutun dieses
Zweigs** — nachgemessen, nicht angenommen:

* `test_manual.py` stirbt reproduzierbar beim Aufbau der `QApplication` unter
  `offscreen`, und zwar an derselben Stelle auf dem unveränderten `051fdb6`.
  Unter einem echten Bildschirm (`xvfb-run`) laufen alle 46 Prüfungen durch.
* `test_operation_ui.py` bricht unregelmäßig ab, mal beim Leeren der
  Verlaufsliste, mal beim Öffnen eines Dialogs — unter `offscreen` wie unter
  `xvfb`, und auf dem unveränderten Stand mit derselben Häufigkeit: ein
  Abbruch in sechs Läufen hier wie dort. Wo er nicht zuschlägt, sind alle 24
  Prüfungen grün.

> **Nachtrag (14.08.2026, eine Runde später): der erste Punkt war kein
> Umgebungsartefakt, sondern ein Fehler.** `tests/test_manual.py` importiert
> `tools.make_figures`, und dieses Modul setzte beim *Import*
> `QT_QPA_PLATFORM` zurück — danach baute die `QApplication` gegen eine echte
> Plattform, die es hier nicht gibt. Behoben, siehe den Abschnitt *Ein
> Umgebungsartefakt, das keines war* unten; die Datei läuft jetzt auch
> offscreen. „Auf dem unveränderten Stand genauso" war richtig gemessen und
> hat trotzdem zur falschen Schlussfolgerung geführt: Ein Fehler, der älter
> ist als der eigene Zweig, ist deswegen kein Fehler der Umgebung.
>
> Der zweite Punkt bleibt bestehen und ist ein eigener, dritter Absturz.

## Ein Umgebungsartefakt, das keines war (14.08.2026)

Die beiden Abstürze, die dieses Repository als **A** und **B** führte, sind
ein einziger Fehler, und er stand in einer Zeile.

```python
# tools/make_manual.py, ganz oben, seit jeher
os.environ.pop("QT_QPA_PLATFORM", None)
```

Die Zeile ist richtig: Das Werkzeug braucht eine echte Plattform, unter
`offscreen` hat Qt auf dieser Maschine null Schriftfamilien. Falsch war nur,
**wann** sie läuft — beim Import, und damit auch bei jedem, der das Modul nur
lesen will. `tests/test_translations.py` führt es aus, um `page_for()` zu
prüfen. Ab diesem Test galt für den *ganzen Prozess* keine
Offscreen-Plattform mehr:

```
vorher: QT_QPA_PLATFORM = offscreen → viewport._available() False
danach: QT_QPA_PLATFORM = None      → viewport._available() True
```

Und `_available()` entscheidet, ob ein `Viewport` einen echten
`QtInteractor` baut. Der Docstring dieser Funktion sagt seit Langem, was
dann passiert: „auf der Offscreen-Qt-Plattform scheiterte es nicht höflich,
sondern nähme den Prozess mit."

**Damit erklären sich beide Bilder und ihre scheinbare Wanderung.** Was
starb, war jeweils die *nächste* Datei, die ein Fenster baut — und welche das
ist, entscheidet `pytest-randomly` mit seiner Dateireihenfolge. Lief
`test_translations.py` vor `test_ui.py`, riss es dort; lief sie vor
`test_sketch_editor.py`, riss es da. Gemessen, jeweils vorher und nachher:

| Aufruf | vorher | nachher |
|---|---|---|
| `test_translations.py` + `test_ui.py` | Zugriffsverletzung bei 22 % | **300 passed** |
| `test_translations.py` + `test_sketch_editor.py` | Abbruch beim ersten Fenster | **195 passed** |
| `test_manual.py` allein, offscreen | reproduzierbar tot im `QApplication`-Aufbau | **46 passed**, dreimal |

Der dritte Fall ist der, den ich eine Runde vorher als Umgebungsartefakt
abgelegt hatte. `tests/test_manual.py` importiert `tools.make_figures` — ganz
gewöhnlich, in Zeile 37 —, und dasselbe Pop stand auch dort. Die Messung
„auf dem unveränderten Stand genauso" war richtig; der Schluss daraus war
falsch. **Ein Fehler, der älter ist als der eigene Zweig, ist deswegen kein
Fehler der Umgebung.**

### Behoben an beiden Enden

- [x] **Die vier Werkzeuge setzen die Plattform in `main()` zurück, nicht beim
      Import** — `make_manual.py`, `make_figures.py`, `make_video.py`,
      `run_ui_audit.py`. Wer sie startet, hat die Variable ohnehin nicht
      gesetzt; wer sie importiert, bekommt keinen Prozess mehr umgebaut.
- [x] **Und der Test gibt die Umgebung von sich aus zurück.**
      `test_the_manual_finds_a_place_for_a_new_language` führt fremden
      Modulcode aus; ein `monkeypatch.setenv` davor stellt sicher, dass pytest
      hinterher aufräumt — auch wenn das nächste Werkzeug wieder so eine Zeile
      mitbringt. Zwei Ebenen, weil eine davon eine Verabredung ist und die
      andere ein Mechanismus.

### Offen: ein dritter Absturz, und er ist ein anderer

- [ ] **`test_operation_ui.py` bricht weiter ab, etwa einmal in acht Läufen.**
      Mit A und B hat er nichts zu tun: Er tritt auch dann auf, wenn die
      Plattform steht, unter `offscreen` wie unter `xvfb`, und er trat auf dem
      unveränderten Ausgangsstand in derselben Häufigkeit auf (ein Abbruch in
      sechs Läufen dort, einer in acht hier).

      **Was gemessen ist.** Die Stelle ist in beiden eingefangenen Fällen
      dieselbe: `panels.py:890`, das `self.list.clear()` in `show_document`,
      erreicht aus `session.wait_for_idle` → `processEvents` → `_on_finished`
      → `_show_scene`. Und die Meldung darunter ist nicht Qt, sondern glibc:
      **`free(): invalid pointer`**. Das ist ein doppeltes Freigeben, keine
      verletzte Qt-Zusicherung.

      **Was ausgeschlossen ist.** Nicht der Speicherbereiniger — die
      naheliegende PySide6-Falle, dass er ein C++-Objekt abräumt, während Qt
      noch darauf steht. Mit `gc.disable()` fielen 5 von 24 Läufen, ohne ihn
      1 von 8: dieselbe Größenordnung. Das spart dem Nächsten den Versuch.

      > **Nachtrag vom 18.08.2026: ein zweiter Stapelabzug, und er zeigt
      > woandershin.** Beim Fahren der Suite in eine *Datei* statt durch `tail`
      > blieb erstmals der Kopf des Abzugs erhalten — die früheren Läufe hatten
      > ihn verschluckt. Was darin steht, ist nicht `panels.py:890` und nicht
      > glibc, sondern:
      >
      > ```
      > tests/test_chat_ui.py:340  test_the_applied_bar_does_not_survive_a_new_project
      >   session.start_new -> _reset_for -> evaluate_async
      >     -> _EvaluationWorker.__init__      Windows fatal exception: access violation
      > ```
      >
      > Ob das derselbe Fehler in anderer Gestalt ist oder ein vierter, ist
      > **nicht** entschieden — die Stelle ist eine andere, die Meldung auch.
      > Festgehalten ist er, weil ein Absturz mit Ort mehr wert ist als drei
      > ohne.
      >
      > Daraufhin geändert, und zwar unabhängig davon richtig: Die Sitzung
      > hielt ihre ausgelaufenen Arbeiter in je einem Feld, während Fenster und
      > Dialoge längst die gemeinsame Halteleine benutzen. Ein Feld hält genau
      > einen — und `_on_thread_done` startet bei `_rerun_pending` sofort den
      > nächsten Lauf. Genau diese Kette steht oben im Abzug. `Session` hängt
      > jetzt ebenfalls an `WorkerLeash`.
      >
      > **Behoben ist der Absturz damit nicht — inzwischen ist das gemessen und
      > keine Vermutung mehr.** Ein späterer Volllauf brachte ihn wieder, und
      > der zweite Abzug ist aufschlussreicher als der erste: **dieselbe
      > Stelle, anderer Weg.**
      >
      > ```
      > session.py:110  _EvaluationWorker.__init__     access violation
      >   evaluate_async <- apply <- import_payload <- import_model
      > ```
      >
      > Beim ersten Mal führte der Weg über `start_new` -> `_reset_for`, jetzt
      > über das Einlesen eines Modells. Was beide teilen, ist der Ort: das
      > Erzeugen des Arbeiters. Und ein Zugriffsfehler bei einer schlichten
      > Attributzuweisung im Konstruktor deutet nicht auf diese Zeile, sondern
      > auf einen Heap, der vorher schon beschädigt war — dieselbe Signatur wie
      > das `free(): invalid pointer` oben. Das stützt die These, dass A und
      > dieser hier **ein** Fehler sind, der an zwei Stellen auffällt, und es
      > bestätigt den nächsten Schritt: ein Werkzeug, das sagt, wer doppelt
      > freigibt. Die Halteleine war trotzdem richtig — sie ist das Muster, das
      > die Gebietsregel verlangt —, sie ist nur nicht die Ursache.
      >
      > **Ein dritter Abzug, und er schließt den Kreis.** Der nächste Lauf fiel
      > an einer dritten Stelle:
      >
      > ```
      > app/ui/command_palette.py:61  _refilter        access violation
      >   tests/test_theme_and_palette.py:250  test_typing_narrows_the_list…
      > ```
      >
      > Zeile 61 ist `self.list.clear()`. **Das ist dieselbe Operation wie in
      > Fall A** (`panels.py:890`, ebenfalls ein `self.list.clear()`), nur in
      > einem anderen Widget. Damit stehen drei Abzüge nebeneinander, und zwei
      > davon fallen auf denselben Aufruf: Eine `QListWidget` zu leeren gibt
      > viele Kindobjekte auf einmal frei, und genau dort schlägt ein Heap zu,
      > der vorher beschädigt wurde. Der dritte (Erzeugen eines `QThread`) ist
      > die Kehrseite — dort wird angefordert, was anderswo doppelt freigegeben
      > wurde.
      >
      > **Wonach also zu suchen ist**, wenn der Punkt drankommt: nicht nach dem
      > Ort des Absturzes, sondern nach dem, der ein Qt-Objekt zweimal
      > freigibt. Die Abzüge sind Symptome an mehreren Stellen, nicht mehrere
      > Fehler.
      >
      > **Und er ist häufig geworden.** In dieser Sitzung lief die Suite
      > achtmal grün (4037 bis 4193 Tests); danach fiel sie viermal in Folge,
      > an vier Stellen — `command_palette.py:61` und `panels.py:1144` und
      > `panels.py:890` (alle drei beim Leeren einer Liste) sowie
      > `session.py:110` beim Erzeugen des Arbeiters.
      >
      > Der naheliegende Verdacht war die Befehlspalette, die seit dem 18.08.
      > sechzig statt dreiundzwanzig Fensterbefehle führt und damit je
      > Tastendruck fast dreimal so viele Listeneinträge erzeugt und wieder
      > wegräumt. **Ein A/B-Lauf hat ihn widerlegt**: Mit beiseitegelegter
      > Änderung fällt die Suite an derselben Stelle
      > (`_EvaluationWorker.__init__`). Die Palette ist unschuldig; sie ist
      > wieder drin, und der Verdacht steht hier, damit ihn niemand ein zweites
      > Mal prüft.
      >
      > Was die Häufung verursacht, ist damit offen. Der Zeitraum fällt mit dem
      > Zusammenführen von 65 Commits zusammen — das ist der nächste Ort zum
      > Suchen, aber ausdrücklich eine Vermutung und keine Messung.

**Was am 18.08.2026 dazu gemessen wurde, und was daraus folgt**

- [x] **Der Ort des Absturzes ist zufällig — er kumuliert.** Vier Läufe fielen
      nach 228, 480, 3698 und 3907 Tests. Vier verschiedene Stellen, drei
      davon beim Leeren einer `QListWidget`, eine beim Erzeugen eines
      `QThread`. Damit ist die Suche nach dem *einen schuldigen Test*
      erledigt: Es gibt ihn nicht, und jede Bisektion über Tests läuft ins
      Leere. Gesucht wird, wer ein Qt-Objekt doppelt freigibt; der Absturz
      fällt später und woanders — bevorzugt dort, wo viel auf einmal
      freigegeben oder neu angefordert wird.
- [x] **Je Datei ein Prozess, und er ist weg.** 130 Testdateien einzeln
      gefahren: 4164 Tests, **kein einziger Absturz**, in zwölf statt siebzehn
      Minuten. Das ist der Beleg für „kumuliert" und zugleich eine benutzbare
      Suite, solange der Punkt offen ist — `tools/run_suite_isolated.py`. Auf
      POSIX täte `pytest --forked` dasselbe je Test; unter Windows gibt es das
      nicht.
- [ ] **Er tritt auch in einer einzelnen Datei auf, und die Rate schwankt
      stark.** `test_split_tool.py` allein fiel einmal in fünf Läufen — und
      danach nicht mehr in acht. Die naheliegende Zuordnung zu einem einzelnen
      Test (`…_pressing_split_makes_two_parts`) ist damit **nicht** belegt:
      Acht Läufe ohne ihn waren sauber, acht Läufe mit ihm aber auch. Wer hier
      weitermacht, braucht viele Läufe je Messpunkt — bei einer Rate um zwanzig
      Prozent sagt ein einzelner Lauf nichts, und genau daran ist in dieser
      Sitzung schon ein A/B-Schluss gescheitert.

      **Nächster Schritt**, wenn er drankommt: ein Lauf unter Valgrind oder
      gegen ein Python mit Adress-Sanitizer, gezielt auf
      `test_every_operation_of_the_history_can_be_opened`. Vorher zu raten
      lohnt nicht — das Bild sagt „jemand gibt zweimal frei", und wer, sagt
      nur ein Werkzeug, das die erste Freigabe mitschreibt.

      **Messpunkt vom 19.08.2026, `test_ui.py`.** Zwei isolierte Suite-Läufe
      hintereinander meldeten dieselbe Datei, und der Lauf davor war grün
      gewesen — das sah nach einer frischen Ursache aus, den Pose-Winkeln.
      War es nicht: Zwölf Läufe **im Wechsel** (HEAD gegen den Arbeitsstand,
      abwechselnd statt hintereinander, sonst misst man die Maschine mit)
      geben **1/6 gegen 1/6**. Kein Unterschied, und die Rate liegt genau in
      dem Band, das dieser Eintrag seit dem 14.08. nennt.

      Das ist derselbe Fehlschluss wie damals, nur von der anderen Seite: Dort
      führte ein einzelner roter Lauf auf einen unschuldigen Test, hier ein
      einzelner grüner auf eine unschuldige Änderung. Ein grüner Lauf bei
      zwanzig Prozent Rate ist erwartbar und beweist nichts — er fühlt sich nur
      an wie ein Beleg.

## Alles Offene abgearbeitet (14.08.2026)

Vier Punkte standen offen, drei davon länger als diese Sitzung. Alle vier sind
zu, und drei haben unterwegs etwas gefunden, das nicht auf der Liste stand.

- [x] **Die Wegekarten am Browser nachgemessen** — und dabei einen Fehler
      gefunden, den keine Rechnung zeigt: Unter 544 px Fensterbreite standen
      die Karten weiter 544 px breit da und wurden abgeschnitten. Der
      ausführliche Eintrag steht oben bei der Durchsicht, in der die Zahlen
      entstanden sind.
- [x] **Drei Namen für benachbarte Dinge** — zwei davon waren *derselbe
      Dialog*. Er heißt jetzt überall *Chat einrichten*: auf dem
      Erstlaufbildschirm, im Menü, im Fenstertitel, im Handbuch und in der
      README. Der dritte bleibt *Fernsteuerung*, weil die Zeile darunter und
      das Handbuchkapitel so heißen; geändert ist, was fehlte — „über MCP"
      nannte das Protokoll, jetzt steht dort *durch andere Programme*.
- [x] **Absturz A und B** — ein Fehler, eine Zeile, siehe oben.
- [x] **Der Schnapper** — gebaut, nachdem zwei meiner drei Ablehnungsgründe
      einer Messung nicht standhielten.

### Was die Suite dabei gefunden hat

Der neue Baustein hat sechs Prüfungen rot gemacht, und jede einzelne war
berechtigt — das ist der Teil, der ohne Suite still danebengegangen wäre:

* Der Baustein erzeugt eine Operation (`insert_snap_connector`), und die
  braucht einen Testaufruf.
* Die Startseiten führen die Zahl der Operationen und der Bausteine; beide
  standen auf dem alten Stand, in beiden Sprachen. Die Pressemitteilung auch.
* Der Registerkopf der ROADMAP führt jeden offenen Punkt — drei fielen weg,
  einer kam dazu.
* Und einer war ein echter Fund an einer ganz anderen Stelle: Der Katalogtest
  suchte nach „zzz-gibt-es-nicht" und erwartete null Treffer. `PARTS.search`
  zerlegt aber an jedem Nicht-Wortzeichen, aus dem Bindestrich wurden vier
  Wörter — und weil der neue Baustein einen Satz mit „gibt es" bekam, fand die
  angeblich leere Suche ihn. Die Anfrage heißt jetzt „qwertzuiopasdfgh": ein
  Buchstabensalat ohne Trennzeichen kann das nicht passieren.

**Volllauf danach:** 3374 bestanden, 10 übersprungen, 1 erwartet
fehlgeschlagen; jede Fensterdatei einzeln grün, `test_manual.py` zum ersten Mal
seit Langem auch offscreen. `ruff`, `ruff format` und `mypy` sauber.

## Drei Funde aus der Slicer-Übergabe (15.08.2026)

Drei Punkte aus der Praxis, alle drei über die laufende Oberfläche
nachgefahren — echte Qt-Plattform, echtes Hauptfenster, echter ElegooSlicer.

### Der Drucker, den es nicht gibt, hielt die Anwendung an

- [x] **Wer die Druckeinstellungen öffnete, ohne einen Drucker eingestellt zu
      haben, sah die Anwendung stehen.** Minutenlang, ohne Anzeige, ohne
      Ausweg. Der Auslöser ist kein Sonderfall, sondern die Vorgabe: Solidon
      startet mit dem „Allgemeinen FDM-Drucker 220 mm", und dazu hat kein
      Slicer ein Profil.

      Die Kette: `match()` findet nichts, `_fill_filaments` bekommt
      `machine=None`, und `match_filament` schlägt dann statt der verträglichen
      Profile **den ganzen Bestand** auf — jedes mit einer Erbkette aus
      Dateien. Gemessen am installierten ElegooSlicer:

      | | Filamente | Dauer |
      |---|---|---|
      | mit erkanntem Drucker | 42 | 0,97 s |
      | ohne | **5962** | nach zehn Minuten noch nicht durch |

      Der Kommentar an der Stelle warnt wörtlich davor („sonst kostete es
      Sekunden statt Zehntel"). Die Vorsicht hängt nur an der
      Verträglichkeitsprüfung, und die gibt es ohne Drucker nicht.

      **Wirkungslos war die Suche obendrein**: Ihr Treffer wird danach mit
      `findData` in einer Liste gesucht, die leer ist. Behoben auf beiden
      Ebenen — im Kern gibt `match_filament` ohne Drucker nichts zurück, in der
      Oberfläche wird nichts vorgewählt, wo nichts zu wählen ist.

      Eingekreist wurde er, indem der Ablauf gegen den unveränderten Stand
      gefahren wurde: Beide starben identisch, also lag es nicht am eigenen
      Änderungssatz. **Vollbild war es nicht** — er tritt in jedem
      Fenstermodus auf.

### Die Übergabe nahm nur Platte 1

- [x] **Der Export konnte alle Platten, die Übergabe eine.** Sie schrieb die
      Baugruppe von `plates[0]`, sagte „geslicet wird die erste" und hörte auf;
      der Satz stand eine Zeile über dem Fortschrittsbalken und wurde von ihm
      gleich wieder ersetzt.

      Eine Platte ist jetzt ein Lauf: eigene Baugruppe, eigene Materialslots,
      eigene Anordnungsprüfung, eigene Druckdatei. Das gilt für alle drei
      Slicer-Familien — die Orca-Familie könnte mehrere Platten in einer
      Projektdatei führen, Cura und PrusaSlicer nicht, und ein Weg, der überall
      gleich läuft, ist mehr wert als einer, der bei zweien anders aussieht.

      Zeit und Material addieren sich (`gcode.combine`), die Schichtzahl nicht:
      über zwei Platten summiert wäre sie eine Zahl, die es nirgends gibt.
      Fehlt ein Wert bei einer Platte, fehlt die Summe.

      **Über die Oberfläche nachgefahren**, sechs Teile auf zwei Platten:

      ```
      [ 0.3 s] Der Slicer rechnet — Platte 1 von 2 …
      [ 1.3 s] Der Slicer rechnet — Platte 2 von 2 …
      [ 2.0 s] Druckzeit: 512 min · Material: 235.9 g · Platten: 2
        Platte 1: solidon-1.gcode — 340 min, 156,9 g
        Platte 2: solidon-2.gcode — 172 min,  78,9 g
      ```

### Der Verbinder sitzt im Füllmuster

- [x] **Die Stiftplanung rechnet in Geometrie, gedruckt wird ein Ring mit
      Muster darin.** Am Querschnitt gemessen, so wie man es am geschnittenen
      Teil nachmisst — ein Zapfen mit Ø 5,04 mm aus `split_pinned`:

      | Wände | Material | Füllkern |
      |---|---|---|
      | 2 | 1,68 mm | **3,36 mm** |
      | 3 (Vorgabe) | 2,52 mm | 2,52 mm |

      Bei zwei Wänden ist mehr Muster als Material, und genau dort sitzt die
      Verbindung; ein Gyroid mit fünfzehn Prozent trifft diesen Kern womöglich
      gar nicht. Bei drei hält es sich die Waage, und dann sagt Solidon nichts —
      die Vorgabe ist in Ordnung.

      `advise._from_connectors` schlägt die Wandzahl vor, nicht die Füllung:
      Wände liegen deterministisch um den Zapfen, Füllung trifft ihn
      statistisch. **Nicht bis vollmassiv** — der Vorschlag bringt ihn genau
      auf die Schwelle, ab der das Material mindestens so breit ist wie sein
      Kern. Bis zum vollen Querschnitt wären es bei einem 8-mm-Zapfen zehn
      Wände auf dem ganzen Teil, und ein Vorschlag, den niemand annimmt, macht
      die vier daneben unglaubwürdig.

### Druckzeit und Materialbedarf des Videoprojekts

- [x] **Gemessen statt geschätzt.** Im Videotext stand keine Zahl, weil keine
      gemessen war. `gehaeuse-mit-bausteinen.p3d` einmal ganz durch die
      Übergabe, auf Elegoo Centauri Carbon 2 mit Elegoo PETG und dem Profil
      „0.20mm Standard @Elegoo CC2 0.4 nozzle":

      | `breite` | Druckzeit | Material | Schichten |
      |---|---|---|---|
      | 70 mm | **52 min** | **17,6 g** | 40 |
      | 96 mm | 64 min | 22,6 g | 40 |

      Der Zuschauer sieht den kleinen Stand, also steht der kleine Wert im
      Intro — in beiden Sprachen. Wer am Projekt oder am Profil dreht, misst
      neu, statt die Zahl anzupassen.

**Nebenbei:** Die Anwendung startet bildschirmfüllend statt auf 1280 auf 820 —
`showMaximized()` und nicht Vollbild, damit Titelleiste und Menüs bleiben.

## Die große Durchsicht vom 16.08.2026 — Code, Oberfläche, Wettbewerb

Sechs Durchgänge über den ganzen Stand: drei Code-Reviews über den Kern,
Oberfläche, Bedienlogik der vier Hauptwege, Wettbewerbsrecherche. Alle Funde
mit Stelle, Beleg und Fix-Skizze stehen in
`.claude/durchsicht-2026-08-16.md` — hier nur, was daraus zu tun ist.

Vorab die Baseline: Umgebung auf `constraints.txt` gebracht (trimesh
4.12 → 5.0.0; der Major-Sprung ist nachweislich folgenlos, in beiden
Kern-Gebieten gegen die installierte Fassung aufgelöst), Suite portionsweise
**4009 Tests grün**, ruff/format/mypy grün. Der Lauf am Stück stirbt weiter
am nativen rtree-Abriss — Umgebung, nicht Code.

**Das Muster der Durchsicht:** Fünf der sieben Stopper sind grün getestet und
trotzdem falsch — die Suite kennt jeweils die Form nicht, in der der Fehler
auftritt (kein Test dividiert *durch* einen Parameter, keiner prüft die
`*_settings_id`-Inhalte, keiner den Slicer-Timeout, keiner die Slot-Filamente
am echten Eingang, keiner Weg 4 am laufenden Programm). **P16 hat nie eine
Live-Abnahme bekommen**, wie sie P15 und die August-Durchsicht hatten.

- [x] **K1 — Division durch einen Parameterverweis ist unmöglich** (§13).
      `expressions.check/references` parsen mit Platzhalter-Nullen, der
      Divisionsschutz lehnt `=@width/@count` überall ab; `sketch/serialize`
      frisst den Fehler still und rechnet mit altem Cache. Fix + Test zuerst.

      **Behoben:** Der Prüfmodus toleriert eine Null im Nenner genau dann,
      wenn der Nenner eine Referenz enthält — ein Zähler je Vorkommen, weil
      das deduplizierende Set als Vorher-nachher-Marke nicht taugt. Die
      Literal-Null (`/0`, `/(2-2)`) bleibt auch in der Prüfung ein Fehler,
      und die Auswertung mit echten Werten wirft unverändert. Vier neue
      Tests, darunter der Skizzenfall `=@d/@n`, dessen Referenzen jetzt in
      den Cache-Schlüssel kommen.
- [x] **K2 — OpenSCAD-Quelltextprüfung umgehbar** (Regel 11, §32).
      `import_stl`/`import_dxf`/`file=` gehen am Muster vorbei; gegen das
      installierte OpenSCAD belegt, die Datei wird gelesen. Vor jeder
      Auslieferung.

      **Behoben:** Beide Muster kennen jetzt die fünf veralteten
      Einbindungen und jedes `file=`; die Literal-Suche merkt sich Spannen
      statt Startpositionen, damit das `file=` innerhalb eines gelesenen
      `import(file="…")` nicht als zweite, ungelesene Anweisung gilt.
      Relative Altformen bleiben erlaubt (gleiche Regel wie `import`),
      `file=` mit Ausdruck statt Literal ist nicht prüfbar und wird
      abgelehnt. Zehn neue Testfälle.
- [x] **K3 — Slot-Filamente erreichen die Übergabe nie**: der Dialog sammelt
      `slot_profiles` ein und meldet Vollzug, `MaterialSlot.material` setzt
      niemand — alle Slots slicen mit dem Basisfilament.

      **Behoben:** `handover.with_slot_profiles` heftet die Wahl positionsweise
      an die Slots (die Position ist die Extruderbelegung), `_plate_run` ruft
      es — `write_config` war auf `MaterialSlot.material` längst vorbereitet.
      Der Dialogtest prüft jetzt den Eingang, nicht nur die Fähigkeit.
- [x] **K4 — die exportierte 3MF trägt absolute Pfade als Profil-IDs**
      (Regel 12; Orca erwartet Namen und trifft kein Preset).

      **Behoben:** `project_settings` schreibt Namen — das Maschinenprofil
      über `_profile_name` (beschnitten wird nur, was wie eine Profildatei
      endet; `.stem` auf „0.12mm Fine @…" schnitte mitten ins Maß), Prozess
      und Filament tragen den Solidon-Namen, unter dem `write_config` sie
      wirklich schreibt. Zwei Tests halten die IDs fest.
- [x] **K5 — Slicer-Lauf: Timeout tötet den Dialog, Schließen friert ein,
      Abbrechen fehlt** (§2.8, Regel 17; `reject()` umgeht `closeEvent`).

      **Behoben:** `_run_slicer` ersetzt das blinde `subprocess.run` —
      Zeitgrenze und Startfehler sind `ExternalToolError` mit Vorschlägen,
      und ein `CancelSignal` beendet den Kindprozess (erst höflich, dann
      endgültig). Der Dialog hat ein Abbrechen neben dem Balken, der bei
      mehreren Platten bestimmt zählt; `reject()` und `closeEvent` gehen
      beide durch `_settle`, das den Lauf abbricht statt ihn auszusitzen —
      das Warten bleibt als Absturzschutz, ist nach dem Kill aber kurz.
      Drei Tests, darunter der Zwilling zum OpenSCAD-Timeout.
- [x] **K6 — Cura scheitert am eigenen Türsteher**: der Dialog verlangt ein
      Maschinenprofil, das es bei Cura strukturell nicht gibt, obwohl der
      Kern die Maschine selbst beschreibt.

      **Behoben:** Der Türsteher gilt nur noch der Orca-Familie; Cura wird
      wie Prusa gar nicht erst durchsucht und sagt ehrlich, dass Solidon
      die Maschine selbst beschreibt (`_machine_keys`, `_cura_base`).
- [x] **K7 — Weg 4 ist gebaut, aber nicht benutzbar**: `finish_armature`
      schickt eine leere Pose (nichts passiert, ohne Ansage); eine getippte
      Pose tötet über ungeschütztes `json.loads` den Auswertungs-Thread und
      die Sitzung meldet Erfolg; „Relief auflegen" bietet kein Bild an (kein
      Bildformat führt in die Quellen); der Startbildschirm-Import lädt ins
      Unsichtbare — und genau darauf zeigt der Schlussknopf der
      Erstinbetriebnahme.

      **Behoben, vierteilig:** (1) Die beiden Sammelparameter-Leser in
      `pose.py` werfen bei fremder Eingabe eine `ValidationError` mit der
      erwarteten Form, und `evaluate` wandelt jede fremde Ausnahme unterhalb
      einer Op in einen `InternalError`-Befund, statt den Thread sterben zu
      lassen — die nächste ungeschützte `json.loads` wäre sonst derselbe
      Fund noch einmal. (2) „Fertig" im Skeletteditor gibt an
      `run_operation` ab, wie es die Skizze vormacht: der Dialog öffnet mit
      gesetztem Skelett. (3) Neuer Parameter- und Quellentyp `image`:
      `displace_image` listet nur Bildquellen, der Dialog bekommt „Bild
      wählen …" (`ImageSourceField`), `session.import_image` bettet ohne
      load-Operation ein, und ein auf das Fenster gezogenes Bild öffnet den
      Relief-Dialog auf dem gewählten Körper. (4) `action_import` legt vom
      Startbildschirm aus ein frisches Projekt an und fängt Fehler; der
      Wechsel in den Arbeitsbereich hängt jetzt am Dokument selbst
      (`_on_project`), damit die vergessene achte Stelle unmöglich wird.
      Offen bleibt das `ArmatureField` (Reihenfolge Punkt 12).
- [x] **Nebensitzung 3MF-Export**: Urteil *nachbessern* — ohne geöffneten
      Dialog ist `print_settings` weiter `None` (A1), der Einzelkörper-Export
      läuft am neuen Code vorbei (A2); Details und A3–A7 in der
      Durchsichts-Datei.

      **Nachgebessert und übernommen:** Jedes 3MF geht über `write_assembly`
      (auch ein Körper — der Plan-Weg kennt keine Einstellungen), `None`
      fällt auf `print_settings.resolve` zurück, `remembered_setup` löst je
      Material auf wie der Dialog selbst, und die Slicer-Suche läuft hinter
      dem Wartezeiger. Der Zip-Test deckt jetzt auch den Normalfall: ein
      Körper, Dialog nie geöffnet. Offen bleiben A5 (Profil erst beim
      Slicen gemerkt, nicht beim Schließen) und A6 (kein Abgleich des
      gemerkten Profils mit dem Drucker des Projekts) — beide gering, beide
      im Gering-Block.
- [x] **Mittel-Block Kern**: Platten-Cache verliert
      `findings`/`solver`/`transform`; T-Vernähen quadratisch und doppelt;
      Rückfallkette unabbrechbar; `FIT_TOLERANCE` widerspricht §14;
      `nut_trap`/`printed_thread` mit Konstanten-Toleranz (Kalibrierung
      erreicht sie nie); **eigene Bausteine werden nie geladen** (§24.5 ohne
      Aufrufer); Lizenzprüfung deckt `agent,brep` nicht; beschädigte
      Nutzer-TOML stürzt beim Start ab; Schlüsselwerkzeug erzeugt bei zwei
      Vorratsläufen identische Schlüssel; Zipbomben-Lücke beim 3MF;
      Einheitenantwort landet nicht in den Op-Parametern (§15.1);
      Nullmessung gilt als Übereinstimmung; Baumstützen erreichen Cura nie.

      **Alles behoben und einzeln committet** — mit zwei Vermerken:
      `FIT_TOLERANCE` ist jetzt im Code begründet (Tessellationsrauschen
      ±0,025 mm; mit `EPS_GEOM` wäre jede Passung auf einem exakten Körper
      „verletzt"), aber **§14 ist mit Ansage nachzuziehen** — Robert
      entscheidet. Und die **Einheitenantwort** bleibt offen: die saubere
      Lösung ist eine Entscheidung zwischen „vorab fragen wie die CLI"
      (kostet `read_mesh` doppelt, im Hauptthread) und
      „`history.change_params` nach der Antwort" (kostet eine eigene
      Undo-Stufe: das erste Undo stellte die Frage erneut) — ebenfalls
      Roberts Entscheidung.
- [x] **Mittel-Block Oberfläche**: Arbeiter-Halteleine in fünf Dialogen
      fehlt (Hauptfenster macht es vor — in ein Modul heben); Export rechnet
      im Hauptthread; Sculpting kennt kein Ziehen (20 Züge = 20 Klicks);
      während Gestensitzungen bleiben alle Ops anklickbar und *Fertig*
      verliert dann die Züge; die Befehlspalette umgeht die Gestenmodi und
      kennt keine Verfügbarkeit; Differenzlegende einfarbig; Fenstergeometrie
      wird nie gespeichert.

      **Fast durch:** Halteleine lebt in `app/ui/leash.py` (mit
      Wiederanstoß) und gilt in allen fünf Dialogen; Gestensitzungen sperren
      die Operationen und *Fertig* prüft sein Ziel; `launch_operation` ist
      der eine Einstieg für Menü und Palette, und die Palette zeigt
      Verfügbarkeit mit Grund; der Pinsel malt beim Ziehen (halber Radius
      als Mindestabstand); Legende zweifarbig, Fenstergeometrie gemerkt,
      Druckeinstellungsdialog wird freigegeben, Wandprüfung mit Wartezeiger,
      „Festschreiben" statt „OK". Der Export läuft im Arbeiter
      (`_ExportWorker`, ohne Abbrechen — mit Begründung im Docstring und in
      der Gebietsregel), die Druckeinstellungen öffnen sofort und
      `take_slice_result` trägt die Analyse nach, die synchronen Lesungen
      stehen unter `waiting()`. Und das letzte Paket ist drin: *Formen* und
      *Skelett* stehen als Knöpfe neben *Zeichnen* in der oberen
      Werkzeugleiste (ausgegraut mit Grund über `_pick_hint`), die Tour
      nennt den echten Weg und das Ziehen, und die Stellung eines Skeletts
      ist ein `ArmatureField` mit drei Zahlenfeldern je Knochen statt rohem
      JSON.
- [x] **Gering-Block als eigene Runde**: ~30 englische Docstrings (AGENTS.md
      behauptet Vollständigkeit), acht englische nutzersichtbare Fehlertexte
      in `backends/mesh.py`, „aufgeloest" in `advise.py`, deutsche
      Bezeichner in `tools/check_env.py` (Sprachprüfung sieht `tools/`
      nicht), Zylinder-Sortierung ohne Z, Redirect kann `check_url` umgehen,
      Analysekarten ohne Abbruch, Details in der Datei.

      **Vollständig erledigt** — Sprache (Übersetzungen, `mesh.py`-Texte
      samt Katalogen, `check_env.py`-Bezeichner, Sprachprüfung sieht
      `tools/`) und der Rest: Zylinder-Sortierung mit Z, `check_url` prüft
      den erreichten Ort nach der Weiterleitung, Analysekarten abbrechbar,
      abhängige Felder grauen mit Grund (G3), die Slicer-Wahl wird beim
      Schließen gemerkt (A5) und gegen den Drucker abgeglichen (A6), und
      *Hilfe → Beispiele* führt auf den Startbildschirm.
- [x] **Vier Stellen versprachen es, der Kern antwortete mit einer
      Fehlermeldung.** Ein Gelenkwinkel darf ein Projektparameter sein — das
      sagten der Registereintrag (*„Ein Winkel darf ein Projektparameter
      sein"*), der Docstring von `Pose` (*„`=@arm_angle` in einer Pose, und die
      Passung am Sockel rechnet mit"*), der `fx`-Umschalter am Winkelfeld des
      Dialogs und der Kopf von `tests/test_pose.py`. Wer es tat, las: **„Diese
      Stellung lässt sich nicht lesen."**

      **Der Denkfehler stand im Testkopf.** Dort hieß es, das prüfe „die
      Ausdrucksauflösung der Szene, nicht diese Datei". Sie prüft es nicht:
      `resolve_params` sieht die **oberste** Ebene eines Parametersatzes, und
      die Stellung steht dort als **ein** Wert — ein JSON-Text. Was darin an
      Ausdrücken steckt, sah nie jemand; `pose_from_text._vector` rief
      `float()` darauf. Ein Satz, der die Zuständigkeit woandershin verweist,
      ist genau die Sorte Beleg, die niemand nachprüft.

      Vier Stücke, und drei davon sind Rückwege, die vorher fehlten:

      **Auflösen** — `pose_from_text(text, values)` rechnet einen Winkel wie
      `=@neigung * 2` gegen dieselben Werte wie überall (§13). `values` ist ein
      Vorgabeargument und keine Pflicht, sonst müsste jeder Aufrufer mitziehen,
      auch die, die nie einen Ausdruck sehen. Ein unbekannter Parametername
      bekommt die Meldung des **Auswerters**, nicht die des unlesbaren Textes:
      Die Stellung ist ja gelesen, und wer den falschen Satz liest, sucht am
      JSON statt am Namen.

      **Sammeln** — `pose_parameter_references(text)`, das Gegenstück zu
      `sketch_parameter_references`. `NESTED_REFERENCES` in `evaluate.py` ist
      jetzt eine **Zuordnung statt einer Bedingung**: `sketch` stand dort hart
      verdrahtet, die Pose kam später und wurde übersehen. Ohne den Eintrag
      bliebe der Arm gebeugt, während die Zahl daneben schon die neue ist — die
      Gegenprobe fällt genau daran.

      **Zurücklesen** — `pose_angles(text)` gibt die Rohwerte, Zahl oder
      Ausdruck. Der Dialog **schrieb** einen Ausdruck wörtlich (das sagte sein
      Docstring zu und hielt es), **las** ihn aber über `pose_from_text`
      zurück, und die gibt drei Zahlen: Der Ausdruck ließ sie scheitern, der
      Fang machte daraus ein leeres Raster, und alle drei Winkel des Knochens
      standen auf null. Ein Rundlauf durch den Dialog verlor genau die
      Bindung, die er zu erhalten versprach.

      **Schreiben** — `pose_text(angles)` nimmt beides. Der Dialog hatte sich
      einen **zweiten Schreiber** für dasselbe Format gebaut (`json.dumps`),
      weil der im Kern nur `Pose` nahm und `Pose.angles` drei Zahlen sind —
      genau das, was sein eigener Docstring vermeiden wollte. Jetzt gibt es
      wieder einen.

      Drei Nachträge aus der Nachprüfung, und der erste ist der wertvollste:

      **Der neue Import schloss einen Kreis, und die Suite konnte ihn nicht
      sehen.** `geom.pose` braucht den Auswerter und importiert
      `scene.expressions`; Python lädt dabei das ganze Paket `scene`, dessen
      `__init__` `scene.evaluate` zieht — und das importierte `geom.pose`. In
      der Suite lief das durch, weil `scene` immer vorher dran war. Wer
      `app.core.geom.pose` **als erstes** lud — ein Skript, ein Werkzeug, eine
      Kommandozeile —, bekam einen `ImportError`. `nested_references()` ist
      deshalb träge.

      Der Test dagegen ist der eigentliche Gewinn:
      `test_every_core_module_imports_first` lädt jedes der 151 Kernmodule
      **als erstes**, mit geleertem `sys.modules` dazwischen. Der bisherige
      Test lud sie der Reihe nach in einem Prozess, und das ist schwächer, als
      es aussieht — ein Kreis zwischen zwei Modulen fällt nicht auf, solange
      das eine schon fertig ist, wenn das andere beginnt. Neun Sekunden für
      eine Klasse Fehler, die sonst erst ein Nutzer findet.

      **Der Skelett-Text kommt am Sammler vorbei**, weil beide Felder von
      `PoseParams` `kind="armature"` tragen. Er ist eine JSON-*Liste*, der
      Fang macht daraus ein leeres Ergebnis — richtig, denn ein Knochen ist
      eine Koordinate. Es steht jetzt im Docstring und in einem Test, weil ein
      stiller `AttributeError` wie ein Entwurf aussieht und nicht wie eine
      Entscheidung.

      **`format_version` bleibt bei 8**, und auch das ist eine Entscheidung.
      Das Schema ändert sich nicht — ein größerer Wertebereich in einem Feld
      ist kein neues Feld. Rückwärts gilt es nicht, aber eine Erhöhung würde
      **jede** neue Datei für die alte Fassung sperren, auch die ohne einen
      einzigen Ausdruck. Die Kette in `migrations.py` erhöht für
      Schemaänderungen, nicht für Fähigkeiten.

      Der kernnahe Cache-Test kam dazu: Der Ende-zu-Ende-Beleg ging über die
      Oberfläche, und fiele Qt aus, fiele der Beleg für §15 mit.
- [x] **Die Operationszahl im Fließtext war weggelaufen.** Das Register
      führt 85; die Funktionsseite sagte 83, die englische 84, während
      beide Startseiten richtig lagen. Der Grund steht weiter oben in
      dieser Datei: „`tests/test_website.py` prüft die Zahl gegen das
      Register und hat es gefangen, bevor die falsche Zahl auf der Seite
      stand" — das galt für die Kennzahlenleiste der zwei Startseiten und
      für sonst nichts. Die Zahl steht aber ein zweites Mal im Text, auf
      der Funktionsseite und in den häufigen Fragen. Der Test liest jetzt
      jede Seite unter `website/` statt einer festen Liste; der Stamm
      „oper" trägt durch alle sechs Sprachen, die Inline-SVG fallen vorher
      heraus (ihr „Vorschlag — 3 Operationen" ist ein Beispiel). Dieselbe
      Zahl stand im README: 84 Schemata und 97 KB, nachgemessen sind es 85
      mit 109 170 Zeichen, rund 107 KB.

      Nachgezogen am 18.08.: `tools.py` nannte 104 KB — gemessen sind es
      110 KB voll und 87 KB kompakt. `.claude/rules/agentenschicht.md`,
      `backends/llm.py` und `tests/test_backends.py` führten dieselben
      „84 Schemata, 99 000 Zeichen, 21 162 Token"; es sind 85 mit 109 170
      Zeichen. Die Tokenzahl kommt aus einem Lauf gegen `qwen3:14b`
      (`prompt_eval_count` bei `num_ctx` 32768, Basislinie ohne Werkzeuge
      abgezogen): **24 474 Token** für die Schemata allein, 26 601 für den
      ganzen Prompt mit allen 96 Werkzeugen, 19 249 für den kompakten Satz,
      den der Ollama-Weg fährt. Keiner davon wurde gekürzt — 81 % des
      Fensters, keine Halbierung, und 4,46 Zeichen je Token passen zur alten
      Messung (4,68). **32768 trägt also weiter**; die Schranke im Test steht
      jetzt auf 25 361 statt 21 162.

      Nebenbefund im selben Docstring: „der doc-Satz und der Menüort machen
      den größten Teil aus" stimmt nicht. Sie sind zusammen 14 013 Zeichen,
      die Parametertexte allein 40 945 — was der Kommentar dreißig Zeilen
      tiefer längst richtig sagte (dort stand 36 KB, gemessen 40 KB).

      Fünf weitere Stellen nannten denselben alten Bestand, ohne ihn zu
      messen: `session.py` („88 Werkzeuge mit 104 KB Schema"), `llm.py` oben
      („dreiundachtzig, rund 96 KB"), `tools/check_local_model.py` („sieben
      statt dreiundachtzig"), `.claude/rules/agentenschicht.md` („gegen 84
      Werkzeuge") und das Konzeptpapier vom August. Sie sind nachgezogen —
      aber nicht durch bloßes Ersetzen der Zahl: Jede nennt die Lage, in der
      **damals** gemessen wurde, und danach den heutigen Bestand. Wer nur die
      Zahl austauscht, behauptet eine Messung, die es nie gab; wer sie stehen
      lässt, beschreibt ein Register, das es nicht mehr gibt. Beides steht
      jetzt nebeneinander, und die Messwerte behalten ihren Bezug.

**Wettbewerb (Recherche 16.08., Quellen in der Durchsichts-Datei):** Die
Chat-Alleinstellung ist seit Zoo „Zookeeper" (01/2026) nicht mehr
konkurrenzlos — verteidigungsfähig als Paket *lokal + kalibrierte Passungen +
Schichtanalyse speist die Konstruktion + Einmalkauf*; kalibrierte Passungen
hat sonst niemand. Gefährlichstes Ökosystem ist Bambu/MakerWorld (Meshy-6,
Hunyuan 3.1, OpenSCAD-Customizer und Slicer-Werkzeuge in einem Gratis-Konto);
Backflip macht seit 03.08. Scan→Feature-Baum für ~10 USD. Die fünf größten
Lücken aus Kundensicht: Weg-3-Einstieg (ComfyUI-Hürde gegen Browser-Klick),
Verrundung auf importierten STLs, Gridfinity-Baustein, Messen am
Referenz-Mesh, Anschluss an fremde `.scad`-Customizer. Preis-Korridor:
69–99 € einmalig, Plasticity (150 USD) als Anker darüber.
## Die Oberfläche im Bild durchgesehen (17.08.2026)

Die vorige Durchsicht endete mit einem Satz, der eine Lücke benannte: *„Nicht
gemessen: das laufende Fenster als Bild. Der Container hier bringt VTK und die
Offscreen-Plattform nicht zusammen."* Diese hier hat genau dort angefangen —
auf einer Maschine, die rendert. Dazu sieben Prüfungen parallel gegen Menüs,
Dialoge, Aussehen, Texte, Rückmeldung, Barrierefreiheit und die vier Wege, jede
mit einer Gegenprüfung, die widerlegen sollte statt zu bestätigen.

**69 Funde haben die Gegenprüfung überlebt**, fünf sind daran gestorben. Was
unten unter „Behoben" steht, hat einen Test; was unter „Offen" steht, ist
belegt und mit Absicht liegen geblieben.

> **Drei der behobenen Funde waren am Quelltext unsichtbar.** Der Achsenmarker,
> die leeren Kästchen am Zahlenfeld und der verschwundene Platzhaltertext sind
> alle drei erst im Bild aufgefallen — und der erste stand seit jeher auf jedem
> Handbuchbild in jeder Sprache.

### Behoben

- [x] **Die Achsenanzeige lag hinter der linken Spalte.** Sichtbar war allein
      die Spitze des roten X-Pfeils, die unter der Karte hervorschaute; das
      sieht aus wie ein Grafikfehler und stand so auf jedem Bildschirmfoto.
      Der Wert `(0.0, 0.0, 0.16, 0.24)` trug die Begründung „unten links, wo
      keine Karte liegt" — dort liegen Objekte, Parameter und Verlauf. Anteile
      können das nicht lösen: Die Karte hält ihren Abstand in Bildpunkten.
      `orientation_corner()` rechnet jetzt aus Punkten, `resizeEvent` zieht
      nach. Unterwegs zwei weitere Funde: Der Docstring beschrieb einen
      anklickbaren Würfel, den es im ganzen Quelltext nicht gibt, und schloss
      mit „er ersetzt aber `add_axes`" — während die Zeilen darunter genau das
      aufrufen. Und `plotter.axes_widget` gibt es in pyvista 0.48 nicht; das
      Nachziehen lief still ins Leere und legte die Anzeige quer über das
      Modell, bis `axes_widget_of()` sie am Renderer suchte.
- [x] **Jedes Zahlenfeld zeigte zwei leere Kästchen statt der Pfeile.** Sobald
      ein Stylesheet an einem `QSpinBox` eine Rahmeneigenschaft setzt — und die
      Regel, die allen Eingabefeldern ihren Radius gibt, tut das —, hört Qt
      auf, dessen Unterelemente zu zeichnen. 27 Felder in 13 Dateien. Ein
      Dreieck aus Rahmenkanten half nicht (Qt füllt die Fläche und malt einen
      hellen Block), also sind es Bilder: zwei SVG im Cache (§38), je Thema in
      seiner Textfarbe geschrieben.
- [x] **Der Platzhaltertext verschwand.** `build_palette` setzte jede Rolle
      außer `PlaceholderText`, und was dort fehlt, kommt vom Betriebssystem.
      Auf einem dunkel eingestellten Windows war er hell — im hellen Thema
      damit weiß auf Weiß. Dreizehn Felder tragen ihre Auskunft dort, darunter
      das Muster `SOLIDON3D-1-…`, das als Einziges sagt, wie ein
      Lizenzschlüssel aussieht.
- [x] **Der Fokusring war im hellen Thema praktisch nicht da**: 2,06 auf einem
      weißen Feld, 1,70 auf dem Fenster, gefordert sind 3,0 (WCAG 1.4.11). Er
      nahm `highlight`; der Bernstein ist für den dunklen Untergrund gewählt.
      Er nimmt jetzt `accent_line` — dieselbe Farbe im dunklen Thema, im hellen
      der abgestufte Ton, den `theme.py` für genau diese Rechnung schon führte.
- [x] **Im Prüfbericht stand jede Zeile unter der Lesbarkeitsgrenze.** Die
      Befunde tragen ihre Rollenfarbe als Schrift (`panels.py`), und die ist
      für Dunkel gewählt: auf der weißen Liste des hellen Themas 2,22 für eine
      Warnung, 2,67 für einen Hinweis, 3,97 für einen Fehler. Der Test dazu
      fand gleich noch einen: Das Fehlerrot bringt auch **dunkel** nur 4,17 —
      im Standardthema, beim Schweregrad, der am dringendsten gelesen wird.
      `text_colour()` wählt den Ton jetzt nach der Helligkeit der Fläche, auf
      die geschrieben wird, nicht nach dem Namen des Themas.
- [x] **Gesperrtes sah aus wie bedienbar.** Die Palette setzte den
      Sperrzustand für `Text` und `ButtonText`, nicht für `WindowText` — und
      daran hängen QLabel, QCheckBox, QRadioButton und QGroupBox. Ein
      gesperrtes Ankreuzfeld war pixelgleich mit einem bedienbaren.
- [x] **Eine Farbe tat zwei Arbeiten und beide schlecht.** `disabled` war
      zugleich die Farbe für Nebentext — Maße, Spaltenköpfe, Gruppentitel, der
      stille Reiter. Damit war Nebentext bei 2,59 unlesbar und Gesperrtes nicht
      als solches zu erkennen. `muted` ist jetzt eine eigene Rolle.
- [x] **Der Splittergriff war einen Bildpunkt breit** — optisch eine Linie,
      praktisch nicht zu treffen. Jetzt zwei Rasterschritte, und er färbt sich
      beim Überfahren.
- [x] **Der Hinweis unter dem Zeiger hatte als einziges Element keine Form**
      und stand im hellen Thema auf dem Blassgelb, das Qt von Windows erbt: die
      einzige Farbe im hellen Thema, die aus keiner Tabelle dieser Anwendung
      stammte.
- [x] **Der Hauptknopf gab beim Drücken nicht nach.** `:default` steht später
      als `:pressed` und wiegt gleich schwer, gewinnt also — der lauteste Knopf
      der Anwendung war der einzige ohne Rückmeldung auf einen Klick.
- [x] **„Einfügen" im Bausteinkatalog versprach eine Wirkung, die er nicht
      hatte.** Ohne Auswahl stand er in voller Akzentfarbe da, nahm den Klick
      an, schloss den Dialog — und setzte nichts: `_accept` rief `accept()`
      auch ohne Baustein. Das ist die stillste Art, jemanden ratlos zu machen.
- [x] **Der Rat des Kernautors kam nie an.** Von 48 Kennungen, die der Kern in
      `Action(...)` vergibt, sind zehn verdrahtet; die übrigen wurden im
      Fehlerdialog verworfen, und an ihrer Stelle stand „Fehlerbericht
      erstellen" als Hauptknopf — auf einen reinen Bedienfehler, obwohl der
      Bericht laut `errors.py` dem `InternalError` gehört. Sätze wie
      „Schreiben Sie das Ziel als obj_2:hole_1." landeten im Nichts. Sie
      werden jetzt gelesen statt geklickt: Knöpfe bleiben denen vorbehalten,
      die etwas tun, der Rest steht als Text im Dialog (§2.7).
- [x] **Die Handbuchbilder zeigten die Oberfläche von vor dem Trennwerkzeug** —
      sieben Knöpfe statt acht, in allen sechs Sprachen. Alle 36 sind neu.
- [x] **Die Ebenentasten 1, 2 und 3 im Skizzeneditor taten nichts.** Die Ziffern
      des Ansicht-Menüs lagen darüber, und Qt lässt bei zwei aktiven Kürzeln
      derselben Taste keines von beiden feuern — eine Regel, die
      `main_window.py` selbst aufstellt und bis dahin nur auf `R` und `C`
      anwandte. Die Zeichenfläche versprach die Taste sichtbar: „(1)", „(2)",
      „(3)" stehen am Ebenenfeld und noch einmal im Tooltip. Die Einträge unter
      *Darstellung* sind im Skizzenmodus jetzt gesperrt — sie wirken dort
      ohnehin auf einen Viewport, den `start_sketch` aus dem Stapel nimmt. Der
      alte Test rief `choose_plane` an einem nackten Panel, also in genau der
      Umgebung ohne den Konflikt; der neue drückt die Taste im gebauten Fenster
      und macht im selben Lauf die Gegenprobe mit wieder aktiven Kürzeln.
- [x] **Der Download-Arbeiter fehlte beim Schließen.** Er folgt dem Muster mit
      `_retire` und `_hold_until_done` sauber, aber in `_retired` landet er
      erst, wenn er fertig ist — solange er lief, hielt ihn allein sein Feld,
      und `wait_for_workers` kannte es nicht. Ein Thread, der sein Fenster
      überlebt, nimmt den Prozess mit. Ein Test liest die Aufzählung jetzt
      gegen die Felder, damit der nächste nicht wieder durchrutscht.

### Offen

- [x] **Die Live-Vorschau rechnete den ganzen Stapel neu**, obwohl ihr
      Docstring seit jeher das Gegenteil zusagt: „der Cache trägt alle
      Schritte, die schon gerechnet sind". Der Aufruf reichte ihn nie durch —
      bei einem Dokument mit zwanzig Schritten also neunzehn fertige, für jede
      Änderung an einer einzigen Zahl. Voraussetzung dafür war ein Schloss im
      `ResultCache`: `_store` sind vier Schritte, und Auswertung, Agent und
      Vorschau schreiben aus eigenen Fäden hinein.

      **Der Test dazu war im ersten Anlauf wertlos**, und das ist die Lehre.
      Er war grün — aber auch ohne Schloss: Mit dem üblichen Umschaltintervall
      von fünf Millisekunden trifft der Fadenwechsel praktisch nie in die vier
      Schritte, die Gegenprobe lief null von fünf Mal auseinander. Mit einer
      Mikrosekunde fällt sie zehn von zehn. Wer hier etwas prüft, stellt das
      Intervall — sonst prüft er nichts.
- [x] **Der Slicer-Lauf ist abbrechbar.** `Popen` statt `run`, ein
      Abbruch-Token, das die Warteschleife abfragt, `terminate()` darauf, ein
      Abbrechen-Knopf am Fortschritt und ein `closeEvent`, das abbricht statt
      zu warten. Gebaut in einer parallelen Sitzung, genau auf dem Weg, den
      die Durchsicht vorgeschlagen hatte.
- [x] **Der Rest der Abbruchpunkte.** Fünf Stellen, und sie hatten alle
      dieselbe Bauart: Der Knopf wirkte, die Maschine hörte nicht auf.

      **Die Vorschau verwarf, statt anzuhalten.** `cancel_preview` erhöhte die
      Generation — das Ergebnis flog weg, die Rechnung lief zu Ende. Wer einen
      Dialog über einem großen Körper schloss, ließ zwei Boolesche Operationen
      je Körper hinter sich, und beim schnellen Tippen stapelten sie sich. Jeder
      Arbeiter führt jetzt ein **eigenes** `CancelSignal`; ein geteiltes mit
      `reset()` davor wäre ein Wettlauf, in dem der alte Lauf den gesetzten
      Zustand womöglich nie sieht. Eine neuere Anfrage bricht die älteren ab.

      **Die Trennebenensuche kannte keinen Abbruch von innen** — der Docstring
      sagte das sogar, als wäre es eine Eigenschaft. Sie schneidet jede
      Kandidatenebene durch das ganze Netz, Minuten an einem großen Körper, und
      „Abbrechen" hieß bisher: *das Ergebnis wird verworfen, wenn es kommt*.
      Das Token geht jetzt durch `plan_split` → `split_to_fit` → `find_plane`
      → `_judge`. Der Sonderfall dort ist die **Blockbildung**: Ein einziger
      Aufruf über alle Ebenen ist von außen nicht zu unterbrechen, und genau er
      ist die Minute — `_sections_in_blocks` schneidet zu acht und fragt
      dazwischen. Zusammengelegt wird gruppenweise, nicht blockweise, sonst
      stünde die Bewertung vor der falschen Nachbarschaft.

      **Im Erzeugen-Dialog war „Abbrechen" während des Laufs gesperrt** —
      `setEnabled(False)` traf die ganze Leiste und damit ausgerechnet den
      einen Knopf, den man bei einer Rechnung von Minuten braucht. Der Ausgang
      selbst war fertig gebaut (`reject` wartet auf den Thread), unerreichbar
      war nur sein Knopf; es blieb Esc, eine Taste, die niemand sucht, solange
      der Weg daneben grau dasteht. Dabei kam ein zweiter Fund mit heraus, den
      die gesperrte Leiste **verdeckt** hatte: `_update_state` hängt am
      Textfeld, und das bleibt bedienbar — wer weitertippte, machte *Erzeugen*
      wieder klickbar und startete einen zweiten Arbeiter über den ersten.

      **Eine abgebrochene Auswertung sagte es nur der Logdatei.** Balken weg,
      Knopf weg, dieselbe Ansicht wie vorher: von außen nicht zu unterscheiden
      von einer Rechnung, die *fertig* geworden ist. Der Satz nennt jetzt
      beides — das Aufhören und den Stand, den man vor sich hat —, und er geht
      in `_announcement`, damit ihn das nächste `_on_busy` nicht wegwischt.
      Gemeldet wird **nur der Abbruch durch einen Menschen**: Eine neuere
      Anfrage bricht die laufende ebenfalls ab, und das im Sekundentakt zu
      melden hieße, beim Ziehen an einem Schieber „abgebrochen" zu schreiben.

      **Speichern blockierte ohne jedes Zeichen.** Gemessen: 903 ms für ein
      Projekt mit einem 62-MiB-Netz — nach §2.8 die mittlere Stufe, Mauszeiger
      *und* Statusleiste, und beide fehlten. Kein Arbeiter dafür: Das Schreiben
      mutiert nichts, es blockiert einmal und ist fertig; ein Thread brächte
      Halteleine, Fehlerpfad und die Frage, was passiert, wenn dazwischen
      jemand weiterarbeitet. Die Zeile zeichnet sich vor dem Blockieren selbst
      neu (`repaint`, nicht `processEvents` — das eine Widget statt fremder
      Eingaben mitten im Aufruf).

      Die **Analysekarte** war der einzige Teil des Punkts, der schon stand:
      sie fragt am Eingang und in ihrer teuersten Schleife (`CANCEL_EVERY`).

      Und ein Nachbarfund: `_preview_finished` entfernte seinen Arbeiter
      **im** `finished`-Slot aus der Liste — die erste Hälfte der Falle aus der
      Gebietsregel, denn `finished` heißt „`run` ist zurück", nicht „das Objekt
      darf weg". Er geht jetzt denselben Weg über die Halteleine wie alle
      anderen.
- [x] **Die Befehlspalette ist der Universalzugang aus §19.2.** 38 von 136
      Menüzeilen fehlten, weil neben der Leiste ein von Hand gepflegtes
      Wörterbuch stand — und von Hand heißt driften. Gelesen wird jetzt die
      Leiste selbst: 82 Operationen kommen weiter aus dem Register (dort
      tragen sie Beschreibung, Kategorie und Verfügbarkeit), 60 Fensterbefehle
      aus dem Menü. Draußen bleiben genau zwei, und der Test nennt sie
      namentlich: *Beenden* ist in einer Liste, durch die man tippt, ein Klick
      zu nah am Verlust der Arbeit, und *Befehlspalette* öffnete sich selbst.
- [x] **Die Suche der Palette kannte weder Umlautfaltung noch ein Synonym.**
      Der Zugang stand, das Finden nicht: Wer „aushoehlen" tippte — und wer
      keine Umlaute auf der Tastatur hat, tippt so —, bekam **null Treffer**
      auf eine Operation, die es gibt. Dasselbe bei „groesse". Gemessen, nicht
      vermutet: die Zahlen unten sind vorher/nachher aus demselben Register.

      Drei Dinge, und jedes löst einen eigenen Fall:

      **Gefaltet wird auf beiden Seiten** (`fold`). „aushoehlen" findet
      „Aushöhlen", „Größe" findet, was intern `groesse` heißt. Angezeigt bleibt,
      was dasteht — gefaltet wird nur der Vergleich.

      **Der Wortstamm ist die zweite Runde, nicht die erste** (`matches(…,
      stem=True)`). „bohren" fand nichts, weil die Operation „Bohrung setzen"
      heißt — ein Fall, den keine Synonymtabelle je vollständig abdeckt und den
      die ersten Buchstaben lösen. Gelockert wird **erst, wenn die genaue Suche
      leer ausgeht**: immer zu lockern hieße, zwischen guten Treffern dauerhaft
      Ungefähres zu zeigen.

      **Ein Treffer im Titel wiegt schwerer als einer in der Beschreibung**
      (`rank`). Bei „bohrung" stand „An Merkmal ausrichten" vorn, weil dessen
      Beschreibung das Wort enthält, und „Bohrung setzen" auf Platz drei. Wer
      tippt, meint fast immer den Namen. Sortiert wird **stabil**, damit die
      Reihenfolge aus `applies_to` innerhalb derselben Güte stehen bleibt.

      | Eingabe | vorher | nachher | zuerst |
      |---|---|---|---|
      | `aushoehlen` | 0 | 2 | Aushöhlen |
      | `bohren` | 0 | 7 | Bohrung setzen |
      | `groesse` | 0 | 5 | Bohrung setzen |
      | `bohrung` | 7 | 7 | Bohrung setzen *(war: An Merkmal ausrichten)* |

      **Der Deckel auf dem Stamm ist der eigentliche Fund** (`STEM_CUT`). Die
      Untergrenze von vier Zeichen allein genügte nicht: „gibtsnicht" fand
      **acht** Einträge, weil „gibt" in acht Beschreibungen steht — und die
      Zeile „Kein Befehl passt zu …" kam nie zum Vorschein. Ein Stamm ist ein
      *gekürztes* Wort, kein beliebiger Anfang; höchstens drei Zeichen dürfen
      fallen. Aufgefallen ist das nicht beim Nachdenken, sondern weil ein
      **bestehender** Test rot wurde — der, der die Auskunftszeile prüft.

      Die **Bauart-Prüfung** war der dritte Teil des Punkts und ist bereits
      erledigt: `_palette_availability` liest sie aus denselben Menü-Actions,
      und ein nicht ausführbarer Eintrag steht ausgegraut da **samt Grund** —
      ausgrauen allein wäre die halbe Antwort (Regel 18).
- [x] **Zurückgenommen: Im deutschen Handbuchbild steht ein Komma, kein
      Punkt.** Der Fund war meiner, und er war falsch. Was ihn erzeugt hat, ist
      lehrreicher als er selbst.

      **Die Messung taugte nicht.** Ob ein Zeichen ein Komma ist, habe ich
      daran geprüft, ob es unter die Grundlinie reicht. Bei 9 pt tut das in
      Segoe UI **auch ein echtes Komma nicht** — es ist schlicht zu klein.
      Zwei Referenzfelder, eines mit „80,00" und eines mit „80.00", im selben
      Widget gerendert, unterscheiden sich in genau **sechs Bildpunkten**:

      ```
      Komma  y=15:  ####..####.##..####..####
      Punkt  y=15:  ####..####.###.####..####
      echtes Feld:  ####..####.##..####..####
      ```

      Zwei Punkte breit, nicht drei — das ist das Komma. Dazu kam die
      achtfache Vergrößerung, in der zwei Pixel auf der Grundlinie aussehen
      wie ein runder Punkt.

      **Was daran hängen blieb**, weil es teuer war: Ein Widerspruch zwischen
      dem, was ein Widget meldet (`lineEdit().text()` sagte durchweg Komma),
      und dem, was man im Bild zu sehen glaubt, ist zuerst ein Verdacht gegen
      die eigene Messung — nicht gegen Qt. Die Stunden, die hier in
      `QLocale`, `translate_parameter_titles` und die Aufnahmereihenfolge
      gingen, hätte ein Vergleich mit einer **Referenz** in fünf Minuten
      gespart: dasselbe Widget zweimal rendern, einmal mit dem vermuteten
      Falschen, einmal mit dem Richtigen.

- [x] **Weg 4 stand in keiner Unterlage** — und der Test wusste es besser als
      sie alle. `test_there_is_one_example_per_way` prüft seit P16 auf vier
      Wege, das Beispielprojekt liegt bei, das Handbuch hat sein Kapitel, die
      Oberflächenregel führt *Formen* und *Skelett* in der Werkzeugleiste.
      Nachgezogen sind jetzt die drei Stellen, die zurückhingen: §2.2 des
      Bauplans hieß „Drei Hauptwege" und listet den vierten jetzt mit seinem
      Ablauf (Grundkörper → verschmelzen → ausformen → exportieren) und mit dem
      Satz, warum Regel 2 dort besonders scharf gilt — hier zählt eine Geste
      und keine Zahl. Die README sprach von drei Wegen und acht
      Beispielprojekten, es sind vier und neun. Und die gezeichnete Abbildung
      im Handbuch zeigte drei Zeilen, während der Text daneben vier beschrieb;
      ihre Höhe folgt jetzt der Zahl der Zeilen, sonst stünde die nächste
      außerhalb des Bildes.
      Damit das nicht wieder driftet, zählt ein Test die Wege und die Beispiele
      **gegen `EXAMPLES`** und liest beide Unterlagen — samt der Tabelle in der
      README, in der jedes Beispiel seine Zeile haben muss. Die Website war
      bereits richtig; ihre 43 Zahlenprüfungen sind grün.

- [x] **Der Rest der Textfunde.** Drei Stück, und das zweite war das
      lehrreichste.

      **168 rohe Bezeichner gingen an den Nutzer.** „oversize_mm: 12.4" im
      Befund-Tooltip, „open_edges: 6" in den Einzelheiten eines Fehlers — eine
      feste englische Zeichenkette in der Oberfläche mit einem Umweg (Regel
      20). `value_label` in `app/ui/labels.py` übersetzt jetzt 156 Stämme; die
      **Einheit steht nicht im Wörterbuch**, sondern kommt aus dem Suffix, also
      teilen sich `size` und `size_mm` einen Eintrag und ein neuer Schlüssel
      mit bekanntem Stamm ist schon übersetzt. Vollständig gehalten wird die
      Liste **nicht von Hand** — von Hand heißt driften, daran war das
      Palettenwörterbuch gescheitert: `tests/test_value_labels.py` liest jeden
      `values=`-Schlüssel per AST aus `app/core` und wird rot, wenn einer keine
      Beschriftung hat. Und andersherum genauso, damit keine Beschriftung ohne
      Schlüssel fünf Kataloge belastet. Nebenbefund dabei: zwei Schlüssel
      hießen `erwartet` und `vorhanden` — **deutsch**, in einem Feld, das
      englisch zu sein hat.

      **Drei fertige Handlungen, an eine Ausnahme gehängt, die niemand wirft.**
      `OutOfBuildVolume` steht in `errors.py` mit *Modell teilen*, *Auf den
      Bauraum verkleinern* und *Anderes Druckerprofil wählen* — und keine Zeile
      im Programm erzeugt sie je. Das ist auch richtig so: Bauraum ist ein
      Bericht und keine Sperre (§29), gemeldet wird `arrange.out_of_build_volume`
      als Befund. Damit war der einzige Weg zu drei vollständig gebauten
      Vorschlägen zugemauert, und der Prüfbericht sagte, was nicht stimmt, und
      hörte auf — die halbe Antwort von §2.7.

      Der Befund bekommt jetzt ein **Kontextmenü** (`FINDING_ACTIONS`), das
      dieselben Handler ruft wie der Fehlerdialog; `as_error` verpackt ihn
      dafür, statt jede Handlung zweimal zu schreiben. Angeboten wird nur, wofür
      es einen Handler gibt — ein Befund ohne Handlung bekommt **kein leeres
      Menü**. Damit eine Handlung überhaupt greifen kann, trägt
      `check_build_volume` die Objektkennung mit: vorher stand dort nur ein
      laufender Index, und ein Bericht, der nicht sagt **welches** Teil zu groß
      ist, kann auch nichts dagegen anbieten.

      Und der Handler dahinter tat nichts: `_scale_after_error` las
      `build_volume` und `size` aus den Werten — zwei Schlüssel, die **weder
      Ausnahme noch Befund** je trägt. Die Bedingung darunter griff also immer,
      und die Methode kehrte still zurück. Gerechnet wird jetzt aus Profil und
      Szene; das ist keine zweite Wahrheit, sondern dieselbe, aus der auch
      `check_build_volume` rechnet.

      **Die Restzeitschätzung stand am falschen Ort.** §2.8 verlangt sie über
      zehn Sekunden — sie hing am Ladeschleier, und den gibt es nur, solange
      **kein** Körper dasteht. Bei jeder langen Rechnung an einem geladenen
      Modell, also genau im gemeinten Fall, stand in der Statusleiste Prozent
      ohne jede Zeitangabe. `remaining_time` ist jetzt eine freie Funktion,
      die beide benutzen.

> **Nachtrag vom 18.08.2026, beim Zusammenführen.** Zwei dieser Punkte hat eine
> parallele Sitzung in denselben Tagen erledigt, und das ist der Grund, warum
> sie hier nicht mehr stehen. Die vier Dialoge halten ihren Arbeiter jetzt über
> `app/ui/leash.py` — genau der Umbau, der oben als Weg beschrieben stand, mit
> einem eigenen Modul, aus dem Fenster und Dialoge erben. Und die Legende der
> Differenzansicht war dort unabhängig gefunden und behoben worden: zweimal
> derselbe Befund aus zwei Richtungen, was für ihn spricht. Geblieben ist die
> Fassung mit Farbfeld und gerechneter Schrift, weil sie neben der Zuordnung
> auch den Kontrast löst — als bloße Schriftfarbe kam die Legende in Graustufen
> auf 1,16 gegen ihr Band.

### Was die Durchsicht entlastet hat

Gezielt geprüft und in Ordnung: Der Prüfbericht trägt zu jeder Farbe ein
Symbol, die Menüs grauen vollständig richtig aus, die gestufte Tiefe hält in
jedem Operationsdialog außer dem einen oben, kein Parameter steht ohne `doc`,
und die Zahlenfelder der Skizzenleiste erklären sich über Tooltips. Fünf
gemeldete Funde sind an der Gegenprüfung gestorben — darunter die Behauptung,
der Startbildschirm trage einen veralteten Produktnamen: Die Domain heißt
`solidon3d.de`, und „Solidon3D" ist der Name, nicht der Rest eines alten.


## Die Konzepte nachrecherchiert (19.08.2026)

Anlass war ein Auftrag in einem Satz: *alle Konzepte ansehen, online
nachrecherchieren, auf einen aktuellen und vollständigen Stand bringen.*
Achtzehn Dokumente, zwei Richtungen — nach innen gegen den Code, nach außen
gegen die Welt. Fünf Tage nach der Durchsicht vom 14.08., die dasselbe ohne
den Blick nach außen tat.

**Der Umfang.** Je Dokument wurden die prüfbaren Behauptungen einzeln
nachgeschlagen: 300 über die Außenwelt, 265 über den eigenen Code. Für die
Außenseite entstanden 469 belegte Faktenkarten aus dreizehn Themenfeldern,
jede mit Quelle und Abrufdatum. Ergebnis der inneren Prüfung über alle
achtzehn: **102 Aussagen stimmen, 168 sind überholt, 26 waren schon beim
Schreiben falsch, 15 nicht mehr prüfbar.**

**Das Muster ist immer dasselbe, und es ist nicht Schlamperei.** Ein Konzept
wird geschrieben, danach wird nach ihm gearbeitet — und der Text bleibt im
Futur stehen, während der Code ihn einlöst. Am teuersten sind die Stellen, an
denen ein Nachtrag „erledigt" sagt und der Haupttext zwanzig Zeilen darüber
weiter „fehlt": Wer nur eine der beiden Stellen liest, baut etwas, das es
gibt, oder hält etwas für fertig, was offen ist. Neun Dokumente hatten genau
diesen Widerspruch in sich.

- [x] **Achtzehn Dokumente nachgezogen.** Jedes trägt jetzt sein Stand-Datum,
      einen Abschnitt „Nachrecherchiert am 19.08.2026" und an jeder
      berichtigten Stelle einen Vermerk mit Beleg — Datei und Zeile, Commit,
      Testname. 2182 Zeilen dazu, 112 geändert. Was Messung war, bleibt
      stehen und bekommt den heutigen Wert daneben: Ein Messwert vom 5. August
      ist am 19. August nicht falsch, sondern datiert.
- [x] **Vier Aussagen führten zu falscher Arbeit** und sind an beiden Stellen
      aufgelöst. `konzept-wettbewerb` ließ den GLB-Export als Aufgabe stehen,
      obwohl die eigene Befundtabelle ihn als erledigt führt (gebaut am
      11.08., einen Tag vor dem Dokument); es empfahl „Sprachen zuerst", die
      seit dem 13.08. liegen, und nannte das fehlende macOS-Paket den
      härtesten Befund, während seit dem 13.08. dafür paketiert wird.
      `konzept-erzeugen-agent-oberflaeche` beschrieb in Vorschlag A1 eine
      Umsetzung, die **gegen §2.6 verstoßen hätte** — nach `applies_to` zu
      filtern hätte dem Agenten je nach Auswahl einen anderen Werkzeugkasten
      gegeben. Gebaut wurde das Kürzen statt des Weglassens; die Begründung
      dagegen stand bis heute nur im Code.
- [x] **Sechsundzwanzig Aussagen waren von Anfang an falsch.** Die
      folgenreichsten: Das Trennwerkzeug ist der **siebte** Umschalter
      (`Alt+7`), nicht der achte — das Handbuch hatte immer recht.
      `hole_compensation` wird von `drill_hole` seit dem 28.07. angewandt,
      nicht erst „zu entscheiden". Der Volumenstrom von PETG war nie 12 mm³/s,
      sondern 10 — 12 ist PLA. Der Bernstein-Akzent hat 5,54 Kontrast gegen
      das Fenster, nicht 7,27. `tests/test_accessibility.py` hat nie
      existiert. Und zwei Zahlen zählten Baumzeilen statt Dinge: 23
      „Bausteine" waren 16 Bausteine unter 7 Gruppenköpfen, 42
      „Kürzelgruppen" 36 Kürzel unter 6.
- [x] **Der Faktor hundert ist ein Faktor 5,2.** Der Vergleich, der in
      `konzept-organische-modellierung` §7.2 die Trennung von `remesh_mesh`
      und `remesh_uniform` am eindrücklichsten begründet, ist unter trimesh
      5.0.0 zusammengefallen: 160 084 statt 3 260 416 Dreiecke gegen
      unveränderte 30 648. Die Entscheidung trägt weiter, aber auf dem anderen
      Bein — der Streuung der Kantenlängen, 2,224 gegen 0,41.
- [x] **Das Veröffentlichungskonzept wusste nicht, dass es einen Nachfolger
      hat.** Von siebzehn Aussagen hielt eine; der Grund ist die Wende vom
      12.08. von Testlauf-und-Verkauf zur kostenlosen Demo. Der Kopf sagt es
      jetzt und verweist auf das Demo-Konzept.
- [x] **P15 hakte einen ViewCube ab, den es seit dem 12.08. nicht mehr gibt**
      (`f04c35d` ersetzte ihn durch das Achsenkreuz). Damit steht D4 wieder
      ganz offen: Die Ansichtsleiste war mit dem Argument gestrichen worden,
      der Würfel decke sie ab.

**Was die Außenrecherche gebracht hat.** Drei Themenfelder haben sich in acht
bis siebzehn Tagen so bewegt, dass Entscheidungen daran hängen:

- [x] **Signierung — die Empfehlung dreht sich.** Azure Trusted Signing heißt
      heute **Azure Artifact Signing** und ist für Einzelpersonen faktisch
      verschlossen: Es verlangt eine Organisation mit drei Jahren
      nachweisbarer Existenz und ein zahlendes Azure-Abonnement. **EV umgeht
      SmartScreen nicht mehr** — Microsoft schreibt es ausdrücklich. Die
      Laufzeit sank am 01.03.2026 von 39 Monaten auf 460 Tage. Dafür gibt es
      einen Weg, den beide Konzepte nicht kannten: **Certum gibt ein
      Cloud-OV-Zertifikat auf den Namen einer Privatperson** aus, 139 $ im
      ersten Jahr, ohne Hardware-Token.
- [x] **Meshy ist einen Schritt näher gekommen, nicht ferner.** Meshy 7 ging
      am 10.08.2026 live. Die **Druckbarkeitsprüfung ist als API-Aufruf
      kostenlos** und meldet dieselbe Liste, die Solidons Prüfbericht führt;
      die Reparatur kostet 10 Guthaben. Das Kreativlabor rechnet seit dem
      01.06. in **Millimetern** — das ist die Richtung, aus der ein Generator
      in unser Feld kommt: über echte Maße an fertigen Produkten, nicht über
      bessere Netze.
- [x] **SindriCAD ist davongelaufen.** Von Fassung 0.1.81 auf **0.1.171**, von
      20 auf **141 Sterne**, 69 Commits in der letzten Woche — sämtlich vom
      Eigentümer. Architektur jetzt belegt: Python-Sidecar mit build123d auf
      OpenCASCADE, Oberfläche TypeScript/Three.js in einer Tauri-Hülle,
      Skizzenlöser **PlaneGCS**. Keine KI-Funktion im Programm, angekündigt am
      09.08. Und die Aussage „doppelt so viele Texturmuster wie SindriCAD"
      trägt nicht mehr: acht gegen sechs, und SindriCAD nimmt zusätzlich
      Graustufenbilder als Höhenkarte.
- [x] **Zwei Rechtsfristen sind eingetreten oder stehen an.** AI Act Artikel
      50 gilt **seit dem 02.08.2026** (er nennt Audio, Bild, Video und Text —
      3D-Modelle nicht, und dazu war kein Leitliniendokument auffindbar). Die
      **CRA-Meldepflichten greifen ab dem 11.09.2026**, also mitten in der
      Demo-Phase; die Ausnahme für freie Software gilt nur bei
      unentgeltlicher Bereitstellung.
- [x] **Der Fassungssatz hat wieder eine Arbeitsliste.** PySide6 und
      shiboken6 6.11.2 (18.08.), und **vtk 9.7.0 ist da, aber nicht ziehbar**:
      pyvista 0.48.4 verlangt in seinen Metadaten `vtk<9.7.0`. Hier entsteht
      die nächste Obergrenze, und sie liegt nicht in unserer Hand. Python
      3.15.0rc1 ist erschienen (Freigabe 01.10.), aber PySide6 deklariert
      `Python <3.15` — P5 bleibt die Wahl zwischen 3.13 und 3.14.

**Was die Durchsicht nebenbei am Code gefunden hat**, jeweils außerhalb der
Konzeptdateien und deshalb hier und nicht dort:

- [x] **`CLAUDE.md` nannte `trimesh<5` als „aufgeschobene Migration".** Der
      Satz war seit dem 14.08. falsch — `pyproject.toml:26` verlangt
      `trimesh>=5.0`, und damit stand dort **keine einzige Obergrenze mehr**.
      Berichtigt, und der Absatz sagt jetzt auch, was daraus folgt: Eine neue
      Grenze ist eine Entscheidung und gehört begründet. Die nächste zeichnet
      sich ab und liegt nicht in unserer Hand — `vtk 9.7.0` ist da, `pyvista`
      verlangt `vtk<9.7.0`.
- [x] **`CLAUDE.md` schickte den Leser für den Umsetzungsstand der
      Bedienkonzepte in ihre Schlusstabellen** — die nennen den Weg und den
      Aufwand, nicht den Stand. Beide Tabellen haben jetzt eine Stand-Spalte,
      und der Satz in `CLAUDE.md` sagt das Ergebnis vorweg: **Entwurf, und
      zwar vollständig** — umgesetzt ist von sechzehn Regeln und sechs
      Konzepten keines, drei sind auf anderem Weg eingelöst worden.
- [x] **`3d-agent-bauplan.md:1244` zählte fünf neue Werkzeuge und nannte
      vier.** Der Rest des zurückgenommenen `set_print_setting`. Auf vier
      berichtigt — und das ist keine Bauplanänderung mit Ansage, sondern die
      Auflösung eines Widerspruchs im Bauplan selbst: Die Aufzählung darüber
      ist die Wahrheit, die Zahl war ihr Rest.
- [x] **Diese Datei sagte „Achter Umschalter in der Werkzeugzeile".** Es ist
      der siebte, `Alt+7`; der achte ist `paint`. Berichtigt an der Stelle,
      die es behauptete.
- [x] **Das Anthropic-Backend sendete `temperature` unbedingt mit** — ab
      Claude Opus 4.7 ist der Parameter entfernt, und ein Nicht-Standardwert
      liefert einen 400er: Der Aufruf wäre also mit jedem neueren Modell
      vollständig gescheitert, nicht bloß anders ausgefallen. Behoben über
      eine **Positivliste** (`ANTHROPIC_MODELS_TAKING_TEMPERATURE`) statt einer
      Sperrliste: Ein unbekanntes Modell fällt in „nicht senden", und das ist
      immer zulässig — ohne Angabe nimmt die Gegenseite ihren Vorgabewert. Eine
      vergessene Sperrzeile wäre dagegen ein harter Fehler. Verglichen wird
      über den Namensanfang, weil dieselbe Fassung unter dem Alias und unter
      ihrem Schnappschuss erreichbar ist. Zwei Tests in
      `tests/test_backends.py`.
- [x] **Die Vorgabe steht auf `claude-sonnet-5`** (entschieden von Robert am
      19.08.2026). Sie kostet weniger — 2 statt 3 USD Eingabe je Mio. Token —
      und trägt das fünffache Kontextfenster: eine Million Token statt
      zweihunderttausend. Bei einem Prompt, dessen Werkzeugschemata allein
      110 KB wiegen, ist das der Unterschied, der zählt. `temperature` fällt
      durch die Positivliste von selbst weg.
- [ ] **Gegen Sonnet 5 ist die Suite nicht gefahren.** Der Wechsel ist in
      Kenntnis dessen entschieden; §35 verlangt die Messung vorher und nachher,
      und sie kostet zwei Läufe über den Schlüssel des Nutzers. Bis dahin ist
      die Trefferquote des Agenten eine Annahme — die letzte gemessene (28/39)
      gilt für Sonnet 4.5 und für ein lokales Modell, nicht für dieses.
      Nebenbei zu prüfen, wenn gemessen wird: Die `thinking`-Blöcke reisen bei
      einem mehrschrittigen Zug nicht zurück, und `stop_reason: "refusal"` ist
      nicht eigens behandelt.
- [x] **Drei Docstrings beschrieben einen überholten Stand.** `PinPlan.shape`
      kennt jetzt den Schnappverbinder samt seiner Mindestnaht von 5,4 mm;
      `start_screen` zählt nicht mehr acht Beispiele, sondern sagt „einen
      Schritt je Beispiel" — die Zahl wächst mit dem Katalog, der Befund
      nicht; und `profile_differences` nennt beim Volumenstrom die richtige
      Zeile: Beide Seiten sind sich mit 10 mm³/s einig, der Unterschied steht
      beim PRO.
- [ ] **D4 steht wieder offen** — ViewCube und Ansichtsleiste, siehe oben. Die
      sieben Kameravoreinstellungen liegen wieder allein im Menü.
- [ ] **Die Rückfallebene für Rechner ohne Grafikkarte steht in keiner
      Arbeitsliste** — B1 im Erzeugen-Konzept: ein zweites Mesh-Backend gegen
      einen gehosteten Dienst (dort fal.ai, 0,16 $ je Lauf), das ohne Umbau in
      das `MeshBackend`-Protokoll passt. ComfyUI bleibt der erste Weg; das hier
      ist der für Maschinen ohne 16 GB Grafikspeicher. Am Code geprüft
      (19.08.2026): Es gibt `ComfyBackend` und eine Test-Attrappe, kein
      gehostetes Backend — der Modulkopf von `backends/mesh.py` hat die
      Schnittstelle dafür ausdrücklich vorbereitet.

      **Vorsicht beim Zitieren:** „B1" bezeichnet in drei Konzepten drei
      verschiedene Dinge — hier die Rückfallebene, in `konzept-sindricad.md`
      die halbfertige Skizzenbedienung, in `konzept-meshy-hyper3d-2026-08.md`
      die fehlende Vergleichstabelle zur Druckbarkeit. Wer ein Kürzel
      übernimmt, nennt das Dokument dazu.

**Was nicht belegbar war und deshalb offen blieb.** Die Durchsicht hat an
neunzehn Stellen ausdrücklich nichts eingetragen: Messwerte, die einen
bestimmten Aufbau brauchen (Fahrgerüst mit echter Qt-Plattform, ComfyUI,
Ollama, Browsermessungen), Zahlen, die ein Anbieter nicht herausgibt
(SindriCADs Downloadzahlen, Patreon-Stände, Alibre- und nTop-Preise), und die
Frage, ob ein erzeugtes 3D-Modell unter die Kennzeichnungspflicht des AI Act
fällt. Eine ehrliche Lücke ist wertvoller als eine plausible Zahl — die
Vorarbeit dazu liegt in `.claude/.state/konzept-durchsicht-2026-08-19/`.

**Eine Lehre für die nächste Durchsicht.** Eine Recherche, die aus „steht
nicht in der Dokumentation" auf „gibt es nicht" schließt, ist keine. Der
Rechercheur zu Claude Code hat auf diesem Weg drei richtige Aussagen der
Bedienkonzepte für falsch erklärt — `argument-hint` etwa steht in sieben
Skills dieses Projekts und funktioniert. Der Korrekturvermerk liegt bei der
Vorarbeit.

**Und eine zweite, die teurer war.** Nach der Durchsicht wurden vier Hebel
vorgeschlagen, mit denen Solidon gegen die Mitbewerber wachsen sollte. **Drei
davon waren erledigt**, und alle drei standen in demselben Dokument, aus dem
sie abgeleitet wurden — nur nicht an derselben Stelle:

- „Weg 1 zum Hauptversprechen machen" (Empfehlung in 2.3) — eingelöst, beide
  Startseiten tragen ihn als `h1`.
- „Höhenkarten als Textur" — die Op `displace_image` steht seit P16 im
  Register. Gefunden auf dem Umweg über eine Stunde Doppelarbeit: Das Modul
  war schon halb nachgebaut, samt derselben Begründung im Kopf.
- „Ziehen und Ablegen sichtbarer machen" (Bedingung der Entscheidung vom
  13.08.) — am selben Tag eingelöst, `c76b735`, auf beiden Startseiten und im
  Startbildschirm.

Teil 6 des Wettbewerbskonzepts führte alle drei als abgehakt: „Zahl
richtiggestellt, Weg 1 nach vorn, Texturen mit Bild." Gelesen wurden die
Empfehlungen im Fließtext, nicht die Statustabelle daneben — **genau der
Fehler, den diese Durchsicht 168 Mal in anderen Dokumenten gefunden hat**, am
selben Tag begangen von demjenigen, der ihn dokumentiert hat.

Die Lehre ist keine über Sorgfalt, sondern über Reihenfolge: **Ein Vorschlag
wird am Register geprüft, bevor er ausgesprochen wird, nicht danach.** Eine
Empfehlung in einem Konzept ist ein Befund von damals; ob sie noch offen ist,
weiß nur der Code.

Das eigentliche Ergebnis dieser Runde steht damit auf der anderen Seite:
**Solidon ist dem Wettbewerbsfeld gegenüber weiter, als jedes seiner Konzepte
sagt.** Die Konzepte tragen ihre Befunde treu — ihre Erledigung tragen sie
nicht.

---
