# Slicer-Audit Cura / CuraEngine — 27.09.2026

Prüfer: Unteragent (nur lesen, keine Änderung im Repository). Gegenstand: Solidons
Übergabe an `C:\Program Files\UltiMaker Cura 5.13.0\CuraEngine.exe`
(Definitionen `share\cura\resources\definitions\`, `setting_version = 27`).
Geprüfter Stand: HEAD `46fa73c17`. Während der Prüfung stand im Arbeitsbaum
vorübergehend eine fremde, nicht committete Änderung (Überhanggrenze je Drucker
aus `printers.toml`, `overhang_limit`, z. B. Ender-3 V3 → 60°); sie war beim
Abschluss wieder verschwunden. Wo sie die Cura-Übergabe berührt, steht es dabei.

Maßstab (Robert): das Herstellerprofil. Jede Abweichung Solidons braucht einen
Grund, der am Modell oder am Material hängt.

Probe-Artefakte (Kommandozeile, übergebene Werte, G-Code, Winkelreihe,
vollständige Vergleichstabellen):
`F:\3D Druck\output\review\slicer-audit-2026-09-27\cura-probe\`.

---

## 0. Wie Solidon an CuraEngine übergibt — und was daraus folgt

### 0.1 Der Weg „Slicen“ (Konsole)

`handover._command` (`app/core/export/handover.py:2290–2318`) baut:

```
CuraEngine slice -j fdmprinter.def.json  -s k=v … (228 Werte)
                 -e0 -j fdmextruder.def.json -s k=v … (dieselben 228)
                 -l <alle Teile als ein STL> -o solidon.gcode
```

- Als Definition geht **immer `fdmprinter.def.json`** hinein (`_cura_base`,
  `handover.py:2357`). Der Druckdialog wählt für Cura bewusst kein
  Maschinenprofil (`app/ui/print_settings_dialog.py:3954–3966`: „Dieser Slicer
  braucht kein Profil — Solidon beschreibt die Maschine selbst“), und
  `slicer_profiles.chosen_machine` liefert für Cura immer leer.
- CuraEngine liest aus einer Definition **nur `default_value`**, nie die
  `value`-Formeln (Quelltext `src/communication/CommandLine.cpp`,
  `loadJSONSettings`: „default_value“ wird gelesen, „value“ nur mit
  `--force-read-nondefault` und dann als Text, nicht ausgewertet). Das
  Cura-Fenster dagegen wertet jede Formel aus und schickt **alle** Werte
  (`plugins/CuraEngineBackend/StartSliceJob.py`, `_buildGlobalSettingsMessage`
  und `_buildExtruderMessage`, lokal in der Installation gelesen).
- **Folge:** Vom „Herstellerprofil“ im Cura-Sinn — Druckerdefinition +
  Qualitätsprofil + Düsenvariante + Material — kommt bei der Konsolenübergabe
  **nichts** an. Was Solidon nicht selbst schreibt, ist der `default_value` von
  `fdmprinter` (ein Ultimaker-Generikum mit 2,85-mm-Material, 6,5 mm Rückzug,
  `infill_before_walls = true`, generischem Start-G-Code). Solidon gleicht das
  mit 228 ausgeschriebenen Werten aus (`values_for` → `as_mapping`,
  `_machine_keys`, `_cura_dependants`); was dort fehlt, fällt auf `fdmprinter`.
- `-s` nach `-l` gilt **je Netz** (`CommandLine.cpp`, `-l`-Zweig:
  `last_settings = …meshes.back().settings_`). Das ist der Weg für
  Objekteinstellungen und die Stützsperre (§ 1.5).

### 0.2 Der Weg „Öffnen“ (Cura-Fenster + `.curaprofile`)

`handover.cura_profile_beside` (`handover.py:3542–3640`) legt eine
`.curaprofile` (`quality_changes`) neben das Modell. Da für Cura nie eine
Maschine gewählt ist, steht darin immer `definition = fdmprinter` und die
Qualitätsart der **fdmprinter-Stufen** mit der nächsten Schichthöhe — bei
0,2 mm also `draft` (`handover.py:3582–3589`; gegengeprüft mit
`slicer_profiles.cura_quality_types`). Curas Importer
(`cura/Settings/CuraContainerRegistry.py:470–515`, lokal gelesen) setzt die
Definition auf die aktive Maschine um und prüft dann die Qualitätsart:

| Aktiver Drucker in Cura | Qualitätsarten dort | Ergebnis mit `draft` |
|---|---|---|
| Creality (Ender-3 V3 SE/KE, K1 Max), Sovol SV06 | adaptive, draft (0,32), low, standard, super, ultra — für 0,4 mm/PLA nur adaptive/low/standard/super | importiert, aber **unsichtbar** („quality type 'draft' is not available for the current configuration“) |
| Elegoo Neptune 4, Centauri Carbon | `Elegoo_layer_020` bzw. `elegoo_cc_layer_020` … | **abgelehnt** („Quality type 'draft' is not compatible …“) |
| Anycubic Kobra 2 (keine eigenen Qualitäten) | fdmprinter-Stufen | importiert, sichtbar |

### 0.3 Wer die Cura-Profile geschrieben hat

Die mitgelieferten Druckerdefinitionen sind Gemeinschaftsbeiträge, nicht
Werksprofile: `creality_base` (Autor trouch.com), `creality_k1max` (Itay
Grudev), `anycubic_kobra2` (ThatGuyZim), `sovol_base` (ed3d.net),
`elegoo_base` (NARUTO), `elegoo_neptune_4` (mastercaution),
`elegoo_centauri_carbon` (Steven Molen) — `metadata.author` in den
`.def.json`. Die Hersteller selbst liefern heute Orca-Abkömmlinge (Creality
Print, ElegooSlicer). Wo die beiden auseinanderliegen — vor allem beim
Stützwinkel —, nennt dieser Bericht beide.

---

## 1. Messungen am Minigolf-Körper

Modell `F:\3D Dateien\Mini+Golf+All+Set-P1S_stls\obj_2_Gövde59.stl`
(82 × 164 × 57 mm), Solidon-Drucker `creality-ender3-v3`, PLA, Stufe
Standard, Weg der Anwendung (`probe.py` nach dem Muster von
`.claude/.state/uebergabe-korpus-2026-09-26/lauf.py`).

### 1.1 Vorschläge und Ergebnis

Solidons Vorschläge für das Teil: `support.style = grid`,
`support.placement = build_plate`, `support.block_channels = true`.

| Lauf | Druckzeit | Stütze | Stützschnittstelle | Schichten mit Stütze |
|---|---|---|---|---|
| Standard (ohne Vorschläge) | 66,4 min | 0 | 0 | 0 von 285 |
| Vorschläge übernommen | 82,3 min | 8,91 m | 14,85 m | 199 von 285, **ab Schicht 0** |

Die Stützsperre kam bei Cura nicht an (`NOT_TAKEN_BY["cura"]`), die
Stützen beginnen mit Schnittstelle bereits in der ersten Schicht direkt am
Teil — dasselbe Fehlerbild wie im ElegooSlicer.

### 1.2 Stützwinkel: Zählrichtung und Menge

Dieselbe Kommandozeile, nur `support_angle` (und die davon gespiegelten
`seam_overhang_angle`, `support_tree_angle`) verändert (`angles.py`):

| `support_angle` | Stütze gesamt | Schichten mit Stütze | Stütze in Schicht 0 |
|---|---|---|---|
| 40° (Cura-Profil Centauri Carbon) | 35,7 m | 227 | 1,81 m |
| **45° (Solidon HEAD; Cura-Profil Creality bei 0,2 mm, Neptune 4)** | **23,8 m** | **199** | **1,61 m** |
| 50° (fdmprinter; Cura-Profil Kobra 2, SV06) | 9,4 m | 12 | 0,66 m |
| 55° | 2,0 m | 3 | 0,63 m |
| 60° (Creality Print/ElegooSlicer: `support_threshold_angle` 30) | 0 | 0 | 0 |

- **Zählrichtung stimmt:** Cura zählt gegen die Senkrechte („At a value of 0°
  all overhangs are supported, 90° will not provide any support“,
  `fdmprinter.def.json`, `support_angle.description`), Solidon auch; ein
  größerer Wert ergibt weniger Stütze. `slicer_keys.py:532` schreibt ohne
  Umrechnung — richtig.
- Der Körper hat Wände zwischen etwa 45° und 55° gegen die Senkrechte: Die
  Grenze entscheidet zwischen „fast überall Stütze“ und „keine“.

### 1.3 Start-G-Code und erste Schicht

Kopf der erzeugten Datei (`ender3v3_pla/vorschlaege/solidon.gcode`):

```
;TIME:6666 / ;Filament used: 0m / ;MINX:2.14748e+06 … / ;TARGET_MACHINE.NAME:Unknown
M140 S60 / M190 S60 / M104 S215 / M109 S215
G28 ;Home
G1 Z15.0 F6000 ;Move the platform down 15mm
G92 E0 / G1 F200 E3 / G92 E0            ← 3 mm Filament in 15 mm Höhe, keine Spüllinie
…
;LAYER:0 … M204 S12000 ;TYPE:SKIRT        ← erste Schicht mit 12 000 mm/s²
```

- Das ist `fdmprinter.machine_start_gcode`. Der Start-Code des Ender-3 V3 SE
  in Cura hätte `M420 S1` (gespeichertes Bettnetz) und zwei Spüllinien auf
  0,28 mm; der des K1 Max ruft das Makro `START_PRINT`; der des Centauri Carbon
  reinigt die Düse (`M729`), setzt Pressure Advance und legt eine Spüllinie.
  Nichts davon kommt an.
- Die Kopfwerte `;TIME:6666`, `MINX … 2.14748e+06`, `Filament used: 0m` sind
  Platzhalter der Konsole — das Fenster ersetzt den Kopf nachträglich. Der
  Kommentar in `_machine_keys` (Bettmaße beheben `MINX`) trifft deshalb nicht
  zu; Solidon liest für Cura `filament_g = null` (Probe `summary.json`).
- CuraEngine ersetzt Platzhalter wie `{material_bed_temperature_layer_0}`
  **nicht**: Probe mit `-s machine_start_gcode=START_PRINT EXTRUDER_TEMP={…}`
  → die Zeile steht wörtlich im G-Code, davor zusätzlich `M190`/`M109`
  (`material_*_temp_prepend` bleibt `true`; das Fenster schaltet es aus, wenn
  der Start-Code die Temperaturen selbst setzt, `StartSliceJob.py`).

### 1.4 Reihenfolge Füllung/Wand

Schicht 4 der Probe: `FILL → WALL-INNER → WALL-OUTER`. Solidon schreibt
`infill_before_walls` nicht; CuraEngine nimmt `fdmprinter`-`true`. Creality,
Anycubic Kobra 2 und Sovol setzen in Cura `false`, Elegoo lässt `true`.

### 1.5 Stützsperre als eigenes Netz — geht

Quader über das ganze Teil als zweites Netz, `-l sperre.stl -s
anti_overhang_mesh=true`:

| Lauf | Stützbewegungen | Modellbewegungen |
|---|---|---|
| ohne Sperre | 18 476 | 277 652 |
| mit Sperre | **0** | 277 654 |

Die Sperre wird nicht als Kunststoff gedruckt (Modellbahn gleich bis auf zwei
Bewegungen). `NOT_TAKEN_BY["cura"]` führt `support.block_channels` damit zu
Unrecht als unerreichbar (`slicer_keys.py:918`).

### 1.6 Mindestfläche der Stütze — am Teil ohne Wirkung

`minimum_support_area` 0 / 2 / 3 mm² ergab an diesem Körper gleich viele
Stützstücke in Schicht 0–2 (84 / 173 / 173) und gleich viel Stütze (5,6 m) —
die Stützen unter der Fase sind zusammenhängende Bänder, keine Krümel.

---

## 2. Abgleich je Drucker (Stufe „Standard“, PLA; PETG wo abweichend)

Cura-Seite: Druckerdefinition + globale Qualität 0,2 mm + Variante 0,4 mm +
`generic_pla_175`/`generic_petg_175` + Materialqualität, Formeln nachgerechnet
(Prüfwerkzeug `cura-probe\werkzeug\curastack.py`, Aufruf über
`compare_wide.py`; Stapelreihenfolge wie Curas Extruder-/Globalstapel). Kobra 2 hat keine eigenen Qualitäten — dort
fdmprinter `draft` (0,2 mm). Cura kennt keinen Ender-3 V3 (CoreXZ), keinen
Centauri Carbon 2, keinen Prusa MK4S/MINI/XL und keinen Bambu: verglichen wird
mit Ender-3 V3 SE/KE und Centauri Carbon (1); für die übrigen gibt es in Cura
kein Herstellerprofil. Solidon-Seite: `handover.values_for(..., "cura")` am
HEAD, Stützen an (`support.style = grid`).

Kürzel: SE = `creality_ender3v3se`, KE = `creality_ender3v3ke`, K1M =
`creality_k1max`, Ko2 = `anycubic_kobra2`, SV = `sovol_sv06`, N4 =
`elegoo_neptune_4`, CC = `elegoo_centauri_carbon` (alle
`share\cura\resources\definitions\`, Qualitäten unter `quality\creality\base\`,
`quality\sovol\`, `quality\elegoo\…`). „·“ = Solidon schreibt nichts, es gilt
fdmprinter. Vollständige Tabellen (100 Schlüssel, je Drucker einzeln):
`cura-probe\vergleich-pla.md`, `cura-probe\vergleich-petg.md`.

### 2.1 Stützen

| Schlüssel | Cura (Hersteller-/Gemeinschaftsprofil) | Solidon | Grund in Solidon? | Empfehlung |
|---|---|---|---|---|
| `support_angle` (gegen die Senkrechte) | SE/KE/K1M 45 (Formel `floor(deg(atan(line_width/2/layer_height)))`, `creality_base`), Ko2/SV 50 (fdmprinter), N4 45 (`45 if speed_print > 99.9 else 50`), CC 40. Werksslicer: Creality Print/Orca `support_threshold_angle 30` = 60° für V3, V3 SE, V3 KE | 45 fest (`rules.py:41`, `types.py:1171`) | nein — Regel „45°“ ohne Drucker- oder Materialbezug; die Zählrichtung stimmt | Grenze je Drucker aus dem Werksslicer (die fremde Arbeitsbaumänderung tut genau das); für Cura dieselbe Zahl, keine Umrechnung. Ohne Angabe die Creality-Formel statt fester 45 (skaliert mit der Schichthöhe: 0,12 mm → 59°) |
| `support_enable` | überall `false` (der Nutzer schaltet) | nach Vorschlag `true` | Vorschlag aus eigener Analyse mit derselben 45°-Grenze | Vorschlag nur mit der Grenze, die übergeben wird (Befund B3) |
| `support_structure` | `normal` | `normal`/`tree` nach Stil | ja | beibehalten |
| `support_type` | `everywhere` | nach Vorschlag `buildplate` | ja (Kanäle, Modellnarben) | beibehalten |
| `support_pattern` | `zigzag` (alle) | `grid` | Grund stammt aus Orca (`rectilinear` kippt, Waschschüssel) — gilt für Curas verbundenes `zigzag` nicht | für Cura `zigzag` lassen (Zeile `slicer_keys.py:527` nur für Orca/Prusa) oder `grid` mit `support_wall_count = 1` |
| `support_wall_count` | Formel: 1 bei `grid`, 1 beim Baum, sonst 0 | 0 bei `grid` (`handover.py:840`) | nein — weicht von der Formel ab, die der Docstring zu übernehmen verspricht | Formel übernehmen: `1 if tree or pattern in (grid, triangles, concentric) else 0` |
| `support_infill_rate` / `support_line_distance` | 20 (Creality), 15; **Baum: 0** (Formel) | 15 auch beim Baum | nein | beim Baum `support_line_distance = 0` wie Curas Formel |
| `support_z_distance` | 0,2 (Creality, N4), 0,15 (CC), 0,1 (Ko2, SV) | 0,2 | ja (eine Schicht) | beibehalten |
| `support_xy_distance` | 0,8 (Creality `wall_line_width_0*2`), 0,7, 0,68 (N4), 0,5 (CC); Orca V3 0,35 | 0,5 | Spanne der Hersteller | beibehalten |
| `support_xy_overrides_z` | Creality `xy_overrides_z`, sonst `z_overrides_xy` | · (`z_overrides_xy`) | — | Kosmetik |
| Schnittstelle an / Höhe | Creality an, 0,8 mm (4 Schichten); SV/Ko2/N4 aus; CC an, 1 mm | an, 0,4 mm (2 Schichten) | ja (Orca-Werksprofile: 2 Schichten) | beibehalten |
| Schnittstellenmuster/-dichte (Blätter `support_roof_pattern`, `support_bottom_pattern`, `support_roof_line_distance`) | Creality `grid` 33 %, Elegoo `lines` 33 %, fdmprinter `concentric` 100 %; Orca V3 Abstand 0,5 mm | `concentric` (·), 100 % (`support_roof_line_distance = line_width`, `handover.py:834`) | nein — fdmprinter-Vorgabe, nicht Werksprofil | `support_roof_pattern`/`support_bottom_pattern = lines` (oder `grid`), Linienabstand ≈ 3 × Bahnbreite (33 %) bzw. Orca 0,5 mm Lücke; CuraEngine liest nur die Blätter, nicht `support_interface_*` |
| `support_bottom_stair_step_height` | 0 bei Schnittstelle unten (Formel), sonst 0,3 | 0 bei Schnittstelle | ja (Formel) | beibehalten |
| `minimum_support_area` | 2 mm² (Creality), 3 mm² (Elegoo), 0 sonst | · (0) | — | 2 mm² schreiben; am Minigolf-Körper ohne Wirkung (§ 1.6), bei Krümelstützen wirksam |
| Stützbrim | `support_brim_enable` an (alle) | · (an), Breite 3 Bahnen | ja (Formel) | beibehalten |
| `speed_support` / Schnittstelle | Creality `speed_wall_0` / `speed_topbottom`; CC Schnittstelle 80; Orca V3 150/80 | = `speed_print` (Innenwand): 214 / 143 mm/s am Ender-3 V3 | nein | Stütze ≤ 150, Schnittstelle ≈ 80 mm/s oder Außenwandtempo |
| Stützsperre | im Fenster „Support Blocker“ = `anti_overhang_mesh` | als unerreichbar geführt | Annahme „STL trägt keine Sperre“ | zweites Netz mit `-s anti_overhang_mesh=true` (gemessen, § 1.5) |

### 2.2 Erste Schicht und Haftung

| Schlüssel | Cura | Solidon | Grund? | Empfehlung |
|---|---|---|---|---|
| Start-G-Code (`machine_start_gcode`) | druckerspezifisch: SE `M420 S1` + Spüllinien; K1M `START_PRINT …`; Ko2 Spüllinie; SV `M420 S1` + Spüllinien; N4/CC Spüllinie, CC `M729`, Pressure Advance | fdmprinter: `G28`, `G1 Z15`, `E3` in der Luft | nein (nur für Orca gelöst) | aus der Druckerdefinition übernehmen, Platzhalter selbst ersetzen, `material_*_temp_prepend` wie das Fenster setzen (Befund B1) |
| `acceleration_print_layer_0` (Blatt; `acceleration_layer_0` ist nur Elternteil) | Creality 500 (Beschleunigung aus); Ko2 2500; SV 1000; N4 500; CC 1000. Orca V3 500, V3 SE 500, V3 KE 1000 | = `acceleration_print`: 12 000 (V3), 10 000 (K1M, CC2), 8 000 (SV06), 6 000 (N4) — `slicer_keys.py:592–595` | nein — fdmprinter-Formel, nicht Werksprofil | eigener Wert für die erste Schicht (Befund B2) |
| `acceleration_skirt_brim` | = Druckbeschleunigung | 12 000 | nein | wie erste Schicht |
| `layer_height_0` | 0,2 (Creality, SV, Elegoo), 0,3 (Ko2) | 0,25 | Solidon-Stufe (dicker = gutmütiger) | vertretbar |
| `initial_layer_line_width_factor` | 100 (Creality-Cura), 125 (N4), 130 (CC), 150 (SV); Orca: V3 0,5 mm ≈ 119 %, SE 0,46 ≈ 115 %, KE 125 % | 106,9 (`print_settings.py:216`: × 1,07) | nein — fester Faktor | je Drucker aus dem Werksprofil (Orca `initial_layer_line_width`), sonst 115–120 % |
| `speed_layer_0` | SE 30 (PETG 15), KE 100, K1M 20, Ko2 40, SV 20, N4 60, CC 50; Orca V3 60, SE 30, KE 50 | 60 (V3), 20 (Ko2, SV), 50 (N4, CC2) | ja (Orca-Standardprozess) | beibehalten |
| `speed_travel_layer_0` | SE/KE 150, Ko2 125 (`= speed_travel`), SV 67, N4 120, CC 100 | Formel `speed_layer_0 * speed_travel / speed_print`: 140 (V3), **16,9 (Ko2)**, 75 (SV) | nein — fdmprinter-Formel auf Solidons Tempi | Untergrenze, z. B. `max(Formel, 100)`, oder Werksprofil (Befund B7) |
| Lüfter erste Schichten | `cool_fan_speed_0 = 0`, voll ab Schicht 4 (Creality `layer_height_0 + 2*layer_height`) bzw. 2 | aus in Schicht 1, voll ab 2 (`_cura_fan_start`) | ja (Material: `disable_fan_layers`) | beibehalten |
| Temperatur erste Schicht | PLA 200–210, PETG 215 (Cura-Generikum), CC PETG 245 | PLA 215, PETG 245 | ja (Material) | beibehalten |
| `adhesion_type` | Skirt (Creality, SV, CC), Brim (Ko2, N4 über fdmprinter) | Skirt, Brim bei kleiner Standfläche | ja (Modell) | beibehalten |
| Skirt | Creality 3 Runden / 10 mm; CC 2 / 2 mm | 2 / 3 mm, `skirt_height` 3 (Formel) | ja | beibehalten |

### 2.3 Wände, Naht, Füllung, Bügeln

| Schlüssel | Cura | Solidon | Grund? | Empfehlung |
|---|---|---|---|---|
| `wall_line_count` | 2 (PLA, Creality/SV/Elegoo), 4 (Creality PETG), 3 (Ko2) | 3 | ja (Solidon-Stufe; Orca V3 3) | beibehalten |
| `top_layers`/`bottom_layers` | 4/4 (Creality), 5/5 (SV), 5/3 (CC) | 5/4 | ja | beibehalten |
| `inset_direction` | `inside_out` | `inside_out` (außen zuerst nach Vorschlag) | ja | beibehalten |
| `infill_before_walls` | `false` (Creality, Ko2, SV), `true` (Elegoo, fdmprinter) | · → `true` (gemessen, § 1.4) | nein | `false` schreiben (Befund B6) |
| `z_seam_type` / `z_seam_corner` | `back` + `z_seam_corner_weighted` (Creality, SV, Elegoo) | `sharpest_corner` (für „aligned“), Ecke · (`inner`) | Zuordnung begründet (`slicer_keys.py:449–462`) | Kosmetik: `z_seam_corner = z_seam_corner_weighted` dazu |
| `fill_outline_gaps` | `false` (Creality, Elegoo), `true` (fdmprinter) | · (`true`) | — | Kosmetik |
| `infill_pattern` / Dichte | `cubic` 20 % (Creality), `lines` 15 % (SV), `grid`, `zigzag` (CC) | `grid` 15 % | ja (Solidon-Stufe) | beibehalten |
| `infill_overlap` / `skin_overlap` | 30/10 % (Creality), 0/20 % (N4) | 10/5 % | fdmprinter-Formel | Kosmetik |
| `wall_overhang_angle` / `wall_overhang_speed_factors` | 90 = aus (alle Cura-Profile); Orca V3: Überhangtempo 50/30/10 mm/s | · (aus) | — | einschalten, sobald die Stützgrenze steigt (Befund B5) |
| `ironing_enabled` | aus | aus / nach Vorschlag | ja | beibehalten |

### 2.4 Kühlung, Rückzug, Fahrwege, Brücken

| Schlüssel | Cura | Solidon | Grund? | Empfehlung |
|---|---|---|---|---|
| Lüfterkurve PLA | 100 % fest (`cool_fan_speed_min = cool_fan_speed`) | 100 % bis 8 s, 50 % ab 80 s | Material (Elegoo @ECC2) | vertretbar; bei Überhängen ohne Stütze beobachten (B5) |
| Lüfterkurve PETG | 100 % (Generikum), 50 % (CC) | 50 % / 20 % | Material | beibehalten |
| `cool_min_layer_time` | 10 s (Creality), 5 s (sonst) | 8 s | Stufe | beibehalten |
| `cool_min_speed` | 10 mm/s | · (10) | — | beibehalten |
| Rückzug PLA | 0,8/40 (SE/KE), 0,5/40 (K1M, SV), 2/80 (Ko2), 0,5/45 (N4), 0,8/30 (CC) | 0,8/35 | Material | vertretbar; Ko2 am Druck prüfen |
| Rückzug PETG | wie PLA (Druckerwert) | 1,2/30 | Material | beibehalten |
| Z-Sprung | aus (Creality, Ko2, N4), an 0,4 (SV, CC) | an, 0,2 (PLA)/0,3 (PETG), bei jedem Rückzug | Material | `retraction_hop_only_when_collides = true` dazu |
| `retraction_combing` | `noskin` (SE, K1M), `no_outer_surfaces` (KE, SV, Elegoo), `off` (Ko2) | `noskin` | ja | beibehalten |
| `retraction_combing_max_distance` | 30 (Creality), 5 (KE), ≈9–14 (Elegoo) | · (0 = unbegrenzt ohne Rückzug) | — | 30 mm, bei PETG ≤ 10 mm schreiben |
| `travel_avoid_supports` | an (Creality, Ko2) | · (aus) | — | an |
| `retraction_min_travel` | 1,5 (Creality), 0,8–2 | 0,84 (Formel 2 × Bahnbreite) | Formel | Kosmetik |
| Brückeneinstellungen | aus in allen Profilen | an, 25–50 mm/s, Fluss 50/60 % (fdmprinter bei „an“) | ja (Solidon-Brückentempo) | beibehalten |

### 2.5 Tempo, Beschleunigung, Volumenstrom, Maschine

| Schlüssel | Cura | Solidon | Grund? | Empfehlung |
|---|---|---|---|---|
| Tempi | SE 90–180, KE 150–300, K1M 25–50 (veraltet), Ko2 40–80, SV 25–60, N4 125–250, CC 150–200 | V3 200–214, K1M 167, Ko2 70–142, SV 25–40, N4 160–178, CC2 160–200 | ja (Orca-Standardprozess des Werks, über den Volumenstrom gedeckelt) | beibehalten; Zuordnung V3 ≠ V3 SE/KE beachten (B8) |
| `acceleration_enabled` / `acceleration_print` / `acceleration_wall_0` | Creality aus (500), Ko2 2500, SV 1000, N4/CC 10 000/5 000 | an, 12 000/5 000 (V3), 10 000 (K1M, CC2) | ja (Orca-Standardprozess) | beibehalten |
| `acceleration_travel` | Creality 500, Ko2 3000, Elegoo = Druck; Orca V3 12 000 | · → 5 000 fest (`CURA_UNTOUCHED`), erste Schicht 5 000 (`handover.py:868`) | Formelargument („nur beim Spiralisieren“) | = `acceleration_print` (Elegoo-Formel, Orca) |
| Jerk | Ko2/SV an (8/5), sonst aus | · (aus) | — | aus lassen (Firmware) |
| `material_max_flowrate` | 16 | 12–21 | — | **wirkungslos**: CuraEngine liest den Schlüssel nicht (0 Treffer in `CuraEngine.exe`); in `NOT_TAKEN_BY["cura"]` aufnehmen — gedeckelt wird ohnehin über die Tempi (`print_settings._within_flow`) |
| `material_flow` | 100 | 98 (PLA) | Material | beibehalten |
| `machine_gcode_flavor`, Maschinengrenzen | aus der Definition | fdmprinter „RepRap (Marlin/Sprinter)“, Grenzen fdmprinter | — | mit dem Start-Code aus der Definition übernehmen (nur Zeitschätzung) |

---

## 3. Was Solidon bei Cura nicht beachtet — und was mit dem STL verloren geht

1. **Die Maschine als Ganzes.** Solidon beschreibt die Maschine mit zwölf
   Werten (`_machine_keys`, `handover.py:901–960`): Bauraum, Düse, Bett,
   Nullpunkt, Nahtpunkt, Beschleunigungsschalter. Es fehlen Start- und
   End-G-Code, Firmware-Art, Maschinengrenzen, der Extruderzug des Druckers
   (`creality_base_extruder_0` statt `fdmextruder`). `machine_missing`
   meldet das für Cura bewusst nicht (`handover.py:357`, „Bauart, kein
   Mangel“) — für die erste Schicht ist es einer (Befund B1).
2. **Werte, die nur über Formeln der Definition entstehen.** Was Creality,
   Elegoo und Sovol per `value` setzen (`infill_before_walls`,
   `minimum_support_area`, Schnittstellenmuster, `retraction_combing_max_distance`,
   `travel_avoid_supports`, `acceleration_travel`, erste-Schicht-Beschleunigung
   …), erreicht CuraEngine nie; ohne Solidon-Zeile gilt `fdmprinter`.
   Solidons eigene Nachrechnung (`_cura_dependants`) bildet nur die
   **fdmprinter**-Formeln nach, nicht die des Druckers.
3. **Blätter statt Eltern.** CuraEngine liest nur Blatt-Einstellungen. Belegt
   am Programm (Zeichenkettensuche in `CuraEngine.exe`): `support_interface_pattern`,
   `support_infill_rate`, `acceleration_layer_0` kommen darin nicht vor,
   `support_roof_pattern`, `support_line_distance`,
   `acceleration_print_layer_0` schon. Solidon schreibt die Blätter bei
   Beschleunigung und Linienabstand richtig mit; beim Schnittstellenmuster
   gar nicht. `material_max_flowrate` liest CuraEngine überhaupt nicht.
4. **Objekteinstellungen.** Cura bekommt alle Teile als **ein** STL
   (`writer.py:1294–1321`, `_cura_assembly`). Verloren gehen:
   - die **Stützsperre** (`support.block_channels`) — machbar als eigenes
     Netz mit `anti_overhang_mesh=true` (gemessen, § 1.5);
   - **Stützen je Teil**: `support_enable` und `support_angle` sind in Cura
     `settable_per_mesh = true`. Ein Satz wie der Minigolf-Satz bekommt heute
     Stützen für alle Teile, sobald eines sie braucht; mit `-l teil_n.stl -s
     support_enable=false` bekämen nur die Teile Stützen, die sie brauchen;
   - „Stütze nur hier“ (`support_mesh=true`) für gezielte Stützen;
   - Brim je Teil (`advise.for_part`) — **nicht** machbar: `adhesion_type`,
     `brim_width` sind in Cura `settable_per_mesh = false`. Der heutige
     Befund „unerfüllt“ ist hier richtig.
5. **Das Fensterprofil.** Beim Weg „Öffnen“ erreicht die `.curaprofile` die
   meisten Cura-Nutzer nicht (§ 0.2) — sie drucken mit Curas eigenem Profil,
   ohne Solidons Werte.
6. **Rückmeldung.** CuraEngine schreibt im Konsolenbetrieb Platzhalter in den
   Kopf; Solidon zeigt für Cura keinen Materialverbrauch (`filament_g =
   null`). Die Gegenprobe über `unknown_keys` prüft nur Schlüsselnamen, nicht
   ob der Schlüssel gelesen wird (`material_max_flowrate` besteht sie).

---

## 4. Recherche — Quellen

Gelesen (Primärquellen):

- CuraEngine, `src/communication/CommandLine.cpp` (Hauptzweig):
  `loadJSONSettings` liest `default_value`, `value` nur mit
  `--force-read-nondefault`; `inherits` über Suchpfade
  (`CURA_ENGINE_SEARCH_PATH`, `-d`); `-l` setzt `last_settings` auf das
  zuletzt geladene Netz, danach folgende `-s` gelten je Netz. —
  https://github.com/Ultimaker/CuraEngine/blob/main/src/communication/CommandLine.cpp
- Cura 5.13, `plugins/CuraEngineBackend/StartSliceJob.py` (lokal,
  gleichlautend https://github.com/Ultimaker/Cura/blob/main/plugins/CuraEngineBackend/StartSliceJob.py):
  das Fenster schickt alle ausgewerteten Werte, ersetzt Start-/End-Code-Platzhalter
  und schaltet `material_bed_temp_prepend`/`material_print_temp_prepend` ab,
  wenn der Start-Code sie enthält.
- Cura 5.13, `cura/Settings/CuraContainerRegistry.py` (lokal;
  https://github.com/Ultimaker/Cura/blob/main/cura/Settings/CuraContainerRegistry.py):
  Profilimport, Ablehnung bzw. Unsichtbarkeit bei unpassender `quality_type`.
- Cura 5.13, `plugins/XmlMaterialProfile/XmlMaterialProfile.py` (lokal):
  Zuordnung der Material-XML-Schlüssel (`print temperature` →
  `default_material_print_temperature` usw.).
- `fdmprinter.def.json` (lokal; https://github.com/Ultimaker/Cura/blob/main/resources/definitions/fdmprinter.def.json):
  Beschreibungen, u. a. `support_angle` („At a value of 0° all overhangs are
  supported, 90° will not provide any support“), `infill_before_walls`
  („the infill pattern might sometimes show through the surface“),
  `wall_overhang_angle`, `wall_overhang_speed_factors`,
  `minimum_support_area`, `support_interface_density`,
  `material_*_temp_prepend`, `speed_travel_layer_0`.
- Druckerdefinitionen, Qualitäten, Varianten, Materialien der Installation
  (Pfade in § 2); Autoren in `metadata.author` (§ 0.3).
- OrcaSlicer-Bestand (Werksprofile Creality, lokal):
  `C:\Program Files\OrcaSlicer\resources\profiles\Creality\process\0.20mm Standard @Creality Ender3V3 0.4 nozzle.json`
  (`support_threshold_angle 30`, `initial_layer_acceleration 500`,
  `initial_layer_line_width 0.5`, Überhangtempo 50/30/10, Schnittstelle 0,5 mm
  Abstand, Stütze 150/80 mm/s), dasselbe für `…Ender3V3SE 0.4.json` (2500 /
  500 / 0,46 / 30 mm/s) und `…Ender3V3KE.json` (5000 / 1000 / 125 % / 50 mm/s).
- Cura-Versionshinweise, https://github.com/Ultimaker/Cura/releases: 5.12.0
  „Overhanging wall speed was previously applied too aggressively“;
  5.14.0-alpha.0 „Custom GCode parts are now processed in the engine“ — ab
  5.14 könnte CuraEngine die Platzhalter selbst ersetzen; Solidons eigene
  Ersetzung bliebe damit verträglich.

Nur als Suchauszug gesehen (Seite lädt per Skript, nicht direkt lesbar —
daher keine Tatsachenaussage darauf gestützt):

- UltiMaker Support, „UltiMaker Cura – Support settings“,
  https://support.ultimaker.com/s/article/1667417606331 — laut Auszug: 40°
  gilt als zuverlässig, ab etwa 55–60° tragen sich die Bahnen selbst.
- Gemeinschaftsbeiträge zu „Infill before walls“:
  https://community.ultimaker.com/topic/27777-infill-showing-through-walls/ ;
  Überhangtempo: https://www.thingiverse.com/thing:6975650 („Overhanging
  Wall Angle Tests [Cura 5.10 Overhang]“, UltiMaker).

Eigene Messungen: § 1 und `cura-probe\` (Probe-Skripte `probe.py`,
`angles.py`, Ergebnisse `ender3v3_pla\…`, `angles_ender3v3.log`).

---

## 5. Befunde, nach Priorität

### B1 — druckentscheidend: kein Start-/End-G-Code des Druckers

- **Fundstelle:** `app/core/export/handover.py:2293–2295` (`-j` immer
  `fdmprinter`), `handover.py:901–960` (`_machine_keys` ohne Start-Code),
  `handover.py:357` (`machine_missing` schweigt für Cura),
  `app/ui/print_settings_dialog.py:3954–3966`.
- **Cura:** `machine_start_gcode` je Drucker — `creality_ender3v3se.def.json`
  (`M420 S1`, zwei Spüllinien auf 0,28 mm), `creality_k1max.def.json`
  (`START_PRINT EXTRUDER_TEMP={…} BED_TEMP={…}`), `anycubic_kobra2.def.json`
  (Spüllinie 50 mm), `sovol_sv06.def.json` (`M420 S1`, Spüllinien),
  `elegoo_centauri_carbon.def.json` (`M729` Düsenreinigung, Pressure Advance,
  Spüllinie); End-Code je Drucker (K1 Max `END_PRINT`).
- **Solidon:** `fdmprinter`: `G28` / `G1 Z15` / `G1 F200 E3` — 3 mm Filament in
  15 mm Höhe, kein Bettnetz, keine Spüllinie; K1 Max ohne `START_PRINT`.
- **Quelle:** Probe `ender3v3_pla\vorschlaege\solidon.gcode`; `CommandLine.cpp`;
  `StartSliceJob.py`.
- **Änderung:**
  1. Druckerprofil um die Cura-Definition ergänzen (`printers.toml`, z. B.
     `cura_definition = "creality_ender3v3se"`), sonst über
     `slicer_profiles.printer_for` auf die Definitionstitel zuordnen.
  2. `machine_start_gcode`, `machine_end_gcode`, `machine_gcode_flavor` aus
     der Erbkette lesen (`default_value`; `_cura_definition_values` kann das)
     und **als eigene Argumente** in `_command` anhängen — nicht über
     `solidon_cura.txt`, deren Zeilenformat und `_without_line_break` keine
     Zeilenumbrüche tragen. Gemessen: ein mehrzeiliges `-s
     machine_start_gcode=…` kommt unverändert im G-Code an
     (`ender3v3_pla\standard\start_test.gcode`).
  3. Platzhalter `{schlüssel}` und `{schlüssel, n}` durch Solidons
     übergebene Werte ersetzen — reine Textersetzung, kein Auswerter (Regel
     10); ein unbekannter Platzhalter hält an und meldet (Regel 21).
  4. `material_bed_temp_prepend` / `material_print_temp_prepend = false`,
     sobald der Start-Code die Temperatur-Platzhalter enthält — dieselbe Regel
     wie im Fenster. Gemessen: ohne das stehen `M190`/`M109` doppelt.
  5. Ohne passende Definition (Ender-3 V3 CoreXZ, Centauri Carbon 2, Prusa,
     Bambu) einen Befund zeigen („ohne Start-Code des Herstellers: keine
     Spüllinie, kein Bettnetz“) statt still `fdmprinter`.
  - Test: G-Code-Kopf der Probe enthält `M420 S1` (SE) bzw. `START_PRINT
    EXTRUDER_TEMP=215 BED_TEMP=60` (K1 Max), kein `{`, genau ein `M190`.

### B2 — druckentscheidend: erste Schicht mit Druckbeschleunigung

- **Fundstelle:** `app/core/export/slicer_keys.py:588–610`
  (`CURA_MIRRORED["acceleration_print"]` → `acceleration_layer_0`,
  `acceleration_print_layer_0`, `acceleration_skirt_brim`);
  `handover.py:868` (`acceleration_travel_layer_0 = 5000`).
- **Cura:** `creality_base` Beschleunigung aus (500), `elegoo_base`
  `acceleration_layer_0 = 500`, `elegoo_centauri_carbon` 1000, Kobra 2 2500,
  SV06 1000. Werksslicer (Orca/Creality Print): V3 500, V3 SE 500, V3 KE 1000.
- **Solidon:** 12 000 (Ender-3 V3), 10 000 (K1 Max, CC2), 8 000 (SV06),
  6 000 (N4) — im G-Code `;LAYER:0 … M204 S12000` vor dem Skirt.
- **Quelle:** Probe-G-Code; Definitionen; Orca-Prozessdateien (§ 4).
- **Änderung:** eigenes Feld `PrinterProfile.first_layer_acceleration`
  (Werte aus Orca `initial_layer_acceleration` je Drucker, Vorgabe 500) und
  in der Cura-Tabelle eine eigene Zeile auf `acceleration_print_layer_0`,
  `acceleration_skirt_brim`, `raft_base_acceleration`; die drei aus
  `CURA_MIRRORED["acceleration_print"]` streichen. Dasselbe Feld für Orca
  (`initial_layer_acceleration`) und PrusaSlicer
  (`first_layer_acceleration`) — dort schweigt Solidon heute, und der
  Herstellerwert gilt.

### B3 — druckentscheidend bei Stützen: feste 45°-Grenze

- **Fundstelle:** `app/core/knowledge/rules.py:41`, `app/core/types.py:1171`,
  `slicer_keys.py:532`, Analyse `advise.py:638–720`.
- **Cura:** Gemeinschaftsprofile 40–50° (SE/KE/K1M 45 über
  `atan(line_width/2/layer_height)`, Kobra 2/SV06 50, N4 45, CC 40);
  Werksslicer von Creality und Elegoo 60°.
- **Solidon:** 45° für jeden Drucker, jede Schichthöhe, jedes Material.
- **Messung:** Minigolf-Körper 23,8 m Stütze über 199 Schichten bei 45°,
  9,4 m / 12 Schichten bei 50°, 0 bei 60° (§ 1.2). **Zählrichtung richtig** —
  keine Umrechnung nötig.
- **Änderung:** Die Grenze je Drucker aus dem Werksslicer (so die zeitweise
  sichtbare Arbeitsbaumänderung `overhang_limit`) gilt für Cura unverändert.
  Für Drucker ohne Angabe nicht 45 fest, sondern Creality/Cura-Formel
  `floor(deg(atan(line_width / 2 / layer_height)))` — sie hängt am Modell
  (Schichthöhe) und ergibt 46° bei 0,2 mm, 59° bei 0,12 mm, 36° bei 0,28 mm.
  Die Analyse, die `support.style` vorschlägt, muss dieselbe Zahl nehmen, die
  übergeben wird (`advise` liest `profiles.for_process(...).overhang_limit_degrees`
  — beim Setzen prüfen, dass beide Wege dieselbe Quelle haben).

### B4 — Qualität: Stützen mit Innenwandtempo, dichter Ringschnittstelle, falscher Wandzahl

- **Fundstelle:** `slicer_keys.py:527` (`support_pattern` grid),
  `slicer_keys.py:665` (`speed_print` → `speed_support`),
  `handover.py:834` (Schnittstelle Linienabstand = Bahnbreite),
  `handover.py:840` (`support_wall_count`), `handover.py:874–877`
  (Schnittstelle = `speed_print / 1.5`), `handover.py:819–830` (Baum mit 15 %).
- **Cura:** `zigzag`; Schnittstelle `grid` 33 % (Creality) / `lines` 33 %
  (Elegoo); Stütze = Außenwandtempo (Creality); CC Schnittstelle 80 mm/s;
  Orca V3 Stütze 150, Schnittstelle 80 mm/s, 0,5 mm Lücke. Formel: 1 Wand bei
  `grid`; Baum ohne Füllung.
- **Solidon:** `grid` ohne Wand, `concentric` 100 %, Stütze 214 mm/s,
  Schnittstelle 143 mm/s (Ender-3 V3), Baum mit 15 % Füllung.
- **Änderung:** Für Cura `support_pattern` nicht setzen (verbundenes
  `zigzag`; der Grund „kippt“ ist an Orcas unverbundenem `rectilinear`
  gemessen) oder bei `grid` `support_wall_count = 1`;
  `support_roof_pattern = support_bottom_pattern = lines`,
  `support_roof_line_distance = support_bottom_line_distance = 3 × Bahnbreite`
  (33 %); `speed_support = min(speed_print, 150)`,
  `speed_support_roof/bottom/interface = min(speed_wall_0, 80)`; Baum:
  `support_line_distance = 0`, `support_wall_count = 1` (Formel).

### B5 — Qualität: Überhangwände ohne Tempo-Rücknahme

- **Fundstelle:** kein Eintrag in `CURA` (`slicer_keys.py:464–567`).
- **Cura:** `wall_overhang_angle = 90` (aus) in allen Profilen — dort mit
  90–180 mm/s Außenwand. Werksslicer Orca V3: Überhangtempo 50/30/10 mm/s.
- **Solidon:** Außenwand 200 mm/s (Ender-3 V3), 160 (N4, CC2); Überhänge
  ungebremst. Steigt die Stützgrenze auf 60° (B3), druckt der Minigolf-Körper
  seine 45–60°-Wände ohne Stütze mit voller Wandgeschwindigkeit und bei
  langen Schichten mit 50 % Lüfter.
- **Änderung:** `wall_overhang_angle` = 45 (bzw. Stützgrenze − 15°, nicht
  unter 30) und `wall_overhang_speed_factors` aus dem Werksprofil:
  `[round(100 · v / outer_wall_speed) for v in (overhang_2_4, overhang_3_4,
  overhang_4_4)]` — V3: `[25, 15, 5]`; ohne Werksangabe `[50, 25]`. Der
  Wert hängt am Modell (Überhang) und am Drucker (Tempo), nicht an einer
  Stufe.

### B6 — Qualität: Füllung vor den Wänden

- **Fundstelle:** kein Eintrag; CuraEngine nimmt `fdmprinter`
  `infill_before_walls = true` (gemessen: `FILL → WALL-INNER → WALL-OUTER`).
- **Cura:** `false` bei `creality_base`, `anycubic_kobra2`, `sovol_base`;
  `true` bei Elegoo. Beschreibung: „the infill pattern might sometimes show
  through the surface“.
- **Änderung:** `infill_before_walls = false` in die Cura-Tabelle (feste
  Zeile in `_for_speeds` oder `CURA_MIRRORED`-freie Konstante); für Elegoo
  vertretbar ebenso, weil Solidon drei Wände fährt.

### B7 — Qualität, erste Schicht: Leerfahrt 17 mm/s, schmale erste Bahn

- **Fundstelle:** `handover.py:878–880` (`speed_travel_layer_0` nach
  fdmprinter-Formel), `print_settings.py:216` (`first_layer_line_width =
  extrusion_width × 1,07`).
- **Cura:** Kobra 2 `speed_travel_layer_0 = speed_travel` (125);
  Creality 100–150; erste Bahn 115–150 % (Orca V3 0,5 mm, SE 0,46, KE 125 %;
  Cura SV06 150 %, N4 125 %, CC 130 %).
- **Solidon:** Kobra 2 16,9 mm/s Leerfahrt in Schicht 1 (20 × 120 / 142);
  erste Bahn 106,9 %.
- **Änderung:** `speed_travel_layer_0 = max(Formel, min(speed_travel, 100))`;
  erste Bahnbreite je Drucker aus dem Werksprofil (neues Feld wie die Tempi
  in `printers.toml`), ohne Angabe 1,15 × Bahnbreite.

### B8 — Qualität: „Ender-3 V3“ ist nicht Curas Ender-3 V3 SE/KE

- **Fundstelle:** `app/core/knowledge/data/printers.toml`
  (`[creality-ender3-v3]`: 12 000 mm/s², Füllung 500 mm/s).
- **Cura:** kennt nur V3 SE (`machine_max_acceleration_x = 2500`, Tempo 180)
  und V3 KE (8000, 300). Orca: SE 2500/500, KE 5000/1000.
- **Änderung:** eigene Einträge `creality-ender3-v3-se` und
  `creality-ender3-v3-ke` aus den Orca-Werksprozessen; sonst bekommt ein
  SE-Besitzer, der „Ender-3 V3“ wählt, die Werte eines CoreXZ-Druckers.

### B9 — Qualität/Bedienung: `.curaprofile` wird abgelehnt oder unsichtbar

- **Fundstelle:** `handover.py:3580–3589` (`definition = fdmprinter`,
  `quality_type` aus fdmprinter-Stufen → `draft`).
- **Cura:** Elegoo: „Quality type 'draft' is not compatible …“; Creality/Sovol
  0,4 mm/PLA: importiert, aber nicht sichtbar (`CuraContainerRegistry.py:506–515`).
- **Änderung:** die aktive Maschine aus `cura.cfg` (`[cura] active_machine`,
  wie `slicer_profiles._cura_loaded_materials` sie schon liest) →
  `machine_instances/<name>.global.cfg` → Definition → `quality_definition`;
  daraus die Qualitätsart mit der nächsten Schichthöhe **für Düse und
  Material dieser Maschine**. Ohne Auskunft einen Befund („Profil passt zu
  keinem eingerichteten Drucker“) statt einer Datei, die still verschwindet.

### B10 — Qualität: Stützsperre und Stützen je Teil über `-l`

- **Fundstelle:** `slicer_keys.py:910–920` (`NOT_TAKEN_BY["cura"]` mit
  `support.block_channels`), `writer.py:1294–1321` (ein STL für alle Teile).
- **Messung:** `-l sperre.stl -s anti_overhang_mesh=true` → Stütze 18 476 → 0
  Bewegungen, Modell unverändert (§ 1.5).
- **Änderung:** Für Cura je Teil ein STL und die Sperre als eigenes STL
  (`_support_blocker` liefert das Netz schon); in `_command` nach jedem `-l`
  die Netzwerte: Sperre `anti_overhang_mesh=true`; Teil ohne Stützbedarf
  `support_enable=false`. `support.block_channels` aus `NOT_TAKEN_BY["cura"]`
  nehmen; `helpers_as_parts` bzw. ein neues Prädikat für „Hilfsteil als
  eigenes Netz“.

### B11 — Qualität: Fahrwege und Rückzug

- **Fundstelle:** keine Zeilen für `retraction_combing_max_distance`,
  `retraction_hop_only_when_collides`, `travel_avoid_supports`;
  `CURA_UNTOUCHED["acceleration_travel"]` (`slicer_keys.py:760`).
- **Cura:** Kämmen ohne Rückzug höchstens 30 mm (Creality), 5 mm (KE),
  9–14 mm (Elegoo); Stützen umfahren (Creality, Kobra 2); Fahrbeschleunigung
  = Druck (Elegoo), Orca V3 12 000.
- **Solidon:** unbegrenztes Kämmen ohne Rückzug, Z-Sprung bei jedem Rückzug,
  Fahrt 5 000 mm/s² bei 12 000 Druck.
- **Änderung:** `retraction_combing_max_distance = 30` (PETG 10),
  `retraction_hop_only_when_collides = true`, `travel_avoid_supports = true`,
  `acceleration_travel = acceleration_print`.

### B12 — Kosmetik

- `material_max_flowrate` (`slicer_keys.py:566`) wird von CuraEngine nicht
  gelesen → in `NOT_TAKEN_BY["cura"]` aufnehmen (die Oberfläche bietet sonst
  eine Attrappe an).
- `minimum_support_area = 2` (Creality) schreiben.
- `z_seam_corner = z_seam_corner_weighted` zu `sharpest_corner`/`back`.
- Kommentar in `_machine_keys` (`handover.py:909–915`): Die Bettmaße beheben
  `MINX:2.14748e+06` nicht — der Kopf ist im Konsolenbetrieb immer ein
  Platzhalter. Verbrauch aus dem Ende der Datei lesen (`;TIME_ELAPSED` gibt
  es; für Filament die `E`-Summe), damit der Bericht für Cura nicht leer
  bleibt.
- `support_bottom_distance` wird auch bei `buildplate` gespiegelt (Formel
  ergibt dort 0) — folgenlos.

---

## 6. Kurzfassung — die zehn wichtigsten Änderungen

1. **Start-/End-G-Code des Druckers** aus der Cura-Definition übergeben
   (Platzhalter selbst ersetzen, `*_temp_prepend=false`); heute druckt jeder
   Cura-Lauf mit `G28 / Z15 / E3` ohne Spüllinie und Bettnetz (B1).
2. **Erste Schicht mit eigener Beschleunigung** (Orca `initial_layer_acceleration`,
   Vorgabe 500) statt 12 000 aus `CURA_MIRRORED` (B2).
3. **Stützgrenze je Drucker** aus dem Werksslicer, für Cura ohne Umrechnung
   (Zählrichtung stimmt); ohne Angabe Formel `atan(Bahnbreite/2/Schichthöhe)`.
   Minigolf: 23,8 m Stütze bei 45°, 0 bei 60° (B3).
4. **Stützen wie im Werksprofil:** `zigzag` bzw. `grid` mit 1 Wand,
   Schnittstelle `lines` 33 %, Stütze ≤ 150 / Schnittstelle ≤ 80 mm/s, Baum
   ohne Füllung (B4).
5. **Überhangwände bremsen** (`wall_overhang_angle`, `wall_overhang_speed_factors`
   aus Orca-Überhangtempo), Pflicht sobald die Stützgrenze steigt (B5).
6. **`infill_before_walls = false`** (Creality/Anycubic/Sovol; gemessen:
   Füllung vor der Wand) (B6).
7. **Erste Schicht:** Leerfahrt nicht unter 100 mm/s (Kobra 2 heute 16,9),
   erste Bahn 115–125 % statt 107 % (B7).
8. **Stützsperre und Stützen je Teil** über `-l … -s anti_overhang_mesh=true`
   bzw. `support_enable` je Netz — gemessen wirksam (B10).
9. **`.curaprofile` an die aktive Cura-Maschine binden** — heute bei Elegoo
   abgelehnt, bei Creality/Sovol unsichtbar (B9).
10. **Ender-3 V3 SE/KE als eigene Drucker**; Fahrwege: Kämmen ≤ 30 mm,
    Z-Sprung nur über Teilen, Stützen umfahren (B8, B11).

Bericht: `F:\3D Druck\output\review\slicer-audit-2026-09-27\cura.md`,
Probe: `…\cura-probe\`.
