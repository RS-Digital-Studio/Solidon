# Sondierung: konzept-bedienung.md

**Titel:** Konzept — Bedienung, Gestaltung und Zeichnen
**Stand laut Dokument:** „Aus einem Lauf am echten Programm, 4. August 2026." — dazu der Nachtrag „## Stand (5. August 2026, zweiter Eintrag)"
**Zweck:** Bestandsaufnahme eines vollständigen Bedienlaufs durch Solidon — Befunde zu Viewport, Kamera, Gestaltung, Touren, Skizzeneditor, Fehlermeldungen, Texten, Handbuch und Karten, jeweils mit „Zu tun", einer nach Wirkung geordneten Reihenfolge und einem Nachtrag, was davon inzwischen erledigt ist.

**Alterung:** 5/5 — Momentaufnahme des eigenen Programmstands: fast jeder Befund ist eine Fehlerbeschreibung mit Datei- und Zeilenangabe, die beim nächsten Commit verfällt. Der eigene Nachtrag vom Folgetag entwertet bereits den größten Teil von Teil 1 bis 4, das Handbuchkapitel und viele Punkte aus Teil 8 und 9, ohne den Haupttext zu korrigieren — wer nur oben liest, liest Falsches. Dazu Zählungen (sechs setStyleSheet, 2736 Tests, 59 Commits) und Fusion-Vergleiche, die mit jeder fremden Fassung altern.

## Gliederung

- Teil 1 — Die drei Befunde, aus denen fast alles andere folgt
- Teil 2 — Gestaltung
- Teil 3 — Das interaktive Tutorial
- Teil 4 — Zeichnen, an Fusion gemessen
- Teil 5 — Rückmeldung, Fehler, Verlauf
- Teil 6 — Texte
- Teil 7 — Handbuch
- Teil 8 — Einrichtung und Aufstellung
- Teil 9 — Die Karten
- Teil 10 — Reihenfolge
- Stand (5. August 2026, zweiter Eintrag)
- Was gut ist und so bleiben soll

## Extern prüfbare Behauptungen (19)

- **[mittel/marktlage] Autodesk Fusion (ehemals Fusion 360)** — Autodesk Fusion ist die Anwendung, aus der die meisten Nutzer kommen; es diente durchgehend als Vergleichsmaßstab  
  _Ort:_ Kopf des Dokuments, Zeilen 3–6
- **[mittel/funktionsumfang] Autodesk Fusion — Startseite** — Fusions Startseite: schmale Spalte mit Hub-Auswahl, zwei Hauptknöpfen, Navigation (Aktuell · Projekte · Mein Fusion · Beispiele), unten Verweise, rechts Inhalt mit Suchfeld und Umschalter Liste/Kacheln  
  _Ort:_ 2.1 Der Startbildschirm
- **[niedrig/funktionsumfang] Autodesk Fusion — leerer Startzustand** — Fusion zeigt den leeren Zustand als Bild plus Überschrift plus Satz plus Knopf: „Noch keine Daten vorhanden. / Erstellen oder öffnen Sie zunächst ein Dokument."  
  _Ort:_ 2.1
- **[hoch/funktionsumfang] Autodesk Fusion — Skizzenmodus** — Fusions Skizzenmodus hat sichtbaren Ursprung mit roter X- und grüner Y-Achse, beschriftete Achsen am Raster, eigenes Werkzeugregister, eine Ändern-Gruppe (Verrunden, Trimmen, Verlängern, Versetzen, Spiegeln, Muster), Projizieren/Konstruktionsgeometrie, eine Skizzenpalette und einen großen grünen Haken zum Abschluss  
  _Ort:_ Teil 4, Vergleichstabelle
- **[hoch/funktionsumfang] Autodesk Fusion — Tastenkürzel** — Fusion-Kürzel im Skizzenmodus: L Linie · R Rechteck · C Kreis · D Bemaßung · T Trimmen · O Versetzen; die Belegung ist bei Fusion kontextabhängig  
  _Ort:_ Teil 4 und „Zu tun" Punkt 2–3
- **[niedrig/funktionsumfang] Autodesk Fusion — ViewCube** — Fusions ViewCube ist ein beschrifteter Würfel, den man anklickt  
  _Ort:_ 2.5 Kleinere Brüche im Bild
- **[niedrig/funktionsumfang] Autodesk Fusion — Auswahldialog** — Fusions Vergleichsdialog: sechs klar verschiedene Symbole, Auswahl über Rahmen und Hintergrund, erklärende Detailspalte rechts  
  _Ort:_ 2.5 Symbole und Kodierung
- **[hoch/funktionsumfang] Elegoo Centauri Carbon 2** — Der Elegoo Centauri Carbon 2 hat einen Bauraum von 256 mm  
  _Ort:_ 1.2
- **[mittel/funktionsumfang] Slicer-Druckerprofile (Bambu, Creality, Prusa, Sovol, Anycubic, Elegoo)** — Installierter Profilbestand: Anycubic, Bambu ×4, Elegoo Centauri Carbon 2, Creality ×3, Elegoo Neptune ×2, Allgemeiner FDM-Drucker, Prusa ×3, Sovol  
  _Ort:_ Teil 8
- **[niedrig/funktionsumfang] Afinia H+1 (HS) — Slicer-Profil** — Erster Eintrag des installierten Profilbestands ist „Afinia H+1(HS) 0.4 nozzle"  
  _Ort:_ Teil 8
- **[mittel/funktionsumfang] Qt / PySide6 — Fusion-Stil** — Qt Fusion ist der geerbte Standardstil; Qt-Standardblau trägt „jede zweite Desktop-Anwendung"  
  _Ort:_ 2.0 und 2.4
- **[hoch/api] Qt / PySide6 — QShortcut-Ambiguität** — Qt lässt bei zwei aktiven Kürzeln derselben Taste keines von beiden feuern  
  _Ort:_ Stand-Abschnitt, Zeichenkürzel
- **[mittel/api] Qt / PySide6 — QKeySequence.toString** — QKeySequence.toString(NativeText) liefert die lokalisierte Kürzelanzeige  
  _Ort:_ Teil 6, „Zu tun" Punkt 4
- **[hoch/api] VTK / pyvista — Kamerasteuerung** — VTKs Trackball-Stil dollyt entlang der Kamera-Achse; pyvista verwirft eine gesetzte Kamera über camera_set wieder  
  _Ort:_ Stand-Abschnitt und Teil 7
- **[mittel/api] VTK-Python-Bindings** — Eine Referenzschleife zwischen Python und VTK war die Absturzursache  
  _Ort:_ Stand-Abschnitt, Punkt 26
- **[mittel/recht] WCAG 2 AA — Kontrastanforderung** — Der Farbkontrast der Themenpaare ist gegen WCAG AA geprüft  
  _Ort:_ 2.4
- **[niedrig/funktionsumfang] Viridis-Farbrampe** — Viridis ist die verwendete wahrnehmungsgleiche Farbrampe statt Regenbogen  
  _Ort:_ 2.4
- **[niedrig/funktionsumfang] OpenCASCADE** — OpenCASCADE liefert „Exakte Kanten" und ist als optionales Zusatzprogramm eingebunden  
  _Ort:_ Teil 6, Texttabelle
- **[niedrig/api] Qt / PySide6 — QLineEdit** — Qt-Warnung `QLineEdit::setSelection: Invalid start position (22)` trat als Spur beim Absturzverdacht auf  
  _Ort:_ 5.5

## Intern prüfbare Behauptungen (15)

- **[hoch]** `_left_down` kehrt im slicer-Schema mit einem return zurück (viewport.py:1240); Linksklick wählt nichts aus, Picking läuft nur bei Messen/Bemalen/Merkmalsüberlagerung  
  _Prüfen:_ app/ui/viewport.py, Funktion _left_down lesen; Stand-Abschnitt nennt Punkt 1 erledigt, Zeilennummer dürfte überholt sein  
  _Ort:_ 1.1
- **[hoch]** „Alles einpassen" passt auf den Bauraum ein; Mausrad zoomt zur Bildmitte statt zum Zeiger (viewport.py:1209); jede Auswahländerung setzt die Kamera zurück  
  _Prüfen:_ .venv\Scripts\python.exe -m app.ui.app starten; Stand sagt behoben, Zoom-Punkt bleibt bei 0,000000 mm — zugehörigen Kameratest in tests/ suchen  
  _Ort:_ 1.2
- **[hoch]** In app/ stehen sechs setStyleSheet-Aufrufe, kein Anwendungs-Stylesheet; nur zwei Schriftgrößen (20px, 24px); 50 Aufrufe von setSpacing/setContentsMargins ohne Raster  
  _Prüfen:_ grep -rn 'setStyleSheet\|setSpacing\|setContentsMargins' app/ zählen; app/ui/style.qss auf Existenz prüfen  
  _Ort:_ 2.0
- **[hoch]** Die Live-Vorschau existiert bereits: main_window.py:2322–2340, 300-ms-Timer auf session.preview_async, Ergebnis an viewport.show_difference; evaluate_cached liegt bei 0,28 ms  
  _Prüfen:_ app/ui/main_window.py an dieser Stelle lesen; Messwert gegen .venv\Scripts\python.exe -m pytest -q -m performance  
  _Ort:_ 2.0.3
- **[hoch]** Der Op-Dialog ist modal (dialog.exec()) und öffnet mittig bei (752, 413) in 1920×1150 über dem Teil  
  _Prüfen:_ grep -rn 'exec()' app/ui/; Stand-Punkt 9a als erledigt gemeldet  
  _Ort:_ 2.0.3
- **[mittel]** Datei → Neu zeigt den Startbildschirm nicht wieder; Beispiele danach nur über Öffnen erreichbar; alte Merkmalsmarkierungen bleiben stehen  
  _Prüfen:_ Anwendung starten, Datei → Neu; Stand-Punkt 11 als erledigt gemeldet  
  _Ort:_ 2.2
- **[hoch]** Helles Thema wirkt nur im Viewport, Symbole verschwinden, Zurückschalten stellt nicht alles zurück  
  _Prüfen:_ Ansicht → Helles Thema in der laufenden Anwendung durchschalten; Stand-Punkt 10 erledigt  
  _Ort:_ 2.3
- **[hoch]** viewport.py:101–145 führt neun eigene Farbkonstanten (OBJECT_COLOUR = "#b9c4d0"), drawing.py:75–90 eine dritte Palette; Auswahl blau (#3d6ea5/#2f6fb0) im Baum gegen orange (#f0a54a) im Viewport  
  _Prüfen:_ grep -rn '#[0-9a-fA-F]\{6\}' app/ und gegen app/ui/palette.py abgleichen; Stand-Punkt 9d erledigt  
  _Ort:_ 2.4
- **[mittel]** Der Test test_the_viewport_follows_the_theme prüft nur, dass viewport_colours() unterschiedliche Werte liefert, nicht die Modulkonstanten  
  _Prüfen:_ grep -rn test_the_viewport_follows_the_theme tests/  
  _Ort:_ 2.4
- **[hoch]** Fünf von sieben Touren beginnen mit einem Beobachtungsschritt, der nie abgehakt wird; Weg 3 Schritt 3 ist gar nicht ausführbar  
  _Prüfen:_ Beispielprojekte öffnen und Touren durchlaufen; Stand-Punkte 6–9 erledigt  
  _Ort:_ 3.1–3.3
- **[hoch]** Im Skizzeneditor bewirken L, R und C nichts; app/ui/shortcut_schemes.py deckt nur Modellieren ab (E, Q, F, C, M, R, H, P, S)  
  _Prüfen:_ app/ui/shortcut_schemes.py lesen; Stand meldet Punkte 15–19 durch, Kürzel nur im Skizzenmodus  
  _Ort:_ Teil 4
- **[mittel]** Die Agentenregel „Erst in der Bausteinbibliothek suchen (§39)" steht im doc-Feld einer Operation (primitive_ops.py:78) und wird dem Nutzer angezeigt  
  _Prüfen:_ grep -rn '§' in den doc-Feldern unter app/core/; Stand-Punkt 25 erledigt  
  _Ort:_ Teil 6
- **[hoch]** Der Tastenkürzel-Dialog listet 17 Befehle, zeigt englische Kürzel und nennt fälschlich Strg+G statt Strg+Umschalt+P; 15 Kürzel (1–6, Strg+0–Strg+6) fehlen  
  _Prüfen:_ Hilfe → Tastenkürzel in der Anwendung; Quelle des Dialogs unter app/ui/ lesen  
  _Ort:_ Teil 6
- **[hoch]** Stand 5. August 2026: neunundfünfzig Commits, Suite bei 2736 Tests; „Damit ist das Konzept abgearbeitet", offen nur ein erneuter Lauf  
  _Prüfen:_ .venv\Scripts\python.exe -m pytest -q und Testzahl vergleichen; git log seit dem Stichtag; ROADMAP.md gegenlesen  
  _Ort:_ Stand-Abschnitt
- **[hoch]** Teilweise offen: Import legt nicht auf die Platte (load-Parameter place_on_bed steht auf False), kein Absturzprotokoll, Merkmalsbeschriftungen dauerhaft statt beim Überfahren, Rückmeldung in der Statusleiste übersehbar  
  _Prüfen:_ grep -rn place_on_bed app/core/; ROADMAP.md-Abschnitt zu den Funden der Durchsichten prüfen  
  _Ort:_ Stand-Abschnitt, „Teilweise"