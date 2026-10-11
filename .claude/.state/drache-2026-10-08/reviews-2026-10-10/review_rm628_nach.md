# Nachprüfung RM-628 — Curas Stützabstand in ganzen Schichten (nach der Behebung)

Prüfling: Worktree `F:\sl-cura`, Zweig `einstellungen/cura-rundung-rm628`, Stand `c9683c3d4`
(welle3 `083dab2f6` enthalten; `origin/welle3` steht inzwischen auf `19b9af109`, ein Commit
weiter, shapely-Untergrenze). Landender Diff: `083dab2f6..c9683c3d4`, 28 Dateien.
Erstreview `review_rm628.md`, Behebung `847c94bc6`, Merges `1893fec34`, `ba30d6e50`,
`91ed3af40`, `c9683c3d4`. Scratch: `scratchpad\rv628n\`. Nichts im Worktree geändert.

Stand des Berichts: begonnen 11:45, Urteil 12:25 (unten).

## Gelesen

- AUFTRAG.md (Reviews, Prüfen), Auftrag `auftrag-rm628b.md`, Erstreview `review_rm628.md`,
  Bericht `berichte-2026-10-10/rm628b.md`, Sonden `rv628\` und `rm628b\probe\`.
- Landender Diff `083dab2f6..c9683c3d4` ganz (28 Dateien, +1544/−199), dazu `847c94bc6` und die
  Merge-Auflösungen (`--remerge-diff` von `1893fec34`, `ba30d6e50`, `91ed3af40`, `c9683c3d4`).
- Im Umfeld: `writer.part_advice`, `_part_values`, `_values_for`, `_part_setting_findings`,
  `write_assembly`; `handover.split_for_parts`, `PartSplit`, `cura_takes_whole`,
  `slot_processes`, `slot_material_type`, `unreachable_overrides`, `cura_profile_beside`,
  `for_the_cura_window`, `write_config` (Cura-Zweig); `advise._support_contact`;
  `profiles.for_object`; Druckdialog `_mark_fields_this_slicer_ignores`.
- Cura 5.13 aus der Installation: `cura/Settings/CuraContainerRegistry.py:220–388`
  (`importProfile`), `fdmprinter.def.json` (Eigenschaften der Abstandsschlüssel).

## Messungen

**Tore am Worktree** (`git status` danach leer):

| Lauf | Ergebnis | Exit |
|---|---|---|
| `ruff check .` | All checks passed | 0 |
| `ruff format --check .` | 1206 files already formatted | 0 |
| `mypy` (Cache im Scratch) | no issues in 374 source files | 0 |
| 26 Testdateien ohne Fenster/Renderer/Leistung/`rendered`/Slicer, `-n 6`, gepinnt (die vier Cura-/Druckeinstellungsdateien, Schnittbefunde, Export, Rat, Hersteller, Floß, Schätzung, Profile, `test_translations`, `test_wording`, `test_changelog`, `test_roadmap`, `test_directory_docs`, `test_language_rules`, **`test_text_length`**, Nicht-Fenster-Teil von `test_print_settings_ui`) | 3755 grün, 10 übersprungen | 0 |
| `test_print_settings_ui.py` Fensterteil, je Datei | 328 grün, 126 abgewählt | 0 |
| `test_real_slicers.py -k "contact or cura"`, gepinnt FFFFF0FF | 25 von 25 (Kontakt 8 Programme × 2 + `cura-grid-0.28`, synthetische Messfälle, Cura-Würfel) | 0 |

**Gemessene Fälle gegen das heutige Modell** (`rv628n\probe_now.py`, Teil A, `probe_out\probe_now.json`):
Die 27 Slicerläufe der Erstprüfung (Cura 5.13, OrcaSlicer, Bambu Studio, ElegooSlicer, Creality
Print, Anycubic, PrusaSlicer) neu gerechnet mit `printed_support_gaps(…, roof=, program=)` am
Stand `c9683c3d4`: **27 von 27 treffen die Ringmessung** auf 0,02 mm. Für jeden Cura-Fall
schreibt die Konsole heute dieselben Werte wie bei der Messung (`support_z/top/bottom_distance`,
`support_roof_enable`, `support_structure` gleich), die Messung gilt also für diesen Stand.
Darunter M2 (Baum ohne Trennschicht 0,20 → 0,40, 0,28 → 0,60, 0,40 → 0,60, 0,44 → 0,80; mit
Trennschicht 0,20 → 0,20, 0,28 → 0,40) und L2 (Bambu Studio und Creality Print 0,30 → 0,20,
die übrigen 0,40; 0,18 bei 0,12 → 0,24 überall). Jeder Cura-Feldsatz nennt den gemessenen
Wert: Gitter „unten mit 0,20 mm“ (PLA 0,08: 0,16; PETG 0,12: 0,12), Baum „auf 0,60 mm“, ohne
Trennschicht „Der Stützabstand wird 0,40/0,60/0,80 mm“, Vielfaches mit Trennschicht kein Satz.

**Fensterprofil gegen Konsole** (Teil B, echte Cura-Installation als aktive Maschine, `.curaprofile`
gelesen wie Curas `CuraProfileReader`): In allen zehn Einzelfällen (PETG 0,2/0,28/0,12, PLA 0,08,
Gitter/automatisch/Baum, nur vom Bett, TPU, ohne Stützen) trägt der Container `solidon` dasselbe
`support_bottom_distance` wie `values_for` (0,2; 0,28; 0,2; 0,24; 0,16; 0,2; 0,44; 0,2; 0,2; 0,2).
Zwei Spulen (PLA+PETG, PETG+PLA, 0,30 bei 0,2): `solidon` und `solidon_extruder_0` wie die
Konsole (`write_config`, erste Spule: 0,4 bzw. 0,2), `solidon_extruder_1` im Band seiner Spule.
Curas Import (`CuraContainerRegistry.importProfile:315–343`): Ein einzelner Container wird beim
Import auf das erste Extruderprofil verteilt, jeder Schlüssel mit `settable_per_extruder`;
`support_bottom_distance` gehört dazu wie `support_z_distance` (`fdmprinter.def.json`, kein
`settable_per_extruder: false`), wirkt über `limit_to_extruder` aus dem Stützextruder. Damit
kommt der Wert im Fenster an, wo `support_z_distance` heute schon ankommt.

**Teile auf einer Cura-Platte am echten Cura 5.13** (`rv628n\plate\test_rv628n_plate.py`,
Ender-3 V3 SE, PETG, 0,2 mm, Gitter mit zwei oberen und drei unteren Trennschichten, gepinnt,
7 von 7, `EXIT=0`, G-Codes in `plate\gcode_plate\`; Werte je Teil aus `writer._values_for`
wie der Export, eingelegt in Solidons Netzliste; Messung je Körper im Ring, 11 000 bis 21 000
Stützpunkte je Körper):

| Fall | Teil | geschrieben (top/bottom) | Solidon sagt | gemessen oben/unten |
|---|---|---|---|---|
| Stichprobe Bauagent: Platte 0,2, A will 0,28 | A | 0,2 / – | 0,20/0,20 | 0,20/0,20 |
| | B (Platte) | – | 0,20/0,20 | 0,20/0,20 |
| Stichprobe Bauagent: Platte 0,24, A will 0,44 | A | 0,44 / 0,4 | 0,44/0,40 | 0,44/0,40 |
| | B (Platte) | – | 0,24/0,20 | 0,24/0,20 |
| Drei Teile: Platte 0,28, A 0,24, B 0,44 | A | 0,2 / – | 0,20/0,20 | 0,20/0,20 |
| | B | 0,4 / 0,4 | 0,40/0,40 | 0,40/0,40 |
| | C (Platte) | – | 0,28/0,20 | 0,28/0,20 |
| Drei Teile: Platte 0,28, A 0,48 (gleicher Rest), B 0,24 | A | 0,48 / 0,4 | 0,48/0,40 | 0,48/0,40 |
| | B | 0,2 / – | 0,20/0,20 | 0,20/0,20 |
| | C (Platte) | – | 0,28/0,20 | 0,28/0,20 |
| Baum auf der Platte (0,2), A will 0,28 | A | 0,28 / 0,28 | 0,40/0,40 | 0,40/0,40 |
| | B (Platte) | – | 0,20/0,20 | 0,20/0,20 |
| Gitter auf der Platte (0,2), A will Baum und 0,28 | A | Gitter, 0,2 | 0,20/0,20 (Baum als nicht übernommen) | 0,20/0,20 |
| | B (Platte) | – | 0,20/0,20 | 0,20/0,20 |
| Ganzer Export, Teil ohne eigenen Wert: PETG-Auftrag (Grundlage 0,28), PLA- und PETG-Teil, übernommen 0,2 | PLA-Teil | 0,2 | 0,20/0,20, Befund „Nur für dieses Teil“ | 0,20/0,20 |
| | PETG-Teil (Rücknahme auf 0,28 → 0,2) | 0,2 | kein Befund | 0,20/0,20 |

Jede Zahl, die Solidon nennt, ist die gedruckte. Der PETG-Teil der letzten Zeile druckt still
0,20 statt seiner Grundlage 0,28; Curas Übergabe druckt dort aber ohnehin nur das erste
Filament (`slicer.overrides_unreachable`, `handover.unreachable_overrides`), hier PLA — kein
Fund, siehe „Prüfpunkte ohne Fund“.

**Dialog gegen Export** (`rv628n\probe_dialog.py`, ein Körper mit PETG-Spule in einem
PLA-Auftrag, Abstand aus Solidons PETG-Rat, Gitter): bei 0,08/0,12/0,2/0,28 mm sagen Dialog,
Export und Konsole dasselbe; **bei 0,1 mm sagt der Dialog „unten mit 0,10 mm“, Export-Befund
und Konsole 0,20** (siehe L-a).

**Trennschicht im Fensterprofil** (`rv628n\probe_roof.py`, Bäume, 0,2 mm, PETG, obere
Trennschichten 0 und 2, drei Drucker): Die Konsole bekommt `support_interface_enable`,
`support_roof_enable`, `support_bottom_enable` und die Höhen; **das `.curaprofile` trägt in
keinem der sechs Fälle einen dieser Schlüssel**. Der Feldsatz folgt Solidons Trennschicht
(0: „Der Stützabstand wird 0,40 mm“, 2: kein Satz). Siehe M-a.

**Gegenproben** (`rv628n\mutate.py`, Mutation am Abzug `rv628n\tree` von `c9683c3d4`, nie am
Worktree; je Lauf vier Testdateien gefiltert, 1067 Fälle ohne Fenster, dazu 3 Fenstertests
des Abstandsfelds; gepinnt; `mutations.jsonl`, Logs `mut_*.log`). Grundlauf 1067 + 3 grün; ein
Fall (`test_old_spool_choice_survives_save_reopen_delete_and_undo`) ist im Abzug abgewählt —
dort fehlen die installierten Operationen (`create_box` unbekannt), am Worktree grün.

| Gegenprobe | rot (ohne Fenster / Fenster) |
|---|---|
| G7 Schreiber gibt `setting_limitations` kein Material | 1 / 0 |
| G8 Dialog gibt `limitation` kein Material | 0 / 1 |
| G14 Übergabe wählt unten ohne Materialband | 6 / 0 |
| N1 Fensterprofil ohne `_cura_bottom_gap` | 5 / 0 |
| N2 Extruderprofil unten mit Auftragsmaterial | 1 / 0 |
| N3 Konsole unten mit Auftragsmaterial | 1 / 0 |
| N4 Teilwert unverändert (`exact_on_the_plate` aus) | 4 / 0 |
| N5 Rest der Platte übergangen | 3 / 0 |
| N6 Trennschichtrat entfernt | 4 / 0 |
| N7 ohne Trennschicht keine Schicht mehr (`up`) | 7 / 0 |
| N8 Feldsatz übergeht die Trennschicht | 2 / 0 |
| N9 Gitter-Satz wieder Warnung | 3 / 0 |
| **N10 Teil wählt im Band des Auftrags (`writer.py:1537`)** | **0 / 0** |
| **N11 „für alle Teile“ ohne Material (`writer.py:2635`)** | **0 / 0** |
| N12 Halbfall überall mit Toleranz | 2 / 0 |
| N13 Feldsatz nennt oben statt unten | 7 / 1 |
| N14 Satz unten auch bei „nur vom Bett“ | 1 / 0 |
| N15 Grundlage als Bäume gefragt | 10 / 0 |
| N16 geänderter Teilwert als „nicht übernommen“ | 2 / 0 |
| N17 unter Bäumen unten im Band | 6 / 0 |
| N18 Zusatzschicht nicht gezählt | 6 / 0 |

G7, G8, G14 — im Erstreview grün — sind rot. Grün bleiben nur N10 und N11 (L-e).

## Stand der Funde des Erstreviews

| Fund | Stand | Beleg |
|---|---|---|
| S1 Fenster ohne Unterseite | behoben | Fensterprofil = Konsole in 10 Einzel- und 2 Spulenfällen (Sonde B), Curas Import verteilt den Wert wie `support_z_distance`; Gegenprobe N1 5 rot |
| M1 Teil oben nur mit Plattenrest genau | behoben | 6 Plattenfälle am echten Cura, jede genannte Zahl gedruckt; Gegenproben N4 4, N5 3 rot. Verbesserung möglich: L-b |
| M2 Bäume ohne obere Trennschicht | an der Konsole behoben | 7 gemessene Baumfälle getroffen (Sonde A), Rat schlägt die Trennschicht vor, übernommen gilt wieder „auf“; Gegenproben N6 4, N7 7, N8 2 rot. **Im Fenster nicht: M-a** |
| M3 Materialband ohne Test | behoben | G7 1 rot, G8 1 rot (Fenstertest), G14 6 rot (vorher je 0) |
| L1 Band der Spule | an Übergabe, Konsole und Fenster behoben und geprüft | Gegenproben N2, N3 je 1 rot; je Teil umgesetzt, aber ohne Anschlusstest (L-e); **im Dialog nicht: L-a** |
| L2 Halbfall je Programm | behoben | gemessen Bambu/Creality 0,20, übrige 0,40 (Sonde A) |
| L3 Feldsatz | behoben | „… oben genau und unten mit 0,20 mm, einem Vielfachen der Schichthöhe.“ |
| L4 Warnung ohne Ausweg | behoben | Gitter-Satz `info` ohne Handlung |
| L5 Unterlagen | weitgehend | Regel `dateiformat.md` fehlt (L-c), zwei Sätze zu weit (L-d) |
| RM-624-Patch | richtig übernommen | nur fachliche Teile, keine doppelte Messung, synthetische Fälle aus `0792f679c` unberührt, `cura-grid-0.28` erhalten, 25 von 25 am echten Programm |

## Funde

### M-a (mittel) — Die obere Trennschicht erreicht Curas Fenster nicht; dort gilt M2 nur zufällig

- `app/core/export/handover.py:2122–2131`: `support_interface_enable`, `support_roof_enable`,
  `support_bottom_enable` und die Höhen entstehen nur in `_for_supports`, also im abgeleiteten
  Teil von `values_for` — der Konsole.
- `app/core/export/handover.py:8009–8029`: `cura_profile_beside` schreibt die Einstellungsseite
  samt `_cura_bottom_gap`, die Trennschicht nicht. Sonde `probe_roof.py`: Das `.curaprofile`
  trägt bei 0 und bei 2 oberen Trennschichten keinen der sechs Schlüssel, die Konsole alle.
- Curas Fenster nimmt dann die Vorgabe der aktiven Maschine: `creality_base.def.json:112–113`
  schaltet die Trennschicht ein (vier Schichten), ebenso einige Qualitätsprofile (Anycubic
  Chiron und i3 Mega, UltiMaker 3/S/Factor/Method, Goofoo u. a.); `fdmprinter` lässt sie aus, und
  Sovol, Elegoo, Prusa i3, Flashforge und Voron setzen weder in der Basis noch in den
  Qualitätsprofilen etwas darüber (Installation durchgesehen).
- Folge, gemessen an der Konsole mit derselben Einstellung (Sonde A, `b2.jsonl`): Auf einer
  Maschine ohne Vorgabe übernimmt der Kunde Solidons Rat „obere Trennschicht“ samt 0,20 mm unter
  Bäumen, Solidon sagt nichts mehr (Vielfaches mit Trennschicht), das Fenster druckt ohne sie
  0,40 — über PETGs Höchstwert 0,30, genau der Fall, den M2 beheben sollte. Auf einer
  Creality-Maschine mit 0 Trennschichten nennt der Feldsatz „Der Stützabstand wird 0,40 mm“,
  das Fenster druckt mit Crealitys Trennschicht 0,20.
- Kein Rückschritt gegen welle3 (das Fenster bekam die Trennschicht nie, auch die untere aus
  RM-583 nicht), aber M2 und der zweite Changelog-Punkt hängen an ihr; dieselbe Bauart wie S1.
- **Fix:** Die Trennschicht als Solidons eigene Wahl auf die Einstellungsseite des
  Fensterprofils — Schalter (`support_interface_enable`, `support_roof_enable`,
  `support_bottom_enable`) als Werte, die Höhen als Formel (`=layer_height * N`; Curas Profile
  tragen Formeln, wie die Elegoo-Qualitätsprofile der Installation), damit sie einer Schichthöhe
  folgen, die der Kunde danach in Cura ändert; je Extruderprofil ebenso. Test nach dem Muster
  `test_curas_window_gets_the_bottom_gap_of_the_console`: Das Fensterprofil schaltet die
  Trennschicht wie die Konsole, bei 0 und bei 2.

### L-a (leicht) — Der Druckdialog nennt Curas Abstand unten im Band des Auftrags, Export und Konsole im Band der Spule

- `app/ui/print_settings_dialog.py:6721`: `material=self.session.profile.material`;
  `app/core/export/writer.py:2695–2697` und `handover.py:3699` fragen
  `handover.slot_material(...)` (erste Spule), je Teil `profiles.for_object(...)`.
- Sonde `probe_dialog.py`: PLA-Auftrag, ein Körper mit PETG-Spule, Solidons PETG-Rat 0,14 bei
  0,1 mm, Gitter: Dialog „unten mit 0,10 mm“, Export-Befund „unten mit 0,20 mm“, Konsole schreibt
  `support_bottom_distance=0.2` — genau das Beispiel aus L1 des Erstreviews, nur noch im Dialog.
  Bei 0,08/0,12/0,2/0,28 mm stimmen alle drei überein.
- Dazu zwei Antworten auf „welches Material druckt diese Spule“: `slot_material` nimmt das
  gewählte Filamentprofil (`slot_material_type`), `profiles.for_object` nur die Art der Spule
  (`_material_of_spool`) — `.claude/rules/zwillinge.md`. Gemessene Abweichung daraus keine.
- **Fix:** Dialog und Export fragen eine Funktion für das Material der Platte
  (`handover.slot_material` mit den Spulen der Platte samt gewählten Profilen); Fenstertest:
  PETG-Spule im PLA-Auftrag bei 0,1 mm nennt am Feld 0,20 wie der Export.

### L-b (leicht) — `cura_part_gap` wählt nur Vielfache; mit dem Rest der Platte druckt Cura auch näher am Material

- `app/core/slice/advise.py:1201–1227`: Passt der Rest nicht zur Platte, schreibt die Übergabe
  `whole_layer_gap` — nur Vielfache. Cura druckt aber auch jeden Wert k·Schicht + Rest der
  Platte genau (gemessen: 0,48 auf Platte 0,28 → 0,48; 0,44 auf Platte 0,24 → 0,44).
- Beispiel aus M1: Teil 0,28 (PETG) auf Platte 0,44 → geschrieben und gedruckt 0,20; 0,24
  (= 0,2 + Rest 0,04) druckte genau, liegt im PETG-Band und im `SUPPORT_GAP_BAND` um 0,28
  (0,86), 0,20 nicht (0,71) — vor der Behebung druckte Cura dort 0,24 (Erstreview). Ebenso
  eigener Wert 0,30 auf Platte 0,28: geschrieben 0,20, erreichbar 0,28.
- Reichweite klein: Verschiedene Werte je Teil entstehen bei Cura fast nur mit mehreren
  Materialien, und Curas Übergabe druckt nur das erste Filament.
- **Fix:** In `cura_part_gap` unter den genau druckbaren Werten {k·Schicht} ∪ {k·Schicht +
  Rest der Platte} im Band den nächsten wählen; Tabellentest um 0,28 auf 0,44 → 0,24.

### L-c (leicht) — Die Lehre aus S1 fehlt in `.claude/rules/dateiformat.md`

- Auftrag `auftrag-rm628b.md`, Punkt 2: „Regel in `.claude/rules/dateiformat.md` ergänzen“; der
  landende Diff berührt die Datei nicht. `dateiformat.md:411–417` sagt weiter nur, wohin
  Gerechnetes gehört, nicht dass eine eigene Wahl Solidons für Cura auch auf die
  Einstellungsseite muss — M-a ist derselbe Fehler an der Trennschicht.
- **Fix:** Ein Satz unter „CuraEngine rechnet keine Formeln“: Was Solidon für Cura selbst wählt
  (nicht Curas Formel), gehört auch ins Fensterprofil (`cura_profile_beside`), sonst rechnet das
  Fenster mit der Formel der Maschine — Beispiele `_cura_bottom_gap`, Trennschicht.

### L-d (leicht) — Zwei Sätze in den Unterlagen gehen über das Gemessene hinaus

- `konzepte/begruendungen/regel-druckrat.md:700`: „und unten wählt jedes Teil ebenfalls im Band
  seiner Spule“ — nur ein Teil mit
  eigenem Wert. Sonde C1: Platte 0,3 bei 0,2 mm mit erster Spule PLA (unten 0,4), PETG-Teil ohne
  eigenen Wert → keine Netzwerte, druckt unten 0,4, im eigenen Band wären es 0,2
  (`object_keys` vergleicht beide Seiten mit dem Material des Teils,
  `handover.py:1346–1356`). Mit Curas einem Filament ist 0,4 dort sogar das Richtige.
- `.claude/rules/druckrat.md:133–135`: „Die übrigen runden zur nächsten, wo sie runden (unter
  organischen Bäumen, neben einem Turm); den Halbfall entscheidet dort das Programm“ —
  `HALF_LAYER_UNGUARDED` gilt nur unter organischen Bäumen (`advise.py:1037`), neben dem Turm ist
  nichts gemessen.
- **Fix:** „jedes Teil mit eigenem Wert“; „unter organischen Bäumen entscheidet den Halbfall das
  Programm“.

### L-e (leicht) — Das Material je Teil im Export hat keinen Test am Anschluss

- Gegenproben N10 (`writer.py:1537`, `_part_values` nimmt `profile.material` statt
  `profiles.for_object(...)`) und N11 (`writer.py:2635`, Zweig „für alle Teile“ ohne Material)
  bleiben grün. `test_a_part_chooses_its_cura_bottom_gap_in_the_band_of_its_spool` ruft
  `writer._values_for` und `object_keys` mit fertigem Material; der Exporttest
  `test_the_cura_export_says_the_bottom_gap_of_the_printing_spool` hat nur ein Teil, also keinen
  Split. `AGENTS.md`, Testart „Anschluss“.
- Beobachtbar wird die Zeile nur, wo ein Teilwert vom Plattenwert abweicht und das Band
  entscheidet, etwa: PLA-Auftrag bei 0,1 mm mit eigener Wahl 0,14, das PLA-Teil übernimmt seinen
  Rat 0,1 (Platte 0,1), das PETG-Teil ohne eigenen Rat bekommt die Grundlage 0,14 zurück →
  `cura_part_gap` im PETG-Band 0,2 je Netz, im PLA-Band 0,1 (gleich der Platte, kein Netzwert).
- **Fix:** Diesen Fall als Exporttest durch `write_assembly` (zwei Körper, zwei Spulen). Ob bei
  Cura überhaupt das Band der Teilspule gelten soll, wo die Übergabe nur das erste Filament druckt
  (`unreachable_overrides`), ist dabei mitzuentscheiden; der Teilrat selbst fragt heute mit der
  Teilspule (`slot_processes`), die Wahl ist also in sich stimmig.

## Prüfpunkte ohne Fund

- **Rundungsmodell:** 27 von 27 Messfällen der Erstprüfung getroffen, die Cura-Werte der Konsole
  unverändert gegen die Messung; Feldsätze nennen jeweils den gemessenen Wert.
- **Je Teil (M1):** sechs Plattenfälle am echten Cura, darunter drei Teile mit drei Werten,
  gleicher Rest wie die Platte (0,48 auf 0,28 genau), Baum auf der Platte (Teil 0,28 → 0,40
  oben und unten, wie gesagt), Gitterplatte mit Baumwunsch (Teil bekommt Gitter, „Baum“ als
  nicht übernommen gemeldet), und der ganze Export mit einem Teil ohne eigenen Wert. Die
  Rücknahme des PETG-Teils auf 0,2 bleibt ohne Befund; Curas Übergabe druckt aber nur das erste
  Filament (`unreachable_overrides`, Befund `slicer.overrides_unreachable` im selben Lauf), hier
  PLA, für das 0,2 der Rat ist. Kein Fund.
- **M2 an der Konsole:** Rat schlägt die Trennschicht nur vor, wo sie fehlt (flache Decke: der
  Deckenrat mit drei Lagen; sonst `up_and_one` mit zwei); der Abstandsrat zielt auf den Wert
  mit Trennschicht, nicht eine Schicht tiefer — übernimmt der Kunde beides, gilt wieder „auf“
  (gemessen 0,20 → 0,20, 0,28 → 0,40); übernimmt er nur den Abstand, nennt der Feldsatz die
  Schicht mehr. Grundtext „Ohne obere Trennschicht lässt Cura eine Schicht mehr Luft.“ und
  Feldsatz stimmen mit der Messung; fünf Kataloge übersetzt; Hybrid und „automatisch“ gehen an
  Cura als `normal` (`slicer_keys.py:650`), und `gap_rounding` behandelt sie wie Gitter.
- **Kontakttest (L-Punkte, RM-624):** `"cura"` in `_CONTACT_PROGRAMS`, Sollwerte aus
  `printed_support_gaps` (oben/unten je Programm), Feldsatzprüfung für Cura über `values`, zwei
  obere Trennschichten gesetzt (sonst gälte `up_and_one`), `cura-grid-0.28` erhalten; die eigene
  Cura-Messung (`_cura_support_gaps` & Co.) ist fort, `tests/gcode_contact.py` und die
  synthetischen Fälle aus `0792f679c` sind gegen welle3 unverändert. 25 von 25 am echten
  Programm.
- **Register und Archiv:** RM-628 aus Tabelle und Block von `ROADMAP.md` entfernt, keine
  verwaisten Verweise; Archiv mit Verzeichniszeile, beiden Ankern, Nacharbeit; RM-624-Satz
  nachgezogen (`[RM-628](#rm-628)` trifft). `test_roadmap` grün.
- **Changelog:** zwei Punkte in sechs Sprachen an gleicher Stelle, 120–195 Zeichen (DE 159/120,
  EN 160/122, ES 180/135, FR 195/143, IT 180/149, PT 185/142); Ursache `fafcd4841` in keinem Tag
  (`git tag --contains` leer, letzter Tag v0.5.3) → Eigenschaft richtig. An der Konsole wahr;
  der zweite Punkt („schlägt eine obere Trennschicht vor“) wirkt im Fenster nicht (M-a).
- **Regeln 1–22 im Umfang:** kein Qt unter `core`, Fließkomma über `is_close`/`EPS_GEOM`, Texte
  über `_()`, fünf Kataloge, englische Bezeichner, keine Abhängigkeit, kein Dialog, Befunde mit
  Schwere und (wo Handlung) Vorschlag; `test_text_length` grün. Gebündelt rechnen: Skalarrechnung
  je Übergabe, nicht betroffen.
- **Vorgaben an den Bauagenten:** RM-624-Patch nur fachlich, Tautologie in
  `test_slice_findings.py` (vorher `:1574`) ersetzt durch eine Prüfung mit allen übernommenen
  Vorschlägen; einzig die Regel in `dateiformat.md` fehlt (L-c).

## Kundensicht

Vorher (welle3): Cura-Kunde mit PETG bekam unter Gitter 0,2 geraten (schweißt an), unten
druckte Cura aufgerundet, der Satz am Feld sprach von ganzen Schichten zu 0,20. Jetzt an der
Konsole: oben der Wert des Materials, unten ein Vielfaches im Band, der Satz nennt beide richtig,
unter Bäumen ohne Trennschicht kommt ein Rat mit verständlichem Grund; die Unterseite stimmt
auch im Fenster. Offen aus Kundensicht: Im Fenster verpufft der Trennschichtrat auf Maschinen
ohne Werksvorgabe (M-a), und bei 0,1 mm nennt der Dialog für eine PETG-Spule im PLA-Auftrag eine
andere Zahl als der Prüfbericht (L-a). Neue Texte sind kurz und sprechen Kundenwörter
(„Stützabstand“, „Trennschicht“, „Vielfaches der Schichthöhe“).

## Läufe

| Lauf | Ergebnis | Exit |
|---|---|---|
| ruff check / ruff format --check / mypy | grün | 0 / 0 / 0 |
| 26 Testdateien ohne Fenster, `-n 6`, gepinnt | 3755 grün, 10 übersprungen | 0 |
| `test_print_settings_ui.py` Fensterteil | 328 grün | 0 |
| `test_real_slicers.py -k "contact or cura"`, gepinnt | 25 von 25 | 0 |
| Rechensonde `probe_now.py` (Messfälle, Fenster, Teile) | geschrieben `probe_out\probe_now.json` | 0 |
| Plattensonde Cura 5.13, gepinnt | 7 von 7 | 0 |
| `probe_roof.py`, `probe_dialog.py` | geschrieben | 0 / 0 |
| Gegenproben, 21 Mutationen + Grundlauf, gepinnt | Tabelle oben | 0 |

`git status` im Worktree nach allen Läufen leer.

## Urteil

**Nicht — aber nah.** S1, M1, M3, L1–L5 und der RM-624-Patch sind behoben und am echten Cura
belegt: 27 Messfälle, 7 Plattenläufe, 25 Slicertests, alle Tore grün, G7/G8/G14 jetzt rot. Es
fehlt M-a: Die obere Trennschicht, an der M2 hängt, erreicht Curas Fenster nicht; dort druckt
eine Maschine ohne Werksvorgabe unter Bäumen weiter eine Schicht mehr, als Solidon sagt
(PETG 0,40 über dem Höchstwert), und der neue Trennschichtrat wirkt nicht — dieselbe Bauart wie
S1. Nach M-a mit Test (und L-c im selben Zug, L-a, L-b, L-d, L-e nach Wahl) kann der Zweig
landen; eine volle Nachprüfung braucht es dann nicht (ein mittlerer Fund), eine Durchsicht der
M-a-Änderung genügt.
