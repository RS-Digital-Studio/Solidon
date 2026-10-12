# Review RM-584-Nachtrag (Prüfer rv584t) — 10.10.2026

Gegenstand: Worktree `F:\sl-stil2`, Zweig `einstellungen/stuetzstil-nachtrag`, Spitze `9907dab53`
(enthält origin/welle4 `02213548a`); eigener Diff `git diff origin/welle4...9907dab53`
(11 Dateien, +427/−84; Commits `630cc601e` L1, `6aeb59de9` Cura). Alle Zeilen des Diffs gelesen,
dazu `_calculate`, `_accepted_targets`, `_with_parts`, `_mark_parts`, `_advice_title`,
`printed_style`, `_from_geometry` (Stützteil), `_support_contact`, `tip_gap`, `gap_rounding`,
`combine`, `part_advice`, `_part_values`, `_values_for`, `asked_for_contact`, `style_per_part`,
`tree_styles`, `ignored_under_trees`, `organic_styles` und die Regeln `druckrat.md`,
`druckerwahl.md`, `zwillinge.md`, `tests.md`. Nur gelesen und gemessen; Worktree vor und nach
jedem Lauf sauber (`git status` leer, HEAD `9907dab53`).
Scratch: `%TEMP%\claude\F--3D-Druck\b00d64ab-ed49-460e-9651-1d89ea000640\scratchpad\rv584t\`
(alter Stand als Schnappschuss `alt\` aus `git archive 02213548a app tests`, kein Worktree; im
Baum liegt kein übersetzter Kern, beide Stände rechnen über dieselbe `.venv`).

**Kurzfassung:** Der Fix stimmt. Am echten Cura (Drache neben Pilz) verschwinden Spitzenluft
und Wandzeile, die Datei bekommt `normal` mit 0,2 mm; der alte Stand schrieb 0,4 über Gitter.
ElegooSlicer bleibt bis auf den G-Code gleich (alt gegen neu, Bewegungen per Hash). Ein
mittlerer Befund: Die Export-Hälfte des Fixes hat keinen Test, der rot werden kann. Dazu vier
leichte und ein vorbestehender neuer Punkt. **Urteil: kann so nicht rein; nach M1 ja, ohne
Nachprüfung.**

## Befunde

### Mittel

**M1: Die Export-Hälfte des Fixes hat keinen Test, der rot werden kann.**
`app/core/export/writer.py:1537` (`_part_values` → `plate_style=split.plate.support.style`),
dazu `app/ui/print_settings_dialog.py:1901` (`_accepted_targets`).
Beleg: Mutante W1 (nur diese Stelle auf `plate_style=None`) → 344 passed, EXIT=0
(`mut_W1.txt`); Mutante D3 (`_accepted_targets` ohne Art der Platte) ebenso grün
(`mut_D3.txt`). Der Test `test_a_tree_cura_prints_as_grid_asks_its_gap_with_grid`
(`tests/test_print_settings.py:8446`) soll beides halten, aber seine Zeilen dazu laufen im
Fixzustand über leere Mengen: Ohne übernommene Abstandszeile schreibt der Export keinem Netz
einen eigenen Abstand, also prüft `all(... for value in gaps.values())` (`:8505`) nichts — und
ob `handover.cura_meshes(written)` überhaupt Netze liefert, sichert niemand zu
(`tests.md`, „Verbotstest über eine leere Menge“). `accepted_others["support.z_gap"]` (`:8488`)
entsteht nur für übernommene Pfade. Die Gegenprobe des Bauagenten (Mutante X, `for_part` überall
ohne Art der Platte) wurde nur über den direkten Aufruf `part_advice(..., plate_style=...)` im
Test rot, nicht über die Aufrufstelle im Export.
Dass die Stelle trägt, zeigt `rv_luecke2.py` (Pilz und Stachelkörper des Tests, Cura, Abstand der
Platte 0,3, alle Zeilen übernommen, also auch „0,3 → 0,2“ aus dem Material; EXIT=0):
Zweig → beide Netze `support_z_distance 0.2`; mit W1 → Netz der Stacheln
`support_z_distance 0.4`, `support_top_distance 0.4`, `support_bottom_distance 0.4`, Platte
`normal` — genau der Fehler, den der Nachtrag behebt, und die Suite bliebe grün. Eine
Abstandszeile aus anderem Grund ist kein Sonderfall: Sie entsteht, sobald der Abstand der
Grundlage außerhalb des Bands um den Wert des Materials liegt (`SUPPORT_GAP_BAND`,
`_support_contact`). Für D3 zeigt `rv_luecke.py` `accepted_others = (('Stacheln', 0.4),)` statt
leer; sichtbar am Feld wird es nur, wo der Vorschlag nicht allen Teilen gilt (in meinen zwei
und drei Körpern zeigte das Feld „Gilt allen Teilen“).
Fix: im Test eine Abstandszeile aus anderem Grund erzeugen (Plattenabstand 0,3), alle Zeilen
übernehmen, `meshes = handover.cura_meshes(written)` mit `assert len(meshes) == 2` und je Netz
kein Abstand über 0,2; dazu `assert not worker.accepted_others.get("support.z_gap")` in diesem
Fall. Gegenprobe: W1 und D3 müssen rot werden.

### Leicht

**L1: Eine Zeile des Dialogtests prüft nichts.**
`tests/test_print_settings.py:8480` (`assert "support.tree_walls" not in together`): Der
Stachelkörper ist 22,5 mm hoch (höchste Säule 19,4 mm), der Pilz 14 mm (12,0 mm);
`TALL_TREE_HEIGHT` ist 100 mm (`advise.py:138`). Gemessen mit `rv_saeule.py` (EXIT=0): Auch
unter Curas Baum ohne Platte, also im alten Zustand, bekommt keiner der beiden eine Wandzeile —
die Zeile kann mit und ohne Fix nicht rot werden. Der Bericht des Bauagenten nennt „keine
Wandzeile“ als geprüft. Gehalten wird die Wandregel unter Curas Gitter nur im Kerntest
(`test_under_curas_plate_grid_a_tree_asks_no_tip_air_and_no_walls`, 120-mm-Turm); im echten
Cura-Lauf verschwindet sie am Drachen (siehe unten). Fix: Zeile streichen oder einen Körper mit
über 100 mm Säulenhöhe nehmen (`tests.md`: „Eine Zeile, deren Entfernen nichts rot macht, prüft
nichts“).

**L2: `on_the_plate` leitet Curas Baum selbst her, statt die eine Quelle zu fragen.**
`app/core/slice/advise.py:1154-1156`: `"tree" if plate == "tree" else "grid"`. Welche Arten ein
Programm als Baum druckt, sagt laut `druckrat.md` `trees` aus `handover.tree_styles` („eine
Quelle“); `_cura_prints_alike` (`print_settings_dialog.py:1485`) fragt dieselbe Auskunft über
`trees`, `slicer_keys.py:692` schreibt sie in die Datei (`_mapped({"tree": "tree"}, "normal")`).
Heute antworten alle drei gleich (`tree_styles` gibt für Cura immer `{tree}`), aber kein Test
bindet `on_the_plate` an die Übersetzung der Datei (`test_on_the_plate_is_the_style_cura_prints`
prüft Literale). Fachlicher Zwilling nach `zwillinge.md`, neu entstanden. Fix: im Test für jede
Stützart `s` prüfen, dass `on_the_plate("tree", s, "cura") == "tree"` genau dann gilt, wenn
`handover.as_mapping(...)["support_structure"] == "tree"` — oder `trees` übergeben.

**L3: Die Regel kennt die neue Pflicht nicht.**
`.claude/rules/druckrat.md:80-83` und `:145-158`: Kontakt und Baumwände fragen dort „mit
`printed_style` gegen `trees`“. Seit dem Nachtrag fragt bei Cura die Art der Platte
(`on_the_plate`), und jeder, der den Rat je Teil für Cura fragt, muss `plate_style` mitgeben
(Dialog nach dem Zusammenführen, Export und Feld mit `split.plate.support.style`); ohne ihn
kommt der alte Fehler zurück (Mutanten C1, D2, W1). Die Regel ist nicht nachgezogen
(`CLAUDE.md`, „Nach einer Muster- oder Entscheidungsänderung die Regel nachziehen“). Fix: ein
Satz in `druckrat.md` beim Kontakt und bei den Wänden: „Bei Cura mit der Art der Platte
(`on_the_plate`); wer den Rat je Teil für Cura fragt, gibt `plate_style` mit.“

**L4: Die Neufrage läuft auch, wenn ihr Rat schon überholt ist.**
`app/ui/print_settings_dialog.py:1775`: `if self.flavour == "cura" and ruled:` fragt nicht
`self.rules_wanted`. Nach `measure_only()` (der Dialog ändert den Auftrag, während der Arbeiter
noch rechnet — nach dem Öffnen die Regel, DRUCK-14) überspringt der Arbeiter alle weiteren
Regeln, `_with_parts` bricht ab, `_accepted_targets` läuft nicht; nur die Neufrage rechnet
weiter, und der nächste Arbeiter wartet, bis dieser ausläuft (`_start_advice`, „ersetzte
Aufträge laufen erst aus“). Gemessen kostet die Neufrage am Drachen 3,5 s CPU je Lauf. Fix:
`if self.flavour == "cura" and ruled and self.rules_wanted:`.
Gleichartig `:1784-1787`: Neu gefragt wird jeder Körper, dessen Name der Art sich ändert, auch
„Automatisch“ oder Hybrid unter einer Gitter-Platte. Bei Cura fragen beide den Kontakt gleich
(`gap_rounding` „exact“, `tip_gap` nur bei `tree`, Wände gegen `trees = {tree}`, `organic`
leer). Gemessen mit `rv_leerlauf.py` (EXIT=0): Cura, Grundlage „Automatisch“, Zeile zur
Stützart abgewählt — Pilz und Stachelkörper werden beide mit `plate_style=auto` neu gefragt
und liefern genau die Zeilen des ersten Durchgangs; am Drachen wären das 3,5 s CPU für nichts.
Fix: neu fragen nur, wo
`advise.on_the_plate(style, plate_style, self.flavour) != advise.on_the_plate(style, style, self.flavour)`.

## Geprüft ohne Befund

- **Zusammenführung, alle Kombinationen bei Cura:** `on_the_plate(P, Q)` gibt für ein
  gestütztes Teil (P ≠ „aus“) Baum genau bei Platte Baum, sonst Gitter — wie die Datei
  (`slicer_keys.py:692`), auch für Platte „aus“ (Netz an, `support_structure=normal`) und
  Hybrid. „Aus“ bleibt aus, `None` (Platte unbekannt) und andere Familien geben P zurück.
  Automatisch, Gitter und Hybrid fragen den Kontakt bei Cura gleich (`gap_rounding`, `tip_gap`,
  Wände gegen `trees = {tree}`, `organic` leer). Die Neufrage ändert nur den Kontakt, nicht die
  Stützart; der zweite Zusammenschluss kann die Art der Platte also nicht mehr verschieben, ein
  Durchgang reicht. Die Rückrichtung (Gitter-Körper auf Baum-Platte → mit Baum gefragt) ist
  abgedeckt. `rules()`/`assembled()` führt Platte und Spulen in derselben Reihenfolge zusammen
  wie vorher (für Elegoo alt gegen neu gemessen, unten).
- **Zwillinge:** Kontakt und Wände fragen nur in `_from_geometry` (Dialog, Export, Feld über
  `for_part`); `writer._values_for` nutzt jetzt `on_the_plate` statt derselben Zeile von Hand.
  Feldsatz (`slicer_keys.limitation`), `cura_part_gap`, `_cura_bottom_gap` und `_cura_grid`
  lesen die Art der Platte selbst — dort war der Fehler nicht. `handover._on_the_plate`
  (Betttemperatur je Druckplatte) ist ein modulprivater Namensgleicher mit anderer Sache, nach
  `zwillinge.md` erlaubt. Agentenzug (`agent/analysis.py:225`) und Dialog ohne Körper
  (`:8210`) fragen einen Körper ohne Cura-Platte — unberührt.
- **Wartezeit, Hauptthread, Abbruch:** Die Neufrage läuft im `Worker(QThread)`, vor jedem
  Körper `raise_if_cancelled()`, nur Körper, deren Art sich ändert (am Drachen neben dem Pilz
  nur der Drache). Kosten siehe Cura-Lauf (rund 2 % des Arbeiters).
- **Feld (L1 des Vorgängers):** `_part_note` gruppiert über `shown_value` wie `_advice_title`,
  kürzt mit `_few_names`, Tooltip und Bildschirmleser bekommen die volle Fassung; „Nur für“ ist
  jetzt ebenfalls gekürzt. Der Rest fällt weg, wo alle Teile genannt sind (Mutante F4 rot).
  Neuer Schlüssel „{parts} bekommen {value}.“ in allen fünf Katalogen (get, reciben, reçoivent,
  ricevono, recebem), Platzhalter gleich, Mehrzahl stimmt auch mit „und {count} weitere“;
  `test_translations`, `test_text_length`, `test_wording` grün.
- **Regeln 1–22:** kein Qt im Kern, keine feste Zeichenkette (alles über `tr()`), keine
  Fließkommagleichheit (Zeichenketten), keine neue Abhängigkeit, Bezeichner englisch
  (`test_language_rules` grün). Übrige Regeln berührt der Diff nicht.
- **Changelog „kein Punkt“:** bestätigt. `git tag --contains` ist für `1ddb4953a` (Spitzenluft),
  `1c902c368` und `c533f04a5` leer; `v0.5.3` kennt weder `printed_style` noch `tip_gap`,
  `tree_walls` oder `gap_rounding`. Der Abschnitt 0.6.0 sagt schon „mehr Abstand … zu den
  Baumstützen“ und „Mit Cura und Gitterstützen folgt der Stützabstand dem Material: oben
  genau“ (`changelog/de.md`, Abschnitt 0.6.0); der Nachtrag lässt das Produkt das auch neben
  einer flachen Decke tun.
- **Archiv:** Nachtrag im Eintrag „RM-584 (Teil 2)“ stimmt mit Bericht und Tests überein;
  `test_roadmap` grün. RM-584 bleibt im Register mit den offenen Teilen.

## Neuer Punkt (vorbestehend, kein Befund dieses Diffs)

**Cura, abgelehnte Stützart-Zeile: Der Kontakt fragt mit der Grundlage, die Platte druckt den
übernommenen Baum.** `rv_abgelehnt.py` (Pilz + Stachelkörper, Cura, Grundlage „aus“, früher
„Baum“ übernommen, neue Zeile „Baum → Gitter“ abgelehnt): keine Spitzenluft-Zeile; die Datei
schreibt `support_structure=tree`, beide Netze an, `support_top_distance=0.2` — 100 Spitzen
unter Curas Bäumen mit einer Schicht Luft. Am alten Stand gleich (`rv_abgelehnt_alt.py`,
EXIT=0). Ursache: Mit `declined` liest `printed_style` die Art aus `asking`
(`asked_for_contact` setzt sie bei Cura auf die Grundlage, weil An/Aus je Netz geht), und
`on_the_plate` lässt „aus“ stehen. Vorschlag: bei Cura mit abgelehnter Stützart den Kontakt mit
der Art der Platte (`self.settings`) fragen, wo das Netz in der Datei gestützt wird.

## Echter Cura-Lauf am neuen Stand (Drache neben Pilz)

`rv_sonde.py` (Sonde des Bauagenten, erweitert um jeden `advise.advise`-Aufruf mit CPU-Zeit und
`plate_style`), Arbeitsverzeichnis `F:\sl-stil2`, gepinnt FFFFF0FF, Cura 5.13 gefunden,
Ender-3 V3 SE, PLA, Grundlage Stützen aus, Abstand 0,2, Weg von *Slicen*
(`_prepare_plate` → `slice_model`). **EXIT=0** (`sonde_cura_neu_out.txt`,
`aus_neu\cura-drache+pilz-alle\ergebnis.json`, Auszug `cura_neu_auszug.txt`).

- Zeilen: „Aus → Gitter“, Ränder frei · Drache, Brückentempo, dichte Trennschicht,
  Trennschichten 3 · Pilz, Brim, Mindesttempo (Spule). **Kein Abstand mit Spitzengrund, keine
  Wandzeile**, auch keine Zeile „Ohne obere Trennschicht lässt Cura …“.
- Nach dem Übernehmen bleibt nur das Mindesttempo (Spule, nicht übernommen); Feld:
  Stützart (Drache, Pilz) = alle, Trennschichten · Pilz, Ränder · Drache, `accepted_others` leer.
- Datei: Platte `support_structure=normal`, `support_top_distance=0.2`, `support_z_distance=0.2`,
  `support_bottom_distance=0.2`, `support_wall_count=0`; Netz Drache `support_enable` und
  Trennschichthöhe 0,4, Netz Pilz `support_enable`, Sperrnetz der Ränder. CuraEngine-Aufruf
  ebenso (`support_structure=normal`, `support_top_distance=0.2`). G-Code: 598 Abschnitte
  `support`, 552 `support-interface`; Slicen 91 s Wanduhr.
- **Wartezeit:** Erster Rat des Drachen 93,9 s CPU (Zeilen Baum, Wände 2, Abstand 0,4), die
  Neufrage mit Gitter 3,5 s CPU (nur noch „Baum“), der Pilz wird nicht neu gefragt. Arbeiter
  gesamt 155,9 s CPU / 129 s Wanduhr; zweiter Lauf mit gleichen Einstellungen 156,4 s CPU,
  Zeilen gleich.

**Gegenprobe am alten Stand** (Schnappschuss `alt\` = `02213548a`, dieselbe Sonde, ohne
Slicen, EXIT=0, `sonde_cura_alt_out.txt`, Auszug `cura_alt_auszug.txt`): Zeilen zusätzlich
„Abstand 0,2 → 0,4: Feine Spitzen brauchen mehr Luft über den Baumstützen · Drache“ und
„Wände der Bäume 1 → 2“; übernommen schreibt die Datei Platte `support_structure=normal` mit
`support_top_distance=0.4`, `support_z_distance=0.4`, `support_bottom_distance=0.4`, Netz Drache
`support_z_distance=0.4`. Arbeiter 152,7 s CPU — der neue Stand braucht 3,2 s mehr, so viel wie
die Neufrage.

## ElegooSlicer als Gegenfall (alt gegen neu)

Dieselbe Sonde mit ElegooSlicer (Centauri Carbon 2, PLA, Grundlage Stützen aus), alle Zeilen
ohne Spule übernommen, geschrieben und geslict, gepinnt — neuer Stand (`F:\sl-stil2`) und alter
(`alt\`), dazu ein zweiter, unabhängiger Lauf des alten Stands als Rauschprobe. Alle drei
EXIT=0 (`sonde_elegoo_neu_out.txt`, `sonde_elegoo_alt_p_out.txt`, `sonde_elegoo_alt_out.txt`),
verglichen mit `vergleich.py` (`elegoo_vergleich.txt`, `elegoo_alt_gegen_alt.txt`):

- **alt gegen neu gleich**: `trees` (auto, hybrid, tree), `organic`, alle Zeilen vor und nach dem
  Übernehmen samt Grund, Teilen und „andere“, Feld (Teile und eigene Werte), Objektwerte der 3MF,
  G-Code-Arten, die Stützzeilen im Kopf und der SHA-256 aller Bewegungszeilen ohne Kommentare.
  Alt gegen alt ebenso gleich, der Vergleich trennt also.
- Inhalt: „Aus → Baum · Drache, Pilz mit Gitter“, „Abstand 0,2 → 0,4: Feine Spitzen … ·
  Drache“, Baumspitze 1,13, dichte Trennschicht · Pilz; Objektwerte Drache `tree(auto)` mit
  `support_top_z_distance 0.4`, Pilz `normal(auto)`, `rectilinear-grid`. Dort druckt jedes Teil
  seine eigene Art, und die Spitzenluft des Drachen bleibt richtig.
- Im neuen Stand kommt `plate_style` als „none“ (Art der Platte, die Teile tragen ihre eigene)
  bei `for_part` an und wird außerhalb von Cura nicht ausgewertet; keine Neufrage.

## Gegenproben (eigene Mutanten, `mut\rv584t_mut.py`)

Jede Mutante ersetzt genau eine Stelle im Quelltext einer Funktion und kompiliert sie im
Modul neu (keine Datei geändert; trifft die Ersetzung nicht genau einmal, bricht das Plugin ab).
Auswahl 344 Tests (test_slice_findings, test_print_settings, test_export,
test_slicer_part_settings mit `-k "cura or Cura or on_the_plate or field_names or row_names or
tips or hybrid or tree_walls or tall_tree"`), gepinnt, -n 4. Ohne Mutante: 344 passed, EXIT=0.

| Mutante | Stelle | Ergebnis |
|---|---|---|
| D1 | Dialog: keine Neufrage bei Cura | 1 rot (`test_a_tree_cura…`) |
| D2 | Dialog: Neufrage mit `None` | 1 rot (`test_a_tree_cura…`) |
| D3 | `_accepted_targets` ohne Art der Platte | **grün** (M1) |
| D4 | `_with_parts` ohne Art der Platte | grün; in den Sondenfällen ohne sichtbare Wirkung (die Abstandszeile nennt dort keine Teile), kein Befund |
| C1 | `_from_geometry` ohne `on_the_plate` | 3 rot (Dialogtest, Kern cura-grid, cura-auto) |
| W1 | `_part_values` ohne Art der Platte | **grün** (M1) |
| W2 | `on_the_plate`: „aus“ wird Gitter | 2 rot (`test_cura_unfulfilled_support_style_keeps_the_requested_value`, `test_on_the_plate…`) |
| W3 | `on_the_plate`: „automatisch“ als Baum | 2 rot (`test_only_the_part_that_is_supported_gets_a_blocker[cura]`, Kern cura-auto) |
| F1 (`mut_L1.txt`) | Feld: sichtbarer Text ungekürzt | 1 rot (`test_the_field_names_many_parts_once_per_value_like_the_row`) |
| F2 (`mut_L2.txt`) | Feld: Tooltip gekürzt | 1 rot (derselbe) |
| F3 (`mut_L3.txt`) | Feld: je Teil ein Satz (alter Stand) | 1 rot (derselbe) |
| F4 (`mut_L4.txt`) | Feld: Rest auch, wo alle genannt sind | 1 rot (`test_the_field_names_the_parts_that_print_their_own_value_with_it[2-…]`) |

## Läufe

- Lauf 1 (gepinnt FFFFF0FF, -n 4, ohne Fenster): test_slice_findings, test_print_settings,
  test_export, test_slicer_part_settings, test_advise, test_cura_machine, test_translations,
  test_text_length, test_roadmap, test_changelog, test_shared_constants, test_language_rules,
  test_registry_consistency, test_wording, test_directory_docs — **4388 passed, 10 skipped,
  EXIT=0**, 148 s (`lauf1_out.txt`, HEAD `9907dab53`, Status leer).
- Fenster `tests/test_print_settings_ui.py` (gepinnt): **345 passed, 126 deselected, EXIT=0**
  (`fenster_out.txt`).
- `ruff check .` Exit 0, `ruff format --check .` Exit 0, `mypy` „no issues found in 374 source
  files“, EXIT=0 (am Worktree).
- 13 Mutantenläufe (`mut_*.txt`), je Exit wie in der Tabelle.
- Sonden, je EXIT=0: `rv_sonde.py` Cura neu (mit Slicen) und alt (ohne), ElegooSlicer neu und
  zweimal alt (mit Slicen), `rv_luecke.py`, `rv_luecke3.py` (drei Körper), `rv_luecke2.py`,
  `rv_abgelehnt.py` (neu), `rv_abgelehnt_alt.py` (alt), `rv_saeule.py`, `rv_leerlauf.py`.
- Kein volles Tor, keine CI, nichts im Worktree geändert, nichts committet.

## Urteil

**Kann so nicht rein: erst M1** — ein Test, an dem die Mutanten W1 und D3 rot werden (die
Export-Hälfte des Fixes ist sonst ungeschützt, und ein Rückfall schriebe still wieder 0,4 über
Curas Gitter). Die leichten L1–L4 im selben Zug. Danach **kann es landen, ohne Nachprüfung**
(ein mittlerer Befund, kein Fehlverhalten im Code): Es genügt, wenn der Bericht des Bauagenten
W1 und D3 rot und den ergänzten Test grün belegt. Der Code selbst ist richtig — am echten Cura
belegt, ElegooSlicer unverändert. Der neue Punkt (abgelehnte Stützart bei Cura) ist
vorbestehend und hält das Landen nicht auf.

## Durchsicht der Fixe (Stand `3370bf34b`, 10.10. ab 23:20)

Auftrag des Koordinators: eng nur `cd45ca608` (L4) und `f48592b75` (Altfall), dazu ob der
M1-Test (`3aa356d76`) mit W1/D3 rot wird, und zwei Fragen. Gelesen: beide Diffs ganz
(`advise.contact_style`, der Aufruf in `_from_geometry`, `_BodyRules.printed` als Paar
(Art mit, Art ohne Ablehnungen), die Neufrage in `_calculate`), die drei neuen Tests und der
geänderte M1-Test. Worktree sauber, HEAD `3370bf34b`.

**Kurz: landbar.** Die Frage des Koordinators verneine ich mit Sonde und Datei. Die Neufrage fragt
jeden Körper neu, der es braucht; in einem Fall fragt sie unnötig neu (N1, leicht). M1 ist
behoben: W1 und D3 werden jetzt rot.

### Frage 1: Fragt ein Körper mit Grundlage „aus“ und abgelehntem „Aus → …“ Zeilen für ein Netz ohne Stütze?

**Nein.** `rv_fixe.py` (Pilz, Stachelkörper, Klotz ohne Stützbedarf; Cura ohne Programm;
Grundlage aus; EXIT=0, `fixe_out.txt`):

- Eine Zeile „Aus → …“ hat als Ausgangswert die Art der Platte (`combine` liest `was` aus
  `self.settings`). Die Zeile zur Stützart ist bei Cura eine für die Platte; abgelehnt wird je
  Pfad, nicht je Körper. Lehnt der Kunde sie ab, bleibt die Platte „aus“, und `contact_style`
  fällt auf `on_the_plate(style, …)` = „aus“ zurück (die `wanted`-Weiche verlangt
  `plate not in (None, "none")`). **Fall 1a** („Aus → Gitter“ abgelehnt) und **1b** („Aus →
  Baum“): keine Abstands-, Spitzenluft- oder Wandzeile, keine Neufrage; Datei: Platte
  `support_enable=false`, kein Netz mit `support_enable=true`.
- Die `wanted`-Weiche greift nur unter gestützter Platte, und dort hat jedes Netz, das Stützen
  will, sie in der Datei auch an: Ist die Stützart übernommen, schreibt der Export jedem Teil
  mit eigenem Stützwunsch `support_enable=true` (`_values_for`, `as_cura_takes_it`). Auf die
  Grundlage zurückgenommen wird nur ein Teil ohne Stützwunsch, und das fragt keinen Kontakt
  (`needs_support`). Ist sie nicht übernommen, erbt jedes Netz die Platte. **Fall 2** (Baum früher
  übernommen, „Baum → Gitter“ abgelehnt): Zeile „Abstand 0,2 → 0,4: Feine Spitzen … ·
  Stacheln“; Datei: Platte `tree`, Netz Stacheln `support_enable=true` mit 0,4, Pilz an,
  Klotz `support_enable=false` und ohne eigene Zeile. **Fall 3** (Gitter übernommen, „Gitter →
  Baum“ abgelehnt): keine Spitzenluft, Datei `normal`, Stacheln an.
- Eine Bedingung „Netz hat in der Datei Stütze an“ braucht es deshalb nicht. **Kein Fund.**
- Vorbestehend, nicht aus den Fixen: In Fall 1a erscheinen weiter die Trennschichtzeilen
  („Eine dichte Trennschicht hält große flache Decken“, Abstand 0,2, Trennschichten 3 · Pilz),
  obwohl die Platte ohne Stützen druckt. Am alten Stand ist das genauso (`rv_fixe_alt.py`,
  EXIT=0); `_support_contact` läuft bei Stützbedarf unabhängig von der Art. Das wird ein neuer
  Punkt mit geringer Dringlichkeit: Zeilen, die nichts ändern, nach einer abgelehnten Zeile
  „Aus → …“.

### Frage 2: Fragt die L4-Bedingung jeden neu, der es braucht, und keinen, der es nicht braucht?

- **Jeden, der es braucht: ja.** Bei Cura hängt der Kontakt nur daran, ob die Art ein Baum ist:
  `gap_rounding`, `tip_gap`, Wände gegen `trees = {tree}`, `organic` leer. Der erste Durchgang
  fragt mit der rohen Art (`contact_style(…, None)` = `style`), und `on_the_plate(style, style)`
  hat dieselbe Baum-Eigenschaft. Ändert die Platte sie, unterscheiden sich die Namen, und die
  Bedingung greift (`:1788-1789`). Fall 2: Pilz und Stacheln werden neu gefragt, die Stacheln
  bekommen 0,4; der Klotz nicht.
- **Keinen, der es nicht braucht: nicht ganz → N1.**

**N1 (leicht): Abgelehntes „aus“ unter einer Gitter-Platte wird umsonst neu gefragt.**
`app/ui/print_settings_dialog.py:1788-1789`. Ist die Art abgelehnt (`style` = „aus“ aus
`asking`) und die Platte gestützt, aber kein Baum, gibt `contact_style` „grid“,
`on_the_plate("none", "none")` aber „none“. Die Namen unterscheiden sich, also fragt der Dialog neu.
„aus“ und Gitter fragen bei Cura aber denselben Kontakt. Fall 3 belegt das: Die Stacheln werden mit
`plate_style=grid` neu gefragt, und die Zeilen sind vorher und nachher gleich
(`['support.style=tree']`). Am Drachen kostet das 3,5 s CPU. Der Fall ist kein Randfall: Ein Kunde mit
Gitter lehnt den Baumvorschlag ab. Fix: die Baum-Eigenschaft vergleichen statt des Namens, aus
der einen Quelle: `(advise.contact_style(style, wanted, plate_style, self.flavour) in trees)
!= (style in trees)` (`trees` aus `handover.tree_styles`, bei Cura immer `{tree}`, für mypy
mit `trees or frozenset()`). Nachgerechnet für Nachtragsfall, Altfall, „auto“, Rückrichtung
(Gitter-Körper auf Baum-Platte) und Platte „aus“ mit Baum-Körper: Neu gefragt wird genau dort,
wo sich die Zeilen ändern können. Dazu im Test
`test_cura_asks_again_only_where_the_plate_changes_the_print` ein Fall „Gitter übernommen,
Gitter → Baum abgelehnt“ mit 0 Neufragen.

### Gegenproben (Stand `3370bf34b`, `mut\rv584t_mut.py`, gepinnt, -n 4)

Auswahl 27 Tests (`-k "tree_cura_prints_as_grid or asks_again_only or declined_style_row or
contact_follows or on_the_plate or under_curas or field_names"` über test_print_settings und
test_slice_findings). Ohne Mutante: 27 passed, EXIT=0.

| Mutante | Stelle | Ergebnis |
|---|---|---|
| W1 | `_part_values` ohne Art der Platte | **rot** (`test_a_tree_cura_prints_as_grid_asks_its_gap_with_grid`) — M1 behoben |
| D3 | `_accepted_targets` ohne Art der Platte | **rot** (derselbe) — M1 behoben |
| A1 | `contact_style` ohne `wanted` | 2 rot (`test_a_declined_style_row…[tree]`, `test_the_contact_follows…`) |
| A2 | Dialog merkt `wanted` = `style` | 1 rot (`test_a_declined_style_row…[tree]`) |
| A3 | Neufrage ohne `rules_wanted` | 1 rot (`test_cura_asks_again…[overtaken-0]`) |
| A4 | Neufrage vergleicht wieder den Namen (`!= style`) | 1 rot (`test_cura_asks_again…[auto-0]`) |
| A5 | `contact_style` auch unter Platte „aus“ | 1 rot (`test_the_contact_follows…`) |

Der M1-Test setzt jetzt den Plattenabstand auf 0,3, prüft zwei Netze (`len(parts) == 2`) und je
Netz oben und unten höchstens 0,2. Die leere Zeile zur Wandzeile (L1) ist gestrichen.

### Läufe der Durchsicht

- `rv_fixe.py` (Fälle 1a, 1b, 2, 3, 3b) EXIT=0; `rv_fixe_alt.py` (Fall 1a am alten Stand) EXIT=0.
- 8 Mutantenläufe (`mut2_*.txt`), Exit wie in der Tabelle.
- Lauf 2 (gepinnt, -n 4, ohne Fenster, HEAD `3370bf34b`, Status leer): test_print_settings,
  test_slice_findings, test_export, test_slicer_part_settings, test_advise,
  test_shared_constants, test_language_rules, test_registry_consistency, test_roadmap,
  test_changelog, test_directory_docs — **3705 passed, 8 skipped, EXIT=0**, 94 s
  (`lauf2_out.txt`).
- Nichts im Worktree geändert, nichts committet.

### Urteil der Durchsicht

**Landbar.** M1, L4 und der Altfall sind behoben und jeweils mit einem Test gesichert, der unter
der Mutante rot wird. Die Frage nach Zeilen für ein Netz ohne Stütze verneine ich mit Sonde und Datei. N1
(leicht) betrifft nur Rechenzeit und lässt sich mit einer Zeile und einem Testfall beheben;
eine weitere Nachprüfung ist nicht nötig.

## Durchsicht 2 (Stand `3e47bc61a`, 10./11.10. ab 23:52)

Auftrag: eng nur `ec301ddea` (N1 und Altfall „Aus → Gitter“ abgelehnt) und der Merge
`3e47bc61a` (welle4 `1e4dec783` mit RM-586/RM-706), vier Fragen. Gelesen: Code- und Testdiff
von `ec301ddea` ganz, die Konfliktstellen des Merges. Worktree sauber, HEAD `3e47bc61a`.
Alter Stand `9907dab53` als Schnappschuss `alt9907\` (`git archive`).

**Kurz: nicht landbar ohne M2.** Für Cura ist `ec301ddea` richtig, ebenso der Merge. Die neue
Sperre greift aber über Cura hinaus: In der Orca-Familie streicht sie Kontaktzeilen eines Teils,
das die Datei weiter stützt.

### (1) Ändert der Fix etwas für Orca/Elegoo/Bambu/Prusa an einer Platte mit Stütze?

`rv_elegoo_klein.py` (ElegooSlicer gefunden, Centauri Carbon 2, PLA, Pilz und Stachelkörper,
Grundlage aus), alt `9907dab53` gegen neu `3e47bc61a`, gepinnt, je Fall EXIT=0
(`klein_alt_out.txt`, `klein_neu_out.txt`, Vergleich `klein_vergleich.txt`):

- **Fall „alle“ (Stütze übernommen, alle Zeilen übernommen): Übergabe gleich.** Zeilen vor und
  nach dem Übernehmen, Feld, Objektwerte gleich. Die 3MF ist bytegleich (`vergleich_3mf.py`,
  alle sechs Einträge, `klein_3mf_vergleich.txt`), ebenso `solidon_process.json`,
  `solidon_machine.json`, `solidon_filament_0.json` und der Aufruf ohne Pfade (mitgeschnitten
  mit `rv_elegoo_eingang.py`, EXIT=0). **Der G-Code-Hash entscheidet hier nichts:**
  ElegooSlicer liefert aus bytegleicher Eingabe verschiedenen G-Code — zwei Läufe des alten
  Stands ergaben 190 und 185 Stützabschnitte, zwei Läufe des neuen 186 und 188, je mit anderem
  Hash (unter `tree(auto)` der 100 Stacheln). Am Drachen war er in der ersten Runde stabil.
- **Fall „Gitter früher übernommen, Zeile zur Art abgelehnt“: Rat und Datei ändern sich → M2.**
- Fall „eigene Wahl Gitter, Zeile abgelehnt“: alles gleich (eine eigene Wahl steht in der
  Grundlage, siehe (2)).

**M2 (mittel): In der Orca-Familie streicht die neue Sperre Kontaktzeilen eines Teils, das die
Datei weiter stützt.** `app/core/slice/advise.py:1790` (`if printed != "none"`) mit dem Rat je
Körper im Dialog (`print_settings_dialog.py`, `rules()` fragt mit `self.declined`). Hat der
Kunde früher „Aus → Gitter“ übernommen und lehnt er jetzt „Gitter → Baum · Stacheln, Pilz mit
Gitter“ ab, fragt der Dialog den Pilz mit der Art aus `asking` (Grundlage „aus“). Außerhalb von
Cura gibt `contact_style` diese Art zurück, also fragt der Pilz keinen Kontakt mehr. Die
Datei stützt den Pilz aber weiter: Die Art ist je Teil übernommen, und `part_advice` fragt mit
`DECIDING_PATHS - accepted`, also mit dem Vorschlag des Teils. Gemessen (ElegooSlicer,
Fall „gitter-abgelehnt“):
alt Zeilen „Eine dichte Trennschicht hält große flache Decken“ (Abstand 0,2, Trennschichten
3 · Pilz), Datei Pilz `normal(auto)` mit `support_interface_top_layers 3`,
`support_interface_spacing 0.2`; **neu fehlen beide Zeilen, Datei Pilz `normal(auto)` ohne sie**
— der 40-mm-Hut druckt mit der lockeren Trennschicht der Grundlage. Das ist ein Rückschritt
gegenüber `9907dab53` für Elegoo, Orca, Bambu, Creality, Anycubic und PrusaSlicer, sobald eine
Stützart übernommen ist und der Kunde eine neue Zeile zur Art ablehnt. Fix: Der Dialog fragt
den Rat je Körper mit derselben Ablehnung wie der Export (`part_advice`:
`DECIDING_PATHS - accepted` mit `accepted = split.accepted_per_part()`), also `rules()` mit
`self.declined - frozenset(handover.split_for_parts(self.settings, …).accepted_per_part())`
(dieselbe Quelle wie `_accepted_targets`). Eine Ablehnung zählt dann nur, wo die Art nicht schon
je Teil übernommen ist. „Aus → Gitter“ abgelehnt bleibt ohne Kontaktzeilen, weil dort nichts
übernommen ist; die Cura-Fälle 2 und 3 ändern sich nicht, weil `known` weiter aus
`self.declined` kommt. Test: Orca, Gitter übernommen, „Gitter → Baum“ abgelehnt → der Pilz behält
die Trennschichtzeilen. Gegenprobe: `ec301ddea` ohne den Fix ist rot.

**Neuer Punkt (vorbestehend, alt wie neu):** Im selben Fall schreibt die Orca-Familie den
Stacheln trotz abgelehnter Zeile „Gitter → Baum · Stacheln“ `support_type tree(auto)`
(Objektwerte in beiden Ständen gleich). Ist ein Pfad je Teil übernommen, schreibt der Export
jedem Teil seinen eigenen Vorschlag (`_values_for`, `applied`); die spätere Ablehnung einer
neuen Zeile erreicht die Datei nicht. Zeile und Datei widersprechen sich dann.

### (2) Hält `test_each_part_gets_the_contact_of_its_own_material` noch, was er hielt?

Ja, für eine Platte mit Stütze, und die Gegenprobe ohne Stütze ist neu. Mit übernommenem Gitter:
PLA kein Abstand, PETG 0,28. Ohne Übernahme bei Grundlage „aus“ (Platte ohne Stützen): kein
Abstand. Mutante B1 (Sperre aus) macht ihn rot, dazu
`test_without_supports_on_the_plate_no_contact_rows[True-orca]` und `[True-cura]`. Vorher hielt
er den Abstand auch ohne jede Stütze. Das war die Zeile, die der Altfall-Fix streichen
wollte. `rv_eigenwahl.py` (EXIT=0) zeigt dazu, dass eine **eigene Wahl** Gitter in der
Grundlage steht (`split.base` und `asking` = grid) und `part_advice` dann ebenfalls 0,28 gibt,
bei Orca und Cura. Der Kontakt je Material hängt also nicht an der Übernahme, der Test deckt
nur diesen Weg ab.

### (3) Stimmt die vorab feste Art der Platte bei abgelehnter Zeile (Cura) mit der Datei?

Ja, in allen fünf Fällen von `rv_fixe.py` am Stand `3e47bc61a` (EXIT=0, `fixe2_out.txt`):
„Aus → Gitter“ und „Aus → Baum“ abgelehnt → gefragt mit „none“, keine Kontaktzeile, Datei
`support_enable=false`; Baum übernommen, „Baum → Gitter“ abgelehnt → gleich mit Baum gefragt,
Spitzenluft 0,4 · Stacheln, Datei `tree`, Stacheln an mit 0,4, Klotz aus und ohne Zeile; Gitter
übernommen, „Gitter → Baum“ abgelehnt → mit Gitter gefragt, keine Neufrage, Datei `normal`;
nicht abgelehnt → erste Runde ohne Art, Datei `tree` mit 0,4 wie die Zeile. Die Datei schreibt
bei abgelehnter Zeile die Art aus `self.settings` (die Zeile wird nicht übernommen); dieselbe
nimmt `known`. Mutante B4 (`known` aus) macht `[grid kept-0]` rot.

**L5 (leicht): Die Baum-Normierung der Neufrage hat keinen Test.** Mutante B3 (`kind()` gibt
den Namen statt „Baum ja/nein“) bleibt grün: 15 passed. Der Fall, den sie trägt — Cura, nicht
abgelehnt, ein Körper mit „Automatisch“ oder Hybrid unter einer Gitter-Platte —, fehlt im Test;
der Fall `auto` dort lehnt ab, und mit `known` gleich der Platte ist die Normierung gleichgültig.
Fix: ein Fall ohne Ablehnung mit einem Körper, der „Automatisch“ druckt, und 0 Neufragen.

### (4) Ist die Konfliktlösung im Merge vollständig?

Ja. `merge_pruefung.sh` vergleicht für `advise.py`, `print_settings_dialog.py` und `writer.py` die
+/−-Zeilen jeder Seite gegen das Ergebnis (`merge_pruefung_out.txt`): Von beiden Seiten fehlt
keine Zeile. Der einzige Rest in `advise.py` ist der Umbruch des `_from_geometry`-Aufrufs, den beide
Seiten gleich gemacht haben. In `print_settings_dialog.py` ist `shared_layers=` aus welle4 in
`rules()` gewandert. Beide Parameter reichen bis in jeden Aufrufer: `advise.advise`,
`_from_geometry`, `for_part`, `writer.part_advice` samt Merkerschlüssel, `_part_values` sowie
`rules()`, `_accepted_targets` und `_with_parts` im Dialog. `_fine_layers` (RM-586) steht hinter
der Kontaktsperre mit `shared_layers`.

### Gegenproben und Läufe (Stand `3e47bc61a`, gepinnt)

| Mutante | Stelle | Ergebnis |
|---|---|---|
| B1 | Sperre `printed != "none"` aus | 3 rot (`test_without_supports…[True-orca]`, `[True-cura]`, `test_each_part_gets_the_contact_of_its_own_material`) |
| B3 | `kind()` vergleicht Namen | **grün** (L5) |
| B4 | `known` bei Cura aus | 1 rot (`test_cura_asks_again…[grid kept-0]`) |

- Ohne Mutante 15 passed, EXIT=0 (`mut3_*.txt`, -n 4).
- Lauf 3 (ohne Fenster, -n 4, HEAD `3e47bc61a`, Status leer): test_print_settings,
  test_slice_findings, test_export, test_slicer_part_settings, test_advise, test_translations,
  test_text_length, test_shared_constants, test_language_rules, test_registry_consistency,
  test_roadmap, test_changelog, test_directory_docs — **3991 passed, 8 skipped, EXIT=0**, 132 s
  (`lauf3_out.txt`).
- Sonden, je EXIT=0: `rv_elegoo_klein.py` (3 Fälle × alt/neu, „alle“ mit Slicen),
  `rv_elegoo_eingang.py` (alt/neu mit Mitschnitt der Slicer-Eingänge), `rv_eigenwahl.py`,
  `rv_fixe.py` am neuen Stand. Nichts im Worktree geändert, nichts committet.

### Urteil der Durchsicht 2

**Nicht landbar ohne M2.** Für Cura sind `ec301ddea` und der Merge in Ordnung. Die neue
Kontaktsperre nimmt in der Orca-Familie aber einem gestützten Teil seine Trennschichtzeilen,
sobald eine Stützart übernommen ist und eine neue Zeile zur Art abgelehnt wird; das ist
gemessen, und die Datei ändert sich. Der Fix ist eine Zeile (`rules()` mit der Ablehnung des
Exports, `self.declined` ohne die je Teil übernommenen Pfade) samt Test. Danach kann es landen, ohne
Nachprüfung (ein mittlerer Befund), wenn der Bericht die Gegenprobe am Elegoo-Fall belegt:
Der Pilz behält die Trennschichtzeilen, die Datei schreibt sie. L5 im selben Zug.
