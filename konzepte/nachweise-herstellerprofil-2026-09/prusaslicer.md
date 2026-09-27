# PrusaSlicer-Übergabe — Abgleich gegen die Herstellerprofile

Stand: 27.09.2026 · PrusaSlicer 2.9.6 · Prusa-Bündel `PrusaResearch.ini` 2.4.14
(`C:\Program Files\Prusa3D\PrusaSlicer\resources\profiles`; `%APPDATA%\PrusaSlicer\vendor`
ist auf dieser Maschine leer, der Assistent wurde hier nie durchlaufen).

Nur gelesen und gemessen, nichts im Repository geändert. Proben, aufgelöste
Herstellerprofile und G-Code liegen unter `prusa-probe/` neben dieser Datei.

**Anlass:** Minigolf-Satz, erste Schicht unbrauchbar, weil Solidon mit der festen
45°-Grenze (`app/core/knowledge/rules.py:41`) Stützen vorschlug und die Schwelle in
jede Übergabe schrieb. Maßstab nach Roberts Vorgabe: das Herstellerprofil; jede
Abweichung Solidons braucht einen Grund am Modell oder am Material.

---

## 0. Methode

1. **Solidons Übergabe, wie die Anwendung sie fährt:** `prusa-probe/probe.py`
   importiert `obj_2_Gövde59.stl` (Minigolf-Satz) über den Weg der Anwendung
   (`lauf.imported_objects`), löst „Standard“ für `prusa-mk4s`, `prusa-mini`,
   `prusa-xl` × PLA/PETG auf, übernimmt einmal alle Vorschläge (`advise`) und
   ruft `writer.write_assembly` + `handover.slice_model` (Konsole, `--load solidon.ini`).
   Ergebnis je Lauf in `prusa-probe/lauf/<drucker>/<material>/<variante>/`
   (`solidon.ini`, `probe.3mf`, `solidon.gcode`), Zusammenfassung `lauf/ergebnis.jsonl`.
2. **Der Maßstab:** Die vorgewählten Herstellerprofile — Drucker, Prozess,
   Filament — aus `PrusaResearch.ini` 2.4.14, aufgelöst über die ganze Erbkette
   (`prusa-probe/resolve_vendor.py`, Solidons eigener `_PrusaStore`) auf
   PrusaSlicers eingebaute Vorgaben (`builtin_defaults.ini`, per `--save` aus
   einem leeren `--datadir`). Ergebnis `prusa-probe/v_*.ini`. Vorgewählt ist,
   was das Druckerprofil als `default_print_profile`/`default_filament_profile`
   nennt:

   | Drucker (Bündelname) | Prozess | Filament PLA / PETG |
   |---|---|---|
   | Original Prusa MK4S HF0.4 nozzle (erste Variante des Modells) | 0.20mm SPEED @MK4S HF0.4 | Prusament PLA @MK4S HF0.4 / Prusament PETG @MK4S HF0.4 |
   | Original Prusa MK4S 0.4 nozzle | 0.20mm SPEED @MK4S 0.4 | Prusament PLA @MK4S / Prusament PETG @MK4S |
   | Original Prusa MINI & MINI+ Input Shaper | 0.20mm SPEED @MINIIS 0.4 | Prusament PLA @MINIIS / Prusament PETG @MINIIS |
   | Original Prusa XL Input Shaper 0.4 nozzle | 0.20mm SPEED @XLIS 0.4 | Prusament PLA @XLIS / Prusament PETG @XL |

   Zusätzlich „0.20mm STRUCTURAL“ für MK4S 0.4 und XL (Stützschwelle 40 statt 35).
3. **Herstellerlauf am selben Körper:** PrusaSlicer 2.9.6 mit `--load v_*.ini`,
   einmal wie vorgewählt, einmal mit „Stützen nur vom Bett“ (`--support-material
   --support-material-auto --support-material-buildplate-only`, genau das, was die
   Auswahl im Fenster setzt). G-Code in `prusa-probe/hersteller/`.
4. **Vergleich** Hersteller gegen die im G-Code von Solidons Lauf *wirksame*
   Konfiguration (`; prusaslicer_config`-Block), mit Herkunft: von Solidon
   geschrieben oder PrusaSlicers eingebaute Vorgabe (`compare.py`, `tabelle.py`).
5. **Gegenproben:** `grenze.py` fährt Solidons Vorschlagsrechnung mit anderen
   Überhanggrenzen (45…55°); `anordnung/` prüft, ob die Konsole eine 3MF-Lage
   verwirft. Die Zeiten sind PrusaSlicers eigene Schätzung; Solidons Läufe schätzen
   dabei ohne Maschinengrenzen (`machine_limits_usage = ignore`), eher zu kurz.

**Nebenbefund zur Konsole (gemessen):** `--printer-profile`, `--print-profile`,
`--material-profile` aus einem eigens angelegten `--datadir` mit dem Bündel
übernahmen in 2.9.6 nur den *Prozess*; im G-Code standen danach
`printer_settings_id = - default FFF -`, der eingebaute Startcode und 200 °C
(`save_*.log`, `mk4s_hf04_speed_pla.ini`). Die Profilschalter der Konsole sind
damit kein verlässlicher Weg; die aufgelöste INI über `--load` ist es.

---

## 1. Messergebnis am Minigolf-Körper (`obj_2_Gövde59.stl`, PLA)

| Lauf | Stützbahn | Modellbahn | Zeit (Schätzung PrusaSlicer) | Material |
|---|---|---|---|---|
| **Hersteller** MK4S HF0.4 SPEED, wie vorgewählt (nur Verstärker) | 0 m | 479,8 m | 1 h 09 min | 54,4 g |
| **Hersteller** MK4S HF0.4 SPEED, „nur vom Bett“ (Schwelle 35) | **1,1 m** (nur Schnittstelle) | 479,8 m | 1 h 10 min | 54,5 g |
| **Hersteller** MK4S HF0.4 SPEED, „überall“ | 1,1 m | 479,8 m | 1 h 10 min | 54,5 g |
| **Hersteller** MK4S 0.4 STRUCTURAL, „nur vom Bett“ (Schwelle 40) | 12,9 m | 493,6 m | 2 h 35 min | 56,6 g |
| **Hersteller** MINI IS SPEED, „nur vom Bett“ (Schwelle 40) | 12,9 m | 494,1 m | 1 h 54 min | 56,7 g |
| **Hersteller** XL IS SPEED, „nur vom Bett“ (Schwelle 40) | 12,9 m | 479,8 m | 1 h 34 min | 55,6 g |
| **Solidon** MK4S Standard (keine Stützen) | 0 m | 557,3 m | 1 h 42 min | 55,4 g |
| **Solidon** MK4S Vorschläge übernommen (Gitter, nur vom Bett, Schwelle 45, Kanalsperre, Bahn 0,438) | **55,6 m** | 564,4 m | 2 h 08 min | 61,2 g |
| **Solidon** MINI Vorschläge übernommen | 55,6 m | 564,4 m | 4 h 34 min | 61,2 g |

Solidons Vorschlag erzeugt am selben Teil **das Fünfzigfache** der Stütze des
MK4S-Standardprofils und **das Vierfache** der strengsten Herstellerschwelle (40).
Die Modellbahn ist bei Solidon um 16 % länger (drei statt zwei Wände), die Zeit am
MK4S um 48 % länger; am MINI 2,4-mal so lang wie beim Hersteller (siehe B6).
Rohdaten: `prusa-probe/metrics.py` über die G-Code-Dateien, `lauf/ergebnis.jsonl`.

---

## 2. Befunde, nach Schwere geordnet

### B1 — druckentscheidend: PrusaSlicer bekommt keinen Drucker, sondern seine eingebauten Vorgaben

**Was geschieht (gemessen):** Die Prusa-Übergabe besteht aus 63 Schlüsseln
(`lauf/prusa-mk4s/pla/standard/solidon.ini`): Solidons Tabellenwerte plus vier
Maschinenschlüssel (`nozzle_diameter`, `bed_shape`, `max_print_height`,
`machine_limits_usage`). Die Konsole lädt nur diese Datei (`--load`), die 3MF-Beilage
trägt denselben Satz. **Von den 347 Schlüsseln, die der G-Code als wirksam ausweist,
sind 284 PrusaSlicers eingebaute Vorgabe (`FullPrintConfig::defaults()`), nicht das
Profil des Herstellers.**
Im G-Code des MK4S-Laufs stehen deshalb:

| Schlüssel | Hersteller MK4S | Solidons G-Code |
|---|---|---|
| `printer_model` | `MK4S` | leer |
| `gcode_flavor` | `marlin2` | `reprap` |
| `start_gcode` | M862-Prüfungen, MBL bei 170 °C (`G29 P1 … G29 A`), Düsenreinigung, Spüllinie | `G28 ; home all axes` / `G1 Z5 F5000` |
| `start_filament_gcode` | `M572 S0.036` (Pressure Advance, 0,4 HF) | `; Filament gcode` |
| `before_layer_gcode` / `layer_gcode` | `M201 …interpolate_table(extruded_weight_total…)` / `M74 W[extruded_weight_total]` | leer |
| `use_relative_e_distances` | 1 (`M83`) | 0 (`M82`) |
| `remaining_times`, `gcode_label_objects`, `arc_fitting`, `thumbnails`, `binary_gcode` | 1, firmware, emit_center, 4 Vorschaubilder, 1 | 0, disabled, disabled, keine, 0 |

Gezählt im G-Code des Solidon-Laufs: **0** × `G29`, `M862`, `M572`, `M74`, `M73`,
`M555`; im Herstellerlauf 6 × `G29`. Die Düse heizt vor `G28` voll auf 215 °C
(Prusas Startcode vermisst bei 170 °C, „set extruder temp for bed leveling“, und
reinigt die Düse vorher mit `G29 P9`; dass eine heiße, nachtropfende Düse die
Wägezellenmessung verfälscht, ist die naheliegende Begründung, aber nicht von Prusa
belegt), keine Spüllinie, und die erste Schicht fährt mit
**4000 mm/s²** statt **500** (`M204 S4000` gegen `M204 P500`, B3). MINI und XL
betrifft es genauso; beim XL fehlt der Ablauf „home carriage, pick tool, home all“
samt Düsenreinigung und MBL (wie der XL auf ein nacktes `G28` reagiert, ist hier
nicht gemessen), beim MINI `G29`, `M572 S0.27`, `M221 S95` und `M572 W0.06`.

**Fundstellen:**
- `app/core/export/handover.py:959–983` — `_machine_keys` gibt für `prusa` nur die
  vier Schlüssel; Docstring `:904–905` „eine `.ini` ist eigenständig lauffähig,
  sobald Düse und Bettform darin stehen“ — lauffähig ja, aber mit PrusaSlicers
  Startcode.
- `app/core/export/handover.py:1411–1423` (`write_config`, Prusa-Zweig) und
  `:2235–2244` (`_command`: nur `--load solidon.ini`).
- `app/core/export/writer.py:1448–1471` (`_plate_config`): die Beilage
  `Metadata/Slic3r_PE.config` bekommt denselben Satz.
- `app/core/export/slicer_keys.py:1124–1133` (`has_readable_profiles`: „Für `prusa`
  nicht … Es gibt dort also nichts auszuwählen“) und `:1059–1092`
  (`takes_a_machine_profile` nur Orca); `handover.py:347–357` (`machine_missing`:
  „für sie ist ‚keine Maschinenseite‘ kein Mangel, sondern die Bauart“).
- Widerspruch zur eigenen Regel: `.claude/rules/schichtanalyse.md`, „Das
  Maschinenprofil wird nicht erfunden. Bettform, Anfahrwege, Start- und Endcode …
  kommen aus dem Bestand des Slicers.“ Für PrusaSlicer kommen sie aus seinen
  eingebauten Vorgaben.

**Das Fenster ist nicht besser:** `Plater::priv::load_files` legt eine geladene
Projektkonfiguration über `FullPrintConfig::defaults()` („and place the loaded config
over the base“) und übergibt sie `load_config_model` (Quelltext 2.9.4, s. Quellen).
Ohne `printer_settings_id`/`print_settings_id`/`filament_settings_id` in der Beilage
entstehen externe Profile mit dem Dateinamen — auf dieser Maschine steht nach einem
früheren Öffnen in `%APPDATA%\PrusaSlicer\PrusaSlicer.ini` `[presets] printer =
probe-1.3mf`, `print = probe-1.3mf`. Wer danach im Fenster weiterdruckt, druckt mit
diesem Druckerprofil ohne Startcode.

**Warum druckentscheidend:** Ohne MBL (`G29`) liegt die erste Schicht nur am
Referenzpunkt von `G28` richtig; Prusa vermisst das Bett „before each print“
(KB *Mesh bed leveling*). Ohne `M572` fehlt der vom Hersteller für Düse und Filament
gesetzte Pressure-Advance-Wert (KB *Pressure Advance* empfiehlt, den Standardwert zu
behalten). Ohne `M862.3` kann die Firmware eine Datei für einen anderen Drucker
nicht abweisen. Und der Anlass selbst — eine unbrauchbare erste Schicht — hat hier
weitere Ursachen neben den Stützen (B3).

**Änderung:**
1. Prusa wie die Orca-Familie behandeln: Druckerprofil aus dem Bündel wählen
   (`printer_model` + Düse + Variante, B7), Prozess und Filament nach
   `default_print_profile`/`default_filament_profile` bzw. der Wahl im Dialog; die
   ganze Kette mit dem vorhandenen `slicer_profiles.resolve_profile`/`_PrusaStore`
   auflösen und **vollständig** in `solidon.ini` und in `Slic3r_PE.config`
   schreiben (Muster: `prusa-probe/resolve_vendor.py`). Solidons Werte gehen nur noch
   als begründete Abweichung darüber (B2–B8).
2. `has_readable_profiles("prusa")` → `True`, damit `find_profiles` Prusa-Profile
   liefert; `_start_profile_search` (`app/ui/print_settings_dialog.py:3918`) nicht
   mehr früh verlassen. Kennt das Bündel den Drucker nicht (eigener Drucker), bleibt
   der heutige Weg mit einem Befund wie `slicer.printer_unknown`.
3. In die Beilage `printer_settings_id`, `print_settings_id`, `filament_settings_id`
   (und `inherits`) schreiben, damit das Fenster ein installiertes Profil
   wiederverwendet statt ein externes nach dem Dateinamen anzulegen
   (`PresetCollection::load_external_preset` sucht zuerst nach dem Namen aus der
   Konfiguration).
4. `machine_limits_usage = ignore` (`handover.py:982`) entfällt: Der Grund dort
   (eingebaute 1500 mm/s²) verschwindet mit dem echten Druckerprofil;
   `emit_to_gcode` ist der Herstellerwert.
5. Für den Konsolenlauf `binary_gcode = 0` ausdrücklich setzen — Grund am Werkzeug:
   `gcode.analyze_lines` liest Text, und die Herstellerbasis schreibt sonst `bgcode`
   (gemessen: Dateikopf `GCDE`). Für die exportierte 3MF gilt der Herstellerwert.
6. Die drei Docstrings und die Regel in `schichtanalyse.md` richtigstellen.

### B2 — druckentscheidend (der Anlass): feste 45°-Grenze, in jede Übergabe geschrieben

**Hersteller** (`support_material_threshold`, gemessen von der Waagerechten):
MK4S HF0.4 SPEED **35** (eigene Zeile im Abschnitt `[print:0.20mm SPEED @MK4S HF0.4]`),
alle übrigen vorgewählten MK4S-/MINI-IS-/XL-IS-Prozesse **40** (aus
`[print:*MK4IS_common*]`), `*common*` 50. **Vorgabe:** `support_material = 1`,
`support_material_auto = 0` — also „nur an Stützverstärkern“, keine automatischen
Stützen (`*MK4IS_common*`, Erbkette mit `prusa-probe/trace.py`).
**Solidon:** `support_material_threshold = 45` in jeder Übergabe, auch ohne Stützen
(`slicer_keys.py:289` über `_angle_from_horizontal`, `:189–211`; Wert aus
`types.py:1171` = `rules.py:41`).

**Was die Zahl in PrusaSlicer bedeutet (Quelltext `SupportMaterial.cpp` und
`TreeSupport.cpp`, Gitter/eng und organisch gleich):** `threshold_rad = π·(T+1)/180`
— das `+1` macht die Grenze einschließend —, und ein Rand gilt als Überhang, wenn er
weiter als `Schichthöhe / tan(threshold_rad)` über die Schicht darunter hinausragt.
**`0` heißt „automatisch“**: dann ist die Grenze die *halbe Breite der Außenwand*
(`0.5f * fw`; organisch: Mittel über die Bereiche). Tooltip 2.9.6: „Set to zero for
automatic detection (recommended)“ (`prusa-probe/help-fff.txt:1329–1334`).
Umgerechnet bei 0,2 mm Schicht und 0,45 mm Außenwand, gegen die Senkrechte
(Solidons Zählweise):

| PrusaSlicer-Wert | Versatz je Schicht | gegen die Senkrechte |
|---|---|---|
| 35 (MK4S HF SPEED) | 0,275 mm | 54° |
| 40 (übrige) | 0,230 mm | 49° |
| 0 = automatisch | 0,225 mm | 48,4° (hängt an Schicht und Breite) |
| **45 (Solidon)** | 0,193 mm | **44°** |

Solidon stützt also alles zwischen 44° und 54° gegen die Senkrechte, was der
MK4S-Hersteller frei druckt — genau die Fasen und 45–55°-Wände aus dem Anlass.

**Gemessen (Abschnitt 1):** 55,6 m Stützbahn gegen 1,1 m (35) bzw. 12,9 m (40).
**Und Solidons eigene Entscheidung kippt mit derselben Grenze** (`prusa-probe/grenze.py`,
`advise` mit anderer Analysegrenze): bei 45°, 48,4° und 49° schlägt Solidon
„Gitter, nur vom Bett“ vor, **ab 50° nicht mehr** — mit der MK4S-HF-Grenze (54°)
käme der Vorschlag an diesem Körper gar nicht.

**Grund am Code:** `types.py:1172–1180` begründet die 45 mit Konsistenz zur
Schichtanalyse, `rules.py:28–40` mit „dieselbe Linie an drei Stellen“ — ein Grund für
*eine* Zahl, keiner für *diese* Zahl, und keiner am Modell oder Material. Die
Kalibrierung (`types.py:944–950`) ist der einzige vorgesehene Modell-/Materialgrund.

**Änderung:**
1. `support_material_threshold` für Prusa **nicht mehr schreiben** (Zeile 289 für
   `prusa` streichen oder nur bei ausdrücklicher Kundenwahl bzw. vorhandener
   Kalibrierung). Dann gilt 35/40 des gewählten Prozesses.
2. Solidons Analyse (`analysis.py:321`, `advise.py:691–705`, Orientierungssuche,
   Karten) fragt die Grenze **aus dem gewählten Slicerprozess**:
   `90 − (T + 1)` für `T > 0`, und für `T = 0` `atan(0,5 · Außenwandbreite /
   Schichthöhe)` gegen die Senkrechte. Nur so sagen Prüfbericht, Vorschlag und Slicer
   dasselbe; heute sagt Solidon „braucht Stützen“ zu Flächen, die der Hersteller
   trägt. `OVERHANG_LIMIT_DEGREES` bleibt Rückfall ohne bekannten Prozess.
3. **Falle beim Umbau:** Auf der Herstellerbasis steht `support_material_auto = 0`.
   Schaltet Solidon Stützen ein, muss es `support_material = 1` **und**
   `support_material_auto = 1` schreiben (genau das setzt die Auswahl „Überall“ /
   „nur vom Bett“ im Fenster; `help-fff.txt:1269–1272`), sonst entstehen nur Stützen
   in Verstärkern — also keine. Aus: die Herstellervorgabe (1/0) stehen lassen.
4. Besser als plattenweite Stützen (Abschnitt 4, N1): Solidons Inseln und große
   freie Stücke als `SupportEnforcer`-Bereiche übergeben und den Herstellermodus
   „nur Verstärker“ lassen.

### B3 — druckentscheidend: die erste Schicht weicht an sechs Stellen ab

| Schlüssel | Hersteller MK4S / MINI / XL | Solidon | Herkunft | Grund am Code? |
|---|---|---|---|---|
| `first_layer_acceleration` | 500 / 500 / 500 | 0 → Druckbeschleunigung (4000 / 1000 / 2500) | eingebaut | nein (B1) |
| `first_layer_height` | 0,2 | 0,25 | Solidon, `print_settings.toml:52` | nein |
| `first_layer_temperature` PLA | 230 / 230 / 230 | 215 | Solidon, `print_settings.toml:120ff.` | nein (generisch) |
| `elefant_foot_compensation` | 0,2 | 0 | eingebaut | nein (B1) |
| `skirts` / `skirt_distance` | 0 / 6 (Spüllinie im Startcode) | 2 / 3 | Solidon, `types.py:1199–1201` | nein |
| `first_layer_speed` / `first_layer_infill_speed` | 40/100 · 30/45 · 40/100 | 40 · 20 · 25 / 0 (= erste Schicht) | Solidon `printers.toml:209,230,250` / eingebaut | Tempo aus Orcas Prusa-Profil, nicht aus PrusaSlicers |
| `first_layer_extrusion_width` | 0,5 | 0,482 | Solidon, `print_settings.py:216` (×1,07) | nein |

Zusammen mit dem fehlenden MBL und der fehlenden Spüllinie (B1) ist die erste
Schicht bei der Prusa-Übergabe heute nicht die, die Prusa abgestimmt hat.
**Änderung:** Mit der Herstellerbasis (B1) gelten diese Werte von selbst; Solidon
schreibt für die erste Schicht nur noch, was ein Modellbefund verlangt (kleine
Standfläche → Brim, `advise.py:793–839`). Keinen Skirt als Vorgabe schreiben, wo der
Startcode eine Spüllinie legt.

### B4 — Qualität: Temperatur, Fluss und Lüfter kommen aus Solidons Materialtabelle, nicht aus dem Herstellerfilament

| Schlüssel | Hersteller PLA MK4S HF / MK4S 0.4 / MINI IS / XL IS | Solidon PLA | Hersteller PETG MK4S HF / MINI / XL | Solidon PETG |
|---|---|---|---|---|
| `temperature` | 230 / 225 / 220 / 225 | 210 | 255 / 250 / 250 | 240 |
| `first_layer_temperature` | 230 | 215 | 255 / 250 / 250 | 245 |
| `bed_temperature` / erste | 60 / 60 | 60 / 60 | 90/85 · 85/85 · 80/80 | 80 / 80 |
| `extrusion_multiplier` | 1 | **0,98** | 1 | **0,95** |
| `min_fan_speed` / `max_fan_speed` | 70/100 · 70/100 · 100/100 · 100/100 | 50 / 100 | 20/40 · 30/50 · 30/50 | 20 / 50 |
| `fan_below_layer_time` | 17 · 17 · 100 · 100 | 80 | 20 | 30 |
| `slowdown_below_layer_time` | 6 · 6 · 12 · 10 | 8 | 7 · 10 · 9 | 8 |
| `min_print_speed` | 20 · 20 · 15 · 15 | 10 (eingebaut) | — | 10 |
| `full_fan_speed_layer` | 3 · 3 · 4 · 3 | 0 (eingebaut) | 5 · 0 · 5 | 0 |
| `disable_fan_first_layers` | 1 | 1 | 3 | 2 |
| `bridge_fan_speed` | 100 | 100 | 40 · 50 · 50 | 100 |
| `enable_dynamic_fan_speeds` / `overhang_fan_speed_0/1` | 1 / 100/100 (MK4S), 0 (MINI, XL) | 0 (eingebaut) | — | 0 |
| `cooling_slowdown_logic` | consistent_surface (MK4S, XL), uniform_cooling (MINI) | uniform_cooling (eingebaut) | — | — |
| `filament_max_volumetric_speed` | 24 · 15 · 14 · 15 | 15 · — · 12 · 15 | 24 · 9 · 12 | 10 |

**Fundstellen:** `app/core/knowledge/data/print_settings.toml:120–160`
(`[material.pla]`, `[material.petg]`), geschrieben über `slicer_keys.py:248–262` und
`:301–306`. **Grund am Code:** Der Dateikopf sagt selbst „belastbare
Ausgangspunkte …, keine Messungen“ (`print_settings.toml:25–26`); die Lüfterkurve ist
„bei PLA auf dem Profil des Centauri Carbon 2 (50 bis 100 %, 80 s)“
(`print_settings.toml:111–118`) — ein Grund für Elegoo, keiner für Prusa. Der
Fluss 0,98/0,95 ist nirgends begründet. Prusa selbst nennt für die Turbine des MK4S
„60–70 % … most of the time“ (Prusa-Blog MK4S) — daher der untere Wert 70.

**Wirkung:** PETG 10–15 K kälter, 5 % Unterextrusion und 100 % Brückenlüfter statt
40–50 % — das ist das bekannte Rezept für schlechte Schichthaftung bei PETG. PLA mit
210 °C bei den Tempi, die Solidon fährt (bis 15 mm³/s), liegt am unteren Rand dessen,
was Prusa für diesen Fluss abstimmt.

**Änderung:** Mit Herstellerbasis (B1) keine Materialwerte schreiben, solange die
Spule kein eigenes Profil und keine ausdrücklichen Spulenwerte trägt; Solidons
Materialtabelle bleibt Rückfall für Drucker ohne Herstellerprofil. Den Fluss nur aus
einer Kalibrierung (`calibration.py`) schreiben. Heute kommt ein Herstellerfilament
nur, wenn PrusaSlicer eingerichtet ist und die Spule es als `slot.material` trägt
(`handover.settings_for_slot:1044–1050`); Drucker und Prozess nie.

### B5 — Qualität: Prozesswerte ohne Modellgrund

| Schlüssel | Hersteller (MK4S HF SPEED; Abweichung MINI/XL in Abschnitt 3) | Solidon (wirksam) | Herkunft | Grund am Code? |
|---|---|---|---|---|
| `perimeters` | 2 (alle SPEED- und STRUCTURAL-Prozesse) | 3 | Solidon, `print_settings.toml:53` | nein |
| `bottom_solid_layers` | 3 (MK4S/XL SPEED), 4 (MINI, STRUCTURAL) | 4 | Solidon | nein |
| `top_solid_min_thickness` / `bottom_solid_min_thickness` | 0,7 / 0,5 | 0 / 0 | eingebaut | — |
| `perimeter_speed` / `external_perimeter_speed` / `infill_speed` | 250 / 200 / 250 | 166 / 166 / 166 | Solidon (`printers.toml:194–213`, gedeckelt durch `print_settings.py:307–325`) | teilweise: Tempo aus **Orcas** Prusa-Prozess (`printers.toml:19–30`), Deckel auf 15 mm³/s |
| `gap_fill_speed` | 120 | 166 | Solidon (`slicer_keys.py:273`, = Innenwand) | RM-191 (Zeitschätzung), kein Modellgrund |
| `small_perimeter_speed` | 170 | **15** | eingebaut | — |
| `support_material_speed` / `…_interface_speed` | 120 / 50 % | 60 / 100 % | eingebaut | — |
| `top_solid_infill_acceleration` / `bridge_acceleration` / `travel_short_distance_acceleration` | 2000 / 1500 / 250 | 0 (= 4000) | eingebaut | — |
| `enable_dynamic_overhang_speeds` / `overhang_speed_0…3` | 1 / 15, 25, 50, 70 % | 0 / 15, 15, 20, 25 | eingebaut | — |
| `thick_bridges` | 0 | 1 | eingebaut | — |
| `over_bridge_speed` | 35 % | 0 | eingebaut | — |
| `extra_perimeters` / `thin_walls` | 0 / 0 | 1 / 1 | eingebaut | — |
| `infill_anchor` / `infill_anchor_max` / `infill_overlap` / `solid_infill_below_area` | 2 / 12 / 15 % / 0 | 600 % / 50 / 25 % / 70 | eingebaut | — |
| `top_fill_pattern` | monotoniclines | monotonic | eingebaut | — |
| `avoid_crossing_perimeters` | 0 | 1 | Solidon, `types.py:1214–1220` | generisch („Becher voller Fäden“), nicht am Modell |
| `wipe` / `retract_before_wipe` | 0 / 80 % (XL: 1 / 80 %) | 1 / 0 % | Solidon (`types.py:1213`) / eingebaut | nein |
| `retract_length` / `deretract_speed` / `retract_before_travel` / `retract_layer_change` | 0,7 / 25 / 1,5 / 1 | 0,8 / 0 / 2 / 0 | Solidon (Material) / eingebaut | Material, nicht Extruder (B6) |
| `travel_ramping_lift` / `travel_max_lift` / `travel_slope` | 1 / 1,5 / 1 | 0 / 0 / 0 | eingebaut | — |
| `extrusion_width` für Deckfläche / Stütze | 0,42 / 0,4 | 0,45 / 0,45 | Solidon schreibt nur `extrusion_width` | nein |

PrusaSlicer begrenzt jede Bahn selbst auf `filament_max_volumetric_speed` („Limits
the maximum volumetric speed of a print to the minimum of print and filament
volumetric speed“, `help-fff.txt:327–330`). Solidons eigener Deckel
(`print_settings._within_flow`) ist für Prusa deshalb überflüssig und fährt beim HF-
Profil unter dem Hersteller (15 statt 24 mm³/s, B7). Die Zeit am MK4S: 1 h 42 min
gegen 1 h 09 min am selben Teil, dazu +16 % Modellbahn durch die dritte Wand.

**Änderung:** Mit Herstellerbasis gelten diese Werte; Solidon schreibt Wände,
Böden, Tempi, Fahrwege und Rückzug nur, wo ein Befund am Modell sie verlangt
(Verbinder → Wände, `advise.py:1045ff.`; Passungen → Außenwand langsam,
`advise.py:960–1030`; offener Hohlraum → `avoid_crossing_perimeters`, als neuer
Vorschlag). `printers.toml`-Tempi für Prusa-Drucker aus dem PrusaSlicer-Bündel statt
aus Orca (sie sind dann ohnehin nur noch Rückfall).

### B6 — Qualität (MINI: druckentscheidend für Fäden und Zeit): der MINI ist mit Altwerten und Direktantrieb-Rückzug beschrieben

| Schlüssel | Hersteller MINI IS SPEED + Prusament PLA @MINIIS | Solidon MINI |
|---|---|---|
| `perimeter_speed` / `external_perimeter_speed` / `infill_speed` | 140 / 140 / 140 | 50 / 40 / 133 |
| `default_acceleration` / `external_perimeter_acceleration` | 2000 / 2000 | 1000 / 700 |
| `first_layer_speed` | 30 | 20 |
| `bridge_speed` | 50 | 25 |
| `travel_speed` | 400 | 150 |
| `retract_length` / `retract_speed` / `deretract_speed` | **2,5** / 70 / 40 | **0,8** / 35 / 0 (= 35) |
| `filament_max_volumetric_speed` | 14 | 12 |
| Startcode | `M221 S95`, `M572 W0.06`, Filament `M572 S0.27` | fehlt (B1) |

`printers.toml:215–233` trägt für den MINI die Werte des nicht mehr aktuellen
Profils ohne Input Shaper (Prusa: Input Shaper für MINI/+ ab Firmware 5.1.0,
Nicht-IS-Profile „relocated to a Legacy category“, KB *Input Shaper*). Der Rückzug
kommt bei Solidon vom Material (`print_settings.toml:131`, `slicer_keys.py:297`),
aber der MINI hat einen Bowden-Extruder: 0,8 mm sind dort ein Drittel dessen, was
Prusa für ihn setzt. Gemessen: 4 h 34 min gegen 1 h 54 min am selben Teil.
**Änderung:** Rückzug gehört zum Druckerprofil (mit Filament-Überschreibungen wie bei
PrusaSlicer, `filament_retract_*`), nicht zum Material allein; MINI-Werte aus dem
IS-Profil. Mit B1 erledigt sich beides für PrusaSlicer, für die Rückfalltabelle
bleibt es zu korrigieren.

### B7 — Qualität: Solidon kennt die HF-Düse des MK4S nicht

Der MK4S wird mit einer eigenen High-Flow-Düse (CHT-basiert) ausgeliefert
(Prusa-Blog MK4S); im Bündel ist `HF0.4` die erste Variante des Modells
(`[printer_model:MK4S] variants = HF0.4; …`). Das HF-Profil fährt 24 mm³/s,
230 °C und prüft die Düse (`M862.1 … F1`, `nozzle_high_flow = 1`). Solidon:
`prusa-mk4s` mit `flow_factor = 1.25` → 15 mm³/s (`printers.toml:213`), also die
Standarddüse. Mit der Herstellerbasis (B1) prüft die Firmware über
`M862.1 P… F…`, ob die eingestellte Düse zur Datei passt — wählt Solidon die falsche
Variante, bremst der Drucker zu Recht; ohne Variante kann Solidon sie nicht richtig
wählen.
**Änderung:** Düsenvariante (Standard/HF, bei XL ebenso) als Druckereigenschaft;
die Übergabe wählt die passende Druckervariante und nimmt Volumenstrom und
Temperatur aus deren Filamentprofil.

### B8 — Qualität: Stützdetails nach einer Messung an einem anderen Slicer

Wenn Stützen an sind, schreibt Solidon für Prusa `support_material_style = grid` +
`support_material_pattern = rectilinear-grid` (`slicer_keys.py:225, 278–287`),
`support_material_spacing` aus der Stützdichte (`handover.py:638–660`: 0,45/0,15 =
**3 mm**), `interface_layers = 2`, `xy_spacing = 0,5` (`types.py:1181–1184`); der Rest
ist eingebaut.

| Schlüssel | Hersteller (alle drei) | Solidon wirksam |
|---|---|---|
| `support_material_style` / `…_pattern` | snug / rectilinear | grid / rectilinear-grid |
| `support_material_spacing` | 2 | 3 (bzw. 2,92 mit Vorschlag) |
| `support_material_interface_layers` / `…_bottom_interface_layers` | 3 / 0 | 2 / −1 (= wie oben) |
| `support_material_interface_spacing` | 0,2 | 0 (voll) |
| `support_material_xy_spacing` | 80 % (≈ 0,36 mm) | 0,5 mm |
| `support_material_with_sheath` | 0 | 1 |
| `support_material_extrusion_width` | 0,4 | 0 (= 0,45) |
| `dont_support_bridges` | 0 | 1 |
| `support_tree_top_rate` / `support_tree_branch_diameter_double_wall` | 30 % / 8 | 15 % / 3 |
| `support_material_speed` / `…_interface_speed` | 120 / 50 % | 60 / 100 % |

**Grund am Code:** das Kreuzmuster ist an der Waschschüssel im **ElegooSlicer**
gemessen (`slicer_keys.py:280–286`: Elegoos `rectilinear` mit 2,8 mm Abstand kippte);
für PrusaSlicer gibt es keine Messung, und Solidons Abstand von 3 mm ist sogar
weiter als Prusas 2 mm — ob das Kreuzmuster das bei Prusa ausgleicht, ist nicht
gemessen. Die Schnittstelle schreibt Solidon nicht; sie fällt auf die eingebaute
Vorgabe 0 (voll geschlossen) statt Prusas 0,2 mm Linienabstand — die Unterseite des
Teils liegt damit auf einer geschlossenen Fläche, was das Ablösen erschwert
(Einschätzung, nicht gemessen).
**Änderung:** Für Prusa nur „an/aus“, „nur vom Bett“ und „organisch“ übersetzen;
Muster, Abstände, Schnittstelle und XY-Abstand beim Herstellerprozess lassen, bis eine
PrusaSlicer-Messung am Modell etwas anderes belegt. Die Stützdichte des Dialogs dann
für Prusa als nicht übernommen führen (`NOT_TAKEN_BY`) oder erst bei Abweichung vom
Hersteller schreiben.

### B9 — Kosmetik/Komfort: was mit dem Druckerprofil verloren geht

`thumbnails` (keine Vorschau am Druckerdisplay), `remaining_times` (kein `M73`,
keine Restzeit), `gcode_label_objects = firmware` (kein Abbrechen einzelner Objekte),
`arc_fitting`, `binary_gcode`, `gcode_resolution` 0,008 statt 0,0125. Alle kommen mit
B1 zurück; `binary_gcode` für den Rücklese-Lauf ausgenommen (B1, Punkt 5).

### B10 — Kosmetik: Beilage und Rücklesen

- Die Gegenprobe `verify` prüft heute nur die 63 geschriebenen Werte; dass
  `start_gcode`, `printer_model`, `gcode_flavor` eingebaut sind, fällt ihr nicht auf.
  Mit B1 sollte sie `printer_model` und `printer_settings_id` im G-Code gegen die
  Wahl prüfen — eine Zusage, deren Einlösen man in der Datei sieht
  (`.claude/rules/dateiformat.md`, „Eine gelungene Übergabe ist noch kein vollständiger
  Druck“).
- `support_material_threshold` steht auch ohne Stützen in jeder Datei und in der
  Gegenprobe; das verschleiert, dass der Wert nichts bewirkt, bis Stützen an sind.

### B11 — Qualität: PETG geht als PLA hinaus

Die Prusa-Tabelle (`slicer_keys.py:227–307`) hat keine Zeile für `filament_type`;
die Orca-Familie bekommt ihn (`handover.py:1933–1936`), PrusaSlicer nicht. Im G-Code
des PETG-Laufs steht deshalb die eingebaute Vorgabe: `; filament_type = PLA`,
`; filament_settings_id = ""` (`lauf/prusa-mk4s/petg/standard/solidon.gcode`,
gemessen). Folgen: Die Buddy-Firmware vergleicht den Filamenttyp der Datei mit dem
geladenen und meldet sonst „A filament specified in the G-code is either not loaded
or wrong type“ (KB *Print preview wrong filament*) — bei geladenem PETG ist diese
Meldung zu erwarten (Schluss aus KB und Datei, nicht am Drucker gemessen). Mit der
Herstellerbasis (B1) wählte Prusas Startcode außerdem die MBL-Temperatur nach dem Typ
(PET → 175 °C statt 170, N7).
**Änderung:** Zeile `("filament.…", "filament_type", …)` bzw. dieselbe Herleitung wie
für Orca (`slicer_keys.filament_type(profile.material.id)`) auch für `prusa`; mit
Herstellerfilament gilt dessen Typ.

---

## 3. Abgleich je Schlüssel: Hersteller gegen Solidon „Standard“, PLA

Hersteller: aufgelöste Kette Drucker + vorgewählter Prozess + Prusament PLA
(`v_mk4s_hf04_speed_pla.ini`, `v_mini_speed_pla.ini`, `v_xl_speed_pla.ini`).
Solidon: wirksamer Wert laut Konfigurationsblock im G-Code des Standardlaufs
(`lauf/prusa-*/pla/standard/solidon.gcode`). Ein Wert gilt für alle drei, wo nur
einer steht; „(=)“ heißt gleich. „Herkunft“: von Solidon geschrieben oder
PrusaSlicers eingebaute Vorgabe. Mit übernommenem Stützvorschlag ändern sich die
Stützzeilen wie in B8 beschrieben (`rectilinear-grid`, Abstand 2,92). PETG steht in B4,
die MK4S-Standarddüse (`0.20mm SPEED @MK4S 0.4`, 225 °C, 15 mm³/s, 170 mm/s) in
`prusa-probe/v_mk4s_04_speed_pla.ini`.

| Thema | Schlüssel | Hersteller MK4S HF / MINI IS / XL IS | Solidon MK4S / MINI / XL | Herkunft | Grund am Code? | Empfehlung |
|---|---|---|---|---|---|---|
| Stützen | `support_material` | 1 | 0 | Solidon | an/aus aus `support.style` | an: 1 **und** `support_material_auto = 1`; aus: Hersteller (B2.3) |
| Stützen | `support_material_auto` | 0 | 1 | eingebaut | nicht geschrieben | mit „an“ zusammen schreiben (B2.3) |
| Stützen | `support_material_threshold` | 35 / 40 / 40 | 45 | Solidon | Konsistenz mit Analyse, kein Modellgrund | nicht schreiben; Analyse fragt 90−(T+1) (B2) |
| Stützen | `support_material_buildplate_only` | 0 | 0 (=) | Solidon | aus `advise.py:739–773` (Stützort) | behalten — Modellgrund |
| Stützen | `support_material_style` | snug | grid | Solidon | Messung im ElegooSlicer (`slicer_keys.py:280–286`) | Hersteller (snug); organisch nur auf Wahl (B8) |
| Stützen | `support_material_pattern` | rectilinear | rectilinear (=) | eingebaut | wie oben | Hersteller (B8) |
| Stützen | `support_material_spacing` | 2 | 3 | Solidon | aus Vorgabedichte 0,15 (`handover.py:638–660`) | Hersteller (B8) |
| Stützen | `support_material_contact_distance` | 0.2 | 0.2 (=) | Solidon | Vorgabe `types.py:1181` | gleich; nicht schreiben |
| Stützen | `support_material_bottom_contact_distance` | 0 | 0 (=) | eingebaut | nicht geschrieben | Herstellerwert (B1) |
| Stützen | `support_material_interface_layers` | 3 | 2 | Solidon | Vorgabe `types.py:1184` | Hersteller (B8) |
| Stützen | `support_material_bottom_interface_layers` | 0 | -1 | eingebaut | nicht geschrieben | Herstellerwert (B1) |
| Stützen | `support_material_interface_spacing` | 0.2 | 0 | eingebaut | nicht geschrieben | Herstellerwert (B1) |
| Stützen | `support_material_xy_spacing` | 80% | 0.5 | Solidon | Vorgabe `types.py:1182` | Hersteller (B8) |
| Stützen | `support_material_with_sheath` | 0 | 1 | eingebaut | nicht geschrieben | Herstellerwert (B1) |
| Stützen | `dont_support_bridges` | 0 | 1 | eingebaut | nicht geschrieben | Herstellerwert (B1) |
| Stützen | `support_material_speed` | 120 / 100 / 110 | 60 | eingebaut | nicht geschrieben | Herstellerwert (B1) |
| Stützen | `support_tree_top_rate` | 30% | 15% | eingebaut | nicht geschrieben | Herstellerwert (B1) |
| Erste Schicht | `first_layer_height` | 0.2 | 0.25 | Solidon | nein (`print_settings.toml:52`) | Hersteller (B3) |
| Erste Schicht | `first_layer_extrusion_width` | 0.5 | 0.482 | Solidon | nein (×1,07, `print_settings.py:216`) | Hersteller (B3) |
| Erste Schicht | `first_layer_speed` | 40 / 30 / 40 | 40 / 20 / 25 | Solidon | Orcas Prusa-Tempo (`printers.toml`) | Hersteller (B3) |
| Erste Schicht | `first_layer_infill_speed` | 100 / 45 / 100 | 0 | eingebaut | nicht geschrieben | Herstellerwert (B1) |
| Erste Schicht | `first_layer_acceleration` | 500 | 0 | eingebaut | nicht geschrieben | Herstellerwert (B1) |
| Erste Schicht | `first_layer_temperature` | 230 | 215 | Solidon | generisch (`print_settings.toml:120ff.`) | Herstellerfilament (B4) |
| Erste Schicht | `elefant_foot_compensation` | 0.2 | 0 | eingebaut | nicht geschrieben | Herstellerwert (B1) |
| Rand | `skirts` | 0 | 2 | Solidon | Vorgabe `types.py:1200` | Hersteller (Spüllinie im Startcode) |
| Rand | `skirt_distance` | 6 | 3 | Solidon | Vorgabe `types.py:1201` | Hersteller |
| Rand | `brim_width` | 0 | 0 (=) | Solidon | nur bei Haftungsart Brim | bei Brim-Vorschlag (Modellgrund) schreiben |
| Rand | `brim_separation` | 0.1 | 0 | eingebaut | nicht geschrieben | Herstellerwert (B1) |
| Wände | `perimeters` | 2 | 3 | Solidon | nein (`print_settings.toml:53`) | Hersteller; mehr nur per Modellvorschlag (B5) |
| Wände | `perimeter_generator` | arachne | arachne (=) | Solidon | `types.py:1079` (§2.4) | gleich |
| Wände | `external_perimeters_first` | 0 | 0 (=) | Solidon | Vorgabe; Vorschlag bei Passung/Keil | nur per Vorschlag schreiben |
| Wände | `extra_perimeters` | 0 | 1 | eingebaut | nicht geschrieben | Herstellerwert (B1) |
| Wände | `extra_perimeters_on_overhangs` | 0 | 0 (=) | eingebaut | nicht geschrieben | Hersteller; als Modellvorschlag erwägen (N3) |
| Wände | `thin_walls` | 0 | 1 | eingebaut | nicht geschrieben | Herstellerwert (B1) |
| Wände | `ensure_vertical_shell_thickness` | enabled | enabled (=) | eingebaut | nicht geschrieben | gleich |
| Wände | `seam_position` | aligned | aligned (=) | Solidon | Vorgabe `types.py:1078` | gleich; nicht schreiben |
| Deckel/Boden | `top_solid_layers` | 5 | 5 (=) | Solidon | Stufe | gleich |
| Deckel/Boden | `bottom_solid_layers` | 3 / 4 / 3 | 4 | Solidon | nein | Hersteller (B5) |
| Deckel/Boden | `top_solid_min_thickness` | 0.7 | 0 | eingebaut | nicht geschrieben | Herstellerwert (B1) |
| Deckel/Boden | `bottom_solid_min_thickness` | 0.5 | 0 | eingebaut | nicht geschrieben | Herstellerwert (B1) |
| Deckel/Boden | `top_fill_pattern` | monotoniclines | monotonic | eingebaut | nicht geschrieben | Herstellerwert (B1) |
| Deckel/Boden | `ironing` | 0 | 0 (=) | Solidon | Vorschlag bei bündiger Passung (`advise.py:970–981`) | nur per Vorschlag schreiben |
| Füllung | `fill_pattern` | grid | grid (=) | Solidon | Stufe | gleich |
| Füllung | `fill_density` | 15% | 15% (=) | Solidon | Stufe | gleich |
| Füllung | `infill_anchor` | 2 / 2.5 / 2 | 600% | eingebaut | nicht geschrieben | Herstellerwert (B1) |
| Füllung | `infill_overlap` | 15% | 25% | eingebaut | nicht geschrieben | Herstellerwert (B1) |
| Füllung | `solid_infill_below_area` | 0 | 70 | eingebaut | nicht geschrieben | Herstellerwert (B1) |
| Tempo | `perimeter_speed` | 250 / 140 / 170 | 166 / 50 / 166 | Solidon | Orcas Prusa-Tempo, Volumenstromdeckel | Hersteller; PrusaSlicer deckelt selbst (B5) |
| Tempo | `external_perimeter_speed` | 200 / 140 / 170 | 166 / 40 / 166 | Solidon | wie oben; Passung → 30 (`advise.py:1006–1017`) | Hersteller; Passungsvorschlag bleibt |
| Tempo | `small_perimeter_speed` | 170 / 140 / 170 | 15 | eingebaut | nicht geschrieben | Herstellerwert (B1) |
| Tempo | `infill_speed` | 250 / 140 / 200 | 166 / 133 / 166 | Solidon | wie oben | Hersteller (B5) |
| Tempo | `solid_infill_speed` | 250 / 140 / 200 | 166 / 133 / 166 | Solidon | RM-191 (Zeitschätzung) | Hersteller (B5) |
| Tempo | `top_solid_infill_speed` | 100 / 80 / 100 | 100 / 40 / 100 | Solidon | Orcas Prusa-Tempo | Hersteller |
| Tempo | `gap_fill_speed` | 120 / 80 / 120 | 166 / 50 / 166 | Solidon | RM-191 | Hersteller |
| Tempo | `bridge_speed` | 50 | 50 / 25 / 50 | Solidon | Orcas Prusa-Tempo; Vorschlag ≤ Außenwand | Hersteller; Vorschlag bleibt |
| Tempo | `travel_speed` | 300 / 400 / 400 | 300 / 150 / 400 | Solidon | Drucker (`printers.toml`) | Hersteller |
| Beschleunigung | `default_acceleration` | 4000 / 2000 / 2500 | 4000 / 1000 / 2500 | Solidon | Orcas Prusa-Wert | Hersteller |
| Beschleunigung | `external_perimeter_acceleration` | 4000 / 2000 / 2500 | 4000 / 700 / 2500 | Solidon | Orcas Prusa-Wert; Passung → vorsichtig | Hersteller; Passungsvorschlag bleibt |
| Beschleunigung | `perimeter_acceleration` | 4000 / 2500 / 3000 | 0 | eingebaut | nicht geschrieben | Herstellerwert (B1) |
| Beschleunigung | `top_solid_infill_acceleration` | 2000 / 1000 / 1500 | 0 | eingebaut | nicht geschrieben | Herstellerwert (B1) |
| Beschleunigung | `bridge_acceleration` | 1500 | 0 | eingebaut | nicht geschrieben | Herstellerwert (B1) |
| Beschleunigung | `travel_short_distance_acceleration` | 250 | 0 | eingebaut | nicht geschrieben | Herstellerwert (B1) |
| Volumenstrom | `filament_max_volumetric_speed` | 24 / 14 / 15 | 15 / 12 / 15 | Solidon | Material × `flow_factor` (Standarddüse) | Herstellerfilament der Düsenvariante (B7) |
| Überhänge | `overhangs` | 1 | 1 (=) | eingebaut | nicht geschrieben | gleich |
| Überhänge | `enable_dynamic_overhang_speeds` | 1 | 0 | eingebaut | nicht geschrieben | Herstellerwert (B1) |
| Überhänge | `overhang_speed_2` | 50 / 25 / 30 | 20 | eingebaut | nicht geschrieben | Herstellerwert (B1) |
| Überhänge | `enable_dynamic_fan_speeds` | 1 / 0 / 0 | 0 | eingebaut | nicht geschrieben | Herstellerwert (B1) |
| Brücken | `thick_bridges` | 0 | 1 | eingebaut | nicht geschrieben | Herstellerwert (B1) |
| Brücken | `over_bridge_speed` | 35% / 50% / 50% | 0 | eingebaut | nicht geschrieben | Herstellerwert (B1) |
| Brücken | `bridge_fan_speed` | 100 | 100 (=) | Solidon | Material | Herstellerfilament (B4) |
| Kühlung | `min_fan_speed` | 70 / 100 / 100 | 50 | Solidon | Centauri-Kurve (`print_settings.toml:111–118`) | Herstellerfilament (B4) |
| Kühlung | `max_fan_speed` | 100 | 100 (=) | Solidon | Material | Herstellerfilament (B4) |
| Kühlung | `fan_below_layer_time` | 17 / 100 / 100 | 80 | Solidon | Centauri-Kurve | Herstellerfilament (B4) |
| Kühlung | `slowdown_below_layer_time` | 6 / 12 / 10 | 8 | Solidon | Stufe (8 s) | Herstellerfilament; Vorschlag bei dünnen Schichten bleibt (`advise.py:944–956`) |
| Kühlung | `min_print_speed` | 20 / 15 / 15 | 10 | eingebaut | nicht geschrieben | Herstellerwert (B1) |
| Kühlung | `disable_fan_first_layers` | 1 | 1 (=) | Solidon | Material | Herstellerfilament (B4) |
| Kühlung | `full_fan_speed_layer` | 3 / 4 / 3 | 0 | eingebaut | nicht geschrieben | Herstellerwert (B1) |
| Kühlung | `cooling_slowdown_logic` | consistent_surf… / uniform_cooling / consistent_surf… | uniform_cooling | eingebaut | nicht geschrieben | Herstellerwert (B1) |
| Temperatur | `temperature` | 230 / 220 / 225 | 210 | Solidon | generisch | Herstellerfilament (B4) |
| Temperatur | `bed_temperature` | 60 | 60 (=) | Solidon | generisch | Herstellerfilament (B4) |
| Material | `extrusion_multiplier` | 1 | 0.98 | Solidon | nein (0,98/0,95) | nur aus Kalibrierung (B4) |
| Rückzug | `retract_length` | 0.7 / 2.5 / 0.8 | 0.8 | Solidon | Material, nicht Extruder | Druckerprofil + Filament-Überschreibung (B6) |
| Rückzug | `retract_speed` | 35 / 70 / 35 | 35 | Solidon | Material | Druckerprofil (B6) |
| Rückzug | `deretract_speed` | 25 / 40 / 25 | 0 | eingebaut | nicht geschrieben | Herstellerwert (B1) |
| Rückzug | `retract_lift` | 0.2 / 0.2 / 0.3 | 0.2 | Solidon | Material (`z_hop`) | Druckerprofil + Filament-Überschreibung |
| Rückzug | `retract_before_travel` | 1.5 | 2 | eingebaut | nicht geschrieben | Herstellerwert (B1) |
| Rückzug | `retract_layer_change` | 1 | 0 | eingebaut | nicht geschrieben | Herstellerwert (B1) |
| Rückzug | `wipe` | 0 / 0 / 1 | 1 | Solidon | Vorgabe `types.py:1213`, ohne Grund | Hersteller (B5) |
| Rückzug | `retract_before_wipe` | 80 / 70% / 80% | 0% | eingebaut | nicht geschrieben | Herstellerwert (B1) |
| Rückzug | `travel_ramping_lift` | 1 / 0 / 1 | 0 | eingebaut | nicht geschrieben | Herstellerwert (B1) |
| Fahrwege | `avoid_crossing_perimeters` | 0 | 1 | Solidon | generisch (`types.py:1214–1220`) | Hersteller; bei offenen Hohlräumen als Vorschlag |
| Maschine | `gcode_flavor` | marlin2 | reprap | eingebaut | nicht geschrieben | Herstellerwert (B1) |
| Maschine | `printer_model` | MK4S / MINIIS / XLIS |  | eingebaut | nicht geschrieben | Herstellerwert (B1) |
| Maschine | `use_relative_e_distances` | 1 | 0 | eingebaut | nicht geschrieben | Herstellerwert (B1) |
| Maschine | `machine_limits_usage` | emit_to_gcode | ignore | Solidon | Workaround für eingebaute Grenzen (`handover.py:975–982`) | Hersteller (emit_to_gcode) (B1) |
| Maschine | `binary_gcode` | 1 | 0 | eingebaut | nicht geschrieben | 0 nur im Konsolenlauf (Rücklesen), sonst Hersteller |
| Maschine | `remaining_times` | 1 | 0 | eingebaut | nicht geschrieben | Herstellerwert (B1) |
| Maschine | `gcode_label_objects` | firmware | disabled | eingebaut | nicht geschrieben | Herstellerwert (B1) |
| Maschine | `arc_fitting` | emit_center | disabled | eingebaut | nicht geschrieben | Herstellerwert (B1) |
| Maschine | `nozzle_high_flow` | 1 / 0 / 0 | 0 | eingebaut | nicht geschrieben | aus Düsenvariante (B7) |

**Zählung:** Von den 100 Zeilen sind 19 gleich. Von den 81 abweichenden sind 45
eingebaute Vorgaben (B1), 36 schreibt Solidon selbst. Für keinen dieser 36 Werte in
„Standard“ steht ein Grund am Modell oder am Material im Code. Modellgründe trägt
Solidon nur in **Vorschlägen**, die auf Klick kommen und bleiben sollen: Stützort
(`support_material_buildplate_only`, `advise.py:739–773`), Brim bei kleiner
Standfläche, Passungs- und Keil-Vorschläge für Außenwand, Reihenfolge und Bügeln,
Mindestschichtzeit bei dünnen Schichten, Wände an Verbindern.

---

## 4. Was Solidon für PrusaSlicer nicht nutzt, obwohl es je Modell zählt

### N1 — Qualität (bei Sätzen wie dem Minigolf druckentscheidend): Stützen gelten plattenweit statt je Teil

`advise.combine` (`app/core/slice/advise.py:274–299`) macht aus dem Stützbedarf
*eines* Körpers eine Einstellung der ganzen Platte („Ein Würfel kann die schon
eingeschalteten Stützen seines Nachbarn nicht abschalten“); `for_part`
(`advise.py:1165–1195`) überträgt je Teil nur die Haftung und begründet das mit
„Temperatur, Kühlung und **Stützen** bleiben plattenweit: sie hängen am Material oder
an der Maschine“ (`:1175–1177`). Für Stützen stimmt das nicht: Sie hängen an der
Geometrie des einzelnen Körpers, und PrusaSlicer führt sämtliche Stützschlüssel je
Objekt (KB *Per model settings*: „Object settings to modify – Support material …
will affect only the relevant object“). Solidon schreibt Objektwerte bereits
(`threemf._prusa_settings_xml`, `threemf.py:380–386`, `metadata type="object"`).
Bei einem Satz aus dreißig Teilen stützt heute ein einziger Körper mit Überhang alle
anderen mit — mit der 45°-Grenze aus B2 an jeder Fase.
**Änderung:** Stützvorschläge (`support.style`, `placement`, `block_channels`) je
Teil als Objektwerte in `Slic3r_PE_model.config` (`support_material`,
`support_material_auto`, `support_material_buildplate_only`, bei Bedarf
`support_material_style`); plattenweit bleibt die Herstellervorgabe.

### N2 — Qualität: Stützverstärker statt Schwelle

Prusas Vorgabe ist „nur Verstärker“ (B2). Die KB empfiehlt genau diesen Modus für
gezielt gesetzte Stützen („If you're painting support enforcers, it makes the most
sense to change supports to *For support enforcers only*“, KB *Paint-on supports*).
Solidon kennt die Stellen, die wirklich Stütze brauchen — Inseln mit Ort
(`slice/findings.py`), größtes freies Stück (`largest_overhang_patch`), Stützort
außen/Kanal (`model_support`) — und schreibt schon einen Sperrbereich als Volumen
(`SupportBlocker`, `threemf.py:394–415`). Derselbe Weg mit `volume_type =
SupportEnforcer` über den Inseln und großen Stücken ergäbe Stützen genau dort, und
die Schwelle bliebe für den Rest ohne Wirkung. Der Leser dafür existiert schon
(`app/core/ingest/threemf.py:220`).

### N3 — Qualität: Überhänge ohne Stützen drucken

`extra_perimeters_on_overhangs` (2.6: „Detect overhang areas where bridges cannot be
anchored, and fill them with extra perimeter paths“, `help-fff.txt:1074–1077`) ist bei
Hersteller und Solidon aus. Für Modelle mit mäßigen, aber nicht verankerten
Überhängen ist das ein Vorschlag, der Stützen spart. Dynamische Überhangtempi und
-lüfter (`enable_dynamic_overhang_speeds`, `enable_dynamic_fan_speeds`) hat der
MK4S-Hersteller an; sie kommen mit B1.

### N4 — Qualität: Maßhaltigkeit und Passungen

- `filament_shrinkage_compensation_xy`/`_z` (Schrumpfausgleich je Filament, 0 %
  bei Prusament PLA): Solidon rechnet Passungen mit Toleranzen aus dem
  Materialprofil (`auto:<material>`). Ob eine gemessene Schwindung zusätzlich hier
  übergeben oder weiter in die Toleranz eingerechnet wird, ist eine Entscheidung —
  doppelt darf sie nicht wirken.
- `elefant_foot_compensation` (Hersteller 0,2, B3): wirkt direkt auf das Maß der
  untersten Schicht — für Passungen am Boden relevant.
- `min_feature_size` (25 %), `wall_distribution_count`, `wall_transition_*`:
  Solidons Messung der schmalsten Stelle (`advise.py:854–908`) schlägt heute eine
  Bahnbreite vor; bei Arachne wäre `min_feature_size` der zweite, engere Hebel.

### N5 — Kosmetik bis Qualität: Sichtflächen

- `scarf_seam_placement` (2.9: nowhere/contours/everywhere) und
  `staggered_inner_seams`: bei Sichtflächen mit Naht ein Vorschlag, den Solidon
  aus den geschützten Flächen (`Document.protected`) ableiten könnte.
- `ironing_type` (top/topmost/solid) — Solidon schaltet nur an/aus, der Typ bleibt
  „top“ (alle Deckflächen); wo nur die oberste Sichtfläche zählt, spart `topmost` Zeit.
- `top_one_perimeter_type`, `only_one_perimeter_first_layer`.

### N6 — Qualität: Haftung

- `brim_type` (outer_only/inner_only/outer_and_inner) und `brim_separation`
  (Hersteller 0,1 mm, erleichtert das Ablösen): Solidon schreibt nur die Breite.
- `support_material_enforce_layers` („useful for getting more adhesion of objects
  having a very thin or poor footprint“, `help-fff.txt`): ein zweiter Weg neben Brim
  für Teile auf kleinen Füßen.
- `draft_shield` für ASA/ABS auf offenen Druckern (MK4S, MINI, XL sind offen):
  ein Materialbefund, den Solidon heute nur als Satz führt.

### N7 — Qualität: Materialschlüssel, die der Startcode liest

Prusas Startcode wählt die MBL-Temperatur über `filament_type` und
`filament_notes` (`MBL160`, `HT_MBL10`, PET → 175 °C, FLEX → 210 °C, PC/PA →
erste Schicht −25 K) und prüft `filament_abrasive` (`M862.1 … A`). Mit der
Herstellerbasis (B1) muss Solidon diese Schlüssel aus dem Herstellerfilament
stehen lassen, sonst vermisst der Drucker PETG bei 170 statt 175 °C; bei einem
eigenen Material ohne Herstellerprofil gehört `filament_type` korrekt gesetzt
(`slicer_keys.filament_type` gibt es schon; heute fehlt er für Prusa ganz, B11).

### N8 — Mehrere Filamente

Bekannt und gemeldet (`slicer.overrides_unreachable`): Über diesen Weg druckt
PrusaSlicer nur das erste Filament. XL mit mehreren Köpfen und MMU3 können mehr;
mit der Herstellerbasis (Drucker „XL - 2T/5T“, Filament je Extruder) wäre das
erreichbar — außerhalb dieses Auftrags, aber dieselbe Baustelle.

---

## 5. Eigenheiten der Konsole gegenüber dem Fenster (gemessen, 2.9.6)

| Frage | Konsole (`prusa-slicer-console.exe`) | Fenster (`prusa-slicer.exe`) |
|---|---|---|
| Woher kommt, was Solidon nicht schreibt? | eingebaute Vorgaben; Vorrang laut `--help`: Kommandozeile > `--load` > Werte aus der 3MF | eingebaute Vorgaben unter der 3MF-Beilage (`FullPrintConfig::defaults()`, Plater.cpp) |
| Profilwahl | `--printer-profile`/`--print-profile`/`--material-profile` gibt es, übernahmen hier aber nur den Prozess (Methode, Nebenbefund) — nicht verwenden, vollständige INI laden | Beilage mit `*_settings_id` → installiertes Profil „(modified)“, sonst externes Profil nach Dateinamen, das danach aktiv bleibt (`PrusaSlicer.ini [presets]`) |
| Anordnen | Lage aus der 3MF bleibt: um 60 mm verschobene Platte ohne und mit `--dont-arrange` bitgleich bei X 70,5 (`prusa-probe/anordnung/`) | ordnet nur auf Befehl |
| Druckerprüfung | keine: ohne `printer_model` fehlen `M862.3`/`M862.1` in der Datei | ebenso |
| Binäres G-Code | folgt `binary_gcode` (Herstellerbasis → `GCDE`-Kopf, gemessen) | zusätzlich Voreinstellung `use_binary_gcode_when_supported` |
| Bauraum | Solidon verschiebt in Bettkoordinaten; Bettform schreibt Solidon selbst (`handover.py:970`) — stimmt mit dem Bündel überein (MK4S 250×210×220, MINI 180×180×180, XL 360×360×360) | ebenso |
| Stützwarnung | keine | seit 2.6 prüft der Stützmaler beim Slicen selbst und warnt, „if a print needs supports“ (Prusa-Blog 2.6; App-Einstellung `alert_when_supports_needed = 1` auf dieser Maschine) |

---

## 6. Quellen

Lokal (Primärquellen, auf dieser Maschine):
- PrusaSlicer 2.9.6, `prusa-slicer-console.exe --help` und `--help-fff`
  (`prusa-probe/help-fff.txt`, Tooltips zu jedem genannten Schlüssel).
- Herstellerbündel `C:\Program Files\Prusa3D\PrusaSlicer\resources\profiles\PrusaResearch.ini`,
  `config_version = 2.4.14`; aufgelöst in `prusa-probe/v_*.ini`, Erbketten mit
  `prusa-probe/trace.py`.
- Messläufe: `prusa-probe/lauf/` (Solidon), `prusa-probe/hersteller/` (Hersteller),
  `prusa-probe/grenze.py` (Stützentscheidung gegen die Grenze), `prusa-probe/anordnung/`.

PrusaSlicer-Quelltext (Tag `version_2.9.4`; Verhalten mit der installierten 2.9.6
an den Messungen gegengeprüft):
- Stützschwelle, `+1`, Automatik `0.5f * fw`:
  https://github.com/prusa3d/PrusaSlicer/blob/version_2.9.4/src/libslic3r/Support/SupportMaterial.cpp
- Dieselbe Regel für organische Stützen (`support_threshold_auto`, halbe Außenwand):
  https://github.com/prusa3d/PrusaSlicer/blob/version_2.9.4/src/libslic3r/Support/TreeSupport.cpp
- 3MF-Konfiguration über `FullPrintConfig::defaults()`, `load_config_model`:
  https://github.com/prusa3d/PrusaSlicer/blob/version_2.9.4/src/slic3r/GUI/Plater.cpp
- `PresetCollection::load_external_preset` (Wiederverwendung über den Profilnamen):
  https://github.com/prusa3d/PrusaSlicer/blob/version_2.9.4/src/libslic3r/Preset.cpp

Prusa Knowledge Base und Blog:
- Support material: https://help.prusa3d.com/article/support-material_1698
- Organic supports: https://help.prusa3d.com/article/organic-supports_480131
- Paint-on supports (Modus „For support enforcers only“): https://help.prusa3d.com/article/paint-on-supports_168584
- Per model settings (Stützen je Objekt): https://help.prusa3d.com/article/per-model-settings_1674
- Mesh bed leveling („before each print“): https://help.prusa3d.com/article/mesh-bed-leveling_112163
- Pressure Advance (M572, Standardwert behalten): https://help.prusa3d.com/article/pressure-advance_814986
- Print preview wrong filament (Typvergleich Datei gegen geladenes Filament):
  https://help.prusa3d.com/article/print-preview-wrong-filament-31805-core-one-35805-core-one-l-26805-mk4s-27805-mk3-9s-28805-mk3-5s-13805-mk4-21805-mk3-9-23805-mk3-5-17805-xl-12805-mini_899400
- The G-code isn't fully compatible (Prüfungen M862.1/.3/.5/.6):
  https://help.prusa3d.com/article/the-g-code-isnt-fully-compatible-31803-core-one-26803-mk4s-27803-mk3-9s-28803-mk3-5s-13803-mk4-21803-mk3-9-23803-mk3-5-17803-xl-12803-mini_899392
- Input Shaper (IS-Profil nötig, Nicht-IS-Profile „Legacy“, MINI/XL ab FW 5.1.0):
  https://help.prusa3d.com/article/input-shaper-core-one-mk4-s-mk3-9-s-mk3-5-s-xl-mini_451816
- Support settings for the XL: https://help.prusa3d.com/article/support-settings-for-the-xl_681927
- MK4S mit High-Flow-Düse, Turbine 60–70 %, Profile für HF und Standard:
  https://blog.prusa3d.com/the-original-prusa-mk4s-is-here_100605/
- PrusaSlicer 2.6 (organische Stützen, dynamische Überhangtempi, Stützwarnung beim Slicen):
  https://blog.prusa3d.com/prusaslicer-2-6-is-here-organic-supports-text-embossing-new-cut-tool-and-more_79322/

Nicht als Tatsache übernommen: Forenbeiträge (etwa zur Vorauswahl der HF-Variante
im Assistenten) — dort nur Hinweis, die Aussage im Bericht stützt sich auf die
Variantenliste des Bündels und den Prusa-Blog.

---

## 7. Kurzfassung — die zehn wichtigsten Änderungen

1. **Herstellerprofil als Basis (B1, druckentscheidend):** Drucker + Prozess + Filament aus `PrusaResearch.ini` auflösen und vollständig in `solidon.ini` und `Slic3r_PE.config` schreiben; heute gelten 284 von 347 Werten als PrusaSlicer-Vorgabe — ohne MBL, Spüllinie, `M862`, `M572`, `marlin2`.
2. **`support_material_threshold` nicht mehr schreiben (B2):** Hersteller 35 (MK4S HF) / 40, Solidon 45 = 44° statt 54°/49° gegen die Senkrechte; Minigolf-Körper 55,6 m Stütze gegen 1,1 m.
3. **Solidons Analyse fragt die Grenze des gewählten Prozesses** (`90 − (T+1)`, bei 0: halbe Außenwand/Schicht); ab 50° entfällt der Stützvorschlag am Anlassteil.
4. **Stützen an = `support_material` 1 und `support_material_auto` 1** (Herstellerbasis hat auto 0 — sonst keine Stützen).
5. **Stützen je Teil statt plattenweit (N1)** und **Verstärker statt Schwelle (N2):** Objektwerte und `SupportEnforcer` über Inseln/großen Stücken.
6. **Erste Schicht nicht überschreiben (B3):** 0,2 mm, 230 °C, 500 mm/s², Elefantenfuß 0,2, Spüllinie statt Skirt.
7. **Material aus dem Herstellerfilament (B4, B11):** PLA 225–230 °C, PETG 250–255/85–90 °C, Fluss 1,0 statt 0,98/0,95, Prusa-Lüfterkurven, `filament_type` schreiben (PETG geht heute als PLA hinaus).
8. **Stützdetails beim Hersteller lassen (B8):** snug/rectilinear, 2 mm, 3 Schnittstellen mit 0,2 mm, XY 80 %; das Kreuzmuster ist nur im ElegooSlicer begründet.
9. **Prozesswerte nur mit Modellgrund (B5):** 2 statt 3 Wände, keine eigenen Tempodeckel (PrusaSlicer deckelt selbst), kein `avoid_crossing_perimeters`/`wipe` ohne Anlass; Passungs-, Brim- und Verbinder-Vorschläge bleiben.
10. **Druckerdaten korrigieren (B6, B7):** MINI mit IS-Tempo und Bowden-Rückzug 2,5 mm; MK4S-HF-Düse als Variante (24 mm³/s); Prusa-Tempi aus PrusaSlicers Bündel statt aus Orca; `binary_gcode = 0` nur im Rücklese-Lauf.


