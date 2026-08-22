# Sondierung: konzept-sindricad.md

**Titel:** Konzept — SindriCAD als Maßstab
**Stand laut Dokument:** Gemessen am 4. August 2026.
**Zweck:** Vergleicht das neu erschienene freie CAD-Programm SindriCAD mit dem tatsächlichen Stand von Solidon und leitet daraus vier Konzeptbausteine (Skizze, Texturen sichtbar machen, letzte Meile zum Drucker, GLB-Export) sowie eine offene Lizenzfrage ab.

**Alterung:** 5/5 — Der Vergleich hängt vollständig an einem fremden Programm in öffentlicher Beta (Funktionsumfang, Finanzierungszahlen, Presseecho) und an Momentaufnahmen des eigenen Repositories (61 Ops, 16 Bausteine, 2598 Tests, Zeilenzahlen, Tor-Ergebnis). Beide Seiten ändern sich in Wochen; zusätzlich können die Bausteine A bis D inzwischen ganz oder teilweise umgesetzt sein.

## Gliederung

- Teil 1 — Was SindriCAD ist
- Teil 2 — Kontrolle: der Stand von Solidon
- Teil 3 — Der Abgleich
- Teil 4 — Die Befunde
- Teil 5 — Was wir ausdrücklich nicht übernehmen
- Teil 6 — Das Konzept
- Teil 7 — Reihenfolge
- Teil 8 — Die offene Entscheidung

## Extern prüfbare Behauptungen (20)

- **[hoch/datum] SindriCAD** — SindriCAD ist am 2. August 2026 als öffentliche Beta erschienen  
  _Ort:_ Einleitung
- **[mittel/sonstiges] SindriCAD / MakerViking / TinkerAtlas** — SindriCAD ist ein freies parametrisches CAD-Programm für den 3D-Druck, Einzelprojekt des Machers hinter TinkerAtlas (Pseudonym MakerViking)  
  _Ort:_ 1.1 Herkunft und Technik
- **[hoch/funktionsumfang] SindriCAD (build123d, OpenCASCADE, Tauri)** — SindriCAD baut im Kern auf build123d über OpenCASCADE (B-Rep, kein Mesh-Kern), Oberfläche in Tauri, für Linux, Windows, macOS  
  _Ort:_ 1.1 Tabelle
- **[hoch/recht] SindriCAD** — SindriCAD steht unter AGPL, quelloffen, ohne Konto, ohne Abo, ohne Testfrist; Builds sind unsigniert  
  _Ort:_ 1.1 Tabelle, 1.3, Teil 8
- **[hoch/funktionsumfang] SindriCAD** — Funktionsumfang: Extrudieren, Rotieren, Loften, Verrunden, Fasen, Aushöhlen, Press/Pull, Spiegeln, Muster, parametrische Historie, Skizzen mit Zwangsbedingungen, Messwerkzeuge, Schnittansichten  
  _Ort:_ 1.2
- **[hoch/funktionsumfang] SindriCAD** — SindriCAD bietet Oberflächentexturen als echte Geometrie (Rändel, Waben, Wellen, Voronoi) — insgesamt vier Muster  
  _Ort:_ 1.2, 3.1, B2
- **[hoch/funktionsumfang] SindriCAD** — SindriCAD exportiert STL, STEP, 3MF und importiert STEP, BREP, STL, 3MF, OBJ, GLB; es schreibt GLB hinaus  
  _Ort:_ 1.2, 3.1, B4
- **[mittel/funktionsumfang] SindriCAD / Autodesk Fusion** — SindriCAD bietet Mehrfarb-Ausgabe über 3MF und vertraute Tastenkürzel aus gängigem professionellem CAD (Fusion-nah)  
  _Ort:_ 1.2, 1.3
- **[hoch/funktionsumfang] Snapmaker U1 / OrcaSlicer** — SindriCAD unterstützt den Snapmaker U1: Mehrmaterial an OrcaSlicer übergeben und G-Code über das lokale Netz an den Drucker schicken  
  _Ort:_ 1.2, 3.2, Teil 5
- **[hoch/preis] SindriCAD Spendenfinanzierung / Apple Developer Program** — Finanzierung: 335 $ Sockelkosten im Monat, 19 % des Ziels erreicht, ein Monat ohne Entwicklung wegen unbezahlter Werkzeuge, 99 $ für das Apple-Entwicklerkonto als Engpass  
  _Ort:_ 1.3
- **[hoch/api] FreeCAD MCP** — FreeCAD lässt sich über eine MCP-Schnittstelle von Claude oder ChatGPT steuern: Dokumente anlegen, Körper hinzufügen, Maße ändern, Python ausführen  
  _Ort:_ 1.4
- **[hoch/funktionsumfang] FreeCAD MCP** — Grenze der FreeCAD-MCP-Anbindung: Primitive, Booleans und Muster gehen, stark bedingte Skizzen und Verrundungsketten kaum; nicht bei toleranzkritischen Teilen  
  _Ort:_ 1.4, Teil 8
- **[mittel/preis] Prusa EasyPrint** — Prusa EasyPrint ist ein Abo-Modell für den Cloud-Slicer, mit öffentlicher Kritik, auf die der Firmengründer reagieren musste  
  _Ort:_ 1.4
- **[mittel/marktlage] Hi3D, Modly, Meshy, Tripo** — Hi3D, Modly, Meshy und Tripo sind KI-Modellerzeuger, teils mit Milliardenfinanzierung  
  _Ort:_ 1.4
- **[niedrig/funktionsumfang] FilaSim, PanX, Watchtower** — FilaSim und PanX simulieren Belastung und Restspannung; Watchtower ist ein lokales Druckerfarm-Dashboard ohne Cloud  
  _Ort:_ 1.4
- **[hoch/marktlage] CAD-Markt / 3Druck.com Software-Rubrik** — KI-gesteuerte CAD-Bedienung ist kein Alleinstellungsmerkmal mehr; lokal und ohne Abo ist gerade ein Verkaufsargument  
  _Ort:_ 1.4 Schluss
- **[mittel/marktlage] 3Druck.com, Tao of Mac, TinkerAtlas** — SindriCAD stand binnen eines Tages in deutscher und englischer Fachpresse: 3Druck.com, TinkerAtlas, Tao of Mac, mehrere Fachkonten  
  _Ort:_ 3.2 Punkt 4, B5
- **[hoch/api] Moonraker/Klipper, OctoPrint** — Moonraker (Klipper) und OctoPrint decken als offene Protokolle den Selbstbau- und Bastelbereich ab; herstellereigene Netzwege haben kein offenes Protokoll  
  _Ort:_ Baustein C, Punkt 1
- **[mittel/funktionsumfang] Elegoo Centauri Carbon 2** — Der Elegoo Centauri Carbon 2 als Referenzmaschine entscheidet, welches Sendeprotokoll zuerst gebaut wird  
  _Ort:_ Baustein C, Punkt 1
- **[niedrig/api] scipy** — Solidons 2D-Löser für Zwangsbedingungen stützt sich auf scipy  
  _Ort:_ 3.1 Tabelle

## Intern prüfbare Behauptungen (15)

- **[hoch]** Anwendung: 178 Python-Dateien, 51.565 Zeilen; Tests: 95 Dateien, 25.678 Zeilen; 35 Oberflächenmodule  
  _Prüfen:_ Dateien und Zeilen unter app/, app/ui/ und tests/ zählen  
  _Ort:_ 2.1 Umfang
- **[hoch]** 61 registrierte Operationen  
  _Prüfen:_ Register auszählen über app.core.registry (alle @register_op)  
  _Ort:_ 2.1
- **[hoch]** 16 registrierte Bausteine  
  _Prüfen:_ register_part-Einträge unter app/core/knowledge/parts/ zählen  
  _Ort:_ 2.1
- **[hoch]** 8 Texturmuster: rib, wave, knurl_straight, knurl_diamond, hexagon, dimple, voronoi, noise  
  _Prüfen:_ Musterliste im Textur-Op-Schema prüfen (grep knurl_diamond unter app/core/geom)  
  _Ort:_ 2.1, 3.1, B2
- **[hoch]** Phasen P0 bis P15, Arbeitsliste bis auf einen Punkt abgetragen  
  _Prüfen:_ ROADMAP.md: höchste Phasennummer und offene Punkte  
  _Ort:_ 2.1
- **[hoch]** Tor grün: ruff format 326 Dateien, mypy ohne Beanstandung in 178 Quelldateien, ruff check grün, pytest 2598 grün in 3:35 min  
  _Prüfen:_ /pruefen bzw. die vier Befehle aus CLAUDE.md ausführen und Zahlen vergleichen  
  _Ort:_ 2.2 Das Tor
- **[mittel]** Der rote Übersetzungstest (verwaiste en-Einträge Entfernt/Hinzugefügt/Unverändert) ist behoben in app/ui/palette.py, Commit 1dcd855  
  _Prüfen:_ git show 1dcd855; pytest tests/test_translations.py -q  
  _Ort:_ 2.3
- **[hoch]** Der native Absturz in der Referenzschleife Python/VTK ist selten, aber nicht beseitigt; ein Absturzprotokoll steht in der Roadmap noch offen  
  _Prüfen:_ ROADMAP.md nach Absturzprotokoll durchsuchen; konzept-bedienung.md 5.5; Suite mehrfach fahren  
  _Ort:_ 2.3
- **[hoch]** Solidon importiert zusätzlich PLY, OFF, GLTF, SVG, DXF; writer.py schreibt nur stl, 3mf, obj, step — GLB kommt herein, geht nicht hinaus  
  _Prüfen:_ READABLE_SUFFIXES unter app/core/ingest und Formattabelle in app/core/export/writer.py prüfen  
  _Ort:_ 3.1, B4, Baustein D
- **[mittel]** Drei Slicer angebunden (Prusa, Orca, Cura) mit Rückprüfung der geschriebenen Werte  
  _Prüfen:_ app/core/export/handover.py und slicer_keys.py  
  _Ort:_ 3.1
- **[mittel]** shortcut_schemes.py bietet eine Fusion-Belegung, aber nur fürs Modellieren, nicht für die Skizze  
  _Prüfen:_ app/ui/shortcut_schemes.py auf Skizzenkürzel prüfen  
  _Ort:_ 3.1, 3.2, Baustein A
- **[hoch]** Die Skizze ist rechnerisch fertig und bedienerisch halb — neun offene Punkte laut konzept-bedienung.md Teil 4 (Ändern-Gruppe, Projizieren, Konstruktionsgeometrie, Zeichenkürzel, Ursprung/Maßstab)  
  _Prüfen:_ konzept-bedienung.md Teil 4 lesen und gegen die Skizzenwerkzeuge in app/ui abgleichen  
  _Ort:_ B1, Baustein A
- **[mittel]** Sieben Touren vorhanden, laut Durchsicht inhaltlich vorbildlich; eine achte zur Textur sowie ein Musterkatalog mit gerenderten Kacheln fehlen (figures.py könnte das bereits)  
  _Prüfen:_ Tour-Registrierungen zählen; app/figures.py und tools/make_figures.py ansehen; Handbuchseite Griff und Muster suchen  
  _Ort:_ Baustein B
- **[hoch]** Der Bauplan kennt das Senden von G-Code nicht — §28 meint Rücklesen und Nachmessen, §29 endet beim Slicer-Aufruf; ein §28.4 wäre eine Bauplanänderung mit Ansage  
  _Prüfen:_ 3d-agent-bauplan.md §28 und §29 lesen  
  _Ort:_ B3, Baustein C
- **[hoch]** LICENSE: Copyright (c) 2026 RS Digital, alle Rechte vorbehalten — proprietär, mit zwei MIT-Ausnahmen für Bausteinbibliothek und Referenzkorpus  
  _Prüfen:_ LICENSE im Repository lesen  
  _Ort:_ Teil 8