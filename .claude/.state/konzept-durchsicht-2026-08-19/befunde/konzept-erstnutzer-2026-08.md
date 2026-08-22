# Sondierung: konzept-erstnutzer-2026-08.md

**Titel:** Konzept — Solidon3D mit den Augen eines Anfängers
**Stand laut Dokument:** Stand 14.08.2026.
**Zweck:** Bestandsaufnahme aus dreizehn Bedienläufen am laufenden Programm plus vier Website-Läufen: Was sieht jemand, der Solidon zum ersten Mal öffnet — mit Befundliste, Messwerten, Belegbildern und Abarbeitungsstand.

**Alterung:** 5/5 — Das Dokument ist eine Momentaufnahme einer laufenden Anwendung: Zeilennummern in einem Dutzend Quelldateien, Zählungen (83 Operationen, 127 Menüzeilen, 22 Fensterbefehle, elf englische Docstrings), Pixelmessungen und eine Statustabelle mit Commit-Kürzeln. Die Kopftabelle erklärt vierzehn Befunde bereits selbst für behoben, das heißt: der Fließtext darunter beschreibt zum Teil einen Zustand, den es nicht mehr gibt. Jede Codeänderung an app/ui/ verschiebt Zeilennummern, jede neue Op die Zählung, jeder neue Sprachkatalog die Aussage über die englische Oberfläche (inzwischen sechs Sprachen statt zwei). Wer das Dokument heute liest, muss praktisch jede Zahl nachmessen.

## Gliederung

- Teil 1 — Die drei, die der erste Eindruck sind
- Teil 2 — Übersichtlichkeit auf einem großen Bildschirm
- Teil 3 — Wo die Menüs einen Anfänger im Stich lassen
- Teil 4 — Kleinigkeiten, jede einzeln billig
- Teil 5 — Was die zweite Runde fand
- Teil 6 — Was die zweite Runde entlastet hat
- Was gemessen wurde

## Extern prüfbare Behauptungen (10)

- **[mittel/api] Ollama / qwen3:14b** — Der Chat zeigt beim Start die Zeile „Modell: ollama:qwen3:14b" — dieses Modell ist die Vorbelegung  
  _Ort:_ Teil 2, Abschnitt 2.2
- **[hoch/preis] Solidon3D — Preisseite der öffentlichen Website** — Die Website nennt drei Preisstufen 0 / 49 / 79 €, deutsch als „49 €", englisch als „€49"  
  _Ort:_ Teil 6, „Die Preise stehen in beiden Sprachfassungen"; Befund 4.6
- **[niedrig/marktlage] Solidon3D — Preisdarstellung mobil** — „Der Preis ist die erste Frage, die ein Interessent hat" — Marktaussage, die den Befund 4.6 trägt  
  _Ort:_ Teil 4, Befund 4.6
- **[hoch/funktionsumfang] CSS overflow-x: clip — Browserverhalten, geprüft im installierten QtWebEngine** — `document.documentElement.style.overflowX = 'clip'` setzt scrollX auf allen drei Seiten auf 0; `body { overflow-x: clip }` greift nicht, weil der Rollbereich dem Wurzelelement gehört  
  _Ort:_ Teil 1, Befund 1.3
- **[mittel/fassung] QtWebEngine / PySide6** — Die Website-Läufe fanden im „installierten QtWebEngine" statt — dessen Rendering gilt als Referenz für die Messwerte  
  _Ort:_ Kopfabschnitt, Zeile 2–3
- **[niedrig/funktionsumfang] Qt / PySide6 — Elision von Menütexten** — „…Nothing is lost here: und…" ist Qts eigene Kürzung von „undo" — kein deutscher Resttext  
  _Ort:_ Teil 6, „Die englische Oberfläche ist vollständig"
- **[mittel/api] Model Context Protocol (MCP)** — Die Einstellungen bieten einen Haken „Fernsteuerung über MCP zulassen" samt Port; „MCP" steht dort unerklärt  
  _Ort:_ Teil 4, Befund 4.2
- **[mittel/funktionsumfang] Slicer-Profilbestand (externer Slicer, Übergabe über handover.py)** — Der Druckdialog hat einen Bereich „Profile des Slicers" mit sechs Auswahlfeldern (Drucker, Grundprofil, Filament, Körper, Schrift, Slot 3)  
  _Ort:_ Teil 5, Befund 5.7
- **[niedrig/funktionsumfang] OpenSCAD** — „OpenSCAD-Teil anheften" ist ein Menüeintrag unter Grundformen — setzt eine externe OpenSCAD-Installation voraus  
  _Ort:_ Teil 3, Befund 3.2
- **[hoch/recht] Rechtstexte der Solidon3D-Website (deutsches Recht: Impressumspflicht, Widerrufsrecht)** — Die Website führt Impressum, AGB, EULA, Widerruf und Datenschutz vollständig gegliedert  
  _Ort:_ Teil 6, „Die Website ist handwerklich sauber"

## Intern prüfbare Behauptungen (15)

- **[hoch]** 83 registrierte Operationen; von 77 auf 83 gewachsen  
  _Prüfen:_ Register auszählen: `.venv\Scripts\python.exe -c "from app.core.registry import ...; len(all_ops())"` bzw. tests/test_registry*.py; Vergleich mit dem Handbuch-Referenzteil  
  _Ort:_ Teil 5, Befund 5.6 und Teil 6
- **[hoch]** `window_commands()` führt 22 Fensterbefehle, fünf davon ohne Kürzel; nur sechs Operationen tragen ein Kürzel  
  _Prüfen:_ `window_commands()` in app/ui/main_window.py aufrufen und Kürzel zählen; Registerkonsistenztest in tests/  
  _Ort:_ Teil 5, Befund 5.6
- **[mittel]** 127 Menüeinträge in drei Szenenzuständen abgefragt; unter *Ändern* sind alle 34 Einträge aus, *Objekt* ganz aus  
  _Prüfen:_ Menübaum über app/core/registry/surfaces.py:menu_tree erneut auszählen; Zustandsabfrage im laufenden Fenster wiederholen  
  _Ort:_ Teil 2, Befund 2.3; Abschnitt „Was gemessen wurde"
- **[hoch]** Elf englische Docstrings in `app/` plus fünf in `tests/`, mit Datei und Zeilennummer je Stelle  
  _Prüfen:_ Syntaxbaum-Lauf über app/ und tests/ wiederholen; die genannten Zeilennummern (z. B. app/ui/first_run.py:95, app/core/geom/measure.py:84) direkt nachsehen — laut Kopftabelle inzwischen „jetzt null"  
  _Ort:_ Teil 5, Befund 5.8; Kopftabelle
- **[hoch]** Kopftabelle: 14 Befunde behoben mit genannten Commit-Kürzeln (2f56d93, 443058f, 61fbc01, 7fe7c30, b07bcfb, 46e2b7c, 8232923, 799fce5, 9aa7df9, c2bd852, b0cb0d1, 5902211)  
  _Prüfen:_ `git show <kürzel>` für jedes Kürzel; prüfen, ob die Commits noch im Verlauf liegen  
  _Ort:_ Kopfabschnitt, Statustabelle
- **[hoch]** Offen bleiben vier: 2.1 Kartenhöhe, 2.5 Import im vorhandenen Körper, 3.1/3.4 Menüs, 5.6 Kürzel  
  _Prüfen:_ ROADMAP.md — Abschnitt mit den Funden der Durchsichten; am laufenden Fenster nachstellen  
  _Ort:_ Kopfabschnitt, Statustabelle
- **[mittel]** 4.1 (halb umgeschaltetes Thema) und 4.3 (Fokus wie Mausüberfahrt) sind geblieben, 3.2 bewusst nicht behoben  
  _Prüfen:_ Themenwechsel nach Zeichenmodus nachstellen; app/ui/style.py:161/162 lesen; test_a_menu_is_sorted_the_way_it_is_read ausführen  
  _Ort:_ Kopfabschnitt; Teil 4
- **[mittel]** `_fit_once_for` in app/ui/viewport.py:3171 passt nur bei `has_objects` ein; Startkamera über view_from("iso") in viewport.py:1056  
  _Prüfen:_ Die beiden Zeilennummern in app/ui/viewport.py prüfen — laut Tabelle behoben (2f56d93)  
  _Ort:_ Teil 1, Befund 1.1
- **[mittel]** `_focus_report` (app/ui/main_window.py:4675) kehrt bei aktiver Tour ohne Reiterwechsel zurück, samt zitiertem Codeblock  
  _Prüfen:_ app/ui/main_window.py um Zeile 4675 lesen; Zitat gegen den heutigen Quelltext halten  
  _Ort:_ Teil 5, Befund 5.1
- **[mittel]** Weitere Codestellen mit Zeilennummer: settings_dialog.py:129, style.py:161/162, analysis_bar.py:209, style.css:203, first_run.py:96  
  _Prüfen:_ Jede Zeile einzeln aufschlagen — Zeilennummern verschieben sich bei jeder Änderung der Datei  
  _Ort:_ Teil 4 und Teil 5
- **[mittel]** Die Merkmalskarte legt 24 farbige Kacheln mit internen Kennungen (face_1 … pin_4) unter den Körper; heißt „Feature-Zuordnung", Winkel als „45 grad"  
  _Prüfen:_ Analyse → Merkmalskarte am laufenden Fenster; laut Tabelle behoben (5902211) — Katalogtexte in app/i18n/locales/ prüfen  
  _Ort:_ Teil 5, Befund 5.4
- **[hoch]** Die englische Oberfläche ist vollständig: 0 deutsche Einträge in 127 Menüzeilen, Dialogen, Bausteinkatalog und Touren  
  _Prüfen:_ tests/test_translations.py; erneuter Lauf der Oberfläche unter en — der Katalogbestand ist seit 08/2026 auf sechs Sprachen gewachsen (en, es, fr, it, pt)  
  _Ort:_ Teil 6
- **[mittel]** Jede der 83 Operationen hat einen Beschreibungssatz, kein Parameter ohne Erklärung; der vollste Dialog hat acht Frontfelder  
  _Prüfen:_ Registerkonsistenztest; Zählung über placement == "front" im Parameterschema  
  _Ort:_ Teil 6
- **[mittel]** Kamera-Messwerte nach start_empty(): (1.0, −1.0, 0.8) wie geliefert gegen (474.7, −474.7, 504.7) nach reset_camera(), Bauraum 220 × 220 mm  
  _Prüfen:_ start_empty() erneut messen; Bauraumvorgabe in den Druckerprofilen unter app/core/knowledge/ prüfen  
  _Ort:_ Teil 1, Befund 1.1
- **[mittel]** Website-Messwerte: scrollX 111 bei 1440 px, 47 bzw. 270 bei 390 px; hero::before 1646 px, hero::after 1458 px; Handbuchtabelle 645 px  
  _Prüfen:_ Messung in website/ wiederholen; laut Tabelle behoben (61fbc01) — handbuch.html wird von tools/make_manual.py erzeugt  
  _Ort:_ Teil 1, Befund 1.3