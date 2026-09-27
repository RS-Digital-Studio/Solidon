# Slicer-Durchsicht Orca-Familie — Solidons Übergabe gegen die Herstellerprofile

Stand: 27.09.2026. Nur gelesen, nichts im Repository geändert.
Geprüft: ElegooSlicer, OrcaSlicer, Bambu Studio, Creality Print (Versionen in
Abschnitt 5). Maßstab nach Roberts Vorgabe: **das Herstellerprofil**; jede
Abweichung Solidons braucht einen Grund, der am Modell oder am Material hängt.

## 0. Anlass und Kurzbefund des Minigolf-Drucks

Nachgemessen an den drei Schnitten unter
`output/review/minigolf-2026-09-27/druckauftrag/` (ElegooSlicer 1.5.3.4,
Bahnlängen aus dem G-Code, eigenes Auswerteskript, nur `G1` mit positiver
Förderung; „Ansätze“ = Beginn einer Förderstrecke nach einer Leerfahrt):

| Lauf | Stütze + Schnittstelle gesamt | Schicht 1: Stütze / Schnittstelle | Schicht 1: Brim | Brim-Ansätze in Schicht 1 |
|---|---|---|---|---|
| `slice-0936` (Solidons Übergabe: Gitter, nur vom Bett, `support_threshold_angle = 45`) | 34,1 + 12,3 = **46,4 m** | 11,06 m / 2,14 m (je 52 Ansätze) | 5,80 m | **298** |
| `var-stuetzwinkel-30` (nur der Winkel auf 30) | 1,4 + 1,5 = 2,9 m | 1,35 m / 0,27 m | 7,71 m | 104 |
| `var-ohne-stuetzen` | 0 | — | 9,26 m | 56 |

Was daraus folgt, und zwar belegt an diesen Zahlen:

1. **Die Stütze trug schon in Schicht 1 Schnittstelle.** Stützen unter
   höher liegenden Überhängen stehen zwar auch in Schicht 1, tragen dort aber
   keine Deckschnittstelle; 52 Stützinseln mit je eigener Schnittstelle in
   Schicht 1 heißen, dass der gestützte Überhang ein bis zwei Schichten über
   dem Bett beginnt — an der Fase der Bodenplatte. Eine 45°-Fase liegt bei Orcas Schwelle 45 genau auf der Kante
   (Orca stützt, „whose slope angle is below the threshold“, Abschnitt 4),
   also fallen Teile davon unter die Schwelle: schmale Stützstreifen rund um
   die Fase, die Orca wegen `support_object_xy_distance` und der
   Schichtstufung treppenförmig vom Körper absetzt.
2. **Der Brim aus „tausenden Stückchen“ ist ein Brim, den die Stützstreifen
   zerschnitten haben.** Ohne Stützen legt ElegooSlicer 56 Brim-Ansätze
   (Körperumrisse) mit 9,26 m, mit Solidons Stützen 298 Ansätze mit nur noch
   5,80 m — bei gleichen Körpern. Der Quelltext sagt, warum: Bei
   Normalstützen trägt Orca die Füllflächen der ersten Stützschicht in die
   Sperrfläche des Brims ein (`Brim.cpp`, `outer_inner_brim_area`:
   `no_brim_area_support.emplace_back(support_contour)` für
   `stInnerNormal`, danach `areas = diff_ex(areas, extruder_no_brim_area)`).
   Liegt die Stütze als Streifen rund um die Fase, wird der Brimring an jedem
   Streifen unterbrochen. Die Ursache ist also nicht die Brim-Einstellung,
   sondern die Stütze an der Fase.
3. **Mit dem Herstellerwinkel 30 bleibt ein Sechzehntel der Stütze übrig**
   (2,9 m statt 46,4 m) — solange „Gitter“ bleibt. **Mit Elegoos vollständigem
   Stützsatz fällt sie ganz weg.** Eigene Messung (27.09.2026, ElegooSlicer
   1.5.3.4, Konsole, `--arrange 0 --slice 0`), in der Übergabe-3MF nur
   `project_settings.config` geändert:

   | Lauf | geändert | Stütze | Schicht 1 Brim | Zeit | Filament |
   |---|---|---|---|---|---|
   | `slice-0936` (Solidon) | — | 46,4 m | 5,80 m, 298 Ansätze | 10 h 53 min | 333,0 g |
   | Elegoo-Stützsatz | `support_type tree(auto)`, `support_threshold_angle 30`, `support_object_xy_distance 0.35`, `support_base_pattern rectilinear`/`1`, `support_on_build_plate_only 0`, `brim_type auto_brim`, `curr_bed_type Textured PEI Plate` | **0 m** | 11,64 m, 63 Ansätze | 10 h 34 min | 329,2 g |
   | dasselbe, nur vom Bett | zusätzlich `support_on_build_plate_only 1` | **0 m** | 11,64 m, 63 Ansätze | 10 h 34 min | 329,2 g |

   `enable_support` blieb dabei eingeschaltet. Elegoos Baumstütze mit 30°
   findet an diesem Satz nichts zu stützen; Solidons Vorschlag „Stützen“ war
   für den Slicer des Herstellers gegenstandslos. Nebenbei belegt der Lauf,
   dass die Konsole `curr_bed_type` aus `project_settings.config` übernimmt
   (G-Code-Kopf: `; curr_bed_type = Textured PEI Plate`, bei `slice-0936`
   dagegen `Cool Plate`).

Damit ist die Kette des Fehlers: Solidons Analysegrenze (45° gegen die
Senkrechte) **wird zugleich als Slicer-Schwelle übergeben** und ersetzt
Elegoos 30 (= 60° gegen die Senkrechte); dazu kommen „Gitter“ statt Elegoos
Baum und ein plattenweites `enable_support` für alle fünf Objekte, obwohl die
Frage je Objekt zu beantworten war.

## 1. Was Solidon an die Orca-Familie schreibt (Codebefund)

Grundlage: `app/core/export/slicer_keys.py` (`ORCA`, Zeilen 337–436),
`app/core/export/handover.py` (`as_mapping` 473, `by_section` 536,
`_only_chosen_adhesion` 613, `_support_spacing` 638, `_machine_keys` 901,
`settings_for_slot` 1013, `write_config` 1382, `project_settings` 1582,
`_orca_machine` 1758, `_orca_process` 1806, `_orca_filament` 1890,
`_with_every_plate` 2038), `app/core/knowledge/print_settings.py`
(`resolve` 194, `_within_flow` 307, `_paced` 328),
`app/core/knowledge/data/print_settings.toml`,
`app/core/knowledge/data/printers.toml`, `app/core/types.py`
(`SupportSettings` 1166, `AdhesionSettings` 1196), `app/core/slice/advise.py`.

### 1.1 Aufbau der Übergabe

- **Prozess:** Das benannte Herstellerprofil wird samt Erbkette aufgelöst,
  danach legt `_orca_process` (handover.py:1847–1848) **jeden** Wert aus
  `TABLES["orca"]` darüber — 45 Prozessschlüssel (dazu 21 Filamentschlüssel), gleich ob der Wert vom
  Nutzer, von einem Vorschlag oder bloß aus Solidons Qualitätstabelle kommt.
  Die Moduldoku sagt „Solidon überschreibt, was es versteht, und lässt den
  Rest in Ruhe“ (slicer_keys.py:19–21). In der Praxis „versteht“ Solidon
  genau die Werte, die ein Herstellerprofil abstimmt: Schichthöhen, alle
  Bahnbreiten, Wände, Füllung, sämtliche Tempi, Beschleunigungen, Stützen,
  Haftung.
- **Filament:** `_orca_filament` legt das Herstellerfilament als Unterlage und
  Solidons Werte darüber (handover.py:1981). Nur wenn der Slot ein **eigenes**
  Herstellerprofil trägt (`slot.material`), gewinnt der Hersteller für die
  Schlüssel aus `FILAMENT_READBACK` (handover.py:1970–1980). Eine lokale Spule
  gleichen Typs — Roberts „PLA Lavendal“ — bekommt **Solidons Tabellenwerte
  über Elegoos Profil**: Die Minigolf-3MF trägt
  `nozzle_temperature_initial_layer = 215` (Elegoo: 210),
  `slow_down_layer_time = 8` (Elegoo: 4), `filament_z_hop = 0.2`
  (Elegoo-Maschine: 0,4), `filament_retraction_speed = 35` (Maschine: 30).
- **Maschine:** aus dem Herstellerbestand übernommen (`_orca_machine`), gut so.
  **`curr_bed_type` schreibt Solidon nirgends** — weder in die Projektdatei
  noch in die Konsolenprofile. Die Konsole des ElegooSlicers nimmt dann
  „Cool Plate“: Im Elegoo-Vergleichslauf (`work-mast/elegoo/config.json`)
  stehen `curr_bed_type = Cool Plate` und `first_layer_bed_temperature = 35`,
  obwohl das CC2-Profil `default_bed_type = 4` (Textured PEI) führt.
  Solidon verdeckt das, indem `_with_every_plate` (handover.py:2038) die
  eigene Betttemperatur auf **alle** Plattentypen schreibt (Abschnitt 6, B-05).
- **Je Objekt** (`model_settings.config`): nur Name, Extruder, Stützsperre und
  die Haftung aus `advise.for_part` (writer.py:1013–1046,
  threemf.py:456). Stützen, Wände, Winkel bleiben plattenweit — so steht es
  auch im Docstring von `advise.for_part` (advise.py:1175–1177).

### 1.2 Die Werte, die dabei entstehen

Solidons Stufe „Standard“ ist **eine** Tabelle für alle Drucker
(`print_settings.toml` 49–66), darüber Material (120–158) und Drucker
(`printers.toml`). Was davon unabhängig vom Modell bei jedem Druck hinausgeht:

| Solidon-Feld | Wert | Herkunft im Code | Grund am Modell/Material? |
|---|---|---|---|
| `support.threshold_angle` | 45 → Orca `45` | `types.py:1171` = `rules.OVERHANG_LIMIT_DEGREES` (rules.py:41), Umrechnung `slicer_keys._angle_from_horizontal` (189–211) | Nein. Die Konstante ist Solidons **Analysegrenze**, nicht die Slicer-Schwelle des Herstellers |
| `support.style` | `none` → `enable_support 0`, aber `support_type normal(auto)` | `_ORCA_SUPPORT_TYPE` (slicer_keys.py:324–328) | Nein. Wer im Slicer Stützen einschaltet, bekommt Gitter statt Elegoos/Bambus Baum |
| `support.xy_gap` | 0,5 | `types.py:1182` | Nein (Hersteller 0,35 bzw. 60 %) |
| `support.density` | 0,15 → `support_base_pattern_spacing 2.8` | `_support_spacing` (handover.py:638–660) | Nein; wird auch bei Baumstützen geschrieben |
| `adhesion.kind` | PLA/PETG `skirt` → `brim_type no_brim`, `skirt_loops 2` | `print_settings.toml:138,158`, `_mapped({"brim": "outer_only"}, "no_brim")` (slicer_keys.py:413) | Nein. Schaltet Orcas `auto_brim` ab, das alle Hersteller stehen lassen |
| `layers.first_layer_height` | 0,25 | `print_settings.toml:52` | Nein (Hersteller fast überall 0,2) |
| `layers.first_layer_line_width` | Bahnbreite × 1,07 = 0,449 | `print_settings.py:216` | Nein (Hersteller 0,5; Creality 0,55) |
| alle Bahnbreiten | 0,42 für jede Rolle | slicer_keys.py:341–350 (RM-191) | Nein (Hersteller innen/Füllung 0,45) |
| `shell.wall_count` / `bottom_layers` | 3 / 4 | `print_settings.toml:53,55` | Nein (Hersteller 2 / 3) |
| `shell.wall_generator` | `arachne` | `types.py:1079` | Allgemein begründet („schmale Stege“), nicht am Modell; Elegoo, Bambu, Creality fahren `classic` |
| `infill.pattern` | `grid` | `print_settings.toml:57` | Nein (Elegoo `rectilinear`, Orca-BBL `crosshatch`, Neptune 4 `cubic`) |
| `temperature.nozzle_first_layer` | Düse + 5 | `print_settings.toml:122,142` | Nein (kein Hersteller hebt die erste Schicht an) |
| `temperature.bed` | auf **alle** Platten | `_with_every_plate`, `PLATE_KINDS` (handover.py:2035) | Nein; überschreibt die Nullen, mit denen Hersteller eine Platte für ein Material sperren |
| `retraction.*` | PLA 0,8 mm/35 mm/s, Z-Hop 0,2; PETG 1,2/30/0,3 | `print_settings.toml:131–133,151–153`, geschrieben als `filament_retraction_*` (slicer_keys.py:426–429) | Material ja, Maschine nein: überschreibt den Rückzug, den die Hersteller an der Maschine abstimmen |
| `cooling.minimum_layer_time` | 8 s (Standard) | `print_settings.toml:63` | Nein; bei Orca ein Filamentwert (Elegoo PLA 4, Bambu PLA 4–6, PETG 12) |
| `retraction.avoid_crossing_walls` | an → `reduce_crossing_wall 1` | `types.py:1214` | Allgemein begründet, alle Hersteller aus |
| Tempi | Herstellertempo, dann auf `max_flow` gedeckelt | `print_settings._within_flow` (307–325) | Gedeckelt mit Solidons PLA 12 mm³/s × `flow_factor`; bei Bambu fehlt der Faktor → 142 mm/s für **alle** Rollen |

Auffällig ist, was gar nicht übergeben wird: `curr_bed_type`,
`support_interface_bottom_layers`, `support_bottom_z_distance`,
`support_style`, `brim_object_gap`, `brim_ears_*`, `tree_support_*`,
`support_critical_regions_only`, `support_remove_small_overhang`,
`make_overhang_printable`, `enable_overhang_speed`/`overhang_*_speed`,
`slow_down_for_layer_cooling`, `dont_slow_down_outer_wall`,
`elefant_foot_compensation`, `pressure_advance`, `seam_slope_*`,
`top_surface_pattern`, `only_one_wall_top`, `ensure_vertical_shell_thickness`,
`bridge_flow`/`thick_bridges`. Diese bleiben beim Hersteller — das ist
richtig; einige davon brauchte Solidon aber, um seine Vorschläge wirksam zu
machen (Abschnitt 3).

## 2. Abgleich je Drucker (Stufe „Standard“, PLA/PETG)

**Wie gemessen.** Solidons Seite ist die Ausgabe des Repository-Codes selbst:
`print_settings.resolve(profiles.make_profile(<drucker>, <material>),
"standard")` und `handover.by_section(..., "orca")` — also genau das, was
`_orca_process`/`_orca_filament` über das Herstellerprofil legen, wenn der
Slot kein eigenes Herstellerfilament trägt (Roberts Fall). Die
Herstellerseite ist der Standardprozess (`default_print_profile` der
Maschine) und das Standard-PLA/-PETG, jeweils mit **aufgelöster Erbkette**
(`inherits` und `include`), eigenes Auflöseskript. Fehlt ein Schlüssel in der
ganzen Kette, gilt die Programmvorgabe aus `PrintConfig.cpp` (markiert ᵛ).
Rückzug und Z-Hop, die das Filament mit `nil` offen lässt, kommen von der
Maschine (markiert ᴹ).

Quellen der Spalten:

| | Drucker | Prozess | PLA | PETG | Bestand |
|---|---|---|---|---|---|
| ¹ | Centauri Carbon 2 | 0.20mm Standard @Elegoo CC2 0.4 nozzle | Elegoo PLA @ECC2 | Elegoo PETG @ECC2 | ElegooSlicer 1.5.3.4, `%APPDATA%\ElegooSlicer\system\Elegoo` (Profilstand 01.05.03.04; OrcaSlicers Elegoo-Bestand 02.04.00.06 ist in allen hier verglichenen Schlüsseln wertgleich) |
| ² | Neptune 4 / 4 Plus, A1 mini, P1S, K1 Max, Kobra 2, SV06 | Standard @… des Herstellers | Standard-PLA des Herstellers (SV06: Generic PLA @System) | entsprechend | OrcaSlicer 2.4.2, `resources\profiles\<Hersteller>` |
| ³ | A1, X1 Carbon | 0.20mm Standard @BBL A1 / X1C | Bambu PLA Basic | Bambu PETG Basic | Bambu Studio 02.08.02.61, `resources\profiles\BBL` (Profilstand 02.08.00.05) |
| ⁴ | K1, Ender-3 V3 | 0.20mm Standard @Creality … 0.4 nozzle | CR-PLA | CR-PETG | Creality Print 7.2 (5483), `%APPDATA%\Creality\Creality Print\7.0\system\Creality` |

Zelle: `=` gleich; sonst **Hersteller → Solidon**. Zeilen ohne Abweichung
sind weggelassen (gleich überall u. a. `layer_height`, `top_shell_layers`
außer Kobra, `seam_position aligned`, `travel_speed`, `ironing_type`,
`support_top_z_distance` außer SV06, `filament_wipe`).

#### PLA

| Schlüssel | CC2¹ | N4² | N4+² | A1³ | A1m² | P1S² | X1C³ | K1⁴ | K1M² | E3V3⁴ | Kobra2² | SV06² |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `initial_layer_print_height` | 0.2→0.25 | 0.2→0.25 | 0.2→0.25 | 0.2→0.25 | 0.2→0.25 | 0.2→0.25 | 0.2→0.25 | 0.2→0.25 | 0.2→0.25 | 0.2→0.25 | 0.28→0.25 | 0.24→0.25 |
| `line_width` | = | = | = | = | = | = | = | = | = | = | = | 0.44→0.42 |
| `initial_layer_line_width` | 0.5→0.449 | 0.5→0.449 | 0.5→0.449 | 0.5→0.449 | 0.5→0.449 | 0.5→0.449 | 0.5→0.449 | 0.5→0.449 | 0.5→0.449 | 0.55→0.449 | 0.8→0.449 | 0.42→0.449 |
| `outer_wall_line_width` | = | = | = | = | = | = | = | = | = | = | 0.4→0.42 | = |
| `inner_wall_line_width` | 0.45→0.42 | 0.45→0.42 | 0.45→0.42 | 0.45→0.42 | 0.45→0.42 | 0.45→0.42 | 0.45→0.42 | 0.45→0.42 | 0.45→0.42 | 0.45→0.42 | 0.5→0.42 | 0.45→0.42 |
| `sparse_infill_line_width` | 0.45→0.42 | 0.45→0.42 | 0.45→0.42 | 0.45→0.42 | 0.45→0.42 | 0.45→0.42 | 0.45→0.42 | 0.45→0.42 | 0.45→0.42 | 0.45→0.42 | 0.45→0.42 | 0.44→0.42 |
| `internal_solid_infill_line_width` | = | = | = | = | = | = | = | = | = | = | 0.5→0.42 | 0→0.42 |
| `top_surface_line_width` | = | = | = | = | = | = | = | = | = | = | 0.45→0.42 | 0.38→0.42 |
| `wall_loops` | 2→3 | 2→3 | 2→3 | 2→3 | 2→3 | 2→3 | 2→3 | 2→3 | 2→3 | 2→3 | = | = |
| `top_shell_layers` | = | = | = | = | = | = | = | = | = | = | 3→5 | = |
| `bottom_shell_layers` | 3→4 | = | = | 3→4 | 3→4 | 3→4 | 3→4 | 3→4 | 3→4 | 3→4 | 3→4 | 5→4 |
| `wall_generator` | classic→arachne | classic→arachne | classic→arachne | classic→arachne | classic→arachne | classic→arachne | classic→arachne | classic→arachne | classic→arachne | = | = | = |
| `precise_outer_wall` | = | = | = | = | 1ᵛ→0 | 1ᵛ→0 | = | = | = | 1→0 | 1ᵛ→0 | 1ᵛ→0 |
| `sparse_infill_density` | = | = | = | = | = | = | = | = | = | 10%→15% | 10%→15% | = |
| `sparse_infill_pattern` | rectilinear→grid | cubic→grid | cubic→grid | = | crosshatch→grid | crosshatch→grid | = | = | = | zig-zag→grid | crosshatch→grid | crosshatch→grid |
| `outer_wall_speed` | = | = | = | 200→142 | 200→142 | 200→142 | 200→142 | 200→167 | 200→167 | = | 150→142 | = |
| `inner_wall_speed` | = | 200→178 | 200→178 | 300→142 | 300→142 | 300→142 | 300→142 | 300→167 | 300→167 | 300→214 | 150→142 | = |
| `sparse_infill_speed` | = | 200→178 | 200→178 | 270→142 | 270→142 | 270→142 | 270→142 | 270→167 | 270→167 | 200→214 | = | = |
| `internal_solid_infill_speed` | 250→200 | 250→178 | 250→178 | 250→142 | 250→142 | 250→142 | 250→142 | 250→167 | 250→167 | 200→214 | 150→70 | 40→60 |
| `gap_infill_speed` | 250→200 | 250→178 | 250→178 | 250→142 | 250→142 | 250→142 | 250→142 | 250→167 | 250→167 | 200→214 | 100→142 | 30→40 |
| `top_surface_speed` | = | 200→178 | 200→178 | 200→142 | 200→142 | 200→142 | 200→142 | 200→167 | 200→167 | = | = | = |
| `initial_layer_speed` | = | = | = | = | = | = | = | = | = | = | 50%→20 | 35%→20 |
| `bridge_speed` | = | = | = | = | = | = | = | = | = | 25→50 | = | = |
| `default_acceleration` | = | = | = | = | = | = | = | = | = | = | = | 0→8000 |
| `outer_wall_acceleration` | = | = | = | = | = | = | = | = | = | = | = | 0→5000 |
| `support_type` | tree(auto)→normal(auto) | = | = | tree(auto)→normal(auto) | tree(auto)→normal(auto) | tree(auto)→normal(auto) | tree(auto)→normal(auto) | = | = | = | = | = |
| `support_threshold_angle` | 30→45 | 30→45 | 30→45 | 30→45 | 30→45 | 30→45 | 30→45 | 30→45 | 30→45 | 30→45 | 30→45 | 40→45 |
| `support_object_xy_distance` | 0.35→0.5 | 0.35→0.5 | 0.35→0.5 | 0.35→0.5 | 0.35→0.5 | 0.35→0.5 | 0.35→0.5 | 0.35→0.5 | 0.35→0.5 | 0.35→0.5 | 60%→0.5 | 60%→0.5 |
| `support_top_z_distance` | = | = | = | = | = | = | = | = | = | = | = | 0.18→0.2 |
| `support_interface_top_layers` | = | = | = | = | = | = | = | = | = | = | 3→2 | 3→2 |
| `support_base_pattern_spacing` | 1→2.8 | 2.5→2.8 | 2.5→2.8 | 2.5→2.8 | 2.5→2.8 | 2.5→2.8 | 2.5→2.8 | 2.5→2.8 | 2.5→2.8 | 2.5→2.8 | 0.2→2.8 | 0.2→2.8 |
| `brim_type` | auto_brimᵛ→no_brim | auto_brimᵛ→no_brim | auto_brimᵛ→no_brim | auto_brimᵛ→no_brim | auto_brimᵛ→no_brim | auto_brimᵛ→no_brim | auto_brimᵛ→no_brim | auto_brim→no_brim | auto_brim→no_brim | auto_brim→no_brim | auto_brimᵛ→no_brim | auto_brimᵛ→no_brim |
| `brim_width` | 5→0 | 5→0 | 5→0 | 5→0 | 5→0 | 5→0 | 5→0 | 5→0 | 5→0 | 5→0 | 3→0 | = |
| `skirt_loops` | 0→2 | 0→2 | 0→2 | 0→2 | 0→2 | 0→2 | 0→2 | 0→2 | 0→2 | 0→2 | 0→2 | = |
| `skirt_distance` | 2→3 | 2→3 | 2→3 | 2→3 | 2→3 | 2→3 | 2→3 | 2→3 | 2→3 | 2→3 | 2→3 | = |
| `reduce_crossing_wall` | 0→1 | 0→1 | 0→1 | 0→1 | 0→1 | 0→1 | 0→1 | 0→1 | 0→1 | 0→1 | 0→1 | 0→1 |
| `nozzle_temperature` | = | 220→210 | 220→210 | 220→210 | 220→210 | 220→210 | 220→210 | 220→210 | 220→210 | 230→210 | 220→210 | 220→210 |
| `nozzle_temperature_initial_layer` | 210→215 | 220→215 | 220→215 | 220→215 | 220→215 | 220→215 | 220→215 | 220→215 | 220→215 | 230→215 | 220→215 | 220→215 |
| `hot_plate_temp` | = | = | = | 65→60 | = | 55→60 | 55→60 | 50→60 | = | 65→60 | 45→60 | 55→60 |
| `textured_plate_temp` | = | = | = | 65→60 | 65→60 | 55→60 | 55→60 | 50→60 | = | 65→60 | –→60 | 55→60 |
| `cool_plate_temp` | 35→60 | 35→60 | 35→60 | 35→60 | 35→60 | 35→60 | 35→60 | 50→60 | = | 65→60 | 35→60 | 35→60 |
| `eng_plate_temp` | 0→60 | 0→60 | 0→60 | 0→60 | 0→60 | 0→60 | 0→60 | 50→60 | = | 65→60 | 0→60 | 0→60 |
| `fan_max_speed` | = | = | = | 80→100 | 80→100 | = | = | = | = | = | = | = |
| `fan_min_speed` | = | 100→50 | 100→50 | 60→50 | 60→50 | 100→50 | 100→50 | 100→50 | 100→50 | 100→50 | 100→50 | 100→50 |
| `fan_cooling_layer_time` | = | = | = | = | = | 100→80 | 100→80 | 100→80 | 100→80 | 100→80 | 100→80 | 100→80 |
| `slow_down_layer_time` | 4→8 | = | = | 6→8 | 6→8 | 4→8 | 4→8 | 12→8 | = | = | = | 4→8 |
| `filament_retraction_length` | = | = | = | = | = | = | = | = | = | = | 2 ᴹ→0.8 | 0.5 ᴹ→0.8 |
| `filament_retraction_speed` | 30 ᴹ→35 | 60 ᴹ→35 | 60 ᴹ→35 | 30 ᴹ→35 | 30 ᴹ→35 | 30 ᴹ→35 | 30 ᴹ→35 | 40 ᴹ→35 | 40 ᴹ→35 | 40 ᴹ→35 | 80 ᴹ→35 | 30 ᴹ→35 |
| `filament_z_hop` | 0.4 ᴹ→0.2 | 0.4 ᴹ→0.2 | 0.4 ᴹ→0.2 | 0.4 ᴹ→0.2 | 0.4 ᴹ→0.2 | 0.4 ᴹ→0.2 | 0.4 ᴹ→0.2 | 0.4 ᴹ→0.2 | 0.4 ᴹ→0.2 | = | 0.4 ᴹ→0.2 | 0 ᴹ→0.2 |
| `filament_flow_ratio` | = | = | = | = | = | = | = | 0.95→0.98 | = | 0.95→0.98 | = | = |
| `filament_density` | 1.25→1.24 | 1.25→1.24 | 1.25→1.24 | 1.26→1.24 | 1.26→1.24 | 1.26→1.24 | 1.26→1.24 | = | = | = | = | = |
| `filament_max_volumetric_speed` | = | 16→15 | 16→15 | 21→12 | 21→12 | 21→12 | 21→12 | 18→14.04 | 12→14.04 | = | = | = |

#### PETG (nur Filamentseite; der Prozess ist derselbe wie bei PLA)

| Schlüssel | CC2¹ | N4² | N4+² | A1³ | A1m² | P1S² | X1C³ | K1⁴ | K1M² | E3V3⁴ | Kobra2² | SV06² |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `nozzle_temperature` | 250→240 | 250→240 | 250→240 | 245→240 | 245→240 | 255→240 | 255→240 | 250→240 | 255→240 | 235→240 | 255→240 | 255→240 |
| `nozzle_temperature_initial_layer` | 250→245 | 250→245 | 250→245 | = | = | = | = | 250→245 | 255→245 | 235→245 | 255→245 | 255→245 |
| `hot_plate_temp` | 70→80 | 70→80 | 70→80 | 70→80 | 70→80 | 70→80 | 70→80 | 70→80 | = | 70→80 | = | = |
| `textured_plate_temp` | 70→80 | 70→80 | 70→80 | 70→80 | 70→80 | 70→80 | 70→80 | 70→80 | = | 70→80 | –→80 | = |
| `cool_plate_temp` | 0→80 | 0→80 | 0→80 | 0→80 | 0→80 | 0→80 | 0→80 | 70→80 | 60→80 | 70→80 | 60→80 | 60→80 |
| `eng_plate_temp` | 70→80 | 70→80 | 70→80 | 70→80 | 70→80 | 70→80 | 70→80 | 0→80 | 0→80 | 0→80 | 0→80 | 0→80 |
| `fan_max_speed` | 40→50 | 40→50 | 40→50 | = | = | 40→50 | 40→50 | 80→50 | 90→50 | 90→50 | 90→50 | 100→50 |
| `fan_min_speed` | 10→20 | 10→20 | 10→20 | 30→20 | 30→20 | = | = | 40→20 | 40→20 | 80→20 | 40→20 | = |
| `fan_cooling_layer_time` | = | = | = | = | = | = | = | = | = | = | = | 20→30 |
| `overhang_fan_speed` | 90→100 | 90→100 | 90→100 | 50→100 | 90→100 | 90→100 | 50→100 | = | 90→100 | 90→100 | 90→100 | = |
| `close_fan_the_first_x_layers` | 3→2 | 3→2 | 3→2 | 3→2 | 3→2 | 3→2 | 3→2 | 3→2 | 3→2 | 3→2 | 3→2 | 3→2 |
| `slow_down_layer_time` | 12→8 | 12→8 | 12→8 | 12→8 | 12→8 | 12→8 | 12→8 | 12→8 | = | = | = | = |
| `filament_retraction_length` | 0.8 ᴹ→1.2 | 0.8 ᴹ→1.2 | 0.8 ᴹ→1.2 | 0.4→1.2 | 0.4→1.2 | 0.4→1.2 | 0.4→1.2 | 0.6→1.2 | 0.8 ᴹ→1.2 | = | 2 ᴹ→1.2 | 0.5 ᴹ→1.2 |
| `filament_retraction_speed` | = | 60 ᴹ→30 | 60 ᴹ→30 | = | = | = | = | = | 40 ᴹ→30 | = | 80 ᴹ→30 | = |
| `filament_z_hop` | 0.4 ᴹ→0.3 | 0.4 ᴹ→0.3 | 0.4 ᴹ→0.3 | 0.4 ᴹ→0.3 | 0.4 ᴹ→0.3 | 0.4 ᴹ→0.3 | 0.4 ᴹ→0.3 | 0.4 ᴹ→0.3 | 0.4 ᴹ→0.3 | 0.2 ᴹ→0.3 | 0.4 ᴹ→0.3 | 0 ᴹ→0.3 |
| `filament_flow_ratio` | 0.98→0.95 | 0.98→0.95 | 0.98→0.95 | 0.94→0.95 | 0.94→0.95 | = | = | = | = | = | = | 1→0.95 |
| `filament_density` | 1.25→1.27 | 1.25→1.27 | 1.25→1.27 | 1.25→1.27 | 1.25→1.27 | 1.25→1.27 | 1.25→1.27 | 1.23→1.27 | = | 1.23→1.27 | = | = |
| `filament_max_volumetric_speed` | 11→10 | 11→10 | 11→10 | 13→10 | 13→10 | 15→10 | 15→10 | 18→10 | = | 8→10 | = | = |

### 2.1 Bewertung je Schlüsselgruppe

„Grund am Code“ heißt: Im Code oder in den Daten steht ein Grund, der am
**Modell oder Material** hängt und die Abweichung von **diesem** Hersteller
trägt. Eine allgemeine Druckerfahrung („belastbare Ausgangspunkte“,
`print_settings.toml:25`) zählt nach Roberts Maßstab nicht.

| Gruppe | Muster | Grund am Code? | Empfehlung |
|---|---|---|---|
| Stützwinkel | überall 45 statt 30 (SV06 40) | **Nein.** `SupportSettings.threshold_angle = OVERHANG_LIMIT_DEGREES` (types.py:1171) ist Solidons Analysegrenze; der Docstring (1174–1180) begründet nur, warum Analyse und Übergabe dieselbe Zahl tragen sollen | Herstellerwert nicht überschreiben (Abschnitt 6, B-01) |
| Stützart | CC2 und alle Bambu: Baum → Gitter | **Nein.** `_ORCA_SUPPORT_TYPE` bildet `none` und `grid` auf `normal(auto)` ab | Art des Herstellers stehen lassen; „Gitter“ nur auf ausdrückliche Wahl (B-02) |
| Stützabstände | XY 0,35 → 0,5; Grundmuster-Abstand 2,5 (Elegoo 1) → 2,8 | **Nein.** Vorgaben der Dataclass (types.py:1182–1183) | Nicht schreiben, solange der Nutzer sie nicht setzt (B-06) |
| Haftung | `auto_brim` → `no_brim` + 2 Skirt-Runden | **Nein.** Materialtabelle `adhesion = "skirt"` für PLA und PETG | `auto_brim` stehen lassen, nur Solidons begründeten Brim je Objekt schreiben (B-03) |
| Erste Schicht | Höhe 0,2 → 0,25, Breite 0,5 → 0,449, Düse +5 °C | **Nein.** Stufe (print_settings.toml:52), Faktor 1,07 (print_settings.py:216), Materialtabelle | Herstellerwerte übernehmen (B-04) |
| Bahnbreiten | innen/Füllung 0,45 → 0,42 | Grund ist RM-191 („jede Rolle bekommt Solidons Wert“), kein Modellgrund | Nur schreiben, wenn der Nutzer oder ein Vorschlag die Breite ändert (B-08) |
| Wände/Boden | 2 → 3 Wände, 3 → 4 Bodenschichten | **Nein** (Stufe) | Herstellerwert; Solidons Wandvorschlag (`_from_connectors`) bleibt als Vorschlag (B-08) |
| Wandgenerator | classic → arachne bei Elegoo, Bambu, Creality K1 | Allgemein (types.py:1080 „schmale Stege“); der modellbezogene Grund existiert als Vorschlag (advise.py:856–869) | Herstellerwert; Arachne nur über den vorhandenen Vorschlag (B-08) |
| Genaue Außenwand | Orca-Vorgabe 1 bzw. Creality 1 → 0 | **Nein** | Nicht schreiben, außer der Passungsvorschlag setzt sie (B-10) |
| Füllmuster | → `grid` (Elegoo `rectilinear`, Orca-BBL `crosshatch`, N4 `cubic`, Creality E3V3 `zig-zag`) | **Nein** (Stufe) | Herstellermuster; `grid` nur bei Nutzerwahl (B-08) |
| Tempi | Bambu alle Rollen 142 mm/s, K1 167, N4 178; Kobra-Vollfüllung 70 | Gedeckelt über Solidons PLA-Volumenstrom 12 mm³/s × `flow_factor`, der bei Bambu fehlt (printers.toml:109–192). Kein Modellgrund | Tempi nicht schreiben; der Slicer deckelt selbst über `filament_max_volumetric_speed` (B-07) |
| Beschleunigung | SV06 0 (Maschinengrenze 500–1250) → 8000/5000 | **Nein** (Stufe; printers.toml hat für den SV06 keine Werte) | Nicht schreiben, wo `printers.toml` keinen Herstellerwert hat (B-07) |
| Temperaturen PLA | 220 → 210 bei allen außer CC2; erste Schicht +5 | Materialtabelle, allgemein. Die 220 der Hersteller gehören zu 18–21 mm³/s Volumenstrom | Herstellerfilament übernehmen (B-09) |
| Temperaturen PETG | 245–255 → 240; Bett 70 → 80 | Materialtabelle, allgemein | Herstellerfilament übernehmen (B-09) |
| Betttemperatur je Platte | alle Platten = Solidons Bettwert, auch wo der Hersteller 0 (= nicht zulässig) oder 35 °C (Cool Plate) setzt | **Nein.** `_with_every_plate` begründet sich mit dem fehlenden `curr_bed_type`, nicht mit dem Material | `curr_bed_type` setzen, Plattenwerte des Herstellers stehen lassen (B-05) |
| Kühlung | PLA-Kurve 50–100 % über 80 s (Elegoo) für alle; Mindestschichtzeit 8 s statt 4–12 | Kurve: am CC2 gemessen, für die übrigen Drucker nicht; Mindestschichtzeit aus der Stufe | Herstellerfilament übernehmen; Solidons 15 s nur als Vorschlag bei dünnen Schichten (bereits advise.py:944) (B-09) |
| Rückzug | Z-Hop 0,4 → 0,2 (PLA) / 0,3 (PETG); Länge PETG 1,2 statt 0,4–0,8; Kobra 2 mm/80 mm/s → 0,8/35; SV06 Z-Hop 0 → 0,2 | Material ja (toml:159–160 „PETG zieht Fäden“), Maschine nein — die Hersteller stimmen den Rückzug am Extruder ab | `filament_retraction_*` nicht schreiben (B-11) |
| Wände nicht kreuzen | 0 → 1 | Allgemein belegt (Orca-Wiki empfiehlt es für fadenziehende Materialien, Abschnitt 4) | Vertretbar; eher je Material (PETG/TPU) als pauschal (B-14) |
| Objektmarken | `gcode_label_objects` 0 → 1 | Begründet (Einzelteil abbrechen, handover.py:1849–1854) | Behalten; zusätzlich `exclude_object` für Klipper-Drucker prüfen (B-15) |

## 3. Was Solidon nicht beachtet

### 3.1 Die Orca-Familie kann je Objekt — Solidon schreibt je Platte

In OrcaSlicer gehören die Stütz-, Brim-, Wand- und Füllwerte zu
`PrintObjectConfig` bzw. `PrintRegionConfig` und lassen sich je Objekt in
`Metadata/model_settings.config` setzen (`<object><metadata key=… value=…/>`).
Nachgelesen in `src/libslic3r/PrintConfig.hpp` (OrcaSlicer, Zweig `main`):

| Ebene | Schlüssel (Auswahl) |
|---|---|
| **Objekt** (`PrintObjectConfig`) | `enable_support`, `support_type`, `support_style`, `support_threshold_angle`, `support_on_build_plate_only`, `support_critical_regions_only`, `support_remove_small_overhang`, `support_top_z_distance`, `support_object_xy_distance`, `support_interface_top_layers`, `support_base_pattern_spacing`, `tree_support_wall_count`, `brim_type`, `brim_width`, `brim_object_gap`, `raft_layers`, `wall_generator`, `elefant_foot_compensation`, `seam_position`, `default_acceleration`, `outer_wall_acceleration`, `layer_height` |
| **Bereich** (`PrintRegionConfig`, ebenfalls je Objekt) | `wall_loops`, `wall_sequence`, `precise_outer_wall`, `sparse_infill_density`, `sparse_infill_pattern`, `outer_wall_speed`, `bridge_speed`, `ironing_type`, `top_shell_layers`, `bottom_shell_layers`, `make_overhang_printable` |
| **nur Platte** (`PrintConfig`) | `skirt_loops`, `initial_layer_print_height`, `initial_layer_line_width`, `initial_layer_speed`, `reduce_crossing_wall`, `curr_bed_type`; Temperaturen, Kühlung und `slow_down_layer_time` hängen am Filament |

Solidon nutzt die Objektebene nur für die Haftung aus `advise.for_part`
(writer.py:1013–1046). Alles andere, was `advise` am **Körper** herleitet,
geht plattenweit hinaus:

- **Stützen** (`support.style`, `support.placement`,
  `support.block_channels`): Braucht ein Körper Stütze, bekommen alle Körper
  der Platte `enable_support = 1`. Am Minigolf-Satz standen vier gleiche
  Bahnen und ein Rumpf auf der Platte; die Stütze lief für alle fünf.
- **Passungen** (`_from_fits`, advise.py:960–1030): genaue Außenwand,
  Außenwand zuerst, Außenwandtempo 30 mm/s, Außenwandbeschleunigung
  2000 mm/s², Bügeln — für die ganze Platte, auch für Teile ohne Passung.
- **Verbinder** (`_from_connectors`): Wandzahl bzw. Fülldichte „gelten für das
  ganze Teil“ (Vorschlagstext), in der Übergabe sogar für die ganze Platte.
- **Dünne Stellen** (`wall_generator arachne`, Bahnbreite): ebenso.

Der Docstring von `advise.for_part` (advise.py:1175–1177) hält Stützen
ausdrücklich plattenweit, „je Teil verstellt wären sie ein Widerspruch, den
der Slicer auflösen müsste“. Für die Orca-Familie stimmt das nicht: Der
Slicer löst nichts auf, er rechnet jedes Objekt mit seinen eigenen Werten.
Für Temperatur und Kühlung stimmt es weiterhin.

### 3.2 Schlüssel, die für die Druckqualität je Modell zählen und die Solidon nicht kennt

| Schlüssel | Was er tut (Quelle: Orca `PrintConfig.cpp`, Orca-Wiki) | Bezug zu Solidons Analyse | Vorschlag |
|---|---|---|---|
| `curr_bed_type` | Welche Druckplatte aufliegt; bestimmt, welche `*_plate_temp` gilt. Vorgabe `Cool Plate` (`set_default_value(... btPC)`) | Keiner — aber ohne ihn rechnet die Konsole mit „Cool Plate“ (gemessen, Abschnitt 1.1) | Immer schreiben: Standardplatte des Druckers (`default_bed_type` des Herstellerprofils; CC2 `4` = Textured PEI) oder die im Druckdialog gewählte |
| `support_critical_regions_only` | Nur Baumstütze: „Only create support for critical regions including sharp tail, cantilever, etc.“ | Genau Solidons Inselbefund (`island_layers`) ohne großflächigen Überhang | Bei Baumstütze und reinem Inselbedarf je Objekt setzen |
| `support_remove_small_overhang` | „Ignore small overhangs that possibly don't require support“, Vorgabe an | Solidons `OVERHANG_LAYER_MINIMUM` fragt dasselbe | Nicht anfassen (Hersteller lässt es an) |
| `support_object_first_layer_gap` | XY-Abstand Stütze–Objekt in der ersten Schicht, Vorgabe 0,2 | Stützen am Fuß des Körpers (Minigolf-Fase) | Nicht anfassen; der eigentliche Fehler war die Stütze selbst |
| `support_threshold_overlap` | Nur Orca/Elegoo: gilt, wenn der Winkel 0 ist | `_angle_from_horizontal` schreibt nie 0 — richtig so | Keiner |
| `make_overhang_printable` (+ `_angle`, `_hole_size`) | Formt Überhänge im Slicer so um, dass sie ohne Stütze druckbar werden (Orca, Elegoo, Creality; **nicht** Bambu Studio) | Alternative zu Stützen bei kleinen Überhängen und Löchern | Allenfalls als Vorschlag je Objekt mit Hinweis, dass der Slicer die Form ändert; nie still |
| `enable_overhang_speed`, `overhang_1_4…4_4_speed`, `slowdown_for_curled_perimeters` | Tempo an Überhängen nach Überdeckung. Bambu: „Overhang speeds are generally set between 10–60 mm/s“ | Der Bereich zwischen Herstellerwinkel und 45° wird **so** gedruckt, nicht mit Stütze | Herstellerwerte stehen lassen (Solidon schreibt sie nicht — gut). Für Robert wichtig: das ist der Grund, warum 30° reicht |
| `overhang_fan_threshold`, `overhang_fan_speed` | Kühlung an Überhängen | Solidon schreibt `overhang_fan_speed` aus `bridge_fan_speed` (1,0) | Herstellerwert behalten (PETG: Elegoo 90, Bambu 50) |
| `wall_sequence = inner-outer-inner wall` | Orca-Wiki: „This option is recommended against the Outer/Inner option in most cases“, ab drei Wänden | Solidons `outer_wall_first` kennt nur Außen/Innen | „Außenwand zuerst“ bei ≥ 3 Wänden als `inner-outer-inner wall` schreiben (in allen vier Slicern vorhanden) |
| `precise_outer_wall` | „This option will be ignored for outer-inner or inner-outer-inner wall sequences“ (Orca `PrintConfig.cpp`; `PerimeterGenerator.cpp` prüft `wall_sequence == InnerOuter`) | `_from_fits` schlägt **beides** vor: genaue Außenwand **und** Außenwand zuerst — damit ist die genaue Außenwand wirkungslos | Für Passungen eines von beiden, nicht beides (B-10) |
| `brim_type = auto_brim` / `brim_ears` | Auto: „computes an optimal brim width by evaluating material properties, part geometry, printing speed, and thermal characteristics“ (Orca-Wiki). Mausohren an Ecken | Solidons `SMALL_FOOTPRINT`, `_slender`, `_on_small_feet` fragen dasselbe | `auto_brim` als Grundlage, Solidons Brim nur als Objektwert, wo die eigene Regel greift |
| `elefant_foot_compensation` | Zieht die unteren Schichten ein (Hersteller 0,075–0,15) | Passungen am Fuß; eine Fase an der Unterkante braucht dann keine Stütze | Herstellerwert behalten; bei Passungen am Boden erwähnen |
| `slow_down_for_layer_cooling`, `dont_slow_down_outer_wall` | Voraussetzung, dass `slow_down_layer_time` greift | Solidons Vorschlag „15 s Mindestschichtzeit“ (advise.py:944) wirkt nur mit dem Schalter | Beim Vorschlag den Schalter mitschreiben (in allen Herstellerprofilen an, deshalb heute unkritisch) |
| `pressure_advance`, `enable_pressure_advance` | Je Filament kalibriert (Orca-Wiki „Pressure Advance“) | — | Nicht anfassen; heute richtig, weil Solidon es nicht schreibt |
| `exclude_object` | Klipper: Objekte einzeln abbrechbar (Elegoo 0, Creality 1) | Solidon setzt nur `gcode_label_objects` | Für Klipper-Drucker prüfen, ob die Firmware es kann; nicht blind setzen |

### 3.3 Werte, die Solidon schreibt, obwohl es nichts über das Modell weiß

Das ist der Kern. `_orca_process` legt jeden Tabellenwert über das
Herstellerprofil, auch wenn er aus Solidons allgemeiner Stufe kommt. Nach
Roberts Maßstab gehört in die Übergabe **nur**:

1. was der Nutzer im Druckdialog ausdrücklich anders gesetzt hat,
2. was ein übernommener Vorschlag mit Grund am Modell oder Material setzt,
3. was Solidon wissen muss, damit das Herstellerprofil überhaupt greift
   (`curr_bed_type`, Filamentzuordnung je Slot, Stützsperre).

Alles Übrige — die Werte der Qualitätsstufe, der Materialtabelle und der
Dataclass-Vorgaben — ist heute eine zweite Meinung neben dem Hersteller und
müsste **aus dem Herstellerprofil gelesen** statt darüber geschrieben werden.
Die Leselogik gibt es schon: `slicer_profiles.filament_values` und
`FILAMENT_READBACK` lesen Herstellerfilamente in Solidons Felder zurück; für
den Prozess fehlt das Gegenstück (Abschnitt 6, B-12).

## 4. Recherche: belegte Werte und Herstellerbegründungen

Nur, was eine Quelle trägt. Quelltextzitate aus `github.com/SoftFever/OrcaSlicer`
(Zweig `main`, abgerufen 27.09.2026) und `github.com/bambulab/BambuStudio`
(Zweig `master`); die installierten Programme sind älter bzw. Abkömmlinge,
die Schlüssel und Vorgaben stimmen mit den Profilen und Binärdateien überein
(Abschnitt 5).

### 4.1 Stützwinkel

- **Bedeutung.** Orca: „Support will be generated for overhangs whose slope
  angle is below the threshold. … Note: If set to 0, normal supports use the
  Threshold overlap instead, while tree supports fall back to a default value
  of 30.“ Vorgabe `ConfigOptionInt(30)` (`src/libslic3r/PrintConfig.cpp`,
  `support_threshold_angle`). Bambu Studio: ebenfalls 30.
- **Warum 30.** Bambu-Wiki „Support“: „The default threshold angle is 30
  degrees. For most materials, this is a safe angle to print without
  support.“ (<https://wiki.bambulab.com/en/software/bambu-studio/support>)
- **Was zwischen 30° und 45° geschieht.** Bambu-Wiki „How to Print
  Overhangs“: Unter 45° zur Platte empfiehlt Bambu Stützen „to improve print
  quality“; darüber Temperatur senken, Überhangtempo („generally set between
  10–60 mm/s“) und Lüfter
  (<https://wiki.bambulab.com/en/filament-acc/filament/print-quality/overhang>).
  Der Bereich 30–45° ist also eine **Oberflächenfrage**, keine
  Druckbarkeitsfrage — und die Herstellerprofile beantworten sie mit
  `enable_overhang_speed`/`overhang_*_speed` und `overhang_fan_speed`, nicht
  mit Stütze. Wer dort Stütze will, entscheidet es für eine sichtbare Fläche
  eines bestimmten Objekts, nicht für die Platte.
- **Warum genau 45 die schlechteste Zahl ist.** 45° ist der häufigste
  Fasenwinkel in der Konstruktion. Eine Schwelle, die genau darauf liegt,
  kippt an der Rundung der Facetten: Ein Teil der Fase liegt knapp unter,
  ein Teil knapp über der Schwelle. Genau das zeigt der Minigolf-Lauf —
  52 Stützansätze und Schnittstelle schon in Schicht 1 (Abschnitt 0).
  Herstellerwerte liegen mit 30 (bzw. 40 beim SV06) sicher darunter.

### 4.2 Stützart

- Orca `support_style`: „For tree support, slim and organic style will merge
  branches more aggressively and save a lot of material (default organic)“;
  `default` heißt bei Baum „Organic“ (`PrintConfig.cpp`).
- Bambu-Wiki „Support“: Standardstil ist „Tree Hybrid“, wenn
  Stützmaterial oder adaptive Schichthöhe aktiv ist, sonst „Tree Organic“;
  Hybrid legt „below the big flat overhang regions“ Gitterstützen, sonst
  Baum.
- Elegoo (CC2) und Bambu (alle vier) setzen `tree(auto)` im Standardprozess;
  Neptune 4, Creality, Anycubic, Sovol `normal(auto)`. Gemessen am
  Minigolf-Satz: Elegoos Baum mit 30° legt **keine** Stütze, Solidons Gitter
  mit 45° 46,4 m (Abschnitt 0).

### 4.3 Brim und erste Schicht

- **Auto-Brim.** Orca-Wiki „Brim“: „The Auto brim feature computes an optimal
  brim width by evaluating material properties, part geometry, printing
  speed, and thermal characteristics.“
  (<https://github.com/OrcaSlicer/OrcaSlicer/wiki/others_settings_brim>).
  Vorgabe `btAutoBrim` in Orca und Bambu Studio. Kein Herstellerprofil
  schaltet es ab.
- **Brim neben Normalstütze.** `Brim.cpp` spart die Füllflächen der ersten
  Stützschicht aus dem Brim aus (`no_brim_area_support`, Abschnitt 0).
- **Erste Schicht.** Alle Hersteller mit automatischer Bettvermessung
  (Elegoo, Bambu, Creality) fahren 0,2 mm Höhe und 0,5 mm (125 %) Breite,
  Creality Ender-3 V3 0,55 mm. Ellis’ Print Tuning Guide empfiehlt „first
  layer line width to 120% or greater“ und eine Höhe von „0.25 or greater (in
  my opinion)“ — ausdrücklich als persönliche Vorliebe für große Drucker ohne
  gleichmäßige erste Schicht
  (<https://ellis3dp.com/Print-Tuning-Guide/articles/first_layer_squish.html>).
  Solidons 0,25 mm hat damit eine Quelle, Solidons 0,449 mm (107 %) keine:
  Beide Quellen verlangen mindestens 120 %.

### 4.4 Wände

- Orca-Wiki „Wall and surfaces“: Innen/Außen „for best overhangs“;
  Innen/Außen/Innen „for the best external surface finish and dimensional
  accuracy … recommended against the Outer/Inner option in most cases“,
  ab drei Wänden
  (<https://github.com/OrcaSlicer/OrcaSlicer/wiki/quality_settings_wall_and_surfaces>).
- Genaue Außenwand: „ignored for outer-inner or inner-outer-inner wall
  sequences“ (`PrintConfig.cpp`, `precise_outer_wall`); Orca-Vorgabe `true`,
  Bambu-Vorgabe `false`.
- Wandgenerator: Orca-Wiki „Classic … ideal for fast, predictable slicing“,
  „Arachne … better handling of thin features“
  (<https://github.com/OrcaSlicer/OrcaSlicer/wiki/quality_settings_wall_generator>).
  Elegoo, Bambu und Creality K1 stellen `classic` ein. Solidon hat den
  modellbezogenen Grund für Arachne bereits als Vorschlag (dünnste Stelle
  unter drei Bahnen, advise.py:854–869) — die pauschale Vorgabe braucht es
  daneben nicht.
- „Wände nicht kreuzen“: Orca-Wiki „can significantly reduce surface defects
  and stringing … especially with materials prone to stringing like PETG or
  TPU“; kostet Zeit. Solidons pauschales `1` ist damit belegt, aber am
  Material, nicht am Drucker.

### 4.5 Platten und Betttemperatur

- Eine Plattentemperatur **0** heißt in der Orca-Familie „diese Platte ist
  für das Filament nicht zulässig“: `Print.cpp` meldet dann „Plate %d: %s
  does not support filament %s“ (für Bambu-Drucker und bei
  `support_multi_bed_types`). Elegoo setzt 0 für PLA auf Engineering Plate
  und für PETG auf Cool Plate; Bambu ebenso für PETG auf Cool Plate.
- Bambu-Wiki „Introduction to Bambu Lab Build Plates“: Cool Plate SuperTack
  — PLA „at just 40 °C“, PETG „55–60 °C“
  (<https://wiki.bambulab.com/en/filament-acc/acc/plates>). Bambus Profile:
  PLA Cool Plate 35 °C, Textured PEI 55–65 °C, PETG 70 °C.
- `curr_bed_type`: Vorgabe `Cool Plate` in Orca und Bambu Studio
  (`PrintConfig.cpp`); die Oberfläche setzt beim Druckerwechsel die
  Standardplatte (`PresetBundle.cpp`: `get_default_bed_type`), die Konsole
  nicht. Gemessen: ohne Angabe `Cool Plate`, mit Angabe in
  `project_settings.config` übernommen (Abschnitt 0).

### 4.6 Volumenstrom, Druckvorschub, Kühlung

- Orca-Wiki „Max Volumetric Speed“: „varies depending on your material,
  machine, nozzle diameter, and even your extruder setup … calibrate it for
  your specific printer and each filament“
  (<https://github.com/OrcaSlicer/OrcaSlicer/wiki/volumetric_speed_calib>).
  Die Hersteller liefern ihn je Filament und Drucker (Bambu PLA Basic 21,
  Elegoo PLA @ECC2 21, CR-PLA @K1 18, Elegoo PETG @ECC2 11, Elegoo PETG PRO
  5). Solidons Deckel aus 12 mm³/s × `flow_factor` ersetzt diese Zahl.
- Druckvorschub: je Filament kalibriert (Orca-Wiki „Pressure Advance“,
  <https://github.com/OrcaSlicer/OrcaSlicer/wiki/pressure_advance_calib>);
  Solidon lässt ihn richtigerweise beim Hersteller.
- Kühlung: Orca-Wiki „Material Cooling“ — die Lüfterkurve über der
  Schichtzeit und „Slow printing down for better layer cooling … so that the
  layer can be cooled for a longer time“ sind Filamentwerte
  (<https://github.com/OrcaSlicer/OrcaSlicer/wiki/material_cooling>).
  Solidons `minimum_layer_time` sitzt in der Qualitätsstufe und überschreibt
  damit einen Filamentwert des Herstellers mit einem Stufenwert.

### 4.7 Elegoo Centauri Carbon 2

Eine öffentliche Elegoo-Dokumentation mit Begründungen für die
Slicerwerte des CC2 fand sich nicht; die Produktseite nennt keine
Slicerwerte. Maßgeblich bleibt das Profil selbst (Abschnitt 2). Ein
Drittanbieter-Leitfaden zum ElegooSlicer bestätigt die Plattenlogik: „Each
plate type stores its own recommended bed temperature for each filament“,
und beim Centauri Carbon sei die Auswahl auf „Textured PEI Plate“ fest
(<https://printago.io/guides/elegoo-slicer-bed-type>). Das CC2-Profil passt
dazu: `default_bed_type = 4`, kein `support_multi_bed_types`.

## 5. Unterschiede innerhalb der Familie

Installiert und geprüft (Binärdateien und Profilbestände auf dieser
Maschine, 27.09.2026):

| Programm | Version | Grundlage | Profilbestand |
|---|---|---|---|
| ElegooSlicer | 1.5.3.4 (`elegoo-slicer.exe`) | Orca-Abkömmling (Kennung „OrcaSlicer 2.3.1-alpha“ in `ElegooSlicer.dll`) | `%APPDATA%\ElegooSlicer\system\{Elegoo,BBL,Creality,Custom,OrcaFilamentLibrary}`, Elegoo 01.05.03.04 |
| OrcaSlicer | Kennung „OrcaSlicer 2.4.2“ in `OrcaSlicer.dll` (Dateiversion leer) | — | `C:\Program Files\OrcaSlicer\resources\profiles\<Hersteller>` |
| Bambu Studio | 02.08.02.61 | eigene Linie (Orca stammt davon ab) | `C:\Program Files\Bambu Studio\resources\profiles\BBL` (02.08.00.05); unter `%APPDATA%\BambuStudio` liegt kein `system` |
| Creality Print | 7.2, Build 5483 | Orca-Abkömmling | `%APPDATA%\Creality\Creality Print\7.0\system\Creality` |

### 5.1 Schlüssel, die fehlen

Geprüft an den Binärdateien (Zeichenkette vorhanden oder nicht):

| Schlüssel | Orca | Elegoo | Bambu | Creality | Folge für Solidon |
|---|---|---|---|---|---|
| alle Schlüssel, die Solidon schreibt (`TABLES["orca"]`, Plattentemperaturen, `gcode_label_objects`, `support_base_pattern_spacing`, `filament_shrink`) | ja | ja | ja außer `gcode_label_objects` | ja außer `supertack_plate_temp` | Bambu übergeht `gcode_label_objects` still (Bambu markiert Objekte ohnehin) |
| `supertack_plate_temp` | ja | ja | ja | **nein** | Creality übergeht ihn; harmlos |
| `textured_cool_plate_temp` | ja | ja | nein | nein | `PLATE_KINDS` kennt ihn nicht → bei Orca/Elegoo bleibt diese Platte beim Filamentwert |
| `epoxy_resin_plate_temp`, `customized_plate_temp` | nein | nein | nein | **ja** | `PLATE_KINDS` kennt sie nicht |
| `support_threshold_overlap` | ja | ja | nein | nein | nicht schreiben |
| `make_overhang_printable` | ja | ja | **nein** | ja | als Vorschlag nur, wo vorhanden |
| `brim_ears_max_angle`, `dont_slow_down_outer_wall`, `tree_support_branch_angle_organic`, `first_layer_flow_ratio`, `hole_to_polyhole` | ja | ja | nein | teils | nicht schreiben, ohne die Familie zu unterscheiden |
| `inner-outer-inner wall` (Wert von `wall_sequence`) | ja | ja | ja | ja | überall nutzbar (B-10) |

### 5.2 Aufzählungen und Vorgaben, die auseinandergehen

- **`support_style`**: Orca/Elegoo/Creality `organic`, Bambu `tree_organic`
  (dazu `tree_hybrid`, `tree_slim`, `tree_strong`, `snug`, `grid` überall).
  Solidon schreibt `support_style` nicht — dabei bleiben. Die Vorgabe
  `default` heißt bei Orca „Organic“, bei Bambu „Hybrid, wenn Stützmaterial
  oder adaptive Schichthöhe, sonst Organic“ (Bambu-Wiki).
- **`support_type`**: dieselben vier Werte in allen (`normal(auto)`,
  `tree(auto)`, `normal(manual)`, `tree(manual)`), dazu das alte
  `hybrid(auto)`.
- **`brim_type`**: überall `auto_brim`, `brim_ears`, `painted`,
  `outer_only`, `inner_only`, `outer_and_inner`, `no_brim`; Vorgabe
  `auto_brim`.
- **`precise_outer_wall`**: Vorgabe Orca `true`, Bambu `false`. Profile ohne
  eigenen Wert (Orca-BBL, Anycubic, Sovol) fahren in OrcaSlicer also mit
  genauer Außenwand; Solidon schaltet sie dort ab.
- **`curr_bed_type`**: Vorgabe `Cool Plate` in Orca und Bambu; Creality
  kennt zusätzlich „Epoxy Resin Plate“. Die Standardplatte eines Druckers
  (`default_bed_type`) setzt nur die Oberfläche, nicht die Konsole.
- **Profilnamen**: Orca `Creality K1 (0.4 nozzle)`, Creality Print
  `Creality K1 0.4 nozzle`. Orcas Ender-3 V3 nennt als
  `default_print_profile` `0.20mm Standard @Creality Ender3 V3`, einen
  Prozess, den es im Bestand 2.4.2 nicht gibt (vorhanden: `@Creality
  Ender-3 V3`). `slicer_profiles.match` fällt dann auf `fitting[0]` zurück
  (slicer_profiles.py:2209–2210) — welcher Prozess das ist, hängt an der
  Sortierung, nicht am Hersteller (B-16).
- **Herstellerprofile nennen Rückzug an der Maschine**, Filamente meist mit
  `nil`. Bambu nennt für PETG Basic einen eigenen Filamentrückzug (0,4 mm).
  Solidon schreibt immer `filament_retraction_*` und hebt damit die
  Maschinenwerte in allen vier Programmen gleich auf.

### 5.3 G-Code und Konsole

- **Bahnarten**: Orca, Elegoo, Creality schreiben `;TYPE:`, Bambu
  `; FEATURE: `; Schichtwechsel Orca/Elegoo/Creality `;LAYER_CHANGE`, Bambu
  `; CHANGE_LAYER`. Solidons Leser (`slice/gcode.py:492`, `516`, `532`)
  deckt beide Schreibweisen ab — kein Befund.
- **Konsole**: gleicher Aufruf für alle vier (`--load-settings
  "<maschine>;<prozess>"`, `--load-filaments`, `--slice 0`, `--outputdir`,
  optional `--arrange 0`; handover.py:2246–2285). Creality braucht die
  vorhandene Kopie ohne `plate`-Block (Absturz 7.2.2.5483, in
  `app/core/export/CLAUDE.md` beschrieben), Bambu sagt über `result.json`
  ab. Beides ist behandelt.
- **Offen und vor einem Umbau zu messen:** Ob `curr_bed_type` aus
  `project_settings.config` auch dann greift, wenn zugleich
  `--load-settings` Maschine und Prozess lädt. Gemessen ist es nur ohne
  `--load-settings` (Abschnitt 0). Sicher ist es, den Schlüssel in **beide**
  Stellen zu schreiben: Projektdatei und Prozessdatei.

## 6. Priorisierte Befunde mit Änderungsvorschlag

Schwere: **D** druckentscheidend · **Q** Qualität/Zeit · **K** Kosmetik.
Zeilennummern gelten für den Arbeitsbaum am 27.09.2026 (im Baum liegen
fremde, unfertige Änderungen an `profiles.py`/`types.py`, siehe B-01).

### Grundsatz vorweg (B-00, Architektur)

`handover.profile_differences` (handover.py:2088–2147) entscheidet heute
ausdrücklich gegen den Hersteller: „Übergeben werden die Einstellungen.“ —
Solidons Tabellenwerte gewinnen, das Herstellerprofil wird nur als
Info-Befund genannt. `_orca_process` (1847–1848) und `_orca_filament`
(1981) setzen das um. Roberts Maßstab dreht die Richtung um. Alle folgenden
Befunde sind Einzelfälle davon; der saubere Weg ist einer:

1. **Grundlage ist das aufgelöste Herstellerprofil** (Prozess, Filament,
   Maschine) — das passiert heute schon.
2. **Geschrieben wird nur eine Abweichung mit Herkunft**: Nutzerwahl im
   Druckdialog, übernommener Vorschlag (mit `SettingAdvice.reason`) oder ein
   technisch nötiger Schlüssel (`curr_bed_type`, Slots, Stützsperre).
3. **Der Druckdialog zeigt die Herstellerwerte** (Rücklesen des Prozesses,
   analog `slicer_profiles.FILAMENT_READBACK`), damit Solidons Vorschläge
   gegen das rechnen, was tatsächlich gedruckt wird.
4. **Ohne installierten Slicer** bleiben Solidons Tabellen der Rückfall —
   nur dann.

Umsetzungsskizze: `PrintSettings` bekommt je Feld die Herkunft (etwa eine
Menge `explicit: frozenset[str]` der ausdrücklich gesetzten Punktpfade, gefüllt
von Dialog und `advise.apply`); `as_mapping` schreibt für die Orca-Familie nur
Einträge, deren Pfad darin steht, plus die technisch nötigen. Eine
Formatänderung der Projektdatei folgt daraus (Checkliste „Dateiformat
ändern“): Ältere Projekte tragen alle Werte als ausdrücklich — Migration
entweder „alles explizit“ (nichts ändert sich) oder „nur, was von der
Stufenvorgabe abweicht“ (empfohlen, mit Befund beim Öffnen).

---

### B-01 · D · Stützwinkel: Solidons Analysegrenze geht als Slicer-Schwelle hinaus

- **Fundstelle:** `app/core/types.py:1171`
  (`threshold_angle: float = OVERHANG_LIMIT_DEGREES`),
  `app/core/knowledge/rules.py:41` (`45.0`),
  `app/core/export/slicer_keys.py:409` mit `_angle_from_horizontal`
  (189–211).
- **Hersteller:** 30 — Elegoo `process/fdm_process_elegoo_common.json`,
  Bambu `process/fdm_process_common.json`, Creality Print
  `0.20mm Standard @Creality K1 0.4 nozzle.json`; Sovol 40. Orca- und
  Bambu-Vorgabe ebenfalls 30.
- **Solidon:** 45 für jeden Drucker.
- **Quelle:** Orca `PrintConfig.cpp` (Vorgabe 30); Bambu-Wiki „Support“
  („safe angle to print without support“); gemessen Abschnitt 0 (46,4 m →
  0 m).
- **Vorschlag:** `support.threshold_angle` **nicht** mehr mit der
  Analysegrenze vorbelegen und **nicht** übergeben, solange der Nutzer ihn
  nicht setzt — der Herstellerwert bleibt stehen. Für die eigene Analyse
  („braucht es Stütze?“) denselben Winkel verwenden, mit dem der Slicer
  stützt: aus dem gebundenen Prozessprofil zurücklesen
  (`support_threshold_angle`, umgerechnet 90 − x gegen die Senkrechte);
  ohne Slicer der Wert aus `printers.toml`. Im Arbeitsbaum liegt eine fremde,
  unfertige Änderung, die `PrinterProfile.overhang_limit` einführt und
  `Profile.overhang_limit_degrees` daraus speist (types.py ab 819/959,
  profiles.py:157) — das trifft die Analyseseite, lässt aber
  `SupportSettings.threshold_angle` (types.py:1171) und damit die Übergabe
  unverändert. Zusätzlich: Überhangflächen, die **auf dem Bett beginnen**
  (Fase an der Unterkante), in `analysis`/`advise` nie als Stützbedarf zählen;
  der Slicer stützt dort nichts Sinnvolles, und eine Schwelle genau auf 45°
  kippt an der Facettenrundung.

### B-02 · D · „Stützen“ heißt bei Solidon Gitter — der Hersteller will Baum

- **Fundstelle:** `slicer_keys.py:324–328` (`_ORCA_SUPPORT_TYPE`:
  `none`/`grid` → `normal(auto)`), `slicer_keys.py:404–407`,
  `advise.py:693–705` (Baum erst ab `TREE_FROM_ISLANDS = 8` Inselschichten,
  advise.py:107, sonst `grid`).
- **Hersteller:** `tree(auto)` bei CC2 (`ECC2/0.20mm Standard @Elegoo CC2
  0.4 nozzle.json`) und allen Bambu (`process/fdm_process_common.json`);
  `normal(auto)` bei Neptune 4, Creality, Anycubic, Sovol.
- **Solidon:** immer `normal(auto)` — auch bei ausgeschalteten Stützen, damit
  bekommt jeder, der im Slicerfenster Stützen einschaltet, Gitter.
- **Quelle:** Orca `support_style` (Baum-Vorgabe organisch), Bambu-Wiki;
  Messung Abschnitt 0.
- **Vorschlag:** Der Vorschlag „Stützen nötig“ setzt nur
  `enable_support = 1` (je Objekt, B-13) und lässt `support_type` beim
  Hersteller. `support.style` bekommt den Wert „wie Hersteller“ als Vorgabe;
  `grid`/`tree` werden nur geschrieben, wenn der Nutzer sie wählt. `none` wird
  als `enable_support 0` geschrieben und `support_type` gar nicht
  (`_only` statt `_mapped`). Die Regel `TREE_FROM_ISLANDS` entfällt für die
  Orca-Familie oder schlägt höchstens Baum vor, wo der Hersteller Gitter hat.

### B-03 · D/Q · Solidon schaltet den Auto-Brim ab und legt einen Skirt

- **Fundstelle:** `slicer_keys.py:413`
  (`_mapped({"brim": "outer_only"}, "no_brim")`), `print_settings.toml:138`
  und `:158` (`adhesion = "skirt"` für PLA und PETG), `types.py:1199`,
  `handover._only_chosen_adhesion` (613–635).
- **Hersteller:** `brim_type` fehlt überall → Vorgabe `auto_brim`
  (Creality setzt es ausdrücklich); `skirt_loops = 0`
  (`fdm_process_elegoo_common.json`).
- **Solidon:** `no_brim`, `skirt_loops 2`, `skirt_distance 3`.
- **Quelle:** Orca-Wiki „Brim“ (Auto rechnet aus Material, Geometrie, Tempo,
  Wärme); `Brim.cpp` (Brim wird neben Normalstütze ausgespart).
- **Vorschlag:** Neuer Haftungswert „wie Hersteller“ als Vorgabe
  (`AdhesionType` um `"auto"` erweitern; Orca: `brim_type` nicht schreiben,
  Skirt nicht schreiben). Solidons eigene Brim-Regeln (`SMALL_FOOTPRINT`,
  `_on_small_feet`, `_slender`) als **Objektwert** `brim_type outer_only`
  mit Breite — dort, wo sie greifen, und nur dort. Der Materialwert „brim“
  bei ASA/ABS/PETG-CF bleibt ein Materialgrund.

### B-04 · Q · Erste Schicht höher, schmaler und heißer als beim Hersteller

- **Fundstelle:** `print_settings.toml:52` (`first_layer_height = 0.25`),
  `print_settings.py:216` (`extrusion_width * 1.07`),
  `print_settings.toml:122` und `:142` (`nozzle_first_layer` = Düse + 5).
- **Hersteller:** 0,2 mm Höhe (`fdm_process_common.json`), 0,5 mm Breite
  (`fdm_process_elegoo_common.json`; Bambu `fdm_process_common.json`;
  Creality 0,5 bzw. 0,55), Düse erste Schicht = Düse (Elegoo PLA 210).
- **Solidon:** 0,25 / 0,449 / 215 (PETG 245).
- **Quelle:** Ellis’ Print Tuning Guide: Breite „120% or greater“; die
  0,25 mm Höhe dort als persönliche Vorliebe.
- **Vorschlag:** Nicht schreiben — aus dem Herstellerprozess übernehmen.
  Wo Solidon die Maße für die eigene Rechnung braucht (`bead_area`,
  `flow_speed_limit(first_layer=True)`), aus dem Profil zurücklesen.

### B-05 · D · Keine Plattenangabe; Solidons Bettwert überschreibt jede Platte

- **Fundstelle:** `handover.py:2035` (`PLATE_KINDS`), `2038–2057`
  (`_with_every_plate`); `project_settings` (1582–1729) und `_orca_process`
  (1806–1887) schreiben kein `curr_bed_type`.
- **Hersteller:** CC2 `default_bed_type = "4"` (Textured PEI,
  `ECC2/Elegoo Centauri Carbon 2 0.4 nozzle.json`); PLA: Textured PEI 60,
  Cool Plate 35, Engineering **0** (`filament/fdm_filament_pla.json`);
  PETG: Cool Plate **0** (`BASE/Elegoo PETG @base.json`, Bambu
  `Bambu PETG Basic @base.json`).
- **Solidon:** alle Platten = eigener Bettwert (PLA 60, PETG 80).
- **Quelle:** Orca `Print.cpp` („Plate %d: %s does not support filament
  %s“ bei 0); `PrintConfig.cpp` (`curr_bed_type` Vorgabe Cool Plate);
  Bambu-Wiki Platten (SuperTack: PLA 40 °C, PETG 55–60 °C); Messung: Konsole
  ohne Angabe → `Cool Plate`, Elegoo-Lauf mit 35 °C Bett.
- **Vorschlag:** `curr_bed_type` immer schreiben (Projektdatei **und**
  Prozessdatei des Konsolenlaufs), Wert aus `default_bed_type` des
  Maschinenprofils bzw. aus einer Plattenwahl im Druckdialog (Liste je
  Programm: Orca/Elegoo sechs Platten inkl. `Textured Cool Plate`, Creality
  zusätzlich `Epoxy Resin Plate`). `_with_every_plate` entfällt; überschrieben
  wird höchstens die Temperatur **der gewählten Platte**, und nur bei
  ausdrücklicher Abweichung. Eine 0 des Herstellers wird nie überschrieben,
  sondern wird zum Befund mit Handlung („Andere Platte wählen“).

### B-06 · Q · Stützabstände und Grundmuster ohne Grund überschrieben

- **Fundstelle:** `types.py:1181–1184` (`z_gap 0.2`, `xy_gap 0.5`,
  `density 0.15`, `interface_layers 2`), `handover._support_spacing`
  (638–660), `slicer_keys.py:410–412`.
- **Hersteller:** XY 0,35 (`fdm_process_elegoo_common.json`), Anycubic/Sovol
  60 %; Grundmuster-Abstand Elegoo CC2 1 (Baum), sonst 2,5, Anycubic/Sovol
  0,2; Schnittstelle oben 2 (Anycubic/Sovol 3); Z oben 0,2 (Sovol 0,18).
- **Solidon:** XY 0,5; Abstand 2,8; Schnittstelle 2; Z 0,2.
- **Vorschlag:** Diese Felder mit „wie Hersteller“ vorbelegen und nur bei
  Nutzeränderung schreiben. `support_base_pattern_spacing` bei Baumstützen
  nie schreiben.

### B-07 · Q · Tempi auf Solidons Volumenstrom gedeckelt, Bambu ohne Faktor

- **Fundstelle:** `print_settings.py:307–325` (`_within_flow`),
  `print_settings.py:274–276` (`max_flow × flow_factor`, nur PLA),
  `printers.toml:109–192` (A1, A1 mini, P1S, X1C ohne `flow_factor`),
  `printers.toml:338–353` (SV06 ohne Beschleunigungen → Stufe 8000/5000),
  `printers.toml:332` (Kobra 2 `speed_infill = 70` wird auch
  `internal_solid_infill_speed`, slicer_keys.py:396).
- **Hersteller:** Bambu 200/300/270/250 mm/s bei 21 mm³/s
  (`Bambu PLA Basic @base.json`); K1 200/300/270 bei 18 (CR-PLA); SV06
  Maschinengrenze 500–1250 mm/s², Prozess 0 (= Maschine); Kobra 2
  Vollfüllung 150.
- **Solidon:** Bambu alle Rollen 142 mm/s und 12 mm³/s; K1 167; Neptune 4 178;
  SV06 8000/5000 mm/s²; Kobra 2 Vollfüllung 70.
- **Quelle:** Orca-Wiki „Max Volumetric Speed“ (je Drucker **und** Filament
  kalibrieren).
- **Vorschlag:** Tempi und Beschleunigungen nicht schreiben; der Slicer
  begrenzt selbst über `filament_max_volumetric_speed` des gewählten
  Filaments. `advise._from_flow` gegen den Volumenstrom des gebundenen
  Filamentprofils rechnen, nicht gegen Solidons Tabelle. Bis dahin
  mindestens `flow_factor` für die Bambu-Drucker (21/12 = 1,75) nachtragen
  und für Drucker ohne Herstellerwerte (SV06) keine Beschleunigung
  übergeben.

### B-08 · Q · Solidons Qualitätsstufe ersetzt den Herstellerprozess

- **Fundstelle:** `print_settings.toml:49–66` (Standard: 3 Wände,
  4 Bodenschichten, `grid`), `types.py:1079` (`arachne`),
  `slicer_keys.py:341–350` (alle Bahnbreiten = `line_width`).
- **Hersteller:** 2 Wände, 3 Bodenschichten, `classic`, Muster
  `rectilinear` (CC2) / `crosshatch` (Orca-BBL) / `cubic` (N4) / `grid`
  (Bambu Studio) / `zig-zag` (Creality E3V3); Innenwand und Füllung 0,45 mm.
- **Vorschlag:** Die Stufen auf die **Herstellerprozesse gleichen Namens**
  abbilden, statt eigene Werte zu schreiben: Standard → `0.20mm Standard`,
  Fein → `0.12mm Fine`, Entwurf → `0.24mm Draft`/`0.28mm Extra Draft`,
  Belastbar → `0.20mm Strength` (bei Elegoo CC2 und Bambu alle vorhanden).
  Arachne, Wandzahl, Bahnbreite und Fülldichte nur über die vorhandenen,
  begründeten Vorschläge (`advise.py:854–869`, `884–908`, `1092–1162`).

### B-09 · Q · Materialtabelle schlägt das Herstellerfilament (lokale Spule)

- **Fundstelle:** `handover.py:1044` (Herstellerwerte nur bei
  `slot.material`), `handover.py:1970–1981` (Solidons Werte über
  `inherited`), `print_settings.toml:120–158`.
- **Hersteller:** z. B. Elegoo PETG @ECC2: 250 °C, Bett 70, Lüfter 10–40 %,
  3 Schichten ohne Lüfter, 12 s Mindestschichtzeit; Bambu PLA Basic 220 °C.
- **Solidon:** PETG 240/80, Lüfter 20–50 %, 2 Schichten, 8 s; PLA 210.
- **Beleg am Auftrag:** Minigolf-3MF, Spule „PLA Lavendal“ auf Elegoo PLA
  @ECC2 als Unterlage: `nozzle_temperature_initial_layer 215`,
  `slow_down_layer_time 8`, `filament_z_hop 0.2` — Solidons Werte, nicht
  Elegoos.
- **Vorschlag:** Eine lokale Spule **gleichen Typs** wie das gewählte
  Herstellerfilament wie `slot.material` behandeln: Herstellerwerte für
  alles aus `FILAMENT_READBACK`, Solidons Tabelle nur ohne jedes
  Herstellerfilament. Ausdrückliche Spulenwerte (`SlotOverride`) gewinnen
  weiter.

### B-10 · Q · Passungsvorschlag setzt zwei Werte, die sich aufheben

- **Fundstelle:** `advise.py:982–993` (`precise_outer_wall = True`) und
  `1018–1029` (`outer_wall_first = True`); Übersetzung
  `slicer_keys.py:355–362`.
- **Hersteller:** `inner wall/outer wall`, `precise_outer_wall` 0 (Elegoo),
  Orca-Vorgabe 1.
- **Solidon:** beide an → `outer wall/inner wall` + `precise_outer_wall 1`.
- **Quelle:** Orca `PrintConfig.cpp`: genaue Außenwand „will be ignored for
  outer-inner or inner-outer-inner wall sequences“; `PerimeterGenerator.cpp`
  prüft `wall_sequence == InnerOuter`. Orca-Wiki empfiehlt Innen/Außen/Innen
  statt Außen/Innen.
- **Vorschlag:** Für Passungen `wall_sequence = inner-outer-inner wall`
  (ab drei Wänden; in allen vier Programmen vorhanden) **oder**
  Innen/Außen mit genauer Außenwand — nicht beides. `shell.outer_wall_first`
  in der Orca-Tabelle auf `inner-outer-inner wall` abbilden, wenn
  `wall_count ≥ 3`. Und je Objekt (B-13): nur die Teile mit Passung.

### B-11 · Q · Rückzug und Z-Hop der Maschine werden überschrieben

- **Fundstelle:** `slicer_keys.py:426–429` (`filament_retraction_length`,
  `…_speed`, `filament_z_hop`, `filament_wipe`), `print_settings.toml:131–133`
  und `151–153`.
- **Hersteller:** Maschine CC2 0,8 mm / 30 mm/s / Z-Hop 0,4
  (`machine/fdm_elegoo_3dp_001_common.json`), Neptune 4 60 mm/s, Kobra 2
  2 mm / 80 mm/s, SV06 Z-Hop 0; Bambu PETG Basic 0,4 mm im Filament.
- **Solidon:** PLA 0,8/35/0,2; PETG 1,2/30/0,3 — für jeden Drucker.
- **Vorschlag:** Die vier `filament_*`-Zeilen nur schreiben, wenn der Nutzer
  oder eine Spule sie setzt; das `nil` der Herstellerfilamente stehen lassen.
  Die PETG-Begründung (toml:159–160) ist ein Materialgrund, aber kein Grund,
  Bambus kalibrierte 0,4 mm auf 1,2 mm zu verdreifachen.

### B-12 · Q · Kein Rücklesen des Herstellerprozesses

- **Fundstelle:** `slicer_profiles.py:2223–2245` (`FILAMENT_READBACK` gibt
  es), kein Gegenstück für Prozesswerte; `print_settings.resolve`
  (print_settings.py:194–278) kennt nur Stufe, Material, Drucker.
- **Folge:** Der Druckdialog zeigt Solidons Stufe statt dessen, was gedruckt
  wird, und `advise` rechnet gegen falsche Wände, Breiten und Tempi (z. B.
  der Verbindervorschlag gegen 3 statt 2 Wände).
- **Vorschlag:** `PROCESS_READBACK` (Solidon-Pfad → Orca-Schlüssel, dieselbe
  Tabelle rückwärts wie `slicer_keys.ORCA`), beim Binden des Prozessprofils
  in `PrintSettings` einlesen; Grundlage für B-00.

### B-13 · D/Q · Stütze, Passung, Verbinder: plattenweit statt je Objekt

- **Fundstelle:** `advise.for_part` (1165–1195, Docstring 1175–1177);
  `writer._part_settings` (1013–1046); `threemf._settings_xml` (456).
- **Hersteller/Slicer:** Stütz-, Brim-, Wand-, Füll- und
  Beschleunigungswerte sind Objektwerte (`PrintObjectConfig`,
  `PrintRegionConfig`, Abschnitt 3.1).
- **Solidon:** `enable_support` für alle Objekte der Platte, sobald eines
  Stütze braucht (Minigolf: fünf Objekte).
- **Vorschlag:** `advise` je Körper auswerten und die Stütz-, Passungs- und
  Verbinderwerte über `object_keys` in `model_settings.config` schreiben;
  plattenweit nur Temperatur, Kühlung, Skirt, erste Schicht,
  `curr_bed_type`. Für Prusa (Objektwerte in `Slic3r_PE_model.config`)
  gilt dasselbe; Cura kann es nicht und bekommt weiter den Plattenwert.

### B-14 · K · „Wände nicht kreuzen“ pauschal an

- **Fundstelle:** `types.py:1214`, `slicer_keys.py:425`.
- **Hersteller:** überall 0.
- **Quelle:** Orca-Wiki empfiehlt es für PETG und TPU („materials prone to
  stringing“), kostet Zeit.
- **Vorschlag:** Als Materialwert führen (PETG, TPU an; PLA wie Hersteller)
  statt als Vorgabe für alles.

### B-15 · K · Objektmarken

- **Fundstelle:** `handover.py:1854` (`gcode_label_objects = "1"`).
- **Befund:** begründet und richtig; Bambu Studio kennt den Schlüssel nicht
  (übergeht ihn still). `exclude_object` (Klipper) setzt Elegoo auf 0,
  Creality auf 1.
- **Vorschlag:** so lassen; `exclude_object` nicht ohne Nachweis der
  Firmware setzen.

### B-16 · K · Rückfall auf irgendein Prozessprofil

- **Fundstelle:** `slicer_profiles.match` (2209–2210): fehlt der
  `default_print_profile`, gilt `fitting[0]`.
- **Befund:** Orcas Ender-3 V3 nennt einen Prozess, den der Bestand 2.4.2
  nicht hat (`@Creality Ender3 V3` statt `@Creality Ender-3 V3`).
- **Vorschlag:** Rückfall auf den Prozess mit der Schichthöhe der Stufe und
  „Standard“ im Namen, sonst leer lassen und fragen (Regel 21).

### B-17 · K · Plattenliste unvollständig

- **Fundstelle:** `handover.py:2035`.
- **Befund:** Orca/Elegoo kennen `textured_cool_plate_temp`, Creality
  `epoxy_resin_plate_temp` und `customized_plate_temp`; Creality kennt
  `supertack_plate_temp` nicht.
- **Vorschlag:** Entfällt mit B-05 (nur noch die gewählte Platte).

### Was vor dem Umbau zu messen ist

- Konsolenweg mit `--load-settings`: Greift `curr_bed_type` aus der
  Projektdatei, aus der Prozessdatei oder aus beiden (Abschnitt 5.3)?
- `verify_settings` vergleicht `SlicerConfig.written`; mit B-00 schrumpft
  diese Menge, die Gegenprobe muss dann die **nicht** geschriebenen Werte
  gegen das Herstellerprofil prüfen, sonst verliert sie ihre Aussage.
- Nach jeder Änderung: echter Slicerlauf an Minigolf, Waschschüssel und einem
  Teil mit Passung, Schicht 1–3 im G-Code lesen (Memory
  „Übergabe je Modell, Slicer, Drucker“).

## 7. Kurzfassung — die zehn wichtigsten Änderungen

1. **Richtung umkehren (B-00):** Herstellerprofil ist die Grundlage, Solidon schreibt nur Nutzerwahl, übernommene Vorschläge und technisch Nötiges; `profile_differences` entscheidet heute „Übergeben werden die Einstellungen“.
2. **Stützwinkel nicht übergeben (B-01):** `types.py:1171` koppelt die Analysegrenze 45° an `support_threshold_angle`; Hersteller 30 (SV06 40). Für die Analyse den Winkel des gebundenen Prozessprofils lesen; Überhänge, die auf dem Bett beginnen (Fase), nie als Stützbedarf.
3. **Stützart beim Hersteller lassen (B-02):** „Stützen nötig“ setzt nur `enable_support`; kein `normal(auto)` über Elegoos/Bambus `tree(auto)`. Gemessen am Minigolf: 46,4 m → 0 m.
4. **Stützen, Passungen, Verbinder je Objekt (B-13):** über `model_settings.config` statt plattenweit.
5. **`curr_bed_type` schreiben, Plattentemperaturen stehen lassen (B-05):** Konsole nimmt sonst „Cool Plate“ (gemessen); `_with_every_plate` hebt Herstellersperren (0 °C) auf.
6. **Auto-Brim nicht abschalten, keinen Skirt erzwingen (B-03):** Solidons Brim-Regeln nur als Objektwert.
7. **Erste Schicht vom Hersteller (B-04):** 0,2 mm / 0,5 mm / Düse gleich statt 0,25 / 0,449 / +5 °C.
8. **Materialwerte vom Herstellerfilament auch für lokale Spulen gleichen Typs (B-09)**; Rückzug/Z-Hop der Maschine nicht überschreiben (B-11).
9. **Tempi nicht deckeln (B-07):** Bambu fährt heute alle Rollen mit 142 mm/s (fehlender `flow_factor`), der SV06 bekommt 8000 mm/s² über seiner Grenze; Volumenstrom aus dem gebundenen Filament.
10. **Qualitätsstufen auf Herstellerprozesse abbilden (B-08, B-12)** und den Passungsvorschlag entwirren (B-10: `inner-outer-inner wall` statt Außen zuerst plus wirkungsloser genauer Außenwand).
