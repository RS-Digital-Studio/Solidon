# Review rvtun: Gitter neben der Stützsperre geht als `snug` (fix/tunnel-gitter)

Gegenstand: Zweig `fix/tunnel-gitter`, Spitze `d3abc9ae9` (welle4 `4c135723a` drin), Worktree
`F:\sl-tunnel` (nur gelesen). Eigener Diff `git diff origin/welle4...d3abc9ae9`: Fix
`dc8a2b4ff`, Slicertest `ee2ad829e`, Karte `48071888c`. Bericht des Bauagenten
`berichte-2026-10-10\rmtun.md`, Anlass `review_rm629_nach.md` („Neuer Punkt außerhalb RM-629“).

Sonden laufen aus ausgepackten Bäumen (`git archive`): `fin` = `d3abc9ae9`, `w4` = `4c135723a`
unter `F:\tmp-agenten\rvtun\`; in `app/` unterscheiden sich nur `handover.py`, `writer.py` und
die Karte. Scratch `…\78c2d72e-…\scratchpad\rvtun\`. Slicer gepinnt `FFFFF0FF`.

Stand: abgeschlossen (11.10.). Alle Läufe fertig, Exit 0 bis auf die erwarteten Roten (alter
Code mit neuen Tests; vier Git-Tests im ausgepackten Baum, im Worktree grün).

## Urteil

**Kann landen mit Fund 1 samt Testfall, ohne ihn nicht.** Der Fix tut für die Hauptwege, was er
sagt: Elegoo CC2 und PrusaSlicer am Becher schräg 20° mit Gitter und Sperre 1,90 → 0,01 bzw.
0,76 → 0,01 m Stütze im Tunnel, Deckel 100/100 %, Kontakt (Abstand, Trennschichten) gleich,
Druckzeit 2–5 % kürzer; Creality K1 gedreht gemessen Deckel 100/100 %; Unit- und Slicertest am
alten Code rot (2 bzw. 2), am Fix grün; Drache, Eiffelturm (Elegoo) und Waschschüssel inhaltsgleich
übergeben; gezielte Tests samt Pflichtliste, ruff, format, mypy grün; keine Abdruckdatei des
Bereichsnachweises berührt; mergt ohne Überschneidung auf das inzwischen weitere welle4
`1ec8d5eee`. Unvollständig ist er dort, wo der Herstellerprozess einen Baumstil führt: Die
Orca-Familie druckt einen Baumstil unter normaler Stütze als Gitter, der Fix schreibt dort kein
`snug` — OrcaSlicer mit Prusa XL, Vorschläge übernommen, 1,14 m im Tunnel (Fund 1, mittel,
eine Zeile, gegengeprüft). Fund 2 bis 7 sind leicht und gehören in denselben Zug; Fund 2 (die
Zweige „automatisch“ und Ersatzart hält kein Test) liefert den Testfall zu Fund 1 gleich mit.
**Nachprüfung:** nicht nötig, wenn Fund 1 wortgleich mit Testfall übernommen wird; anders
gebaut, die Sonde `test_rvtun_becher.py` für `orcaslicer-prusa-xl` nachfahren (Soll: `snug` in
der Datei, Tunnel ≤ 0,05 m, Deckel 100 %).

## Funde

### 1. mittel — Ein Baumstil des Herstellers unter Gitter bekommt kein `snug`, und das Raster bleibt im Tunnel

`app/core/export/handover.py:3636–3637` (dazu `_RASTER_STYLES` `:3599–3602`): In der
Orca-Familie schreibt der Fix `snug` nur, wenn `support_style` des Herstellerprozesses `""`,
`default` oder `grid` ist. Solidons Gitter schreibt aber `support_type = normal(auto)` und lässt
den Stil des Herstellers stehen, und OrcaSlicer, Anycubic Slicer Next und Bambu Studio machen
aus jedem Baumstil unter normaler Stütze Gitter (`SupportParameters.hpp`: `tree_slim`,
`tree_strong`, `tree_hybrid`, `organic` und `!is_tree(support_type)` → `smsDefault` →
`smsGrid`). Herstellerprozesse mit Baumstil: Prusa XL in OrcaSlicer, ElegooSlicer und Creality
Print (`process_common_xl`: `tree(auto)`, `organic`; Prusa XL steht in Solidons Druckerliste),
CoLiDo SR1, Creality Sermoon V1, LH Stinger, in Anycubic Slicer Next Kobra 2 Max / Kobra 1 Max.
Dort schlägt RM-584 Gitter vor („automatisch“ sind Bäume), und das Raster läuft wie vor dem Fix
in den gesperrten Tunnel.

Beleg: Matrix `orca:prusa-xl`, Becher schräg 20°, Fix-Stand, Vorschläge übernommen: Rat Gitter
und Kanäle sperren, Übergabe ohne `snug`, **1,14 m Stütze im Tunnel** (`mess_matrix_xl.txt`).
Sonde mit gewähltem Gitter: 1,06 m an welle4 und am Fix gleich (`mess_w4_grid.txt`,
`mess_fin_grid.txt`).

Fix (gegengeprüft im Baum `fix2`, Sonde OrcaSlicer Prusa XL: `snug` in der Datei, Tunnel
1,06 → 0,01 m, Deckel 100 %, Simsdecke 38,6 % wie bei den übrigen, `mess_fix2_grid.txt`):

```
return {} if native_style == "snug" else {"support_style": "snug"}
```

Dazu Docstring und Kommentar an `_RASTER_STYLES` („unter normaler Stütze wird jeder Baumstil
Gitter“; die Konstante fällt dann weg oder gilt nur noch PrusaSlicer), Begründung („Herstellerprozess
mit normaler Stütze im Rasterstil“ → „mit normaler Stütze, außer `snug`“) und ein Testfall
(Fund 2). Wer es ganz einfach will: unter normaler Stütze immer `snug` schreiben — beim
Herstellerstil `snug` ändert das nichts, und es deckt auch den Fall, dass die Platte selbst
einen Baumstil schreibt (Hybrid an der Platte, Gitter am Teil).

### 2. leicht — Die Zweige „automatisch“ und Ersatzart hält kein Test

`handover.py:3624–3633` und `:3640–3645`; `tests/test_export.py:5201–5239` prüft nur Gitter und
Baum ohne Slicer (`setup=None`). Summenmutante (keine Ersatzart über `slicer_keys.substitute`,
„automatisch“ in beiden Familien nie `snug`): **1608 passed, Exit 0** über `test_export`,
`test_print_settings`, `test_real_slicers` (ohne Slicer), `test_slicer_part_settings`,
`test_manufacturer`, `test_threemf_assembly`, `test_export_readback` (`mutante.txt`). Gerade
„automatisch“ über normaler Stütze ist der Fall, den es schon in 0.5.x gab (OrcaSlicer Kobra 2,
Creality K1). Fix: ein parametrisierter Unit-Test wie `test_organic_trees_are_known_per_program`
(`monkeypatch` auf `handover._native_process` bzw. `manufacturer.prusa_chain`): Orca Gitter mit
`{}` → snug, mit `organic`/`tree(auto)` → snug (Fund 1), mit `snug` → nichts; „automatisch“ mit
`normal(auto)` → snug, mit `tree(auto)` → nichts; Baum und Hybrid → nichts; Prusa „automatisch“
mit Kette `grid` und ohne Kette → snug, mit `organic`/`snug` → nichts; SuperSlicer Baum und
PrusaSlicer Hybrid → snug; Cura → nichts.

### 3. leicht — Der Herstellerprozess wird je Teil außerhalb des Lesedurchgangs aufgelöst

`app/core/export/writer.py:2866–2873`: `snug_beside_blocker` ruft `_native_process` je Teil mit
Sperre, nach dem Block `with slicer_profiles.single_read()` (`:2599–2623`); der Schneidefaden
(`_SliceWorker` → `_prepare_plate`) legt keinen äußeren Durchgang darum. Gemessen
(`kosten_snug.py`, ElegooSlicer CC2): 31–78 ms CPU je Aufruf außerhalb, 0–16 ms innerhalb
eines Durchgangs. Muster RM-670/RM-622 (`_tower_causes`: „je Platte neu aufgelöst 39 ms“).
Fix: die `snug`-Werte im vorhandenen Durchgang je Teil mitrechnen (die Art steht in
`part_values[...].effective`), oder die Sperrschleife in `single_read()` legen.

### 4. leicht — Zwei Herleitungen derselben Auskunft „was druckt automatisch“

`handover.py:3641–3643` wiederholt wörtlich die Prusa-Herleitung aus `tree_styles`
(`:3763–3764`: Stil der Kette, sonst `prusa_defaults`); für die Orca-Familie fragt der Fix
`support_type.startswith("normal")`, während `manufacturer.auto_prints_trees` „die eine Auskunft
für Zeitmodell und Rat“ ist. Mit Fund 1 kommt die Regel „Baumstil unter normaler Stütze ist
Gitter“ als dritte Stelle dazu. Regel `zwillinge.md` (ungewollt → zusammenlegen). Fix: eine
Hilfsfunktion für den Prusa-Stil unter „automatisch“, von `tree_styles` und
`snug_beside_blocker` gefragt; für Orca `auto_prints_trees` statt eigener Präfixprüfung.

### 5. leicht — Der Dialog sagt Gitter, die Datei schreibt `snug`, und kein Satz erklärt es

Der Druckdialog zeigt für das Teil weiter „Gitter“ (Vorschlag RM-584 oder eigene Wahl,
`surfaces.py:289`), die Übergabe trägt am Teil `support_style`/`support_material_style` =
`snug`; `export.support_blocker` (`writer.py:2091–2097`) nennt nur die Sperre. Wer *Im Slicer
öffnen* nimmt, sieht am Objekt „Snug“, das Solidon nie nannte. Vorbild: Ersatzarten gehen mit
Hinweis hinaus (`substituted_choices`, RM-480), und der Dialog soll zeigen, was gedruckt wird
(Entscheidung H, `tree_over_hybrid`). In der Sache ist `snug` dieselbe normale Stütze (Deckel
100 %, Kontakt gleich), deshalb nur leicht. Fix: ein Halbsatz im Befund, wo `snug` geschrieben
wird, etwa „Gitter liegt dort eng am Überhang an.“ — fünf Kataloge und `test_text_length.py`
mitfahren.

### 6. leicht — „Sims gleich abgedeckt“ gilt nur am Stand mit RM-629, und RM-629 ist nicht in welle4

Docstring `handover.py:3618–3620` („bei derselben Abdeckung des Simses daneben (98,5 und
98,8 %)“) und Begründung `regel-dateiformat.md` (+„Deckel und Sims gleich abgedeckt“) sind am
RM-629-Stand gemessen. `git merge-base --is-ancestor origin/einstellungen/schacht-rm629
origin/welle4` ist falsch. Am Stand, auf dem der Fix landet, sinkt die Simsdecke des schrägen
Bechers: Elegoo 46,2 → 39,2 %, PrusaSlicer 65,2 → 38,0 %, Creality K1 (gedreht) 64,8 → 38,6 %
(`mess_*_grid.txt`, `cr_gedreht.txt`). Ursache ist RM-629 (der Sims liegt zu 65 % im
Sperrkörper); Gitter lief über die Sperre hinaus und stützte zufällig mit, `snug` hält sie. Der
Fix macht also jede zu große Sperre wirksamer. Fix: in Docstring und Begründung den Stand nennen
(„am Stand mit RM-629; wo die Sperre einen Überhang zu Unrecht deckt, fällt die zufällige
Gitterstütze weg“); RM-629 in derselben Welle landen lassen, sonst sinkt die Simsstütze dieses
Bechers mit dem Fix.

### 7. leicht — Changelog: für Orca und Creality mit „automatisch“ lag die Ursache in einem Tag

„Kein Punkt“ stützt sich auf `55236d39c`: `git tag --contains` ist leer (nachgeprüft, 0 Tags).
Für OrcaSlicer Kobra 2 und Creality K1 („automatisch“ über normaler Stütze) gab es Sperre und
Raster schon in v0.5.3 (`_support_blocker` in `v0.5.3:app/core/export/writer.py`), und die
Stütze in den Mündungen sieht der Kunde in der Vorschau (Creality K1 am Stand welle4, Bericht
0,94 → 0,01 m, meine gröbere gedrehte Rechteckprüfung 1,76 → 0,12 m). Die Begründung des
Bauagenten (an der Außenstütze befestigt, mit ihr
entfernt) ist vertretbar; nach der Regel „Behebung, wenn die Ursache in einem Tag lag“ passt aber
eine eigene Zeile, etwa „*Kanäle frei halten* hält jetzt auch Gitterstützen aus den Mündungen
der Kanäle.“ Entscheidung des Koordinators; ohne Zeile genügt ein Satz im Archiv, warum nicht.

## Zu den Fragen des Auftrags

1. **Welche Teile bekommen `snug`:** Teile mit Sperre (`blockers[...] is not None`, nur bei
   `for_slicer`), die Gitter drucken — Orca-Familie bei Gitter oder „automatisch“ über
   `normal(…)`, sofern der Herstellerstil `""`/`default`/`grid` ist (Lücke: Fund 1);
   PrusaSlicer bei Gitter, Hybrid (Ersatz Gitter) und „automatisch“ über `grid` oder ohne Kette;
   SuperSlicer auch bei Baum und Hybrid (Ersatz Gitter). Nie: ohne Sperre (Code und Test), Baum
   und Hybrid in der Orca-Familie, Baum in PrusaSlicer, Cura (früher Ausgang `as_stl`, Curas
   Fenster über `_cura_window`, und `{}` für jede andere Familie). Belegt am Korpus: Drache,
   Eiffelturm (Elegoo, Bäume mit Sperre) und Waschschüssel (Hybrid mit Kanal- und Randsperre)
   inhaltsgleich. **Gelesen** wird der Objektwert von ElegooSlicer, OrcaSlicer, PrusaSlicer
   (eigene Läufe), Bambu Studio, Anycubic Slicer Next (Slicertest des Bauagenten), Creality Print
   (Matrix, gedreht nachgemessen) und SuperSlicer (Stütze 84 → 51 m, Bericht). **Gespeicherte
   3MF:** nein — `snug` entsteht nur im Zweig der Sperre unter `for_slicer`; der Dateiexport
   (`main_window.py:2063`, `for_slicer=False`) bekommt weder Sperre noch `snug`, *Im Slicer
   öffnen* beides. Passt zu `dateiformat.md`.
2. **Kundensicht:** Deckel 100 % vor und nach (Elegoo, PrusaSlicer, Orca Prusa XL mit Fix 1,
   Creality K1 gedreht); Sims siehe Fund 6. Lösen: Abstand oben 0,2 mm und Trennschichten gleich,
   Kontaktzellen −0,3 bis −2,3 %. Druckzeit laut Slicer kürzer: Elegoo 3:16:26 → 3:07:35,
   PrusaSlicer 2:59:59 → 2:55:43, Orca Prusa XL 3:43:37 → 3:37:39. Widerspruch Zeile ↔ Datei:
   ja, ohne Satz (Fund 5).
3. **Selbst nachgestellt:** ElegooSlicer CC2, PrusaSlicer MK4S, OrcaSlicer Prusa XL und Kobra 2,
   Becher schräg 20°, gepinnt, beide Stände (Tabelle im Verlauf); Matrix OrcaSlicer Prusa XL
   (Fund 1). Gegenfall: Korpusübergaben inhaltsgleich (Verlauf).
4. **Tests:** Unit- und Slicertest am alten Code rot, am Fix grün (Verlauf). Gezielte Auswahl
   (30 Dateien des Gebiets, `affected_tests` meldet „das ist die Suite“) samt Pflichtliste der
   Baumleser mit `test_value_labels`, `test_directory_docs`, `test_translations`,
   `test_wording`, `test_slicer_selection`: **6922 passed, 10 skipped, 4 failed, Exit 1** — die
   vier rot nur, weil der ausgepackte Baum kein Git-Klon ist (`git … exit status 128`,
   `hooks_are_wired` → `None`); dieselben vier im Worktree `F:\sl-tunnel`: **4 passed, Exit 0**,
   `git status` davor und danach leer. mypy 377 Dateien Exit 0. Abdruckdateien des
   Bereichsnachweises: keine Datei im Diff gegen welle4. Regel, Begründung, Karten knapp und
   richtig bis auf Fund 1 (Begründung) und Fund 6; die gekürzte Klammer in `dateiformat.md`
   steht vollständig in der Begründung (`regel-dateiformat.md:63–64`). Changelog: Fund 7.

## Zum Bericht des Bauagenten

- „Schlitz 45° 22 mm: … Deckel überall 100 % vor und nach“: für Creality Print steht in
  `messung_schlitz.txt` 40,0 → 28,8 %, ungedreht gemessen (`deckel.py` dreht nicht); der
  Vorher-Lauf dort heißt `becher_schlitz45_22_ungueltig` und ist mit dem Nachher-Lauf identisch.
  Am schrägen Becher habe ich Creality gedreht nachgemessen: Deckel 100/100 % stimmt.
- Neuer Punkt des Bauagenten „Hybrid neben einer Sperre nicht gemessen“ bleibt offen.

## Neue Punkte (Vorschlag, keine Nummer vergeben)

- Fund 1, falls nicht in diesem Zweig behoben.
- Jede zu große Sperre kostet mit `snug` die zufällige Gitterstütze daneben (Fund 6); ein
  Korpuslauf Sperre gegen Stützabdeckung (`gcode_stuetzen.py`) unter Gitter wäre der Nachweis.

## Verlauf

- Auftrag, Bericht rmtun, Anlass gelesen; Diff ganz gelesen (app, Regel, Begründung, Karten,
  Tests).
- 04:40 Eigene Sonde `test_rvtun_becher.py` (Weg des Slicertests: `_prepare_plate`,
  `slice_model`; Gitter, überall, Kanäle sperren gewählt), Becher schräg 20° Ø 34, gepinnt,
  je Stand; Messung `miss_becher.py` mit `support_in_box` des Fix-Stands (Tunnel x 20…28,
  y −8…8, z 4…20), Deckel und Simsdecke wie im Bericht (oberste Stützlage, 0,5 mm aufgeweitet).
  Läufe Exit 0 (4 passed je Stand), Messung Exit 0 (`mess_w4_grid.txt`, `mess_fin_grid.txt`):

| Programm (Drucker, Prozess) | snug in der Datei w4/fin | Tunnel w4 → fin | Deckel w4/fin | Simsdecke w4/fin | Stütze w4/fin |
|---|---|---|---|---|---|
| ElegooSlicer (CC2, 0.20mm Standard) | nein/ja | 1,90 → 0,01 m | 100/100 % | 46,2/39,2 % | 552/527 m |
| PrusaSlicer (MK4S, 0.20mm SPEED) | nein/ja | 0,76 → 0,01 m | 100/100 % | 65,2/38,0 % | 248/233 m |
| OrcaSlicer (Prusa XL, 0.20mm Speed, `organic`) | nein/**nein** | **1,06 → 1,06 m** | 100/100 % | 54,5/54,5 % | 267,5/267,5 m |
| OrcaSlicer (Kobra 2, 0.20mm Standard) | nein/ja | 0,00 → 0,00 m | 6,3/4,1 % | 22,0/16,6 % | 83/45 m |

  Kobra 2 ohne übernommenen Stützwinkel stützt den Deckel in keinem Stand (eigene Grenze des
  Prozesses); in der Matrix mit Vorschlägen 100/100 % (Bericht). Die Simsdecke sinkt, weil der
  Sims am Stand welle4 ohne RM-629 zu 65 % im Sperrkörper liegt und `snug` die Sperre hält,
  Gitter lief darüber hinaus (Erklärung des Berichts, hier bestätigt: 38–39 % ≈ freier Anteil).
- 04:50 Quelltext OrcaSlicer, Anycubic Slicer Next und Bambu Studio
  (`src/libslic3r/Support/SupportParameters.hpp`, über `gh api`, in
  `F:\tmp-agenten\rvtun\quellen\`): Ein Baumstil (`tree_slim`, `tree_strong`, `tree_hybrid`,
  `organic`) unter normaler Stützart wird `smsDefault` und damit `smsGrid` (GitHub-Stand; am
installierten OrcaSlicer durch die Sonde mit Prusa XL bestätigt). Herstellerprozesse
  mit Baumstil: Prusa XL in OrcaSlicer, ElegooSlicer und Creality Print 7.2
  (`process_common_xl`: `tree(auto)`, `organic`), CoLiDo SR1 (`tree_hybrid`), Creality
  Sermoon V1 (`tree_slim`), LH Stinger; Anycubic Slicer Next Kobra 2 Max / Kobra 1 Max
  (`organic`); Bambu Studio keiner (nur `support_recommended_params.json` eines Filaments).
  Daraus Fund 1.
- Matrix `orca:prusa-xl`, Becher schräg 20°, Fix-Stand (`matrix_fin_orca_prusa-xl`, Exit 0):
  Rat `support.style` = `grid` und `support.block_channels`; die Übergabe schreibt am Teil
  `support_type normal(auto)`, `support_base_pattern rectilinear-grid`, Platte `tree(auto)`/
  `organic`, **kein `snug`**; Stütze im Tunnel (Vorschläge übernommen) **1,14 m**, Deckel
  100 %, Simsdecke 54,5 % (`mess_matrix_xl.txt`).
- Gegenprobe Fix 1 (Baum `fix2` = `d3abc9ae9` mit
  `return {} if native_style == "snug" else {"support_style": "snug"}`), Sonde wie oben,
  OrcaSlicer Prusa XL, Gitter: `snug` in der Datei, Tunnel **1,06 → 0,01 m**, Deckel 100 %,
  Simsdecke 38,6 %, Stütze 267,5 → 248,0 m (`mess_fix2_grid.txt`, Lauf Exit 0).
- Lösbarkeit, soweit der G-Code sie zeigt (`support_contact`, `inset` 2 mm, `kontakt.txt`):
  Gitter und `snug` gleich — oben 0,2 mm und 3 Trennschichten (Elegoo, Prusa) bzw. 6 (Orca
  Prusa XL), unten gleich; Kontaktzellen oben −0,3 bis −2,3 %. Druckzeit: Stützbahn −4,6 %
  (Elegoo) bzw. −6,2 % (Prusa), also etwas kürzer.
- Korpus, Übergaben des Bauagenten vorher/nachher je Eintrag verglichen
  (`vergleich_3mf.py`, `vergleich_korpus.txt`): Drache (Elegoo, alle drei Varianten),
  Eiffelturm (Elegoo drei, Orca Kobra 2 standard und stuetzen_auto), Waschschüssel (Elegoo
  drei) **inhaltsgleich**; einziger Unterschied Eiffelturm Orca Kobra 2 mit Vorschlägen: genau
  die Zeile `support_style = snug` in `model_settings.config` und `Slic3r_PE_model.config`.
- Unit-Test, alter Code mit neuen Tests (Baum `w4t` = welle4 + Tests des Fixes):
  `-k hugs_the_overhang` **2 failed, 4 passed, Exit 1** (genau die beiden snug-Fälle); am
  Fix-Stand **6 passed, Exit 0**.
- Slicertest `test_grid_support_stays_out_of_a_blocked_channel`, ElegooSlicer und
  PrusaSlicer, gepinnt: `w4t` **2 failed, Exit 1** (1025 bzw. 544 mm im Tunnel, dieselben
  Zahlen wie im Bericht), Fix-Stand **2 passed, Exit 0** (`slicertest_*.txt`).
- Summenmutante (`mut`: keine Ersatzart über `slicer_keys.substitute`, „automatisch“ in
  beiden Familien nie `snug`) gegen `test_export`, `test_print_settings`,
  `test_real_slicers` (ohne Slicer), `test_slicer_part_settings`, `test_manufacturer`,
  `test_threemf_assembly`, `test_export_readback`: **1608 passed, 4 skipped, Exit 0** — kein
  Test hält diese Zweige (Fund 2).
- Kosten je Teil (`kosten_snug.py`, ElegooSlicer CC2, gepinnt, Exit 0):
  `snug_beside_blocker` außerhalb eines Lesedurchgangs 31–78 ms CPU (55–81 ms Wanduhr) je
  Aufruf, innerhalb nach dem ersten 0–16 ms CPU (2–4 ms). `write_assembly` ruft es je Teil
  mit Sperre außerhalb von `single_read()` (Fund 3).
- ruff check (fünf Dateien) Exit 0, ruff format --check (neun Dateien) Exit 0.
- Creality Print K1, G-Codes der Matrix des Bauagenten (schräg 20°, Vorschläge), gedreht
  gemessen (`deckel_gedreht.py`: Drehung aus den Wandbahnen bei z 10 gegen den Körperschnitt;
  Kontrolle ElegooSlicer ungedreht: 359,40°, Deckel 100 %, Simsdecke 46,2 % wie
  `miss_becher.py`), `cr_gedreht.txt`, Exit 0: Drehung 144,95°, Deckel **100/100 %**,
  Simsdecke 64,8 → 38,6 %, Tunnel 1,76 → 0,12 m (Rechteckprüfung der gedrehten Mitten, gröber
  als `support_in_box`).
- Gezielte Auswahl und Pflichtliste (`tests_auswahl.sh`, `-n 6`, ohne Fenster, Renderer,
  Leistung, Slicer) im Baum `fin`: **6922 passed, 10 skipped, 4 failed, Exit 1**
  (`tests_fin.txt`); rot nur `test_toolchain` (drei Hook-Tests) und
  `test_memories_stay_out_of_the_repository`, alle mit `git … exit status 128` bzw.
  `hooks_are_wired() is None` im ausgepackten Baum. Dieselben vier im Worktree `F:\sl-tunnel`
  (nur lesend: ohne Cache und Bytecode, Temp außerhalb): **4 passed, Exit 0**; `git status
  --short` davor und danach leer (`git4*.txt`).
- mypy (Baum `fin`, Cache außerhalb): **377 Dateien, Exit 0** (`mypy.txt`).
- welle4 ist während des Reviews auf `1ec8d5eee` gegangen (Merge fix/agent-nachtrag: Backends,
  Kataloge, `dialogs.py`, `test_wording.py`, `test_backends.py`). Keine Datei überschneidet
  sich mit dem Zweig; `git merge-tree --write-tree 1ec8d5eee d3abc9ae9` Exit 0 ohne Konflikt
  (schreibt nur unreferenzierte Objekte, keine Referenz).
