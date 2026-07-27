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
      (Kontextmenü am Feature erst mit den Bohrungs-Ops in P2/P3 belegbar,
      Objekt-Kontextmenü steht)

---

## P1 — Sehen und Messen
- [x] Darstellungsmodi, Schattierung, Kameravoreinstellungen (§18.1)
- [x] Schnittebene **mit Capping**, Bildvergleichstest (§18.2) — der Nachweis
      läuft über Geometrie statt Pixel: die geschnittene Hälfte ist wasserdicht
      und hat genau das halbe Volumen, was ein Bild nicht unterscheiden könnte
- [ ] Messwerkzeuge, Durchmesser über Feature, Bemaßungen (§18.3)
- [ ] Gizmo und Snapping — jede Manipulation erzeugt eine Op (§18.10)
- [ ] Paletten und Alternativkodierung, Test auf Farbunabhängigkeit (§19.1)
- [ ] Tastaturnavigation, Befehlspalette (§19.2)
- [ ] Helles und dunkles Thema, HiDPI (§19.3)
- [ ] Leistungsziele Viewport (§31)

## P2 — Operationen manuell
- [ ] Reparatur-Ops gegen `broken_open`, `degenerate`
- [ ] Transformationen, Ausrichten, druckoptimal orientieren (Heuristik)
- [ ] Boolesche Ops mit Rückfallkette §17.2, Stufe und Startwert in der Op
- [ ] Bohrungs-Ops, Schneiden, Anordnen, Kollisionsprüfung
- [ ] Export nach §29 einschließlich Namensschema und Exportprüfung
- [ ] Orientierung vorerst als Normalen-Heuristik, in P3 ersetzt
- [ ] Fehlerdarstellung als Vorschlag (§2.7) für alle Geometriefehler
- [ ] **Weg 1 aus §2.2 als Ende-zu-Ende-Test**

## P3 — Wahrnehmung und Schichtanalyse
- [ ] Feature-Erkennung (§21.1) gegen `plate_holes`
- [ ] Provenienz-IDs und Zuordnung, `plate_holes_twin` als mehrdeutig
- [ ] Verwaisungsdialog über `ctx.ask`, Prüfung beim Öffnen
- [ ] Steckbrief (§23)
- [ ] Analysekarten (§18.4), Klick auf Warnung fährt die Kamera hin
- [ ] Feature-Overlay mit Kontextmenü (`applies_to`)
- [ ] Passungen anlegen und prüfen (§14)

### Schichtanalyse (§22)
- [ ] `core/slice`: Ebene-Mesh-Schnitt, Konturverkettung, Clipper2
- [ ] Kennzahlen je Schicht: Fläche, Überhang, Inseln, Brückenweite, Minimalbreite
- [ ] Test gegen analytisch bekannte Körper (Würfel, Zylinder, Kegel) auf 1 %
- [ ] `island_tower.stl` wird erkannt
- [ ] Orientierungssuche über hunderte Kandidaten, mit Startwert, abbrechbar
- [ ] Analysekarten Überhang und Stützbedarf auf echte Werte umstellen
- [ ] Schichtenvorschau im Viewport (§18.10), ehrlich beschriftet
- [ ] Herkunft jeder Kennzahl ausweisen (`internal`), nie mit G-Code vermischen

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
