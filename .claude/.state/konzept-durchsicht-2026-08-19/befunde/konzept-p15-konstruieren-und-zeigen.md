# Sondierung: .claude/konzept-p15-konstruieren-und-zeigen.md

**Titel:** Konzept P15 — Konstruieren und Zeigen
**Stand laut Dokument:** „Erhoben am 03.08.2026 gegen den Arbeitsbaum" (§2); der Kopf nennt zusätzlich „bis zum 08.08.2026" für den Wechsel von „Entwurf" auf „Erledigt"; die SindriCAD-Eckdaten sind auf „GitHub-API, 03.08.2026" datiert, die Farbakzent-Entscheidung „vom 03.08.2026"
**Zweck:** Begründet, wie Solidon vier Wettbewerbsquellen (SindriCAD, Meshy, 3Druck-Ticker, CAD-Übersicht) in Funktionen, Bediensprache und Darstellung übertrifft, ohne dass die Oberfläche mitwächst — mit 22 Delta-Punkten, 15 Leitentscheidungen und zehn inzwischen abgearbeiteten Etappen.

**Alterung:** 5/5 — Zwei schnell alternde Achsen: ein sechs Wochen altes, täglich bauendes Fremdprojekt (SindriCAD 0.1.81 samt Funktionsliste und eigenem Audit) mit Marktmeldungen und Finanzierungsrunden — und ein auf den Tag gemessener Solidon-Ist-Stand (55 Ops, 2211 Tests, 13 Symbole, kein ViewCube), den die zehn Etappen desselben Dokuments bereits überholt haben. §2 widerspricht §7 schon intern (55 vs. dreiundsiebzig Operationen, 33 vs. 39 Referenzanfragen). Als Begründung bleibt der Text gültig, als Bestandsaufnahme ist er zum Stand-Datum eingefroren.

## Gliederung

- 1. Was die Quellen zeigen
- 2. Ist-Stand Solidon — gemessen, nicht behauptet
- 3. Das Delta — zweiundzwanzig Punkte
- 4. Leitentscheidungen
- 5. Die Oberfläche darf nicht mitwachsen
- 6. Der Farbakzent — vertagt
- 7. Etappen
- 8. Was nicht gebaut wird — und warum
- 9. Folgen für Bauplan und Roadmap
- 10. Der Satz, um den es geht

## Extern prüfbare Behauptungen (20)

- **[hoch/fassung] SindriCAD (github.com/MakerViking/sindricad)** — Repository angelegt am 17.06.2026, Version 0.1.81, 20 Sterne, 6 Forks, AGPL-3.0, 13,4 MB, TypeScript; jeder grüne main erzeugt einen Build  
  _Ort:_ §1.1, „Belegbare Eckdaten (GitHub-API, 03.08.2026)"
- **[hoch/api] SindriCAD** — Architektur: Tauri-Rahmen in Rust, TypeScript/Three.js-Frontend, Geometrie-Sidecar in Python mit build123d/OpenCASCADE, JSON über WebSocket auf 127.0.0.1:8765  
  _Ort:_ §1.1, Architekturkasten
- **[hoch/funktionsumfang] SindriCAD** — Harte Invariante „Stateless full rebuild" — kein serverseitiger Zustand, kein Cache über Zwischenstände  
  _Ort:_ §1.1; trägt E10 und den behaupteten Cache-Vorsprung
- **[niedrig/sonstiges] SindriCAD / OpenCASCADE (OCCT)** — Ein Rust-Geometriekern wurde 2026 geprüft und verworfen, weil er OCCT weder in Robustheit noch Tempo schlug  
  _Ort:_ §1.1
- **[hoch/funktionsumfang] SindriCAD** — Funktionsumfang laut Quelltext: Spline, Text in Systemschriften, Projizieren, assoziative Skizzenmuster, Referenzmaße, Press/Pull mehrflächig, Offset Face, Thicken, Delete Face mit Heilung, Selektoren statt Topologie-Indizes  
  _Ort:_ §1.1, Funktionstabelle — trägt D8–D16
- **[mittel/funktionsumfang] PlaneGCS / FreeCAD** — SindriCAD benutzt PlaneGCS, den Solver aus FreeCAD  
  _Ort:_ §1.1, Funktionstabelle Skizze
- **[mittel/funktionsumfang] SindriCAD** — Import STEP, BREP, STL, 3MF, OBJ, GLB mit STEP-Kanonisierung; Texturen als exakte Gitter, umlaufend auf Zylindern, Zweifarbmodus  
  _Ort:_ §1.1, Funktionstabelle
- **[mittel/funktionsumfang] SindriCAD / OrcaSlicer / Moonraker / Snapmaker U1 / 3Dconnexion** — Ausgabe als OrcaSlicer-Projekt-3MF mit Extruderzuordnung, U1-Profilbindung; Moonraker-Client in Rust für LAN-Upload und Drucküberwachung; 3Dconnexion SpaceMouse nativ ohne Treiber; selbstaktualisierend  
  _Ort:_ §1.1, Funktionstabelle; trägt D21, D22, E10
- **[hoch/funktionsumfang] SindriCAD (docs/IMPROVEMENT-AUDIT.md)** — Eigenes Audit docs/IMPROVEMENT-AUDIT.md vom 10.07.2026 mit 45 bestätigten Funden („CI runs zero tests", „Save / Save As fail silently", main.ts 1710 Zeilen, SketchMode 1615 Zeilen); docs/EDGE-CASES.md mit 63 Fällen  
  _Ort:_ §1.1 „Schwächen"; stützt Etappe 4 (nicht-assoziative Skizzenmuster)
- **[mittel/marktlage] SindriCAD** — SindriCAD ist ein sechs Wochen altes Ein-Personen-Projekt und bewirbt sich um ein Grant  
  _Ort:_ §1.1, „Einordnung"
- **[hoch/funktionsumfang] Meshy 3D Agent / Bambu Studio** — Meshy 3D Agent: Modell in etwa einer Minute, ~97 % der Figuren bestehen die Bambu-Studio-Prüfung im ersten Anlauf, acht Exportformate, Ein-Klick-Übergabe an Bambu Studio  
  _Ort:_ §1.2
- **[hoch/marktlage] Meshy** — Meshy: 12 Millionen registrierte Nutzer, 400 Mio. $ Series B bei 1,5 Mrd. $ Bewertung  
  _Ort:_ §1.2, §1.3-Tabelle, §8 — trägt die Absage an Cloud-Generierung
- **[mittel/funktionsumfang] Meshy** — Meshys eigenes Eingeständnis: „Kein KI-Generator kann CAD vollständig ersetzen"; Details unter 1 mm fragil, exakte Abmessungen nicht garantiert  
  _Ort:_ §1.2
- **[hoch/funktionsumfang] FreeCAD MCP** — FreeCAD ist über MCP von Claude/ChatGPT steuerbar; zwei Umsetzungen, Installation über einen Ordner in /Mod  
  _Ort:_ §1.3-Tabelle; trägt D19 und E9
- **[mittel/funktionsumfang] FilaSim / CNC Kitchen** — FilaSim — quelloffene FEM und Infill-Optimierung im Browser von Stefan Hermann (CNC Kitchen), gibt ein 3MF-Projekt für den Slicer aus  
  _Ort:_ §1.3-Tabelle, §8
- **[mittel/funktionsumfang] Spherene NXT** — Spherene NXT — adaptive Minimalflächen (ADMS) plus TPMS, ortsabhängige Dichte, Zellgröße, Wandstärke  
  _Ort:_ §1.3-Tabelle, E6, §8
- **[mittel/marktlage] Tripo / Hi3D / Modly** — Finanzierungsrunden: Tripo 150 Mio. $, dazu Hi3D und Modly; Modly als lokale Alternative  
  _Ort:_ §1.3-Tabelle
- **[hoch/preis] Prusa EasyPrint** — Prusa EasyPrint-Abo sorgt für Kritik — Zahlbereitschaft ja, Abo nein, bestätigt den Einmalkauf  
  _Ort:_ §1.3-Tabelle; trägt die Preismodellentscheidung
- **[mittel/funktionsumfang] 3Druck.com CAD-Übersicht** — Die CAD-Übersicht von 3Druck listet zehn kostenlose Programme (FreeCAD, OpenSCAD, M4 Personal, BRL-CAD, BlocksCAD, Tinkercad, Figuro, SelfCAD, trCAD, Shapr3D) mit der Spalte „Deutschsprachig"; Tinkercad steht dort auf „Nein"  
  _Ort:_ §1.3, Absatz nach der Tabelle; trägt das DACH-Verkaufsargument
- **[mittel/recht] WCAG 2.x** — WCAG verlangt 3:1 für Bedienelemente und 4,5:1 für Text  
  _Ort:_ §6, „Die Farbfamilie — gerechnet, nicht behauptet"

## Intern prüfbare Behauptungen (15)

- **[hoch]** 55 Operationen im Register, 16 Kategorien, 16 Bausteine  
  _Prüfen:_ @register_op / @register_part in app/core/registry zählen; Etappe 8 spricht dagegen von „dreiundsiebzig" Operationen und vierzehn Kategorien — Widerspruch im Dokument  
  _Ort:_ §2 erster Punkt vs. Etappe 8
- **[hoch]** 2211 Tests grün (-m "not performance", 158 s), keine Importfehler  
  _Prüfen:_ .venv\Scripts\python.exe -m pytest -q -m "not performance" — Zahl und Dauer vergleichen  
  _Ort:_ §2
- **[hoch]** Skizzen: 5 Ops, 9 Bedingungsarten, 200 Bedingungen in 90 ms; Elemente nur Punkt, Linie, Kreis, Bogen  
  _Prüfen:_ app/core/sketch/ — Bedingungsarten und Elementarten zählen; Etappe 4 ergänzte Referenzmaß (zehnte Art) und Spline  
  _Ort:_ §2, Etappe 4
- **[hoch]** 6 Kürzel an Operationen, 21 im Fenster; 13 Symbole insgesamt, keines für eine Operation  
  _Prüfen:_ shortcut- und icon-Felder im Register zählen; Etappe 8 hat Symbole je Kategorie und zwei Kürzelbelegungen nachgezogen — Zahl überholt  
  _Ort:_ §2, D5, D6
- **[hoch]** Viewport ohne Anti-Aliasing, Umgebungsverdeckung, Schatten, Studiolicht; kein ViewCube, keine Ansichtsleiste; keine Druckerverbindung  
  _Prüfen:_ app/ui viewport nach enable_anti_aliasing / enable_ssao / add_camera_orientation_widget durchsuchen; Etappe 1 ist abgehakt, §2 also überholt  
  _Ort:_ §2, D4, D20, D22
- **[hoch]** Agent mit 33 Referenzanfragen  
  _Prüfen:_ tools/run_agent_suite.py bzw. die Anfragenliste zählen — AGENTS.md nennt 39  
  _Ort:_ §2.1, Absatz „Agent"
- **[mittel]** Handbuch mit 25 Seiten und 20 Abbildungen, sieben Beispielprojekte, sechs Formatversionen mit Migrationen  
  _Prüfen:_ app/core/manual.py, figures.py und format_version in app/core/scene/ prüfen  
  _Ort:_ §2.1
- **[mittel]** Auswertung aus dem Cache in 0,3 ms  
  _Prüfen:_ .venv\Scripts\python.exe -m pytest -q -m performance, Cache-Messung gegen Bauplan §31  
  _Ort:_ §1.1, §2.1
- **[hoch]** P15 ist vollständig abgearbeitet; von 22 Lücken sind vier begründet abgelehnt, der Rest umgesetzt (alle zehn Etappen abgehakt)  
  _Prüfen:_ ROADMAP.md-Abschnitt P15 lesen; jeden [x]-Punkt in §7 gegen den Code prüfen  
  _Ort:_ Kopfkasten „Erledigt", §7
- **[mittel]** Import STL/3MF/OBJ/GLB/GLTF/PLY/OFF/STEP/STP/SVG/DXF, Export STL/3MF/OBJ/PLY/STEP  
  _Prüfen:_ Formatlisten in app/core/ingest/ und app/core/export/ vergleichen  
  _Ort:_ §2
- **[hoch]** Die sieben Obergrenzen aus E12 (≤9 Menüs, ≤8 Umschalter, ≤8 Felder vorn, genau 1 Menüeintrag je Op, ≤12 Untermenüeinträge, 0 Werkzeuge ohne Hinweis, 0 Ops ohne Symbol) sind als Tests umgesetzt und werden eingehalten  
  _Prüfen:_ Test zu den Obergrenzen in tests/ suchen und laufen lassen  
  _Ort:_ E12, Etappe 0, Abnahme Etappe 8
- **[mittel]** Der Farbakzent ist vertagt; Anwendungssymbol bleibt kupfer (#e08b4e), Diff-Blau bleibt #3b82c4  
  _Prüfen:_ app/images/icon/solidon3d.svg und die Themendatei auf die Hexwerte prüfen  
  _Ort:_ §6
- **[mittel]** Höhenkarte aus Graustufenbild in apply_texture fehlt („notiert, nicht gebaut"); acht Muster statt neun  
  _Prüfen:_ Parameterschema von apply_texture — Musterwerte zählen  
  _Ort:_ Etappe 5
- **[hoch]** Die Bauplanänderungen aus §9 (§25, §18, §19, §10, §30.1, §26/§32, §31, §41) stehen noch aus  
  _Prüfen:_ 3d-agent-bauplan.md an den genannten §-Nummern lesen: Kategorie Oberfläche, Feld icon, Werkzeugregel, MCP, Obergrenzen vorhanden?  
  _Ort:_ §9, Folgentabelle
- **[niedrig]** Sechs von 68 Modellen im Korpus sind nicht geschlossen  
  _Prüfen:_ tests/data/ zählen und den Prüfbericht über den Korpus fahren  
  _Ort:_ Etappe 6, thicken