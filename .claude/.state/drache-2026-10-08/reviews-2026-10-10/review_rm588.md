# Review RM-588 — Naht hinten an Figuren, Bügeln großer Oberseiten, Format 52 (Prüfer rv588)

Gegenstand: Worktree `F:\sl-naht`, Zweig `einstellungen/naht-rm588`, Spitze `4243682c3`
(welle4 `a72079433` drin), eigener Diff `git diff origin/welle4...4243682c3` (55 Dateien,
+1054/−57). Nur gelesen und gemessen; nichts im Worktree geändert. Sonden und Ausgaben unter
`F:\sl-naht-mess\rv588\` (Quellstände `w4\` = `git archive origin/welle4`, `v053\` =
`git archive v0.5.3`). Alle Läufe gepinnt (`/affinity FFFFF0FF`), `app.__file__` je Sonde geprüft,
pytest mit `-p no:cacheprovider`, `PYTHONDONTWRITEBYTECODE=1`, `--basetemp` auf F:.

## Urteil

**Nicht landen, bis S1 behoben ist** — dann kann es landen. S1 macht `test_value_labels` rot
(Tor und welle4 rot); der Fix ist eine Hilfsfunktion, im Prüfbaum belegt (454 passed, Abdrücke
vollständig gleich). L1–L5 sind leicht und gehören in denselben Zug. Inhaltlich hält der Punkt:
Format 52 öffnet jede alte Datei wie welle4 (89 von 89, auch über 35 → 36), der Abdruck einer
Buchung aus 0.5.3 und welle4 bleibt (6 von 6, beide Abdruckarten), die zwölf Beispiele ändern sich
nur im Format, „oberste Fläche“ und „alle Oberseiten“ kommen in ElegooSlicer und Cura genau so an
und die Schätzung trifft die Bügelzeit (1,00–1,04), „hinten“ legt die Naht in beiden nach hinten
(Cura 75 → 91 %, ElegooSlicer Spider-Man vorn 29 → 1 %), und der Kumiko-Rat ist gemessen kein
falscher. **Nachprüfung nicht nötig** (ein
schwerer Fund mit belegtem mechanischem Fix, sonst leichte); nach dem Fix genügen
`test_value_labels.py`, `test_filament_usage*.py`, `test_changelog.py`, `test_text_length.py`
und `test_manufacturer.py` grün im Bericht des Bauagenten.

## Neue Punkte für den Koordinator

1. `test_value_labels.py` in die Pflichtliste der Baumleser im AUFTRAG (S1 rutschte durch, weil
   weder der Importgraph noch die Liste ihn nennt). Dieselbe Lücke haben weitere Leser des ganzen
   Baums, die die Liste nicht nennt (u. a. `test_security.py`, `test_style.py`,
   `test_native_keys.py`, `test_source_escapes.py`) — hier alle grün (`lauf2`).
2. `test_print_settings_ui.py::test_print_advice_remembers_measured_layers_across_dialogs` ist
   unter `-n 4` einmal rot gewesen (3 statt 2 Messungen), einzeln dreimal grün — Kandidat für
   eine wackelige Fensterprüfung, nicht RM-588.

## Funde

### S1 — schwer (Landeblocker): `test_value_labels` ist rot

- **Wo:** `app/core/filament_usage.py:909` (`values["plate_choices"] = {…}` in `prepare`).
- **Beleg:** `tests/test_value_labels.py::test_every_value_key_has_a_label` → „ohne
  Beschriftung landet der Bezeichner selbst im Tooltip: plate_choices (filament_usage.py)“, rot in
  `lauf1` (61 Dateien: 8652 passed, 30 skipped, **1 failed**, EXIT=1) und `lauf2` (52 Dateien:
  3101 passed, 2 skipped, **1 failed**, EXIT=1). Gegenprobe `werteschluessel.py` (dieselbe
  AST-Suche des Tests über beide Stände): welle4 403 Schlüssel, keiner ohne Beschriftung; RM-588
  404, `plate_choices` ohne. welle4 hat in `filament_usage.py` keine Zuweisung `values["…"] =`.
- **Warum es zählt:** Das Entwicklungstor vor main wird rot; welle4 nach dem Merge ebenso.
  Der Test liest jede Zuweisung an einen Namen `values` in `app/core` als Befundwert — hier ein
  Fehlalarm, aber ein roter Lauf. Der Test stand weder in der Auswahl des Bauagenten noch in der
  Pflichtliste der Baumleser im AUFTRAG (er liest den ganzen `app/core`).
- **Fix:** Die Umrechnung aus `prepare` in eine Hilfsfunktion neben `_as_saved` ziehen, die den
  Satz unter anderem Namen baut, etwa `_saved_data(mine)`: `data = print_settings_to_data(mine)`,
  `data["shell"]["ironing"] = …`, `data["plate_choices"] = {…}`, `return data`; in `prepare`
  `values = _saved_data(mine)`. Damit stehen beide Format-51-Lesarten (`_owned_settings` und der
  ausgewertete Abdruck) an einer Stelle.
- **Fix belegt** (in einem Prüfbaum `F:\sl-naht-mess\rv588\fix\` = `git archive 4243682c3` plus
  Wurzel-`conftest.py`, nicht im Worktree): mit `_saved_data` sind `test_value_labels.py` und alle
  acht Abdruck-/Verbrauchsdateien grün (`fixlauf.sh`: **454 passed, EXIT=0**; derselbe Lauf am
  Worktree 453 passed, 1 failed), `ruff`/`format` der Datei 0/0, und die Abdrucksonde gibt mit
  dem Fix **vollständig dieselben** Abdrücke (ausgewertet, gespeichert, Alt- und Vorabdrücke,
  6 von 6 je Schreiber, `abdruck_fix.sh`).
- **Neuer Punkt für den Koordinator:** `test_value_labels.py` in die Pflichtliste der Baumleser
  im AUFTRAG (er liest jede Zuweisung an `values` in `app/core`).

### L1 — leicht: Changelog-Gliederung, ein fremder Punkt ohne Not geteilt

- **Wo:** `changelog/de.md:131–133` und dieselben drei Zeilen in `en/es/fr/it/pt.md`.
- **Beleg:** Der welle4-Punkt „Neu in den Druckeinstellungen: *Trennschichten unten*, *Wände der
  Bäume* und *Baumspitze*, dazu *Erste Schicht einziehen* und *Löcher weiten*, …“ wurde in einem
  Merge (`cf3ca5d89`) geteilt, als RM-588 noch ein neues Feld *Oberste Fläche bügeln* hineinschrieb;
  `208030f2c` nahm das Feld wieder heraus und setzte den Bügelpunkt **zwischen** die zwei Hälften.
  Jetzt folgt „Ebenfalls neu sind *Erste Schicht einziehen* und *Löcher weiten*“ auf „Bei
  *Oberfläche bügeln* wählen Sie jetzt …“ — das „Ebenfalls“ greift über einen fremden Punkt.
- **Warum:** Kundentext (`auslieferung.md`, AUFTRAG „Kundenwirkung“); RM-588 ändert einen Punkt
  anderer RM ohne eigenen Grund.
- **Fix:** In allen sechs Sprachen den welle4-Punkt wiederherstellen (Längen dort 182–188 Zeichen
  ohne Sternchen, `cl_w4_*.md`) und den Bügelpunkt dahinter setzen; `test_changelog.py`,
  `test_text_length.py`.

### L2 — leicht: Die Regel verlor ihre Anweisung

- **Wo:** `.claude/rules/dateiformat.md:386–389`.
- **Beleg:** Vorher „wer die Auflösung ändert, prüft an einer von der alten Version
  gespeicherten Datei (`print_settings_v33.p3d`)“, jetzt „…, einen Wert mit neuem Typ vorher
  umgerechnet (Bügeln, Format 52); geprüft an `print_settings_v33.p3d`“ — eine Feststellung statt
  einer Regel. Gerade die neue Lehre (35 → 36 liest mit heutigen Funktionen, ein Typwechsel muss
  dort vorher umgerechnet werden) braucht den Imperativ für den Nächsten.
- **Fix:** „…; wer die Auflösung oder den Typ eines Werts ändert, rechnet ihn in 35 → 36 vorher
  um (Bügeln, Format 52) und prüft an `tests/data/projects/print_settings_v33.p3d`.“

### L3 — leicht: Prusa deutet „solid“ um, Orca nicht (Zwillinge)

- **Wo:** `app/core/export/manufacturer.py:1899–1908` (`_prusa_ironing`) gegen `:480–484`
  (Orca `_choice`).
- **Beleg:** Prusa liest `ironing = 1` mit `ironing_type = solid` als `top_surfaces`; Orca liest
  `ironing_type = solid` als `Foreign("solid")` („Hersteller: solid“). Regel `dateiformat.md`:
  „Was sich nicht übersetzen lässt, wird nicht umgedeutet (`Foundation.foreign`)“. Kein
  Herstellerprofil nutzt „solid“ (gezählt: Elegoo/Orca 657/656 „no ironing“, 12 „top“; Bambu 165
  „no ironing“; Prusa 21 `ironing_type = top`) — es trifft nur eigene Profile.
- **Fix:** `_prusa_ironing` gibt für eine Art außer `top`/`topmost` `Foreign(text)` zurück (`take`
  nimmt es an), Test in `test_ironing_the_topmost_surface_is_read_back` mit „solid“ für beide
  Familien.

### L4 — leicht: Die Figurenprüfung rechnet je Umriss in Python

- **Wo:** `app/core/slice/analysis.py:5522` (`_outline_measures`).
- **Beleg:** cProfile an der Kumiko-Schale (`profil.py`, 476 Schichten, 19 626 Umrisse):
  `_outline_measures` 0,99 von 1,24 s (80 %), je Umriss zwei `np.diff` und zwei Skalarprodukte
  (39 728 `diff`-Aufrufe). Ohne Profiler 0,39–0,48 s CPU je Körper und Schnitt (`kosten.py`:
  Spider-Man 0,42 s, Kumiko 0,48 s, Besenhalter 0,30 s; zweites Fragen 0,0000 s).
- **Warum:** AGENTS „Schleifen je Element … als Feldrechnung gebündelt“; der Rat fragt jeden Körper
  einer Platte einmal je Schnitt.
- **Fix:** Fläche und Umfang aus den schon gebauten Ringen vektorisiert (`shapely.area` über
  `shapely.polygons(rings)`, `shapely.length(rings)`, je Schicht summiert) oder per
  `np.add.reduceat` über das ohnehin gebaute `np.concatenate(outlines)`; Anteil am Korpus vorher
  und nachher gleich (Drache, Spider-Man, Kumiko, Besenhalter), CPU-Zeit im Wechsel.

### L5 — leicht: Der Docstring des Schritts verspricht, was der Leser nicht tut

- **Wo:** `app/core/scene/migrations.py:1574–1575` („ein anderer Wert bleibt, wie er ist, die
  Datei öffnet dann mit der Vorgabe“).
- **Beleg:** `serialise._group_from_data` übernimmt jeden Wert mit `klass(**values)`, die
  `Literal`-Typen gelten zur Laufzeit nicht (`project._validate_print_settings`, Docstring). Ein
  fremder Text bleibt also im Satz, nicht die Vorgabe — und dann schreibt die Orca-Familie
  `no ironing` (`_mapped(_IRONING_TYPES, "no ironing")`), Prusa `ironing = 1`
  (`_mapped({"none": "0"}, "1")`), Cura `ironing_enabled = true`. Nur bei beschädigten Dateien.
- **Fix:** Den Satz berichtigen („bleibt, wie er ist“) oder im Schritt einen unbekannten Wert auf
  `none` setzen und das so sagen; kein Wächter nötig, eine Zeile im vorhandenen
  `test_the_ironing_step_leaves_everything_else_alone`, falls es umgesetzt wird.

## Stand des Durchgangs (fortlaufend)

- Auftrag, Regel `dateiformat.md`, Bericht `rm588.md`, ganzer Diff gelesen.
- `lauf1.sh` (61 Testdateien samt Pflicht-Baumleser, ohne Fenster): 8652 passed, 30 skipped,
  1 failed (S1), EXIT=1, 14 min.
- `lauf2.sh` (52 weitere Baumleser und Leser der berührten Dinge, ohne Fenster): 3101 passed,
  2 skipped, 1 failed (S1), EXIT=1.
- `lauf3.sh` `test_print_settings_ui.py` mit Fenster (`-n 4`): 344 passed, 1 failed
  (`test_print_advice_remembers_measured_layers_across_dialogs`: 3 statt 2 Messungen), EXIT=1;
  `lauf4.sh` derselbe Test einzeln dreimal: 3 von 3 passed, EXIT=0 — unter Last wackelig, nicht
  RM-588 zuzuordnen (RM-588 ändert die Zahl der Schnitte im Dialog nicht). Grün darin u. a.
  `test_every_group_holds_one_subject`, die Suche nach „Oberfläche bügeln“ und der
  Prusa-Zweitfilament-Test.
- `ruff check` EXIT=0, `ruff format --check` EXIT=0 (1217 Dateien), `mypy` EXIT=0 (375 Dateien),
  alle ohne Cache im Worktree (`lint.sh`).

## Geprüft und gehalten

### 1. Formatschritt 51 → 52

- **Checkliste „Dateiformat ändern“**: `FORMAT_VERSION` 52, Schritt `_ironing_becomes_a_choice`
  (Satz und `plate_choices`), alte Beispieldatei `ironing_v51.p3d` (von welle4 `1e4dec783`),
  Test `test_v51_ironing_switch_becomes_the_same_choice` (Herkunft, Übergabe, Druckzeit),
  `example_v52.p3d` aus `build_example_project`; ältere Schritte bleiben einzeln.
- **35 → 36 öffnet alte Dateien wie vorher** (`migr_sonde.py`, `vergleich.py`): alle 84
  öffnenden Dateien aus `tests/data/projects` plus fünf Abwandlungen mit Bügeln an
  (`varianten.py`: `example_v4`, `example_v5`, `print_settings_v33`, `example_v40`,
  `example_v51`) mit welle4 und mit RM-588 geöffnet: **89 von 89 Druckeinstellungssätze gleich**
  (Bügeln als Wahl verglichen), samt `chosen`/`accepted`/`plate_choices`. 23 Dateien tragen
  einen Satz (Formate 4, 5, 33, 36–52). Gegenprobe RM-588 ohne die Umrechnung in 35 → 36:
  `print_settings_v33.p3d` bekäme `shell.ironing` als eigene Wahl (1 von 89 anders). Die
  Änderung am alten Schritt ist also eine Korrektur, die das alte Ergebnis hält — kein Fund.
- **Beispielprojekte nur um den Formatschritt verändert** (`beispiele_diff.py` über
  `git show`): zwölf von zwölf unterscheiden sich allein in `format_version` 51 → 52; Bilder,
  Quellen, Bericht bytegleich. Wächter `test_every_example_carries_the_current_file_format`.
- **Schema/Leser**: `_validate_print_settings` prüft nur die Form; `_plate_choices` verwirft
  einen Wert falscher Art — deshalb muss 51 → 52 auch `plate_choices` umrechnen (tut es).
  Verlauf/Undo tragen keine Druckeinstellungen (`history.py` nur `spool_bindings`),
  Spulenwerte keine Wände (`_OVERRIDE_GROUPS`), Rezepte tragen keine Druckeinstellungen,
  Agentenschicht und CLI setzen kein Bügeln, `filament_readback` liest kein Bügeln, kein
  3MF-Export trägt Solidons Satz. Kein übrig gebliebener Wahrheitswert-Test auf
  `shell.ironing` im Code.

### 2. Abdruck einer Buchung (RM-705/706)

Eigene Sonde `abdruck_sonde.py` (sechs Szenarien, nur Felder aus 0.5.3: ohne Bügeln, Wahl an,
Vorschlag an, Wahl aus, Vorschlag an über Plattenwahl aus, Vorschlag aus über Plattenwahl an),
geschrieben von 0.5.3 (Format 46) und welle4 (Format 51), gelesen von 0.5.3, welle4, RM-588
und RM-588 ohne `_as_saved`; Abdruck über ausgewertete Netze **und** über gespeicherte
Eingänge (`StoredInputs`, RM-706; die Sonde des Bauagenten prüfte nur den ersten):

- 0.5.3-Abdruck (ausgewertet) = RM-588 ausgewertet/`former`: **6 von 6** (Dateien von 0.5.3
  und von welle4).
- welle4-Abdruck über gespeicherte Eingänge = RM-588: **6 von 6**.
- Gegenprobe ohne Umrechnung: ausgewertet 0 von 6 gleich, gespeichert 1 von 6 (der Fall
  ohne Bügeln in `explicit`, richtig so).

### 3. Übergabe im echten Slicer (eigene Sonde `slicer_sonde.py`, Herstellerprofil, Standard, PLA)

Sockel 30 × 30 × 10 mit Würfel 10 × 10 × 10, *Oberfläche bügeln* als eigene Wahl:

| Programm | none | topmost | top_surfaces | Bügelzeit Slicer / Solidon |
|---|---|---|---|---|
| ElegooSlicer (Neptune 4, 0.20mm Standard) | keine Bügelbahn | z 20,00: 614,4 mm | z 10,00: 5 174,3 + z 20,00: 614,4 mm | topmost +17 / +17,0 s, top_surfaces +192 / +192,9 s |
| Cura 5.13 (Ender-3 V3 SE) | keine | z 20,05: 863,2 mm | z 10,05: 7 433,5 + z 20,05: 863,2 mm | topmost +24,5 / +25,5 s, top_surfaces +255,9 / +262,8 s |

Bahnlängen gleich denen im Bericht (614,4/5 788,6 und 863/8 297 mm). Die Gesamtzeit weicht
davon unabhängig ab (Elegoo Solidon 830 gegen 913 s, Cura 1 056 gegen 1 269 s) — RM-281.
Cura legt Bügeln als `SKIN` mit wenig Förderung; erkannt über ein Drittel des 90. Perzentils
(`cura_buegeln.py`; mit dem Median sah die erste Lesart bei „alle Oberseiten“ nichts, weil dort
die meisten SKIN-Stücke selbst Bügelbahn sind).

Naht (je geschlossener Außenschleife: Anfang im hintersten/vordersten Fünftel ihrer Tiefe,
Ecke = Knick über 30° am Anfang; „Grundlage“ ist die Naht des Herstellerprofils, „rear“ der
übernommene Vorschlag):

| Körper, Programm | Anteil frei geformt, Rat | Grundlage hinten / vorn / Ecke | rear hinten / vorn / Ecke | Zeit |
|---|---|---|---|---|
| `generated_figure.stl`, Cura | 0,998, „rear“ | 74,6 / 0 / 16,9 % (142 Schleifen) | 90,8 / 0 / 2,1 % | 1 219 → 1 222 s |
| `clean_figure.stl` (Gliederpuppe aus Grundformen), ElegooSlicer | 0,138, kein Rat | 38,6 / 55,5 / 37,0 % (541) | 98,9 / 0 / 42,7 % | 3 633 → 3 631 s |
| Kumiko-Schale, ElegooSlicer | 0,775, „rear“ und „topmost“ | 46,5 / 48,1 / 97,3 % (32 075) | 95,5 / 1,4 / 92,7 % | 21 050 → 21 306 s |
| Spider-Man (Voronoi, 886 000 Dreiecke), ElegooSlicer | 0,999, „rear“ | 33,5 / 29,2 / 23,4 % (6 475) | 81,3 / 1,0 / 20,6 % | 10 772 → 10 717 s |

ElegooSlicer hier mit Neptune 4 statt der Maschine des Bauagenten und mit eigener Zählweise (jede
geschlossene Außenschleife, „hinten“ im eigenen Tiefenmaß): Spider-Man vorn 29 → 1 % wie dort
(39 → 2 %); hinten 81 statt 90 %.

`generated_figure.stl` schnitt ElegooSlicer schon ohne Rat nicht (offenes Netz, roh übergeben —
kein RM-588-Befund). **Kumiko, „falscher Rat?“ — nein, gemessen:** Mit „aligned“ beginnt fast
jede zweite Schleife vorn (48,1 %), wenn auch in einer Ecke; „hinten“ nimmt die Naht von der
Vorderseite (1,4 %) und lässt sie fast überall in einer Ecke (97,3 → 92,7 %), für +1,2 %
Druckzeit. Die Gliederpuppe zeigt die Grenze der Regel in die andere Richtung: Rumpf und Glieder
sind Prismen, nur der Kopf zählt als frei geformt — kein Rat, obwohl „hinten“ dort 55,5 % vordere
Nähte nähme. Beides keine Fehlfunktion, sondern die gewählte Schwelle; der Neue Punkt 3 des
Bauagenten kann entfallen oder um die Gliederpuppe ergänzt werden.

### 4. Rat und Feld

- `_from_top` und `_from_fits` geben nie zwei Vorschläge für denselben Pfad („flush“ schließt
  „topmost“ aus); „topmost“ nur ohne eigenes Bügeln, mit Deckschicht, letzte Schicht ab 400 mm²
  und halbem größtem Querschnitt. Naht nur bei „aligned“/„nearest“, ab 10 mm Höhe.
- Gründe in sechs Sprachen, Kundenwörter; `test_text_length.py`, `test_translations.py`,
  `test_wording.py` grün (`lauf1`). Werte „Ohne / Oberste Fläche / Alle Oberseiten“ mit Satz je
  Wert (`labels._CHOICE_NOTES`), Katalognamen gleich den Changelog-Namen in allen sechs Sprachen.
- Reiter *Wände* 15 Felder: `test_every_group_holds_one_subject` mit Fenster grün,
  `test_interface_limits.py` grün.
- Der Rat läuft im Arbeiter (`_AdviceWorker`, Export `writer._part_values`); der synchrone Aufruf
  in `print_settings_dialog.py:8260` läuft nur ohne Körper auf der Platte.
- `shell.ironing` in `SLICED_PATHS` ist nötig: Ohne Schnitt fände der Export den Rat „topmost“
  je Teil nicht (`writer._part_values`, Zeile 1524).

### 5. Leistung, Regeln, Unterlagen

- **Figurenprüfung** (`kosten.py`, CPU-Zeit, gepinnt, unter Fremdlast): Spider-Man 0,42 s erst,
  0,0000 s zweit; Kumiko 0,48/0,0000 s; Besenhalter 0,30/0,0000 s — wie im Bericht, gemerkt je
  Schnitt. Bündelung siehe L4. Kein §31-Budget für Rat oder Druckzeit (`test_performance.py`
  fragt beides nicht).
- **Harte Regeln:** 1 (kein Qt im Kern, `test_core_isolation` grün), 6 (Vergleiche über
  `is_close`/Toleranzen; `==` nur auf Texten), 7/8 (Schwellen `FIGURE_SHARE`, `STRAIGHT_RUN`,
  `IRONING_TOP_AREA`, `IRONING_TOP_SHARE`, `IRONING_SHARE`, `IRONING_SPACING` sind Ratsschwellen
  und Slicervorgaben mit Herkunft, keine Toleranzen), 17/20 (keine neue Ausnahme, alle Texte über
  `_()`), 18 (Vorschlag mit Text) — gehalten. Regel 21 nicht berührt.
- **Changelog:** neue Punkte ≤ 200 Zeichen, sechs Sprachen, gleiche Gliederung
  (`test_changelog.py` grün); Wortlaut kurz und sachlich. „Die geschätzte Druckzeit rechnet das
  Bügeln jetzt mit.“ als Eigenschaft ist richtig (0.5.3 hatte `print_time` ohne Bügeln, die
  Ursache lag im Tag; als Eigenschaft immer zulässig). Gliederung: L1.
- **Archiv/Register:** RM-588 aus dem Register, Eintrag im Archiv mit Messwerten,
  `test_roadmap.py` grün. Karten und Regeln: `test_directory_docs.py` grün (Budgets), Karte
  `slice/CLAUDE.md` nachgezogen, Regel `druckrat.md` +3 Punkte, `dateiformat.md`: L2.
