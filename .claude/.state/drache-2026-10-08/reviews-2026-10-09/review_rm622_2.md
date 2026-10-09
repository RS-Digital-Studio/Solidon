# Nachprüfung RM-622, zweite Runde (`F:/sl-turm`, `fafcd4841..f597ffbd4`) — solidon3d-review, 09.10.2026

Umfang: drei Commits (3ac1c73b4 Turm, f605411f9 Turmfrage je Auftrag, f597ffbd4 organische Bäume),
Diff vollständig gelesen, dazu die berührten Stellen in `advise.py`, `handover.py`, `writer.py`,
`slicer_keys.py`, `print_settings_dialog.py`, Regel `druckrat.md`, `dateiformat.md`, Begründung,
Changelog. Ausgeführt: ruff check und format über die zehn Python-Dateien (grün), 149 gezielte
Kerntests (`-k tower|organic|under_trees|…`, grün), acht Sonden über `_AdviceWorker` und
`write_assembly` (Scratchpad `rm622_2/test_sonden2.py`, Ausgaben `lauf1.txt` bis `lauf3.txt`).
Nicht gefahren: die vier neuen Fenstertests (nur beim Release), keine Leistungsmessung.

## Stand der Befunde aus den Vorrunden

**Runde 1 (`review_rm622.md`)**

| Befund | Stand | Beleg |
|---|---|---|
| M1 Gegenproben der drei Aufrufstellen | behoben | dritter Körper, `row.parts`, `accepted_parts`: `test_print_settings_ui.py:11182`; Export mit `job=`: `test_print_settings.py:9118`. Beide wären ohne `whole_layers` an `_with_parts`/`_accepted_targets`/`_served_elsewhere` rot (Tische verlangten 0,10/0,12 statt 0,16) |
| M2 Kosten je Platte | behoben (Aufbau; nicht nachgemessen) | `_tower_causes` in `single_read` (`writer.py:2891–2907`), Arbeiter ganz im Durchgang (`print_settings_dialog.py:1480–1482`), Export ein Durchgang (`writer.py:2526–2544`), Turm einmal je Auftrag an `_served_elsewhere`; `single_read` ist threadlokal und verschachtelbar (`slicer_profiles.py:99–125`) |
| L1 `ExternalToolError` in `_native_process` | behoben | `handover.py:3071–3075`, Test `test_print_settings.py:9188` (ohne Fang rot); die Grundlage meldet die Kette (`manufacturer.py:2346–2350`, `slicer.process_unreadable`) |
| L2 Zwillinge Turm/ganze Schicht/rundet | behoben | `_tower_causes` von `tower_plates` und `_tower_cause` geteilt; `advise.in_whole_layers` in `handover.py:3055`, `slicer_keys.py:1660`, `writer.py:2940`, `advise.py:1043`; `rounds_to_whole_layers` in `advise.py:995`, `:1042`, `slicer_keys.py:1592`. Neuer Zwilling siehe M3 |
| L3 Turm über den Auftrag | behoben | `writer.py:2520–2527` (`every` aus `job` und `chosen`) |
| L4 Testtexte, Bandgrenze, Herkunft | behoben | `test_print_settings.py:9004–9005`; 0,18 in `test_slice_findings.py:1609`; Herkunft `:1499–1500`, gegen `materials.toml:55–57`, `:70–72` geprüft |
| L5 Register, „Band“ | teilweise | Regeltext geklärt (`druckrat.md:80–87`); RM-622 weiter weder in `ROADMAP.md` noch in `ROADMAP-ARCHIV.md` (L6 unten); Begründung sagt weiter „im Band“ (L8) |

**Runde 2 (`review_rm622_baeume.md`)**

| Befund | Stand | Beleg |
|---|---|---|
| M1 Dialog und Export fragen mit verschiedener Art | teilweise | Elegoo-Fall stimmt und ist geprüft (`test_print_settings_ui.py:11320`); der Dialog fragt aber weiter jeden Körper mit dem übernommenen Stil — M2 unten |
| M2 Filter je Körper | behoben | `print_settings_dialog.py:1578–1584`, Test `:11290` (mit Plattenfilter rot, Stil der Platte wäre „Baum“) |
| M3 Ursache „Bäume“ je Datei | behoben | `_gaps_between_layers` je Teil (`writer.py:2928–2946`), Test `test_print_settings.py:9290`; Nebenwirkung L1 unten |
| M4 eine Auskunft je Programm | teilweise | `organic_styles` (`handover.py:3113–3151`) kennt SuperSlicer, `tree_hybrid`/`tree_slim`/`tree_strong`, Prusa „automatisch“; `slicer_keys.limitation` leitet dieselbe Frage neu her — M3 unten |
| L1 Satz am Feld | behoben, aber als Zwilling | M3 unten |
| L2 Abstand setzt Baumvorschlag voraus | **nicht behoben** | M1 unten (Sonde 1 und 8) |
| L3 Docstrings | weitgehend behoben | Reste in L8 |
| L4 Tests zu M1–M3 | behoben | eine leere Zusicherung (L3 unten) |
| L5 Anycubic-Wortlaut | behoben | Texte behaupten keine Lagenzahl mehr |
| L6 Ausweg, Changelog | teilweise | „Mit Gitter gilt er genau.“ steht (`writer.py:2822–2823`); die Changelog-Zeile zur unteren Trennschicht verspricht sie weiter pauschal (L7) |

## Mittel

**M1 — Wählt der Kunde „Baum“ ab, verliert das Teil Abstand und untere Trennschicht für sein
Gitter** (Vorrunde L2, nicht behoben, Rückschritt gegen `fafcd4841`).
`advise.py:1263–1272` fragt den Kontakt mit dem *vorgeschlagenen* Stil, `writer.py:1406–1413` und
`print_settings_dialog.py:1581–1584` filtern die untere Trennschicht nach ihm — im Dialog wie im
Export, auch wenn die Stützart nicht übernommen wird. Die Zeilen sind ausdrücklich einzeln
abwählbar (`print_settings_dialog.py:8224–8227`). Beleg Sonde 8 (Bambu, Prozess mit Gitter, PETG,
eigenes Gitter, untere Lagen 0, Kinn und Tisch; „Stützart“ abgewählt, alles andere übernommen):
Zeilen `z_gap 0,28 · Tisch`, `untere Trennschichten 2 · Tisch`; Datei: Kinn `{}` — es druckt Gitter
auf dem Modell mit 0,2 mm und ohne untere Trennschicht. Gegenprobe ohne organische Bäume (Stand
vorher): Kinn `support_top_z_distance 0.28`, `support_interface_bottom_layers 2`. Sonde 1 (Kinn
allein, Orca): einzige Zeile „Stützart: Baum“; ohne Baum-Auskunft rät derselbe Körper 0,28.
Warum: Kern von RM-583 (Abstand je Material) fällt auf dem vorgesehenen Abwahlweg still weg; der
Kunde sieht keinen Hinweis. Fix: Abstand und untere Trennschicht nur dann mit dem vorgeschlagenen
Stil fragen, wenn er übernommen wird — im Export, wenn `support.style` nicht in `accepted` steht
(oder mit anderem Wert), mit `settings.support.style`; im Dialog beim Abwählen der Zeile Stützart neu
fragen (abgewählte Pfade an den Arbeiter). Test: Sonde 8 als Testfall, Kinn bekommt 0,28 und 2.

**M2 — Der Dialog fragt jeden Körper mit dem übernommenen Stil, der Export nur den Körper, der
ihn verlangt** (Rest von Vorrunde M1, Rückschritt gegen `fafcd4841`).
`handover.asked_for_contact` (`handover.py:1469–1496`) setzt nur `CONTACT_PATHS` auf die
Grundlage; `support.style` bleibt übernommen, und der Arbeiter (`print_settings_dialog.py:1499–1516`)
rechnet den Tisch als Baum. Der Export gibt den Baum je Teil nur dem Kinn (`writer.py:1415–1431`,
Kette über `accepted`), der Tisch druckt das Gitter der Platte. Seit RM-622 hängen Abstand und
Filter am Stil, deshalb verschwinden Zeilen. Beleg Sonde 7 (wie oben, PETG): Schritt 1 `z_gap 0,28 ·
Tisch`, `untere 2 · Tisch`; nach Übernahme nur der Stützart sind beide Zeilen weg; Datei: Tisch ohne
Abstand und ohne untere Trennschicht (Platte 0,2 und 0, `normal(auto)`); alles auf einmal
übernommen: Tisch 0,28 und 2. Dasselbe trifft jeden Körper, der zu einem Projekt mit schon
übernommenem Baum dazukommt. Warum: `druckrat.md:94–95` („fragt sie wie der Export gegen die
Grundlage“); die Datei hängt von der Reihenfolge des Übernehmens ab. Fix: `asked_for_contact`
setzt auch `support.style` je Teil auf `split.base`, wie der Export fragt; kein Gegenzeilen-Risiko,
weil `combine` gegen den übernommenen Stil vergleicht. Test: Sonde 7 zweistufig, Tisch behält 0,28
und 2.

**M3 — Feldsatz und Rat leiten „organischer Baum?“ getrennt her und widersprechen sich**
(Rest von Vorrunde M4, `zwillinge.md`: ungewollter Zwilling).
`slicer_keys.limitation` (`slicer_keys.py:1670–1689`) prüft `style == "tree"`, Familie und
SuperSlicer; `handover.organic_styles` (`handover.py:3113–3151`) dazu den Stil des
Herstellerprozesses und „automatisch“. Beleg Sonde 2 (kein Slicer, Orca, Baum, PETG 0,2): Rat
0,28, Feld „Unter Baumstützen rechnet der Slicer … in ganzen Schichten zu 0,20 mm.“; Sonde 3:
Prozess `tree_hybrid` bzw. `tree_slim` — Rat lässt 0,28, Feld sagt Rundung; Elegoo „automatisch“
mit `tree(auto)` — Rat 0,2, Export meldet Rundung, Feld schweigt. Dazu verspricht der Docstring
`handover.py:3132–3133` „Ohne Programm gilt die Familie“, der Code gibt ohne `setup` die leere
Menge (`:3136`). Warum: Der Kunde liest am Feld das Gegenteil des Vorschlags daneben. Fix:
`limitation` bekommt `organic` vom Aufrufer (Dialog: `handover.organic_styles(setup, profile)` je
Profilantwort im Durchgang oder die Menge des Arbeiters) und fragt `settings.support.style in
organic`; den Fall ohne Slicer einmal entscheiden und Docstring wie Feld danach richten. Test:
Feldsatz und Rat für `tree_hybrid`, Elegoo-„automatisch“ und ohne Slicer gleich.

## Leicht

**L1 — Unter Bäumen allein schaltet die Datei die eigene Stützschichthöhe still gegen den
Hersteller ein.** `writer.py:2784–2788` rechnet den Schalter aus allen geschriebenen Abständen,
`:2829–2831` unterdrückt dann `slicer.support_layers_freed` (`exact` falsch). Sonde 4 (Orca,
Prozess mit `independent_support_layer_height 0`, Baum, 0,28): Datei `1`, Befunde nur
`export.support_gap_rounded`. Unter organischen Bäumen wirkt der Schalter laut Messung nicht; er ist
eine unerklärte Abweichung vom Herstellerprofil (Grundsatz in `handover.py:3182–3183`), und
`dateiformat.md:333` sagt, ein Abstand zwischen zwei Schichten werde mit eigener Höhe gedruckt.
Fix: Schalter nur aus Teilen, die nicht organisch drucken (dieselbe Je-Teil-Frage wie
`_gaps_between_layers`), Regel nachziehen; Test: Baum-Platte mit 0,28 ohne Schalter.

**L2 — PrusaSlicer: Unter Bäumen nennt der Export die Rundung nicht.** Der Satz entsteht nur
innerhalb `free_support_layers` (`writer.py:2809–2828`), und der gilt nur für Orca
(`slicer_keys.py:1595–1604`). Sonde 5 (PrusaSlicer, Baum, 0,28 bei 0,2): Feld sagt Rundung,
`organic_styles` `{"tree"}`, Export ohne `export.support_gap_rounded`. `druckrat.md:86–87`
verspricht den Satz für „jedes Programm unter organischen Bäumen“; der Docstring
`slicer_keys.py:1600` („PrusaSlicer legt die Kontaktschicht ohnehin in den gewünschten Abstand“)
stimmt unter Bäumen nicht mehr. Fix: `_gaps_between_layers` auch für Prusa fragen und den Satz
geben, Docstring ergänzen; Test.

**L3 — Leere Zusicherung.** `test_print_settings.py:9283` (`slicer.support_layers_freed` nicht
dabei) kann nicht rot werden: Der Prozess der Attrappe (`:9261`) führt
`independent_support_layer_height` nicht, und `support_layers_findings` gibt dann immer `[]`
(`handover.py:3187`). Fix: Attrappe mit `"independent_support_layer_height": "0"`, nach L1 auch den
Schalter in der Beilage zusichern (`tests.md`: „Eine Zeile, deren Entfernen nichts rot macht, prüft
nichts.“).

**L4 — Der Prusa-Zweig von `organic_styles` ist ungeprüft.** `handover.py:3141–3145` und
`_prusa_process_style` (`:3154–3162`) laufen in keinem Test: `test_organic_trees_are_known_per_program`
(`test_print_settings.py:9232`) fragt ohne `profile`. Fix: Fall mit gepatchter
`manufacturer.prusa_chain` (`support_material_style = organic` → `{"tree", "auto"}`) und einer, die
`ExternalToolError` wirft (→ `{"tree"}`).

**L5 — Kein Slicertest mit echtem Programm für das Gemessene.**
`IGNORED_UNDER_TREES_BY_PROGRAM` (`slicer_keys.py:1152–1162`) und die Rundung unter Bäumen und am
Turm beruhen auf Messungen, die nur in `.claude/.state/drache-2026-10-08/kontakt_je_teil.py` stehen;
`tests.md` („Neues bringt seinen Test für diese Auswahl mit … Slicertest mit echtem Programm“). Ein
Programmupdate fiele niemandem auf. Fix: `@pytest.mark.slicer`-Fälle in `test_real_slicers.py`
(zwei PETG-Tische unter Baum ohne Zwischenebenen; Bambu ohne untere Lagen unter Baum, Elegoo mit).

**L6 — RM-622 steht weder im Register noch im Archiv** (aus beiden Vorrunden offen). `grep RM-622`
in `ROADMAP.md` und `ROADMAP-ARCHIV.md`: kein Treffer; Code, Tests und Unterlagen nennen die Nummer
rund dreißigmal. Fix: Registerzeile jetzt oder Archiveintrag mit Nachweis beim Landen.

**L7 — Changelog verspricht die untere Trennschicht weiter überall** (`changelog/de.md:83` und die
fünf Geschwister): Unter Bäumen schlägt Solidon sie bei Bambu Studio, Creality Print, Anycubic
Slicer Next und PrusaSlicer nicht mehr vor. Fix: „bei Gitterstützen“ oder ein Halbsatz zu Bäumen,
sechs Sprachen.

**L8 — Unterlagen ungenau.** `konzepte/begruendungen/regel-druckrat.md:487` „ganze Schichten im
Band“ (das Vielfache liegt in den Materialgrenzen, nicht in `SUPPORT_GAP_BAND`); `:506–508`
„ElegooSlicer und OrcaSlicer zwei; dort schlägt Solidon sie … nicht vor“ — „dort“ zeigt auf die
falschen Programme; `:514` „Der Schalter richtet sich …“ hängt jetzt im Baum-Absatz und behauptet
einen Befund, den es unter Bäumen nicht gibt (L1). `advise.py:981–986`: unter Bäumen zitiert der
Docstring `SupportMaterial.cpp` (organisch ist `TreeSupport3D`) und nennt nur die Orca-Familie,
nicht PrusaSlicer. Fix: Sätze richten, Absatz trennen.

## Ohne Befund geprüft

Memo-Schlüssel von `part_advice` vollständig (`writer.py:1351–1361`: Turm, Bäume, Programm,
Übernahmen; Test `test_print_settings.py:9390` ohne `whole_layers` im Schlüssel rot); Fehlerweg
`ExternalToolError` samt Prusa-Kette; Texte: drei neue Sätze mit 8, 11 und 18 Wörtern, in allen
fünf Katalogen, Platzhalter und Feldnamen je Sprache wie im Changelog, Genus in fr/it/es/pt stimmt;
Changelog-Punkt unter `## 0.6.0` in sechs Sprachen an gleicher Stelle; Regeln 1–22 im Umfang ohne
Verstoß (kein Qt im Kern, Fließkomma über `is_close`, keine Streuzahl, Texte über `_()`), Bezeichner
englisch; Sollwerte in `test_slice_findings.py` nachgerechnet; Konsolenweg liest den Schalter aus der
Beilage; SuperSlicer rundet nicht. Sonde 6 (Orca, Baum übernommen, Kinn und Tisch): Zeile
„0,2 · Kinn“, Datei Kinn 0,2 unter Baum, Tisch nur `enable_support` mit dem Abstand der
Platte — stimmig.

Drei mittlere Befunde — Nachprüfung nach den Fixes nötig. Kann das so rein: nein.
