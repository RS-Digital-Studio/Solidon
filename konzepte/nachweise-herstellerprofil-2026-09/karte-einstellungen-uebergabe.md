# Karte: Druckeinstellungen und Slicer-Übergabe (Solidon, Stand 27.09.2026)

- **Wurzel:** `F:\3D Druck.minigolf\` (Worktree). Alle Pfade unten sind relativ dazu.
- **Stand:** HEAD `46fa73c17` plus uncommittete Änderungen vom 27.09. (`overhang_limit`, `match`-Sortierung) in `app/core/types.py`, `knowledge/print_settings.py`, `knowledge/profiles.py`, `knowledge/rules.py`, `knowledge/data/printers.toml`, `slice/advise.py`, `export/slicer_profiles.py`.
- **Zeilen:** gelten für diesen Arbeitsbaum.

- **Herkunft:** Ergebnis des Suchagenten (nur lesend, 27.09.2026), von der Hauptsitzung unverändert gesichert.

## Zusammenfassung

1. **Kein Feld weiß, woher sein Wert kommt.** `PrintSettings` (`types.py:1363`) hat 10 Gruppen mit 59 Feldern, und alle sind immer gefüllt. Nur `SlotOverride` kennt „nicht gesetzt“, und das gruppenweise (`None`). Was der Nutzer selbst gewählt hat, erkennt der Code heute nur am Vergleich mit `resolve()` (`_scene_profile_changed`, Dialog:3165).
2. **`resolve`** (`print_settings.py:194`) baut die Werte aus Stufe, Material und Drucker. `printers.toml` enthält schon abgeschriebene Herstellerwerte (Tempi, Leerfahrt, `flow_factor`, `overhang_limit`). Danach deckelt `_within_flow` die Tempi auf den Volumenstrom.
3. **Speichern:** `Document.print_settings = None` bedeutet „es gilt `resolve`“. Trotzdem schreiben drei Stellen die vollständig aufgelösten Werte ungefragt ins Projekt:
   - `_plate_job` (Dialog:6421), wenn noch keine Lager-Projektkennung existiert,
   - `MainWindow._inventory_settings` (`main_window.py:6975`) beim Filament-Zuweisen und beim 3MF-Export,
   - `history.restore` (`history.py:309`) mit den reinen Dataclass-Vorgaben `PrintSettings()`.
4. **Ältere Projekte:** Fehlende Felder bekommen die Dataclass-Vorgabe; nur die Lüfterkurve kommt aus dem Material (`serialise._group_from_data:779`). Migrationen gibt es für 3→4, 19→20, 20→21 und 21→22. `advise` bietet älteren Projekten Leerfahrt und Stützwinkel des Druckers an.
5. **Druckdialog:** Maschine, Prozess und Filament werden nur für die Orca-Familie gesucht. `_start_profile_search` (Dialog:3918) kehrt bei Prusa und Cura früh zurück. Die Wahl wird in `UiSettings` als Dateipfad gemerkt, das Filament zusätzlich je Material. Slot-Profile reisen als Namen im Projekt (`slot_profile_bindings`).
6. **`_choose_filament_profile` gibt es nicht.** Die Spule bekommt ihr Profil über `NewFilamentDialog._choose_slicer_profile` (`filament_picker.py:968`), das über `spool_slot` in `MaterialSlot.material` landet.
7. **Der Dialog zeigt nur Solidon-Werte.** Vom Hersteller erscheint nur der Name des Filamentprofils mit dem Knopf „Werte übernehmen“ (`_adopt_filament_values`). Auch der Spulendialog `FilamentOverrideDialog` zeigt Projektwerte.
8. **Rücklesen gibt es nur für Filamentprofile:** 18 Pfade (Orca), 18 (Prusa), 12 (Cura). Prozesswerte werden nicht zurückgelesen, und `MACHINE_READBACK` hat keinen Aufrufer.
9. **Wo das Rücklesen wirkt:** in `settings_for_slot` (`handover.py:1044`), aber nur für `slot.material`, nicht für das im Dialog zugeordnete Grundfilament (`setup.base_filament`).
10. **Orca heute:**
    - Maschinenprofil: vollständig aufgelöstes Herstellerprofil,
    - Prozessprofil: Herstellerbasis plus 45 Solidon-Zuordnungen,
    - Filamentprofil: Herstellerbasis plus 22 Solidon-Zuordnungen. Solidon gewinnt, außer bei einer Spule mit eigenem Profil.
11. **PrusaSlicer heute:** nur `--load solidon.ini` mit 63 Schlüsseln bei Vorgabewerten, dazu `Slic3r_PE.config` in der 3MF. Ein Hersteller-Druckerprofil oder -Prozess wird nie geladen, und es gibt keinen `start_gcode`; es gilt die Programmvorgabe von PrusaSlicer.
12. **CuraEngine heute:** `-j fdmprinter.def.json`, dazu `-s` mit Tabellenwerten, 14 Maschinenschlüsseln und abgeleiteten Werten. Der Start-G-Code kommt aus der Vorgabe von `fdmprinter`. Für das Cura-Fenster entsteht eine `.curaprofile`.
13. **Einlesen der Herstellerprofile ist schon gebaut** (`_PrusaStore`, `_cura_definition_values`, `resolve_profile`), wird bei der Übergabe an Prusa und Cura aber nicht genutzt.
14. **Einstellungen je Teil** betreffen nur die Haftung: `advise.for_part` → `object_keys` → `model_settings.config` bzw. `Slic3r_PE_model.config`. Cura bekommt ein STL und verliert sie.
15. **`advise` liest praktisch alle Prozesswerte:** Wandzahl, Bahnbreite, die fünf fördernden Tempi, `max_flow`, erste Schicht, Mindestschichtzeit, Beschleunigung. `combine`/`apply` schreiben übernommene Werte in `PrintSettings` bzw. in einen `SlotOverride`, und zwar jeweils die ganze Gruppe.
16. **Tests für „Solidon gewinnt“**, alle in `tests/test_print_settings.py`: `:2041`, `:1513`, `:3809`, `:4662`, `:4513`. Außerdem `tests/test_export.py:2709` und `:2689`.
17. **Tests für `profile_differences`** (`tests/test_print_settings.py`): `:3424`, `:3463`, `:3663`.
18. **Tests für `verify`** (`tests/test_print_settings.py`): `:1265` bis `:1303`, dazu `:3266`, `:5860`, `:5900`.

Vorgesehener Speicherort: `F:\3D Druck\output\review\slicer-audit-2026-09-27\karte-einstellungen-uebergabe.md`

## 0. Datenfluss im Überblick

```
printers.toml / print_settings.toml
  └─ knowledge/print_settings.resolve(profile, stufe)          → PrintSettings (voll)
Document.print_settings (None ⇒ resolve)                        types.py:2242
  └─ PrintSettingsDialog.settings  (Dialog:2608)
       ├─ Vorschläge: _AdviceWorker → handover.settings_for_slot → advise.advise/combine
       └─ _slice / _open_in_slicer → _plate_job → _PlateJob
            └─ _prepare_plate(s) → writer.write_assembly (3MF | STL)
                 ├─ project_settings.config  (handover.project_settings, nur Orca)
                 ├─ Slic3r_PE.config         (writer._plate_config, nur Prusa)
                 ├─ model_settings.config / Slic3r_PE_model.config (Teilwerte)
            └─ handover.slice_model → write_config (je Familie) → _command → Lauf
                 └─ verify_settings, profile_differences, … (Befunde)
```

## 1. Einstellungsmodell

### 1.1 `PrintSettings` und Untergruppen (`app/core/types.py`)

Das Modell „überschreibt, ersetzt nicht“ (Docstring `PrintSettings` :1366–1368). Das Wörterbuch `slicer_keys` sagt dasselbe (`slicer_keys.py:15–17`).

Literale:

| Typ | Zeile | Werte |
|---|---|---|
| `InfillPattern` | :1054 | |
| `SupportStyle` | :1055 | none, grid, tree |
| `SupportPlacement` | :1056 | |
| `SeamPosition` | :1057 | |
| `WallGenerator` | :1065 | |
| `AdhesionType` | :1066 | |
| `QualityPreset` | :1067 | draft, standard, fine, strong |
| `HandoverKind` | :1071 | slice, open |

Gruppen und Vorgaben:

| Klasse (Zeile) | Felder = Vorgabe |
|---|---|
| `LayerSettings` :1075 | layer_height 0.2 · first_layer_height 0.25 · line_width 0.42 · first_layer_line_width 0.45 |
| `ShellSettings` :1085 | wall_count 3 · top_layers 5 · bottom_layers 4 · outer_wall_first False · seam_position "aligned" · wall_generator "arachne" · precise_outer_wall False · ironing False |
| `InfillSettings` :1108 | density 0.15 · pattern "grid" · angle 45 |
| `TemperatureSettings` :1118 | nozzle 210 · nozzle_first_layer 215 · bed 60 · bed_first_layer 60 · chamber 0 |
| `CoolingSettings` :1129 | fan_speed 1.0 · minimum_fan_speed 1.0 · fan_below_layer_time 60 · bridge_fan_speed 1.0 · disable_first_layers 1 · minimum_layer_time 8 |
| `SpeedSettings` :1161 | outer_wall 40 · inner_wall 60 · infill 80 · top_surface 40 · first_layer 20 · travel 150 · bridge 25 · acceleration 8000 · outer_wall_acceleration 5000 |
| `SupportSettings` :1182 | style "none" · placement "everywhere" · threshold_angle = `OVERHANG_LIMIT_DEGREES` (45, `knowledge/rules.py:47`) · z_gap 0.2 · xy_gap 0.5 · density 0.15 · interface_layers 2 · block_channels False |
| `AdhesionSettings` :1212 | kind "skirt" · skirt_loops 2 · skirt_distance 3.0 · brim_width 5.0 · raft_layers 3 |
| `RetractionSettings` :1223 | length 0.8 · speed 35 · z_hop 0.2 · wipe True · avoid_crossing_walls True |
| `FilamentSettings` :1240 | diameter 1.75 · density 1.24 · flow_ratio 1.0 · colour "#4A90D9" · cost_per_kg 0 · max_flow 12 |
| `SlotOverride` :1262 | Identität: name, colour, material, material_type. Gruppen temperature, cooling, retraction, filament jeweils `\| None` (Gruppe ganz oder gar nicht). `empty` :1314, `key` :1319 |
| `SpoolBinding` :1327 | spool_identifier + Identität |
| `SlotProfileBinding` :1345 | profile_name + Identität |
| `PrintSettings` :1363 | id "standard" · title "Standard" · quality "standard" · handover "slice" · 10 Gruppen · slot_overrides () · slot_profiles () · spool_bindings () · inventory_project_id "" · slot_profile_bindings None (None = alte Positionsfolge) · Eigenschaft `wall_thickness` :1426 |
| `SettingAdvice` :1433 | path, value, was, reason, severity |
| `Document.print_settings` :2242 | `None` = „noch nichts eingestellt, es gilt die Auflösung“ |

**Herstellerwerte in Solidons Druckerprofil.** `PrinterProfile` (:726) trägt:
- `travel_speed` (:786),
- `speed_outer_wall` … `speed_bridge`, `acceleration`, `outer_wall_acceleration` (:804–811),
- `flow_factor` (:812),
- `overhang_limit` (:819).

Gelesen wird das in `knowledge/profiles.py:_printer_from_table` (:94, Felder :151–157, `PRINTER_PACE_FIELDS` :166). Die Daten stehen in `knowledge/data/printers.toml` (Kopfkommentar :19–35). Von 18 Einträgen tragen 15 Tempi und `overhang_limit`, 8 einen `flow_factor`. Beispiel `[centauri-carbon-2]` :50–72.

Weitere Eigenschaften:
- `Profile.overhang_limit_degrees` (:958): Kalibrierung vor Drucker vor 45°.
- `Profile.minimum_wall_thickness` (:936).
- `profiles.for_process` (:704) setzt `layer_height` und `extrusion_width` des Druckers aus den PrintSettings. `Session.profile` (`ui/session.py:1742`) benutzt das, die Analyse hängt also an den Einstellungswerten.

### 1.2 `print_settings.resolve` (`app/core/knowledge/print_settings.py`)

Hilfsteile:
- **Tabellen laden:** `_load` :97 liest die mitgelieferte `data/print_settings.toml` und legt `&lt;Nutzerdaten&gt;/profiles/print_settings.toml` je Eintrag darüber. `_all` :118, `reload` :130, `quality_presets` :136, `_quality_table` :141.
- **Materialtabelle:** `_material_table` :180. Ein unbekanntes Material ergibt `{}`, also Dataclass-Vorgaben; `has_material` :152.
- **Datei `print_settings.toml`:** `[quality.draft|standard|fine|strong]` :30/:49/:68/:88, `[material.pla|petg|petg-cf|asa|abs|tpu-95a]` :120/:140/:162/:184/:204/:226.

`resolve(profile, quality)` :194–283, Feld für Feld:

| Ziel | Quelle heute | Zeilen |
|---|---|---|
| layers.layer_height, first_layer_height | Stufe × Düse/0,4 (`REFERENCE_NOZZLE` :59), gedeckelt auf 0,75·Düse (`MAX_LAYER_RATIO` :63). Resin: `printer.layer_height` | :200–214 |
| layers.line_width | `printer.extrusion_width` (Düse·1,05) | :215 |
| layers.first_layer_line_width | round(extrusion_width·1,07, 3) | :216 |
| shell.wall_count, top_layers, bottom_layers | Stufe; übrige Schalenfelder Dataclass-Vorgabe | :228–232 |
| infill.density, pattern | Stufe (`_pattern` :394); angle Vorgabe | :233–236 |
| temperature.* | Material, gedeckelt auf die Druckergrenzen; Kammer nur bei geschlossenem Bauraum (`_temperatures` :375) | :237 |
| cooling.fan_speed, bridge_fan_speed, disable_first_layers | Material | :239–242 |
| cooling.minimum_fan_speed, fan_below_layer_time | `fan_curve` :357 (Material) | :240 |
| cooling.minimum_layer_time | **Stufe** | :243 |
| speed.outer_wall … bridge, acceleration, outer_wall_acceleration | `_paced` :333: Stufenwert oder Druckertempo × (Stufe/Standard), gerundet auf 0,1 | :245–255 |
| speed.travel | `printer.travel_speed`, sonst Vorgabe 150 | :258 |
| support.threshold_angle | `profile.overhang_limit_degrees`; übrige Stützfelder Vorgabe | :265 |
| adhesion.kind | Material (`_adhesion` :405); Maße Vorgabe | :266 |
| retraction.length, speed, z_hop | Material; wipe und avoid_crossing Vorgabe | :267–271 |
| filament.density, flow_ratio, colour | Material | :272–275 |
| filament.max_flow | Material × `flow_factor`, nur für PLA (`HOTEND_FLOW_MATERIAL` :84) | :279–280 |
| filament.diameter, cost_per_kg | Vorgabe | — |
| danach | `_within_flow` :312 deckelt die fünf fördernden Tempi (`FLOW_BOUND_SPEEDS` :68) auf `flow_speed_limit` :298 (`bead_area` :286) | :283 |

Weitere Funktionen: `material_temperature` :162 (ungedeckelter Materialwunsch für `advise.warnings_for`), `GROUPS` :421, `read_path` :435, `with_path` :454 (erzeugt eine neue unveränderliche Kopie; prüft den Pfad über `read_path`).

### 1.3 Speichern und Laden

**Speichern:** `scene/serialise.py:print_settings_to_data` :927 schreibt alle Gruppen vollständig (`_SETTING_GROUPS` :765). Dazu kommen `slot_profiles`, `slot_profile_bindings` (None bleibt None), `slot_overrides` (`_override_to_data` :812, nur gesetzte Gruppen), `spool_bindings`, `inventory_project_id` und `handover`. `document_to_data` :993 legt es unter `"print_settings"` ab (:1019).

**Laden:** `print_settings_from_data` :958:
- `_group_from_data` :779 übernimmt nur bekannte Felder. Was fehlt, bekommt die **Dataclass-Vorgabe**; nur die Lüfterkurve wird aus dem Material ergänzt (:794–797 über `print_settings.fan_curve`).
- `handover` wird zu "open" oder sonst "slice" (:977).
- `_override_from_data` :837 ergänzt die Kurve aus der eigenen Materialart der Spule.

`document_from_data` :1096 übergibt `profiles.material_for(printer, material)` als Material (:1124–1134).

**Ablauf in `scene/project.py`:**
- `save` :1363 → `document_to_data` (:1462) → Schemaprüfung (:1463).
- `load` :1595 → `_validate_project_schema` (:1627) → `migrate` (:1628) → Schemaprüfung (:1641) → `document_from_data` (:1642).
- Die Formprüfung steht in `_validate_print_settings` :779 (Steuerzeichen) und `_validate_current_project_schema` :1067 (Block :1137–1185).

**Migrationen** (`scene/migrations.py`, `FORMAT_VERSION = 35` :29, Kette `MIGRATIONS` :891, `migrate` :929):

| Schritt | Funktion | Wirkung |
|---|---|---|
| 3→4 | `_add_print_settings` :67 | `print_settings: None` |
| 19→20 | `_keep_explicit_choices` :416 | Slot-Übersteuerungen bekommen `material`/`material_type` = None (:425–429). Das sind Altwerte ohne Identität. |
| 20→21 | `_add_spool_bindings` :548 | |
| 21→22 | `_add_slot_profile_bindings` :557 | `slot_profile_bindings: None`, also alte Positionsfolge |

Ein eigener Formatschritt für die Lüfterkurve existiert nicht. Die Begründung steht in `.claude/rules/dateiformat.md:495–503`.

### 1.4 Wer bei `None` auflöst und wer implizit schreibt

**Auflösen bei `None`:** `document.print_settings or resolve(...)` steht an diesen Stellen:
- `ui/main_window.py:effective_print_settings` :19807 (Statuszeile :19852, Filamentpanel :19524, Prüfbericht :19543),
- `_edit_filament_settings` :7299,
- `_compare_support` :7520, `_compare_totals` :7547,
- Abstands-Vorbelegung :19261–19263,
- `ui/session.py:split_margin` :3456,
- `core/agent/analysis.py` :89,
- `print_settings_dialog.settings_for_export` :1096–1100 und Dialogaufbau :2608–2611.

**Schreiben ins Projekt:**
- `Session.set_print_settings` :2766, wird im Hauptfenster nur bei `dialog.has_changes()` aufgerufen (`main_window.py:7273`).
- **Implizit ohne Nutzerwahl:**
  - `PrintSettingsDialog._plate_job` :6421–6423 bei jeder Übergabe, wenn die Lager-Projektkennung fehlt,
  - `MainWindow._inventory_settings` :6975 (aufgerufen von :7207 Filament zuweisen, :7728 3MF-Export, :17342, `_spool_change` :6987),
  - `scene/history.py:restore` :309–311 mit `document.print_settings or PrintSettings()`, also den nicht aufgelösten Dataclass-Vorgaben,
  - `Session._bind_filament_profiles` :2742 (bindet alte Positionen).
- `ingest/plan.py:521` behandelt `print_settings is not None` als Nutzerentscheidung.

### 1.5 Sonderwege für ältere Projekte

- **Fehlende neue Felder** werden zu Dataclass-Vorgaben, nicht zu Werten aus `resolve` (`serialise.py:961`). Ausnahme ist die Lüfterkurve (`_group_from_data` :779, `_override_from_data` :837). Tests: `tests/test_print_settings.py:1026`, `:1048`, `:1096`.
- **`advise._from_machine`** bietet älteren Projekten Leerfahrt (:425–442) und Stützwinkel (:444–466) des Druckers an. Tests: `tests/test_advise.py:606`, `:675`.
- **Alte Spulenwerte ohne Materialidentität:**
  - `handover.unbound_override_for` :1161,
  - Dialogknopf „Alte Filamentwerte übernehmen“ (`FilamentOverrideDialog._take_legacy_values` :1485),
  - Befund `slicer.overrides_unassigned` in `unreachable_overrides` :1083–1107.
- **Positionsgebundene Slot-Profile:**
  - `slot_profile_bindings is None` → `configured_slots` :1275, `_profiles_for` :4636–4645,
  - Umstellung in `Session._bind_filament_profiles` :2742, `handover.bind_slot_profiles` :1248,
  - Auswahl-Export: `_ExportWorker._profiles_for_selection` (`main_window.py:1247`).
- **Beschriftung statt Name** bei alten Slot-Wahlen: `_filament_index` :4482.
- **UiSettings „von früher“:** leere `slicer_profile_printer`/`slicer_profile_slicer` werden nicht verglichen (`ui/settings.py:90–118`, `remembered_setup` :1139–1152).
- **`handover`-Feld fehlt:** es gilt "slice" (`types.py:1375`, `serialise.py:977`).

## 2. Druckdialog (`app/ui/print_settings_dialog.py`)

### 2.1 Aufbau, Anfangswerte, Übernahme ins Projekt

- `PrintSettingsDialog` :2458, `__init__` :2506.
- Startwert: `self.settings = stored or resolve(session.profile, _remembered_quality())` (:2608–2611, `_remembered_quality` :2692 aus `UiSettings.print_quality`).
- `_opened_with` :2617, `has_changes` :2674.
- Aufruf aus `MainWindow.action_print_settings` (`main_window.py:7225`). Nach `exec()` wird `set_print_settings` nur bei Änderung aufgerufen (:7273); die Stufe geht nach `UiSettings` (:7275).
- Kopfzeile `_build_head` :2697:
  - Stufe,
  - Drucker `printer_choice`,
  - Düse (`_nozzle_changed` :3117 → `profiles.save_printer`),
  - Düsenzahl,
  - Materialanzeige (`show_materials` :2939, `_materials_of` :2968),
  - „Werte mitgeben“ (`share_settings`, `_share_toggled` :2922 → `UiSettings.print_settings_in_files` :207).

### 2.2 Slicer wählen und merken

- `_remembered_slicer` :5141 (`discover.remembered_path("slicer")`).
- `_start_slicer_search` :5176 → `_SlicerWorker` :2425 → `_slicers_found` :5196 → `_choose_slicer` :5164.
- Ausdrückliche Wahl: `_slicer_chosen` :5294 → `discover.remember_path`.
- `_fill_slicer_choice` :5268, `recheck_slicer` :5313.

### 2.3 Maschine, Prozess und Filament (nur Orca-Familie)

`_start_profile_search` :3918:
- `_clear_profile_choices` :3892.
- **Prusa: früher Rücksprung** (:3943–3953), Hinweis „Solidon schreibt eine vollständige Konfiguration“.
- **Cura: früher Rücksprung** (:3954–3966), Hinweis „Solidon beschreibt die Maschine selbst“.
- Sonst `_ProfileWorker` :2390 → `slicer_profiles.find_profiles(kinds=("machine","process","filament"))` (:2409–2416).

`_profiles_found` :4004:
- Liste: `_machines_worth_showing` :4171 (`printer_for` → Düse → alle).
- Vorwahl: aktuelle Wahl → `UiSettings.slicer_machine_profile` → `slicer_profiles.match` (`slicer_profiles.py:2183`) → der einzige Eintrag. Kein Rückfall auf den ersten Eintrag (:4058–4084).

`_fill_processes` :4143:
- `slicer_profiles.processes(profiles, machine)`.
- Vorwahl: `UiSettings.slicer_base_process` → Prozess aus `match` → `machine.default_process` → **Index 0** (`max(index, 0)` :4168).

`_fill_filaments` :4273:
- Liste aus `_filaments_worth_showing` :4232 (mit Maschine `filaments(..., machine)`, ohne Maschine Herstellerpräfix).
- Wunsch: `UiSettings.slicer_filament_per_material.get(material, slicer_base_filament)` (:4327, Pfad oder Titel) → `match_filament` (`slicer_profiles.py:2118`) → erstes Profil gleicher Materialart über `type_of` (:4351–4362) → keines.
- `_remember_filament_profile` :4380 setzt `_filament_profile` (Pfad), `_filament_source` und `_filament_title` und schaltet „Werte übernehmen“ frei.
- `_forget_filament_profile` :4395.

`_machine_chosen` :4134, `_refill_slicer_profiles` :3227 (nach Druckerwechsel), `_profile_gap` :4912.

### 2.4 Merken

**`_remember_slicer_choice(require_machine)`** :6168. Aufgerufen in `_open_in_slicer` :6272, `_slice` :6346 und `_settle` :6864. Es schreibt in `UiSettings` (`ui/settings.py`):

| Feld | Zeile | Inhalt |
|---|---|---|
| `slicer_machine_profile` | :80 | Pfad |
| `slicer_base_process` | :83 | Pfad |
| `slicer_base_filament` | :86 | Pfad |
| `slicer_profile_printer` | :90 | |
| `slicer_profile_slicer` | :99 | |
| `slicer_filament_per_material[material]` | :119 | nur wenn ein Filament zugeordnet ist |

Sind alle Auswahlfelder leer (Prusa/Cura), wird nichts gemerkt (:6190–6194).

**Verbraucher:**
- `_current_setup` :6219 baut `handover.SlicerSetup` aus den Auswahlfeldern.
- `_start_advice` :5761–5771 baut ein eigenes `SlicerSetup`.
- `remembered_setup` :1103 für den Export (`main_window._ExportWorker._assembly` :1288).

### 2.5 Filamentprofile je Slot

**Anzeige und Wahl im Dialog:**
- `_build_slot_rows` :4411 legt Zeilen erst ab 2 Slots an.
- `_plate_slots` :4595 (`threemf.merge_slots`).
- `_profiles_for` :4619 liest `slot_profile_bindings` nach Identität, sonst alte Positionen.
- `_slot_filament_chosen` :4647 schreibt **Namen** in `slot_profiles` und `SlotProfileBinding` (:4675–4692).
- `_profile_name` :4466, `_filament_index` :4482.

**Wahl an der Spule:**
- `NewFilamentDialog._choose_slicer_profile` (`ui/filament_picker.py:968`) → `slicer_filaments()` :486 (`find_profiles(kinds=("filament",))`, auch für Prusa und Cura) → `CatalogueFilament.slicer_profile`.
- `spool_slot` :298 → `MaterialSlot.material` (Name).
- Eine Funktion `_choose_filament_profile` existiert nicht.

**In der Übergabe:** `_plate_job` :6424–6430 → `_PlateJob.slot_profiles`; `_slots_with_profiles` :1691 → `handover.with_slot_profiles` :1286.

### 2.6 Angezeigte Werte und ihre Herkunft

- **Felder:** Tabelle `FIELDS` :301–1038, 59 Einträge (je Modellfeld eines).
  - 7 davon mit `front=True`: `layers.layer_height`, `shell.wall_count`, `infill.density`, `infill.pattern`, `temperature.nozzle`, `temperature.bed`, `support.style`. Aufgebaut in `_build_front` :3296.
  - Übrige in Reitern je Gruppe (`_build_tabs` :3500).
- **Werte:** `_load_into_editors` :5399 liest ausschließlich `self.settings` (Solidon-Werte). Rückweg: `_collect` :5411, `_editor_changed` :5420.
- **Ausgrauen je Slicer:** `_mark_fields_this_slicer_ignores` :4931 (`slicer_keys.takes`, `limitation`).
- **Herstellerseite:** nur `filament_shown` (Name, :3698) und Knopf `adopt_filament` (:3700). Keine Anzeige von Maschinen- oder Prozesswerten des Herstellers.
- **Spulendialog `FilamentOverrideDialog`** :1336 (geöffnet von `main_window._edit_filament_settings` :7282): Ausgangswerte sind die **Projektwerte** (`source = own_section or getattr(settings, group)` :1440), nicht `settings_for_slot`. Rückgabe `override()` :1519 gruppenweise. `FILAMENT_GROUPS`/`FILAMENT_FIELDS` :1039–1044.

### 2.7 Stufe und Drucker wechseln

- `_quality_changed` :5428 → `_resolved` :3261: neu `resolve`, nur Slot-Zuordnung und Spulenfelder bleiben.
- `_scene_profile_changed` :3165: Was vom **alten** `resolve` abweicht, gilt als Nutzerwahl und überlebt; der Rest wird neu aufgelöst (:3194–3220).

### 2.8 „Werte übernehmen“

`_adopt_filament_values` :4705 → `slicer_profiles.filament_values(source, roots)` → `print_settings.with_path` auf die **Projekt**-Einstellungen. Nur auf Klick.

### 2.9 Vorschläge

**Auslösen:**
- `_refresh_advice` :5635. Ohne Körper sofort `advise.advise(self.settings, profile, slice_result)` (:5671).
- Kontexte: `_analysis_context` :5678, `_advice_context` :5704 (enthält Maschine, Prozess und Filament).
- `_start_advice` :5740.

**`_AdviceWorker`** :1820, `_calculate` :1879:
1. Je Körper und je benutztem Slot: `effective = handover.settings_for_slot(self.settings, self.profile, slot, self.setup)` (:1908) und `profiles.for_process(material_profile, effective)`.
2. Schichtanalyse mit `self.settings.layers.layer_height/first_layer_height` (:1942–1952).
3. `advise.advise(effective, material_profile, result, …)` (:1957).
4. Aufteilen in gemeinsame Werte → `advise.combine(self.settings, common)` (:1988) und Filamentgruppen je Slot → `combine(groups[0][0], groups)` als `_TargetedAdvice` (:1805, :1989–2001).
5. Prusa/Cura: Filamentrat für Slot 2 und folgende wird als „unavailable“ markiert (:2002–2036).

**Anzeigen:** `_current_advice` :5451 (filtert `slicer_keys.takes`; `_BY_HAND_IN_THE_SLICER` :1796), `_show_advice` :6000, `_chosen_advice` :6100.

**Übernehmen:** `_apply_advice` :6115:
- gemeinsame Vorschläge → `advise.apply` (:6125),
- Filamentvorschläge → **ganze Gruppe** aus `entry.effective` → `handover.with_slot_override` (:6133–6150).

### 2.10 Übergabe auslösen

**„Slicen“:** `_slice` :6312
- Pflicht bei Orca: Maschine (:6326) und Prozess (:6340).
- `_may_hand_over` :6370, `_remember_handover("slice")`.
- `_plate_job` :6410 (**immer `with_settings=True`**) → `_PrepareAndSliceWorker` :2196.
- Je Platte `_prepare_plate` :1748 → `write_assembly(…, settings=local_settings, flavour, setup)`.
- `_comparison_for_job` :1622 (benutzt `settings_for_slot` und `settings_for_handover`), `prepare_usage`.
- `_SliceWorker.work` :2147 → `handover.slice_model` (:2154).

**„Im Slicer öffnen“:** `_open_in_slicer` :6247
- `with_settings = UiSettings.print_settings_in_files` (:6290) → `_OpenInSlicerWorker` :2237.
- Orca mit mehr als 1 Platte: `_open_as_one_project` :2306 → `_prepare_plates` :1709.
- Sonst `_prepare_plate` → `handover.cura_profile_beside` (:2285–2291) → `handover.open_in_slicer` :3468.

**Datenklassen:** `PlateRun` :1545, `_PlateJob` :1580 (objects, plates, folder, name, setup, settings, profile, slot_profiles, with_settings, scene, document, cancelled), `ProjectRun` :1682, `SliceComparison` :1611.

`_plate_run` :6445 ruft nur noch Testcode auf.

## 3. Rücklesen aus Herstellerprofilen (`app/core/export/slicer_profiles.py`)

### 3.1 Finden und Auflösen

**Finden:**
- `find_profiles` :1374 verzweigt nach Familie: Prusa → `_prusa_profiles` :1714; Cura → `_cura_profiles` :1033; Orca → JSON-Durchlauf plus Erbkette für `compatible_printers`.
- `DEFAULT_KINDS` :1371, `profile_roots` :1526, `install_root` :141, `user_roots` :202.

**Prusa:**
- `_PrusaStore` :1591 (`find_parent` :1616, `read` :1637, `resolve` :1676). Erbt innerhalb des Bündels; eigene INI-Dateien dürfen Herstellerbasen nutzen.
- `prusa_config` :298, `_prusa_presets` :354, `_prusa_configured` :365.

**Cura:**
- `_CURA_DIRS` :1013: `definitions/*.def.json` = machine, `quality(_changes)/*.inst.cfg` = process, `materials/*.xml.fdm_material` = filament.
- Leser: `_read_cura_machine` :1121, `_read_cura_process` :1163, `_read_cura_material` :1203.
- Werte: `_cura_definition_values` :1244 (Vererbung als Daten, Formeln werden übersprungen), `_CURA_MATERIAL_KEYS` :1300, `_cura_material_values` :1310.
- Weitere: `cura_setting_version` :591, `cura_quality_types` :613.

**Allgemein:**
- `resolve_values` :1832 (Endungen je Format; Orca über `_chain` :1917 ohne `DESCRIBING_KEYS` :1480).
- `resolve_profile` :1759 (Prusa-Abschnitt über `_PrusaStore`).
- `binding` :1884, `profile_by_name` :1750.

**Zuordnung:**
- `match` :2183, `match_filament` :2118, `type_of` :2166, `processes` :2098, `filaments` :2108, `compatible_with` :2027.
- `printer_for` :856, `machine_with_nozzle` :874, `chosen_machine` :243, `configured_filaments` :412.
- In `handover.py`: `profile_source` :189 (Name oder Pfad, Prusa-Abschnitt bleibt erhalten), `profile_file` :205.

### 3.2 Rücklesetabellen

**`FILAMENT_READBACK` (Orca)** :2233, 18 Pfade:
- temperature: nozzle, nozzle_first_layer, bed, bed_first_layer, chamber
- cooling: fan_speed, minimum_fan_speed, fan_below_layer_time, bridge_fan_speed, disable_first_layers, minimum_layer_time
- filament: density, flow_ratio, max_flow, diameter
- retraction: length, speed, z_hop

Anteile werden über `_AS_FRACTION` :2258 in Brüche umgerechnet.

**`_PRUSA_FILAMENT_READBACK`** :2420: dieselben 18 Pfade (`temperature`, `max_fan_speed`, `extrusion_multiplier`, `filament_retract_*` …).

**`_CURA_FILAMENT_READBACK`** :2441, 12 Pfade:
- alle 5 Temperaturen,
- cooling.fan_speed, minimum_fan_speed, fan_below_layer_time,
- filament.density, diameter,
- retraction.length, speed.

**`filament_values(path | SlicerProfile, roots)`** :2457:
- wählt die Tabelle nach Dateiendung,
- lässt `nil` und leere Werte weg,
- wirft bei nicht endlichen Werten `ValidationError`,
- lässt `max_flow ≤ 0` weg.

**Nie zurückgelesen:** filament.colour, filament.cost_per_kg, retraction.wipe und alle Prozess- und Tempowerte.

**`MACHINE_READBACK`** :2278 und `machine_values` :2386 haben **keinen Aufrufer**. Das steht im eigenen Docstring (:2403–2414).

**Prozesswerte werden nicht zurückgelesen.** Sie gehen nur als rohe Unterlage in `_orca_process` und `project_settings` ein. `cura_quality_types` liest `layer_height` allein für die Wahl des `quality_type`.

### 3.3 Wo das Rücklesen wirkt

| Stelle | Datei:Zeile | Wirkung |
|---|---|---|
| `settings_for_slot(settings, profile, slot, setup)` | handover.py:1013 | (1) Weicht die Materialart der Spule vom Projekt ab, kommen temperature, cooling, retraction und filament aus `resolve()` für dieses Material (:1032–1043). (2) Mit `setup` und `slot.material`: `filament_values` → `with_path` (:1044–1050). (3) `SlotOverride`-Gruppen gewinnen (:1051–1060). **`setup.base_filament` wird hier nicht zurückgelesen.** |
| Aufrufer mit setup | handover.py:1406 (`flat_values` über `settings_for_handover` :1228 → `settings_for_shared_slicer` :1211 = Slot 0), :1464, :1657, :2860/2864, :3613/3618; writer.py:1470; Dialog :1639/1645, :1908 | |
| Aufrufer ohne setup (kein Rücklesen) | core/filament_usage.py:197, :211 | |
| `_orca_filament` | handover.py:1970–1980 | Hat der Slot ein eigenes Profil, bleiben die Herstellerwerte aller `FILAMENT_READBACK`-Schlüssel stehen, sofern keine Übersteuerungsgruppe gesetzt ist. Solidons eigene Werte fallen dort weg. |
| `_adopt_filament_values` | Dialog:4705 | nur auf Klick, ins Projekt |

## 4. Übergabe je Familie (`handover.py`, `slicer_keys.py`)

### 4.1 Gemeinsame Bausteine

**Tabellen in `slicer_keys.py`** (`Entry` :60):

| Tabelle | Zeilen | Umfang |
|---|---|---|
| `PRUSA` | :223–303 | 60 Zeilen |
| `ORCA` | :333–432 | 67 Einträge, davon 45 Prozess und 22 Filament |
| `CURA` | :460–563 | 55 Einträge |

Weitere Tabellen: `CURA_MIRRORED` :583, `CURA_SCALED` :687, `CURA_UNTOUCHED` :719, `ADHESION_KEYS` :793, `TABLES` :818, `NOT_TAKEN_BY` :903, `AS_GEOMETRY` :924, `LIMITED` :930. Funktionen `takes` :938, `limitation` :955. Prädikate :1023–1193.

Wandler, die bei bestimmten Werten nichts schreiben: `_number_or_silent` :90 (0 heißt nicht schreiben), `_only` :151.

**Pipeline in `handover.py`:**
- `as_mapping` :473:
  - `_fan_curve_in_order` :502,
  - Tabellen,
  - `_only_chosen_adhesion` :613,
  - Prusa/Orca: `_support_spacing` :638,
  - Cura: `_first_layer_width` :704 und `_cura_fan_start` :722.
- `values_for` :519 = `as_mapping` + `_machine_keys` :901, bei Cura zusätzlich `_cura_dependants` :663 (`_cura_computed` :750, `_from_line_width` :773, `_for_supports` :819, `_for_speeds` :858, `_full_fan_layer` :762), danach `_without_line_break` :1341.
- `by_section` :536 teilt die Orca-Werte in Prozess und Filament.
- `SlicerConfig` :987 (`written` = Sollwerte für die Gegenprobe).
- `write_config` :1382 setzt zuerst `machine_for` :228 (`_fits_the_printer` :300).

### 4.2 Orca-Familie (OrcaSlicer, Bambu Studio, ElegooSlicer, Creality Print ≥ 6)

**`write_config`** :1425–1501 schreibt drei Dateiarten.

`solidon_machine.json` ← `_orca_machine` :1758:
- Kopf `type/from=system/instantiation`,
- **vollständig aufgelöstes Herstellerprofil** (`resolve_values`, einschließlich Start- und End-G-Code),
- Name „Solidon …“.
- Ohne Maschinenprofil nur Kopf und Name.

`solidon_process.json` ← `_orca_process` :1806:
- Kopf,
- aufgelöster Hersteller-Prozess (`base_process`),
- **darüber alle Solidon-Prozesswerte** (`document.update(values)` :1848): 45 Tabellenzeilen, davon `support_base_pattern` nur bei grid, plus `support_base_pattern_spacing`,
- `gcode_label_objects=1`,
- Name,
- `compatible_printers` (eigene Maschine oder `binding`).

`solidon_filament_&lt;i&gt;.json` je Slot ← `_orca_filament` :1890:
- Kopf, `filament_type`, `filament_is_support`, `filament_shrink`,
- aufgelöstes Herstellerfilament (`slot.material` oder `setup.base_filament`; eine lokale Spule anderen Typs bekommt keine Unterlage, :1917–1926),
- **darüber alle 22 Solidon-Filamentschlüssel** (Ausnahme Slot mit eigenem Profil, siehe 3.3),
- Farben vom Slot (`_hex` :2015),
- Name,
- `_with_every_plate` :2038 (`PLATE_KINDS` :2035) schreibt die Betttemperatur auf alle Plattentypen (`_plate_source` :2021).
- Danach gleicht `_with_equal_keys` :1531 die Schlüssel aller Filamente an (`_OWN_FILLS` :1521).

**Sollwerte:** Prozesswerte, `gcode_flavor` und je Slot verbundene Filamentwerte (:1483–1500).

**Kommando** `_command` :2246–2285:
```
--load-settings "machine;process" --load-filaments "f0;f1" [--arrange 0] --slice 0 --outputdir &lt;out&gt; &lt;3mf&gt;
```
(`_without_separator` :2325)

**3MF-Beilage** `project_settings` :1582:
- aufgelöste Hersteller-Maschine und -Prozess (:1628–1635),
- `_orca_process` darüber,
- `_machine_keys` (leer für Orca),
- Filamente je Extruder (`threemf.by_extruder`) über `settings_for_slot` und `_orca_filament`,
- `_with_equal_keys`, Listenform,
- IDs `printer/print/filament_settings_id` (:1721–1726), `printer_model` und `nozzle_diameter` per `setdefault`.

### 4.3 PrusaSlicer

**`write_config`** :1411–1423 schreibt `solidon.ini` mit `flat_values()`, also `values_for(settings_for_handover(...))`:
- PRUSA-Tabelle, dazu `support_material_spacing`,
- `_machine_keys` (:959–983): `nozzle_diameter`, `bed_shape` ab Ecke, `max_print_height`, `machine_limits_usage=ignore`,
- eine Titel-Kommentarzeile.
- Zählung bei Vorgabewerten: 60 Zeilen − `support_material_pattern` − `filament_cost` (beide still) + 1 + 4 = **63**.

Herstellerfilament: nur Slot 0 und nur über `_PRUSA_FILAMENT_READBACK` (18 Pfade).

**Kommando** :2235–2244:
```
--export-gcode --load solidon.ini --output &lt;out&gt;/solidon.gcode &lt;3mf&gt;
```

**Die 3MF** trägt zusätzlich `Metadata/Slic3r_PE.config` (`writer._plate_config` :1448 → `values_for`, Kopfzeile `PRUSA_CONFIG_HEADER`, threemf.py:87).

**Nie geladen:** Druckerpreset und Druckpreset des Herstellers. Solidon schreibt keinen `start_gcode`, `end_gcode`, `gcode_flavor` oder `printer_model`; es gilt die eingebaute Vorgabe von PrusaSlicer. Das Einlesen dafür wäre vorhanden (`_PrusaStore`, Test `test_slicer_profile_resolution.py:184`).

Die Dialoganzeige nennt das „vollständige Konfiguration“ (Dialog :3946–3951). `machine_missing` :327 schweigt für Prusa (:357).

### 4.4 CuraEngine

**`write_config`** :1503–1514 schreibt `solidon_cura.txt` mit `flat_values()`:
- CURA-Tabelle,
- `_cura_fan_start` (2 Schlüssel),
- `_machine_keys` Cura (:917–958, 14 Schlüssel: Bauraum, Düse, beheiztes Bett, `machine_center_is_zero=false`, `z_seam_x/y`, `acceleration_enabled` …),
- `_cura_dependants`.

Materialwerte der 1. Spule über `_CURA_FILAMENT_READBACK`.

**Kommando** :2287–2318:
```
slice -j &lt;setup.machine_profile | fdmprinter.def.json&gt; -s k=v … -e0 -j fdmextruder.def.json -s k=v … -l &lt;stl&gt; -o &lt;out&gt;/solidon.gcode
```
(`_cura_base` :2357, `_cura_extruder_base` :2373, `_cura_definition` :2384)

**Start-G-Code:** Vorgabe `machine_start_gcode` aus `fdmprinter.def.json`. Der Dialog wählt nie eine Herstellerdefinition, `machine_profile` bleibt leer.

**Cura-Fenster:** `cura_profile_beside` :3542 schreibt eine `.curaprofile` mit `as_mapping` je Extruder; `quality_type` kommt aus `cura_quality_types`, `definition` aus `machine_for` oder `fdmprinter`.

Cura bekommt ein STL (`writer._cura_assembly` :1474) ohne Teilwerte und ohne Stützsperre.

### 4.5 Einstellungen je Teil

- `writer._part_settings` :1015: Aufstandsfläche aus `cross_section` → `advise.for_part` (advise.py:1189, **nur `adhesion.kind`**) → `handover.object_keys` :574 (ganze Gruppe plus alle geänderten Schlüssel, `_applied` :601).
- Übertragen in `AssemblyPart.settings` (threemf.py:111), in `write_assembly` :1298–1303 und :1345–1358.
- Orca: `threemf._settings_xml` :423 → `Metadata/model_settings.config`.
- Prusa: `_prusa_settings_xml` :370 → `Metadata/Slic3r_PE_model.config` (`type="object"`).
- Beide Beilagen werden in jede 3MF geschrieben (threemf.py:342–345).
- Cura/STL: Befund `export.part_setting_unavailable` (`_part_setting_findings` :1049).

### 4.6 Prüfungen und Befunde

Vor der Übergabe (`writer.write_assembly`):
- `setting_limitations` :2066 (`NOT_TAKEN_BY` + `LIMITED`),
- `unreachable_overrides` :1063 (Prusa/Cura: nur Filament 1),
- `machine_missing` :327 (nur Orca).

Nach dem Lauf (`slice_model` :3380–3397):
- **`profile_differences` :2088:** nur Orca und nur, wenn `setup.base_filament` gesetzt ist. Vergleicht `by_section(settings)["filament"]` (Projektwerte, nicht die wirksamen Slotwerte) mit dem aufgelösten Grundfilament, überspringt `nil` und meldet einen info-Befund `slicer.filament_differs` („Übergeben werden die Einstellungen“).
- **`unknown_keys` :2150:** nur Cura, gegen `fdmprinter.def.json`/`fdmextruder.def.json`.
- **`verify` :3670 / `verify_settings` :3686:** vergleicht die G-Code-Kommentare mit `config.written` (Aufruf :3369–3370), ausgenommen `_RECOMPUTED` :3653, nachsichtiger Vergleich `_same` :3714. Geprüft wird nur, was Solidon geschrieben hat, nicht die geerbten Herstellerwerte.
- `off_the_bed` :2498, `too_short` :2685, `fan_in_off_layers` :2728, `spools_left_out` :2762.
- `_readback_materials` :2845 liefert Dichte und Durchmesser für die G-Code-Auswertung.
- Zum Schluss immer der info-Befund `slicer.handover` („gerechnet mit den Werten aus Solidon“).

### 4.7 Export ohne Slicerlauf

- `main_window.py:7751` → `settings_for_export` (Dialog :1065). Ergibt `None`, wenn „Werte mitgeben“ aus ist oder der Drucker Resin ist.
- `_ExportWorker._assembly` :1279 → `remembered_setup` → `write_assembly(for_slicer=False)` → `_plate_settings` :1422 (`project_settings`) bzw. `_plate_config`.

## 5. Analyse und Vorschläge (`app/core/slice/advise.py`)

### 5.1 Einstiege

- `advise` :177 ruft nacheinander `_from_machine`, `_from_material`, `_from_geometry`, `_from_fits`, `_from_connectors` (auf den Stand nach `apply`) und `_from_flow` (ebenfalls nach `apply`) auf und führt alles in `_merged` :258 zusammen.
- `_advice` :230 setzt `was = read_path`.
- `combine` :274 mit `_combined_value` :306: Tempi, Schichtwerte und `cooling.fan_speed` nehmen das Minimum, übrige Zahlen das Maximum; Aufzählungen nach Rang.
- `_differs` :326, `apply` :1565 (Kette von `with_path`).
- `for_part` :1189 prüft nur die Haftung.

### 5.2 Regeln und die Werte, die sie lesen

| Regel | Zeilen | Liest | Schwelle / Vorschlag |
|---|---|---|---|
| `_from_flow` | :363–417 | `filament.max_flow`; `layers.layer_height`, `line_width`, `first_layer_*` (`bead_area`); die 5 fördernden Tempi | Tempo auf `flow_speed_limit`; Fehler, wenn schon 1 mm/s zu viel fördert |
| `_from_machine` Leerfahrt | :431–442 | `speed.travel` | auf `printer.travel_speed` |
| `_from_machine` Stützwinkel | :449–466 | `support.threshold_angle` | auf `overhang_limit_degrees` |
| `_from_machine` Schichthöhe | :468–502 | `layers.layer_height`, `first_layer_height` | ≤ 0,75·Düse |
| `_from_machine` Temperaturen | :514–537, :562–584 | `temperature.nozzle_first_layer`, `bed`, `bed_first_layer`, `nozzle`, `chamber` | Druckergrenzen |
| `_from_machine` Bahnbreite | :545–560 | `layers.line_width`, `first_layer_line_width` | ≥ 0,85·Düse |
| `_from_material` Verzug | :593–636 | `adhesion.kind`, `cooling.fan_speed` (&gt;0,3), `temperature.chamber` | nur ASA/ABS |
| `_from_material` TPU | :638–658 | outer_wall, inner_wall, infill, top_surface, first_layer, bridge | ≤ 30 mm/s |
| `_from_geometry` Stützen | :717–815 | `support.style`, `placement`, `block_channels` | |
| `_from_geometry` Haftung | :817–863 | `adhesion.kind` | Brim bei kleiner Fläche, kleinen Füßen, schlanker Form |
| `_from_geometry` Wandgenerator | :878–893 | `shell.wall_generator`, `layers.line_width` (3·Bahnbreite) | |
| `_from_geometry` Brücke | :895–906 | `speed.bridge` gegen `speed.outer_wall` | |
| `_from_geometry` dünne Wand | :908–932 | `layers.line_width` | halbe dünnste Stelle, mindestens 0,85·Düse |
| `_from_geometry` Keilwand | :946–966 | `shell.outer_wall_first`, `wall_generator` | |
| `_from_geometry` Mindestschichtzeit | :968–980 | `cooling.minimum_layer_time` | ≥ 15 s |
| `_from_fits` | :984–1054 | `shell.ironing`, `precise_outer_wall`, `speed.outer_wall_acceleration`, `speed.outer_wall`, `shell.outer_wall_first` | Beschleunigung ≤ 2000, Außenwand ≤ 30 mm/s |
| `_from_connectors` | :1116–1186 | `shell.wall_count`, `layers.line_width`, `infill.density` (`solid_core` :1057, `_fill_the_core` :1069) | Wandzahl bis 20, sonst Fülldichte |
| `warnings_for` | :1273 | `support.style`, `support.z_gap`, `layers.layer_height`, Materialtabelle | nur Befunde |

### 5.3 Weitere Leser von `PrintSettings`

- **Druckzeit und Gramm** `slice/estimate.py` (`support_material` :100, `shell_thickness` :137, `flow_rate` :150, `wall_speed` :162, `estimate` :199, `total` :230): wall_count, line_width, layer_height, Tempi, max_flow, infill.density, filament.density. Verwendet für Statuszeile und `SliceComparison`.
- **Abstände** `export/writer.py:adhesion_margin` :397, `support_margin` :417, `clearance_margin` :436.
- **Prüfbericht** `slice/findings.py:print_findings` :87.
- **Profil** `profiles.for_process` :704 bindet Mindestwand und Überhang an Schichthöhe und Bahnbreite.
- **Verbrauch** `filament_usage.prepare` :125.

## 6. Tests, die die heutigen Verträge festhalten

Ohne Dateiangabe gilt `tests/test_print_settings.py`.

### „Solidons Werte gewinnen“

| Test | Zeile | Hält fest |
|---|---|---|
| `test_the_filament_profile_keeps_what_the_maker_knows` | :2041 | `nozzle_temperature` von Solidon statt 999 aus dem Herstellerprofil |
| `test_an_orca_process_keeps_what_the_base_profile_knew` | :1513 | `wall_loops` von Solidon |
| `test_a_project_file_carries_its_values_written_out` | :3809 | Solidon über dem geerbten Wert |
| `test_without_slots_it_stays_one_filament` | :4662 | |
| `test_a_manual_slot_type_wins_over_the_projects_base_filament` | :4513 | |
| `test_the_bed_temperature_reaches_every_plate` | :3899 | |
| `test_a_prusa_config_stands_on_its_own` | :1372 | |
| `test_every_setting_reaches_every_slicer` | :763 | mit `UNREACHABLE` :739 |
| `test_every_setting_reaches_every_slicer_or_stands_in_the_list` | :5465 | mit `UNREACHED` :5402 |
| `test_the_orca_family_gets_solidons_speed_and_width_for_every_role` | test_export.py:2709 | |
| `test_prusa_gets_the_infill_speed_for_solid_infill_and_no_guessed_machine_limits` | test_export.py:2689 | |
| `test_a_prusa_assembly_carries_its_settings` | test_export.py:700 | |
| `test_export_as_3mf_writes_one_assembly`, `test_a_single_body_3mf_carries_the_settings_too`, `test_export_as_3mf_carries_the_print_settings` | test_ui_export.py:491/584/1372 | |
| `test_a_customer_can_export_geometry_without_our_values` | test_print_settings_ui.py:4872 | |

### Herstellerwerte gewinnen (Spule mit eigenem Profil)

| Test | Datei:Zeile |
|---|---|
| `test_every_slot_gets_its_own_filament` | :4466 |
| `test_the_manufacturers_fan_curve_survives_the_handover` | :975 |
| `test_a_slot_override_wins_over_its_selected_filament_profile` | :4615 |
| `test_slot_advice_uses_inherited_values_and_the_adopted_group_reaches_both_outputs` | :5828 |
| `test_local_spool_defaults_keep_process_and_explicit_spool_values` | :4570 |
| `test_a_local_spool_sets_the_material_values_of_a_shared_slicer` | :4597 |
| `test_every_filament_profile_of_a_run_carries_the_same_keys` | :4335 |
| `test_prusa_selected_filament_reaches_the_written_configuration` | test_slicer_profile_resolution.py:157 |
| `test_print_advice_uses_manufacturer_flow_and_keeps_other_manufacturer_values` | test_print_settings_ui.py:5809 |
| `test_accepted_material_advice_preserves_the_effective_filament_group` | test_print_settings_ui.py:5788 |

### `profile_differences`

- `test_a_filament_profile_that_disagrees_is_reported` :3424
- `test_a_filament_profile_that_agrees_says_nothing` :3463
- `test_a_profile_that_says_nothing_is_no_disagreement` :3663

### `verify` / `verify_settings`

- `test_the_check_stays_quiet_when_everything_arrived` :1265
- `test_the_check_finds_what_the_slicer_ignored` :1269
- `test_a_key_the_file_never_mentions_says_nothing` :1285
- `test_the_check_compares_leniently` :1296
- `test_recomputed_keys_are_left_alone` :1303
- `test_the_first_spools_value_is_verified_as_written` :3266
- `test_written_slicer_values_include_the_resolved_temperature_of_every_tool` :5860
- `test_the_gcode_comparison_preserves_all_filament_values` :5900
- `test_creality_cli_uses_the_manufacturers_tower_modes` :2813 (prüft `verify` bei :2832)
- `test_a_key_cura_does_not_know_becomes_a_finding` :2265, `test_without_a_definition_nothing_is_claimed` :2300 (`unknown_keys`)

### `resolve` und Druckertempo

- :65–:300, darunter `test_the_printers_own_pace_is_the_standard_stage` :117, `test_no_stage_asks_for_more_than_the_filament_flows` :184, `test_every_named_printer_carries_its_makers_pace` :227, Pfad-Tests :287/:299
- test_advise.py :593–:716 (Leerfahrt, Stützgrenze, ältere Projekte)

### Rücklesen

- test_slicer_profiles.py: `test_a_filament_profile_tells_its_own_values` :556, `test_both_ends_of_the_fan_curve_are_read_back_in_every_format` :596, `test_what_a_filament_does_not_say_is_not_invented` :644, `test_a_machine_profile_gives_up_what_solidon_cannot_know` :665, `test_a_machine_profile_that_says_nothing_yields_nothing` :720, `test_nonfinite_filament_values_are_rejected_with_a_profile_error` :1422
- test_slicer_profile_resolution.py: alle Tests, besonders :136, :184, :279, :289
- test_print_settings_ui.py: :414, :452, :691, :720, :753

### Speichern und Migration

- :1026, :1048, :1096, :1836, :1884, :1389
- test_project.py: :2384, :2394, :2406, :2426, :2450, :2493, :1666, :1898, :2157
- test_review_project_choices.py: :42, :86
- test_print_settings_ui.py: :163

### Dialog

test_print_settings_ui.py:
- Grundwerte und Änderungen: :646, :778, :4924, :1909, :2285
- Slot- und Werte-Erhalt bei Wechseln: :3089, :3129, :3155, :3182, :3219
- Profilsuche und Merken: :2738, :2759, :2811, :2842, :2874, :3337, :3367, :2076, :2111, :2140, :2172, :2193, :2211, :2239, :921, :5132, :5181, :5227, :5309, :5396
- Ausgegraute Felder und Vorschlagsgrenzen: :5056, :4979
- Export: :6102, :6243
- test_ui_export.py:543 (`remembered_setup`)

### Übergabe je Familie

- Orca: :1906, :1967, :2016, :2098, :4380, :4436, :4545, :5949
- Cura: :2207, :2226, :3919, :3942, :3958, :3977, :5941, :6040
- Maschinenwahl: :4008–:4266, :5627, :5660, :5673, :5706, :5726, :5783, :5808
- Nur ein Filament: :1738, :1777, :1802, :5884

### Einstellungen je Teil

- :3597, :3615, :3624, :3633, :3657
- test_export.py: :1980, :2027, :2053, :2211

## 7. Beobachtungen für den Umbau

1. **Keine Herkunft je Feld.** Was „ausdrücklich gewählt“ ist, lässt sich heute nicht belegen. Ansätze wären `has_changes` und der Vergleich mit den alten Vorgaben in `_scene_profile_changed`.
2. **Implizite Vollschreibungen** machen aus `None` („Dialog nie geöffnet“) einen vollen Satz: `_plate_job`, `_inventory_settings`, `history.restore` mit `PrintSettings()`.
3. **Zweimal Herstellerwissen.** `printers.toml` enthält kopierte Herstellertempi und Winkel; `resolve` und `advise` rechnen damit, unabhängig vom gewählten Slicerprofil.
4. **Prusa und Cura:** Profilsuche, Merken und `write_config` übergehen die vorhandenen Leser (`_PrusaStore`, `_cura_definition_values`). Der Dialog bietet dort keine Auswahl an.
5. **Grundfilament des Dialogs** (`setup.base_filament`) liegt bei Orca als Unterlage unter der Datei, wird aber weder für Vorschläge noch für den Verbrauch zurückgelesen. Nur Spulen mit eigenem Profil (`slot.material`) werden zurückgelesen.
6. **`FilamentOverrideDialog`** zeigt Projektwerte statt der wirksamen Spulenwerte aus `settings_for_slot`.
7. **Ein übernommener Filamentvorschlag** friert die ganze Gruppe als `SlotOverride` ein (`_apply_advice` :6133–6150).
8. **Veraltete Kommentare:**
   - Dialog :3696 („`filament_values` hat sonst keinen Aufrufer“),
   - `has_readable_profiles` (slicer_keys :1120–1129, Prusa „nichts auszuwählen“),
   - `ProfileSection` (slicer_keys :52: „Ein Maschinenprofil schreibt Solidon nicht“), obwohl `_orca_machine` eines schreibt,
   - `MACHINE_READBACK` ohne Aufrufer.
9. **`verify_settings`** prüft nur Solidons Sollwerte. Schreibt Solidon künftig weniger, prüft die Gegenprobe automatisch weniger.
10. **`profile_differences`** vergleicht Projektwerte, nicht die wirksamen Spulenwerte, und nur gegen das Grundfilament.</result>
