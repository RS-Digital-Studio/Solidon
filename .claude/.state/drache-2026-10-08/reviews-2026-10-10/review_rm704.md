# Review RM-704 — Baumspitze mit Trennschicht (Zweig `einstellungen/drache-druck3`)

Gegenstand: Worktree `F:\sl-drache3`, Commits `053141305`, `121697bcb`, Merge `917b49bbe`
(welle3 `c7a6f853d`). Diff `git diff 02515ef3c..121697bcb` (gleich `c7a6f853d...917b49bbe`,
24 Dateien, +354/−15), jede Zeile gelesen. Beginn 10:10, abgeschlossen 10:55 (Formatfrage des Koordinators eingeschlossen).
Scratch und Sonden: `scratchpad\rv704\` (Skripte `fuesse.py`, `fuesse_vergleich.py`,
`fuss_art.py`, `bein_abstand.py`, `sonde_spitze.py`, `mutanten.py`, `mutanten_ui.py`).

## Urteil

**Kann landen, nach den Fixes zu M1–M3.** Kein schwerer Fund. Der Rat ist richtig hergeleitet,
hängt an der richtigen Konstante und erscheint nur dort, wo er wirkt. Nach dem Merge sind
Slicertest, Fenstertest, ruff, format und mypy grün. Zu beheben sind Texte, die mehr versprechen
als gemessen ist (M1), eine nicht abgewogene Nebenwirkung (M2, nur Unterlagen) und ein Slicertest,
der für Bambu über eine leere Menge grün ist (M3).
**Nachprüfung: ja, kurz und nur über den Fix-Diff**, weil mehrere Befunde mittel sind (Texte in
sechs Sprachen, Zähler im Slicertest, Unterlagen). Einen neuen Matrix- oder Kundenweglauf braucht
es nicht, nur den geänderten Slicertest einmal.
Zum Format (Frage des Koordinators): Weder Projekt- noch Cacheformat müssen steigen. Alte Projekte
öffnen, ältere 0.6-Stände öffnen neue Projekte und übergehen die Spitze, 0.5.3 lehnt sauber ab
(Abschnitt „Format, Cache und ältere Stände“). Dabei gefunden: Der Abdruck der Verbrauchsbuchung
ändert sich mit jedem neuen Einstellungsfeld. Das ist ein neuer Punkt, der schon in welle3 gilt;
RM-704 hält er nicht auf.

## Läufe nach dem Merge (HEAD `917b49bbe`, gepinnt FFFFF0FF)

| Lauf | Ergebnis |
|---|---|
| `test_real_slicers.py -k roof_tip` (Orca, Bambu, Elegoo, Creality, Anycubic) | 5 passed, 177 s, EXIT=0 |
| `test_print_settings_ui.py -m "not performance and not rendered"` (ganze Datei, mit Fenster) | 436 passed, 284 s, EXIT=0 |
| `test_text_length`, `test_translations`, `test_wording`, `test_changelog`, `test_roadmap`, `test_directory_docs`, `test_language_rules`, `test_interface_limits` | 834 passed, 4 skipped, EXIT=0 |
| Kopie `git archive 917b49bbe`: `test_slice_findings`, `test_print_settings`, `test_manufacturer`, `test_slicer_profiles`, `test_export` | 1801 passed, 4 skipped, EXIT=0 |
| `ruff check`, `ruff format --check` (geänderte Dateien), `mypy` (374 Dateien) | Exit 0, 0, 0 |

## Antworten auf die Prüffragen

**1. Richtigkeit des Rats.** Er kommt, wenn `tip_gap` gilt (PLA mit `support_tip_gap`,
mindestens `TIP_ISLANDS` Spitzeninseln, organische Bäume), die Familie Orca ist, oben
Trennschichten gedruckt werden (eigene oder vorgeschlagene) und die Spitze unter
`ROOF_TIP_DIAMETER` liegt (`advise.py:1222-1235`). Dialog (`_shown_advice`, `takes`) und
Export (`writer.py:1417`) lassen ihn für Bambu und Creality weg.
- Herleitung: π·d²/4 > 1 mm² ⇒ d > 1,1284 ⇒ 1,13 auf Hundertstel aufgerundet. Dieselbe Konstante
  `TIP_ROOF_AREA` wie die Inselzählung, keine zweite Zahl im Code. **Am Programm bestätigt**
  (ElegooSlicer, Kegelplatte, 0,2 mm): 1,10 und 1,12 → 0 Trennschichtbewegungen unter den Kegeln,
  1,13 → 646. Ein Hundertstel weniger reicht also nicht.
- Je Programm: Orca, Elegoo und Anycubic wirken (Slicertest). Bambu kennt den Schlüssel nicht:
  `BambuStudio.dll` führt `tree_support_*` ohne `tip_diameter`, und die Druckdateien mit 0,8 und
  1,13 sind byte-gleich. Creality liest ihn (Konfigurationsblock 0.8/1.13), baut damit andere Äste
  (Stützbewegungen 3772 → 3806), aber keine Trennschicht (0/0). Dass dort kein Rat kommt, ist
  richtig.
- Schichthöhen: 0,08 mm gibt bei Elegoo 0 → 1228 Bewegungen, bei Orca 0 → 1208. 0,28 mm gibt bei
  Elegoo 451 → 744, bei Orca 489 → 959. Der Rat wirkt auf allen drei Rastern.
- Herstellerprofil mit breiterer Spitze: Der Wert wird über `ORCA_PROCESS` gelesen, ab 1,13 kommt
  kein Rat. Im Bestand haben Orca und Elegoo 26× 1,2, 11× 1,5 und 16× 2 mm, Anycubic 28× 1,5. Für
  die 3× 1,0 kommt 1,13. Die Leserzeile selbst ist ungetestet (L1).
- Eigene Wahl: Unter 1,13 kommt der Rat als Vorschlag über die Wahl (wie jeder Vorschlag), ab
  1,13 kommt keiner.
- Gitter: kein Rat, das Feld ist inaktiv (ungetestet, L1). Hybrid: kein Rat, weil `tree_hybrid`
  nicht organisch ist. Das Feld wirkt dort trotzdem (siehe L2, zurückgenommen).
- Mehrere Teile: Die Spitze geht **plattenweit** (nicht in `PART_PATHS`), `combine` nimmt das
  Maximum. Ein Teil ohne Bedarf bekommt sie mit, Abstand und Trennschichten bleiben je Teil.
  Messbar unschädlich bei 0,2 mm Abstand (V18: Stachelkontakt 94 → 80 mm²). PETG daneben ist nicht
  gemessen. Die Regel sagt das nicht (L3).

**2. Nebenwirkung.** Ja, es steht mehr Stütze auf dem Modell (M2). An den Stacheln bleiben weniger
Reste (Kontakt 3,2 → 1,9 mm²), am Kinn ebenso (7,0 → 4,0 mm²).

**3. Übergabe und Dialog.** Gelesen wird aus dem Herstellerprofil. Geschrieben wird nur bei Wahl
oder Übernahme: Im Kundenweg tragen *standard* und *stuetzen_auto* in alt und neu 0.8 (vom
Hersteller), nur *vorschlaege* neu trägt 1.13 (`beleg\*\Drache.3mf`). Ohne Herstellerprofil
schreibt Solidon wie bei jedem Feld seinen Wert 0,8 (Entscheidung D). Die Dialogzeile ist nach
`takes` gefiltert. Die Kataloge in sechs Sprachen stimmen in den Begriffen mit „Trennschicht“ und
„Baum…“ überein, `test_text_length` ist grün. Der Changelog führt den Punkt als Eigenschaft, und
das stimmt: Die Ursache `1ddb4953a` (Spitzenabstand) liegt in keinem Tag. Inhaltlich trifft er
nicht zu (M1). Register und Archiv führen RM-704 mit dem offenen Rest (Wände an schlanken
Gliedern, Spitze für PrusaSlicer und Cura); es fehlt die Kinnprüfung an Druck 4 (M1, M2).

**4. Tests.** Siehe L1 (Mutationen) und M3 (Slicertest).

## Befunde

### M1 (mittel) — Changelog und Feldhinweis versprechen, dass nichts mehr durchhängt

`changelog/de.md:112` und die fünf Übersetzungen: „Jede Spitze trägt dann eine Trennschicht, und
Unterseiten daneben hängen nicht durch.“ `app/core/knowledge/print_fields.py:701-702`:
„…bekommt jede Spitze eine Trennschicht und trägt die Unterseite flächig.“
Die Messung (drache3.md, Teil B, Kundenweg mit 1,13 mm) sagt anderes. Getragen sind die flachen
Teile der Kieferunterseite zu **25 % statt 22 %** (mit 1,2 mm 27 %; in Druck 2, der nicht
durchhing, 54 %). Die schrägen Ränder bleiben bei 26 → 25 %. Neu ist, dass das Getragene auf
Trennschicht liegt (5 → 25 %) und weniger anhaftet (Kontakt 7,0 → 4,0 mm²). Der Abstand von
0,4 mm, den drache3.md als Ursache des Durchhängens nennt, bleibt. Ob das Kinn mit 1,13 mm weniger
durchhängt, zeigt erst Druck 4.

Der Changelogsatz ist außerdem schwer zu lesen. Bei „Zu mehr Abstand über feinen Spitzen“ liegt
die Luft unter den Modellspitzen, nicht darüber. „Spitze“ meint im ersten Satz das Modell, im
zweiten den Baum, und „daneben“ bleibt unklar.

Im Feldhinweis steht dazu die Zahl 1,13 als Text in sechs Katalogen, neben
`advise.ROOF_TIP_DIAMETER` (`.claude/rules/zwillinge.md`).

**Fix:**
- Changelog: die gemessene Wirkung, z. B. „Wo Solidon mehr Abstand über Baumstützen vorschlägt,
  schlägt es auch eine breitere *Baumspitze* vor. Dann sitzt auf jeder Spitze eine Trennschicht,
  und am Teil bleibt weniger von der Stütze hängen.“ In allen sechs Sprachen, höchstens 200
  Zeichen.
- Feldhinweis: „…Ab etwa 1,13 mm trägt jede Spitze eine Trennschicht.“ Dazu ein Test, der die
  Zahl im Hinweis gegen `ROOF_TIP_DIAMETER` hält.
- Register RM-704, offen: „An Druck 4 prüfen, ob das Kinn trägt (25 % statt 54 % getragen); wenn
  nicht, bleibt der Abstand der Hebel (V18).“

### M2 (mittel) — Mehr Stütze auf dem Modell, in den Unterlagen nicht abgewogen

Gemessen mit `fuesse.py` (Messweg von `gcode_auflage.py`, dazu Lage je Fuß) am Drachen
(ElegooSlicer, CC2):

| Lauf | Füße auf dem Modell | Fläche |
|---|---|---|
| Matrix V0 | 31 | 8,53 mm² |
| Matrix V20 (nur Spitze 1,13) | 49 | 14,32 mm² (**+68 %**) |
| Kundenweg `beleg\alt` (alle Vorschläge) | 31 | 8,53 mm² |
| Kundenweg `beleg\neu` (alle Vorschläge) | 49 | 14,32 mm² |

Alt und neu im Kundenweg sind genau gleich wie V0 und V20, die Messung ist also wiederholbar.
- 13 Füße sind neu (3,46 mm²; vorher lag keiner näher als 2 mm seitlich und 1 mm in der Höhe).
  Der Rest der Zunahme sind größere alte Füße (+2,33 mm²).
- Laut `fuss_art.py` stehen die neuen auf Außenwänden: am **Kopf** auf 105,6–112 mm Höhe
  (2,49 mm²), an Hals und Brust auf 77–78 mm (0,78 mm²), drei sehr kleine an **beiden
  Vorderbeinen** auf etwa 21 mm (0,19 mm²; Stütze über Modell, das bei 20,4–20,6 mm endet).

drache3.md nennt die Gesamtzahl im Nachtrag A (V12: 12,9 mm² bei 49 Füßen). Begründung
(`regel-druckrat.md`), Archiv und Register führen aber nur die Gewinne. Teil B sagt „keine
Stütze setzt auf den Beinen auf (Auflage 0 mm² in allen Varianten)“; für V20 trifft das nur
fast zu.

Gegen den Rat spricht das nicht: Die Reste an Kinn und Stacheln nehmen ab. Aber am sichtbaren
Kopf entstehen neue Narben.

**Fix:**
- Begründung und Archiv nennen die Kosten: Füße 31 → 49, 8,5 → 14,3 mm², neue am Kopf und an
  den Vorderbeinen.
- Register RM-704, offen: an Druck 4 (Spitze 1,2, ebenfalls 49 Füße) den Kopf auf 105–112 mm
  Höhe und die Vorderbeine bei etwa 21 mm ansehen.

### M3 (mittel) — Slicertest: Der Bambu-Fall ist über eine leere Menge grün, der Docstring stimmt nicht

`tests/test_real_slicers.py:378-394` (`_interface_extrusions`), `:403-438`.

Der Zähler erkennt nur `;TYPE:`. Bambu Studio schreibt `; FEATURE: …`: In der Sonde (A1,
Kegelplatte) steht keine einzige `;TYPE:`-Zeile, alle 7477 Druckbewegungen unter z 19 sind ohne
Art, `; FEATURE: Support interface` kommt dreimal vor. Für Bambu ist der Zähler daher immer 0, und
der Bambu-Fall besteht aus `0 == 0`. Er bliebe grün, auch wenn Bambu die Spitze nähme
(`.claude/rules/tests.md`, „Ein Verbotstest über eine leere Menge ist immer grün“; bei einem
Rechenergebnis „nicht leer“ zusichern). Die Aussage selbst stimmt (siehe 1).

Der Docstring sagt „dort schreibt Solidon ihn nicht“. Das ist falsch: Die gewählte Spitze steht
in beiden 3MF. Bambu meldet „slicer ignored 1 setting(s): tree_support_tip_diameter“, also einen
Befund `slicer.setting_ignored`. Creality liest sie und baut andere Äste.

Der Testname verspricht „on every tip“, zugesichert ist nur „mehr“.

Gegenprobe: Ohne den Bambu-Eintrag in `NOT_TAKEN_BY_PROGRAM` wird der Test rot (`0 > 0`), nur der
Gleich-Zweig ist leer.

**Fix:**
- Die Art aus `^;\s*(?:TYPE|FEATURE)\s*:` lesen, wie `gcode_auflage.py`.
- Je Programm zusichern, dass unter den Kegeln überhaupt Stütze gedruckt wird.
- Im Nein-Zweig für Bambu gleiche Stützbewegungen zusichern, für Creality gleiche Trennschicht.
- Den Docstring richtigstellen: „Solidon schreibt die Wahl, das Programm übergeht sie.“
- Gut wäre zusätzlich: Trennschicht unter jedem der sechs Kegel zusichern.

### L1 (leicht) — Testlücken, belegt mit Gegenproben

Kopie `scratchpad\rv704\kopie`, `mutanten.py` und `mutanten_ui.py`:

| Mutation | Getestete Dateien | Ergebnis |
|---|---|---|
| ohne `flavour == "orca"` | Rat-Tests | rot (prusa, cura) |
| ohne `tips is not None` | Rat-Tests | rot (few) |
| ohne `roofs > 0` | Rat-Tests | rot (no roof) |
| `< ROOF_TIP_DIAMETER + 10` | Rat-Tests | rot (wide tip) |
| `floor` statt `ceil` | Rat-Tests | rot (`test_the_roof_tip_is…`) |
| `roofs = layers` gestrichen | ganze `test_slice_findings.py` | **grün**, 217 passed |
| Spitze unter Gitter aktiv | `test_print_settings.py`, `test_print_settings_ui.py` | **grün**, 840 / 436 passed |
| Leserzeile in `ORCA_PROCESS` gestrichen | `test_manufacturer`, `test_print_settings`, `test_print_settings_ui` | **grün**, 1041 / 436 passed |
| Prusa ohne `NOT_TAKEN_BY` | `test_print_settings_ui` | rot (dort gemessen) |

**Fix:**
- (a) Ein Fall „0 Trennschichten, flache Decke, Rat schlägt Lagen vor, dann auch die Spitze“,
  oder `roofs = layers` begründet streichen.
- (b) `support.tip_diameter` in `test_the_tree_walls_rest_under_a_grid` aufnehmen.
- (c) Ein `test_the_tip_is_read_back` nach dem Muster von `test_the_tree_walls_are_read_back`
  (`"1.2"` wird 1,2, `"0"` wird fremd).

### ~~L2 — Feld unter Hybrid ohne Wirkung~~ (zurückgenommen)

Ich hatte vermutet, dass die Spitze unter Hybrid (`tree_hybrid`) nichts tut. Gemessen (Elegoo,
Kegelplatte) unterscheiden sich die Druckdateien mit 0,8 und 1,13 (Stützbewegungen 4024 → 4052),
nur ohne Trennschicht. Das Feld wirkt also, und der Rat schweigt dort zu Recht. Kein Fund.

### L3 (leicht) — Regel und Unterlagen

- `.claude/rules/druckrat.md:140-146`: Dass die Spitze plattenweit geht (Maximum über die Teile),
  während Abstand und Trennschichten je Teil gehen, fehlt.
- `app/core/export/slicer_keys.py:506-508`: Dort steht „unter 0,8 bis zur Stützbahn hebt die
  Übergabe sie ohnehin“. `organic_tree_fitted` hebt aber jede Spitze unter der Stützbahn,
  unabhängig von 0,8.
- `app/core/types.py:1402-1406`: „Die Vorgabe ist die … aller gemessenen Herstellerprofile“ — im
  Bestand stehen auch 1,0 bis 2 mm (siehe 1). Richtig wäre „der meisten“.
- `advise.SLICED_PATHS` fehlt `support.tip_diameter`, obwohl der Rat sie aus dem Schnitt setzt.
  Der Wächter `test_every_path_the_cut_decides_makes_the_export_cut_the_part` liest nur
  `_from_geometry` und `_calm_walls`, nicht `_support_contact`. Folgenlos, solange die Spitze
  plattenweit geht; `tree_walls` steht dort.
- Bei Creality sagt der Dialog „kennt diese Einstellung nicht“, obwohl Creality sie liest. Das
  kommt aus dem gemeinsamen Mechanismus und ist hinnehmbar; im Archiv steht es richtig.

## Format, Cache und ältere Stände (Frage des Koordinators, 10:45)

**Ergebnis: keine Erhöhung nötig.** Weder das Projektformat (Worktree 50, welle3 51, nächste
freie 52) noch `CACHE_FORMAT_VERSION` (54) muss steigen.
- **Projekt:** Das Feld steht in `print_settings.support`, `support.tip_diameter` kann in
  `chosen`/`accepted` stehen.
  - Der Leser verwirft unbekannte Schlüssel (`serialise._group_from_data`) und unbekannte Pfade
    (`_known_paths`). Was fehlt, bekommt die Vorgabe der Dataclass.
  - Beim Öffnen gilt nur die eigene Wahl und das Übernommene, alles andere kommt aus der
    Grundlage (`print_settings.on_base`). Ein altes Projekt bekommt die Spitze also aus dem
    Herstellerprofil, nicht aus der 0,8 der Dataclass.
  - Die Migration für Dateien vor Format 36 (`legacy_choices`) hält die fehlende Spitze für die
    Vorgabe, nicht für eine Wahl.
  - Vorbild ist `support.tree_walls` (RM-584), ebenfalls ohne Formatschritt eingeführt.
- **Cache:** `scene/cache.py` enthält keine Druckeinstellungen, die Merker im Rat und in der
  Übergabe hängen nur an `own_part` (eigene Wahl). Keine Erhöhung.

Gemessen mit `sonde_format.py` (Codekopien per `git archive`):

| Fall | Stand | Ergebnis |
|---|---|---|
| A: alte Projekte öffnen | Zweig | `print_settings_v33`, `example_v46`, `example_v49`, `example_v50`: öffnen ohne Fehler, ohne Spitze in der Datei, Satz trägt 0,8. `dose-mit-deckel` (v50, ohne Satz) öffnet. |
| B: neues Projekt schreiben | Zweig | `neu_mit_spitze.p3d`, v50, `support.tip_diameter = 1.13`, `accepted = ["support.tip_diameter"]` |
| C: welle3 vor RM-704 öffnet B | `c7a6f853d`, Format 50 | öffnet; Spitze und Pfad fallen still weg; neu gespeichert ohne beides |
| D: welle3 heute öffnet B | `083dab2f6`, Format 51 | migriert 50 → 51 und öffnet; Spitze und Pfad fallen weg |
| E: 0.5.3 öffnet B | Format 46 | sauber abgelehnt: „Diese Projektdatei ist neuer als das Programm … Ein Update öffnet sie.“ Das gilt für jede Datei aus 0.6.0, nicht wegen dieses Felds. |

Dazu in der Kopie `test_project`, `test_corpus`, `test_cache` und die vier
`test_filament_usage*`: 741 passed, 1 skipped, 1 failed. Der eine Fehlschlag ist
`test_every_corpus_file_has_its_line_in_the_readme`; er braucht `git ls-files`, und die Kopie
ist kein Repository. Im Worktree läuft er grün (1 passed).

**Aber, neuer Punkt (mittel, nicht aus diesem Diff allein): Der Abdruck der Verbrauchsbuchung
ändert sich mit jedem neuen Feld.** `filament_usage.prepare` bildet den Abdruck über alle Werte
von `print_settings_to_data` (`filament_usage.py:224-284`).

Gemessen mit `sonde_abdruck.py`, derselbe Würfel mit denselben Einstellungen (CC2, PLA, ohne
eigene Wahl):

| Stand | Abdruck | Altabdruck |
|---|---|---|
| 0.5.3 | `77d4d8f6…` | `b69fbca5…` |
| welle3 (`c7a6f853d` und `083dab2f6`) | `0ee20626…` | `83a6db3a…` |
| Zweig | `66f3b558…` | `109cb59d…` |

Kein früherer Abdruck steht unter den Altabdrücken eines späteren Stands. Ein
vor dem Update gebuchter Druck wird danach nicht wiedererkannt, und der Hinweis auf eine frühere
Buchung (`ui/filament_usage._legacy_bookings`) greift nicht. Altabdrücke gibt es nur für die
additiven Brim- und Raftfelder.

Seit 0.5.3 sind sieben solche Felder dazugekommen:
- `support`: `spare_ledges`, `bottom_interface_layers`, `interface_spacing`, `tree_walls`,
  `tip_diameter`
- `cooling`: `minimum_speed`, `support_interface_cooling`

Der Bruch gegen 0.5.3 besteht in welle3 also schon. RM-704 fügt ein Feld derselben Art hinzu und
blockiert deshalb nicht.

**Vorschlag:**
- Den Abdruck auf einen Feldbestand festlegen: neue Felder auf ihrem Vorgabewert auslassen, wie
  es `brim_gap` bei 0 schon tut. Oder die Felder seit 0.5.3 als Altabdruck führen.
- Dazu ein Wächter: Jedes neue Feld der Dataclass braucht einen Eintrag dort, sonst rot.
- Vor 0.6.0 klären, weil sonst jede Buchung aus 0.5.x nach dem Update als neu gilt.

## Neuer Punkt (Vorschlag, nicht aus diesem Diff)

Die Plattenwerte der Orca-Familie laufen nicht durch `NOT_TAKEN_BY_PROGRAM`. Nur der Rat und die
Aufteilung je Teil filtern danach, für PrusaSlicer gibt es `for_program`. Eine mitgebrachte Wahl
(zum Beispiel unter ElegooSlicer gewählt, dann zu Bambu gewechselt) geht deshalb als fremder
Schlüssel hinaus, und der Kunde bekommt „nicht übernommen“. Das gilt schon für
`cooling.support_interface_cooling`.
**Vorschlag:** `for_program` auch auf die Platte der Orca-Familie anwenden.

## Gelesen und nicht ausgeführt

Den Bauplan berührt die Änderung nicht: kein §9-Vertrag, kein Dateiformat. Neue Einstellungen
lädt `serialise.print_settings_from_data` mit der Vorgabe nach. Die übrigen Fälle von
`test_real_slicers.py` laufen über das umgebaute `_sliced_tower`; den Umbau habe ich gelesen
(gleiche Rückgabe), die Fälle nicht gefahren.
