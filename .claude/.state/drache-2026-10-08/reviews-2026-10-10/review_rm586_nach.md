# Nachprüfung RM-586 — Feine Schichten nach Detail (Fixrunde rm586b)

Prüfer rv586n. Gegenstand: Worktree `F:\sl-schichten`, Zweig `einstellungen/schichten-rm586`,
Spitze `fb289a8bc` (= origin, enthält origin/welle4 `02213548a`). Fix-Diff `ff4e31e47..ebe3d1756`
(27 Dateien, +840/−150) plus `fb289a8bc` (Karte, 1 Zeile), Merge `af470ec86` gesondert.
Erstreview `review_rm586.md` (F1–F10), Fixbericht `berichte-2026-10-10\rm586b.md`.
Scratch `scratchpad\rv586n\`. Beginn 22:31, Urteil 23:10. Nichts im Worktree geändert.

## Urteil

**Kann landen**, sobald die fünf leichten Restfunde N1–N5 behoben sind; eine weitere
Nachprüfung ist dafür nicht nötig (ein Katalogsatz, Docstrings/Karte/Regel/Begründung/Archiv,
zwei kleine Tests). F1–F7, F9, F10 sind behoben und am echten Slicer bzw. bitgenau nachgestellt;
F8 ist im Changelog und in der Regel ehrlich, im Docstring und in der Begründung noch nicht
ganz (N2). Keine Regression gefunden: ohne Turm und abseits genauer Gleichstände druckgleich
(Korpus 160 Fälle, Drache, Eiffelturm, Kuppe: Kurven gleich), Turmlogik an sechs Druckern
gemessen, Merge sauber.

| Fund | Schwere | Kurz |
|---|---|---|
| N1 | leicht | it: Grund „richiede circa il {share} % in più“ — „Zeit“ fehlt |
| N2 | leicht | F8 halb: Docstring-Ursache falsch, Begründung „erst R 9“ — Grenze flackert zwischen R 8,3 und R 9,6 |
| N3 | leicht | Kein Test fährt `_shallow_faces` über mehr als einen Block (F9-Versatz ungeschützt) |
| N4 | leicht | Karte `slice/CLAUDE.md`, `_fine_layers`-Docstring, Regelsatz „Das Feld sagt es“, Archiv RM-586 nach F2/F4/F8 veraltet |
| N5 | leicht | Druckdialog reicht `shared_layers` an drei Stellen weiter, kein Test dort |

Dazu ein **neuer Punkt außerhalb des Zweigs** (vor v0.2.1, nicht Teil des Urteils): Am XL 2T
meldet die Übergabe „weitere Farben und Materialien werden nicht gedruckt“, gedruckt werden sie
aber — siehe unten.

## Restfunde

### N1 — leicht: Der italienische Grund verliert die Zeit

`app/i18n/locales/it.json:4371`: „Glattere Kuppen: Dieses Teil druckt rund {share} % länger.“ →
„Cupole più lisce: questo pezzo richiede circa il {share} % in più.“ — „richiede … in più“
ohne Gegenstand (Zeit? Material?). Die alte Fassung hatte „di tempo in più“; es, fr, pt, en
nennen die Zeit („tarda“, „de temps en plus“, „demora“, „prints … longer“). Fix (66 Zeichen,
Grenze 70 in `test_every_reason_fits_under_the_table_of_the_print_dialog`): „Cupole più lisce:
circa il {share} % di tempo in più per il pezzo.“ — nicht „questo pezzo dura …“ (liest sich
als Haltbarkeit).

### N2 — leicht: F8 ist im Docstring und in der Begründung noch nicht ehrlich

`app/core/slice/fine_layers.py:110–113` sagt: „Fein wird sie bei 0,2 mm Schicht ab etwa R 9 mm,
bei 0,28 mm ab R 8 — darunter ist ihr flacher Scheitel kürzer als ein Übergang“.
`konzepte/begruendungen/regel-druckrat.md:759–763`: „bekommen Halbkugeln R 6 und R 8 keine
Kurve, erst R 9; bei 0,28 mm ab R 8 … Augen, Knöpfe und Schuppen unter etwa 18 mm Durchmesser
bleiben gleichmäßig.“

Beleg (`kuppen2.py`, `kuppen3.py`, gepinnt, EXIT=0; Halbkugeln Ikosphäre 6, Bahn 0,42):
- Die Ursache stimmt nicht: Bei 0,2 mm ist der flache Scheitel `R·(1 − cos 25,46°)` bei R 9
  0,874 mm, bei R 10 0,971 mm — beide kürzer als ein Übergang (1,0 mm), und beide bekommen eine
  Kurve. Bei 0,28 mm hat R 8 1,344 mm Scheitel gegen 1,4 mm Übergang und bekommt eine. Wirksam
  ist, wie lang der Bereich ist, in dem das über einen Übergang gemittelte Schrägmaß die
  Schwelle hält (R 9: 8,0–9,0 mm, R 8: 7,2–8,0) — er reicht über den Scheitel hinaus nach
  unten und ist in ganzen Schichten gequantelt.
- Die Grenze ist nicht scharf, sie hängt an der Lage des Rasters zum Scheitel. Radiusreihe in
  0,1-mm-Schritten, 0,2 mm Schicht: Kurve bei R 8,3, keine bei 8,4–8,9, Kurve bei 9,0–9,4,
  **keine bei R 9,5** (Bereich 0,8 mm), ab R 9,6 durchgehend. 0,28 mm: 6,9 ja, 7,0–7,1 nein,
  7,2–7,3 ja, 7,4 nein, 7,5–7,6 ja, 7,7 nein, ab 7,8 durchgehend. „erst R 9“ und „unter etwa
  18 mm bleiben gleichmäßig“ stimmen also beide nicht (R 8,3 fein, R 9,5 = 19 mm gleichmäßig).

Regel (`druckrat.md`: „Wirksam ab Kuppen von etwa R 9 mm … Ein Bereich ist mindestens einen
Übergang lang“) und Changelog („flache Kuppen und Schrägen“) stimmen.

Fix: Docstring und Begründung: „Wirksam ist die Mindestlänge: Die Schichten, deren über einen
Übergang gemittelte Schrägfläche die Schwelle hält, müssen einen Übergang lang sein. Bei 0,2 mm
Schicht schafft das eine Kuppe ab R 9,6 immer, unter R 8,3 nie, dazwischen je nach Lage des
Schichtrasters zum Scheitel (R 9,5: 0,8 mm, keine Kurve); bei 0,28 mm ab R 7,8.“ Den
Radiusbereich in den neuen Punkt 1 des Fixberichts (kleine Kuppen) mitnehmen.

### N3 — leicht: Der Blockversatz aus F9 hat keinen Test

`app/core/slice/fine_layers.py:200–218` (`chosen.append(up[keep] + start)`): Erst ab 262 144
Dreiecken gibt es einen zweiten Block. Kein Test kommt dorthin: `test_the_shallow_faces_are_
those_of_the_stable_normals` (`tests/test_slice.py:2940`) nimmt eine Ikosphäre 5 (20 480
Dreiecke), die übrigen Feinschicht-Tests höchstens Ikosphäre 6 (81 920), der Plattformweg
Keile mit 8 Dreiecken. Fiele `+ start` weg, wählten Drache und Eiffelturm still falsche
Dreiecke. Gegenprobe (`mutant\rv586n_mutant.py`, Plugin ersetzt `_shallow_faces` durch die
Fassung ohne `+ start`, `run_mutant.sh`, gepinnt): **217 passed, EXIT=0** über alle Tests zu
feinen Schichten, Turm und Kurve in `test_slice`, `test_export`, `test_advise`,
`test_estimate`, `test_print_settings`, `test_platform_identity`,
`test_slicer_part_settings`. Die Umsetzung selbst ist richtig (Beleg unten, auch mit
Blockgröße 7). Fix: den Test
über `_FACE_BLOCK` parametrisieren (`monkeypatch.setattr(fine_layers, "_FACE_BLOCK", 997)`
neben der Vorgabe), gleiche Erwartung.

### N4 — leicht: Vier Stellen sprechen noch vom alten Stand

- `app/core/slice/CLAUDE.md:23`: „feine Schichten an Kuppen und Details … (`_fine_layers`, nicht
  für Cura, **am Reinigungsturm** oder unter organischen Bäumen …)“ — nach F2 gilt die Sperre nur
  am Turm neben weiteren Teilen (`shared_layers`). Die Karte wurde in der Fixrunde nicht
  nachgezogen (nur die des Exports).
- `app/core/slice/advise.py:2034–2039` (`_fine_layers`): „an Kuppen und **feinen Formen**“ und
  „mit dem Anteil, um den **der Druck** länger dauert“ — F8 hat „kleine Formen“ aus dem Changelog
  genommen, F4 den Anteil dem Teil zugeschrieben.
- `.claude/rules/druckrat.md:194–196`: „… ein Körper allein behält die feinen Schichten neben
  seinem Turm. **Das Feld sagt es** (`slicer_keys.limitation`).“ — `limitation` meldet für
  `layers.fine_layer_height` nur die Bäume (`slicer_keys.py:2010–2022`), nichts zum Turm. Durch
  die neue Satzfolge liest es sich, als sage das Feld den Turmfall.
- `ROADMAP-ARCHIV.md:47737–47740` (RM-586, „Gebaut“): „nicht unter organischen Bäumen und
  **nicht neben einem Reinigungsturm** (beides lehnen die Slicer ab, `Print::validate`; Befund
  und **Satz am Feld**)“ — nach F2 falsch (Einzelkörper behält die Kurve, kein Satz am Feld
  zum Turm), PrusaSlicer an Mehrwerkzeugmaschinen fehlt. Anders als RM-587 und RM-589
  (`ROADMAP-ARCHIV.md:46898`, `:47392`, `:47403`) trägt der Eintrag keinen Absatz
  „Review (`review_rm586.md`) behoben“, und er nennt nur `rm586.md`, nicht `rm586b.md`.

Fix: Karte „… nicht für Cura, am Turm neben weiteren Teilen (`shared_layers`) oder unter
organischen Bäumen …“, „Kuppen und flachen Schrägen“; Docstring „an Kuppen und flachen
Schrägen“, „um den das Teil länger druckt“; Regel „Unter Bäumen sagt es das Feld
(`slicer_keys.limitation`).“ vor den Satz über den einzelnen Körper; im Archiv einen Absatz
„Review (`review_rm586.md`) behoben: F1 … F10“ (Turm nur neben weiteren Objekten, PrusaSlicer
an Mehrwerkzeugmaschinen mit Messwerten, Grenze ohne Winkelfunktion, Blöcke 272 → 65 MB) und
„Nachprüfung (`review_rm586_nach.md`)“ mit Bericht `rm586b.md`. Budget: Karte slice 21 970
von 25 600 Byte, `druckrat.md` 21 101 von 30 720.

### N5 — leicht: Die Turmsperre im Druckdialog ist ungeprüft

`app/ui/print_settings_dialog.py:1606` (`self.shared = shared_layer_plates(...)`) und die drei
Weitergaben `:1691`, `:1835`, `:1914`. Kein Test berührt sie (`grep shared_layers|fine_layers_tower`
in `tests/`: nur `test_advise.py`, `test_export.py`; in `test_print_settings_ui.py` kein
`fine_layer`); der vorhandene Turmtest des Dialogs
(`test_beside_a_tower_the_dialog_proposes_the_gap_the_file_gets`) prüft nur den Stützabstand.
Gegenprobe (`mutant\rv586n_dialog.py`: `shared_layer_plates` im Dialog gibt immer ∅,
`run_mutant_dialog.sh`, gepinnt, ohne xdist): `test_print_settings`, `test_print_settings_ui`
(ohne Fenster), `test_slicer_part_settings`, `test_advise`, `test_export` **1 643 passed,
4 skipped, EXIT=0**.
Fehlte eine Weitergabe, schlüge der Dialog feine Schichten vor, die der Export dann mit Befund
verwirft. Heute stimmt es (Sonde `f12.py` rechnet den Rat über `_AdviceWorker._calculate`:
Turmplatte mit zwei Teilen kein Rat, Einzelkörper Rat). Fix: mit `_advice_of`
(`tests/test_print_settings.py:8322`) und einem Setup der Orca-Familie (`_native_process`
gepatcht auf `enable_prime_tower`): bemalte Kuppe neben Klotz → keine Zeile
`layers.fine_layer_height`, Kuppe allein → Zeile.

### Zurückgenommen: zweite Turmfrage als Kosten oder Zwilling

Vermutet: `shared_layer_plates` fragt für die Orca-Familie den Turm ein zweites Mal
(`same_layers_required` → `tower_cause`, `writer.py:3170–3172` neben `_tower_causes`
`writer.py:3014–3018`). Sonde `zwilling.py` (gepinnt, EXIT=0): In allen sechs Fällen
(ElegooSlicer CC2, Bambu P1S; allein, paar, zwei Platten) ist `shared` genau „Turmplatten mit
mehr als einem Körper“. Einzeln gerufen kostet die zweite Frage am ElegooSlicer 47–109 ms CPU,
**im einen Lesedurchgang, in dem Dialog (`_AdviceWorker.work`) und Export sie stellen, 0–16 ms**
(Timerauflösung). Beide teilen `tower_cause`; doppelt ist nur der Aufrufausdruck. Kein Fund.

## F1–F10 im Einzelnen

**F1 — behoben.** `handover.same_layers_required`/`_prusa_tower` (`handover.py:3546–3586`),
`writer.shared_layer_plates` (`writer.py:3153–3173`). Sonde `f12.py` (Weg des Druckdialogs,
`matrix_unit.plate_run`, gepinnt, EXIT=0), Kuppe R 20 + Klotz, feine Schichten 0,1 vom Kunden
gesetzt, PrusaSlicer 2.9.6:

| Fall | `shared` | Rat fein | Befund | Kurve | G-Code |
|---|---|---|---|---|---|
| XL 2T, zwei Spulen | {0} | keiner | an Kuppe | keine | 101 Höhen, Turm 6 129 Bahnen, T0/T1, 51,6 min |
| XL 2T, eine Spule | {0} | keiner | an Kuppe | keine | 100, kein Turm, T0, 32,6 min |
| XL 5T, eine Spule | {0} | keiner | an Kuppe | keine | 100, 32,6 min |
| MK4S MMU3, eine Spule | {0} | keiner | an Kuppe | keine | 100, 18,4 min |
| MK4S HF0.4 (ein Werkzeug) | {} | 0,1 + Decke 0,8 an „Kuppe“ | — | `object_id=1` | Kuppe fein 17,2–20,03 |
| XL 2T, bemalte Kuppe allein | {} | 0,1 + Decke 0,8 | — | `object_id=1` | 113 Höhen, 27 fein, Turm 1 650, T0/T1 |

Vorher (Erstreview): kein G-Code, „The Wipe tower is only supported if all objects have the same
variable layer height“. Befundtext dort: „Mit Reinigungsturm verlangt PrusaSlicer gleiche
Schichten für alle Teile neben „Kuppe“. Auf einer eigenen Platte gelten die feinen.“ — der Weg
hinaus stimmt (Zeile XL 2T allein). Der G-Code der Turmfälle bestätigt die Annahme der
Erkennung: `; nozzle_diameter = 0.4,0.4`, `; wipe_tower = 1`.

**F2 — behoben.** Gleiche Sonde, Orca-Familie, bemalte Kuppe (obere Hälfte Spule 2):

| Fall | `towers` | `shared` | Rat fein | Befund | Kurve | G-Code |
|---|---|---|---|---|---|---|
| Bambu P1S, Kuppe allein | {0} | {} | „… rund 12 % länger“ | — | `object_id=1` …17,8;0,1;20;0,1 | 113 Höhen, 28 fein (0,1–0,176), Turm 2 700, T0/T1 |
| Bambu P1S, Kuppe + Klotz | {0} | {0} | keiner | nur an Kuppe | keine | 100, Turm 6 850 |
| ElegooSlicer CC2, allein | {0} | {} | „… rund 12 % länger“ | — | dieselbe | 113, 28 fein, Turm 15 130, T0/T1 |
| ElegooSlicer CC2, + Klotz | {0} | {0} | keiner | nur an Kuppe | keine | 101, Turm 28 531 |

Der Befund steht nur am Teil, das eine Kurve verliert (`_layer_heights` rechnet erst die Kurve,
`writer.py:3088–3099`); der Klotz bekommt keinen Satz. Dasselbe gilt jetzt für den Baumbefund.

**F3 — behoben.** `tests/test_real_slicers.py:1939–1943`: ohne Lagenzähler zählen die Höhen mit
Vorschub, die Grenze gilt allen Programmen. `-k test_fine_layers_arrive_where_solidon_says`,
gepinnt: **6 passed, 78 deselected, EXIT=0** (135 s).

**F4 — behoben** (de, en, es, fr, pt); it siehe N1. Rat und Changelog nennen das Teil; Sonde:
„Glattere Kuppen: Dieses Teil druckt rund 12 % länger.“ (Bambu, Elegoo), 10 % (MK4S), 9 % (XL 2T).

**F5 — behoben.** `.claude/.state/drache-2026-10-08/slicer_fein.py` versioniert, Modell `paar`
baut die Platte selbst (dieselben Körper wie meine Sonde), Kommentar
`tests/test_slicer_part_settings.py:617` zeigt dorthin.

**F6 — behoben.** `dateiformat.md`: „Geprüft an der Modellbahn, nicht an der Stütze“ zurück;
„nicht unter organischen Bäumen, am Turm neben anderen Teilen, für Cura“. 30 715 von 30 720
Byte — jede weitere Zeile dort braucht eine Verschiebung. `AS_HEIGHT_PROFILE` ist aus der Regel
gefallen, steht aber in Karte und `karte-app-core-export.md` (nicht verloren).

**F7 — behoben.** `_step_cosine` und `exact_cos_degrees` statt `math.atan2/cos`
(`fine_layers.py:93–119`, `:196–216`); `math.sqrt` und `math.pi` bleiben (zugelassen). Sonde
`f7_f9.py` (gepinnt, EXIT=0), alter Stand aus `ff4e31e47` daneben geladen, `platform_noise`
Muster 0–3:

| Keil, h/Bahn | alt: still | alt kippt (Muster 0–3) | neu: still | neu kippt |
|---|---|---|---|---|
| 1:2, 0,2/0,4 | 670,8 mm², Kurve | –, ja, –, ja | 0, keine | nie |
| 1:2, 0,1/0,2 | 1 341,6 mm², Kurve | –, ja, –, ja | 0, keine | nie |
| 1:3, 0,2/0,6 | 948,7 mm², Kurve | ja, ja, ja, ja | 0, keine | nie |
| 1:3, 0,1/0,3 | 948,7 mm², Kurve | ja, ja, ja, ja | 0, keine | nie |
| 1:2, 0,15/0,3 | 670,8 mm², Kurve | –, ja, –, ja | 0, keine | nie |

Der neue Weg `fine_layers` in `_WAYS` ist still = verrauscht für alle vier Muster; er fängt
einen Rückfall in der Auswahl über den 1:3-Keil (kippt schon mit Muster 0, das der Test nimmt)
und einen im Schwellwert über `stepped_area_worth` im Abdruck. Druckgleich (alt gegen neu,
`korpus2.py`, `eiffel.py`): 38 Korpusnetze × 4 Raster = **160 Fälle, 0 verschieden**; Drache
und Kuppe Auswahl bitgleich; Eiffelturm bei Bahn 0,4 und 0,2 drei Dreiecke weniger — genau auf
der Grenze (26,565051° = atan 0,5), zusammen 0,0013 mm², Kurve unverändert. Größte Abweichung:
keine in einer Kurve.

**F8 — teilweise**, siehe N2. Changelog „flache Kuppen und Schrägen“ in allen sechs Sprachen,
Regel mit „etwa“: stimmen.

**F9 — behoben.** Sonde `f7_f9.py`: Blöcke (`_FACE_BLOCK` = 2¹⁸) gegen dieselbe Funktion am
Stück **bitgleich** (Indizes und Flächen als `uint64`) an Kuppe, Eiffelturm, Drache bei
0,2/0,42 · 0,2/0,4 · 0,1/0,2 · 0,28/0,42; an der Kuppe auch mit Blockgröße 7 bitgleich.
Spitze (tracemalloc): Drache **272,4 → 64,5 MB** (0,28/0,42: 65,8), Eiffelturm 29,7 → 25,5,
Kuppe 1,4 → 1,4. CPU Drache 0,31–0,39 s gegen 0,36–0,48 s am Stück (unter Fremdlast). Test
fehlt: N3.

**F10 — behoben.** es: „Con soportes en cuadrícula valen las capas finas.“; die übrigen
„rejilla“ im Katalog meinen das Rechenraster, nicht die Stützart.

## Prüfpunkt 2: Was zählt als Objekt, wen trifft die Prusa-Erkennung

- **Objekt = Körper der Platte im ganzen Auftrag.** `_assembly_plates(bodies)` gruppiert nach
  `body.plate`; der Export fragt mit `every` = Auftrag + Platte (`writer.py:2590–2598`), der
  Dialog mit allen Körpern der gewählten Platten (`_plate_bodies`). Geschrieben wird je Körper
  genau ein `object`/`item` (`writer.py:2863–2877`, `threemf.py:870–941`), keine Instanzen
  (`instances_count` immer 1), Kopien sind eigene Körper. Eine Stützsperre ist Komponente bzw.
  Bereich desselben Objekts und zählt nicht. Mehrere Platten: je Platte eine eigene Zählung,
  und die Slicer prüfen je Platte (Orca: eine `Print` je Platte; PrusaSlicer bekommt im
  Druckdialog je Platte einen Lauf). Gezählt werden höchstens mehr Objekte, als der Slicer
  sieht (Auftrag ⊇ geschrieben) — das sperrt im Zweifel, nie zu wenig.
- **Prusa-Erkennung** = Bedingung von 2.9.6 (`wipe_tower` ∧ ¬`spiral_vase` ∧ mehr als ein
  Eintrag in `nozzle_diameter`), gelesen aus der aufgelösten Kette, die Solidon nicht
  überschreibt (`wipe_tower`, `spiral_vase` schreibt die Übergabe nicht; der G-Code des XL 2T
  trägt `nozzle_diameter = 0.4,0.4`). Ein Einwerkzeugdrucker hat einen Eintrag und wird nie
  gesperrt (MK4S HF0.4 gemessen); XL 2T, XL 5T, MK4S MMU3 gemessen gesperrt. Ohne
  Prozess/Drucker des Bestands keine Kette → keine Sperre, dann gilt PrusaSlicers Vorgabe
  `wipe_tower = 0` (laut Fixbericht mit `--save` gemessen). SuperSlicer läuft als `prusa` durch
  dieselbe Prüfung (Fork von PrusaSlicer; nicht gemessen, Heimdrucker Mini hat ein Werkzeug).
  `wipe_tower` und `spiral_vase` schreibt Solidon nirgends (`grep` über `app/`), die Kette ist
  also, was der Slicer prüft.
- **Andere Familien:** `shared_layer_plates` gibt für Cura und „other“ ∅, `_layer_heights`
  kehrt ohne 3MF-Leser sofort zurück, `_fine_layers` lehnt Cura ab;
  `test_cura_gets_no_height_curve` grün. Orca-Familie geändert nur wie beabsichtigt (F2).
  `whole_layers` bleibt für die Rundung des Stützabstands (RM-622) und wird an allen
  Aufrufern weiter gesetzt (Export, `_served_elsewhere`, Dialog dreimal).

## Prüfpunkt 3: Changelog

Beide Punkte unter `## 0.6.0`, Abschnitt Drucken/Übergabe, am Ende, in allen sechs Sprachen in
gleicher Lage; kein `## 0.6.1` mehr. Längen (Zeichen mit „- “): de 161/137, en 157/117,
es 158/145, fr 186/154, it 157/149, pt 155/152 — alle unter 200. Eigenschaft statt Behebung
richtig (kein `v0.6*`-Tag). Liest sich nicht nach KI. Inhalt stimmt mit dem Rat überein
(„wie viel länger das Teil dann druckt“).

## Prüfpunkt 4: Merge, Tests, Budgets

- **Merge `af470ec86`:** `git merge-tree --write-tree 02213548a ebe3d1756` ergibt genau den Baum
  des Merges (`00a4b9058…`), `git show --cc` ohne Auflösung — sauber. origin/welle4 ist seither
  auf `ac244486b` (fix/intel-mac, 6 Dateien in perceive/scene, ohne Berührung); Probemerge mit
  dem Zweig konfliktfrei.
- **Tests am Endstand** (gepinnt, `-n 6`, ohne Fenster/Renderer/Leistung/Slicer, 47 Dateien:
  die Auswahl des Fixberichts ohne `test_transform`/`test_repair`, dazu `test_print_findings`, `test_print_contract`,
  `test_prusa_cli_warnings`, `test_native_keys`, `test_slicer_profiles`, `test_slicer_verify`,
  `test_gcode`, `test_hard_rules`, `test_errors`, `test_core_isolation`,
  `test_print_settings_ui` (ohne Fenster), `test_print_equal`, `test_cache`; darin die
  Pflichtliste des Auftrags): **7 562 passed, 30 skipped, EXIT=0** (253 s). `affected_tests.py`
  meldet für jede Fixdatei „das ist die Suite“ (430/452), deshalb gezielt.
- Slicertest feine Schichten: 6 passed, EXIT=0 (oben). ruff check 0, ruff format --check 0
  (1 214 Dateien), mypy 0 (375 Dateien).
- **Budgets:** `dateiformat.md` 30 715/30 720, `druckrat.md` 21 101/30 720, Karte export
  25 431/25 600, Karte slice 21 970/25 600, `tests/CLAUDE.md` 25 523/25 600 — alle in der
  Grenze (`test_directory_docs` grün), aber `dateiformat.md` und die Exportkarte ohne Luft.

## Neuer Punkt (außerhalb des Zweigs, für das Register)

**PrusaSlicer mit Werkzeugwechsler: Die Übergabe behauptet, die zweite Farbe werde nicht
gedruckt.** `handover.py:2903–2933` (`slicer.overrides_unreachable`, seit `1261935fc`, in
v0.2.1 und später): „Diese Übergabe verwendet nur das erste Filament, weitere Farben und
Materialien werden nicht gedruckt. OrcaSlicer oder Bambu Studio können mehrere.“ Am XL 2T mit
Kuppe (Spule 1) und Klotz (Spule 2) steht der Befund (Sonde `f12.py`, Fall `xl2t_zwei`, auch im
Erstreview `rv586\xl.txt`), aber der G-Code druckt den Klotz mit T1 (je 100× Perimeter, äußerer
Perimeter, Füllung unter T1, `M486 S1`) und baut den Turm. Wahr ist nur: Die Filamentwerte der
zweiten Spule reisen nicht mit (`; filament_settings_id = "Generic PLA @XL"`, ein Eintrag,
PrusaSlicer verlängert ihn auf beide Werkzeuge). Vorschlag: an Druckern mit mehreren Werkzeugen
(`nozzle_diameter` mit mehreren Einträgen in der Kette) den Satz auf die Werte beschränken
(„Die zweite Spule druckt mit den Werten der ersten …“) oder die Filamentwerte je Werkzeug
schreiben; Slicertest am XL 2T.

## Läufe (alle gepinnt `FFFFF0FF`, Exit im Ausgabefile)

| Sonde/Lauf | Datei | Ergebnis |
|---|---|---|
| Tests gezielt | `tests_lauf.sh` → `tests_lauf.txt` | 7 562 passed, 30 skipped, EXIT=0 |
| Slicertest feine Schichten | `run_slicertest.sh` → `slicertest.txt` | 6 passed, EXIT=0 |
| F1/F2 an sechs Druckern | `f12.py`, `run_f12.sh` → `f12_alle.txt`, `f12_alle\f12.json` | 10 Fälle, alle G-Code, EXIT=0 |
| F7/F9 | `f7_f9.py` → `f7_f9.txt` | EXIT=0 |
| Eiffelturm-Gleichstände | `eiffel.py` → `eiffel.txt` | EXIT=0 |
| Korpus alt/neu | `korpus2.py` → `korpus2.txt` | 160 Fälle, 0 verschieden, EXIT=0 |
| Kuppenschwelle | `kuppen2.py`, `kuppen3.py` → `kuppen2.txt`, `kuppen3.txt` | EXIT=0 |
| Zweite Turmfrage | `zwilling.py` → `zwilling.txt` | 6/6 gleich, im Durchgang 0–16 ms, EXIT=0 |
| Mutante ohne Blockversatz | `run_mutant.sh` → `mutant.txt` | 217 passed (Lücke belegt), EXIT=0 |
| Mutante Dialog ohne `shared` | `run_mutant_dialog.sh` → `mutant_dialog.txt` | 1 643 passed, 4 skipped (Lücke belegt), EXIT=0 |
| ruff, format, mypy | `ruff.txt`, `fmt.txt`, `mypy.txt` | je 0 |
