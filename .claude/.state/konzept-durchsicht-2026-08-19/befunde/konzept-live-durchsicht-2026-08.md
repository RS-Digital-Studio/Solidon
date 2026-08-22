# Sondierung: .claude/konzept-live-durchsicht-2026-08.md

**Titel:** Konzept — was die Live-Durchsicht gegen Fusion und den ElegooSlicer ergeben hat
**Stand laut Dokument:** Datum: 5. August 2026. (mit Nachträgen „Stand 08.08.2026: abgearbeitet." und „nachgeprüft am Code, 14.08.2026")
**Zweck:** Festhalten, was eine Live-Messung der laufenden Anwendung gegen Autodesk Fusion und den ElegooSlicer ergeben hat — fünfzehn belegte Befunde mit Messwerten, Begründungen, Reihenfolge und Abgrenzung, inzwischen durchgängig mit Erledigt-Vermerken.

**Alterung:** 4/5 — Das Dokument hängt an zwei fremden Programmen in genau benannten Fassungen (Fusion 2704.1.36, ElegooSlicer 1.5.3.4), die schnell weiterziehen, und an einer Momentaufnahme des eigenen Codes samt Testzahl (2756 bzw. 2809) und Messwerten. Als historisches Messprotokoll bleibt es gültig; als Beschreibung des heutigen Zustands veraltet es mit jedem Umbau an Bausteinen, Wahrnehmung und Slicer-Übergabe — die Erledigt-Vermerke sind bereits nachträglich eingezogen worden.

## Gliederung

- 1. Was die Prüfung getragen hat
- 2. Die Befunde
- 3. Reihenfolge
- 4. Was nicht gebaut wird
- 5. Anhang: wie gemessen wurde

## Extern prüfbare Behauptungen (18)

- **[hoch/fassung] Autodesk Fusion** — Autodesk Fusion in der Fassung 2704.1.36 ist auf dieser Maschine installiert und dient als Maßstab  
  _Ort:_ Kopf des Dokuments, Abschnitt 5 (Anhang)
- **[hoch/fassung] ElegooSlicer** — ElegooSlicer 1.5.3.4 ist die installierte Fassung und „eine Fassung neuer als die, gegen die die Tabelle gebaut wurde“  
  _Ort:_ Kopf des Dokuments, Abschnitt 1, Abschnitt 5
- **[hoch/api] ElegooSlicer / OrcaSlicer-Kommandozeile** — Der ElegooSlicer kennt die Schalter arrange, ensure_on_bed, orient in seiner Bibliothek; --arrange 0 schaltet das eigene Anordnen ab  
  _Ort:_ B1
- **[hoch/funktionsumfang] ElegooSlicer / Orca-Familie** — Der Slicer verwirft übergebene Positionen und ordnet selbst an, solange --arrange 0 fehlt  
  _Ort:_ B1
- **[hoch/funktionsumfang] Elegoo Centauri Carbon 2** — Der Bettursprung der Maschine erzeugt einen Versatz von 1,5 mm in Y (extruder_offset)  
  _Ort:_ B1, Paket 2
- **[mittel/funktionsumfang] ElegooSlicer Profilbestand** — Die Profile heißen „Elegoo Centauri Carbon 2 0.4 nozzle“, „0.20mm Standard @Elegoo CC2 0.4 nozzle“, „Elegoo PETG @ECC2“; der Bestand umfasst 9849 lesbare Profile  
  _Ort:_ Abschnitt 1
- **[mittel/preis] ElegooSlicer Filamentprofil PETG** — Das Filamentprofil des Herstellers führt 30 €/kg, die von Solidon geschriebene Null überschreibt das  
  _Ort:_ B2
- **[mittel/api] OrcaSlicer/ElegooSlicer G-Code-Schlüssel** — Die G-Code-Schlüssel filament_cost und brim_width werden aus den übergebenen Werten geschrieben  
  _Ort:_ B2
- **[mittel/api] OrcaSlicer 3MF-Format** — Die Plattendaten der Orca-Familie liegen als plate-Blöcke in model_settings.config  
  _Ort:_ Abschnitt 4
- **[mittel/fassung] Open CASCADE STEP translator** — Der STEP-Header eines Fusion-Exports nennt „Open CASCADE STEP translator 7.9 1“  
  _Ort:_ C6
- **[mittel/funktionsumfang] Autodesk Fusion** — Fusion misst einen Zylinder Ø 50 mit „Radius: 25.00 mm“ und zeigt für den Netz-Prüfkörper drei Flächen statt einundfünfzig  
  _Ort:_ A1, C2
- **[hoch/funktionsumfang] Autodesk Fusion (Bohrungswerkzeug)** — In Fusion ist der angeklickte Punkt der Anfang der Bohrung, die Tiefe läuft ins Material  
  _Ort:_ A2
- **[niedrig/funktionsumfang] Autodesk Fusion** — Fusion führt Skizzen als eigene Gegenstände, die mehrere Features speisen; ein importiertes Teil heißt „Körper1“  
  _Ort:_ Abschnitt 4, C6
- **[mittel/api] OpenCASCADE / pythonocc (BRepBndLib)** — BRepBndLib.Add_s nimmt die Triangulation, wo eine existiert; AddOptimal_s misst die Flächen  
  _Ort:_ A1 samt Erledigt-Vermerk
- **[mittel/api] VTK / PyVista Picker-API** — vtkPointPicker trifft nur Eckpunkte, vtkCellPicker mit gesetzter Toleranz trifft Flächen; enable_point_picking(picker="point")  
  _Ort:_ C1
- **[mittel/api] trimesh** — trimesh.creation.cylinder erzeugt einen auf dem Ursprung zentrierten Zylinder  
  _Ort:_ A2
- **[niedrig/api] OpenCASCADE (TopAbs)** — TopAbs_REVERSED bzw. die Normalenrichtung zur Achse erlaubt die Unterscheidung Bohrung/Zapfen  
  _Ort:_ C3
- **[niedrig/api] OpenCASCADE (STEPControl_Writer)** — STEPControl_Writer bzw. Interface_Static erlauben das Setzen des PRODUCT-Namens  
  _Ort:_ C6

## Intern prüfbare Behauptungen (15)

- **[hoch]** Ausgangslage: pytest -m "not performance" grün, 2756 Tests in 267 s; nach C2 „die 2809 Tests“  
  _Prüfen:_ .venv\Scripts\python.exe -m pytest -q -m "not performance" — Testzahl und Laufzeit gegen 2756/2809 halten  
  _Ort:_ Kopf „Ausgangslage“, C2
- **[hoch]** Alle fünfzehn Funde sind erledigt (Stand 08.08. bzw. nachgeprüft 14.08.2026); offen blieb allein die fehlende Passung; ROADMAP führt sie unter „Live gegen Fusion und den ElegooSlicer“ einzeln mit Haken  
  _Prüfen:_ ROADMAP.md nach diesem Abschnitt durchsehen, Haken und offene Punkte abgleichen  
  _Ort:_ Kasten „Stand 08.08.2026“, Abschnitt 3
- **[hoch]** Solid.bounds kommt über BRepBndLib.AddOptimal_s aus der Form; Test test_the_bounding_box_comes_from_the_shape_not_from_the_triangles  
  _Prüfen:_ grep AddOptimal_s in app/core/brep/, Testnamen in tests/ suchen und laufen lassen  
  _Ort:_ A1
- **[hoch]** drill hat den Parameter anchor (mouth Vorgabe, centre); Migration 6 → 7; tests/data/projects/drilled_v6.p3d mit 31 276,89 gegen 31 231,74 mm³  
  _Prüfen:_ Registereintrag drill lesen, Migrationsliste in app/core/scene/ prüfen, drilled_v6.p3d und zugehörigen Test laufen lassen  
  _Ort:_ A2, Erledigt-Vermerk
- **[hoch]** Bausteinbibliothek auf Version 2 mit Änderungseintrag MOUTH_AT_ORIGIN; sechzehn Bausteine, drei geändert (magnet_pocket, keyhole, cable_gland), jetzt 150 / 343 / 309 mm³  
  _Prüfen:_ parts_version und Änderungsverlauf in app/core/knowledge/parts/ prüfen, registrierte Parts zählen, tests/test_parts.py laufen lassen  
  _Ort:_ A2, Erledigt-Vermerk
- **[mittel]** Der Satz über den wirkungslosen Schnitt steht in geom/boolean.py und greift für jeden abziehenden Weg  
  _Prüfen:_ app/core/geom/boolean.py lesen, Testfall Magnettasche in tests/test_parts.py  
  _Ort:_ A3
- **[mittel]** Die Passung entsteht in app/core/lid_flow.py statt in den Ops (Regel 3); tests/test_lid_flow.py hält es fest  
  _Prüfen:_ Existenz und Inhalt von app/core/lid_flow.py und tests/test_lid_flow.py prüfen  
  _Ort:_ B3, Abschnitt 3
- **[mittel]** gcode.compare läuft dreimal (Stützvolumen, material gegen metrics.grams, time gegen metrics.print_minutes), 15-%-Schwelle unverändert; ursprünglicher Einzelaufruf an main_window.py:1642  
  _Prüfen:_ grep compare( in app/ui/main_window.py — Zeilennummer und Zahl der Aufrufe prüfen  
  _Ort:_ B4
- **[mittel]** Solidons Schätzung 12 g / 46 min gegen G-Code 10,0 g / 37 min (−17 % / −20 %); slice/estimate.py braucht Arbeit  
  _Prüfen:_ handover-Lauf gegen dieselbe Dose wiederholen und Zahlen vergleichen; ROADMAP nach estimate.py durchsehen  
  _Ort:_ B4
- **[mittel]** History._outputs_for plant für takes_whole_scene ohne Eingaben keine Ausgänge; test_arranging_without_inputs_changes_nothing prüft result.complete  
  _Prüfen:_ grep _outputs_for und den Testnamen, Test laufen lassen  
  _Ort:_ B5
- **[mittel]** Der Viewport benutzt vtkCellPicker an beiden Stellen und gibt das Getroffene über objectPicked heraus  
  _Prüfen:_ grep vtkCellPicker / vtkPointPicker in app/ui/  
  _Ort:_ C1
- **[mittel]** Nach C2: Zylinder mit Bohrung 4 Merkmale statt 51, Würfel 6, Platte mit Stift 7, Achteck 10, Kugel keines; Trennwinkel dreißig Grad  
  _Prüfen:_ app/core/perceive/features.py lesen und den Merkmalstest laufen lassen  
  _Ort:_ C2
- **[mittel]** FeatureKind führt pin neben hole, face, edge_loop, thread; Mesh-Weg detect_pins, B-Rep-Weg hollow in _describe; Bauplan führt pin in derselben Zeile  
  _Prüfen:_ FeatureKind in app/core/ und §4.2/§21 in 3d-agent-bauplan.md prüfen  
  _Ort:_ C3
- **[mittel]** sketch_bar sitzt im mittleren Bereich als Teil des SketchPanel (P15 Etappe 3); Dialog und Modus benutzen dasselbe Panel  
  _Prüfen:_ app/ui nach SketchPanel/sketch_bar durchsehen, P15-Stand in ROADMAP.md  
  _Ort:_ C4
- **[niedrig]** first_run._printer_from_slicer() über chosen_machine und printer_for; hollow_object bekam einen Schalter „oben öffnen“; writer._step_bytes reicht den Objektnamen durch  
  _Prüfen:_ grep _printer_from_slicer in app/ui/first_run, Parameterschema hollow_object im Register, grep _step_bytes in app/core/export/  
  _Ort:_ C5, C7, C6