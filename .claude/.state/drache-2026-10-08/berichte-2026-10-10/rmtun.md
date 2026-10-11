# rmtun: Stütze im gesperrten Tunnel unter Gitter

Zweig `fix/tunnel-gitter` (Worktree `F:\sl-tunnel`, von origin/welle4 `3d782213e`, welle4
`a72079433` hineingemergt). Scratch `…\78c2d72e-…\scratchpad\rmtun\` und ab dem Hinweis zu C:
`F:\tmp-agenten\rmtun\` (Matrixläufe, Slicerausgaben, Sonden).

## Ursache

Solidon sperrt den Tunnel: Der Sperrkörper der Übergabe deckt das Rechteck des Tunnels auf jeder
Höhe ganz (`deckung.py`, frei 0,00 mm²). Die Sperre der Orca-Familie und von PrusaSlicer nimmt aber
nur die **Überhangfläche** in ihr aus. Unter dem Deckel des Bechers (große flache Decke, der Grund
für „Gitter“) stehen Säulen bis zum Boden, auch vor den Tunnelmündungen. Im Gitterstil legen die
Programme jede Säule auf ein Raster (`SupportGridPattern`) und schneiden sie danach nur am Modell
zu; das Raster ragt 1,1 mm in beide Mündungen, von der Sohle bis zur Decke (je Schicht ~15 mm Bahn
bei y ±6,88…±8,0, `segmente.py`). Mit „auto“ druckten Elegoo und Bambu Bäume, die das nicht tun —
deshalb 0,00 m vor RM-584. Dieselbe Ursache trifft „automatisch“ über einem Herstellerprozess mit
normaler Stütze (OrcaSlicer Kobra 2, Creality K1), dort schon vor 0.6.0.

Varianten an derselben Übergabe (ElegooSlicer CC2, `objekt_variante.py`): wie geliefert 1,08 m;
`support_style=snug` 0,01; `support_base_pattern` des Herstellers 1,44; Baum 0,00; ohne Sperre
1,15 (die Sperre trägt unter Gitter fast nichts zum freien Tunnel bei — es ist das Raster).

## Fix

`handover.snug_beside_blocker`: Ein Teil mit Sperre, das normale Stütze im Rasterstil druckt
(Gitter, oder „automatisch“, wo der Herstellerprozess `normal(…)` mit Stil `default`/`grid`/leer
führt; PrusaSlicer: Gitter oder „automatisch“ über einem Prozess mit `grid`), bekommt
`support_style`/`support_material_style` `snug` als Objektwert (`writer.write_assembly`, nur wo
die Sperre tatsächlich mitreist). Baum, Hybrid und Cura bleiben. Regel `dateiformat.md`, Warum in
`konzepte/begruendungen/regel-dateiformat.md`, Karte `app/core/export/CLAUDE.md`.

Warum snug und nicht „kein Gitter vorschlagen“: snug ist dieselbe normale Stütze unter der flachen
Decke (Grund von RM-584 bleibt), nur am Umriss statt auf dem Raster; Deckel und Sims bleiben gleich
gestützt (unten). Größere Sperre hilft nicht: Sie nimmt keine Säulen fremder Überhänge aus.

## Tests

- `test_export.py::test_grid_support_beside_a_blocker_hugs_the_overhang` (Orca/Prusa × Gitter mit,
  Gitter ohne Sperre, Baum mit Sperre). Gegenprobe am Stand davor (Worktree `alt` auf `3d782213e`):
  2 rot (genau die beiden snug-Fälle), 4 grün.
- `test_real_slicers.py::test_grid_support_stays_out_of_a_blocked_channel`: Block mit Tunnel unter
  überstehendem Dach, Gitter, Sperre; ElegooSlicer, OrcaSlicer, Bambu Studio, Anycubic Slicer Next,
  PrusaSlicer. Neu: **5 passed, Exit 0** (Tunnel 8/8/7/8/14 mm, vor der Mündung 1378–6729 mm).
  Gegenprobe am alten Stand: **5 failed, Exit 1** (1025/761/1010/418/544 mm im Tunnel). Creality
  Print ausgenommen: dreht das Teil beim Anordnen (145°), von Hand mit Drehung gemessen.
- Messung `support_in_box` in `tests/gcode_contact.py`, Leser mit `support_contact` geteilt; die 7
  synthetischen Tests der Datei grün (Exit 0).
- Gezielt + Pflichtliste der Baumleser (`tests.sh`, 40 Dateien): vor dem Merge 6494 passed, 3 rot
  (`test_finding_ways`, zwei in `test_toolchain` — am Stand `3d782213e` ohne meine Änderung ebenso
  rot, mit welle4 behoben); nach dem Merge von welle4: **6499 passed, 11 skipped, Exit 0**. Nach dem
  Slicertest: Baumleser + directory_docs **3090 passed, Exit 0**; `test_directory_docs` Exit 0.
- ruff, ruff format --check, mypy: Exit 0 (je dreimal, zuletzt nach dem Merge von welle4
  `fdff3bb8f`).
- Nach dem Merge von welle4 `fdff3bb8f`: gezielt + Pflichtliste samt `test_value_labels.py` und den
  synthetischen Tests von `test_real_slicers.py` (`-m "… and not slicer"`): **6736 passed, 11
  skipped, Exit 0**. `test_value_labels.py` einzeln vorher: 299 passed, Exit 0.

## Slicerbelege (Matrix `tools/matrix_unit.py`, heim, Herstellerprofil, Vorschläge übernommen, gepinnt)

Becher schräg 20° Ø 34 (Stand welle4 ohne RM-629), Stützbahn im Tunnel / unter dem Sims, m;
Deckel: Anteil der Überhangfläche unter dem Deckel mit Stütze in der obersten Lage.

| Programm (Drucker) | Art | vorher Tunnel / Sims | nachher Tunnel / Sims | Deckel vorher/nachher |
|---|---|---|---|---|
| ElegooSlicer (CC2) | Gitter | 1,08 / 10,84 | 0,01 / 7,57 | 100 / 100 % |
| Bambu Studio (P1S) | Gitter | 0,97 / 6,04 | 0,01 / 2,97 | 100 / 100 % |
| OrcaSlicer (Kobra 2) | auto (normal) | 0,70 / 6,31 | 0,01 / 4,16 | 100 / 100 % |
| Creality Print (K1, gedreht 144,6°) | auto (normal) | 0,94 / 2,09 | 0,01 / 1,96 | 100 / 100 % |
| PrusaSlicer (MK4S) | auto = snug | 0,01 / 1,78 | 0,01 / 1,78 | 100 / 100 % |
| PrusaSlicer, Gitter als Objektwert | Gitter | 0,95 / 4,14 | 0,01 / 1,78 (snug) | 100 / 100 % |
| SuperSlicer (MINI) | auto (grid) | 0,00 / 2,32 | 0,00 / 1,67 | 0 / 0 % (eigenes Verhalten) |
| Cura (SV06) | — | 0,00 / 7,72 | 0,00 / 7,72 | 100 / 100 % |

Schlitz 45° 22 mm: Elegoo 1,08 → 0,01 (Sims 10,61 → 6,42), Bambu 0,97 → 0,01, Orca 0,70 → 0,01,
Creality 0,94 → 0,01, Prusa/SuperSlicer/Cura unverändert (0,01/0,00/0,00); Deckel überall 100 % vor
und nach (SuperSlicer 0/0). Anycubic Slicer Next fehlt in der Matrix (`heim`), belegt im Slicertest.

**Sims:** Am Stand welle4 ohne RM-629 liegt der Sims zu 65 % im Sperrkörper (`deckung.py`: frei
68,69 von 196 mm²) — das ist RM-629. Gitter lief über diese Grenze hinaus in die Sperre (Abdeckung
der Simsdecke 47,8 %), snug hält sie (39,5 %). Am RM-629-Stand (Sims frei, Übergaben der
Nachprüfung `rv629n/matrix`, Elegoo) gleich gestützt: Abdeckung 98,5 % Gitter / 98,8 % snug,
Tunnel 1,08 → 0,01 m in allen drei Bechern (schräg 20°: Sims 23,36 → 19,46 m; Schlitz 10,52 →
6,42; groß Y22 68,86 → 59,79, Tunnel 1,09 → 0,01). Die Meter sinken, weil das Raster über den Umriss
hinaus druckt.

## Korpus (Drache, Eiffelturm, Waschschüssel)

`korpus.sh` (Matrix, Elegoo CC2 und Orca Kobra 2, Vorschläge übernommen; vorher Worktree `alt`
auf `3d782213e`, nachher `fix/tunnel-gitter`), Ausgaben in `F:\tmp-agenten\rmtun\korpus_*`.

- **Eiffelturm, ElegooSlicer:** Rat „automatisch“ (dort Baum) mit Sperre, kein `snug` — die
  Übergabe-3MF ist vorher und nachher inhaltsgleich (`cmp` über den entpackten Inhalt). Der G-Code
  unterscheidet sich in zwei Stützabschnitten (804 gegen 802 `;TYPE:Support`): Streuung von
  ElegooSlicers Bäumen bei gleicher Eingabe, nicht Solidon.
- **Eiffelturm, OrcaSlicer Kobra 2:** „automatisch“ = normale Stütze, nachher `snug` am Teil.
  Stütze im Sperrkörper 0,04 → 0,00 m, gesamt 155,33 → 150,80 m; gestützter Anteil dessen, was
  Stütze braucht (`gcode_stuetzen.py`, `needed_share`), 100 % vorher und nachher.
- **Waschschüssel, ElegooSlicer:** Rat Hybrid (`tree_hybrid`) mit Kanal- und Randsperre, kein
  `snug`; Übergabe vorher und nachher inhaltsgleich. OrcaSlicer Kobra 2: in beiden Ständen
  „größer als die Druckfläche“, kein Schnitt.
- **Drache** (beide Läufe Exit 0): ElegooSlicer und OrcaSlicer Kobra 2 bekommen `tree(auto)` mit
  Sperre, kein `snug`; die Objektwerte der Übergabe sind vorher und nachher gleich (md5 von
  `model_settings.config`). Unverändert. Scratch-Worktree `alt` danach entfernt.

## Changelog

Kein Punkt: Die Ursache für Elegoo/Bambu (`55236d39c`) liegt in keinem Tag (`git tag --contains`
leer); für Orca/Creality mit „automatisch“ über normaler Stütze bestand der Rand von ~1 mm in der
Mündung schon in 0.5.x, aber er ist an der Außenstütze befestigt und mit ihr entfernt — nicht
kundenspürbar genug für eine eigene Zeile, und in den bestehenden 0.6.0-Punkt passt er nicht unter
200 Zeichen.

## Neue Punkte (Vorschlag)

- SuperSlicer (prusa-mini, Übergabe „automatisch“) stützt den Deckel des Bechers gar nicht
  (0 % in beiden Ständen, Stütze nur als Umriss eines Kreises); unabhängig von diesem Fix.
- Creality Print ordnet über die Konsole selbst an und dreht dabei (145° am Becher,
  `slicer.arranged_itself`); Messungen gegen den Körper brauchen die Drehung (`kanal_gedreht.py`).
- Hybrid (`tree_hybrid`) neben einer Sperre nicht gemessen: Der normale Teil darin könnte dasselbe
  Raster haben; snug lässt sich dort nicht setzen, ohne Hybrid aufzugeben.

## Zusammenfassung

Ursache: Die Sperre der Orca-Familie und von PrusaSlicer nimmt nur Überhangfläche aus; im
Gitterstil ragt das Raster der Deckelsäulen 1,1 mm in die Tunnelmündungen. Fix: `snug` als
Objektwert für Teile mit Sperre, die Gitter drucken. Tunnel nachher 0,01 m in Elegoo, Bambu, Orca,
Creality (gedreht gemessen), Prusa (Gitter), Anycubic im Slicertest; Deckel 100 % wie vorher,
Sims am RM-629-Stand gleich abgedeckt. Neuer Slicertest in fünf Programmen grün, am alten Stand rot.

## Commits

- `dc8a2b4ff` Gitterstütze neben einer Stützsperre liegt am Überhang an …
- `aa2bde396` Merge origin/welle4 (a72079433; die Meldung nennt nur die HTTP-Fristtests, mit hinein
  kam auch fix/intel-mac)
- `ee2ad829e` Ein Slicertest hält Gitterstütze aus einem gesperrten Kanal, in fünf Programmen
- `48071888c` Die Testkarte nennt die Messung der Stütze im Quader
- `d71a0552d` Merge origin/welle4 (fdff3bb8f)
- `d3abc9ae9` Merge origin/welle4 (4c135723a); danach ruff, format, mypy Exit 0 und test_export,
  test_real_slicers (ohne Slicer), test_print_settings, test_toolchain, test_finding_ways,
  test_directory_docs, test_value_labels, test_shared_constants, test_language_rules:
  **2059 passed, 8 skipped, Exit 0**. Gepusht.

Keine der für den Bereichsnachweis gesperrten Dateien berührt.

## Review rvtun (review_tunnel.md), alle sieben Funde behoben

| Fund | Commit | Beleg |
|---|---|---|
| 1 Baumstil des Herstellers unter Gitter | `6580f7bce` | Orca-Familie: snug, außer der Herstellerstil ist schon snug. Becher-Sonde des Reviews (`test_rvtun_becher.py`) OrcaSlicer Prusa XL, Gitter: snug in der Datei, Tunnel 0,01 m (vorher 1,06), Deckel 100 %, Simsdecke 38,1 %; Kobra 2 unverändert (0,00 m). Slicertest um `orcaslicer-prusa-xl` erweitert (`cabacc4a6`): am Stand vor Fund 1 rot (781 mm im Tunnel), jetzt grün |
| 2 Zweige ohne Test | `6580f7bce` | `test_print_settings.py::test_normal_support_beside_a_blocker_goes_out_snug`, 20 Fälle; sechs Mutanten (alter Stand, keine Ersatzart, „automatisch“ nie snug Orca/Prusa, snug-schon-da ignoriert, Bäume bekommen snug) je Exit 1 (1–3 rot) |
| 3 Prozess außerhalb des Lesedurchgangs | `5432fc917`, `e6da4d8cb` | `kosten_export.py`, drei Tunnelblöcke, ElegooSlicer CC2, je 3 Exporte in 2 Runden, gepinnt: CPU in `snug_beside_blocker` je Export vorher 172–234 ms, nachher 0–16 ms; jeder Aufruf jetzt im `single_read()`. `5432fc917` war mypy-rot (der Zuweisungsausdruck band `own`, das weiter unten eine Liste ist) — behoben in `e6da4d8cb` |
| 4 Zwei Herleitungen „automatisch“ | `6580f7bce` | Orca über `manufacturer.auto_prints_trees`, Prusa über neues `_prusa_auto_style`, das auch `tree_styles` fragt |
| 5 Dialog Gitter, Datei snug | `5432fc917` | Infobefund `export.snug_support` am Teil („In „{name}“ liegt die Gitterstütze neben der Sperre eng am Überhang an, damit sie nicht in gesperrte Stellen reicht.“), fünf Kataloge; Test in `test_export.py` |
| 6 Simsabdeckung braucht RM-629 | `6580f7bce` (Docstring), `42dcb422a` (Begründung) | Text nennt den Deckel als Beleg und sagt, dass eine zu große Sperre mit snug die zufällige Gitterstütze verliert (46 → 39 %) |
| 7 Changelog | `7276af5ba` | Behebung unter 0.6.0 / Drucken, sechs Sprachen, 149–169 Zeichen; Sperre seit `1db1dbfdd` (`git tag --contains`: v0.5.1, v0.5.2, v0.5.3) |

Merges: `e506f64d8` (welle4 `bc8595595`, mit RM-588). Tests nach dem letzten Stand (`e6da4d8cb`):
gezielt + Pflichtliste samt `test_value_labels`, `test_slicer_selection`, `test_real_slicers`
ohne Slicer: **6833 passed, 11 skipped, Exit 0**; Slicertest Kanalsperre sechs Fälle (Elegoo,
Orca K1 Max, Orca Prusa XL, Bambu, Anycubic, PrusaSlicer) **6 passed, Exit 0**; ruff, format,
mypy Exit 0. Handbuchseiten-Tests (`rendered`) bleiben wie erwartet außen vor. Keine
Abdruckdatei des Bereichsnachweises berührt. Spitze `e6da4d8cb`, gepusht.
