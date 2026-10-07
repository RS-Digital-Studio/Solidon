# Übergabe: Gesamtprüfung und RM-281 (Herstellerprofil) bis v0.5.1

## Matrixwerkzeug für die Gesamtabnahme (04.10.2026, RM-281 Paket 3)

**Seit RM-530 liegt das Werkzeug in `tools/`:** `treiber.py` heißt
`tools/matrix_driver.py`, `einheit.py` `tools/matrix_unit.py`, `bericht.py`
`tools/matrix_report.py`, `matrix_config.py` `tools/matrix_config.py` und
`gcode_lesen.py` aus `uebergabe-matrix-2026-09-27/` `tools/matrix_gcode.py`.
Die alten Namen unten meinen diese Dateien; geändert wird nur noch dort.

Stand des Zweigs `claude/rm281-paket3`: `einheit.py` geht den Weg des
Druckdialogs mit dessen eigenem Code (`_AdviceWorker._calculate`,
`_PlateJob`/`_prepare_plate`, Aufruf aus `_SliceWorker`, `plates_findings`),
mit Stufenprozess, Zeit ab der ersten Schicht gegen Solidons Schätzung,
Stützweg je Körper (`support_ways`), Marken „Slicer stützt nicht“,
„Stützvorschlag ohne Stütze“ und „Zeit ab Schicht 1 weicht ab“ und
Auslegen über Platten, wenn die Übergabe „keine Anordnung“ meldet. Bilder mit
Pillow. Aufruf aus dem Arbeitsbaum, Kerne über die Masken im Treiber:

```
python tools/matrix_driver.py <code-wurzel> <ausgabe> probe|modelle|drucker [--arbeiter 2]
python tools/matrix_report.py <ausgabe> > bericht.md
```

`probe` sind die drei Abnahmemodelle über die sieben Heimkombinationen; der
Gesamtlauf ist `modelle` auf einem eingefrorenen Codestand (eigener
Arbeitsbaum, nicht der laufende), weil der Treiber am Ende Code- und
Profilstand gegen den Beginn prüft.

## JETZT (28.09.2026, 10:45)

- **Gesamt-Nachtrag auf main** (Merge `99c0ac7bb`); die Release-Sitzung hat N6
  selbst behoben (`effaef006`, Dateiexport mit `job`). `F:\3D Druck.gesamtfix`
  und der Zweig `uebergabe-gesamtpruefung` sind entfernt.
- **Einfügen F1 „einmal legen, festhalten“ fertig und gemeldet:** Endcommit
  `bc901772c` auf `einfuegen-freier-platz` (Agent `a405d443dfd109de6`), Tor
  17 994/18 053 Exit 0, mypy ×3 grün, Gegenprobe der drei Bohrtests am Stand
  `cf1015de2` selbst nachgefahren (rot), am neuen Stand grün. Bericht
  `output/review/einfuegen-2026-09-28/nachtrag-f1.md`. Arbeitsbaum
  `F:\3D Druck\.claude\worktrees\agent-a405d443dfd109de6` bleibt bis zum Merge
  der Release-Sitzung stehen, danach entfernen (Zweig löscht sie).
- **Einfügen auf main (`da1541794`), Register RM-303 bis RM-306.** Arbeitsbaum
  und Zweig entfernt; lokal nur noch `main`. Die Release-Sitzung fährt die
  Leistungsprüfung: **keine Läufe, bis sie Bescheid gibt.** Für 0.5.1 ist von
  dieser Sitzung nichts mehr offen; danach: RM-252, Prozesswerte beim Öffnen
  des Slicers, Paket 3, Matrix, Gesamtlauf.
- Zweiter Einfügen-Nachtrag fertig und gemeldet (13:00): Endcommit
  `e85c77ed0` (N1 `eeafc867e`, N2 `8c343fc00`, N3–N6 `e85c77ed0`), Tor
  18 067/18 067 Exit 0, mypy ×3 grün, Gegenprobe N1/N2 am Stand `bc901772c`
  selbst nachgefahren (4 rot), neu grün. Bericht `nachtrag-2.md`. Wartet auf das
  Urteil der Release-Sitzung; danach Arbeitsbaum des Agenten entfernen.
- Vorher (11:00): Nachprüfung von `bc901772c`
  nicht mergebar (N1 Cache trägt keine Antwort, N2 Regression Platte der
  3MF). Agent fortgesetzt mit N1–N6, `CACHE_FORMAT_VERSION` → 33, Tests mit
  echtem Plattencache, Gegenproben am Stand `bc901772c`, Bericht
  `nachtrag-2.md`. Review: Abschnitt „Nachtrag bc901772c“ in
  `F:\3D Druck.review-051\reports\review-einfuegen.md`.

- **Nachtrag fertig und gemeldet:** Endcommit `211789878` (N1 `6a066c2bc`,
  N2+N5 `1afb1c377`, Kopien-Merker `04ca4e53d`, B5-Bettlage `d1c3d0462`,
  RM-257 `211789878`). Tor `tor-b5-2.txt` + Nachlauf grün, mypy ×3 grün.
  Die Release-Sitzung merged auf main und löscht danach die Zweige; dann
  `F:\3D Druck.gesamtfix` und den lokalen Zweig entfernen.
- Aufgeräumt: `stand-3018613e6`, `F:\3D Druck.gesamt`, `F:\3D Druck.probe`,
  Stash (Sicherung `output/review/aufraeumen-2026-09-28/`), drei
  `agent-*`-Worktrees.
- Offen nach 0.5.1: RM-252 (Solidons Netz bringt Elegoo zum Absturz), warum
  der Dialog beim Öffnen des Slicers andere Prozesswerte schreibt, N3/N4 (von
  der Release-Sitzung ins Register), Paket 3, Matrix, Gesamtlauf.

## Vorher (28.09.2026, 08:45)

- **Im Baum, ungestaged, fertig bis aufs Tor** (vier Code-Einheiten + Register):
  N1 (`writer` job/`_served_elsewhere` Hunks < Zeile 1800, Dialog,
  `test_print_settings`), N2 (`orientation` Hunks < 700, `findings`,
  `schichtanalyse.md`, `test_orientation_search`), Kopien-Merker
  (`orientation` ab 700, `prepare_ops`, `test_orient`), B5-Bettlage
  (`writer` Rest, `slicer_profiles` `CuraActiveMachine.bed`, Karte export,
  `dateiformat.md`, `test_export`, `test_slicer_profiles`), RM-257 geschlossen
  (ROADMAP + Archiv). Commit-Texte `commit-*.txt` hier, Vormerken mit
  `scratchpad/stage_hunks.py <baum> <datei> <von> <bis>`.
- **B5 im Cura-Fenster erledigt** (Bilder `output/review/b5-cura-2026-09-28/`):
  Werte je Objekt, Sperre als Stützblocker, Kanal frei (Gegenprobe ohne Sperre
  voll). Bettlage war auf Solidons Drucker gerechnet → behoben auf Curas
  aktive Maschine, im Fenster belegt (D-alt über den Rand, D-neu mittig).
  Curas Senden (Druckdaten, Absturzberichte) aus.
- **N2 nachgebessert (08:45):** Der Richtungsvergleich half an obj_30 nicht
  (Gewinner 0,0114° neben −Z, `stays` 2,2 s für ein Nein). Jetzt
  `orientation.same_pose` (Diagonale × Richtungsabstand < Schichthöhe),
  Test `test_a_winner_a_hair_beside_the_delivered_pose_costs_no_fine_slice`
  (am alten Stand rot). Bericht-Entwurf `scratchpad/bericht-n1-n2-b5.md`.
- **Danach:** Messung `minigolf_wechsel.sh` + `projekt_wechsel.sh` (alte
  Ergebnisse in `vor-richtung/`, `vor-kippe/`), Tor `tor.sh b5`, mypy Linux/macOS, Commits,
  Bericht an „Release 0.5.1" (auch die drei Agentenzweige: einfuegen
  `cf1015de2`, speicher `23bd961d4`, merkmale `b9252ee36`, Fragen daraus),
  dann `agent-*`-Worktrees und `stand-3018613e6` entfernen.

## Früher (28.09.2026, 06:00)

- **Committet und gepusht** (Tor `tor-b1b4.txt` grün, 17 961; Nachlauf
  `nachtor.txt` grün; mypy Linux/macOS grün, `mypy-gesamtfix.txt`):
  `2611950c2` Ausrichtung, `a1926aa93` B3, `4f2f96adf` B1, `176d961c9` B4+B2,
  `14d7a73b9` RM-252 berichtigt (Original stürzt nicht ab, Nachstellung in
  `output/review/rm252-meldung-2026-09-28/`). Offen im Baum: die vier
  Fenstertests (`test_ui.py`, `test_filament_workflow.py`); Lauf mit Frist
  `fenster-rm281.txt` über `lauf_frist.sh`, danach committen und alles an
  „Release 0.5.1" melden (mypy Linux/macOS ist dort jetzt Pflicht).
- **Einfügen an freier Stelle:** Robert hat §17.1/§25 für 0.5.1 freigegeben;
  Agent zieht *Modell erzeugen* im Zweig nach, dann Fenstertests des Zweigs
  mit Frist fahren, Bericht nach `output/review/einfuegen-2026-09-28/`
  kopieren, Worktree entfernen (Release-Sitzung will vor dem Tag aufgeräumt).

- **Vorher (erledigt):** Ausrichtung
  (stützenfrei stehend bleibt, `orientation.stays` vor der Vorauswahl,
  `advise.support_need`), B1 (`object_keys` nur Pfade des Rats + Partner),
  B3 (`"none"` in `UNANCHORED`), B4 (Befund je Teil mit `object_id`, Feld und
  Wert über `print_settings_dialog.setting_title`/`shown_value`, CLI bündelt),
  B2 (`writer._unserved`: was kein Teil verlangt, geht als Objektwert an jedes
  Teil, `export.part_setting_all`). Commits in vier Einheiten: Ausrichtung
  (advise ohne UNANCHORED-Hunk), B3 (UNANCHORED-Hunk, test_manufacturer,
  Param-Hunk test_print_settings), B1 (handover, B1-Hunks test_print_settings),
  B4+B2 (writer, panels, Dialog, CLI, Kataloge, test_export, test_value_labels,
  oberflaeche.md, dateiformat.md). Werkzeug: `stage_hunks.py` im Scratchpad.
  Danach Endcommit und Tor an „Release 0.5.1" melden.
- **Drei Agenten in eigenen Worktrees von main** (Robert: „Jetzt, für 0.5.1"
  für die zwei Leistungspakete): `speicher-ohne-prozesswerte`,
  `merkmale-an-kopien`; `einfuegen-freier-platz` braucht Roberts Ansage zu
  Bauplan §17.1, bevor die Release-Sitzung merged. Berichte unter
  `output/review/{speicherschluessel,merkmale-kopien,einfuegen}-2026-09-28/`.
- App für Robert nur **ohne Sandbox** starten (sonst keine 3D-Ansicht).

Stand: 27.09.2026, 19:30. Diese Datei hält die laufende Sitzung aktuell, damit
eine andere jederzeit weitermachen kann (Robert: Nutzungslimit). Wer übernimmt:
zuerst hier lesen, dann `git -C "F:\3D Druck.gesamtfix" status` und `log main..HEAD`.

## Auftrag

- Robert, 27.09.2026: „dann mach alles" — vor dem Tag v0.5.1 kommt RM-281 ganz:
  C (PrusaSlicer auf dem Herstellerbündel), E (je Teil), F (Stufe wählt den
  Herstellerprozess), L (Analyse mit den wirksamen Werten), dazu alle Befunde der
  Gesamtprüfung (Paket 3) und der Rest von K. Danach der Lauf „jedes Modell ×
  jeder Slicer × jeder Drucker" und der Bericht „komplett fertig" an Robert und
  die Release-Sitzung. Keine Stundenschätzungen. Volle Freigabe („du kannst
  alles machen und brauchst nicht mein ok"), Qualität vor Tempo.
- Konzept: `konzepte/konzept-herstellerprofil-als-grundlage-2026-09.md`
  (Entscheidungen A–L, Stufen-Tabelle in Abschnitt 4).
- Diese Sitzung ist die einzige, die am Code arbeitet. **Kerne 8–11 nie**
  (RM-272). Tor und Messungen auf 0–7 (`start /affinity FF`), Matrix auf 12–31.
  Andere Python-Prozesse (Tor der Setup- oder Release-Sitzung im Hauptbaum,
  `tools/docs_scan.py`) gehören nicht hierher — nicht beenden.

## Wo die Arbeit liegt

- Arbeitsbaum `F:\3D Druck.gesamtfix`, Zweig `uebergabe-gesamtpruefung`.
  Im Hauptbaum `F:\3D Druck` nichts ändern oder committen (dort liegen fremde
  Änderungen, u. a. Karten-Verdichtungen und Handbuch-PDFs).
- Commits deutsch mit echten Umlauten, Schluss
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. **Seit 19:10 mit
  Push** (neue CLAUDE.md: pushen nach jedem Punkt); der Zweig liegt auf origin.
- Stand der Meldungen an die Release-Sitzung („Alle Python Prozesse stoppen"):
  - Paket bis `c282e782d` ist auf main (Merge 42560b695).
  - **Gemeldet 19:30, noch nicht übernommen:** Endcommit `9fe7804f5` mit
    `5063fc9f5`, `575e5ef83`, `e0e3cf982` (L), `6fc852fb0`, `d4dd5332b` (F),
    `64a0e4677` (Hänger), `f94973b0a` (Regeln, Roadmap), `9fe7804f5` (Karten);
    Tor `tor-karten2.txt` grün (17 821). Changelog-Sätze und Katalogdetails
    stehen in der Nachricht; Entwurf `scratchpad/paket-meldung-entwurf.md`.
- Regeln und Karten sind frei (Setup-Sitzung hat verdichtet und freigegeben).
  Budget laut `tests/test_directory_docs.py`: Regel ≤ 30 KiB, Karte ≤ 25 KiB,
  Ladelast je Quelldatei ≤ 160 KiB, keine Datumsangaben in Überschriften.
  `schichtanalyse.md` steht bei 30 097 B, `app/ui/CLAUDE.md` bei 25 177 B.
- Stash im Arbeitsbaum: `stash@{0}` (alte lokale Prusa-Zeilen in
  `dateiformat.md`, auf main eingearbeitet) — nur Sicherung, nicht anwenden.

## Stufe L — erledigt, Commit `e0e3cf982`

Tor darüber grün (`tor-l.txt`: 17 802 bestanden, 0 Läufe mit Fehler, ruff,
format, mypy grün). Noch nicht gemeldet. Inhalt zur Erinnerung:

Entscheidung L: Die Schichtanalyse stützt ab der Schwelle, mit der der Slicer
stützt (gemessen > gewählter Prozess > printers.toml > 45°).

- `app/core/knowledge/profiles.py`: `for_process(profile, settings, *, effective=False)`;
  die Schwelle gilt aus wirksamen Einstellungen immer, aus einem gespeicherten
  Satz nur als eigene Wahl (Projekte aus 0.5.0 tragen 45° ohne Wahl).
- `app/ui/session.py`: `evaluation_profile`, `evaluation_follows`,
  `_current_effective_settings`; `evaluate_async` und `evaluate_now` holen die
  wirksamen Einstellungen des Fensters im Hauptthread; Auswertung, Revisions-
  arbeiter, Formen, Platzierung und `_Snapshot` rechnen mit `evaluation_profile`.
- `app/ui/main_window.py`: Karten, Schichtanalyse, Agentenanalyse mit
  `evaluation_profile`; `_print_profile`; `_foundation_found` wertet neu aus,
  wenn die Grundlage mit anderer Schwelle nach dem Lauf kommt.
- `app/ui/print_settings_dialog.py`: Ratgeber-Arbeiter und synchroner Rat mit
  `effective=True`.
- `app/core/export/writer.py`: `_support_blocker` schneidet mit der Schwelle der
  hinausgehenden Einstellungen (sonst Sperre nach Tabelle und verfehlte
  DRUCK-14-Wiederverwendung).
- Tests: `tests/test_manufacturer.py` (drei am Ende:
  `test_the_analysis_supports_where_the_chosen_process_supports`,
  `test_a_stored_threshold_is_the_analysis_limit_only_as_a_choice`,
  `test_the_session_evaluates_with_what_the_window_prints`),
  `tests/test_export.py::test_the_blocker_cuts_with_the_threshold_that_goes_out`.
  Betroffene Dateien grün (`l-tests*.txt`), Ruff und Format grün.
- Die lokale Änderung `.claude/rules/dateiformat.md` im Arbeitsbaum **nicht
  committen** (siehe Regeln).

## In Arbeit: Herstellerregel für PrusaSlicer (Fehler aus Stufe C)

Gefunden bei der Vorbereitung von Stufe F (`stufen-prozesse.json`): Für den
MK4S HF0.4 bot Solidon Prozesse von BIBO2, LulzBot, Trimaker und Zonestar an —
Profile ohne Bedingung galten als passend. PrusaSlicer 2.9.6
(`is_compatible_with_printer` in `src/libslic3r/Preset.cpp`) prüft zuerst den
Hersteller: Ein Systemprofil passt nur zum Drucker desselben Bündels (Vendor-ID
= Dateistamm des Bündels), außer das Bündel trägt `templates_profile = 1`; ein
eigenes Profil gehört dem Hersteller seines ersten Vorfahren mit Hersteller.
Plan: `SlicerProfile.vendor`, `_PrusaStore.vendor_of`, Prüfung in
`_prusa_fits`; `tests/test_slicer_profiles.py::test_prusa_filaments_fit_by_condition_and_the_models_suggestion_wins`
erwartet bisher „Generic PLA @SOVOL" am MK4S — das war falsch und wird
umgestellt. Die Vorwahlen der Matrix waren trotzdem richtig (Prusament bzw.
Sovol am SV06).

## Herstellerregel PrusaSlicer — erledigt, Commit `6fc852fb0`

Tor grün (`tor-hersteller.txt`, 17 803 bestanden). Am echten Bestand bleiben
für den MK4S HF0.4 acht Prozesse, alle von Prusa (`stufen-prozesse-prusa.json`).

## Bambu-Hänger — Korrektur im Arbeitsbaum, Tor läuft (`tor-haenger.txt`)

Bei der Abnahme von Stufe F hing Bambu Studio **auf den gesunden Kernen 0–7**
(P1S „Belastbar", 18:27): G-Code und `result.json` geschrieben, Prozess
stand, Solidon meldete nach 300 s „Zeitlimit überschritten". Also nicht
RM-272, sondern Bambu selbst (drei von rund hundert Läufen). Korrektur:
`process.run_limited(finished=, linger=)` beendet den Baum
`FINISHED_LINGER_SECONDS` (10 s) nach gemeldetem Ergebnis;
`handover._result_written(target)` fragt nach einer *neuen*, lesbaren
`result.json`; `slice_model` gibt die Frage der Orca-Familie mit (beide
Läufe, auch der ohne Anordnungsvorgabe). Tests: `test_process` (zwei),
`test_print_settings` (`_result_written`, Anschluss in `slice_model`).
Commit-Vorschlag: „Bambu Studio hält die fertige Druckdatei nicht mehr fest".
Changelog-Satz (Entwurf): „Mit Bambu Studio wartet Solidon nicht mehr bis zum
Zeitlimit, wenn der Slicer nach der fertigen Druckdatei nicht beendet wird."

## Stufe F — erledigt, Commit `d4dd5332b` (Tor `tor-f.txt` grün, 17 810)

Abnahme im Slicer: `output/review/gesamt-2026-09-27/stufe-f/abnahme.json`
(`stufen_abnahme.py`): zwölf Läufe mit Schichthöhe und Werten des
Herstellerprozesses, Rundreise an allen drei verlustfrei.

## Stufe F — Umsetzung (zur Erinnerung)

Stand im Arbeitsbaum: `slicer_profiles.layer_in_name/STAGE_WORDS/names_stage/
stage_process/standard_process`, `manufacturer.for_stage` (+ `_stage_process`,
`_prusa_stage_process`), `main_window` Grundlagen- und Export-Arbeiter,
Dialog (`_follows_stage`, `_standard_process`, `_machine_standard`,
`_stage_process_for`, `_show_stage_process`, `_show_own_process`,
`_process_picked`, `_OWN_PROCESS`, Speichern), zwei neue Katalogtexte, ein
Handbuchsatz (Druckseite). Tests: `test_slicer_profiles` (Zuordnung an vier
echten Listen, eigene Kopie), `test_manufacturer` (for_stage Orca und Prusa),
`test_print_settings_ui::test_the_quality_picks_the_manufacturers_process`
(einmal gezielt gefahren, grün, samt fünf berührten Dialogtests).
Am echten Bestand gemessen (`stufen_echt.py`): 20–66 ms je Frage.

Commit-Vorschlag: „Die Qualität wählt den Prozess des Herstellers".
Changelog-Satz (Entwurf): „Fein, Entwurf und Belastbar wählen jetzt den
passenden Prozess Ihres Slicers, etwa „0.12mm Fine“ am Centauri Carbon 2."

## Stufe F — Entwurf (Planung, zur Erinnerung)

Messung der Prozesslisten: `output/review/gesamt-2026-09-27/stufen-prozesse.json`
(`stufen_prozesse.py`). Creality Print nennt alle Prozesse „Standard" (nur die
Schichthöhe unterscheidet) → dort Rückfall (Überlagerung wie bisher).
Regeln: Fein = Name mit fine/detail/quality, feiner als der Standard, nächste
Schichthöhe zu Solidons Fein; Entwurf = draft, gröber als der Standard;
Belastbar = strength/structural, ±0,05 mm um den Standard; Systemprofile vor
eigenen. Kosten (`prozessliste_zeit.py`): find_profiles ElegooSlicer 1,8 s
(ungespeichert), Bambu 0,4 s, Prusa 1,2 s dann 0,02 s — im Dialog also nicht
über die ganze Suche, sondern über die Geschwister der Standarddatei (gleicher
Namenszusatz nach „@") bzw. den gespeicherten Prusa-Bestand.
`ui.slicer_base_process` bleibt „Standard der Maschine = folgt der Stufe" oder
eine eigene Wahl; die Stufe wird bei der Auflösung angewandt, nicht gespeichert.

Vorprüfung der Regeln an allen gemessenen Listen: `stufen_regel_probe.py`
über `output/review/gesamt-2026-09-27/stufen-prozesse-alle.json`. Ergebnis:
CC2 und P1S 0.12 Fine / 0.28 Extra Draft / 0.20 Strength, MK4S 0.10 FAST
DETAIL / 0.28 DRAFT / 0.20 STRUCTURAL, Kobra 2 nur Entwurf (0.30 Draft),
Creality Print meist nichts (Rückfall).

Umsetzungsplan:
- `slicer_profiles`: `layer_in_name`, `STAGE_WORDS`, `stage_process(fitting,
  standard, quality, stage_layer)` rein; Belastbar ±0,02 mm um den Standard.
- `manufacturer.for_stage(setup, profile, quality)` mit Dateizugriff:
  Orca über die Geschwister der Standarddatei (gleicher Zusatz nach „@",
  Verträglichkeit über `binding`), Prusa über den gespeicherten Bestand.
- Anwenden: `main_window` Grundlagen-Arbeiter (Zeile ~1033) und
  Export-Arbeiter `_assembly` (~1321); im Dialog zeigt das Prozessfeld den
  Stufenprozess, `_follows_stage` merkt „folgt der Stufe", ein Stufenwechsel
  stellt das Feld, eine Wahl im Feld stellt die Stufe oder „Eigener Prozess"
  (deaktivierter Eintrag im Stufenfeld); beim Speichern geht der Standard der
  Maschine in `slicer_base_process`, wenn das Feld der Stufe folgt.

## Koordination

- Setup-Sitzung („Claude Code Setup Überprüfung") verdichtet `.claude/rules/`.
  Bis zu ihrer Meldung dort nichts ändern; Regeltexte an sie schicken, sie
  arbeitet sie ein. Beim Merge von main gilt main's Fassung von
  `dateiformat.md` und `schichtanalyse.md`.
- Paketmeldung an die Release-Sitzung: vorher `git merge main` in den Zweig
  (Merge, kein Rebase) und Tor. Meldung: Endcommit, Changelog-Sätze
  (Kundensprache, „Sie", keine Gedankenstriche, höchstens 200 Zeichen, altes
  Verhalten gegen v0.5.0 geprüft), Katalogdetails. Sie übernimmt über einen
  privaten Index nur die eigenen Hunks. Der Tag bleibt bis „komplett fertig"
  gehalten.

## Matrix (Gesamtprüfung)

**29.09.2026, Release-Sitzung:** Der Lauf `alle_plaene.sh` (seit 28.09. 00:05, Plan
„modelle“ auf PAUSE bei 90/124) ist beendet. Sein Schnappschuss `F:\3D Druck.gesamt` war
am 28.09. vormittags schon entfernt, weitergelaufen wäre er nicht. Zum Fortsetzen einen
neuen Schnappschuss auf dem aktuellen Stand anlegen und alle Pläne neu starten.

**05.10.2026, nach 0.5.2:** `output/review/` ist auf Roberts Freigabe gelöscht, mit allen
Ausgaben der Gesamtprüfung darunter (`gesamt-2026-09-27/`). Die Pfade unten nennen, wohin
die Werkzeuge schreiben; frühere Ergebnisse liegen dort nicht mehr.

- Werkzeuge: `tools/matrix_driver.py`, `tools/matrix_unit.py`,
  `tools/matrix_report.py`, hier `alle_plaene.sh`/`.ps1`. Ausgaben:
  `output/review/gesamt-2026-09-27/` (`drucker/`, `modelle/`, `prusa-c3/`,
  `drucker-alt-9b58af5/`).
- Schnappschuss `F:\3D Druck.gesamt` steht auf `b4579e943` (vor Stufe C!).
  Plan „drucker" läuft seit 16:05 (pwsh 39568 → treiber 68736/9028, drei
  Arbeiter). Plan „modelle" ist über `modelle/PAUSE` angehalten.
- Nach Ende von „drucker": Schnappschuss auf den neuesten Zweigstand bringen,
  `modelle/PAUSE` löschen, die Prusa-Kombinationen mit neuem Code wiederholen.
- **Kernbindung war bis 27.09. 17:45 wirkungslos**: `einheit.py` rief
  `SetProcessAffinityMask` über ctypes ohne `argtypes`, das Pseudohandle kam
  als 32-Bit-Zahl an (ERROR_INVALID_HANDLE). Alles lief auch auf 8–11.
  Behoben (eigene Signaturen, Fehler wirft); die laufenden Prozesse wurden von
  außen gebunden. Ergebnisse vor 17:45 stehen unter RM-272-Vorbehalt.
- **Befund Bambu-Hänger:** Bambu Studio schrieb G-Code und `result.json` und
  endete nicht (ein Thread, 2 s CPU): Wedge-Lock A1 „stuetzen_auto" (16:18,
  45 min bis Zeitlimit) und A1 mini „standard" (17:03). Nachmessung auf
  gesunden Kernen mit demselben Aufruf über `run_limited`
  (`output/review/gesamt-2026-09-27/bambu-haenger/`): 8/8 einzeln und 45/45
  in drei parallelen Schleifen ohne Hänger, je Lauf rund eine Sekunde. Stand:
  Verdacht auf die Maschine (RM-272), kein Code geändert. Tritt er mit
  wirksamer Bindung wieder auf, ist es Bambu selbst — dann in der Übergabe
  fertige Ausgabe annehmen, statt 300 s bis zur Absage zu warten.
- Offene Matrixbefunde (Paket 3, noch einzuordnen): ElegooSlicer-Konsole mit
  Prozentwerten/Enums fremder Hersteller (in `einheit.py` als
  Konsoleneigenheit führen); Kobra 2 Bahnbreite 0,344 plattenweit; K1
  Arachne-Vorschlag; Waschschüssel 85–93 % Stütze in Schicht 1 mit Stützen an
  („Stützbedarf gegen das Urteil des Herstellers"); XL-Druckzeit ×1,7;
  generische Absagen bei zu kleinen Druckern; SV06-Schwellenvorschlag (mit L
  erledigt).

## Offene Arbeit, in dieser Reihenfolge

**STAND 03:40 (28.09.) — Robert: „mach den Punkt noch fertig das nächste machen wir
nach 0.5.1“.** Für 0.5.1 endet die Arbeit mit diesem Punkt. Erledigt aus Paket 3:
Mindestschichtzeit (auch an Keilspitzen): Vorschlag nur noch ohne Mindestzeit,
Tests und Regel `schichtanalyse` (Tor `tor-schichtzeit.txt`, dann Commit);
Bahnbreite plattenweit (Kobra 2): mit Stufe E schon je Teil, nachgemessen
(`bahnbreite-sonde.json`: 0,344 nur für Gövde59, Platte 0,42, `bahnbreite_sonde.py`);
schmale Stege geeicht (`43d333525`). Matrix: `modelle/PAUSE` gesetzt (03:36, 90/124),
damit die Release-Sitzung Kerne für Leistungsprüfungen hat; `einheit.py` gibt jetzt
`flavour` an `advise` (Brim über Orca-Auto). **Nach 0.5.1, in dieser Reihenfolge:**
PAUSE löschen und Modellplan zu Ende; Stützbedarf gegen das Urteil des Herstellers
(`stuetzen_auto`-Läufe der Matrix gegen Solidons Urteil, Verdacht Brückenregel 15 mm
und Inseln an Schrauben); RM-282; RM-164; RM-228 Code-Teil (Kammerlüfter, unbemalte
Spulen, Curas Schichtzeitschwelle entscheiden); RM-191 mit Messung schließen; RM-252
(Besteckeinsatz mit neuem Code nachmessen, Stützregel entscheiden, Meldungstext an
Elegoo/Orca für Robert); Konsoleneigenheiten aus `bericht-drucker.md`; Gesamtlauf
beider Pläne mit Endstand; „komplett fertig“.

**STAND 03:10 (28.09.):** Alles bis 00:30 committet und gepusht, dazu `83a8e3de1`
(kein Brim-Vorschlag über Orcas Auto-Brim), `a97ee3d2e` (Kalibrierhinweis nur mit
Passungen), `f1a1fba65` (K-Rest Cura: `;TARGET_MACHINE.NAME` + Startcode vor
`;LAYER:0`, an echten SV06-Dateien still), `f333bd008` (PHP ohne OPcache),
`984760af4` (Roadmap: RM-250 archiviert, E und K stehen), Merge von main
`dd95985e5` (Tor `tor-merge4.txt` 17 955 grün). **Paket an „Release 0.5.1“ gemeldet**
(neuer Name der Release-Sitzung, Adresse `local_60fcecf3-…`), mit Changelog-Sätzen,
Katalogen und Umfang: RM-281+Paket 3+Gesamtlauf, RM-282, RM-228 Code-Teil samt
seinen zwei Entscheidungen, RM-191 (mit Messung schließen), RM-252 Stützfrage
(Meldung an Elegoo/Orca bleibt bei Robert, Text bereitlegen), RM-257 schließt mit
ihrer Sichtprüfung, keine Formatänderung (sie nehmen 37). Matrix: Plan „drucker“
00:05 beendet (Minigolf 89/108 am Zeitlimit, alter Code), Bericht
`bericht-drucker.md`; Schnappschuss `F:\3D Druck.gesamt` auf `f333bd008`, Plan
„modelle“ läuft seit 01:08 (03:06: 83/124). **Paket 3 im Einzelnen** (Herkunft:
Morgensitzung 69f96fd4, „selbst bei 60° bekommt ein Drittel aller Körper Stützen“):
Mindestschichtzeit (Vorschlag 15 s, 97-mal) und Keilspitzen; Stützbedarf gegen das
Urteil des Herstellers (Waschschüssel 85–93 % Stütze in Schicht 1); Brückenregel
(15 mm) und Inseln an Schrauben; Bahnbreite plattenweit (Kobra 2, 0,344); RM-164;
RM-282; Konsoleneigenheiten (ElegooSlicer mit fremden Prozentwerten, XL ×1,7,
Absagen zu kleiner Drucker, Arachne am K1). Dann RM-228, RM-191, RM-252, Gesamtlauf.

**STAND 00:30 (28.09., Robert schläft):** Gepusht auf `uebergabe-gesamtpruefung`:
`36ca07053` Prusa-Stütze je Teil, `4ce7908ce` Namen der Stützsperre, `43d333525` Stege
nach Fläche, `b50d94d1d` Messung auf dem Raster ihrer Probe, `75bdc1914` Erststart,
`67f42c99a` Druckdialog Slicer/Drucker (+14 Fenstertests), `f1c9c4330`
Abweichungstests (`test_analysis_ui`, Auftrag der Release-Sitzung). Tor `tor-raster.txt`
17 853 grün bis auf zwei: `test_value_labels` (Parametername `values` → `written`,
behoben) und ein Lastwackler in `test_maps` (einzeln grün). E6 fertig: Elegoo und Prusa
stützen nur den Pilz (`stufe-e-prusa.out`). **Neuer Fund aus E6:** Der übernommene
Brim-Vorschlag ersetzt Orcas Auto-Brim durch 5 mm und gibt weniger Halt (Schäfte 0,9
statt 1,9 m Randbahn; Waschschüssel 0,40 statt 0,93 m laut RM-250). Fix im Baum
(uncommittet): `advise.AUTO_BRIM_FLAVOURS`, `_unanchored(settings, flavour)`, `flavour`
durch `advise`, `for_part`, `writer.part_advice`, `_part_values`, `_AdviceWorker`;
`handover._adhesion_for` fragt dieselbe Menge; Tests in `test_print_settings`
(`test_the_orca_auto_brim_already_holds_a_part`). Betroffene Tests laufen
(`brim-betroffen.txt`, `betroffen.sh`). Danach: Commit, Roadmap (RM-250 ins Archiv,
Brim-Fund), `settings.uncalibrated_material` nur mit Passungen (Release-Punkt 2a),
K-Rest Cura (Name `;TARGET_MACHINE.NAME` + Startcode vor `;LAYER:0`, Prusa ist mit C
erledigt), PHP-OPcache, Antwort an die Release-Sitzung (Entwurf
`scratchpad/antwort-release.md`; dazu: `test_value_labels::test_the_offer_button_click_
reaches_the_handler` ist auch am alten Stand rot — ihr Gebiet), dann Matrix.

**STAND 23:45 (Robert schläft):** Alles aus 22:55 ist im Arbeitsbaum gelöst, Tor
`tor-raster.txt` läuft, danach Commits in Einheiten (Aufteilung mit
`scratchpad/stage_hunks.py`, Hunks nach Stichwort): (1) Prusa-Stütze je Teil
(`_with_automatic_prusa_support`, `test_export`); (2) Namen der Stützsperre
(`slicer_keys.GEOMETRY_KEYS`, threemf, writer); (3) Stege nach Fläche
(`advise.NARROW_WEB_AREA` = 100 mm², Eichung `stege_korpus.py`, Regel
schichtanalyse); (4) **Messung gilt auf dem Raster ihrer Probe** — neuer Fund:
Nach anderer Bahnbreite oder Stufe „Fein“ blieb der gemessene Überhangwinkel in der
Grundlage (seit Entscheidung L und `0372e5184`), Fenstertest `..._reanalyses_when_
line_width_...` war deshalb rot. Lösung: `Foundation.unmeasured`/`.profile`,
`manufacturer.measured_on`, `effective` und `written_paths` danach, `resolve` prüft
die Probe auf dem Stufenraster, der Druckdialog leitet `settings` als Property
durch `measured_on`; Tests `test_manufacturer` (2 neu); (5) Erststart (gemerkter
Slicer sofort, *Fertig* wartet; Testleck `remember_path("slicer", "")` in der
Vorrichtung); (6) Druckdialog: Slicerwahl außerhalb des Abschnitts, Druckerwahl
merkt `ui_settings.printer`, Wächter für die gemerkte Maschine, „{printer}
übernehmen“ (Knopf verschwindet jetzt auch, wenn danach ein Profil passt),
Prusa-Hinweis, Fenstertest-Reparaturen (14 → 0 rot, 249 grün), 3 neue Tests.
E6: Prusa neu (Pilz gestützt, sonst nichts), Elegoo-Wiederholung läuft
(`stufe-e-prusa.out`). ROADMAP (RM-281 E steht, Abendbefunde, Stege) im Baum;
RM-250 nach der Elegoo-Wiederholung ins Archiv. Danach: PHP-OPcache in den Zweig,
Antwort an die Release-Sitzung, dann K-Rest.

**STAND 22:12 (Folgesitzung):** E4 erledigt und gepusht, `074364017` (Tor
`tor-e4.txt` grün, 17 850): Zeile „Haftung · Turm“ im Druckdialog
(`_AdviceWorker._with_parts`, `_TargetedAdvice.parts`), dazu Fehler aus E2
behoben: Der Export fragte den Rat je Teil nur mit dem Material von Slot 0
(`handover.slot_processes`, `writer.part_advice`, Gegenprobe am Stand davor
rot). PHP-Portversuch: vorwärts auf den eingecheckten Stand zurückgebaut
(Patch hier daneben unverändert gesichert), Ursache des Wacklers noch offen
(Punkt 1b unten). Probe-Worktree `F:\3D Druck.probe` (006ff5118) für
Gegenproben. Gezielte Läufe: `lauf.sh <name>` mit `laeufe/<name>.args`.
**Nächster Schritt: E5** (Entwurf in Abschnitt „E5 — Entwurf“ unten), dann E6.

**STAND 22:55 (Robert schläft, „alles sauber abarbeiten“):** E5 gepusht
(`6daf7ee39`, Tor 17 852). Uncommittet im Arbeitsbaum (Tor noch nicht): Fenstertest-
Reparaturen (`test_print_settings.py` Prusa-Hinweis + `wait_for_profiles`,
`test_print_settings_ui.py` Befunde 1–8 von 14), Haftungssatz gekürzt (Kataloge),
`slicer_keys.GEOMETRY_KEYS`/`*_SUPPORT_BLOCKER`. Offen von den 14 Fenstertests:
`test_print_advice_keeps_its_layers_when_only_the_advice_changes`,
`..._cannot_disable_support_needed_by_another_body`, `test_empty_print_dialog_...[before_open]`,
`..._uses_manufacturer_flow_...`, `test_secondary_filament_advice_..._prusa`,
`..._reanalyses_when_line_width_...` (Liste in `fenster-psui.txt`).
**PHP-Wackler gelöst (noch nicht im Zweig):** OPcache ist im eingebauten Server an
und unter Windows prozessübergreifend geteilt; Prüfserver mit anderen Erweiterungen
führen fremden Opcode aus (`mb_substr` lief als `sodium_crypto_auth_keygen`, Absturz =
ConnectionReset). Mit `-d opcache.enable=0` in `php_probe._php_command` und im
Server von `test_shared_hosting_removed` 6/6 grün unter Last, ohne 6/6 rot
(`php-sonde/`, `php-sonde-mit-opcache/`, Patch in `F:\3D Druck.probe`).
**Roberts Funde 22:30–22:50 (Vorrang):** (1) „Erste Schritte“ belegt `generic-220`
vor und schlägt den Drucker des Slicers (CC2) erst nach ~6 s vor (Druckersuche
startet erst nach der Werkzeugsuche); Robert schloss nach 4 s → `settings.printer =
generic-220` (Protokoll `%LOCALAPPDATA%\RS Digital\Solidon3D\logs\app.log` 22:19,
Sonde `scratchpad/erststart_sonde.py`). Behebung: Druckersuche für den gemerkten
Slicer sofort starten, „Fertig“ wartet auf eine laufende Druckersuche.
(2) Slicer im Druckdialog nicht einstellbar — Slicerwahl sitzt im zugeklappten
„Profile des Slicers“ und nur bei >1 Slicer; Sonde läuft. (3) Erste Schicht nicht
wie in `output/druckbereit/minigolf-2026-09-27/…-schraegnaht.*` (50 mm/s); zu prüfen:
Grundlage des falschen Druckers, Vorschlag „schmale Stege“ an seinen Teilen
(`F:\3D Dateien\Mini+Golf+All+Set-P1S_stls`: Gövde59, Gövde78, Golf Başlığı V3).
**Release-Sitzung wartet auf** (Nachricht 22:40): Antwort zu RM-282/228/252/191 im
Umfang, Beleg für Changelog-Satz „500 statt 150 mm/s … weniger ausläuft“,
`test_analysis_ui` Abweichungsbericht (zwei Arbeiter: `_FoundationWorker` +
`_MapWorker`), Durchsichtfunde `settings.uncalibrated_material` nur mit Passungen,
`_AdviceWorker` vor fertiger Erkennung.

**STAND 22:27:** E5 gebaut (Tor `tor-e5.txt` läuft): `threemf.write_assembly(cura=True)`,
`writer._cura_window`/`_cura_blockers`, `handover.for_the_cura_window`,
`_PlateJob.for_window` (vom `_OpenInSlicerWorker`), alter Cura-Sonderbefund samt
Katalog raus. Curas Leser am Quelltext belegt (libSavitar `Scene.cpp`/`SceneNode.cpp`,
`ThreeMFReader.py`, Uraniums `MeshFileHandler.readerRead` zentriert wieder — kein
doppelter Versatz). Bildschirm-Abnahme im Cura-Fenster nicht möglich (kein
Desktop-Werkzeug in der Sitzung) → Robert bitten. E6 läuft: `je_teil_abnahme.py`
→ `output/review/gesamt-2026-09-27/stufe-e/`. **Neue Funde, nach E5 beheben:**
(a) Fenstertest `test_print_settings.py::test_a_slicer_that_arrived_is_picked_up_without_reopening`
rot auch am alten Stand: wartet nicht auf die Profilsuche, die PrusaSlicer seit
Stufe C hat (Sonde `F:\3D Druck.probe\tests\test_zz_sonde_slicer.py`); (b) der
Hinweis „ohne sie lehnt dieser Slicer den Auftrag ab“ steht auch bei PrusaSlicer,
das seit C ohne Profile mit Solidons Werten druckt — Texte liegen bereit
(`prusa-profile-texte.json`, `katalog_eintragen.py` hier daneben).

Erledigt heute: Herstellerregel, Stufe F, Stufe L, Bambu-Hänger, Regeln,
Karten, Roadmap (RM-281 fortgeschrieben, RM-255 archiviert), Paket gemeldet.

1. Stufe E (Objektwerte Orca/Prusa, Cura je Netz samt Sperre für Curas
   Fenster, Dialogzeile je Teil; RM-250, RM-257). Abnahme: Minigolf-Satz mit
   einem gestützten Körper, Stütze nur an ihm, Brim der übrigen geschlossen.
   **Plan (ohne Formatänderung):** Übernahme bleibt ein Pfad der Platte
   (`settings.accepted`); beim Schreiben entscheidet der Grund:
   - E1 Kern `advise`: `PART_PATHS` (support.style/placement/block_channels,
     adhesion.kind, shell.precise_outer_wall/outer_wall_first/ironing,
     speed.outer_wall(_acceleration), shell.wall_count, infill.density,
     shell.wall_generator, layers.line_width); `for_part(settings, profile,
     result, bounds, footprint, fit_kinds, connectors)` = Brim-Regeln plus
     Geometrierat nur dieser Pfade; `plate_paths(base, profile)` = was
     plattenweite Regeln (Maschine, Material, Volumenstrom) verlangen —
     `_from_material` setzt auch speed.outer_wall und adhesion.kind, dann bleibt
     der Pfad plattenweit. Passungsarten je Körper und Zapfendurchmesser aus
     dem Dialog (`_fits_in_play`, `_connector_diameters`, `FITTING_OPS`) in den
     Kern ziehen.
   - E2 Export: je Teil = übernommene PART_PATHS minus plate_paths; die Platte
     bekommt dort den Wert der Grundlage (`without_choice`), gleich in
     `write_config`, 3MF-Projektkonfiguration und `_part_settings`
     (Objektwerte über `object_keys` → `AssemblyPart.settings`). Analyse je
     Körper über `remembered_analysis`, sonst `slice_body` — nur wenn ein
     Geometriepfad übernommen ist.
   - E3 Cura je Netz (`CuraMesh.settings`), Haftung dort plattenweit.
   - E4 Dialog: die Zeile nennt die Teile („Brim · Loch 3, Loch 7"), aus dem
     Rat je Körper des `_AdviceWorker`.
   - E5 RM-257: Curas Fenster bekommt eine 3MF mit der Sperre als Objekt.
   - E6 Abnahme im ElegooSlicer, PrusaSlicer, CuraEngine.
   **E1 bis E3 erledigt, Commit `2cf02ad2d`** (Tor `tor-e2.txt` grün, 17 832):
   `handover.split_for_parts` + `PartSplit` + `CURA_PER_MESH` +
   `cura_takes_whole`; `writer._part_values` (Objektwerte Orca/Prusa, Cura je
   Netz mit Rücknahme), Haftungsprüfung und Sperre je Teil wirksam,
   `slice_model` nimmt dieselbe Platte; `for_part` mit Profil, eigene
   Brim-Regeln zuletzt. Regeln (dateiformat, schichtanalyse), Karten, ROADMAP
   nachgezogen. **Offen: E4, E5, E6** (Reihenfolge nach der Schrägnaht, 1a).
   Weitere heute: Stufennamen übersetzt (`8bc90a204`), PHP-Port je
   xdist-Arbeiter (`5b3b80583`), beide auf main (19fc95e35).
**STAND 21:45 (Sitzungsende am Limit, Robert):** Schrägnaht erledigt und
   gepusht: `bfe67bc7b` (Einstellung, Schlüssel aller Familien, Rücklesen,
   Regel, Dialog, sechs Sprachen, Abnahme `output/review/gesamt-2026-09-27/naht/`
   mit `naht_abnahme.py`) und `006ff5118` (Knick über Arme der Düsenbreite, wie
   der Slicer; Minigolf-Rumpf bekommt sie nicht). Robert hat die
   Vergleichsdatei noch nicht gemeldet bekommen:
   `output/druckbereit/minigolf-2026-09-27/minigolf-cc2-erste-schicht-50-schraegnaht.gcode`
   (9:49 statt 9:18 h, Schäfte je 2995 Rampen). **Nächster Schritt: E4, E5, E6.**
   **Offen und uncommittet im Arbeitsbaum: PHP-Portversuch** (`tests/php_probe.py`,
   `test_activation_server.py`, `test_public_php_security.py`,
   `test_shared_hosting_removed.py`; gesichert als `php-port-versuch.patch` hier
   daneben). Befund: `test_corrupt_rate_limit_states_fail_closed` und drei weitere
   Support-Tests scheitern unter Last mit `ConnectionResetError` bzw. 200 statt
   503 — **auch der eingecheckte Stand** (Probe-Worktree auf `bfe67bc7b`,
   `pytest -n 4` der drei PHP-Dateien: 1 von 4 Läufen mit 6 Fehlern). Versucht:
   Laufbereiche und Lauschprobe in `free_port`, `serve()` mit Port 0 (PHP 8.5.8
   nennt den vergebenen Port in der Startzeile) über Leitung (3/3 Läufe rot) und
   über Datei (1/3 rot). Ports sind es also nicht; Verdacht: Support-Endpunkt
   unter Last (Windows-`mail()` gegen 127.0.0.1:1, eingebauter Server). Nächste
   Sitzung: Serverausgabe je Test mitschreiben, Ursache finden; den Versuch
   fertig belegen oder vorwärts auf den eingecheckten Stand zurückbauen — nicht
   halb committen.
1a. **Schrägnaht an runden Außenwänden, für alle Slicer** (Robert 27.09.,
   „bei allen Slicern ausbessern, nicht nur am ElegooSlicer"). Anlass: Roberts
   Minigolf-Druck `output/druckbereit/minigolf-2026-09-27/…-erste-schicht-50`;
   Diagnose steht in ROADMAP (RM-281, Punkt „Schrägnaht"). Gemessen: Elegoos
   Basisprozess hat `seam_slope_type none`, `seam_slope_min_length 0`,
   `seam_slope_inner_walls 1`; mit Typ allein greift nichts, mit 20 mm Rampe
   997/1000 Schleifen, 9:18 → 10:39 h (Innenwände mit). **Als Objektwert
   nimmt ElegooSlicer es an** (`scratchpad/naht_objekt.py`: nur Objekt 5
   rampt, 2995 Außenwandschleifen, Innenwände 0, 9:17:44 → 9:25:33 je
   Schaft). Schlüssel: Orca-Familie `seam_slope_type external`,
   `seam_slope_min_length 20`, `seam_slope_conditional 1`,
   `seam_slope_inner_walls 0` (Elegoo, Orca, Bambu, Creality 7.2 führen sie;
   Bambu hat zusätzlich `override_filament_scarf_seam_setting`, prüfen);
   PrusaSlicer 2.9 `scarf_seam_placement contours|nowhere`,
   `scarf_seam_length 20`, `scarf_seam_only_on_smooth 1`,
   `scarf_seam_on_inner_perimeters 0` (je Objekt prüfen); Cura 5.13
   `scarf_joint_seam_length` (0 = aus, je Netz → CURA_PER_MESH). Plan:
   `ShellSettings.scarf_seam: bool`, Tabellenzeilen, Rücklesen in
   `manufacturer` (an nur mit Art und Länge > 0), Regel in
   `advise._from_geometry` (glatte Außenschleife: kein Knick > 25°, Länge ≥
   Rampe, genug Höhe), `PART_PATHS` und `writer._SLICED_PART_PATHS`,
   Dialogfeld nach `shell.seam_position`, Texte sechs Sprachen (Begriffe aus
   den Slicer-Katalogen: Schrägnaht, Scarf seam, Couture en biseau, Costura en
   bisel, Cucitura a sciarpa, Costura em bisel), Tests, Abnahme je Slicer.
2. K-Rest (Identität und Startcode bei PrusaSlicer und Cura in der Gegenprobe).
3. Matrix: nach Ende des Plans „drucker" Schnappschuss `F:\3D Druck.gesamt` auf
   den Zweigstand, `modelle/PAUSE` löschen, Prusa-Kombinationen neu, dann
   Plan „modelle".
4. Paket 3: Mindestschichtzeit, Keilspitzen, Stützbedarf gegen das Urteil des
   Herstellers, Brückenregel, Inseln an Schrauben, Bahnbreitenvorschlag
   plattenweit, Schwelle „schmaler Steg" am Korpus eichen, RM-164 (Creality
   „Slicen" → Fenster), RM-282.
5. Matrix auswerten (`bericht.py`), Konsoleneigenheiten einordnen.
6. Gesamtlauf über alle Slicer × Drucker × Modelle, dann Bericht „komplett
   fertig" an Robert und die Release-Sitzung.

## E5 — Entwurf (Curas Fenster bekommt Sperre und Werte je Teil)

Aus Curas Quelltext belegt: libSavitar `SceneNode::fillByXMLNode` liest
`<object><metadatagroup><metadata name="cura:<key>">` und streift das Präfix
`cura:` ab; `ThreeMFReader._convertSavitarNodeToUMNode` setzt bekannte Schlüssel
als Einstellung des Knotens (Wahrheitswerte als `True`/`False`). Eine 3MF behält
ihre Lage (kein Anordnen beim Laden, `CuraApplication._readMeshFinished`), Ursprung
Bettecke (`-machine_width/2`). Ein freistehender Knoten fällt aufs Bett
(`drop_to_buildplate`), ein Kind einer Gruppe nicht → Teil mit Sperre als Objekt
mit zwei Komponenten (wie die Orca-Schreibweise), Sperre mit
`cura:anti_overhang_mesh=True`.
Plan: `write_assembly(..., for_window=True)` für Cura schreibt statt STL eine 3MF
(Lage = Szene + halbes Bett von Solidons Drucker, wie die Konsole), Werte je Teil =
`part_values[...].keys` im Fensterformat; keine Orca-/Prusa-Beilagen.
`_PlateJob.for_window`, gesetzt vom `_OpenInSlicerWorker`, durch `_prepare_plate`.
Der Sonderbefund „im Cura-Fenster setzen Sie selbst einen Stützblocker“ entfällt
(Katalogeinträge in fünf Sprachen entfernen), Test
`test_cura_gets_every_part_and_the_blocker_as_meshes_of_their_own` anpassen.
Abnahme im Cura-Fenster (Sperre grau, Werte je Objekt) per Bildschirm.

## Werkzeug-Fallen dieser Arbeit

- Tor: `bash .claude/scripts/suite-getrennt.sh` plus ruff, format, mypy;
  gebunden über ein Wrapper-Skript
  (`cmd //c "start /b /wait /affinity FF bash <skript>"` — ein gequoteter
  exe-Pfad direkt nach `start` scheitert). Ergebnis nur aus der Ausgabedatei
  (`TOR-EXIT`, `Läufe mit Fehler`), nie aus `$?` nach einer Kette.
- Fenster-, Leistungs- und `rendered`-Tests nur beim Release.
- Python-Skripte mit dem Write-Werkzeug anlegen (Heredocs fressen `\\`);
  `write_text(..., newline="\n")`, sonst CRLF.
- Pyright im Editor liest den Hauptbaum, nicht den Arbeitsbaum — seine
  Meldungen zu `with_choice`, `effective=` usw. sind veraltet; maßgeblich ist mypy.

## Entwurf für RM-281, Stufe C (für ROADMAP.md)

```
  - **C steht** (Zweig `uebergabe-gesamtpruefung`): PrusaSlicer bekommt Drucker, Prozess
    und Filament seines Bündels, aufgelöst in `solidon.ini` und die Beilage der 3MF
    (`handover.prusa_values`), darüber nur die Abweichung; die Grundlage liest sie zurück
    (`manufacturer.prusa_chain`, `PRUSA_PROCESS`, eingebaute Vorgaben gemessen). Der
    Druckdialog bietet dieselbe Profilwahl wie für die Orca-Familie, verlangt sie aber
    nicht; ohne Drucker im Bündel bleibt Solidons Satz samt `filament_type`, und
    `slicer.printer_unknown` sagt es. Gemessen am Minigolf-Auftrag in PrusaSlicer 2.9.6:
    MK4S HF0.4 und XL IS ohne Vorschläge in allen 259 und 260 Schlüsseln gleich der Kette,
    `G29`-Vermessung und Spüllinie im G-Code; der MINI lehnt ab, weil ein Teil 200 mm hoch
    ist (Bauraum 180). Schließt RM-255 für PrusaSlicer. Mit C erledigt: H12 (übernommene
    Filamentwerte gehen mit ihrem Filament) und H15 (eine Spule schreibt nur, was sie
    ändert).
```
