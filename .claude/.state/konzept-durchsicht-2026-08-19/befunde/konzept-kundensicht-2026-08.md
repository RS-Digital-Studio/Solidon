# Sondierung: konzept-kundensicht-2026-08.md

**Titel:** Konzept — Solidon3D aus Kundensicht, vollständig nachgefahren
**Stand laut Dokument:** Stand 08.08.2026. (Kopfzeile: „Aus zehn Bedienläufen am echten Programm, 8. August 2026"; Nachtrag: „08.08.2026, derselbe Tag")
**Zweck:** Bestandsaufnahme der Oberfläche aus Kundensicht: zehn gemessene Bedienläufe am laufenden Programm, daraus zehn nummerierte Befunde mit Zahlen, eine Gegenliste dessen, was trägt, eine Reihenfolge zur Abarbeitung — und ein Nachtrag, der die noch am selben Tag erfolgten Behebungen mit Vorher-/Nachher-Messwerten belegt.

**Alterung:** 5/5 — Momentaufnahme eines laufenden Programms an einem einzigen Tag, die fast vollständig aus Zählungen (77 Operationen, 127 Menüeinträge, 23 Bausteine, 1986 Katalogeinträge, 3168 Tests), Millisekunden- und Pixelmessungen sowie datei- und zeilengenauen Quelltextverweisen besteht. Jede dieser Zahlen verschiebt sich mit dem nächsten Commit; die Zeilennummern sind durch die im Nachtrag genannten Behebungen schon am Erstellungstag angreifbar. Das Dokument altert zudem gegen sich selbst: Teil 1 bis 4 beschreiben Befunde und eine Arbeitsreihenfolge, die der Nachtrag darunter bereits als erledigt meldet — wer nur den vorderen Teil liest, bekommt ein falsches Bild vom Stand. Extern altert weniger, aber die Slicer-Profilnamen, die Elegoo-Profile und das rtree-Verhalten hängen an fremden Fassungen.

## Gliederung

- Konzept — Solidon3D aus Kundensicht, vollständig nachgefahren (Dokumenttitel)
- Teil 1 — Die drei Befunde, aus denen die Arbeit folgt
- Teil 2 — Weitere Befunde
- Teil 3 — Was trägt
- Teil 4 — Vorschlag zur Reihenfolge
- Anhang — wie gemessen wurde
- Nachtrag — was daraus wurde (08.08.2026, derselbe Tag)

## Extern prüfbare Behauptungen (12)

- **[mittel/funktionsumfang] ElegooSlicer (OrcaSlicer-Familie)** — ElegooSlicer wird als Orca-Familie erkannt; sein Bestand liefert 1001 Maschinen, 7 Prozesse, 42 Filamente  
  _Ort:_ Teil 3, „Die Druckeinstellungen finden von selbst das Richtige" (Z. 338–342)
- **[mittel/funktionsumfang] Elegoo Centauri Carbon 2 (Drucker- und Filamentprofile)** — Vorbelegt sind die Profile „Elegoo Centauri Carbon 2 0.4 nozzle", „0.20mm Standard @Elegoo CC2", „Elegoo PETG @ECC2"  
  _Ort:_ Teil 3 (Z. 338–341)
- **[mittel/funktionsumfang] OpenSCAD, ElegooSlicer, Ollama, ComfyUI** — Vier externe Programme werden bei der Erstinbetriebnahme erkannt: OpenSCAD, ElegooSlicer und Ollama gefunden, ComfyUI fehlt  
  _Ort:_ Teil 3, „Die Erstinbetriebnahme ist fertig" (Z. 310–314)
- **[hoch/funktionsumfang] rtree (Python-Paket) / libspatialindex** — rtree greift „reproduzierbar daneben — eine Zugriffsverletzung in etwa jedem zwanzigsten Lauf"; trimesh benutzt rtree für die Nachbarschaftssuche, und es gibt indexfreie Wege für den nächsten Oberflächenpunkt  
  _Ort:_ 1.3 (Z. 158–180)
- **[hoch/api] trimesh (trimesh.proximity.on_surface)** — 14,6 von 15,9 s lagen in trimesh.proximity.on_surface; 113168 Indexanfragen für eine Beschriftung  
  _Ort:_ 1.2 Kastenzitat (Z. 110–112), Nachtrag (Z. 419)
- **[mittel/funktionsumfang] trimesh, manifold3d** — Die acht Sekunden beim ersten Öffnen sind das Nachladen von trimesh, manifold3d und den Netzbibliotheken  
  _Ort:_ 2.6 (Z. 286–289)
- **[mittel/sonstiges] STEP (ISO 10303) / OpenCASCADE** — STEP hält Flächen und Kanten fest, ein Netz hat keine — STEP-Export aus Netzen ist grundsätzlich unmöglich (NeedsSolidError)  
  _Ort:_ 2.5 (Z. 259–276)
- **[mittel/funktionsumfang] Autodesk Fusion, Onshape (Tastenkürzelbelegung)** — Das Kürzelschema „Wie Fusion und Onshape" bringt elf Ein-Tasten-Kürzel für Umsteiger aus einem CAD  
  _Ort:_ Nachtrag, „Nicht geändert: die Tastenkürzel" (Z. 442–446)
- **[niedrig/marktlage] CAD-Programme allgemein (Marktvergleich)** — Für ein Programm, das mit CAD verglichen wird, sind sechs Kürzel wenig — dort ist die Tastatur der schnelle Weg  
  _Ort:_ 2.7 (Z. 294–298)
- **[mittel/api] VTK (vtkCellPicker, vtkRenderWindowInteractor)** — Klicks laufen über den VTK-Interactor (SetEventPosition + InvokeEvent("LeftButtonPressEvent")), also dieselbe Stilklasse wie eine echte Maus; der vtkCellPicker trägt  
  _Ort:_ Teil 3 (Z. 322–326), Anhang (Z. 391–395)
- **[mittel/api] Qt / PySide6 (QScreen.grabWindow, QWidget.grab, QMenu.exec, offscreen-Plattform)** — screen().grabWindow() erfasst den OpenGL-Viewport, widget.grab() nicht; unter offscreen hat Qt auf dieser Maschine null Schriftfamilien; QMenu.exec() blockiert wie ein modaler Dialog, ist aber keiner  
  _Ort:_ Anhang (Z. 384–398)
- **[niedrig/api] CPython (setobject.c)** — Folgefehler nach der rtree-Zugriffsverletzung: „SystemError: setobject.c:2676: bad argument to internal function"  
  _Ort:_ 1.3 (Z. 151–156)

## Intern prüfbare Behauptungen (15)

- **[hoch]** Das Register führt 77 Operationen, alle in Menüs, keine tiefer als zwei Ebenen; 72 mit Dialog, 5 ohne  
  _Prüfen:_ @register_op-Einträge zählen (app/core/registry) und tests/test_registry*.py; Menütiefe in app/ui/main_window.py  
  _Ort:_ Kopf (Z. 33–34), 2.7 (Z. 294), Teil 3 (Z. 317–320)
- **[hoch]** Sechs von 77 Operationen tragen ein Tastenkürzel; 2.7 bleibt als einziger Punkt offen, und zwar als Design-Entscheidung  
  _Prüfen:_ shortcut-Felder im Op-Register zählen; app/ui/shortcut_schemes.py; Funde-Abschnitt in ROADMAP.md  
  _Ort:_ Kastentabelle (Z. 26), 2.7, Nachtrag (Z. 442–446)
- **[mittel]** Neun Menüs mit 127 Einträgen, acht Beispiele auf dem Startbildschirm, sieben Analysekarten, 14 Fehlerklassen mit je ein bis vier Handlungsvorschlägen  
  _Prüfen:_ Menüaufbau in app/ui/main_window.py zählen; Beispielprojekte im Auslieferungsordner; Analysekarten in app/core/perceive; app/core/errors.py und der Fehler-Test  
  _Ort:_ Kopf „Durchgegangen" (Z. 32–41), Teil 3 (Z. 333–350)
- **[mittel]** Bausteinkatalog mit 23 Bausteinen, Skizzeneditor mit 24 Werkzeugen, Handbuch mit 33 Kapiteln, Tastenkürzel-Fenster mit 42 Gruppen  
  _Prüfen:_ @register_part-Einträge zählen; Kapitelliste in app/core/manual.py; Werkzeugliste im Skizzeneditor  
  _Ort:_ Teil 3 (Z. 352–357)
- **[hoch]** 1986 Einträge im englischen Katalog, keiner leer; kein Registertext ohne englische Entsprechung  
  _Prüfen:_ .venv\Scripts\python.exe -m pytest tests/test_translations.py -q und Einträge in app/i18n/locales/en zählen — der Katalogbestand umfasst inzwischen en, es, fr, it, pt  
  _Ort:_ Teil 3, „Die Sprache ist vollständig" (Z. 344–346)
- **[hoch]** Zeilengenaue Quelltextverweise: panels.py:981 (MAX_ROWS = 12), panels.py:1018 (fit_to_rows), panels.py:756, overlay.py:160 (natural_height), main_window.py:548, main_window.py:2665, features.py:261, mesh.py:169, print_settings_dialog.py:763  
  _Prüfen:_ Die genannten Zeilen direkt öffnen; nach den im Nachtrag genannten Behebungen sind Nummern verschoben oder der Code (etwa MAX_ROWS) entfernt  
  _Ort:_ 1.1, 1.3, 2.1, 2.2, 2.3
- **[hoch]** Alle Befunde 1.1 bis 2.6 sind behoben, belegt durch die Commits b017fde, b3de01e, 0c80417, 06e5e56, 22ce4c6, f49a7fa  
  _Prüfen:_ git show für jeden Hash; danach prüfen, ob spätere Commits dieselben Stellen erneut geändert haben  
  _Ort:_ Kastentabelle (Z. 15–30), Nachtrag
- **[hoch]** Nachher-Messwerte: Parameteränderung 1,47 s, erstes Öffnen 1,55 s, 1180 rtree-Anfragen je Auswertung, 0 Fehlgriffe in 60 Läufen, Prüfbericht 322 px ohne Rollbalken, Objektbaum 873 px  
  _Prüfen:_ .venv\Scripts\python.exe -m pytest -q -m performance (Budget §31) und erneutes Nachmessen am laufenden Fenster unter echter Qt-Plattform  
  _Ort:_ Nachtrag, Tabelle (Z. 411–424)
- **[mittel]** Kontextmenü: 6 Einträge am Merkmal (vier davon aus applies_to), 7 am Körper nach Kategorie gruppiert  
  _Prüfen:_ object_tree.context_menu() aufrufen bzw. den zugehörigen Test lesen und Einträge zählen  
  _Ort:_ 2.1, Nachtrag (Z. 421–422)
- **[mittel]** Nur noch ein Beispiel öffnet mit Warnung (das Reparatur-Beispiel, gewollt); dose-mit-deckel.p3d hat sieben Operationen und zwei Körper  
  _Prüfen:_ Alle mitgelieferten Beispielprojekte öffnen und die Prüfbericht-Befunde zählen; Op-Zahl in dose-mit-deckel.p3d nachsehen  
  _Ort:_ 1.2 (Z. 116), 2.4, Nachtrag (Z. 424)
- **[mittel]** Vier von fünf Klicks auf verschiedene Flächen treffen ihr Merkmal; der frühere Befund aus konzept-bedienung.md ist erledigt  
  _Prüfen:_ konzept-bedienung.md gegenlesen; Pick-/Zuordnungstests in tests/ fahren  
  _Ort:_ Teil 3 (Z. 322–326)
- **[mittel]** Analysekarten je 1,41–1,51 s (§31 erlaubt 3 s), Schichtenvorschau 2,67 s bei 200 Schichten, Auto Split 1,77 s, Handbuch 2,5 s  
  _Prüfen:_ Leistungstests -m performance; Bauplan §31 über die Skill „bauplan" gegenlesen  
  _Ort:_ Teil 3 (Z. 333–336, 352–357)
- **[hoch]** Stand danach: 3168 Tests grün, ruff und mypy sauber  
  _Prüfen:_ Skill /pruefen bzw. pytest -q, ruff check, ruff format --check, mypy — Testzahl vergleichen  
  _Ort:_ Nachtrag, Schlusszeile (Z. 455)
- **[niedrig]** test_the_slider_reports_a_factor wurde umgestellt; die Entprellung beträgt 120 ms  
  _Prüfen:_ Test im Bestand suchen und prüfen, ob Name und Entprellzeit noch stimmen  
  _Ort:_ Nachtrag, „Nebenbei aufgefallen" (Z. 448–453)
- **[hoch]** Teil 4 nennt sechs Punkte als noch zu leistende Arbeit in vorgeschlagener Reihenfolge  
  _Prüfen:_ Gegen den Nachtrag derselben Datei und ROADMAP.md halten — der Nachtrag meldet fünf dieser sechs Punkte bereits als erledigt, Teil 4 widerspricht damit dem eigenen Dokument  
  _Ort:_ Teil 4 (Z. 361–378)