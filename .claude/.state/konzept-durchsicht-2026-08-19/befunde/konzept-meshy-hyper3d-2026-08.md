# Sondierung: konzept-meshy-hyper3d-2026-08.md

**Titel:** Konzept — Solidon3D gegen Meshy und Hyper3D Rodin (12.08.2026)
**Stand laut Dokument:** Stand 12.08.2026, vierte Fassung (Titelzeile: „12.08.2026"; Kopf nennt bereits eine „Fünfte Fassung"; Nachträge datiert 13.08.2026 und 14.08.2026)
**Zweck:** Vergleich von Solidon gegen die beiden KI-3D-Generatoren Meshy und Hyper3D Rodin in sechs Bereichen (Erzeugen, Druckbarkeit, Oberfläche, Handbuch, Schnittstelle, Preis), mit sechzehn nummerierten Befunden und einer Schlusstabelle, was davon umgesetzt wurde.

**Alterung:** 5/5 — Das Dokument ruht fast vollständig auf zwei bewegten Größen: fremden Preis-, Funktions- und API-Angaben zweier schnell wachsender KI-Dienste (Guthabenpreise, Tarifstufen, Auto-Split-Einschränkungen, Endpunktumfang, Nutzerzahlen, angekündigte Werkzeuge) und dem eigenen Codestand in Zählungen (77 Operationen, 16 Bausteine, 11 Regeln, 40 Normteilmaße, Zeichenzahlen des Handbuchs, Kontrastwerte). Beides veraltet in Wochen. Das Dokument widerspricht sich stellenweise schon selbst: Kopf nennt „Fünfte Fassung", Fußzeile „vierte Fassung"; 4.3/B16 nennen Kontraste, die Teil 10 bereits als geändert meldet (1,10 → 1,45, Trennlinie 1,43 → 2,30); 4.2.3 nennt 90 px Leerraum, Teil 10 nennt 189 → 26 px; die MCP-Doku-Lücke aus 3.6 gilt laut Teil 10 als geschlossen.

## Gliederung

- Teil 1 — Was die beiden heute sind
- Teil 2 — Erzeugen: der Bereich, den wir verlieren
- Teil 3 — Wo die Namen gleich sind: sechs Paare im Detail
- Teil 4 — Design und Oberfläche
- Teil 5 — Handbuch gegen docs.meshy.ai
- Teil 6 — Preis, Eigentum und Dauer
- Teil 7 — Können wir mithalten?
- Teil 8 — Was die späteren Durchgänge korrigiert haben
- Teil 9 — Befunde
- Was ausdrücklich nicht folgt
- Abnahme
- Teil 10 — Was daraus wurde (12.08.2026)

## Extern prüfbare Behauptungen (20)

- **[hoch/preis] Meshy (meshy.ai) Preismodell** — Frei: 100 Guthaben/Monat, Ergebnis CC BY 4.0; Pro 20 $/M (1.000 Guthaben), Premium 40 $, Ultra 100 $, Studio 70 $ (+10 $ je Mitglied), Enterprise auf Anfrage; ab Bezahlplan gehören die Ergebnisse dem Nutzer  
  _Ort:_ 1.1 Tabelle, Zeile Geschäftsmodell
- **[hoch/recht] Meshy Asset Retention** — Erzeugte Dateien werden nach drei Tagen gelöscht, außer bei Enterprise („Asset Retention")  
  _Ort:_ 1.1, Absatz „Ein Detail mit Gewicht"; Teil 6; 3.6
- **[mittel/marktlage] Meshy Nutzerzahlen** — Meshy meldet 100 Mio. erzeugte Modelle, 12 Mio. Nutzer, 10 Mio. Besuche im Monat, G2 und Trustpilot je 4,8  
  _Ort:_ 1.1 Tabelle, Zeile Größe; Teil 7
- **[hoch/funktionsumfang] Meshy Funktionsumfang** — Meshy-Funktionsumfang: Auto Split, Mehrfarbdruck bis 16 Farben mit 3MF-Ausgabe, Druckbarkeitsprüfung, Auto-Reparatur, Übergabe an acht Slicer, Auto-Rigging, über 600 Bewegungsvorlagen, HD-Textur in 4K  
  _Ort:_ 1.1 Tabelle
- **[mittel/funktionsumfang] Meshy Ökosystem/Integrationen** — Meshy-Erweiterungen für Bambu Studio, Creality Print, OrcaSlicer, Cura, Elegoo Slicer, Lychee, Snapmaker, Flash Studio sowie Blender, Unity, Unreal, Godot, Maya, 3ds Max, Roblox; Veröffentlichen nach MakerWorld, Printables, Thingiverse; Druckservice mit Versand  
  _Ort:_ 1.1 Tabelle, Zeile Ökosystem
- **[hoch/api] Meshy API / MCP-Server** — Meshy betreibt einen eigenen MCP-Server; REST mit Playground, Webhooks, SSE, Ratenbegrenzung, Changelog  
  _Ort:_ 1.1 Tabelle; 3.6; Teil 8 Punkt 2
- **[niedrig/api] Meshy Creative Lab** — Meshys Kreativlabor liefert Fertigteile (Schlüsselanhänger, Magnet, Figur, Vinylfigur, Klemmbaustein-Figur, Lampe, Tastenkappe); der Schlüsselanhänger nimmt badge_shape, size_mm (0–400), relief_height_mm (0–20), base_thickness_mm  
  _Ort:_ 1.1 Tabelle, Zeile Kreativlabor
- **[hoch/preis] Hyper3D Rodin Preismodell** — Rodin: Frei 0 $ (Einzelkauf 1,50 $/Guthaben), Creator 30 $/M (~60 Modelle), Business 120 $/M (~416 Modelle, API 120–240 Anfragen/Minute, 4K-Texturen), Enterprise mit privater Installation und eigenem LoRA, Bildungstarif  
  _Ort:_ 1.2 Tabelle, Zeile Geschäftsmodell; Teil 6
- **[hoch/funktionsumfang] Hyper3D Rodin Gen-2.5** — Rodin Gen-2.5 nennt ~4 s für die Geometrie, ~5 s für das ganze Modell, über 10 Mio. Polygone; fünfstufiger Aufwandsregler ~4 s bis ~80 s  
  _Ort:_ 1.2 Tabelle; 4.1; 4.2.5
- **[hoch/funktionsumfang] Hyper3D Rodin ControlNet / OmniCraft** — Rodin bietet 3D ControlNet (Hüllquader, Voxel, Punktwolke), iteratives Aufteilen, partielle Bearbeitung, Smart Low-Poly, OmniCraft-Werkzeugkasten, SSO über SAML 2.0  
  _Ort:_ 1.2 Tabelle; Teil 2; B10
- **[mittel/funktionsumfang] Hyper3D Rodin 3D-Druck** — Rodin hat keine Druckbarkeitsprüfung, keine Slicer-Anbindung, keinen Mehrfarbdruck; 3D-Druck nur als Anwendungsfall plus STL-Export  
  _Ort:_ 1.2 Tabelle, Zeile 3D-Druck
- **[hoch/api] Meshy API analyze-printability** — Meshys analyze-printability prüft nur wasserdicht, Volumen, nicht-mannigfaltige Kanten, degenerierte Flächen, Löcher plus Gesamturteil; ausdrücklich nicht Wandstärke, Überhänge, dünne Teile, Stützbedarf; Endpunkt kostenlos  
  _Ort:_ 3.1; B1
- **[hoch/funktionsumfang] Meshy Auto Split** — Auto-Split-Doku unter /en/webapp/guides/3d-model/auto-split; Vorschau in ~40 Sekunden; Schnitt folgt der Form statt einer Ebene; Schnittflächen automatisch verschlossen  
  _Ort:_ 3.2; B13
- **[hoch/funktionsumfang] Meshy Auto Split FAQ / Einschränkungen** — Auto Split unterstützt derzeit nur unstrukturierte Entwurfsmodelle, die mit Meshy 6 erzeugt wurden; geteilte Teile werden ohne Farbinformation exportiert; Verbindungen sind kein Teil des Werkzeugs  
  _Ort:_ 3.2 Tabelle „Ihre Aussage / Folge"
- **[hoch/api] Meshy API multi-color-print** — Meshys multi-color-print: Eingang GLB oder FBX über URL oder Aufgaben-ID, max_colors 1–16 mit Vorgabe 4, Ausgang 3MF, 10 Guthaben je Lauf  
  _Ort:_ 3.3 Tabelle
- **[mittel/api] Meshy MCP-Server Grenzen** — Meshy MCP: 20 Anfragen/s, 10–100 gleichzeitige Aufgaben je Tarif, 1–50 Guthaben je Aufruf, Verkettung über input_task_id  
  _Ort:_ 3.6 Tabelle
- **[mittel/funktionsumfang] docs.meshy.ai** — Meshy-Doku in vier Pfaden (Web App, API, Plugins, 3D Printing), nur Englisch, Funktionsreferenz von Hand gepflegt mit ~20 Funktionen, Quick Start ohne Bilder, Changelog vorhanden  
  _Ort:_ Teil 5 Tabelle
- **[mittel/funktionsumfang] Meshy 3D Printing Academy** — Meshy betreibt eine 3D-Druck-Akademie mit fünf Modulen und 27 Lektionen (Erste Schritte 5, Mit Meshy erstellen 9, Materialien 5, Slicing 6, Fehlersuche 2)  
  _Ort:_ 5.2; Teil 7; Teil 8 Punkt 6
- **[hoch/funktionsumfang] Meshy Free Tools / STL Repair** — Meshy liefert fünf kostenlose Browser-Werkzeuge ohne Konto (STL-Reparatur, Dateikonverter, Online-Betrachter, Dateikompressor, 3D-Textgenerator); die STL-Reparatur nimmt STL/OBJ/GLB bis 100 MB, braucht etwa eine Minute, kostet nichts; acht weitere sind als Fahrplan angekündigt, darunter ein KI-Steinteile-Generator  
  _Ort:_ 5.3; B15; 3.7
- **[mittel/marktlage] Slicer-Familien und Wettbewerber (OrcaSlicer, PrusaSlicer, Cura, Netfabb, Magics, Tripo)** — Die Orca-Familie umfasst OrcaSlicer, Bambu Studio, Creality Print und ElegooSlicer; PrusaSlicer und CuraEngine stehen daneben — Meshy vergleicht sich mit Netfabb, Magics, Blender, Tripo, Trellis 2, Hunyuan3D  
  _Ort:_ 3.5; 5.3

## Intern prüfbare Behauptungen (15)

- **[hoch]** „alle 77 Operationen" — das Register hat 77 Ops (über load_operations(), ohne den Aufruf fehlen sechzehn)  
  _Prüfen:_ .venv\Scripts\python.exe -c "from app.core.registry import load_operations, ...; load_operations(); len(all_ops())" bzw. tests/test_registry_consistency.py; Abschnitte Methode, 3.7, Teil 5  
  _Ort:_ Methode (Kopf), 3.7, Teil 5 Tabelle, Schlussabsatz
- **[hoch]** 16 Bausteine mit Features; 18 Bausteine-Ops für Verbindungen und Normteile  
  _Prüfen:_ Register der Parts auslesen (app/core/knowledge/parts/), tests/test_parts.py  
  _Ort:_ Methode; 3.7 Tabelle
- **[hoch]** 6 Materialprofile, 16 Druckerprofile, 40 Normteilmaße in acht Tabellen, 11 Konstruktionsregeln (Version 2)  
  _Prüfen:_ app/core/knowledge/*.toml zählen: materials.toml, printers.toml, standards.toml, rules.toml  
  _Ort:_ 5.2 Aufzählung; B4
- **[mittel]** Handbuch: 20 geschriebene Seiten + 15 erzeugte Referenzseiten, ~110.000 Zeichen, ~19.600 Wörter, 32 Verweise, 25 Abbildungen, 6 Bildschirmfotos je Sprache, zwei Sprachen vollständig  
  _Prüfen:_ manual.pages() auszählen; app/images/ je Sprache; tools/make_manual.py  
  _Ort:_ Teil 5 Tabelle; 4.2
- **[hoch]** Handbuchseite zur Fernsteuerung hat 980 Zeichen ohne Werkzeugliste; kein Changelog, keine Prompting-Anleitung, keine Anwendungsfall-Anleitungen  
  _Prüfen:_ manual.pages() nach der MCP-Seite, Zeichenzahl; Teil 10 sagt B6 sei inzwischen erzeugt — Widerspruch prüfen  
  _Ort:_ 3.6 Tabelle; Teil 5 Tabelle; B6
- **[hoch]** theme.py:30 setzt _SELECTION = "#f0a54a"; Kontrast 7,27 gegen die Fensterfarbe; Panel gegen Fenster 1,10, Zebrazeile 1,16, Viewport-Verlauf 1,21, Trennlinie 1,43; sieben Flächenrollen zwischen 1,3 % und 5,0 % Helligkeit  
  _Prüfen:_ app/ui/theme.py und style.py lesen, Kontraste nachrechnen; tests/test_accessibility.py — Teil 10 meldet bereits 1,45 bzw. 2,30, also überholt  
  _Ort:_ 4.3; B16
- **[hoch]** split_plane und split_pinned schneiden nur an einer Ebene; autosplit.py holt die Normale aus AXIS_NORMALS, die Suche kennt drei Achsen (nachgesehen 14.08.2026)  
  _Prüfen:_ grep AXIS_NORMALS in app/core/geom/autosplit.py; SectionPlane.normal in slice/  
  _Ort:_ 3.2; B13 beide Fassungen; Teil 10
- **[mittel]** handover.py kennt drei Profilfamilien prusa, orca, cura (slicer_keys.py:25) und liest den Profilbestand der installierten Anwendung  
  _Prüfen:_ app/core/export/slicer_keys.py Zeile 25, slicer_profiles.py  
  _Ort:_ 3.5
- **[mittel]** Gemessene Kette am 12.08.2026: read_mesh(glb) → 1.304 Dreiecke, 0 Materialslots; to_slots mit 3 Filamenten → 3 Slots; export_bytes 3mf → 13.098 Bytes, verlustfrei zurückgelesen  
  _Prüfen:_ Messung nachfahren mit einer GLB aus tests/data/; Abnahmepunkt 2 verlangt genau diesen Test  
  _Ort:_ 3.4
- **[mittel]** Hy3DMeshGenerator nimmt nur model, image, steps, guidance_scale, seed, attention_mode — keine Formvorgabe  
  _Prüfen:_ app/core/backends/data/ Workflow-JSON lesen  
  _Ort:_ B10
- **[mittel]** Der Operationsdialog hat rund 90 Pixel Leerraum über dem Beschreibungssatz  
  _Prüfen:_ Teil 10 nennt bereits 189 → 26 px — also im Dokument selbst widersprüchlich und überholt; am laufenden Fenster messen  
  _Ort:_ 4.2.3; B12; Teil 10
- **[hoch]** Solidon 1.0 ist noch nicht erschienen (Website: „Version 1.0 erscheint 2026"); Preis 49 € einmalig, später 79 €, 14 Tage vollständig testen  
  _Prüfen:_ website/ Preisseite und Startseite lesen; app/core/activation/store.py (Demo-Frist)  
  _Ort:_ Einordnung vorweg; Teil 6; B7
- **[hoch]** Teil 10 meldet B1, B3–B9, B11, B12, B14–B16 als umgesetzt, B2 als teilweise, B13 als offen  
  _Prüfen:_ ROADMAP.md und Commit-Verlauf gegen die Zeilen prüfen; Website- und Handbuchseiten öffnen  
  _Ort:_ Teil 10 Tabelle
- **[mittel]** Offen laut Teil 10: Bildschirmfoto einer Analysekarte fehlt im Abbildungskatalog; Website läuft mit 1456 px in 1265 px über; Statuszeile überlappt „Keine Auswahl" und Demo-Hinweis  
  _Prüfen:_ app/core/figures.py Katalog prüfen; Website im Fenster messen; Statuszeile im laufenden Programm ansehen  
  _Ort:_ Teil 10, Absatz „Was offen bleibt"
- **[mittel]** Verweis auf konzept-wettbewerb-2026-08.md (11.08.), konzept-bedienung.md und konzept-organische-modellierung-2026-08.md §17 (Entscheidung P16, Figuren gehören zum Kundenkreis)  
  _Prüfen:_ Die drei Konzeptdateien im Repository lesen; ROADMAP.md nach P16  
  _Ort:_ Kopf „Verhältnis zu den bestehenden Konzepten"; Nachtrag 13.08.2026 in B13