# Gezielte Nachprüfung N1/N2 RM-584 Teil 2 (F:\sl-stil, Zweig einstellungen/stuetzstil, Stand 89ac1ca6c) — 10.10.2026

Letzte Prüfrunde des Pakets. Gegenstand: die Behebungen `1c902c368` und `c533f04a5` zu N1 und N2
aus `reviews-2026-10-09/review_rm584_teil2_nach.md`. Ich habe nur gelesen und gemessen. Der
Worktree war vorher und nachher sauber (`git status` leer, HEAD = origin = 89ac1ca6c). Scratch:
`scratchpad/rv584n/`.

**Kurzfassung:** N1 und N2 sind behoben, am Code, mit Gegenproben und an beiden echten Slicern.
Kein schwerer und kein mittlerer Befund, ein leichter. **Kann landen.**

## N1: Cura, flache Decke, Gitter statt Baum: behoben

**Code.** `advise.py:1311-1313`: Unter Cura (`plate_kind`) verlangt die flache Decke ausdrücklich
`under_ceiling`, also Gitter, weil Cura kein Hybrid kennt (`trees` = {tree}). `advise.py:1366-1380`
liefert dazu „Automatisch → Gitter“. `combine` macht aus Gitter und Baum ohne Hybrid Gitter
(`advise.py:432`, `:467`). Der Arbeiter wirft danach jede Stützzeile weg, die Cura gleich druckt
(`print_settings_dialog.py:1690-1699`). `_cura_prints_alike` (`:1439-1447`) bildet genau die
Übergabe ab: `slicer_keys.py:650` schreibt `tree` → `tree` und alles andere → `normal`, das
An und Aus regelt `support_enable`. Die Prüfung auf „none“ hält „Aus → Gitter“ am Leben.
`tree_styles` liefert für Cura auch ohne Programm {tree} (`handover.py:3419-3420`), und zwar
an beiden Stellen, die fragen (`writer.py:1355`, `print_settings_dialog.py:1575-1577`). Am Feld
nennt ein Wechsel der Art keine Teile (`:1772-1778`), und ein eingeschaltetes Teil zählt mit der
Art der Platte (`:1800-1804`). Das passt zu `writer._values_for`, das die Art der Platte nimmt
(`writer.py:1585-1591`).

**Echtes Cura 5.13 (CuraEngine, Ender-3 V3 SE, PLA), gepinnt FFFFF0FF.** Gelaufen ist der Weg von
*Slicen*: Dialogarbeiter mit gefundenem Programm → `_prepare_plate` → `slice_model`. Alle vier
Läufe EXIT=0 (`slicer_lauf.txt`, `slicer_auswertung.txt`).

| Platte | Körper | Stützzeile im Dialog | Aufruf | Hut gestützt |
|---|---|---|---|---|
| Automatisch | Pilz allein | keine | `support_structure=normal`, `support_enable=true` | 99,9 % |
| Automatisch | Pilz + Figur | keine | `support_structure=normal`, Netze ohne eigene Werte | 99,9 % |
| Aus, übernommen | Pilz + Figur | „Aus → Gitter“, Grund „Die Überhänge sind zu groß …“, ohne Teilnamen | `support_structure=normal`, beide Netze `support_enable=true` | 99,9 % |

Nach dem Übernehmen zeigt das Feld keinen Hinweis: `accepted_parts` = (Pilz, Figur), also alle
Teile, und `accepted_others` ist leer. Eine Zeile ohne Wirkung habe ich nicht gesehen. Jede
Stützzeile ändert, was Cura bekommt. Die übrigen Zeilen betreffen Trennschicht, Haftung und
Brücken, nicht die Stützart.

**Gegenproben**, Mutation im geladenen Code ohne Dateiänderung (Plugin `rv584n_mut.py`). Gefahren
wurden 22 Tests (`test_grid_and_tree_become_hybrid_only_where_the_style_is_the_plates`,
`test_a_row_names…`, `test_the_field_names…`, `test_the_tree_styles_say…`,
`test_grid_over_automatic_only_where_automatic_means_trees`,
`test_a_flat_ceiling_and_details_on_one_plate_combine_to_hybrid`). Ohne Mutante: 22 grün, Exit 0.

| Mutante | rot |
|---|---|
| A Cura-Filter aus (`_cura_prints_alike` → False) | 1 (`[cura-trees2-auto-None]`) |
| B `plate_kind = False` | 4 |
| C `tree_styles` für Cura nur mit Programm | 3 |
| F Cura-Feld nennt beim Artwechsel Teile (`cura = False`) | 4 |
| G Filter ohne Prüfung auf „Aus“ (eigene, nicht in der Liste des Bauagenten) | 2 |

## N2: Zeile und Feld nennen den Pilz mit seinem Wert: behoben

**Code.** `_with_parts` und `_accepted_targets` merken sich, welche Teile mit der Zeile einen
anderen Wert bekommen (`print_settings_dialog.py:1880-1887`, `:1805-1806`). Der Titel nennt sie
einmal je Wert und kürzt sie mit `_few_names` (`:8565-8573`), also höchstens drei Namen je Wert.
Bei der Stützart gibt es höchstens vier Werte, die Zeile ist damit begrenzt. Der Tooltip nennt
jedes Teil (`:8582-8586`). Das Feld nennt zuerst die Teile des Vorschlags, dann die mit eigenem
Wert, und den Rest nur, wenn noch Teile übrig sind (`:7509-7518`). Der alte zusammengesetzte
Schlüssel ist aus Code und allen fünf Katalogen verschwunden.

**Texte.** Alle fünf Kataloge führen „{part} mit {value}“ (with/con/avec/con/com), „{part} bekommt
{value}.“, „Die übrigen Teile drucken mit {value}.“, „Nur für {parts}.“ und „und {count} weitere“.
Übersetzung und Grammatik stimmen. Die Platzhalter stimmen überall, auch bei it „e altri {count}“
und pt „e mais {count}“.

**Echter ElegooSlicer (Centauri Carbon 2, PLA), gepinnt, EXIT=0.** Platte „Aus“, Zeile übernommen:

- Zeile „Stützen · Figur, Pilz mit Gitter“ (Aus → Baum), Tooltip „Gilt für: Figur / Pilz bekommt
  Gitter.“; nach dem Übernehmen Feld „Nur für Figur. Pilz bekommt Gitter.“
- 3MF: Figur `enable_support 1`, `support_type tree(auto)`; Pilz `enable_support 1`,
  `normal(auto)`, `support_base_pattern rectilinear-grid`; Platte `enable_support 0`. Hut zu
  100 % gestützt, Stützbahn Pilz 80,7 m, Figur 11,2 m.

Zeile und Feld beschreiben also, was die Datei tut. Lehnt der Kunde die Zeile ab, nennt sie
ihm vorher auch den Pilz.

**Gegenproben:** D (alte Reihenfolge im Feld) 1 rot, E (Zeile nennt jedes Teil einzeln) 1 rot.

## Haben die Behebungen etwas kaputt gemacht? (nur soweit es N1/N2 betrifft)

`_few_names` rechnet dieselbe Kürzung wie der frühere eingebaute Code. Die Cura-Zweige in
`_with_parts` und `_accepted_targets` greifen nur bei Cura, und nur, wenn weder der alte noch
der neue Wert „Aus“ ist. „Aus → Gitter“ nennt deshalb weiter die Teile. Ein drittes Teil ohne
Stützbedarf bekommt bei Cura weiter `support_enable` aus der Grundlage. Das Feld sagt dazu „Die
übrigen Teile drucken mit Aus“. Einen Bruch habe ich nicht gefunden.

## Befunde

### Leicht

**L1: Das Feld fasst gleiche Werte nicht zusammen, die Zeile schon**
`app/ui/print_settings_dialog.py:7495-7498`. Das Feld schreibt für jedes andere Teil einen
eigenen Satz. Die Zeile fasst seit `c533f04a5` je Wert zusammen und kürzt (`:8569-8573`, Test
`test_a_row_names_the_parts_that_get_their_own_value_with_it`, fünf Teile ergeben „Pilz, Hut und
2 weitere mit Gitter“). Mit denselben fünf Teilen schreibt das Feld nach dem Übernehmen fünf
Sätze „Pilz bekommt Gitter. Hut bekommt Gitter. …“. Beleg ist der Code, nicht gemessen. Zeile und
Feld sagen dasselbe auf zwei Arten (`.claude/rules/zwillinge.md`). Der Hinweis bricht um und
sprengt kein Layout. „Nur für {parts}“ ist ebenfalls ungekürzt, das aber schon seit RM-289 B6.
Fix: im Feld wie in der Zeile je Wert gruppieren und `_few_names` nehmen, mit einem Text, der
Mehrzahl verträgt (etwa „{parts} mit {value}.“). Test wie oben mit fünf Teilen an `_mark_parts`.
Hält das Landen nicht auf.

### Hinweis, kein belegter Fund

Unter Cura fragt ein Körper, dessen Baum durch die Zusammenführung zu Gitter wird, Abstand und
Spitzenluft weiter mit seinem Baum (`advise.py:1458` `printed_style`, `:1118` `tip_gap` gilt bei
„cura und tree“). Gefiltert wird danach nur die Stützzeile (`print_settings_dialog.py:1690-1699`).
Sitzt ein Körper mit mindestens 100 Spitzen, der Bäume will (der Drache, 199), mit einer flachen
Decke auf einer Cura-Platte, käme nach dem Code „Abstand oben → 0,4: Feine Spitzen brauchen mehr
Luft über den Baumstützen“, obwohl Cura `normal` druckt. Gemessen ist das nicht. Meine Sonde mit
100 schwebenden Stiften (`probe_spitzen.py`, EXIT=0, `probe_spitzen_none.json`) will keinen
Baum („Aus → Automatisch“) und löst den Fall nicht aus. Den Drachen habe ich nicht gefahren.
Vorschlag als neuer Punkt: bei Cura den Kontakt nach der Zusammenführung mit der Art der Platte
fragen, geprüft am Drachen neben dem Pilz.

## Ausgeführt

- 4 Slicerläufe gepinnt, alle EXIT=0: Cura Pilz allein „Automatisch“, Cura Pilz+Figur „Automatisch“
  und „Aus“, ElegooSlicer Pilz+Figur „Aus“ (`slicer_stil.py` des Zweigs, ergänzt um alle Zeilen,
  den Feldtext und „Pilz allein“).
- 8 Testläufe gepinnt (ohne Mutante und A–G), je 22 Tests (`mut_lauf.txt`, `mut_*.txt`): ohne
  Mutante Exit 0, jede Mutante Exit 1 mit den oben genannten roten Tests.
- 1 Sonde gepinnt (`probe_spitzen.py`, zwei Starts, EXIT=0).
- Kein volles Tor, keine CI, kein ruff und kein mypy, weil ich nichts geändert habe.

## Urteil

**Kann landen.** N1 und N2 sind am Code, mit Gegenproben und an Cura wie am ElegooSlicer belegt
behoben. L1 und der Hinweis können als neue Punkte folgen.
