# Übergabe 09.10.2026 — RM-620, RM-583, RM-621, danach RM-622 und RM-584–589

Auftrag (Robert, gilt weiter): Solidon liefert für jedes Modell sinnvolle Stützen
und richtige Slicer-Einstellungen, **immer nach dem Material der Spule, kein
Projektmaterial**; RM-583 bis RM-589 mit Werten aus
`konzepte/recherche-slicer-einstellungen-2026-10.md` abarbeiten, in allen
Familien gemessen; mehr liefern, wo es geht; Leistungsfunde beheben. Keine
Vorschläge machen, gleich abarbeiten. Jeder Zweig trägt seinen Changelog-Punkt
selbst unter `## 0.6.0` in allen sechs `changelog/*.md` (allgemein, keine
Prüfmodelle wie Kinn oder Drache). Nummern: RM-580–589, RM-620–629 sind meine.

Alles in diesem Ordner: Patches der ungesicherten Arbeit (Rückfall, falls ein
Worktree fehlt), Commit-Meldungen, Archiventwurf, Reviews, Agentenbericht,
CI-Starter, Drachen-Skript, berichtigte Kontaktsonde.

## 1. RM-620 — landen (Worktree `F:/sl-mischtemp`, Zweig `slicer/mischtemperatur`)

Commit `40ad9a5c4`, gepusht. Review zwei Runden, alles behoben; Tor grün
(24 875 bestanden, 116 übersprungen); ruff, format, mypy grün.
CI-Auswahl: Slicer 37877662930 **grün**, Fenster 37877660387 lief noch
(`gh run view 37877660387 --repo RS-Digital-Studio/Solidon`).

- Bei Grün: main hineinmergen, falls weiter (`git -C F:/sl-mischtemp fetch` +
  `merge origin/main`), dann von main aus `git merge --no-ff slicer/mischtemperatur`
  (Meldung per Datei), pushen, Worktree `F:/sl-mischtemp` und Zweig abbauen.
- Ein roter Job: Log lesen, beheben, nicht übergehen.

## 2. RM-583 — fertigstellen (Worktree `F:/sl-stuetzen`, Zweig `einstellungen/stuetzabstand`)

HEAD `936def3fc`, darüber **39 Dateien ungesichert** (`rm583-ungesichert.patch`).
Alle Funde der Nachprüfung (`review_rm583_2.md`: H1, M1, M2, N1, L1–L6) sind
umgesetzt, jede Behebung mit Test und Gegenprobe. **Keine weitere Review-Runde**
(Entscheidung Robert: Nachprüfung nur einmal).

Was gebaut ist (Kurzform, Einzelheiten in `archiv-rm583.md`):
- `handover.asked_for_contact`: Dialog fragt den Kontakt gegen die Grundlage wie
  der Export; `advise.combine(..., separate=)` nimmt bei je Teil geschriebenen
  Pfaden nur die verlangenden Körper; `_with_parts` nennt nur Teile mit dem
  Zeilenwert. Tests `test_the_contact_rows_settle_after_one_round` (Kern) und
  `test_the_contact_rows_settle_in_the_dialog` (UI).
- `profiles._load_materials`: Nutzereintrag ergänzt fehlende Schlüssel aus dem
  mitgelieferten (`test_an_older_calibration_keeps_the_shipped_support_values`).
- Cura: Satz zum Abstand nur mit Stützen, nennt „Abstand oben und unten“, Handlung
  `OPEN_PRINT_SETTINGS` mit `field`; Grundlage `z_gap` als ganzes Vielfaches
  (`manufacturer.base_settings`), Lücke ohne Wahl `manufacturer.cura_interface_gap`.
- `handover.tower_cause(setup, filaments=, objects=)` statt `prints_a_tower`;
  Writer meldet mit Turm nur `export.support_gap_rounded` (zwei Sätze: Filamente /
  Herstellerprofil baut Turm), sonst `support_layers_findings`.
- `advise.WHOLE_LAYER_GAP_FLAVOURS` (Kante slice→export war verboten);
  `slicer_keys.support_gap_in_whole_layers` liest sie träge.
- Halbe Schicht rundet auf (`+ EPS_GEOM`), Test `test_half_a_layer_rounds_up`.
- Test `test_the_console_frees_the_support_layers_like_the_file`.
- Changelog-Satz Trennschicht folgt der Fläche (sechs Sprachen), `druckrat.md`,
  Begründung `regel-druckrat.md` mit berichtigten Messzahlen.
- `slicer_keys.py` neue Kommentarzeilen (Zählung der Orca-Familie) und
  `WHOLE_LAYER_GAP_FLAVOURS`-Umstellung: **der Sitzung „Codesigning und
  Druckerprofile“ ansagen.**

Offene Schritte, in dieser Reihenfolge:
1. **Tor** lief zuletzt (`bash .claude/scripts/suite-getrennt.sh` in
   `F:/sl-stuetzen`); Ergebnis war noch nicht da. Neu fahren, Exit-Code lesen.
   Der Lauf davor hatte 12 Fehler, alle behoben und einzeln grün (647 Tests der
   betroffenen Dateien, 50 Dialogtests). ruff, format, mypy grün.
2. **Drache PETG**: lief beim Wechsel (`drache_petg.sh`, gepinnt mit
   `cmd //c "start /b /wait /affinity FFFFF0FF bash drache_petg.sh"`), Log
   `output/drache-2026-10-08/kontakt-drache-petg.log` endet mit `EXIT=`. Fehlt
   die Zeile, neu starten. Auswerten wie den PLA-Lauf
   (`output/drache-2026-10-08/kontakt-drache-pla`, alter Zwischenstand
   `kontakt-drache-petg-zwischenstand`): Abstand je Programm am PETG-Drachen
   (Erwartung 0,28 mm wo frei, Cura ganze Schicht), kein Absturz.
3. **Archiv**: `archiv-rm583.md` in `ROADMAP-ARCHIV.md` einsetzen (oben in die
   Tabelle und als Abschnitt wie RM-620), `{DRACHE}` mit dem Ergebnis aus 2,
   `{TOR}` mit der Zahl aus 1 füllen; `test_calibration.py` in die Testliste.
   Eintrag RM-583 aus `ROADMAP.md` entfernen (Tabellenzeile 69 und Abschnitt ab
   `- [ ] **RM-583`).
4. **Commit** mit `git commit -F commit_rm583.txt` (nur eigene Pfade,
   `git diff --cached --name-only` lesen), CI-Auswahl mit
   `python ci_start.py einstellungen/stuetzabstand` (startet beide Workflows),
   bei Grün per Merge landen, Worktree abbauen.
5. Budgets: `dateiformat.md` RM-583 30 715, RM-620 30 708, main 30 719 — beide
   zusammen bleiben unter 30 720; nach dem zweiten Merge `wc -c` prüfen.

## 3. RM-621 — Signaltod hinter Flatpak (Worktree `F:/sl-signal`, Zweig `slicer/signaltod`)

Von main `204025590`, **ungesichert** (`rm621-ungesichert.patch`):
`handover.crashed(exit_code, *, wrapped=False)` erkennt 128 + {4,6,7,8,9,11};
`handover._wrapped(setup)` = Slicer als Flatpak oder Solidon im Flatpak; Aufruf
in `slice_model`. Tests `test_a_crash_behind_flatpak_is_a_crash` und
`test_a_flatpak_slicer_that_crashes_says_so`, Gegenprobe rot ohne Fix.

Offen, **nach** der Landung von RM-620 (gleiche Zeilen in `dateiformat.md`):
main hineinmergen; in `.claude/rules/dateiformat.md` unter „Ein Absturz ist keine
Absage“ ergänzen „hinter Flatpak 128 + Signal“ (Budget 30 720, vorher straffen);
Begründung in `konzepte/begruendungen/regel-dateiformat.md`; Changelog-Punkt
unter 0.6.0 (Behebung, Linux mit Flatpak: Absturz statt „keine Druckdatei“),
sechs Sprachen; Archiveintrag RM-621; Tor, Review `solidon3d-review`, Commit,
CI-Auswahl, Landung.

## 4. RM-622 — neu: mit Reinigungsturm den Abstand in ganzen Schichten raten

Befund aus dem Agentenbericht (`agent-cura-bambu-bericht.md`): Mit Turm legt die
Orca-Familie die Stütze auf die Schichten des Modells und rundet auf die nächste
(`SupportMaterial.cpp:1698-1718`); PLA bei 0,08er Schichten bekäme 0,08 statt
mindestens 0,10. Bau: Rat erfährt, ob die Platte einen Turm hat
(`handover.tower_cause`), und nimmt dann `support_gap_target` wie bei Cura
(ganze Schichten im Band) — im Dialog (`_AdviceWorker._calculate`) und im Export
(`writer.part_advice`, Cache-Schlüssel) gleich (Zwillinge). Ins Register
eintragen, bauen, messen (gemischte Platte PLA+PETG bei 0,08 mm im ElegooSlicer).

## 5. Danach RM-584 bis RM-589 (Register in `ROADMAP.md`, Recherche Nr. 4–15)

RM-584 Stilwahl je Deckenform (Orca `tree_hybrid`, Prusa `snug`), Bäume ab
~100 mm mit zwei Wänden/Fuß/Doppelwand, Baumspitze; RM-585 Bögen schließen sich
(Eiffelturm); RM-586 variable Schichthöhe über die 3MF, Deckschicht ≥ 0,8 mm;
RM-587 dicke Brücken, Brückenfluss, Zusatzwände an Überhängen; RM-588 Naht
hinten, Bügeln der obersten Fläche; RM-589 Loch-/Elefantenfußausgleich mit dem
Spiel des Materialprofils.

## Werkzeug und Fallen

- Interpreter aus den Worktrees: `"/f/3D Druck/.venv/Scripts/python.exe"`.
- Python-Ersetzungen mit Bytes (LF); **kein `\n` in Strings eines Heredocs** —
  Git Bash macht daraus Zeilenumbrüche (zweimal passiert). Edit-Werkzeug nehmen.
- Elegoo-Messungen mit `slicer-orca-af8733f715e1dfb0606b`.
- Kontaktsonde `.claude/.state/drache-2026-10-08/kontakt_je_teil.py` (im Zweig
  RM-583 versioniert) misst jetzt mit 2-mm-Raster und Bambus Übergangslage als
  Stütze; `SONDE_NUR_MESSEN=1` misst vorhandene G-Codes neu.
- Die Konsolidierungssitzung nutzt RM-630–639.
