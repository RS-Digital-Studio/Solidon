# Durchsicht v0.5.1 — Prüfer fenster

## 1. Kopf

- Gebiet: Hauptfenster, Prüfbericht und seine Knöpfe, Laden und Wartezeit,
  Frage vor der Vollerkennung, lokale Erkennung samt Tastatur, *Zuletzt
  geöffnet*, Dialoge, Werkzeugleiste.
- Arbeitsbaum: `F:\3D Druck.review-051\wt-fenster` auf `aeb562ede` (detached),
  `_chain`-Erweiterung aus dem Hauptbaum kopiert.
- Diff `v0.5.0..HEAD` (Zeilen +/−):
  - `app/ui/main_window.py` +965 / −150
  - `app/ui/panels.py` +356 / −59
  - `app/ui/session.py` +219 / −17
  - `app/ui/loading.py` +166 / −16
  - `app/ui/local_recognition.py` +174 / −12
  - `app/ui/local_recognition_flow.py` +100 / −12
  - `app/ui/dialogs.py` +10 / −1
  - `app/ui/tool_strip.py` +8
  - `app/ui/palette.py` +22
  - `app/ui/labels.py` +15 / −2
  - `app/ui/CLAUDE.md` +146 / −16
- Stand (26.09.2026, zweite Sitzung ab 18:00, fortgesetzt nach Abbruch am
  Nutzungslimit): Diff vollständig gelesen, Sonden `sonden/fenster/p01`–`p33`
  gefahren, 17 eigene Befunde und sieben übernommene (KUNDE-02, -06, -07,
  -09, -12, -14, -15) — alle behoben bis auf zwei Reste mit Registersatz
  (FENSTER-03: Qt-Lücke ohne GIL und ohne CPU, braucht einen nativen
  Abtaster; RM-131 bleibt Roberts Zurückstellung).
- Last: sieben bis neun Prüfer auf der Maschine; alle Zeiten „unter Last“.
  Vergleiche HEAD gegen Arbeitsbaum in getrennten Prozessen abwechselnd
  (Oberflächencode lässt sich nicht im selben Prozess tauschen); der HEAD-Stand
  als `git archive aeb562ede app`, dazu `_chain.*` aus dem Arbeitsbaum, über
  `SONDE_TREE` (nach der Durchsicht wieder gelöscht; die Reihenskripte
  `p04c_reihe.sh`, `p23_reihe.sh` erwarten ihn unter `sonden/fenster/headbaum`).

## 2. Befunde

### FENSTER-01 · Bedienfehler · verschobene Projektdatei aus „Zuletzt geöffnet“

- Fundstelle: `app/core/scene/project.py:1588` (`load`, `missing_file`) und
  `:1761` (`unreadable`); `app/ui/main_window.py` Handler `choose_another_file`.
- Kundensicht vorher: Klick auf ein verschobenes Projekt → Dialog „Die Eingabe
  war so nicht verwendbar.“ / „Diese Projektdatei gibt es nicht.“ mit den Knöpfen
  *Details anzeigen* und *Fehlerbericht erstellen* — ein Fehlerbericht für eine
  verschobene Datei, und kein Weg zu einer anderen. (Beim Modell stimmt es seit
  `dcde032e5`; die Changelog-Zusage „Ist eine Datei aus *Zuletzt geöffnet*
  verschoben worden, … bietet *Andere Datei wählen* an“ galt für Projekte nicht.)
  Dazu führte *Andere Datei wählen* immer zu *Einfügen*, auch wo ein Projekt
  gemeint war.
- Messung: Sonde `sonden/fenster/p01_lesen.py`, Lage B (Dialog abgefangen,
  angebotene Knöpfe über `offered_actions`).
- Nachher: Titel „Diese Datei ließ sich nicht lesen.“ (vorhandener Katalogtext),
  Knopf *Andere Datei wählen*; bei `.p3d` öffnet er *Öffnen*, sonst *Einfügen*
  (`MainWindow._choose_another_file`). Dasselbe für eine gesperrte/unerreichbare
  Projektdatei (`unreadable`).
- Nachher gemessen (`p01_lesen.py` Lage B): Titel „Diese Datei ließ sich nicht
  lesen.“, Knopf *Andere Datei wählen*.
- Tests: `test_project.py::test_a_moved_project_offers_another_file_not_a_bug_report`,
  erweitert `::test_an_unreadable_project_file_is_a_file_error_not_a_crash`;
  Fenstertest (Release) `test_ui.py::test_a_moved_project_leads_to_open_and_a_moved_model_to_insert`.
- Dazu: Nach dem gescheiterten Öffnen stand der tote Eintrag weiter in
  „Zuletzt geöffnet“ (die Liste prüft nur beim Aufbau). `_on_import_failed` und der
  Fehlerzweig von `open_path` bauen sie neu (`_show_recent`, Daemon-Faden wie
  bisher). Gemessen (`p01_lesen.py` Lage A): vorher `verschoben.stl`,
  `Wedge-Lock (Base).stl` — nachher nur noch `Wedge-Lock (Base).stl`. Test
  (Release): `test_ui.py::test_a_recent_file_that_vanished_leaves_the_list_after_the_attempt`.
- Nebenfund: `test_an_unreadable_project_file_is_a_file_error_not_a_crash` riss
  allein gefahren mit 0xC0000409 — der `ZipFile.__init__`-Patch galt noch, als
  der Fixture-Abbau PySide6 importierte (shiboken braucht `zipfile`). Auch am
  unveränderten HEAD. Der Patch gilt jetzt nur um `load` (`monkeypatch.context`).
- Status: behoben.

### FENSTER-02 · Bedienfehler · *Abbrechen* wirkt beim Lesen erst, wenn das Laufwerk antwortet

- Fundstelle: `app/ui/session.py` `_ReadWorker` (`dcde032e5`).
- Kundensicht vorher: Modell auf einem langsamen/toten Laufwerk, nach 2 s
  *Abbrechen* — nichts geschieht, bis das System aufgibt (gemessen mit um 8 s
  verzögertem Lesen: frei nach 6,1 s; bei einem toten Netzlaufwerk nach dessen
  Zeitlimit, gemessen 21 s laut RM-224). Schließt der Kunde währenddessen das
  Fenster, hängt ein `QThread` in einem `stat` — der Fall, den
  `_show_recent` wegen 0xC0000409 ausdrücklich meidet.
- Messung: `p01_lesen.py` Lage D (`read_local_payload` um 8 s verzögert).
- Behebung: gelesen wird in einem Daemon-Faden, der Arbeiter sieht alle 50 ms
  nach einem eigenen `CancelSignal`; `Session.cancel_evaluation` setzt es,
  `stopped` meldet `importFinished(False)` und verbraucht den Abbruch, wenn keine
  Auswertung daneben läuft.
- Nachher, gleiche Sonde: frei nach 0,06 s. Schließen des Fensters während
  eines 20 s hängenden Lesens (`p05_schliessen_beim_lesen.py close`, HEAD gegen
  Arbeitsbaum im selben Aufbau): **19,2 s → 0,07 s** bis das Fenster zu ist; der
  Prozess endet regulär mit Exit 0, der Lesefaden läuft als Daemon aus.
- Test (Release): `test_ui.py::test_cancelling_frees_the_window_while_the_drive_still_reads`.
- Status: behoben.

### FENSTER-03 · Leistung · Hauptfaden steht beim Einlesen einer großen 3MF

- Fundstelle: `app/core/ingest/threemf.py` `_leaves`/`read` (`ET.fromstring` über das
  ganze Modell-XML) und `_read_numbers` (`np.array` über Millionen Zeichenketten) —
  beide hielten den GIL am Stück; bestehend seit vor 0.5.0.
- Kundensicht vorher: Mausoleum Dragon.3mf (2,3 Mio. Dreiecke, 195 MB Modell-XML)
  öffnen — das Fenster reagiert rund 4 s gar nicht, danach noch einmal 2 bis 4 s
  stockend (Windows schreibt ab 5 s „Keine Rückmeldung“). Das widerspricht §2.8.
- Ursache (`p06_xml_gil.py`, `p09_findall.py`, `p10_gc.py`, `p31_xml_freeze.py`,
  `p31b_phasen.py`, ohne Qt, Nebenfaden im 5-ms-Takt): `ET.fromstring` hält den GIL
  4–5 s am Stück; dazu Läufe des Speicherbereinigers über die 3,5 Mio. gebauten
  `Element`-Objekte (0,8–1,5 s je Lauf, `gc.callbacks`), `np.array` über die ganze
  Zeichenkettenliste (1,1–1,7 s) und das Loslassen des fertigen Baums am Stück
  (0,5–0,6 s).
- Behebung (vollständig im Kern):
  1. `_numbers_in_blocks` wandelt in Blöcken zu `NUMBER_BLOCK` = 65 536 (erste Runde).
  2. `_parse_model` parst das Modell-XML in `XML_CHUNK` = 256-KB-Stücken
     (`XMLParser.feed`, dieselben Fehler wie `fromstring`) und friert nach jedem
     Stück ein, was steht (`gc.freeze`) — die gebauten Elemente zählen für spätere
     Läufe des Bereinigers nicht mehr mit.
  3. `_reading_trees` umschließt `read_objects` und `read`: am Ende gibt `_release`
     die Ecken- und Dreieckslisten in Scheiben frei, danach `gc.unfreeze`. Nichts
     bleibt eingefroren (Test).
  Gemessen ohne Qt, je drei Läufe: Parsen + Zahlen am Stück 9,4 s / längste
  Lücke 4,6 s → stückweise mit Einfrieren 6,9 s / 0,7 s; mit Freigabe in Scheiben
  längste Lücke 0,13 s. `read_objects` am Drachen (`p32_scan.py`, HEAD-Export gegen
  Arbeitsbaum): **HEAD 9,9–11,4 s, längste Lücke 2,9–3,9 s → Arbeitsbaum 7,2–9,7 s,
  längste Lücke 81–125 ms**; der Zählweg `scan_assembly` hielt schon vorher nie
  länger als 66 ms.
- Am Fenster (`p04c_exec.py`, **echte Ereignisschleife** `exec()`, Drache von der
  Startfläche, *Sofort laden*, je drei Läufe abwechselnd, unter Last):

  | | HEAD | Arbeitsbaum |
  |---|---|---|
  | längste Lücke eines Python-Fadens (GIL) | 4,09 · 4,08 · 3,79 s | **keine über 250 ms** |
  | längste Lücke des Qt-Takts im Hauptfaden | 4,09 · 4,08 · 4,60 s | 2,09 · 0,93 · 2,34 s |
  | bis alles ruht | 28,4 · 28,7 · 28,2 s | 24,3 · 26,6 · 24,0 s |

- **Offen, aber nicht mehr der GIL:** Der Qt-Takt im Hauptfaden setzt während des
  Parsens weiter bis 2 s aus, obwohl ein Python-Faden daneben nie länger als 250 ms
  wartet. Gemessen: Der Hauptfaden verbraucht in diesen Lücken **keine CPU-Zeit**
  (`p04g_cpu.py`, `GetThreadTimes`: 0,03 s in 4,3 s), steht ohne Python-Rahmen in
  `exec()` und stellt vereinzelt Mal-Ereignisse zu; kein Lauf des Bereinigers
  über 100 ms, nicht die Ladeanzeige (`p04e_malen.py`: 37 Malvorgänge, zusammen
  0,27 s), nicht das Aufwärmen des Pickers (ausgeschaltet unverändert,
  `SONDE_OHNE_PICKER`), nicht der Zeitgebertyp (präzise unverändert,
  `SONDE_PRAEZISE`); `time.sleep(0)` zwischen den Stücken änderte nichts und ist
  nicht eingebaut. Bei HEAD steckt dieselbe Lücke in den
  größeren GIL-Lücken (Qt-Lücken 2,1 s neben Python-Lücken 0,9 s). Die Ursache liegt
  in nativem Code und braucht einen nativen Stapelabtaster (etwa `py-spy dump
  --native`) — ein Werkzeug, das hier nicht installiert ist (Registersatz).
- Nebenbefund der Sonden, kein Produktfehler: Zwei von zwölf Läufen endeten mit
  einer Zugriffsverletzung **in `os._exit`**, während Schichtanalyse und
  Vorschaubild noch rechneten (faulthandler: Hauptfaden in `os._exit`, die beiden
  Arbeiter in `_plane_segments` und `numpy.unique`). Die Anwendung beendet über
  `closeEvent` → `release` und wartet ihre Arbeiter ab; Sonden müssen das auch.
- Tests: `test_threemf_assembly.py::test_numbers_in_blocks_give_the_same_arrays`,
  `::test_the_model_xml_is_read_in_pieces_and_nothing_stays_frozen` (Stück zu 7
  Bytes durch Tags und „ü“, nichts bleibt eingefroren, Parsefehler wie
  `fromstring`, Freigabe), angepasst `::test_the_scan_streams_the_count_without_the_full_parse`
  (sperrt jetzt `_parse_model`); `test_threemf_assembly.py` und
  `test_threemf_native_materials.py` grün (104).
- Status: behoben, was am GIL lag; die verbleibende Lücke ohne CPU ist ein
  Registersatz (nativer Abtaster).

### FENSTER-04 · Verständnis · Laden von der Startfläche: Schleier sagt „Wird berechnet …“, Startfläche bleibt stehen

- Fundstelle: `app/ui/main_window.py` `_update_veil` (Reihenfolge der Bedingungen).
- Kundensicht: Beim Öffnen von der Startfläche bleibt diese während Lesen und
  Plan stehen (Dragon: 5 s, eine 63-MB-3MF laut Regel 14 s), und nur die
  Statuszeile sagt „Modell wird gelesen · 0 % · Verstrichen“. Danach steht über
  der Ansicht „Wird berechnet …“, während die Statuszeile „Modell einfügen“
  meldet — zwei Auskünfte über denselben Vorgang, genau was der Docstring von
  `_update_veil` ausschließen will: Nach `start_new` gibt es immer schon ein
  (leeres) Ergebnis, also gewinnt die Zeile „Wird berechnet …“ vor „Modell wird
  gelesen“.
- Messung: `p02_drache.py`, Abtastung alle 2 s.
- Behebung: `_update_veil` fragt zuerst `_loading_model`, dann das Ergebnis.
  Nachher (`p01_lesen.py` Lage C): Überschrift „Modell wird gelesen“.
  Die Startfläche bleibt während Lesen und Plan stehen — das ist eine bewusste
  Entscheidung (`_on_import_finished`: „Der Startbildschirm weicht erst hier“),
  und die Statuszeile trägt Uhr und nach 2 s *Abbrechen*; nicht geändert.
- Test (Release): erweitert `test_ui.py::test_the_veil_says_whether_a_model_or_a_project_is_coming`.
- Status: behoben.

### FENSTER-05 · Verständnis · Restzeit springt nach einer Zeile, die bei 0 % stand

- Fundstelle: `app/ui/loading.py` `ProgressTiming.step` (`a5e6bf614`, `49d898d48`).
- Kundensicht vorher: Mausoleum Dragon.3mf öffnen: 16 s „Modell einfügen · 0 %“,
  dann „Punkte verschweißen · 20 % · noch etwa 70 s“ und zwei Sekunden später
  „Außenseiten angleichen · 60 % · noch etwa 15 s“. Die Korrektur aus
  `49d898d48` greift nur, wenn der Anteil **sinkt**; hier stieg er von 0 auf 20 %,
  und die 16 s der ersten Zeile galten als Rechenzeit der zweiten.
- Messung: `p02_drache.py` (Statuszeile alle 2 s), unter Last.
- Behebung: Stand die vorige Zeile bei null und wechselt die Zeile mit dem ersten
  gemessenen Anteil, zählt die Schätzung ab dort und rechnet nur hoch, was seitdem
  dazukam (`_counted_fraction`, `remaining_time(..., since=)`). Eine Zeile, die
  selbst bei 0 % beginnt, behält ihren Anfang.
- Tests: `test_loading.py::test_a_line_that_stood_at_zero_gives_its_time_to_nobody`,
  `::test_one_line_that_reports_from_zero_keeps_its_own_start` (ohne Fenster,
  grün); alle übrigen Uhr-Tests unverändert grün.
- Status: behoben.

### FENSTER-06 · Kleinigkeit · „Abgebrochen …“ bleibt nach *Ohne Merkmalserkennung laden* stehen

- Fundstelle: `app/ui/main_window.py` `_load_without_recognition` (`2c67b684e`).
- Kundensicht vorher: Nach *Ohne Merkmalserkennung laden* steht das Modell
  vollständig da, die Statuszeile sagt weiter „Abgebrochen. Zu sehen ist der
  letzte vollständig gerechnete Stand …“ (`p02_drache.py` Schritt 5).
- Behebung: Der Knopf räumt die Ansage (`announce("")`, das nimmt ihn mit).
- Status: behoben.

### FENSTER-07 · Kleinigkeit · Titelleiste „Unbenannt“ nach dem Einlesen

- Fundstelle: `app/ui/main_window.py` `_update_header` / `_on_project` (bestehend
  vor 0.5.0).
- Kundensicht vorher: Nach dem Öffnen des Drachen stand oben „Unbenannt —
  Solidon3D“, in Kopfzeile und Baum „Mausoleum Dragon“: `session.title` leitet
  den Namen aus dem Ergebnis ab, gesetzt wurde die Titelleiste aber nur beim
  Dokumentwechsel, vor der Auswertung. Erst eine spätere Dokumentänderung
  brachte den Namen.
- Behebung: `_update_header` (läuft nach jeder Auswertung) setzt die Titelleiste mit.
- Test (Release): `test_ui.py::test_the_window_title_names_the_model_once_it_is_read`.
- Status: behoben.

### FENSTER-08 · Leistung · automatische Sicherung hält das Fenster alle zwei Minuten an (RM-233, Teil 1)

- Fundstelle: `app/ui/main_window.py:2337` → `Session.autosave` (bestehend).
- Kundensicht vorher: Nach dem Einlesen gilt ein Projekt als ungespeichert; alle
  120 s schrieb der Zeitgeber im Hauptfaden das ganze Projekt samt Modell neu.
  Am Drachen (Sicherung 32,9 MB): Stillstand 851 / 769 / 1 033 ms, alle zwei
  Minuten. Und ein Schreibfehler (volles Laufwerk) warf im Slot des Zeitgebers —
  der Kunde erfuhr nie, dass es keine Sicherung gab (RM-233).
- Messung: `p08_sicherung.py` (Zeitgeber-Slot von Hand, 5-ms-Takt), unter Last.
- Behebung: `Session.autosave_async` kopiert das Dokument im Hauptfaden und
  schreibt im `_AutosaveWorker`; ein Fehler kommt über `autosaveFailed`, das
  Fenster sagt ihn einmal je Sitzung. Speichern, Verwerfen und Dokumentwechsel
  zählen `_autosave_epoch` hoch — eine Sicherung, die danach fertig wird, wird
  gleich wieder geräumt, sonst böte sie sich beim nächsten Start an.
  `wait_for_idle` kennt den Arbeiter; Schließen während der Sicherung wartet sie
  ab (`p11_schliessen_beim_sichern.py`: 2,7–3,0 s bei 3 s verzögertem Schreiben,
  regulärer Ausgang, dreimal Exit 0). `Session.autosave` bleibt als gerader Weg.
- Nachher, gleiche Sonde: Slot 1–3 ms, längste Lücke 26 ms; der Schreibfehler
  steht in der Statuszeile.
- Katalog: neuer Text „Die automatische Sicherung ließ sich nicht schreiben —
  prüfen Sie den freien Speicherplatz und speichern Sie das Projekt selbst.“
- Tests (Release): `test_ui.py::test_the_autosave_writes_beside_the_window_and_says_when_it_cannot`,
  `::test_a_backup_that_finishes_after_saving_is_cleared`.
- Status: behoben.


### FENSTER-09 · Verständnis · „Art: Die Eingabe war so nicht verwendbar.“ unter jedem Grund der Stellensuche

- Fundstelle: `app/ui/local_recognition.py` `_RecognitionWorker.work` (`2c67b684e`:
  `values=dict(finding.values)`).
- Kundensicht vorher: Im Fenster *Merkmale an dieser Stelle* stand unter „Dieser
  Bereich enthält zu viele Dreiecke …“ eine zweite Zeile „Art: Die Eingabe war so
  nicht verwendbar.“ — `_finding_from` legt den Klassentitel als `kind` in die
  Werte, und `spoken_values` las ihn vor.
- Messung: `p07_stelle.py` am Drachen, Text des `ErrorNotice`.
- Behebung: `kind` wird nicht in den Fehler des Dialogs übernommen; `constraint`
  bleibt (es wählt die Wege je Grund). Nachher: nur noch der Satz.
- Status: behoben.

### FENSTER-10 · Leistung · Suche an einer Stelle las das ganze Modell neu ein

- Fundstelle: `app/ui/local_recognition.py:171` (`quality="fine"`, bestehend seit
  vor 0.5.0; seit 0.5.1 der empfohlene Weg an großen Modellen).
- Kundensicht vorher: Drache, *Merkmale an einer Stelle erkennen* aus dem Bericht,
  Stelle per Tastatur: 51–65 s „Merkmale werden erkannt …“, dann „zu viele
  Dreiecke“; *Suchradius verkleinern* noch einmal 48 s. Die Schrittmeldungen
  zeigen, warum: „Modell laden“, „Punkte verschweißen“ … „Auf das Bett setzen“ —
  40 s Einlesen, erst dann die Suche. Die Sitzung rechnet im Entwurf, der
  Suchlauf in „fein“; der Cache-Schlüssel enthält die Qualität (`operation_hash`,
  gemessen über einen Mitschnitt der Schlüssel: `draft` gegen `fine`). Ein
  abgelehnter Suchlauf legt nichts in den Cache (`stopped_at`), also bei jedem
  neuen Radius wieder.
- Behebung: Der Dialog sucht in der Qualität der Sitzung (`quality=session.quality`
  durch `LocalRecognitionFlow.begin` → `LocalRecognitionDialog` →
  `_RecognitionWorker`). `detect_region` liest die Qualität nicht; übernommen wird
  ohnehin in der Qualität der Sitzung.
- Nachher, gleiche Sonde und Stelle, unter Last: erste Suche **58 → 21,6 s**, neuer
  Radius **48 → 6,4 s**. Der Rest (15–19 s bis zur Absage „zu viele Dreiecke“ bei
  10 mm) liegt in `perceive/local.py` — siehe „Für Nachbarn“.
- Test (Release): `test_local_recognition_flow.py::test_the_search_reuses_what_the_session_already_computed`.
- Status: behoben (Rest beim Nachbarn).

### FENSTER-11 · Bedienfehler · „… von denen manche ineinanderstecken“ bleibt nach *Überschneidungen auflösen* stehen

- Fundstelle: `app/core/scene/evaluate.py` `SETTLED_BY` / `_without_settled`
  (`2b83f72a5`).
- Kundensicht vorher (drill-holder.3mf, 69 Teile, `p15_bericht_knoepfe.py`): Nach
  dem Klick stand im Bericht **beides**: „Das Modell besteht aus 69 Teilen, von
  denen manche ineinanderstecken.“ mit *Überschneidungen auflösen* und
  „Überschneidungen wurden aufgelöst.“ Ein zweiter Klick hätte einen zweiten
  Reparaturschritt angelegt. `ONE_PIECE_CODES` greift erst, wenn der Körper ein
  Stück ist — hier bleiben viele.
- Behebung: `SETTLED_BY_OFFER` — die Fassung des Befunds, die *Überschneidungen
  auflösen* anbietet, wird von jedem späteren Satz über die Überschneidungen
  desselben Körpers aufgehoben; die Fassung ohne Überschneidung bleibt.
- Nachher: drei Zeilen (kleine Teile, Teil im Teil, „wurden aufgelöst“); Strg+Z
  bringt den Einlesebefund mit Knopf zurück.
- Test: `test_evaluation.py::test_resolved_intersections_settle_the_load_note_that_offered_it` (grün).
- Status: behoben.

### FENSTER-12 · Verständnis · Die Frage vor der Vollerkennung: Liste mit wanderndem Knopf

- Fundstelle: `app/ui/dialogs.py` `AskDialog` (bestehend), benutzt von
  `MainWindow._on_ask` für die neue Frage aus `2c67b684e`.
- Kundensicht vorher (`p02_drache.py`, Dialog abgelesen): Text, darunter eine Liste
  „Sofort laden“ / „Mit Merkmalserkennung laden“, darunter die Knöpfe
  *Sofort laden* und *Abbrechen*. Wer mit Erkennung laden will, muss erst die
  zweite Zeile wählen — dann heißt der Knopf *Mit Merkmalserkennung laden* — und
  dann klicken. Eine Liste mit zwei Handlungen erkennt niemand als Auswahl; der
  Slicer fragt mit zwei Knöpfen.
- Behebung: `AskDialog(as_buttons=True)` zeigt je Antwort einen Knopf, der erste ist
  der Hauptknopf und hat den Fokus; Liste und Antwortknopf bleiben als Ablage der
  Wahl (bestehende Tests und Wege über `list`/`chosen` gelten weiter).
  `MainWindow._answers_as_buttons` schaltet es nur ein, wo keine Kandidaten im Bild
  stehen und zwei oder drei kurze Antworten zur Wahl sind (≤ 40 Zeichen,
  `ANSWER_BUTTON_CHARS`) — Merkmals-, Kanten- und Dateiwahl bleiben Listen.
- Nachher (`p17_frageknoepfe.py`): sichtbar *Abbrechen*, *Sofort laden* (Standard),
  *Mit Merkmalserkennung laden*; gesperrt, solange die Ansicht nicht bereit ist;
  ein Klick antwortet.
- Tests: `test_ui_dialogs.py::test_only_short_actions_without_candidates_become_buttons`
  (grün), `::test_two_ways_are_two_buttons_not_a_list` (Release).
- Status: behoben. (*Abbrechen* bleibt; es lädt ohne Vollerkennung, wie der Satz
  der Frage es ankündigt — „Ohne sie erscheint das Modell sofort“.)

### FENSTER-13 · Verständnis · Strg+Z nach *Offen lassen* sagt „Modell einfügen zurückgenommen.“

- Fundstelle: `app/ui/main_window.py` `action_undo` (Titel aus
  `History._swap_operation`, bewusst der Titel des Schritts).
- Kundensicht vorher (`p15_bericht_knoepfe.py`, offene Schachtel): *Offen lassen*
  ändert den Ladeschritt; Strg+Z nimmt die Änderung zurück, und die Statuszeile
  sagt „Modell einfügen zurückgenommen.“ — das Modell steht aber weiter da. Gleiches
  für *Überschneidungen auflösen* an einem alten Reparaturschritt und jede
  Wertänderung eines Schritts.
- Behebung: `_undone_text` — nimmt Strg+Z nur geänderte Fassungen zurück (keine
  eigenen Schritte, kein Umbau, nichts gelöscht), heißt es „Änderung an „{name}“
  zurückgenommen.“; sonst wie bisher. Der Titel der Transaktion bleibt (Entscheidung
  in `_swap_operation`).
- Katalog: neuer Text „Änderung an „{name}“ zurückgenommen.“
- Test: `test_ui_dialogs.py::test_undoing_a_changed_step_says_the_change_not_the_step` (grün).
- Status: behoben.

### FENSTER-14 · Bedienfehler · Die gewählte Analysekarte kommt nach einer Änderung nicht wieder

- Fundstelle: `app/ui/main_window.py` `_on_busy` / `_show_scene` (bestehend; seit
  `3c36a3950` mit *Reparieren* in der Legende der naheliegende Weg dorthin).
- Kundensicht vorher (`p18_fehlerkarte.py`, drill-holder.3mf): Netzfehlerkarte
  gewählt, Legende zeigt *Reparieren*, Klick → ein Reparaturschritt, und danach:
  Wähler steht auf „Netzfehler“, im Bild keine Karte, Legende leer — auch nach
  60 s nicht. `_show_scene` räumt die Karte ab, die Auswahl, die sie neu
  anstoßen würde, kommt noch während `busy`, und `_analysis_map` lehnt dort ab.
  Danach fragte niemand mehr. Gilt für jede Änderung und jedes Strg+Z mit
  offener Karte.
- Behebung: `_resume_map_after_idle` im Ruhe-Zweig von `_on_busy`: Ist eine Karte
  gewählt, keine gezeigt und keine in Arbeit, wird sie für die Auswahl neu
  angefordert; ein Abbruch des Kunden gilt weiter (`_map_cancelled_for`).
- Nachher: nach *Reparieren* steht die Karte wieder da, mit „Keine Netzfehler
  gefunden.“ und ohne Knopf.
- Test (Release): `test_analysis_ui.py::test_the_chosen_map_comes_back_after_a_change`.
- Status: behoben.

### FENSTER-15 · Leistung · Ein Projekt von einem langsamen Laufwerk hält das Fenster an

- Fundstelle: `app/ui/session.py` `open_project` / `recover` → `load(path)` im
  Hauptfaden (bestehend; RM-224 hat nur Modelle in den Arbeiter geholt).
- Kundensicht vorher: Ein Projekt aus „Zuletzt geöffnet“ auf einem Netzlaufwerk
  öffnen — das Fenster steht, bis das Laufwerk antwortet (bei einem toten bis zum
  Zeitlimit des Systems, laut RM-224 21 s). Die Changelog-Zusage sagt „Modell“ und
  stimmt wörtlich; der Kunde unterscheidet nicht.
- Messung `p22_projekt_oeffnen.py` (Drache als 32-MB-Projekt gespeichert,
  wieder geöffnet, 5-ms-Takt; `load` um 5 s verzögert): vorher längste Lücke
  **5 101 ms**; ohne Verzögerung 127–209 ms.
- Behebung: `_load_beside_the_window` liest in einem Daemon-Faden; solange er
  liest, stellt der Hauptfaden Ereignisse zu, aber keine Eingaben (das Öffnen
  bleibt ein Schritt, niemand bearbeitet mitten darin das alte Projekt; der
  Wartezeiger bleibt). Antwortet die Platte in 50 ms, ist es der gerade Aufruf
  wie vorher; ohne Anwendung (Kommandozeile) ebenso. Ein Abbrechen gibt es auf
  diesem Weg nicht — ein hängendes `stat` lässt sich nicht unterbrechen, der Faden
  hält aber das Beenden nicht auf.
- Nachher, gleiche Sonde: mit 5 s Verzögerung längste Lücke **90 ms**; ohne 54–152 ms.
- Test (Release): `test_ui.py::test_a_project_on_a_slow_drive_does_not_stop_the_window`.
- Status: behoben (ohne Abbrechen — ein asynchrones Öffnen mit Abbrechen hieße,
  dass das alte Projekt während des Lesens bedienbar bleibt; das wäre ein neuer
  Zustand und ist hier bewusst nicht gebaut).

### FENSTER-16 · Absturz · Der Start endet bei doppelter Skalierung mit `AttributeError`

- Fundstelle: `app/ui/main_window.py` `resizeEvent` → `_fit_toolbar` (bestehend).
- Kundensicht: Solidon startet nicht. Gefunden bei der nativen Abnahme (RM-238):
  `QT_SCALE_FACTOR=2` auf diesem 2560 × 1440-Schirm (logisch 1280 × 720 — dieselbe
  logische Größe wie ein Full-HD-Laptop mit 150 %). Beim Bau der Ansicht fragt
  der Renderer nach seinem nativen Fenster (`winId`), dabei entsteht das des
  Hauptfensters samt einer Größenänderung — mitten in `__init__`, bevor es eine
  Werkzeugleiste gibt: `'MainWindow' object has no attribute 'toolbar'`.
- Messung `p30_start.py` (echte Plattform, `QT_SCALE_FACTOR=2`): HEAD-Export
  „START GESCHEITERT: AttributeError …“ (Exit 3), Arbeitsbaum gestartet,
  Fenster 1600 × 1000, schmale Werkzeugleiste.
- Behebung: `resizeEvent` kürzt die Leiste erst, wenn es sie gibt (beim ersten
  Zeigen kommt die nächste Größenänderung ohnehin).
- Test (Release): `test_ui.py::test_a_resize_before_the_toolbar_exists_does_not_end_the_start`.
- Status: behoben. Ob ein echter 150-%-Laptop denselben Weg nimmt, belegt nur ein
  solcher Rechner — der Fehler ist unabhängig davon ein Absturz auf einem Weg,
  den `QT_SCALE_FACTOR` jedem Kunden öffnet.

### FENSTER-17 · Verständnis · Das Fadenkreuz der Stellenwahl verdeckt die Stelle (RM-238)

- Fundstelle: `app/ui/viewport.py` `set_surface_picker`/`_place_surface_picker`
  (Gebiet massbild; seit `2c67b684e` der Weg aus dem Prüfbericht).
- Kundensicht vorher: Das Kreuz war ein `QLabel` mit dem durchsichtigen
  Messzeiger. Als natives Kind der Ansicht (`hold_above_the_view`) kann es über
  der Grafikfläche nicht durchsichtig sein — es stand in einem 32 × 32 Punkte
  großen Quadrat der Fensterfarbe genau über dem Zielpunkt.
- Messung `p29_nativ.py schirm` (echtes, sichtbares Fenster, für die Aufnahme
  obenauf, fremde Fenster per `WindowFromPoint` ausgeschlossen; Aufnahme mit und
  ohne Kreuz): HEAD **1024 von 1024** Bildpunkten des Kreuzrechtecks verdeckt,
  die Mitte (6 × 6 Punkte um den Zielpunkt) **36 von 36**; Arbeitsbaum **160**
  Bildpunkte (die vier Arme), Mitte **0 von 36**. Bilder
  `sonden/fenster/out/p29_mit_kreuz_head.png`, `…_neu.png`.
- Behebung: vier Arme (`_ReticleArm`, je ein volles Rechteck: dunkler Rand
  `ON_LIGHT_FIELD`, heller Kern `ON_DARK_FIELD`, 4 × 10 Punkte, Abstand 4 zur
  Mitte). Deckend dürfen sie sein, die Mitte bleibt frei; keine Fenstermaske
  (`fenstermaske-ueber-vulkan-verliert-das-geraet`). Der obere Arm hält Fokus,
  Namen und Beschreibung wie vorher das `QLabel`. Nebenbei liegt die gezeichnete
  Mitte jetzt genau auf dem gehaltenen Gerätepixel (vorher 0,5–1,0 Gerätepixel
  daneben, Rundung der Zeigergröße).
- Tests: `test_local_recognition_flow.py::test_surface_picker_position_is_clamped_and_drawn_in_logical_pixels`
  (neu gefasst: Arme um die freie Mitte, Faktor 2), `::test_ending_the_surface_picker_gives_the_keyboard_back_to_the_view`
  (grün, ohne Fenster).
- Status: behoben.

### KUNDE-02 (übernommen) · Kleinigkeit · Erststart nennt Slicer mit Dateinamen

- Fundstelle: `app/ui/first_run.py` (drei `addItem(….stem, …)`), richtig nur im
  Druckdialog (`print_settings_dialog._slicer_title`).
- Behebung: `labels.slicer_title` — eine Stelle für beide; der Druckdialog nimmt
  sie (`from app.ui.labels import slicer_title as _slicer_title`), der Erststart an
  allen drei Stellen, mit dem Pfad als Kurzhilfe. Dabei die Lücke der alten Regel
  geschlossen: `/usr/bin/prusa-slicer` hieß „bin“, `…/PrusaSlicer.app/Contents/MacOS/
  PrusaSlicer` hieß „MacOS“ (Plattformen funktionieren gleich) — jetzt Dateiname
  bzw. Paketname. `C:\Program Files\ElegooSlicer\elegoo-slicer.exe` → „ElegooSlicer“,
  Cura → „UltiMaker Cura 5.13.0“.
- Tests: `test_ui_dialogs.py::test_a_slicer_is_named_as_on_its_box` (vier Pfade),
  `::test_the_first_run_names_slicers_like_the_print_dialog` (grün).
- Status: behoben.

### KUNDE-06 (übernommen, entschieden) · Verständnis · „Das Teil ist druckbereit“ erscheint praktisch nie

- Fundstelle: `app/ui/panels.py` `ReportPanel._count_up` und `_preselect`.
- Behebung (Entscheidung Hauptsitzung: Urteil statt Zählung): Ohne Fehler **und
  ohne Warnung** an einem vorhandenen Körper heißt die Kopfzeile
  **„Druckbereit · 1 × Hinweis“** — die Zahl in der Schreibweise der übrigen
  Zählung, weil der Katalog keine Mehrzahl kennt („1 Hinweis“/„2 Hinweise“
  ginge nur mit zwei Schlüsseln je Zahl). Hinweise zählen schon heute nicht als
  `alerts`. Mit einer Warnung bleibt die Zählung — dort ist „druckbereit“ nicht
  sicher (Bauraum, Überhang); ohne jeden Befund bleibt „Keine Befunde. Das Teil
  ist druckbereit.“. Ein Hinweis **ohne Körper** (Einrichtung, „Material
  kalibrieren“) wird nicht mehr vorgewählt; ein Hinweis am Körper (*Auf das
  Bett setzen*) bleibt vorwählbar.
- Katalog: neu „Druckbereit“; der Zwischenstand „Das Teil ist druckbereit.“
  (nur aus diesem Paket) ist wieder entfernt.
- Beleg am Fenster (`p25_urteil.py`, echte Modelle): `dice_w6_16mm_v00.stl`
  „Druckbereit · 1 × Hinweis“, nichts vorgewählt; angelegter Quader dasselbe;
  `screwdriver-holder-hex.stl` (5 mm über dem Bauraum) „0 × Fehler · 1 × Warnung ·
  1 × Hinweis“, die Warnung vorgewählt; Laptopständer 9 Warnungen, Zählung.
  Vorher laut kunde (HEAD): „0 × Fehler · 0 × Warnung · 1 × Hinweis“, der
  Materialhinweis vorgewählt.
- Test (Release): `test_analysis_ui.py::test_a_part_with_only_notes_is_called_ready_to_print`
  (Urteil, keine Vorwahl; Warnung → Zählung; Hinweis am Körper → vorgewählt).
- Status: behoben.

### KUNDE-07 (übernommen) · Bedienfehler · Nach dem Zeichnen steht rechts der Chat

- Fundstelle: `app/ui/main_window.py` `start_sketch` / `finish_sketch`.
- Behebung: Beim Betreten wird der Reiter davor gemerkt (`_tab_before_sketch`),
  beim Verlassen kommt er zurück (sonst der Prüfbericht); wer während der Skizze
  selbst einen anderen Reiter wählte, behält ihn.
- Messung `p20_reiter.py`, HEAD gegen Arbeitsbaum: nach Übernehmen und nach
  Verwerfen HEAD „Chat“ / Arbeitsbaum „Prüfbericht“; vom Chat aus begonnen bleibt
  der Chat.
- Test (Release): `test_sketch_editor.py::test_leaving_the_sketch_brings_back_the_tab_from_before`.
- Status: behoben.

### KUNDE-09 (Dialogteil) · Bedienfehler · Übermaß: Dialog am Weg des Kunden, und *Auf den Bauraum verkleinern* hob das Teil vom Bett

- **Dialog (Gebiet druck, DRUCK-12) am Weg des Kunden belegt** (`p26_uebermass.py`,
  Baum `wt-druck`, nur gelesen): Laptopständer von der Startfläche, Prüfbericht
  „0 × Fehler · 9 × Warnung · 4 × Hinweis“, *An den Slicer übergeben …* sichtbar →
  Druckdialog nach 1,9 s: Zeile oben „„parametric-laptop-riser“ ist 52,45 mm zu
  groß für diesen Drucker (Allgemeiner FDM-Drucker 220 mm). Teilen oder
  verkleinern Sie es — sonst lehnt der Slicer es ab.“ mit *Modell teilen* und *Auf
  den Bauraum verkleinern*; *Slicen* grau mit demselben Satz als Grund; *Im
  Slicer öffnen* aktiv. Stimmt. Vom Fenster aus nötig und erledigt: Der Bericht
  nennt ein Teil mit Warnung nicht „druckbereit“ (KUNDE-06).
- **Nebenfund, behoben:** *Auf den Bauraum verkleinern* (Dialog wie Prüfbericht,
  `MainWindow._scale_after_error`) verkleinerte um die Mitte des Objekts; die
  Unterseite hob sich um die halbe Höhenabnahme. Gemessen (`p27_verkleinern.py`,
  Laptopständer, Knopf an der Berichtszeile): HEAD unten **z = 9,229 mm**, danach
  „Ein Objekt schwebt über dem Druckbett.“ im Bericht; Arbeitsbaum **z = 0,000 mm**,
  kein Schwebe-Hinweis; Maße in beiden 163,5 × 217,8 × 73,6 mm im Bauraum
  220 × 220 × 250. Behebung: `scale_object` mit `about="bed"` (Mitte in X/Y,
  Unterseite in Z). Test (Release):
  `test_ui.py::test_scaling_to_the_build_volume_keeps_the_part_on_the_bed`.
- Status: Dialog stimmt (druck); Verkleinern behoben.

### KUNDE-15 (Kartenteil) · Verständnis · Netzfehlerkarte verlangt eine Wahl, die es nicht gibt, und zeigt eine Rohzahl

- Fundstellen: `app/ui/main_window.py` `_on_map_changed` (ohne Auswahl immer „Wählen
  Sie zuerst ein Objekt im Objektbaum.“), `app/ui/analysis_bar.py`
  (`unknown_count` in der Zeile).
- Kundensicht vorher (`p28_netzfehlerkarte.py` am HEAD-Export, Laptopständer, ein
  Körper, keine Auswahl, „Netzfehler“ im Wähler): „Wählen Sie zuerst ein Objekt im
  Objektbaum.“, keine Karte. Mit Auswahl (laut kunde): Zeile „… Die Suche nach
  Überschneidungen ist unvollständig. Markierte Fehler sind bestätigt; weitere
  sind möglich. · 33140 × nicht bestimmbar (Überschneidungen nicht vollständig
  geprüft)“.
- Behebung: Mit genau einem sichtbaren Körper wählt die Karte ihn selbst
  (`_lone_visible_body`, die Auswahl stößt die Karte an); bei mehreren bleibt der
  Satz. In der Netzfehlerkarte steht die Zahl der unbestimmten Flächen nur noch im
  Tooltip, wenn der Satz der Karte die unvollständige Suche schon sagt.
- Nachher, gleiche Sonde: Auswahl `obj_1`, Karte nach 16 s da, Zeile „Herkunft:
  intern geschätzt · Die Suche nach Überschneidungen ist unvollständig. Markierte
  Fehler sind bestätigt; weitere sind möglich.“, Knopf *Reparieren*, die Zahl im
  Tooltip. Dass die Suche am Ständer nicht bis zum Ende kommt, ist Gebiet
  reparatur (KUNDE-15 Suche).
- Tests (Release): `test_analysis_ui.py::test_an_incomplete_defect_search_says_so_once`,
  `::test_the_defect_map_needs_no_choice_with_one_body`.
- Status: behoben (Kartenteil).

### KUNDE-12 (übernommen) · Bedienfehler · Eine Datei ohne Modell wird Schritt 1 und sperrt das Fenster

- Fundstelle: `app/ui/session.py` `_apply_import_plan`/`import_payload` (der Import
  gilt mit dem Plan als angenommen), `app/ui/main_window.py`
  `_on_import_finished` (merkt die Datei in „Zuletzt geöffnet“, bevor die
  Auswertung gezeigt hat, ob sie ein Modell enthält); bestehend.
- Kundensicht vorher (`p24_kaputt.py` am HEAD-Export, `kaputt.stl` = STL-Text mit
  Facetten ohne gültige Ecke, wie ein abgebrochener Download): kein Dialog, Seite
  „Arbeit“, Schritt 1 `load`, Status „Die Kette hält an — siehe Prüfbericht.“,
  „Zuletzt geöffnet“ `kaputt.stl`. Danach `gut.stl` (Wedge-Lock) abgelegt: Dialog
  „Die Kette hält an — ein neuer Schritt dahinter würde nicht gerechnet. /
  Angehalten ist Schritt 1 (Modell einfügen): Die Datei enthält keine
  Dreiecksgeometrie. / Endung: .stl / Art: Die Eingabe war so nicht verwendbar. /
  Operation: 1“ mit *Eingabe korrigieren*; die gute Datei kam nicht an.
- Behebung: Der Import bleibt vorgemerkt, bis das erste Bild oder Ergebnis ihn
  enthält (`Session._track_import`, `_settle_import`, beide Importwege). Hält
  der Stand an genau seinem Ladeschritt mit einem `ValidationError` (eindeutig
  die Datei) und ist der Import noch die letzte Transaktion, wird er
  zurückgenommen — **ohne Redo** (`History.withdraw`, neu im Kern: undo +
  Redo-Zweig verwerfen, sonst brächte Strg+Y einen Schritt ohne Quelle
  zurück) —, die Quelle geht mit, ein neues Projekt gilt danach als
  ungeändert, und `importRejected` trägt einen `UserError` „Diese Datei ließ sich
  nicht lesen.“ mit dem Grund des Ladeschritts, dem Dateinamen und *Andere Datei
  wählen*. Das Fenster (`_on_import_rejected`) zeigt ihn, bringt die Startfläche
  zurück, wenn das Projekt leer ist, und trägt nichts in „Zuletzt geöffnet“ ein;
  eingetragen wird erst auf `importConfirmed` (`_recent_candidate`). Ein
  anderer Halt am Ladeschritt (Frage ohne Wahl geschlossen, `AmbiguityError`)
  bleibt stehen wie bisher — dort hilft *Schritt erneut öffnen*.
- Dazu die Absage hinter einem Halt (`Session.halt_in_the_way`): ohne die Werte
  „Art“ (bei `op.*`-Befunden der Titel des Fehlers) und „Operation“ (die Nummer
  steht im Satz) — die Handler lesen `op_id`.
- Nachher, gleiche Sonde: nach 2,5 s Dialog „Diese Datei ließ sich nicht lesen. /
  Die Datei enthält keine Dreiecksgeometrie. / Pfad: kaputt.stl“ mit *Andere
  Datei wählen* und *Abbrechen*; Startfläche, keine Schritte, kein Redo, nicht
  geändert, keine Quelle, „Zuletzt geöffnet“ leer. `gut.stl` danach: ohne Dialog
  geladen, „Zuletzt geöffnet“ `gut.stl`.
- Tests (ohne Fenster, grün): `test_evaluation.py::test_a_file_without_a_model_does_not_become_a_step`,
  `::test_a_file_with_a_model_is_confirmed`, `::test_a_broken_file_after_other_work_is_not_withdrawn_blindly`,
  `::test_the_halt_refusal_does_not_repeat_its_sentence`; Fenstertest (Release)
  `test_ui.py::test_a_file_without_a_model_leaves_no_step_and_no_recent_entry`.
- Status: behoben.

### KUNDE-14 (übernommen, entschieden) · Leistung · Das Modell erscheint erst nach seiner Erkennung

- Fundstelle: `app/ui/session.py` `_EvaluationWorker.work` (ein Lauf, Erkennung
  vor dem ersten Ergebnis); Anlass `2c67b684e` (Grenze der automatischen
  Vollerkennung 1 → 1,5 Mio. Dreiecke).
- Kundensicht vorher: Piratenschiff (`pirate+ship+with+sails_stls/obj_15_Assembly.stl`,
  1,22 Mio. Dreiecke) von der Startfläche öffnen — 8 s Einlesen, danach der
  Ladeschleier mit „Merkmale erkennen · 0 %“, bis die Erkennung fertig ist.
- Behebung (Entscheidung Hauptsitzung: Modell zuerst): Der Ladeweg rechnet zweimal
  im selben Arbeiter. Erst ohne Erkennung (`run_evaluation(detect_features=False)`,
  derselbe Weg wie die Live-Vorschau); steht danach ein Netzkörper ab
  `PICTURE_FIRST_TRIANGLES` = 50 000 Dreiecken ohne Merkmale da
  (`_recognition_follows`), geht dieses Bild über `pictureWith` →
  `Session._on_picture` → `pictureChanged` ins Fenster (`MainWindow._on_picture`:
  derselbe Aufbau wie ein Ergebnis, dann weicht der Schleier). Dann der ganze
  Lauf, der die Geometrie aus dem Cache nimmt (dort liegt die rohe Ausgabe,
  gemessen: `load` einmal gerechnet). Das Bild wird `last_result`,
  `result_current` bleibt falsch — Karten, Passungen, Abschlüsse, Antworten im
  Stapel warten weiter auf das Ergebnis; das Kontextmenü „Merkmale an dieser
  Stelle“ bleibt wie bei jeder Rechnung weg. Der Bericht des Bildes trägt statt
  „Vollerkennung ausgelassen“ (die Frage kommt erst danach) die Zeile „Die
  Merkmale sind noch nicht erkannt — Bohrungen und Flächen lassen sich danach
  einzeln wählen.“ (`perceive.pending`); die Schichtanalyse des Berichts startet
  erst mit dem Ergebnis (neben der Erkennung nähme sie ihr den Rechner).
  - **Wann:** `Session.picture_first()` — ein nicht unterdrückter Ladeschritt,
    dessen Körper noch nie im Bild standen (`last_result.object_names`, damit
    zählen auch verbrauchte Körper), oder ein stehendes Bild (eine Änderung
    während der Erkennung zeigt ihr Bild sofort). Jede andere Änderung rechnet
    wie bisher, das Modell bleibt stehen (§15.3). Ein Ladeschritt, an dem der
    letzte Lauf anhielt, rechnet nicht doppelt; hält schon der erste Durchgang
    ohne Körper an, ist er das Ergebnis.
  - **Rückfragen:** Was der erste Durchgang fragt (Einheit), beantwortet der
    zweite aus dem Gedächtnis (`_pending.asked`/`_pending.replay` in
    `ask_from_worker`), die Antwort des Schritts geht mit ins Ergebnis
    (`answers`). `_quality_once` verbraucht erst der zweite Durchgang.
  - **Abbrechen während der Erkennung:** Das Modell bleibt stehen; die Statuszeile
    sagt „Abgebrochen. Das Modell steht da, seine Merkmale sind nicht erkannt —
    die nächste Änderung erkennt sie.“ (statt „der letzte vollständig gerechnete
    Stand“). Bei einer bestätigten Vollerkennung (Drache) kommt wie bisher
    *Ohne Merkmalserkennung laden*.
- Messung `sonden/fenster/p23_schiff.py` (Fenster wie die Anwendung, offscreen;
  „erstes Bild“ = `Viewport.sceneApplied` mit Körper, kein Schleier; Herzschlag
  5-ms-Takt), HEAD-Export (`git archive aeb562ede app`) und Arbeitsbaum
  abwechselnd, je ein Prozess, kalter Cache, **unter Last** (sieben Prüfer):

  | | HEAD (3 Läufe) | Arbeitsbaum (3 Läufe) | Median vorher → nachher |
  |---|---|---|---|
  | Modell im Bild | 59,8 · 33,0 · 31,8 s | 7,5 · 7,3 · 8,8 s | **33,0 → 7,5 s** |
  | Merkmale stehen | 59,8 · 33,0 · 31,8 s | 31,1 · 32,2 · 41,5 s | 33,0 → 32,2 s |
  | längste Lücke im Hauptfaden | 328 · 336 · 280 ms | 283 · 278 · 399 ms | 328 → 283 ms |

  Während der Erkennung: Status „Merkmale erkennen · 0 % · Verstrichen …“ mit
  *Abbrechen*, kein Schleier, Bericht mit vier Zeilen (Übergröße für Karten,
  Reparaturhinweise, `perceive.pending`). Die „0 %“ sind der Fortschritt der
  Erkennung selbst — Gebiet erkennung.
- **Abstimmung mit erkennung** (`reports/erkennung.md`, „Für Nachbarn“, erst nach
  meinem Bau gelesen): Die dort beschriebene Schnittstelle ist genau dieser Weg —
  erster Lauf `detect_features=False`, zweiter Lauf mit demselben Cache, echter
  Anteil während „Merkmale erkennen“, Frage erst im zweiten Lauf. Zwei Stellen
  beim Zusammenführen: (1) erkennung führt `EvaluationResult.recognition_left_out`
  ein; dann wird in `_recognition_follows` aus `not entry.features` genauer
  `entry.id in picture.recognition_left_out` (die Größenschwelle bleibt — sie
  entscheidet, ob sich ein zweites Bild lohnt). (2) Der erste Lauf schreibt
  dort `perceive.too_large` nicht mehr; `_as_picture` filtert ihn trotzdem, das
  schadet nicht. Die Frage „darf während des zweiten Laufs geändert werden?“ ist
  hier entschieden: ja — eine Änderung bricht ihn ab, und der nächste Lauf zeigt
  wieder zuerst sein Bild (`picture_first` bei stehendem Bild). Kleine Modelle:
  unter `PICTURE_FIRST_TRIANGLES` = 50 000 kein zweites Bild; 50 000 statt der
  200 000 aus dem Erkennungsbericht, weil die Kundenrechner (acht Jahre alte
  Hardware) ein Mehrfaches der Messzeit brauchen.
- Tests (ohne Fenster, grün): `test_evaluation.py::test_a_large_import_is_shown_before_its_recognition`
  (ein Bild, ohne Merkmale, `perceive.pending`; Ergebnis mit Merkmalen; `load`
  einmal gerechnet; `picture_first` vorher/mit Bild/danach),
  `::test_a_small_import_is_not_shown_twice`, `::test_the_run_after_the_picture_does_not_ask_again`,
  `::test_a_halted_load_is_not_computed_twice`.
- Status: behoben.

## 3. Sollliste (changelog/de.md, 0.5.1 — Zusagen des Gebiets fenster)

Am Produkt belegt, an Modellen aus `F:\3D Dateien`, am Fenster wie die Anwendung
gebaut (Sonden unter `sonden/fenster/`). „vorher falsch“ heißt: am Stand
`aeb562ede` gemessen falsch, im Arbeitsbaum behoben.

| Zusage | Weg | Beleg | Urteil |
|---|---|---|---|
| Beim Laden und bei langen Rechnungen zählt eine Uhr die verstrichene Zeit mit, auch wenn der Fortschritt stillsteht | Piratenschiff und Drache von der Startfläche | `p23_schiff.py`: „Merkmale erkennen · 0 % · Verstrichen: 7 s … 30 s“ bei stehendem Anteil; `p02_drache.py`: „Modell einfügen · 0 % · Verstrichen: 4 … 14 s“ | stimmt |
| Ein Modell auf einem langsamen oder nicht antwortenden Laufwerk friert das Fenster beim Öffnen nicht mehr ein | Lesen um 8 s / 20 s verzögert | `p01_lesen.py` Lage D, `p05_schliessen_beim_lesen.py`: Fenster bedienbar; *Abbrechen* frei nach 0,06 s (vorher 6,1 s), Schließen 0,07 s (vorher 19,2 s) — FENSTER-02; ein **Projekt** vom langsamen Laufwerk hielt das Fenster weiter an (5,1 s → 90 ms, FENSTER-15) | stimmt (Modell); fürs Projekt vorher falsch, behoben |
| Ist eine Datei aus *Zuletzt geöffnet* verschoben worden, sagt Solidon das und bietet *Andere Datei wählen* an | verschobenes Modell und verschobenes Projekt aus der Liste | `p01_lesen.py` Lage B: „Diese Datei ließ sich nicht lesen.“ mit *Andere Datei wählen*, bei `.p3d` führt der Knopf zu *Öffnen*; der tote Eintrag verschwindet nach dem Versuch | fürs Modell stimmt, fürs Projekt vorher falsch (Fehlerbericht angeboten) — FENSTER-01, behoben |
| Eine Datei, die sich nicht lesen ließ, landet nicht mehr in *Zuletzt geöffnet*, und die nächste Datei meldet nicht deren Namen | `kaputt.stl` (Facetten ohne Ecke), danach `gut.stl` | `p24_kaputt.py`: HEAD `kaputt.stl` in der Liste, Schritt 1, jede weitere Datei abgewiesen; Arbeitsbaum: Dialog mit *Andere Datei wählen*, Liste leer, danach `gut.stl` geladen, Titel „gut (ungespeichert)“, Liste `gut.stl` | vorher falsch für inhaltlich kaputte Dateien — KUNDE-12, behoben |
| Bis 1,5 Mio. Dreiecke von selbst erkannt; bis 5 Mio. fragt Solidon vorher und nennt Speicherbedarf und Dauer auf Ihrem Rechner | Piratenschiff (1,22 Mio.), Drache (2,33 Mio.) | Schiff ohne Frage, 8 Merkmale; Drache: Frage „… 2,3 Millionen Dreiecke … 1 bis 8 Minuten, auf langsamen Rechnern länger, … etwa 5 GB …“ mit Knöpfen *Sofort laden* / *Mit Merkmalserkennung laden* / *Abbrechen* (`p02_drache.py`). Seit KUNDE-14 steht das Modell **vor** der Erkennung und vor der Frage im Bild (Schiff 7,5 s statt 33 s; Drache Bild nach 22,7 s, Frage unmittelbar danach) | stimmt; der Preis dafür (erst nach der Erkennung ein Bild) ist behoben |
| Wer ablehnt, holt die Erkennung mit *Alle Merkmale erkennen* nach; dauert sie zu lange, lädt *Ohne Merkmalserkennung laden* ohne | Drache: *Sofort laden* → *Alle Merkmale erkennen* → *Mit Merkmalserkennung laden* → *Abbrechen* → *Ohne Merkmalserkennung laden* | `p02_drache.py` (Arbeitsbaum): Frage nach 0,6 s, Abbrechen frei nach 0,31 s, Knopf sichtbar, danach in 0,1 s geladen, Absage am Ladeschritt, Statuszeile leer (FENSTER-06) | stimmt |
| *Merkmale an einer Stelle erkennen* … Die Stelle lässt sich auch per Tastatur wählen | Drache: Bericht → Knopf → Pfeile → Enter; `plate_holes.stl` in vier DPI-Stufen, sichtbar für Fokus und Aufnahme | `p07_stelle.py`, `p29_nativ.py` (RM-238): Treffer genau unter dem Kreuz in jeder Stufe, Fokus beim Kreuz, Escape gibt ihn zurück; die Suche 58 → 21,6 s (FENSTER-10); das Kreuz verdeckte die Stelle (FENSTER-17) | stimmt nach den Behebungen |
| Die Netzfehlerkarte zeigt heile Stellen in Körperfarbe und trägt *Reparieren* in der Legende | Laptopständer, „Netzfehler“ ohne Auswahl | `p28_netzfehlerkarte.py`: HEAD verlangt eine Auswahl, keine Karte; Arbeitsbaum Karte, *Reparieren*, Satz zur unvollständigen Suche ohne Rohzahl (KUNDE-15); nach *Reparieren* kommt die Karte wieder (FENSTER-14) | stimmt nach den Behebungen; dass die Suche am Ständer nicht bis zum Ende kommt, ist reparatur |
| Der Prüfbericht nach dem Einlesen ist kürzer … wo sich etwas tun lässt, steht ein Knopf | Bohrmaschinenhalter, offene Schachtel | `p15_bericht_knoepfe.py`: Knöpfe *Überschneidungen auflösen*, *Offen lassen*, *Stelle zeigen*; nach dem Auflösen blieb die alte Zeile mit Knopf (FENSTER-11), Strg+Z sagte „Modell einfügen zurückgenommen.“ (FENSTER-13) | stimmt nach den Behebungen |
| Große Baugruppen lesen schneller ein (Reparatur des Piratenschiffs 3,6 statt 6 s) | Piratenschiff | Gebiet reparatur; am Fenster sah kunde 6,7 gegen 6,8 s | nicht mein Gebiet (reparatur) |

Sonst berührt das Gebiet fenster keine Zusage; die Oberflächenzeilen der
Zusagen anderer Gebiete (Druckdialog, Maße im Bild) belegen deren Prüfer.

## 4. Übertrag aus dem Register

### RM-233 — fünf Kleinigkeiten (am Stand `aeb562ede` nachgemessen)

1. **`autosave` wirft im Zeitgeber** — bestätigt und behoben, zusammen mit dem
   Stillstand, den dieselbe Stelle verursachte: FENSTER-08.
2. **Kontextmenü der Skizze wird nie freigegeben** — bestätigt, und nicht nur
   dort. Sonde `p12_menues.py`, zehn Rechtsklicks, `QMenu`-Kinder vorher/nachher:
   HEAD Zeichenfläche 0 → 10, Bedingungsliste 11 → 21, **Startfläche
   („Zuletzt geöffnet“, *Aus der Liste entfernen*) 0 → 10**; Arbeitsbaum
   0 → 1, 2 → 2, 0 → 1 (das eine ist das `deleteLater` der letzten Runde).
   Behebung: `deleteLater` nach `exec` in `SketchCanvas._context_menu`,
   `SketchPanel._constraint_menu` (auch für das leere Menü, das nie aufging)
   und `StartScreen._on_recent_menu`. Tests (Release):
   `test_sketch_editor.py::test_the_sketch_menus_do_not_stay_behind`,
   `test_start_screen.py::test_the_recent_menu_does_not_stay_behind`. **Behoben.**
3. **Objektnamen in der Sprache des Augenblicks** — am heutigen Code bereits
   behoben: `Scene.unused_name` nimmt und liefert `TranslatableText`
   (`types.py:1511`), *Drehdeckel* (`lid.py:1494`) und *Prüfstück*
   (`prepare_ops.py:14293`, `cache_version` 2) reichen `_(…)` durch; Nachweis
   `test_missing_ops.py::test_the_screw_lid_name_follows_the_language`
   (Französisch gerechnet, deutsch gelesen, mit Zähler). Nichts zu tun.
4. **„Schwerpunkt“ statt Hüllquadermitte** — bestätigt: `transform.anchor_point`
   rechnet `bounds.centre`, die Auswahl heißt „Mitte“, die Kurzhilfe von
   *Drehen*, *Skalieren* und *Spiegeln* sagte „Schwerpunkt“, „Weltnullpunkt“,
   „Aufstandsfläche“ — drei andere Wörter als die Auswahl daneben („Mitte“,
   „Ursprung“, „Druckbett“). Behebung: die drei `doc`-Sätze in
   `app/core/geom/ops.py` nennen die Wörter der Auswahl; fünf Kataloge
   nachgezogen, alte Schlüssel entfernt. Test:
   `test_transform.py::test_the_centre_anchor_is_called_what_it_computes`
   (L-Winkel, bei dem Hüllmitte und Schwerpunkt auseinanderliegen; grün).
   **Behoben.**
5. **Rückfragekarte fest 520 Punkte** — bestätigt am echten Fenster (Plattform
   `windows`, verborgen, `p13_rueckfragekarte.py`): Bei 1024 und 1280 Punkten
   Fensterbreite stand sie oben mittig **unter** Objektbaum und Prüfbericht,
   weil kein freier Streifen 520 breit war. Behebung: `SurveyNotice.width_for`
   nimmt den freien Streifen bis hinunter zur Breite ihrer zwei Knöpfe (am
   echten Fenster 252 Punkte, Untergrenze `NOTICE_MIN_WIDTH` 240). Nachher bei
   1280: 282 × 158 Punkte zwischen den Karten, verdeckt von nichts; bei 1600
   unverändert 520. **Bei 1024 × 760 gab es keinen freien Ort** — zwischen den
   Karten 125 Punkte, darunter kein Band hoch genug —, und die Karte stand oben
   in der Mitte, verdeckt, und wartete auf eine Antwort, die niemand geben
   konnte. Jetzt lädt die Uhr dort nicht ein (`SurveyNotice.has_room`,
   `_free_spot`; `MainWindow._offer_survey` wartet wie bei einer laufenden
   Rechnung und fragt eine Minute später wieder). Gemessen (`p33_einladung.py`,
   echte Plattform, `_offer_survey` wie die Uhr): HEAD 1024 und 1280 Karte
   520 × 110 **unter** beiden Karten, 1600 frei; Arbeitsbaum 1024 **keine Karte,
   Uhr läuft**, 1280 282 × 158 frei, 1600 520 × 110 frei. Tests (Release):
   `test_feedback.py::test_the_survey_card_narrows_before_it_hides_under_the_cards`,
   `::test_the_survey_card_only_speaks_where_it_can_be_seen`. **Behoben.**

### RM-238 — lokale Erkennung aus dem Bericht und per Tastatur

Sonde `p07_stelle.py`, echte Plattform (`windows`), alle Fenster verborgen, am
Mausoleum-Drachen nach *Sofort laden*:

- Bericht → *Merkmale an einer Stelle erkennen*: Auswahl bereit, Ziel genau
  `obj_1` (aus dem Befund, nicht aus dem Baum), Fadenkreuz gesetzt und sichtbar,
  Ansage „Wählen Sie eine Oberfläche: klicken oder mit Pfeiltasten zielen und Enter
  drücken. Escape beendet die Auswahl.“ — stimmt.
- Escape: Auswahl, Fadenkreuz und Marke weg — stimmt.
- Pfeile an die Ansicht: 8 Gerätepixel, mit Umschalt 1 (675/445 → 666/453) —
  stimmt; die Marke folgt. Unter dem Kreuz ein Treffer am Original; Enter öffnet
  das Suchfenster — stimmt.
- Suche → Befund mit Wegen (*Suchradius verkleinern*, *Dreiecke verringern*),
  neuer Radius sucht sofort — stimmt; zwei Befunde daran behoben (FENSTER-09,
  FENSTER-10).
- **Native Abnahme (Fokus, Darstellung, DPI) — jetzt belegt** (`p29_nativ.py`,
  echte Plattform `windows`, nicht offscreen, `plate_holes.stl`, Weg über
  `LocalRecognitionFlow.arm`):
  - **DPI** (verborgen, `QT_SCALE_FACTOR` 1 · 1,25 · 1,5 · 2): Grafikfläche
    1350 × 890 · 1685 × 1113 · 2022 × 1335 · 2696 × 1780 Gerätepixel; ein Pfeil
    8 · 10 · 12 · 16 Gerätepixel (8 Punkte), Umschalt 1 · 1,2 · 1,5 · 2 (1 Punkt);
    gezeichnete Kreuzmitte gegen gehaltenen Trefferpunkt 0,0 · 0,2 · 0,0 · 0,0
    Gerätepixel daneben (HEAD 0,5 · 0,9 · 0,8 · 1,0); unter dem Kreuz in jeder Stufe
    derselbe Treffer am Original (`obj_1`, 13,9 / −6,2 / 8,0 mm); Enter öffnet das
    Suchfenster. Stimmt. Bei Stufe 2 startete HEAD gar nicht — FENSTER-16.
  - **Fokus** (sichtbares Fenster, obenauf): Fenster aktiv, Tastaturfokus beim
    Kreuz (`_ReticleArm`, vorher `QLabel`), Escape gibt ihn der Ansicht zurück
    (`focusChanged`: `_ReticleArm -> Viewport`). Stimmt.
  - **Darstellung**: Das Kreuz verdeckte die Stelle — FENSTER-17, behoben.
- Übernehmen und Strg+Z an einer gefundenen Fläche konnte die Sonde am Drachen
  nicht fahren: an der Stelle unter dem Kreuz gibt es kein ganzes Merkmal. Der
  Weg Übernehmen → eine Transaktion → Strg+Z ist durch
  `test_local_recognition_flow.py::test_local_edit_has_one_transaction_and_restores_original_on_undo`
  abgedeckt (Release).

Stand: RM-238 vollständig belegt; zwei Befunde daraus behoben (FENSTER-16, -17).
Offen bleibt nur, was ausschließlich ein Mensch prüft: ein Bildschirmleser, der
Namen und Beschreibung des Kreuzes vorliest.

### RM-131 — Mehrfachimport

Am Code nachgesehen: `MainWindow.dropEvent` öffnet von mehreren gezogenen Dateien
die erste und sagt die übrigen an („{count} weitere Dateien nicht geöffnet —
bitte einzeln einfügen.“, `_say_files_left_out`). Der Registerpunkt lautet
„Mehrfachimport **bewusst zurückgestellt lassen**“ — eine Entscheidung Roberts
über den Umfang, keine offene Wahl. Nicht gebaut; Stand unverändert.

## 5. Geprüft und in Ordnung

- **Uhr und Restzeit** (`loading.ProgressTiming`, `a5e6bf614`, `49d898d48`): Der
  Sekundentakt läuft bei stehendem Anteil weiter (Schiff 30 s bei 0 %), eine
  Kernfrage zählt nicht als Rechenzeit, sinkt der Anteil, rechnet die Uhr neu —
  gelesen und am Drachen und am Schiff gesehen; nur der Sprung nach einer
  0-%-Zeile war falsch (FENSTER-05).
- **Frage vor der Vollerkennung** (`2c67b684e`): Der Text nennt Dreiecke, Minuten
  auf diesem Rechner und Speicher; die Antwort geht sofort an den Stapel
  (`recognitionAnswered` → `_record_recognition_answer`), ein Abbruch danach
  fragt nicht noch einmal (`p02_drache.py`: „Fragen: 1“). Mit dem Bild vor der
  Erkennung unverändert — die Frage kommt aus dem zweiten Durchgang.
- **Überholte Läufe** (`Session._outdated`, `_stale`, `_on_thread_done`): Ein
  Bild eines überholten Arbeiters wird wie sein Ergebnis verworfen
  (`_on_picture` fragt `_stale` und das Abbruchsignal).
- **Ladeanzeige** (`_update_veil`, `LoadingVeil`): verdeckt nur das leere Bild und
  weicht mit dem ersten Bild (Schiff: kein Schleier ab 7,5 s); 37 Malvorgänge am
  Drachen zusammen 0,27 s (`p04e_malen.py`).
- **Lesen im Arbeiter** (`_ReadWorker`, RM-224): kein Dateizugriff im Hauptfaden
  beim Einfügen; ein `OSError` wird ein Hinweis mit Weg, kein Fehlerbericht
  (`p01_lesen.py` Lage A und B).
- **Knöpfe im Prüfbericht** (`3c36a3950`, `2b83f72a5`): *Überschneidungen
  auflösen*, *Offen lassen*, *Stelle zeigen*, *Dicke geben*, *Reparieren* in der
  Legende führen je genau eine Transaktion aus, Strg+Z nimmt sie zurück
  (`p15_bericht_knoepfe.py`, `p18_fehlerkarte.py`).
- **Tastaturweg der Stellenwahl** (`LocalRecognitionFlow.arm`,
  `Viewport._surface_picker_key`): Pfeile 8 Punkte, Umschalt 1 Punkt, Enter trifft
  den Originaltreffer unter dem Kreuz, Escape beendet — in vier DPI-Stufen gleich
  (`p29_nativ.py`).
- **Drucken aus dem Bericht bei Übermaß** (druck, DRUCK-12): Zeile, zwei Knöpfe,
  *Slicen* grau mit Grund, am Weg des Kunden belegt (`p26_uebermass.py`).
- **Rückfragekarte bei 1280 und 1600 Punkten**: frei zwischen den Karten, verdeckt
  von nichts (`p33_einladung.py`).
- **Kontextmenüs** (RM-233/2): Nach zehn Rechtsklicks bleibt kein `QMenu` liegen
  (`p12_menues.py`).

## 6. Katalogschlüssel, geänderte Dateien, Tests

### Katalogschlüssel (alle fünf Kataloge `en`, `es`, `fr`, `it`, `pt`)

Neu:

- „Abgebrochen. Das Modell steht da, seine Merkmale sind nicht erkannt — die nächste Änderung erkennt sie.“ (KUNDE-14)
- „Die Merkmale sind noch nicht erkannt — Bohrungen und Flächen lassen sich danach einzeln wählen.“ (KUNDE-14, Befund `perceive.pending`)
- „Druckbereit“ (KUNDE-06)
- „Die automatische Sicherung ließ sich nicht schreiben — prüfen Sie den freien Speicherplatz und speichern Sie das Projekt selbst.“ (FENSTER-08)
- „Änderung an „{name}“ zurückgenommen.“ (FENSTER-13)
- „Der Punkt, der stehen bleibt: Mitte des Objekts, Ursprung oder Druckbett — oder ein genannter Punkt, damit mehrere Körper zusammen wachsen.“ (RM-233/4)
- „Mitte des Objekts, Ursprung oder Druckbett — oder ein genannter Punkt, um den mehrere Körper gemeinsam drehen.“ (RM-233/4)
- „Wo die Spiegelebene liegt: in der Mitte des Objekts, im Ursprung oder am Druckbett.“ (RM-233/4)

Entfernt (der Code nennt sie nicht mehr):

- „Der Punkt, der stehen bleibt: Schwerpunkt, Nullpunkt, Aufstandsfläche — oder ein genannter Punkt, damit mehrere Körper zusammen wachsen.“
- „Schwerpunkt des Objekts, Weltnullpunkt, Aufstandsfläche — oder ein genannter Punkt, um den mehrere Körper gemeinsam drehen.“
- „Wo die Spiegelebene liegt: Schwerpunkt, Nullpunkt oder Aufstandsfläche.“
- „Das Teil ist druckbereit.“ (nur ein Zwischenstand dieses Pakets)

Unverändert benutzt: „Diese Datei ließ sich nicht lesen.“, „Andere Datei wählen“.
Die drei Wächter von texte (Handlung an Warnungen und Fehlern,
Konstrukteurswörter, zitierte Knöpfe) halten die neuen Texte ein:
`perceive.pending` ist ein Hinweis, keine Formulierung enthält ein Wort der
Liste, keine zitiert einen Knopf.

### Geänderte Dateien

Gebiet fenster: `app/ui/main_window.py`, `app/ui/session.py`, `app/ui/panels.py`,
`app/ui/loading.py`, `app/ui/local_recognition.py`,
`app/ui/local_recognition_flow.py`, `app/ui/dialogs.py`, `app/ui/labels.py`,
`app/ui/first_run.py`, `app/ui/start_screen.py`, `app/ui/survey.py`,
`app/ui/analysis_bar.py`, `app/ui/sketch_editor.py`, `app/ui/CLAUDE.md`,
`.claude/rules/wartezeit.md`, die fünf Kataloge.

**Änderungen außerhalb des Gebiets** (mit Grund):

| Datei | Gebiet | Was | Befund |
|---|---|---|---|
| `app/core/ingest/threemf.py` | reparatur | `_parse_model`, `_reading_trees`, `_release`, `XML_CHUNK`; `read`/`read_objects` als Hülle um `_read_groups`/`_read_objects`; `ET.fromstring` → `_parse_model` an drei Stellen; `_numbers_in_blocks` | FENSTER-03 |
| `.claude/rules/dateiformat.md` | reparatur/druck | Absatz „Ein 3MF-Modell wird nie am Stück geparst“ unter *Formate* | FENSTER-03 |
| `app/core/scene/history.py` | erkennung | neu `History.withdraw` (nach `redo`) | KUNDE-12 |
| `app/core/scene/evaluate.py` | erkennung/reparatur | `SETTLED_BY_OFFER`, `_without_settled` | FENSTER-11 |
| `app/core/scene/project.py` | reparatur | `load`: `missing_file`/`unreadable` mit Titel und *Andere Datei wählen* | FENSTER-01 |
| `app/core/geom/ops.py` | bohrung | drei `doc`-Sätze (Mitte, Ursprung, Druckbett) | RM-233/4 |
| `app/ui/viewport.py` | massbild | `_ReticleArm`, `RETICLE_*`, `set_surface_picker`, `_place_surface_picker` | FENSTER-17 |
| `app/ui/print_settings_dialog.py` | druck | `_slicer_title` aus `labels.slicer_title` | KUNDE-02 |

**Zusammenführung, genau benannt:**

- `main_window.py`/`panels.py` mit **massbild**: keine Überschneidung. massbild
  ändert `main_window.py` nur bei HEAD-Zeile 16409–16553 (Maße im Bild),
  `panels.py` bei 2034 (`ObjectTree`), 5953 (`_set_shown`), 6639 und 7630
  (`FeaturePanel`). Meine Stellen in `main_window.py`: `_undone_text`,
  `ANSWER_BUTTON_CHARS`, `_answers_as_buttons` (nach `_edge_labels`), der
  Autosave-Zeitgeber im Konstruktor, `_tab_before_sketch`, `_choose_another_file`,
  `_connect_session` (`pictureChanged`, `importRejected`, `importConfirmed`,
  `_recent_candidate`), `_confirm_close` (Autosave zweimal), `open_path`
  (Fehlerzweig), `action_undo`, `start_sketch`/`finish_sketch`,
  `_on_map_changed`, `_lone_visible_body`, `_on_scene`/`_on_picture`,
  `_show_scene` (Schichtanalyse nicht für das Bild), `_on_import_failed`,
  `_on_import_finished`/`_on_import_confirmed`/`_on_import_rejected`,
  `_update_header` (Titelleiste), `_on_busy`/`_resume_map_after_idle`,
  `_on_evaluation_cancelled`/`_load_without_recognition`, `_update_veil`,
  `_on_ask` (`as_buttons`), `error_handlers` (`choose_another_file`),
  `_scale_after_error`, `_offer_survey`, `resizeEvent`, `_autosave_failed`. In
  `panels.py`: `ReportPanel._preselect` (Hinweis ohne Körper) und `_count_up`
  (Urteil).
- `main_window.py` mit **reparatur** (HEAD 20045 +3, 20583 +25) und **texte**
  (12829, 12836, 20123 +2, 20662 +15): Die nächste eigene Stelle ist 20068
  (`choose_another_file`, eine Zeile) — 23 Zeilen Abstand, der Kontext trägt.
- `viewport.py` mit **texte** (HEAD 7095–7102: Beschreibung des Kreuzes neu
  formuliert): Mein Hunk ersetzt die Zeilen **davor** (`QLabel` → vier
  `_ReticleArm`) und danach (`_surface_picker_arms`); die zwei Textzeilen selbst
  bleiben stehen. Beim Zusammenführen den Wortlaut von texte übernehmen.
- `threemf.py` mit **druck** (HEAD 683–701 in `read_objects`, 1659–1715 in
  `_leaves`): Konflikt wahrscheinlich. Meine Änderung dort ist klein und
  mechanisch nachzubauen: nach dem Docstring von `read_objects` die Hülle
  `with _reading_trees(): return _read_objects(payload, findings)` und der Rumpf
  als `_read_objects`; dasselbe für `read`/`_read_groups`; in `_leaves` und
  `_read_groups` `ET.fromstring(...)` → `_parse_model(...)`; der neue Block
  (`XML_CHUNK` … `_release`) vor `NUMBER_BLOCK`; Importe `gc`, `Iterator`,
  `contextmanager`, `ContextVar`.
- `print_settings_dialog.py` mit **druck**: nur der Import von `_slicer_title`
  (eine Zeile) statt der lokalen Funktion.

### Gefahrene Tests

Ausgaben in `sonden/fenster/out/fenster-*.txt`, Exit-Code jeweils unmittelbar
gelesen.

| Lauf | Exit | Ergebnis |
|---|---|---|
| `ruff check .` | 0 | All checks passed |
| `ruff format --check .` | 0 | 1268 files already formatted |
| `mypy` | 0 | no issues in 323 source files |
| `pytest tests/test_language_rules.py` | 0 | 395 passed |
| `tools/affected_tests.py <alle geänderten Dateien> --run` | — | 343 Testdateien (Kataloge, `history.py`, `session.py`: praktisch die Suite); nach 1 h 30 unter fünf parallelen Suiten von der Hauptsitzung angehalten, ohne Ergebnis |
| stattdessen die Testdateien der geänderten Module, ohne Fenster (`-p tools.list_windowed_tests --window-group plain`): `test_evaluation`, `test_threemf_assembly`, `test_threemf_native_materials`, `test_history`, `test_project`, `test_loading`, `test_local_recognition_flow`, `test_ui_dialogs`, `test_transform`, `test_language_rules`, `test_translations`, `test_wording`, `test_directory_docs`, `test_analysis_ui`, `test_feedback`, `test_start_screen`, `test_sketch_editor`, `test_ui`, `test_value_labels`, `test_errors`, `test_registry_consistency`, `test_ingest`, `test_leash`, `test_widget_lifetime`, `test_overlay` | 1 | **3043 passed, 1 skipped, 6 failed**, 1389 Fenstertests abgewählt, 8 min |

Die sechs roten sind
`test_wording.py::test_every_manual_paragraph_reaches_the_generated_page[de|en|es|fr|it|pt]`:
Die erzeugte Handbuchseite der Website ist älter als die Quelle. Die fehlenden
Absätze stammen aus `extras` (lokales Modell, dreimal), `models`, `repair` und
`holes` — keiner aus diesem Paket (die geänderten `doc`-Sätze von Drehen,
Skalieren, Spiegeln stehen nicht in der Liste). Die Seite entsteht beim Release
mit `tools/make_manual.py` (Handbuch nur beim Paketbau); kein Befund dieses
Pakets.

Fenstertests geschrieben oder angepasst, nicht gefahren (Release): `test_ui.py`
(`test_a_file_without_a_model_leaves_no_step_and_no_recent_entry`,
`test_scaling_to_the_build_volume_keeps_the_part_on_the_bed`,
`test_a_resize_before_the_toolbar_exists_does_not_end_the_start` und die
früheren dieses Pakets), `test_analysis_ui.py`
(`test_an_incomplete_defect_search_says_so_once`,
`test_the_defect_map_needs_no_choice_with_one_body`,
`test_a_part_with_only_notes_is_called_ready_to_print`), `test_feedback.py`
(`test_the_survey_card_only_speaks_where_it_can_be_seen`) — ihr Verhalten ist
per Sonde am Fenster belegt (Abschnitt 2).

## 7. Registersätze

- **FENSTER-03, Rest — Der Qt-Takt steht beim Parsen großer 3MF bis 2 s, ohne GIL
  und ohne CPU.** Gemessen: ein Python-Faden daneben ohne Lücke, der Hauptfaden
  0,03 s CPU in 4,3 s Lücke, in `exec()` ohne Python-Rahmen; bei HEAD in den
  GIL-Lücken verborgen. Ausgeschlossen: Speicherbereiniger, Ladeanzeige,
  Picker-Aufwärmen, Zeitgebertyp, GIL-Abgabe zwischen den Stücken. Nächster
  Schritt: ein nativer Stapelabtaster am Hauptfaden während des Drachenimports
  (etwa `py-spy dump --native`, MIT, Entwicklerwerkzeug — nicht Teil des Pakets,
  braucht aber die Freigabe, es in die Arbeitsumgebung zu holen). Empfehlung:
  freigeben und eine halbe Stunde messen; Nutzen: das Fenster während großer
  Importe flüssig.
- **RM-131 bleibt zurückgestellt** (Roberts Entscheidung, unverändert).

## Für Nachbarn

- **erkennung:** Während der Erkennung nach dem Bild steht die Statuszeile auf
  „Merkmale erkennen · 0 %“ (am Schiff 25 s lang) — die Uhr zählt, der Anteil
  nicht. Echter Fortschritt aus `detect` ist der einzige fehlende Teil von
  KUNDE-14; die Oberfläche braucht dafür nichts Neues (`progress` wie bisher).
  Und aus FENSTER-10: Am Drachen braucht die Suche an einer Stelle mit 10 mm
  Radius nach dem Cache-Treffer noch 15 bis 19 s, bis `perceive/local.py`
  „zu viele Dreiecke“ sagt — die Absage könnte vor der Rechnung stehen.
- **druck (DRUCK-14):** Mit dem Bild vor der Erkennung startet die Schichtanalyse
  des Prüfberichts erst mit dem Ergebnis (neben der Erkennung nahm sie ihr den
  Rechner). Öffnet ein Kunde den Druckdialog, während noch erkannt wird, findet
  `_AdviceWorker` also noch keine gemerkte Analyse und schneidet selbst — wie vor
  DRUCK-14/1. Kein Fehler, nur kein Gewinn in diesem Zeitfenster. Die doppelte
  Fensterzeit selbst hat druck gefunden und behoben.
- **reparatur:** `threemf.py` siehe Zusammenführung; und am Laptopständer kommt
  die Überschneidungssuche nicht bis zum Ende (KUNDE-15, 33 140 unbestimmte
  Flächen) — die Karte sagt es jetzt ohne Rohzahl.
- **massbild:** Das Fadenkreuz ist Oberfläche über der Ansicht (`viewport.py`),
  gebaut ohne Maske als vier deckende Arme (FENSTER-17). Wer „Tinte über dem
  Bild“ lieber im Renderer hat, kann die Arme dorthin verlegen — Fokus und Namen
  brauchen dann weiter ein kleines Widget.
- **alle Sondenbauer:** `os._exit` bei laufender Schichtanalyse oder laufendem
  Vorschaubild endete in 2 von 12 Drachenläufen mit einer Zugriffsverletzung beim
  Beenden (kein Produktfehler; die Anwendung wartet ihre Arbeiter in `release`
  ab). Sonden sollten vor `os._exit` `window.session.release()` rufen und die
  Arbeiter des Fensters abwarten.
- **Hauptsitzung:** Beim ersten Tor dieser Sitzung habe ich `ruff.txt`,
  `fmt.txt` und `mypy.txt` im gemeinsamen Scratchpad geschrieben, bevor die
  Warnung kam — falls massbild seine gleichnamigen Ausgaben dort braucht, sind sie
  überschrieben. Seither liegt alles unter `sonden/fenster/out/fenster-*`.
