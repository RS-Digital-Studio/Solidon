# Review RM-628 — Curas Stützabstand in ganzen Schichten

Prüfling: Worktree `F:\sl-cura`, Zweig `einstellungen/cura-rundung-rm628`, `0ca808f9b` auf
`d5ddfc217` (Zwischenstand `8c2c381e8`), dazu der Patch für RM-624
(`scratchpad\rm628\rm624_cura_patch.diff`). Scratch: `scratchpad\rv628\`. Nichts im Worktree
geändert (`git status` sauber nach allen Läufen); Sonden laufen aus dem Scratch mit dem Worktree
als erstem `sys.path`-Element (`app.__file__` geprüft), ohne Bytecode, mit eigenem TEMP.

## Gelesen

- AUFTRAG.md (Reviews, Prüfen, Gebündelt rechnen), Bericht `berichte-2026-10-10/rm628.md`.
- Diff `d5ddfc217..0ca808f9b`, 24 Dateien, jede Zeile; Regeln `druckrat.md`,
  `schichtanalyse.md`, `dateiformat.md`, `tests.md`, `zwillinge.md`, `/regelcheck`.
- CuraEngine 5.13.0: `support.cpp`, dazu selbst geholt `FffGcodeWriter.cpp`,
  `sliceDataStorage.h/.cpp`, `TreeSupportSettings.h`, `TreeSupport.cpp`,
  `TreeSupportTipGenerator.cpp`, `PathConfigStorage.cpp` (`rv628\cura_src\`); Cura 5.13
  `fdmprinter.def.json`, `creality_base.def.json`.
- Kontaktzweig `F:\sl-kontakt` am Stand `0792f679c` (nur gelesen).

## Messungen am echten Programm (gepinnt FFFFF0FF, Stand `0ca808f9b`)

Sonde `rv628\test_rv628_probe.py`: Körper wie im Kontakttest (Platte über Säule auf Sockel),
PETG wenn nicht anders genannt, je Fall zwei Messungen — `support_contact` aus
`F:\sl-kontakt\tests\gcode_contact.py` (Zellen, Inset 4 mm) und eine eigene Ringmessung.
Ergebnisse `one.jsonl`, `all.jsonl`, `b2.jsonl`, G-Codes `gcode_all\`, `gcode_b2\`. Läufe:
17 von 17, 9 von 9, 1 von 1, je `EXIT=0`.

| Fall (geschrieben, Schicht, Trennschicht oben/unten) | Solidon erwartet oben/unten | Zellen | Ring |
|---|---|---|---|
| Cura Gitter 0,28, 0,2, 2/3 | 0,28 / 0,20 | 0,28 / 0,20 | 0,28 / 0,20 |
| Cura Gitter 0,28, 0,2, 0/0 | 0,28 / 0,20 | – / 0,20 | 0,28 / 0,20 |
| Cura Gitter 0,28, 0,2, 0/3 | 0,28 / 0,20 | – / 0,20 | 0,28 / 0,20 |
| Cura Gitter 0,30, 0,2, 2/2 | 0,30 / 0,20 | 0,30 / 0,20 | 0,30 / 0,20 |
| Cura Gitter PLA 0,10, 0,08, 2/2 | 0,10 / 0,16 | 0,10 / 0,16 | 0,10 / 0,16 |
| Cura Gitter 0,168, 0,12, 2/2 | 0,168 / 0,12 | 0,168 / 0,12 | 0,168 / 0,12 |
| Cura Baum 0,44, 0,2, 2/3 | 0,60 / 0,60 | 0,60 / 0,60 | 0,60 / 0,60 |
| Cura Baum 0,28, 0,2, 2/0 | 0,40 / 0,40 | 0,40 / 0,40 | 0,40 / 0,40 |
| Cura Baum 0,20, 0,2, 2/3 | 0,20 / 0,20 | 0,20 / 0,20 | 0,20 / 0,20 |
| **Cura Baum 0,20, 0,2, 0/0** | **0,20** / 0,20 | – / 0,20 | **0,40** / 0,20 |
| **Cura Baum 0,28, 0,2, 0/0** | **0,40** / 0,40 | – / 0,40 | **0,60** / 0,40 |
| **Cura Baum 0,40, 0,2, 0/0** | **0,40** / 0,40 | – / 0,40 | **0,60** / 0,40 |
| **Cura Baum 0,44, 0,2, 0/3** | **0,60** / 0,60 | – / 0,60 | **0,80** / 0,60 |
| OrcaSlicer Gitter 0,28 | 0,28 / 0,28 | 0,28 / 0,28 | 0,28 / 0,28 |
| OrcaSlicer Baum 0,28 / 0,30 / 0,18 bei 0,12 | 0,20 / 0,40 / 0,24 | gleich | gleich |
| Bambu Studio Gitter 0,28 | 0,28 / 0,28 | 0,28 / 0,28 | 0,28 / 0,28 |
| Bambu Studio Baum 0,28 | 0,20 / 0,20 | 0,20 / 0,20 | 0,20 / 0,20 |
| **Bambu Studio Baum 0,30** | **0,40 / 0,40** | **0,20 / 0,20** | **0,20 / 0,20** |
| Bambu Studio Baum 0,18 bei 0,12 | 0,24 / 0,24 | 0,24 / 0,24 | 0,24 / 0,24 |
| **Creality Print Baum 0,30** | **0,40 / 0,40** | **0,20 / 0,20** | **0,20 / 0,20** |
| ElegooSlicer / Anycubic Baum 0,30 | 0,40 / 0,40 | 0,40 / 0,40 | 0,40 / 0,40 |
| PrusaSlicer Gitter 0,28 | 0,28 / 0,28 | 0,28 / 0,28 | 0,28 / 0,28 |
| PrusaSlicer Baum 0,28 / 0,30 | 0,20 / 0,40 | gleich | gleich |

Kein Programm außer Cura rundet auf; Curas Gitter ist oben auch ohne Trennschicht genau (die
Stütze direkt unter dem Überhang bekommt ebenfalls die Bruchteillage, `sliceDataStorage.cpp:821–845`).
Untere Trennschichten bei Cura wie gewählt (3/3 bzw. 2/2). Zellen- und Ringmessung stimmen in
jedem Fall überein, wo beide messen (die Zellenmessung misst oben nur über einer Trennschicht).

**Zwei Teile auf einer Cura-Platte** (`test_rv628_plate.py`, `plate.jsonl`, 3 von 3, `EXIT=0`;
Werte je Teil aus Solidons `handover.object_keys`, gefiltert auf `CURA_PER_MESH`, in der
Netzliste der Übergabe):

| Platte | Teil A | Solidon erwartet A oben | gemessen A oben | B oben |
|---|---|---|---|---|
| 0,2 | 0,28 | 0,28 | **0,20** | 0,20 |
| 0,44 | 0,28 | 0,28 | **0,24** | 0,44 |
| 0,28 | 0,2 | 0,20 | 0,20 | 0,28 |

## Gegenproben (Mutation am Abzug `rv628\tree628` von `0ca808f9b`, nie am Worktree)

19 Testfunktionen des Diffs, 122 Fälle; Grundlauf 122 grün, `mutate.py`, `mutations.jsonl`.

| Gegenprobe | rot |
|---|---|
| G1 `cura_bottom_gap` gibt den Wert von oben | 11 |
| G2 `CURA_MIRRORED` spiegelt wieder nach unten | 4 |
| G3 Cura oben unter Gitter aufgerundet | 27 |
| G4 Cura unten zur nächsten statt auf | 24 |
| G5 `whole_layer_gap` ohne Materialband | 10 |
| G6 im Band das kleinste statt das nächste | 3 |
| **G7 Schreiber gibt `setting_limitations` kein Material** | **0** |
| **G8 Dialog gibt `limitation` kein Material** | **0** |
| G9 Unterseite ohne Stützart | 1 |
| G10 Feldsatz unten auch bei „nur vom Bett“ | 1 |
| G11 gedruckter Wert unten aus dem Wert von oben | 7 |
| G12 Feldsatz nennt den Wert von oben | 3 |
| G13 Grundlage wieder in ganzen Schichten | 10 |
| **G14 Übergabe wählt unten ohne Materialband** | **0** |

---

## Funde

### S1 (schwer) — Curas Fenster bekommt die Unterseite nicht; dort druckt PETG unten 0,40 bzw. 0,56, und der Feldsatz sagt 0,20

- `app/core/export/handover.py:2084–2091`: `support_bottom_distance` entsteht in `_for_supports`,
  also in `_cura_computed`/`_cura_dependants` — nur `values_for`, die Konsole.
- `app/core/export/handover.py:7746–7755`: `cura_profile_beside` schreibt die
  Einstellungsseite (`as_mapping`). Sonde `probe_values.json`: Die `.curaprofile` trägt
  `support_xy_distance = 0.5` und `support_z_distance = 0.28`, kein `support_bottom_distance`.
- Curas Fenster rechnet selbst: `support_bottom_distance = extruderValue(…,
  'support_z_distance') if support_type == 'everywhere' else 0` (`fdmprinter.def.json`;
  `creality_base` setzt nur `support_z_distance`). CuraEngine rundet das auf (`support.cpp:1119`,
  `:1703`), gemessen vom Bauagenten am Stand mit Spiegel: 0,28 → unten 0,40, bei 0,28 mm Schicht
  0,30 → 0,56.
- Die Fenster-3MF (`writer.py:3141`) trägt je Teil nur, was vom Konsolenwert der Platte abweicht
  (`object_keys`), also bei einem einzelnen Teil nichts.
- Folge, ohne dass der Kunde etwas wählt: Die Cura-Grundlage für PETG ist jetzt 0,28 (Standard)
  bzw. 0,30 (Entwurf) statt 0,2 bzw. 0,28 (`manufacturer.py:2295–2301`). Über *Im Slicer öffnen*
  liegt der Stützfuß damit 0,40 bzw. 0,56 über dem Modell — vorher 0,2 bzw. 0,28; genau der Fehler,
  den `0ca808f9b` für die Konsole behebt. Der Feldsatz (`slicer_keys.py:1689–1692`) nennt für
  beide Wege 0,20 bzw. 0,28, und der Changelog sagt „Wo Cura aufrundet, nennt das Feld den
  gedruckten Wert“.
- Ursache im Aufbau: `_cura_computed` ist laut Docstring (`handover.py:1951–1954`,
  `:1879–1882`) und Regel (`dateiformat.md:411–414`, „Gerechnetes in `_cura_computed` (die Formel
  aus der Definition, keine eigene Meinung)“) für Werte reserviert, die Curas Fenster genauso
  rechnet. `cura_bottom_gap` ist eine eigene Wahl Solidons. Denselben Fall gab es mit dem
  Lüfterhochlauf (`handover.py:1934–1938`: „Steht hier und nicht in `_cura_dependants`, weil das
  Cura-Fenster nur diese Seite bekommt“).
- **Fix:** `support_bottom_distance` auf die Einstellungsseite legen — im Cura-Zweig von
  `as_mapping` (`handover.py:1017–1029`) oder in `cura_profile_beside` aus derselben Funktion
  `advise.cura_bottom_gap`, mit dem Material des Profils, auch je Extruderprofil. Test:
  `.curaprofile` trägt denselben unteren Wert wie `values_for` (Helfer in
  `tests/test_cura_machine.py`), PETG 0,28 bei 0,2 → `0.2`. Regel `dateiformat.md` um den Satz
  ergänzen, dass eigene Cura-Werte auf die Einstellungsseite gehören, sonst fehlen sie dem Fenster.

### M1 (mittel) — Je Teil auf einer Cura-Platte gilt „oben genau“ nur mit dem Rest der Platte

- CuraEngine 5.13 legt die Bruchteillage um `support_top_distance % layer_height` **der
  Platte** tiefer (`PathConfigStorage.cpp:155–165`, `current_mesh_group->settings`); ob ein Netz
  eine Bruchteillage bekommt, entscheidet sein eigener Wert. Abstände selbst gelten je Netz
  (`support.cpp:1010`, `:1119`, `:1703`, `:1734`).
- Gemessen (Tabelle oben): Teil 0,28 auf Platte 0,2 → oben 0,20; auf Platte 0,44 → 0,24.
- Solidon schreibt je Teil `support_z_distance`/`support_top_distance` als eigenen Netzwert
  (`writer.py:1577–1619`, Cura-Zweig von `_values_for`) und nimmt oben „genau“ an
  (`advise.py:974–975`, `printed_support_gaps`, Feldsatz `slicer_keys.py:1689–1692`). Bei zwei
  Materialien (Platte trägt die Übernahme, das andere Teil bekommt die Grundlage zurück) druckt ein
  PETG-Teil mit 0,28 auf einer 0,2-Platte oben 0,20 — das Anschweißen, das RM-628 verhindern soll.
- **Fix:** Für Cura je Teil oben nur Werte schreiben, deren Rest dem der Platte gleicht; sonst das
  Vielfache im Band der Spule des Teils (`whole_layer_gap`, exakt in Cura), und `printed_support_gaps`
  bzw. der Befund je Teil nennt den gedruckten Wert. Test mit zwei Teilen (Einheitstest an
  `_values_for`, am echten Programm nach `rv628\test_rv628_plate.py`).

### M2 (mittel) — Curas Bäume ohne obere Trennschicht drucken oben eine Lage mehr; Rat und Feldsatz rechnen ohne sie

- Gemessen (Tabelle oben): ohne obere Trennschicht 0,20 → 0,40, 0,28 → 0,60, 0,40 → 0,60,
  0,44 → 0,80; mit Trennschicht 0,20 → 0,20, 0,28 → 0,40. Unten unverändert aufgerundet.
  Ohne Trennschicht baut CuraEngine die Spitzen als „fake roof“
  (`TreeSupportTipGenerator.cpp:33`, `use_fake_roof_ = !support_roof_enable`).
- Solidon: `gap_rounding("cura", style="tree")` = `up` (`advise.py:974–975`); „Ein Vielfaches
  druckt jeder Slicer genau“ (`advise.py:1051–1053`) und „Ein Vielfaches druckt auch Cura genau“
  (`advise.py:1178–1179`). Folge: PETG unter Curas Bäumen bekommt 0,2 geraten und druckt ohne
  Trennschicht 0,4, über dem Höchstwert 0,30; der Feldsatz schweigt bei Vielfachen
  (`slicer_keys.py:1677`) und nennt bei 0,28 „auf 0,40 mm“ statt 0,60.
- Erreichbar über *Trennschichten oben* = 0; der Rat hebt 0 unter nicht flachen Decken nicht an
  (`advise.py:1262–1269`).
- **Fix:** Die Rundungsauskunft bekommt die obere Trennschicht: Cura-Baum ohne sie = aufgerundet
  plus eine Lage. `support_gap_target` zielt dort eine Lage tiefer (oder rät die Trennschicht),
  der Feldsatz nennt den gedruckten Wert auch bei Vielfachen; Docstrings korrigieren; Test samt
  einem Fall am echten Programm (Baum, `support.interface_layers` 0).

### M3 (mittel) — Das Materialband erreicht Übergabe, Schreiber und Dialog ohne Test

- Gegenproben G7, G8, G14 bleiben grün (122 von 122). Alle Fälle in
  `test_cura_gets_its_bottom_gap_in_whole_layers_under_grid`,
  `test_cura_gets_the_bottom_gap_it_prints_as_meant` und `test_cura_says_what_it_prints_of_the_gap`
  liegen dort, wo „nächstes Vielfaches“ und „nächstes im Band“ dasselbe ergeben; nur
  `test_a_whole_layer_gap_is_the_nearest_inside_the_material_band` prüft das Band, an der Funktion
  selbst. Die Kernaussage der Fertigstellung („im Band des Materials“) hält an keiner
  Anschlussstelle ein Test (`AGENTS.md`, Testart „Anschluss“).
- Die Dialogänderung (`print_settings_dialog.py:6609–6617`) bringt keinen Fenstertest mit
  (`tests.md`, „Neues bringt seinen Test für diese Auswahl mit“; Muster:
  `test_the_gap_field_asks_the_trees_the_advice_asked`).
- Nebenbei: `tests/test_slice_findings.py:1574` (`printed_gap(gap, layer, "up" if tree else
  "exact") == gap`) gilt nach der Zusicherung davor durch Konstruktion; die Zeile prüft nichts.
- **Fix:** Fälle, wo Band und Nächstes auseinandergehen, mit gemessener Herkunft (Cura 5.13 oben):
  PETG 0,30 bei 0,2 → unten 0,20 (nicht 0,40), PLA 0,10 bei 0,08 → 0,16 (nicht 0,08) — an
  `values_for`/`object_keys`, am Befund aus `write_assembly` und als Fenstertest am Feld.

### L1 (leicht) — Mehrere Materialien: Die Unterseite wählt im Band des Auftragsmaterials, nicht der Spule

- Platte: `write_config` → `values_for(settings_for_handover(…), profile, …)`
  (`handover.py:3453–3458`); `settings_for_shared_slicer` nimmt die Werte der ersten Spule
  (`handover.py:2834–2848`), `_for_supports` aber `profile.material` (`handover.py:2088–2090`).
  Je Teil: `writer._values_for(…, profile=profile)` → `object_keys(…, profile=profile)`
  (`writer.py:1531`, `:1615–1616`), während der Rat desselben Teils mit dem Profil seiner Spule
  fragt (`writer.py:1391`).
- `probe_values.json` („mixed“): PETG-Teil auf PLA-Auftrag bei 0,1 mm → unten 0,10 statt 0,20
  (unter PETGs Mindestwert 0,12); PLA-Teil auf PETG-Auftrag bei 0,08 mm → 0,08 statt 0,16 (unter
  PLAs 0,10). Ab 0,12 mm gleich.
- **Fix:** Die Unterseite mit dem Material der Spule wählen, die das Teil bzw. die Platte druckt
  (je Teil `profiles.for_object`, auf der Platte das der ersten Spule); Test bei 0,1 mm.

### L2 (leicht) — Bambu Studio und Creality Print runden den Halbfall unter organischen Bäumen anders

- Gemessen: 0,30 bei 0,2 mm → 0,20 (OrcaSlicer, ElegooSlicer, Anycubic, PrusaSlicer: 0,40);
  0,18 bei 0,12 mm → 0,24. 0,3/0,2 ist in Gleitkomma 1,4999999999999998, 0,18/0,12 genau 1,5:
  beide runden ohne Epsilon.
- `tests/test_slice_findings.py:1497` sichert für die ganze Orca-Familie 0,30 → 0,40 zu,
  `printed_gap` (`advise.py:989`) ebenso. Kundensichtbar ist heute keine Zahl (der Baumsatz nennt
  die Schichthöhe, der Rat schlägt Vielfache vor); der Kontakttest nimmt 0,44.
- **Fix:** Halbfall in Docstring und Tabellentest als gemessen „je Programm verschieden“
  ausweisen und aus der Familienzusage nehmen; erst eine kundensichtbare Zahl braucht die Rundung
  je Programm.

### L3 (leicht, Kundensicht) — „in ganzen Schichten zu {gap}“ liest sich wie die Schichthöhe

- `slicer_keys.py:1690`: „… unten in ganzen Schichten zu {gap}.“ — dieselbe Wendung wie der
  Baumsatz `slicer_keys.py:1704` „in ganzen Schichten zu {layer}“, dort ist die Zahl die
  Schichthöhe. Bei 0,12 mm Schicht steht „unten in ganzen Schichten zu 0,24 mm“, lesbar als
  Schichten von 0,24 mm.
- **Fix:** z. B. „Cura druckt den Stützabstand oben genau und unten mit {gap}, einem Vielfachen der
  Schichthöhe.“; fünf Kataloge nachziehen (die heutigen Übersetzungen „at/con/à/a/com {gap}“
  sind eindeutiger als die Quelle).

### L4 (leicht, Kundensicht) — Solidons eigene PETG-Grundlage löst bei Cura eine Warnung ohne Ausweg aus

- `setting_limitations` macht aus dem Gitter-Satz `slicer.setting_not_transferred`, Schwere
  `warning`, Handlung *Druckeinstellungen öffnen* (`handover.py:4897–4911`). Mit der neuen
  Grundlage (PETG 0,28) steht er bei jeder Cura-Übergabe mit Stützen
  (`test_cura_gets_the_materials_gap_from_its_foundation`: `said(supported)` wahr). Am Feld kann
  der Kunde nichts besser machen: 0,2 schweißt an, 0,4 liegt über dem Band. Nicht übertragen ist
  dabei nichts; die Unterseite ist Solidons Wahl.
- **Fix:** Für den Gitter-Satz Schwere `info` ohne Handlung (oder nur am Feld); der Baumsatz
  (Kundenwert wird nicht gedruckt) bleibt Warnung.

### L5 (leicht) — Unterlagen behaupten mehr, als gemessen ist

- `.claude/rules/druckrat.md:80–84`: „die übrigen runden zur nächsten“ ohne die Bedingung
  (organische Bäume, Turm); „oben gilt dort der Wert des Materials genau“ — es gilt der
  geschriebene Wert, je Teil nur mit dem Rest der Platte (M1), unter Bäumen nicht ohne
  Trennschicht (M2).
- `konzepte/begruendungen/regel-druckrat.md:540–542`: „Gemessen … (`tests/test_real_slicers.py`):
  Gitter mit 0,28 oben 0,28 und unten 0,4“ — der Test sichert seit `0ca808f9b` unten 0,20 zu.
- Docstrings `advise.py:1051–1053`, `:1178–1179` (siehe M2), `handover.py:1951–1954` (siehe S1).
- **Fix:** mit S1, M1, M2 nachziehen.

## Prüfpunkte ohne Fund

- **Rundungsmodell sonst:** Cura Gitter oben genau (mit und ohne Trennschicht), unten aufgerundet;
  Bäume mit Trennschicht oben und unten aufgerundet; Orca-Familie und PrusaSlicer unter Gitter genau,
  unter organischen Bäumen zur nächsten (bis auf L2). 0,08 mm (PLA 0,10 → 0,10/0,16), 0,12 mm,
  Wert zwischen zwei Schichten (PETG 0,30 → 0,30/0,20), Wert auf der Grenze (0,6/0,2 =
  2,9999999999999996 → ganze Schichten, `is_close`/`EPS_GEOM`, kein `==`), Material ohne Band
  (TPU: nächstes Vielfaches, gleich Curas eigenem Aufrunden) — alles wie berechnet.
- **Nur bei Cura, nichts Ungefragtes:** `_for_supports` läuft nur über `_cura_computed`;
  Orca/Prusa schreiben unten weiter den Wert von oben (`test_the_support_gap_reaches_both_sides…`).
  Für Cura gibt es keinen Herstellerprozess (Grundlage ist Solidons Tabelle, die Übergabe schreibt
  sie ganz, `manufacturer.base_settings`); `support_bottom_distance` stand auch vorher immer in der
  Übergabe (Spiegel). Kein neuer ungefragter Schlüssel. Eine Rücklesung der Cura-Abstände gibt es
  nicht (CuraEngine schreibt keine Konfiguration in den G-Code).
- **Changelog:** sechs Sprachen, gleiche Stelle, 159–195 Zeichen, Ursache `fafcd4841` in keinem Tag
  → Eigenschaft richtig. Der zweite Satz gilt erst mit S1 (und M2) für alle Wege.
- Regeln 1–22 im Umfang: kein Qt unter `core`, kein `==` auf Fließkomma, Texte über `_()`, alle
  fünf Kataloge, englische Bezeichner; keine Abhängigkeit, keine Ausnahme, kein Dialog.
- Gebündelt rechnen: Skalarrechnung je Übergabe, keine Schleife je Element — nicht betroffen.

## Zusammenspiel mit RM-624 (Patch `rm624_cura_patch.diff`)

- **Sollwerte und Feldsatz richtig:** `printed_support_gaps(gap, layer, setup.flavour, style,
  organic, profile.material)` und die Feldsatzprüfung (`shown = top if tree else bottom`) treffen
  Cura: selbst gemessen mit `tests/gcode_contact.support_contact` am Stand `0ca808f9b` — Gitter
  0,28/0,20, Baum 0,60/0,60, je drei untere Trennschichten (der `else`-Zweig passt), 180/180 bzw.
  180/112 Zellen; Feldsatz „0,20 mm“ bzw. „0,60 mm“. Für die sechs übrigen ändert sich nichts
  (0,28 genau, 0,44 → 0,40).
- **Doppelt oder keine:** Danach bleibt genau eine Cura-Kontaktmessung (Kontakttest, zwei Fälle bei
  0,2 mm); RM-628s eigene Ringmessung samt vier Fällen entfällt. Damit fallen die Fälle 0,28-mm-Gitter
  (0,30 → unten 0,28) und 0,12-mm-Baum weg; Fenster (S1), zwei Teile (M1) und Baum ohne
  Trennschicht (M2) prüft kein Fall.
- **(mittel) Der Patch ist veraltet:** Er ist die Volldatei-Differenz eines Probemerges mit
  `e5533f2ce` und trägt in Z. 244–302 die damaligen synthetischen Fälle. Der Kontaktzweig steht auf
  `0792f679c` („Die synthetischen Kontaktfälle werden mit jeder verstümmelten Messung rot“): eigene
  Bahnhöhe der untersten Stützlage, `top_cells == 0`, Rand als Ring. So angewandt fiele der Patch
  durch oder machte diese Schärfung rückgängig. **Fix:** beim Zusammenführen nur die fachlichen Teile
  übernehmen: `"cura"` in `_CONTACT_PROGRAMS`, Sollwerte über `printed_support_gaps`, Feldsatzprüfung
  für Cura, Docstringsatz zu Cura (ersetzt den aus `5c87b1d6b`), RM-628s eigene Messung samt
  `_CURA_MODEL`, `_CURA_WORD`, `_CuraGaps`, `_cura_support_gaps`, ihrem Messtest und
  `test_curas_support_gap_arrives_as_solidon_says` und die dann ungenutzten Importe (`math`,
  `dataclass`); den Fall 0,28-mm-Gitter über `layer` als Parameter behalten.
- **Akten beim Zusammenführen:** Registereintrag RM-628 aus `5c87b1d6b` entfernen — seine Abnahme
  nennt noch „Gitter 0,28 / 0,40“, nach `0ca808f9b` sind es 0,28 / 0,20. Im Archiv RM-624 den Satz
  „Cura fehlt, weil es aufrundet … das richtet RM-628, und Cura kommt mit ihm hierher“ nachziehen.

## Bemerkung zum Bericht des Bauagenten (kein Fund im Repository)

„Zwei Messungen stimmen in jedem Fall überein“ (Abschnitt 3) hält für seine Rohdaten nicht: Die
Zellenmessung seiner Sonde (`uebergabe-2026-10-09\gcode_kontakt.py`) lieferte unter Curas Bäumen
unten −3,01/−3,05 und unter Gitter der übrigen Programme unten 0,20 bzw. 0,0 gegen 0,24 im Ring.
Mit `tests/gcode_contact.py` vom Kontaktzweig stimmen beide Messungen in allen meinen Fällen.

## Läufe

| Lauf | Ergebnis | Exit |
|---|---|---|
| Rechensonde `probe_values.py` (Konsole, `.curaprofile`, Feldsätze, Grundlage, Randfälle, Mischmaterial) | geschrieben `probe_values.json` | 0 |
| Slicersonde Cura 5.13 / Orca / Bambu / Elegoo / Creality / Anycubic / Prusa, gepinnt | 1 von 1, 17 von 17, 9 von 9 | je 0 |
| Zwei Teile auf einer Cura-Platte, gepinnt | 3 von 3 | 0 |
| Gegenproben am Abzug, 15 Läufe (Grund + 14 Mutationen), gepinnt | siehe Tabelle | 0 |
| 23 Testdateien am Worktree ohne Fenster/Renderer/Leistung/`rendered`, `-n 6`, gepinnt (`test_advise`, `test_slice_findings`, `test_print_settings`, `test_export`, `test_cura_machine`, `test_cura_fan_curve`, `test_cura_raft_contact`, `test_cura_skin_speeds`, `test_manufacturer`, `test_slicer_part_settings`, `test_slicer_verify`, `test_print_time`, `test_estimate`, `test_rm484_raft_cura`, `test_rm484_raft_gap`, `test_slicer_profiles`, `test_export_readback`, `test_translations`, `test_wording`, `test_changelog`, `test_roadmap`, `test_directory_docs`, `test_language_rules`) | 3424 grün, 10 übersprungen, 0 rot | 0 |
| ruff check, ruff format --check, mypy (Cache im Scratch) | grün | je 0 |

`git status` im Worktree nach allen Läufen leer.

## Urteil

**Nicht.** Das Konsolenmodell stimmt am echten Cura in jedem gemessenen Fall mit oberer
Trennschicht und einem Teil je Platte, Tests und Tore sind grün. Aber der Fensterweg bekommt die
neue Unterseite nicht und druckt mit der neuen PETG-Grundlage ungefragt 0,40/0,56 unter einem
Feldsatz, der 0,20 nennt (S1); dazu M1 (Teil je Platte), M2 (Baum ohne Trennschicht), M3
(Materialband ohne Anschlusstest) und der veraltete RM-624-Patch. Nach den Fixes ist eine
**Nachprüfung nötig** (ein schwerer und vier mittlere Funde), am besten mit den Sonden
`rv628\test_rv628_probe.py` und `test_rv628_plate.py`.
