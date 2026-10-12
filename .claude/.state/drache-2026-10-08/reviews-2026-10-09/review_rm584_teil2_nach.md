# Nachprüfung RM-584 Teil 2 (F:/sl-stil, Zweig einstellungen/stuetzstil, Stand b89d942e7) — 09.10.2026

**Kurzfassung:** Alle 17 Befunde des ersten Reviews sind im Kern behoben; 18 von 19
Gegenproben werden rot. Neu: 2 mittel, 8 leicht, beide mittleren entstehen aus den
Behebungen M1 und M3. **Kann so nicht rein**, nach N1 und N2 gezielte Nachprüfung.

## Die Befunde des ersten Reviews

Gegenprobe heißt: der Fix im geladenen Code zurückgenommen (Pytest-Plugin
`scratchpad/mutants.py`, keine Datei geändert), die zuständigen Tests gefahren.

| Befund | Stand | Beleg |
|---|---|---|
| M1 Gitter über „automatisch“ | behoben | `handover.tree_styles`, `advise.py:1285-1302`; `test_grid_over_automatic_only_where_automatic_means_trees`, `test_the_tree_styles_say_…`. Gegenproben `auto_trees = True` und „Prozess nicht gefragt“: je 1 rot. Rest: N1 (Cura) |
| M2 Ersatz verdrängt Grund | behoben für „Stützen an“ | `slicer_keys.py:1584`; Satz 54 Zeichen (en 58, fr 57); `_reason_texts` prüft Ersatzsätze, grün. Gegenprobe 2 rot. Rest: N3 (Hybrid aus der Zusammenführung) |
| M3 Gitter + Baum = Hybrid ohne Datei | behoben für Orca/Prusa | `style_per_part`, `combine(together=)`; Test `[orca-tree]`, `…combine_to_hybrid`. Gegenproben Dialog und `combine`: je 1 rot. Rest: N1, N2 |
| M4 Wandvorschlag fragt Solidons Art | behoben | `advise.py:1417-1444`; `test_the_walls_ask_the_style_the_program_prints`. Gegenprobe 2 rot |
| M5 Prusas Doppelwand | behoben | kein Prusa-Schlüssel, `NOT_TAKEN_BY["prusa"]`, Feldsatz; `test_tree_walls_reach_each_family`. Gegenprobe rot |
| M6 kein Slicertest | behoben | drei Slicertests; hier gelaufen: `test_tree_walls_change_…[elegooslicer-cc2]` und `test_hybrid_for_one_part_…[elegooslicer]`, 2 grün (155 s). Rest: N9 |
| L1 Säulenhöhe | behoben | `analysis.py:4109-4127`; Test mit Turm, Landung, Rand. Gegenproben „ohne Bett“ und „Ränder zählen“: je 1 rot. Rest: N4 |
| L2 Tests | behoben | Paar 95/105, Gitter, abgelehnter Baum |
| L3 Feld unter Gitter | behoben für Gitter | `print_settings.py:725`; Gegenprobe rot. Rest: N5, N6 |
| L4 Zwillinge | behoben | Wächter Hybrid gegen Ersatztabelle (Gegenprobe rot), Feldgrenze |
| L5 Bambu | behoben | gemessen, Parameter im Test, Gegenprobe rot |
| L6 Gitter über Hybrid | behoben | Gegenprobe rot |
| L7 Hybrid nur mit Details | behoben | `details_on_model`; Gegenprobe (`on_model`) rot |
| L8 Baum über Hybridprozess | behoben | `tree_over_hybrid`; Gegenprobe 2 rot |
| L9 Unterlagen | behoben in Regel, Begründung, Testdocstrings | Rest: ROADMAP-ARCHIV (N8) |
| L10 Wände plattenweit | behoben | Begründung an `PART_PATHS` |
| L11 Changelog | behoben | sechs Sprachen, es „cuadrícula“ |
| Hohle Bäume, Creality-Schlüssel | gebaut | Gegenproben `hollow_trees`, `_read_process` gemeinsamer Name, `PROGRAM_KEYS` ohne Creality: 2, 2, 3 rot |

## Neue Befunde

### Mittel

**N1 — Cura mit gefundenem Programm: Pilz und Figur auf einer Platte drucken beide unter Bäumen**
`app/core/slice/advise.py:1294-1295` mit `:448-457`, `app/ui/print_settings_dialog.py:1545-1549`.
Seit M1 sagt der Pilz unter Cura „automatisch“ (dort `normal`), und `_combined_value`
stellt `tree` über `auto`; Curas `support_structure` gilt der Platte. Sonde mit
`tree_styles` = {tree} (`probe_cura_choice.txt`): Platte „Aus“ gibt „Aus → Baum“ ohne
Teile, Platte „Automatisch“ „Automatisch → Baum · Figur“. Export
(`probe_rm584n_cura_export.txt`): `support_structure` tree, beide Netze
`support_enable` true, Befund `export.part_setting obj_pilz tree` mit dem Grund des
Pilzes, kein `part_setting_unavailable` (ohne Programm kommt er). Der Hut des Pilzes hängt
zwischen Baumspitzen durch, genau was RM-584 verhindern soll. Vor M1 (568fdd649) sagte
der Pilz Gitter, die Platte bekam Gitter. Der Test
`test_grid_and_tree_become_hybrid_only_where_the_style_is_the_plates[cura-hybrid]`
(`tests/test_print_settings.py:8279`) fährt ohne Setup (`trees` None) und behauptet „Hybrid
bleibt und geht als Gitter hinaus“ — mit gefundenem Cura stimmt das nicht.
Fix: Wo die Art der Platte gilt (Cura), unter der flachen Decke ausdrücklich Gitter
vorschlagen (Curas „automatisch“ druckt ohnehin `normal`), oder `combine` die `trees`
geben und ein „automatisch“, das kein Baum ist, in der Regel {grid, tree} wie Gitter
zählen. Test am Arbeiter und am Export mit `tree_styles` = {tree}.

**N2 — Stützart je Teil (Orca, Prusa): Zeile und Feldhinweis verschweigen den Pilz**
`app/ui/print_settings_dialog.py:1804-1811` (Teilnamen nur bei gleichem Wert, seit M3 auch
für `support.style`) und `:7383-7419` (`_mark_parts`). Die Zeile heißt
„Aus → Baum · Figur“ (der Test sichert das, `tests/test_print_settings.py:8307`). Sonde
`probe_rm584n_parts.txt`: nach dem Übernehmen `accepted_parts` = {support.style: (Figur,)},
also „Nur für Figur. Die übrigen Teile drucken mit Aus aus …“ — die 3MF gibt dem Pilz
`enable_support` 1, `normal(auto)`, `rectilinear-grid`. Wählt der Kunde die Zeile ab,
weil er an der Figur keine Bäume will, druckt der Pilz ohne Stütze, und keine Zeile hat ihn
genannt. Der Feldhinweis hat die Lücke seit RM-289 B6, die Teilnamen der Zeile kamen mit M3.
Fix: Für Pfade in `separate` die Teile mit eigenem, abweichendem Wert nennen („Baum ·
Figur, Gitter · Pilz“ oder je Wert eine Zeile), `_mark_parts` den Wert der übrigen aus
ihrem eigenen Rat statt aus der Grundlage; Test an `parts` und Hinweis.

### Leicht

**N3 — Cura: Hybrid aus der Zusammenführung bringt den Ersatzsatz, und die Zeile nennt nur ein Teil**
Platte „Baum“ (eigene Wahl), Pilz und Figur, Cura gefunden (`probe_cura_choice.txt`):
Arbeiter „Baum → Hybrid · Pilz“, Dialog nach `offered` „Baum → Gitter — Dieser Slicer kennt
kein Hybrid und stützt mit Gitter.“ Hybrid hat der Kunde nie gesehen, der Grund „Große
flache Decken …“ ist weg (`slicer_keys.py:1584` behält ihn nur bei `was == "none"`).
Gedruckt bekommt auch die Figur Gitter (`probe_rm584n_cura_switch.txt`:
`support_structure` normal, beide Netze an, Befund nur am Pilz). Dieselbe Bauart gab es
für „Gitter → Baum · Figur“ schon (RM-289). Fix: `combine` gibt Gitter, wo das Programm
Hybrid nicht anbietet, mit dem Deckengrund; bei Cura keine Teilnamen für einen Wechsel der
Art, nur für ein/aus.

**N4 — Säulenhöhe vom Nullpunkt statt vom Boden des Körpers**
`app/core/slice/analysis.py:4115-4127` zieht für Säulen bis zum Bett 0,0 ab;
`bed_columns` (`:4356-4364`) nimmt `layers[0].z` als Bett. Ein Körper über dem Bett (Deckel
auf der Dose, Teil auf der Grundplatte, Baugruppe, `prepare.py:3953`) bekommt die Höhe
dazu: Turm mit Insel 40 mm auf dem Bett 35,2 mm, um 70 mm angehoben 105,2 mm und
„Zwei Wände“ (`probe_rm584n_lifted.txt`); Korpusnetze um den Ursprung liefern negative
Höhen (`near_sphere_ellipsoid` −5,8). Fix: vom Boden des Körpers messen wie `bed_columns`;
Test mit angehobenem Körper.

**N5 — Der Dialog-Ersatz für das inaktive Feld ist ungetestet**
`app/ui/print_settings_dialog.py:4331-4340`: Hybrid bei PrusaSlicer und Cura als Gitter.
Gegenprobe (Ersatz entfernt) bleibt grün über `test_print_settings_ui.py`,
`test_print_settings.py`, `test_rm484_raft_*` (20 Tests). Fix: `_inactive_paths` mit
Prusa- oder Cura-Pfad und „Hybrid“ testen (die rm484-Tests bauen den Wirt schon).

**N6 — „Automatisch“ als normale Stütze: das Baumwand-Feld bleibt aktiv**
`print_settings.py:725` und `print_settings_dialog.py:4338` kennen nur „grid“. Unter Curas
„automatisch“ (`normal`) und Orca-Prozessen mit `normal(auto)` (OrcaSlicer, Creality)
wirkt das Feld nicht; `tree_styles` weiß es. Fix: `trees` wie `organic` am Arbeiter
behalten und ein „automatisch“ außerhalb von `trees` wie Gitter fragen.

**N7 — Kein Baum über einem ersetzten Hybrid**
`advise.py:1319`: `settings.support.style in ("auto", "grid")`. Ein „Hybrid“ aus einem
Elegoo-Projekt druckt unter PrusaSlicer und Cura Gitter, die Figur bekommt aber keinen
Baumvorschlag. Fix: eine ersetzte Art wie ihren Ersatz fragen (`"hybrid" not in printed_trees`).

**N8 — Unterlagen nicht nachgezogen**
- `app/core/types.py:1396-1400`: „zwei heißt dort ab 3 mm, Prusas Vorgabe“ — seit M5 kein Prusa-Schlüssel.
- `ROADMAP-ARCHIV.md:27324ff.`: Prusa `support_tree_branch_diameter_double_wall`, „Mehrere
  Körper mit Gitter und Baum ergeben Hybrid“, Gitter „auch statt automatisch“, „Die
  Orca-Familie liest … nicht; Dialog und Export filtern“ — überholt durch M1, M3, M5, L5, L9.
- `tests/test_real_slicers.py:359`: „auch für Bambu Studio, das dort fehlt, bis es gemessen ist“ — gemessen.
- `app/ui/print_settings_dialog.py:2686-2690`: `self._hollow_trees = False` steht zwischen
  `_organic` und dessen Attribut-Docstring; der Satz gehört jetzt dem falschen Attribut.

**N9 — M6-Rest: Messskript ungesichert**
`F:/sl-stil/.claude/.state/drache-2026-10-08/stil_je_decke.py` ist unversioniert
(`.claude/.state` ist versioniert, 504 Dateien); die Begründung zitiert die Messung daraus.
Mit dem Abbau des Arbeitsbaums wäre es weg. Fix: einchecken.

**N10 — Übersetzungen**
en „PrusaSlicer does not count tree walls and gives thick branches two itself.“ (etwa
„PrusaSlicer has no tree wall count and doubles the walls of thick branches itself.“); fr
„supporte en grille“ zweimal (Hybrid- und SuperSlicer-Satz; „… et utilise une grille.“); it
„soffitti piani“ in den Gründen, „soffitti piatti“ im Feldhinweis.

## RM-626 (F:\solidon-claude-a)

RM-626 steht nur im Register (`ROADMAP.md:1010`), gebaut ist nichts; der Baum ist sauber,
sein Commit ea03ab0cc ist RM-571 (`_channel_space`, `_open_above`). `git merge-tree` mit
`origin/claude/lauf-a`: `analysis.py`, `druckrat.md`, `test_slice_findings.py` laufen
sauber zusammen, Konflikt nur in `ROADMAP-ARCHIV.md` (beide hängen 09.10.-Einträge an); mit
`origin/welle2` (8 Commits weiter) sauber.

Wer RM-626 baut („Säule bis zur untersten Auflage oder Höhe je Auflage“), ändert genau
`descend` (`analysis.py:4061-4092`), wo RM-584 `lowest[owner] = index - 1` und die
Dreifachrückgabe eingeführt hat, und die Zusammenführung `:4104-4107` — Textkonflikt
wahrscheinlich. Inhaltlich ist die unterste Auflage dann zweimal geführt: RM-626 soll
`lowest` und `on_bed` übernehmen statt eine zweite Buchführung. Setzt RM-626
`landed[owner][0]` auf die unterste Auflage, wandern `channel_columns`, `open_columns` und
der Ort der Kanalfrage (`under = max(names[owner][0] - 1, low + 1)`) mit;
`tallest_column` bleibt unberührt, weil es `lowest`/`on_bed` liest. Empfehlung: RM-626
nach RM-584 landen.

## Ausgeführt

- `test_slice_findings.py` (23 RM-584-Fälle), `test_print_settings.py` (60),
  `test_export.py`/`test_print_settings_ui.py`/`test_rm484_*` (37): grün.
- `test_manufacturer.py`, `test_advise.py`, `test_print_time.py`, `test_wording.py`,
  `test_translations.py` (Auswahl): 296 grün, 6 rot in
  `test_every_manual_paragraph_reaches_the_generated_page` (`rendered`, erzeugte
  Handbuchseiten im Arbeitsbaum veraltet, Absätze sketch/resin/models — fremd).
- `test_language_rules.py`, `test_interface_limits.py`: 541 grün, 1 rot im Fenstertest
  `test_the_shortcut_list_knows_every_key_the_window_holds` (Fixture `window`, Zweig ändert
  keine Tasten — fremd, nicht im Entwicklungstor).
- 19 Gegenproben (`mutants_result.txt`, `mutant_*.txt`), 2 Slicertests, 6 Sonden
  (`probe_cura_combine`, `probe_cura_choice`, `probe_rm584n_parts`,
  `probe_rm584n_cura_export`, `probe_rm584n_cura_switch`, `probe_rm584n_lifted`), Längen der
  neuen Texte in sechs Katalogen (`lengths.py`: Gründe de ≤ 58, Kataloge ≤ 69), ruff und
  format über die geänderten Dateien grün. Kein volles Tor, kein mypy.
- Im geteilten Scratchpad überschrieben: `mutants.py`, `run_mutants.sh` (gleichnamige
  Dateien früherer Läufe). Eigene Prozesse beendet; die laufenden `korpus_alle.py` gehören
  einer anderen Sitzung.

## Urteil

Kann so nicht rein: N1 (Cura stützt den flachen Hut wieder mit Bäumen) und N2 (die Zeile
verschweigt das Teil, das mit ihr Stützen bekommt) zuerst, die leichten dazu; danach
gezielte Nachprüfung von N1 und N2.
