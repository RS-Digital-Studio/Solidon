# Nachprüfung RM-704 — Fix-Diff `ddea0dd43` (Zweig `einstellungen/drache-druck3`)

Gegenstand: Worktree `F:\sl-drache3`, Fix `ddea0dd43`, Merge welle3 `076965bfe` (HEAD, Worktree
sauber). Diff `git diff 917b49bbe..ddea0dd43` (22 Dateien, +231/−82), jede Zeile gelesen.
Erstreview: `review_rm704.md`. Scratch: `scratchpad\rv704n\` (Kopien `kopie`, `kopie2` per
`git archive 076965bfe`, Skripte `mutanten.py`, `auswertung.py`, `kegelstuetze.py`,
Sonde `kopie2\tests\test_sonde_rv704n.py`). Beginn 11:32.

## Läufe nach dem Merge (HEAD `076965bfe`, gepinnt FFFFF0FF)

| Lauf | Ergebnis |
|---|---|
| `test_real_slicers.py -k roof_tip` (Orca, Bambu, Elegoo, Creality, Anycubic), `--basetemp rv704n\bt` | 5 passed, 199 s, EXIT=0 |
| `test_print_settings_ui.py -m "not performance and not rendered"` (ganze Datei, mit Fenster) | 450 passed, 3 deselected, 300 s, EXIT=0 |
| `test_text_length`, `test_changelog`, `test_translations`, `test_wording`, `test_roadmap`, `test_directory_docs` | 339 passed, 4 skipped, EXIT=0 |
| `ruff check --no-cache .` / `ruff format --no-cache --check .` (1206 Dateien) | EXIT=0 / EXIT=0 |
| `mypy` (Cache im Scratch) | 374 Dateien ohne Befund, EXIT=0 |
| Kopie, Grundlinie ohne Mutation: `test_slice_findings`, `test_print_settings`, `test_manufacturer` | 1264 passed, 4 skipped, EXIT=0 |

## Gegenproben per Mutation (Kopie `rv704n\kopie`, `mutanten.py`)

| Mutation | Testdateien wie beim Erstprüfer | Erstprüfer | Jetzt |
|---|---|---|---|
| M4 `roofs = layers` gestrichen | `test_slice_findings.py` | grün, 217 passed | **rot**: `test_proposed_roofs_bring_the_roof_tip_along` |
| M7 Spitze unter Gitter aktiv | `test_print_settings.py` | grün, 840 passed | **rot**: `test_the_tree_walls_rest_under_a_grid[grid-True]` |
| M8 Leserzeile in `ORCA_PROCESS` gestrichen | `test_manufacturer.py`, `test_print_settings.py` | grün, 1041 passed | **rot**: `test_the_tip_is_read_back[1.2]`, `[0.8]`, `test_a_tip_of_nothing_stays_foreign` |
| M11 `_number` statt `_positive` (Null als Spitze) | `test_manufacturer.py` | – | **rot**: `test_a_tip_of_nothing_stays_foreign` |
| M12 Italienischer Katalog nennt 1,2 statt 1,13 | `test_slice_findings.py -k tip_field_names` | – | **rot**: `test_the_tip_field_names_the_roof_tip` |

L1 ist damit behoben: Alle drei Lücken des Erstprüfers fangen jetzt einen Fehler.

## Bambu: Liest es die Spitze doch? Nein.

Sonde `test_sonde_rv704n.py` (Kopie `kopie2`, gleiche Platte und Werte wie der Slicertest, Bambu
A1, gepinnt). Viermal geschnitten, in der Folge 0,8 / 1,13 / 0,8 / 1,13 mm (a, b, c, d).
Verglichen wurden die Endpunkte als Multimenge, unter z 19.

| Paar | Stütze verschieden (von 5920) | Modell verschieden (von 2151) | Trennschicht |
|---|---|---|---|
| a 0,8 – c 0,8 (gleiche Eingabe) | 19 + 19 | 8 + 8 | 0 / 0 |
| b 1,13 – d 1,13 (gleiche Eingabe) | 19 + 19 | 8 + 8 | 0 / 0 |
| a 0,8 – b 1,13 | 19 + 19 | 8 + 8 | 0 / 0 |
| **a 0,8 – d 1,13** | **0** | **0** | 0 / 0 |

- Bambu wechselt von Lauf zu Lauf zwischen zwei Fassungen derselben Platte: Lauf 1 gleicht Lauf 4
  und Lauf 2 gleicht Lauf 3, egal welche Spitze. Die Abweichung trifft auch die Modellbahnen. Der
  Bauagent sah mit seinen zwei 0,8-Läufen zufällig dieselbe Fassung. Seine 38 Punkte sind diese
  19 + 19, also Streuung von Bambu und keine Wirkung der Spitze.
- Der Konfigurationsblock der vier Druckdateien ist gleich, und `tree_support_tip_diameter` kommt
  darin nicht vor. In der 3MF unterscheidet sich nur `Metadata/project_settings.config`, und dort
  nur `tree_support_tip_diameter` (0.8 / 1.13).
- Im Slicertest ist es genauso (`auswertung.json`): Bambu 19 + 19 von 5920, Trennschicht 0 / 0.

Bambu stützt dabei jede Kegelspitze, mit 38–72 Stützpunkten je Kegel in z 14–16,4, in beiden
Läufen gleich (`kegelstuetze.txt`). Die zugesicherte gleiche Trennschicht (0 = 0) hat also eine
Aussage: Nähme Bambu die Spitze, käme unter den gestützten Spitzen Trennschicht dazu.

## M1–M3, L1, L3 im Einzelnen

- **M1, Feldhinweis: behoben.** Der Hinweis lautet „Ab etwa 1,13 mm trägt jede Spitze eine
  Trennschicht.“, in allen sechs Sprachen. `test_the_tip_field_names_the_roof_tip` hält die Zahl in
  Quelle und Katalogen gegen `ROOF_TIP_DIAMETER`; M12 wird rot.
- **M1, Changelog: Rest offen, siehe N1.** Das Durchhängen ist gestrichen, die sechs Sprachen sind
  gleich gegliedert, `test_changelog` ist grün. „Am Teil bleibt weniger von der Stütze hängen“ ist
  aber nur an den Unterseiten gemessen.
- **M1, Register: behoben** (Druck 4 prüfen, sonst V18).
- **M2: behoben.** Begründung (`regel-druckrat.md:708-712`), Archiv und Register nennen 49 statt 31
  Füße und 14,3 statt 8,5 mm², dazu Kopf 105–112 mm und Vorderbeine bei etwa 21 mm. Dabei kam ein
  falscher Vergleich ins Bein (N3).
- **M3: behoben.**
  - Art aus `TYPE|FEATURE`; Stütze unter z 19 wird verlangt.
  - Im Ja-Zweig Trennschicht unter jedem der sechs Kegel: gemessen 54–289 Punkte je Kegel mit
    1,13 mm, 0 mit 0,8 mm (Orca, Elegoo, Anycubic).
  - Im Nein-Zweig gleiche Trennschicht. Für Bambu kommt die Meldung dazu (geloggt für 0,8 und
    1,13).
  - Der Docstring stimmt jetzt. Nur die Begründung der 38 Punkte im Kommentar ist falsch (N2).
- **L1: behoben** (siehe Mutationen).
- **L3: behoben, soweit gefordert.**
  - Regel, `slicer_keys`-Kommentar und `types.py` stimmen mit dem Code (`organic_tree_fitted`
    hebt jede Spitze unter der Bahn).
  - `SLICED_PATHS` ohne Spitze und die Creality-Zeile hatte der Erstprüfer folgenlos bzw.
    hinnehmbar genannt. Das bleibt so, weil die Spitze plattenweit geht (nicht in `PART_PATHS`).

## Befunde

### N1 (mittel, Rest von M1) — Der Changelog verspricht weniger Stütze am ganzen Teil, gemessen ist es nur an den Unterseiten

`changelog/de.md:115` und die fünf Übersetzungen: „…und am Teil bleibt weniger von der Stütze
hängen.“ (en „less of the support sticks to the part“, fr „moins de support reste collé“, it „sul
pezzo resta meno supporto“, es/pt sinngleich).

Beleg aus dem Erstreview (M2) und `drache3.md`, Kundenweg mit 1,13 mm:
- An den Unterseiten nimmt der Kontakt ab: Kinn 6,95 → 3,95 mm², Stacheln 3,16 → 1,87 mm².
- Auf dem Modell stehen mehr Füße: 31 → 49, Fläche 8,53 → 14,32 mm². Neu sind Füße am Kopf
  (105–112 mm), an Hals, Brust und Vorderbeinen.
- Zusammengezählt liegt mehr Stütze am Teil an, nicht weniger (18,6 → 20,1 mm²). Die Maße sind
  nicht ganz gleichartig, Kontakt mit 0,2 mm Luft gegen Auflage.

Der Satz stammt wörtlich aus dem Fixvorschlag des Erstreviews. M2 im selben Review widerlegt ihn
für das ganze Teil. Begründung und Archiv nennen die Kosten jetzt; der Kundentext bleibt beim
Gewinn.

Gleiche Art, im Erstreview nicht genannt: Der Grund am Vorschlag,
`app/core/slice/advise.py:1233`, sagt „Trennschicht auf jeder Baumspitze trägt die Unterseite.“
Getragen ist die flache Unterseite aber kaum mehr (22 → 25 %). Was sich ändert, ist die Haftung.

**Fix:**
- Changelog in allen sechs Sprachen auf die Unterseiten begrenzen. Deutsch zum Beispiel: „Dann
  sitzt auf jeder Spitze eine Trennschicht, und an Unterseiten bleibt weniger Stütze hängen.“ Das
  sind 196 Zeichen, gezählt mit `laengen.py`. Französisch steht heute bei 199 und muss dafür an
  anderer Stelle kürzer werden.
- Grund, empfohlen im selben Zug: „Mit Trennschicht löst sich jede Baumspitze leichter.“ (52
  Zeichen), dazu die fünf Kataloge. Danach `test_text_length` fahren.

### N2 (leicht) — Kommentar und Bericht schreiben Bambus Streuung der Spitze zu

`tests/test_real_slicers.py:570-571`: „Bambu meldet den Schlüssel selbst als übergangen; seine Äste
weichen trotzdem an einzelnen Punkten ab (38 von über 4000 unter den Kegeln).“ Ebenso
`drache3.md`, Fixes M3: „1,13 weicht an 38 … ab, obwohl Bambu den Schlüssel als übergangen
meldet“.

Die Sonde oben widerlegt das. Zweimal 0,8 mm weichen genauso ab (19 + 19), während 0,8 und 1,13
in passender Fassung gleich sind (a – d: 0). Die Zusicherung über die Meldung bleibt richtig, die
Begründung im Kommentar nicht. Ein Leser schlösse daraus, Bambu lese den Wert doch.

**Fix:**
- Kommentar: „Bambu legt dieselbe Platte von Lauf zu Lauf an einzelnen Punkten anders an (19 + 19
  von 5920 Stützpunkten, auch zweimal mit 0,8 mm). Gleiche Äste lassen sich deshalb nicht
  zusichern; die Meldung zeigt, dass Bambu den Schlüssel nicht kennt.“
- Wahlweise zusätzlich eine feste Zusicherung: gleicher Konfigurationsblock beider Druckdateien.
  Er war in allen vier Läufen gleich und enthielt den Schlüssel nicht.
- Im eigenen Bericht `drache3.md` den Satz berichtigen.

### N3 (leicht) — „kaum mehr Stütze“ am Bein kehrt den Vergleich um

`konzepte/begruendungen/regel-druckrat.md:714-716` und `ROADMAP.md:951`: „Das Vorderbein, das
beim Abnehmen brach, hatte kaum mehr Stütze als im zweiten Druck (Umfang mit Stütze in 1 mm 2
gegen 3–5 %, mit der Spitze 0,2 mm² Auflage)“.

Am gebrochenen Bein in Druck 3 war es weniger Stütze, 2 gegen 3–5 % (`drache3.md`, Matrix). Die
0,2 mm² Auflage gehören zur neuen Spitze (V20), die Druck 3 nicht hatte. Vor dem Fix stand
richtig „nicht mehr“. Der Fix zu M2 hat Druck 3 und V20 vermischt.

**Fix:** „…hatte nicht mehr Stütze als im zweiten Druck (Umfang mit Stütze in 1 mm 2 gegen
3–5 %, keine Auflage; mit der breiteren Spitze kämen drei kleine Füße mit 0,2 mm² dazu)“. Im
Register entsprechend „nicht mehr Stütze“.

### N4 (leicht) — Der Slicertest sichert für 0,8 mm nicht zu, was sein Docstring sagt

`tests/test_real_slicers.py:535` sagt „mit der Spitze von 0,8 mm keine“ Trennschicht.
Zugesichert ist in `:565` nur „mehr“ (`len(roof) > len(plain)`).

Gemessen (`auswertung.json`): Mit 0,8 mm liegt in allen fünf Programmen unter z 19 keine einzige
Trennschichtbewegung. Mit 1,13 mm sind es in Orca, Elegoo und Anycubic 54–289 je Kegel. Die
Zusicherung „keine“ würde zugleich die Voraussetzung des Rats bewachen: Legte ein Programm schon
mit 0,8 mm Trennschicht auf die Spitzen, wäre der Rat überflüssig.

**Fix:** Im Ja-Zweig `assert not plain["interface"], program`. Den Wert hat der Lauf schon
gemessen.

## Beobachtungen ohne Fund

- `plain["support"] and roof["support"]` meldet „stützt die Kegel nicht“. Geprüft wird aber
  Stütze irgendwo unter z 19, und dort stehen auch die Bäume der Platte.
  - Gemessen je Kegel (`kegelstuetze.txt`): Bambu, Orca, Elegoo und Anycubic stützen jede
    Spitze.
  - Creality stützt mit 0,8 mm zwei der sechs Spitzen erst ab etwa z 17 statt an der Spitze.
  - Die Aussage des Nein-Zweigs trägt also. Eine Zusicherung je Kegel wäre genauer, ist aber
    keine Pflicht.
- Der Changelog sagt „Wo Solidon mehr Abstand … vorschlägt, schlägt es auch … vor“. Den Abstand
  schlägt Solidon auch für PrusaSlicer, Cura, Bambu Studio und Creality Print vor
  (`tip_gap`, `advise.py:1106-1130`), die Spitze nur in OrcaSlicer, ElegooSlicer und Anycubic.
  Der Nachbarpunkt zu den Baumwänden hält es genauso, ohne Programme zu nennen. Neben 200
  Zeichen ist dafür kaum Platz; ich führe es deshalb nicht als Fund.
- Nichts Neues kaputt im Fix-Diff:
  - `_support_below` liest Lage und Art richtig, für Bambu ohne `;TYPE:`.
  - Die Mitte der Platte aus den Modellbahnen trifft die Kegel: je Kegel Trennschicht in 2 mm,
    0,8 mm ohne.
  - Die Kommentare in `slicer_keys` und `types.py` stimmen mit `organic_tree_fitted` und dem
    Bestand.
  - Die Regel nennt die Plattenweite richtig (`combine` nimmt das Größte).

## Urteil

**Nicht — nach dem Fix zu N1 kann es landen, ohne weitere Nachprüfung.**

M2, M3, L1 und L3 sind behoben. M1 ist es am Feldhinweis und im Register; die drei vorher grünen
Mutationen sind jetzt rot. Slicertest, Fenstertest, Texttests, ruff, format und mypy sind am
HEAD grün.

Bambu liest die Spitze nicht. Die 38 Punkte sind Bambus Streuung von Lauf zu Lauf.

Offen bleibt N1: Der Changelog in sechs Sprachen verspricht weniger Stütze am ganzen Teil,
gemessen ist das nur an den Unterseiten, während die Füße auf dem Modell zunehmen. N2 bis N4 sind
leicht und gehören in denselben Commit: ein Kommentar, zwei Sätze in den Unterlagen, eine
Zusicherung mit schon gemessenem Wert. Danach den Slicertest einmal gepinnt fahren, dazu
`test_text_length` und `test_changelog`.

Ende 11:49.
