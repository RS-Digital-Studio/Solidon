# Prüfbericht `konzept`-Agent zum Konzept Funktionsdurchgang (11.10., Entwurf)

Urteil: noch nicht abgabefähig; nach H1–H7 abgabefähig. Nur gelesen.

## Hoch
- **H1** Nächster Bestand fehlt: `tools/file_acceptance.py` (RM-184) — Prozess/Profil je Fall, echtes
  Fenster, Vorschau, Übernehmen, Undo/Redo mit SHA-256-Netzabdruck, Bild je Schritt, Bericht JSON+MD,
  Wiederaufnahme, `QTest.mouseClick`, `accessibleName`; Logik ohne Fenster in
  `tests/test_file_acceptance.py` (18 Tests). Kein drittes Fensterwerkzeug; `tools/CLAUDE.md` hat 537 B
  Platz. D0 erweitert `file_acceptance.py` um Funktionsfälle; Ziele aus `guide_targets`, Wartewege
  aus `make_web_images`.
- **H2** `make_guides` umgeht echte Bedienung: `QAbstractButton.click()` (verdeckt egal),
  `_editors[…].set_value` (Z. 947), `itemDoubleClicked.emit` (Z. 979), `bar._apply()` (Z. 1364),
  `session.apply` in `story_two_colours` (Z. 1641); `make_web_images.select_body` über
  `object_tree.select_object` (Z. 637); `file_acceptance`: „gesetzt … nicht getippt“. Vorschlag:
  Eingabeereignisse an `area_for`-Stelle, vorher `QApplication.widgetAt` muss Ziel/Kind liefern
  (sonst Fund „verdeckt“), `QTest.mouseClick`/`keyClicks`, Zahlen getippt; nur Startszene über
  `open_path`; Unerreichbares wird neues Ziel, kein Zugriff auf private Attribute.
- **H3** Wortschatz löst nicht alles auf: `area_for("operation:…")` fragt zuerst `_op_actions`
  (Z. 343–354) — 90 Aktionen für 189 Ops; `field:` nur `_op_dialog` (Z. 312–317); `report.action` nur
  erste Handlung (Z. 102–108); Kontextmenüs nur `history:`. Fehlen: Merkmalfenster, Kantenzeilen,
  Kontextmenüs Baum/Ansicht/Kante, Punkte und Griffe, Befundzeilen, Suchfeld, Druckfelder,
  Einstellungszeilen, Leisten (Schnitt, Teilen, Analyse, Explosion, Formen, Skelett, Zeichnen), Chat,
  Kameraleiste, Kürzel-/Handbuch-/Update-/Erstlauf-/Freischaltfenster. Erweitern nur über
  `guides.TARGET_KINDS` + Zweig in `guide_targets`, gehalten von `test_guides` (Z. 340–344): `feature:`,
  `edge:`, `menu:<objectName>`, `finding:`, `finding.action:`, `print:<feld>`, `setting:<schlüssel>`,
  `search`, `handle:<rolle>`; `point_for(…)` über `Viewport.projection` (viewport.py Z. 9106),
  `make_video._world_to_window` zieht dorthin; sichtbarer Knopf gilt auch ohne Menüaktion.
- **H4** §9 „nie dieselbe Datei zur selben Zeit; Funde warten“ = Dateisperre (gegen Codestruktur §5,
  4.2 Punkt 2). Stattdessen: Fixe landen normal; Codestruktur schneidet neu; ab deren Schritt 0 gilt W1
  mit Regel 6.
- **H5** Lokale Fenstertests: Codestruktur §7.2 gilt nur für deren Schritte. Frage an Robert: je Fund
  die eine reproduzierende Fenstertestdatei lokal (vorher rot, nachher grün)? Stufe A ist Werkzeuglauf
  wie RM-184, kein Fenstertest.
- **H6** Ort der Abhakliste: Programm und D0–D10 als Registerpunkte; Abhakliste je Paket in
  `.claude/.state/funktionsdurchgang-2026-10/abhakliste-<paket>.md` (versioniert, `konzepte/README.md`
  Z. 176–181, `.claude/README.md` Z. 19), nur Text, Bilder/Rohdaten außerhalb (`--out`); „offen“ nur mit
  RM; am Ende nach `konzepte/`, Zustandsordner entfernen.
- **H7** Wächter tautologisch oder bindet Tor ans Fenster; Stufe B schreibt Urteile. Vorschlag: im Tor
  jede Op/jeder Fensterbefehl hat Startszene (aus `consumes`, `applies_to`, `requires_kind` über
  Tabelle „Anforderung → Szene“), rot nur neue Anforderung ohne Szene; beim Release als
  `rendered`-Test mit Abdruck aus W3 der Codestruktur; Urteile B/C in `urteile-<paket>.toml`, Prüfstand
  erzeugt Abhakliste; Bedienflächenliste aus dem Wortschatz ableiten.

## Mittel
- M1 Bilder je Sprache/Thema ~3 600 Läufe → Textpassung in jeder Sprache messen; Bilder Deutsch hell
  und je Fund; dunkles Thema Stichprobe je Dialogart.
- M2 Sollwert von außen (Slicer-Wort, CAD-Fachbegriff, Fragebögen); Ort misst der Prüfstand selbst
  (Inventur offscreen, vor RM-735); `window_commands()` hat 15 `settings.*`, 43 `menu.*`-Spiegel →
  Quelle folgt RM-735.
- M3 §31-Budgets nur 14 Vorgänge, Referenzrechner, Umrechnung `recognition_time`; Überschreitung =
  Verdacht, bestätigt über `window_bench.py`/Leistungstests; sonst `wartezeit.md`.
- M4 „druckgleich“ vergleicht Codestände; Vorschlag §35: dieselben Werte über die Kommandozeile ergeben
  druckgleiches Netz.
- M5 Stufe C: Dateidialoge, Ziehen, vier Wege realistisch (1–3 h); 3D-Maus nicht (keine HID) → Robert
  oder Tests an `spacemouse.camera_step`; Weg 3 lokaler Generator, Chat lokales Modell, bezahlter
  Dienst = Roberts Entscheidung; Steuerung braucht Freigabe je Anwendung und Zeitfenster;
  Rechtsziehen/zweiter Schirm vorher proben; Expertenprüfung: Entscheidungen nur aus sichtbarem Text,
  Fehlklicks zählen.
- M6 Aufwand: D0 8–12 Tage; Zeilenspezifikation je Paket; Hunderte Funde erwartbar (0.5.2: 86 an 12);
  Bausteine eine Zeile mit Lauf über 83; acht bis zwölf Wochen ohne Fixe.
- M7 Fristen: Verkaufskandidat 25.11., Start 01.12. → D0, D1, D8, D7 (Weg 1 bis Slicer), D3, D4, Rest;
  Kundenpakete bis 25.11. vor MainWindow-Komponenten der Codestruktur; RM-734 vor Prüfpunkt 1 an
  Booleschen; Prüfstand früh auf main (W5 schreibt ihn mit um).
- M8 Abnahme: Gegenproben je Prüfpunkt ohne Fenster; Test vor Fix rot; „offen“ nur mit RM; sechs
  Sprachen ohne Abschneiden; Protokoll Stufe C; Konzept/Nachweise in `konzepte/`; Schritt in `/erzeugen`.

## Gering
- G1 Tab-Kette per Tastendruck + `focusWidget()`, nie `nextInFocusChain`.
- G2 Eine Quelle mit Skill `ux-review` (deckt 7 von 11): Skill ergänzen, Konzept verweist, `sync_agents.py`.
- G3 Kostenabschnitt: `/erzeugen`, `RENDERED_TESTS`, Karten (`tools/CLAUDE.md` 537 B, `app/ui/CLAUDE.md`
  603 B), Skills, Übersetzungen, Website/Handbuch, `test_interface_limits`.
- G4 Inventur offscreen; `output/` ignoriert, bis zum Ablegen unversioniert.
