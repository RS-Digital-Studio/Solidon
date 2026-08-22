# Sondierung: konzept-wettbewerb-2026-08.md

**Titel:** Konzept — Solidon3D gegen das Wettbewerbsfeld
**Stand laut Dokument:** 11.08.2026 (Titelzeile: „Konzept — Solidon3D gegen das Wettbewerbsfeld (11.08.2026)"; Methode: „Marktstand kommt aus Recherche vom 11.08.2026"; Nachträge „Nachgetragen 13.08.2026" bzw. „Stand am 13.08.2026")
**Zweck:** Ein vollständiger Bereichsdurchgang durch Solidon gegen das Wettbewerbsfeld, der je Bereich ein Urteil (führend/gleichauf/zurück) fällt, die kaufrelevanten Lücken W1–W9 sortiert und vier Entscheidungen für Robert vorlegt.

**Alterung:** 5/5 — Zwei schnell alternde Schichten tragen das Dokument: Marktzahlen fremder Programme (Preise, Fassungen, GitHub-Sterne, eingestellte Produkte, Autodesks generative Funktionen) und gemessene Eigenzahlen (77 Operationen, 16 Bausteine, Sprachkataloge, Agentenquote). Es widerlegt sich bereits selbst — 2.10 behauptet zwei Sprachen, Teil 4 und 6 melden sechs; 2.8 führt GLB-Export als offen, W7 als erledigt; vier von neun Lücken wurden geschlossen, während das Dokument sie als offen führte. Das Dokument sagt es über sich selbst: eine Lückenliste altert schneller als der Code.

## Gliederung

- Teil 1 — Das Feld in sechs Gruppen
- Teil 2 — Der Bereichsdurchgang
- Teil 3 — Wo Solidon allein steht
- Teil 4 — Die Lücken, nach Kaufrelevanz
- Teil 5 — Was wir nicht übernehmen
- Teil 6 — Empfohlene Reihenfolge
- Teil 7 — Was du entscheiden musst

## Extern prüfbare Behauptungen (20)

- **[hoch/preis] Autodesk Fusion 360 (Personal/Abo)** — Fusion 360 Personal ist kostenlos, aber mit Fesseln: 10 aktive Dokumente, eingeschränkte Exportformate; CAD-Gruppe reicht bis ~545 $/Jahr  
  _Ort:_ Teil 1 Tabelle G1; 2.12 Wettbewerb
- **[hoch/preis] Plasticity (indie CAD)** — Plasticity kostet ~150 $ einmalig, mit 12 Monaten Aktualisierungen  
  _Ort:_ Teil 1 Tabelle G2; 2.12
- **[hoch/preis] Shapr3D** — Shapr3D kostet ~299 $/Jahr, kein Einmalkauf; der Sprung von kostenlos auf 299 $/Jahr lässt eine Preislücke, in die 49 € passen  
  _Ort:_ Teil 1 Tabelle G2; 2.12 Urteil
- **[mittel/fassung] OrcaSlicer** — OrcaSlicer in Fassung 2.9.4 bzw. 3.0  
  _Ort:_ Teil 1 Tabelle G5
- **[mittel/fassung] Tencent Hunyuan3D** — Hunyuan3D 2.1 als ComfyUI-Graph  
  _Ort:_ 2.4 Stand
- **[hoch/funktionsumfang] Autodesk Fusion / Autodesk Foundation Models** — Autodesk baut generative, editierbare B-Rep-Geometrie in Fusion aus einem Prompt, angetrieben von eigenen Foundation-Modellen  
  _Ort:_ Teil 1 Bewegung 1; Teil 3; Teil 5
- **[hoch/funktionsumfang] Bambu Lab MakerWorld Parametric Model Maker** — MakerWorld Parametric Model Maker läuft direkt auf der Modellseite, seit v1.0 auch mit Fusion-Dateien  
  _Ort:_ Teil 1 Bewegung 2; 2.11; W9
- **[hoch/marktlage] blender-mcp / freecad-mcp (GitHub)** — Blender-MCP zählt 17.800 Sterne; FreeCAD-MCP bringt 165 Werkzeuge über 15 Module  
  _Ort:_ Teil 1 Bewegung 3
- **[hoch/marktlage] Autodesk Meshmixer, Microsoft 3D Builder, MeshLab, Netfabb, Materialise Magics** — Meshmixer ist eingestellt, 3D Builder abgekündigt, MeshLab veraltet in der Bedienung, Netfabb und Magics kosten industriell  
  _Ort:_ Teil 1 Tabelle G4; 2.3; Teil 3
- **[mittel/funktionsumfang] Meshy, Modly, MakerWorld/AMS** — Meshy hat automatische Farbzonen für AMS und ist in MakerWorld eingebaut; Modly macht dasselbe lokal und kostenlos  
  _Ort:_ 2.4
- **[mittel/marktlage] Zoo, AdamCAD, Spectral SGS-1, Meshy, Tripo** — Zoo, AdamCAD, Spectral SGS-1 als Text→CAD; Meshy, Tripo, Hunyuan3D, Modly als Text→Mesh  
  _Ort:_ Teil 1 Tabelle G6
- **[hoch/funktionsumfang] OrcaSlicer, PrusaSlicer, Bambu Studio, Cura** — Orca hat die Kalibriersuite, Prusa die organischen Stützen; Orca, Prusa, Bambu und Cura schicken die Datei über das Netz an die Maschine  
  _Ort:_ 2.6; 2.8 (trägt Entscheidung 2 in Teil 7)
- **[mittel/funktionsumfang] Cura, OrcaSlicer, PrusaSlicer (Lokalisierung)** — Cura, Orca und Prusa liefern zweistellig viele Sprachen  
  _Ort:_ 2.10
- **[hoch/funktionsumfang] macOS-Verfügbarkeit der CAD-/Slicer-Programme** — Fusion, Shapr3D, Plasticity, Orca, Prusa, Blender und Bambu Studio decken macOS alle ab  
  _Ort:_ 2.10 (trägt Entscheidung 1)
- **[hoch/recht] Apple Developer Program / Gatekeeper-Notarisierung** — Apple-Signierung braucht ein Konto und kostet eine jährliche Gebühr; Gatekeeper verweigert bei unsignierten Paketen den ersten Start bis zum Öffnen über das Kontextmenü  
  _Ort:_ Teil 7 Frage 1
- **[mittel/api] macOS arm64 vs. x86_64 (CI-Runner)** — Ein auf Apple Silicon gebautes Paket startet auf keinem Intel-Gerät — daher zwei Macs in der Paketmatrix  
  _Ort:_ Teil 7 Frage 1
- **[niedrig/sonstiges] Paddle (Merchant of Record)** — Paddle wickelt den Verkauf ab  
  _Ort:_ 2.11 Stand
- **[niedrig/marktlage] SindriCAD** — SindriCAD stand binnen eines Tages in der Fachpresse  
  _Ort:_ 2.11
- **[mittel/api] Anthropic API, Ollama** — Agentenzugang über Anthropic mit eigenem Schlüssel oder Ollama lokal, ohne Hersteller-SDK  
  _Ort:_ 2.5 Stand
- **[niedrig/preis] Tinkercad, SelfCAD, Womp, SolidWorks for Makers, Onshape, FreeCAD, Alibre** — Tinkercad, SelfCAD, Womp, Thingiverse Customizer kostenlos; SolidWorks for Makers, Onshape, FreeCAD 1.x, Alibre im CAD-Feld  
  _Ort:_ Teil 1 Tabellen G1/G3

## Intern prüfbare Behauptungen (15)

- **[hoch]** 77 Operationen im Register, davon 16 aus der Bausteinbibliothek (erster Zähllauf kam fälschlich auf 61)  
  _Prüfen:_ Register über load_operations() vollständig laden und zählen; tests/test_website.py prüft die Zahl gegen das Register  
  _Ort:_ 2.1 Stand; 2.12 Fehlbefund
- **[hoch]** 16 Bausteine, Normteile in sechs Tabellen, 6 Materialien, 16 Druckerprofile, Selbstkalibrierung über Testkörper  
  _Prüfen:_ app/core/knowledge/ auslesen: Part-Register, Normteiltabellen, Materialprofile, Druckerprofile zählen  
  _Ort:_ 2.7 Stand
- **[mittel]** Neun Zwangsbedingungen plus reference, fünf Elementarten inkl. Spline, Ändern-Gruppe trim/extend/offset/mirror/project vorhanden  
  _Prüfen:_ app/core/sketch/ — Constraint-Typen und Elementarten im Code zählen  
  _Ort:_ 2.2 Stand
- **[mittel]** B-Rep-Kern über OpenCASCADE installiert und aktiv, mit fillet_edges, chamfer_edges, shell_exact, draft_faces, thread_exact, push_face und fünf Skizzen-Ops  
  _Prüfen:_ app/core/brep/ und Register prüfen; Suite fahren, ob B-Rep-Tests laufen oder sich abmelden  
  _Ort:_ 2.2 Stand
- **[mittel]** Kein gehosteter Backend — P11 offen  
  _Prüfen:_ ROADMAP.md Phase P11 nachschlagen; app/core/backends/ prüfen  
  _Ort:_ 2.4 Stand
- **[hoch]** Agenten-Suite mit 39 Referenzanfragen, Ergebnis 28 von 39 und 98 % der Werkzeugaufrufe, so auf der Website  
  _Prüfen:_ tools/run_agent_suite.py (kostet Geld) bzw. das festgehaltene Ergebnis; Website-Text und tests/test_website.py  
  _Ort:_ 2.5; Teil 4 Nachmessung W4
- **[mittel]** Schichtanalyse mit Orientierungssuche über bis zu 2000 Lagen, Einstellungsvorschläge als SettingAdvice, getrennt von G-Code-Werten  
  _Prüfen:_ app/core/slice/advise.py und Grenzwert im Code prüfen  
  _Ort:_ 2.6 Stand
- **[hoch]** Import STL, 3MF, OBJ, PLY, OFF, GLB, GLTF, STEP, SVG, DXF; Export STL, 3MF, OBJ, PLY, STEP — GLB kommt herein und geht nicht hinaus  
  _Prüfen:_ app/core/ingest/ und app/core/export/ (ExportFormat, _glb_bytes) prüfen — laut W7 inzwischen erledigt, die Aussage in 2.8 ist überholt  
  _Ort:_ 2.8 Stand vs. Teil 4 W7
- **[mittel]** 8 Beispielprojekte, sieben Touren, 103 Modelle durch die laufende Oberfläche ohne Stolperer geprüft  
  _Prüfen:_ Beispiel- und Tourdateien zählen; Prüfprotokoll der 103 Modelle suchen  
  _Ort:_ 2.9 Stand
- **[hoch]** app/i18n/locales/ enthält genau en.json — nur zwei Sprachen  
  _Prüfen:_ Verzeichnis app/i18n/locales/ auflisten — laut W3 und CLAUDE.md sechs Sprachen; die Aussage in 2.10 ist überholt  
  _Ort:_ 2.10 (widerspricht Teil 4 W3 und Teil 6 Punkt 2)
- **[hoch]** Sechs Sprachen, je 2279 Einträge, tests/test_translations.py mit 104 Fällen, Handbuch- und Website-Tests 460 Fälle  
  _Prüfen:_ Schlüssel je Katalog zählen; pytest tests/test_translations.py -q und Fallzahlen vergleichen  
  _Ort:_ Teil 4 W3; Teil 6 Punkt 2
- **[hoch]** Kein macOS-Paket — build.yml Job „Paket" nur [windows-latest, ubuntu-latest]  
  _Prüfen:_ .github/workflows/build.yml ansehen — laut Teil 7 inzwischen zwei Macs, .app-Bundle und ICNS; Signierung offen  
  _Ort:_ 2.10 vs. Teil 7 Frage 1
- **[mittel]** marketing/video/ enthält vier fertige Filme, deutsch und englisch, quer 1080p und hoch 1080×1920, mit eingesprochener Tonspur  
  _Prüfen:_ Ordner marketing/video/ auflisten  
  _Ort:_ 2.9 Nachtrag 13.08.2026; Teil 7 Frage 4
- **[hoch]** Offen: W1 Sichtbarkeit, W2 macOS-Signierung, W5 letzte Meile, W9 Modellkatalog; einziger Arbeitspunkt ist Ziehen-und-Ablegen sichtbarer machen, dazu Nachaufnahme der Handbuchbilder je Sprache  
  _Prüfen:_ ROADMAP.md gegen diese Punkte prüfen; app/images/ je Sprache auf aktuelle Bilder ansehen  
  _Ort:_ Teil 4 Tabelle; Teil 6 Punkte 2 und 5; Teil 7 Frage 3
- **[hoch]** Preisaufstellung: 14 Tage Test, 49 € zur Einführung, später 79 €, Einmalkauf, alle 1.x-Updates, Betrachterbetrieb nach Ablauf; Website-Überschrift führt mit Weg 1; Pressemitteilung durch tests/test_press_release.py gehalten  
  _Prüfen:_ Website-Preis- und Startseite lesen, app/core/activation/store.py; pytest tests/test_website.py tests/test_press_release.py -q  
  _Ort:_ 2.12 Stand; Teil 4 W4; Teil 7 Frage 4