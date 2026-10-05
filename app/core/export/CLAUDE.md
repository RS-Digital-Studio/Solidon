# `app/core/export/` — hinaus

Dateien schreiben, Plattenbelegung, Übergabe an den Slicer (§29). Die Regeln
stehen in `.claude/rules/dateiformat.md`; Herleitungen in
`konzepte/begruendungen/karte-app-core-export.md`. STEP geht über
`brep/step.py`. Der Slicer wird gerufen, nie mitgeliefert (Regel 15).

## Die Karte

| Datei | Rolle |
|---|---|
| `writer.py` | Export und **die Prüfung, die davor läuft** (§29, §16.3): `check_before_export`, `default_scheme` (Namensmuster, im Dateidialog), `mesh_for_export` an allen drei Stellen des Schreibers, `export_part_scad` (erst `activation.require(EXPORT)`); bei Resin lässt `write_assembly` den FDM-Satz fallen (keine Haftungs- und Filamentbefunde, keine Beilage); `part_advice` ist der Rat je Körper und Spule (auch für die Zeile im Druckdialog), mit den übernommenen Werten je Teil bis zum Fixpunkt gefragt, `_part_values` schreibt daraus Objekt- oder Netzwerte |
| `readback.py` | Gegenprobe: liest Geschriebenes zurück (Dreiecke, Volumen, Außenmaße), `Readback` |
| `threemf.py` | 3MF **schreiben** — Körper oder Baugruppe, Farbgruppen, Slicer-Beilagen (§20, §29), `AssemblyPart.support_blocker` je nach `blocker_as_part`; Körper und Sperren behalten ihre float64-Koordinaten ohne Rundung; gelesen wird in `ingest/threemf.py` |
| `handover.py` | Übergabe an den Slicer (§29, §28.1): `write_config`, `project_settings`, `values_for`, `slice_model` und seine Gegenproben, `prusa_values`; `machine_for` bindet importierte Orca-Düsenvarianten an Quellprofil, Modell und belegten Hersteller; `project_settings` und `_machine_name` schreiben bei auflösbarer Maschinenkennung den nativen Profilnamen, während intern die stabile Kennung erhalten bleibt (`_source_profile_name`); `split_for_parts` trennt übernommene Werte nach gemessener Programmmarke in plattenweite und solche je Teil (`PartSplit`, `CURA_PER_MESH`; `PartSplit.accepted_per_part` trägt die Übernahmen in den Rat je Teil); `settings_for_slot` liest gebundene Bambu-Filamente mit derselben aktiven Variante, `_resolve_slot` hält Rücklesen, Ausgabe und Befund zusammen; eine nicht zuordenbare Variante verwirft das gebundene Profil und schreibt Projektwerte; in gemischten 3MFs löst `project_settings` je Slot nur ausdrücklich variantengebundene Bambu-Felder (`BAMBU_FILAMENT_VARIANT_SETTINGS`) bei passender Variantenanzahl auf; Profilvektoren anderer Semantik bleiben auch bei gleicher Länge vollständig; `_followers_not_faster` vergleicht Tempovorschläge mit dem aktiven Prozesswert; `organic_tree_fitted` hebt die Baumspitze; `slot_processes` nennt je Spule eines Körpers Profil und Einstellungen, `chosen_slot_profiles` die gewählten Filamentprofile |
| `manufacturer.py` | **Die Grundlage aus dem Herstellerprofil**: `base_settings` liest Prozess, Filament und Maschine des gewählten Slicerprofils in Solidons Felder zurück (`ORCA_PROCESS`, `slicer_profiles.FILAMENT_READBACK`); Bambu-Listen löst es über den vollständigen Variantennamen aus Extrudertyp und `nozzle_volume_type` auf, jedes Prozess-, Maschinen- und Filamentprofil mit seinem eigenen Variantenindex und Extruder (`_variant_selection`, `_variant_values`); mehrdeutige Varianten fallen auf Solidons Tabelle zurück, mit eigenem Befund (`Foundation.unresolved_variant`, `slicer.process_variant_unresolved`), nie als unlesbares Profil; ohne lesbare Variante (`nil`, leer, Zahl) ebenso, mit `slicer.process_variant_unreadable`. Die vier Orca-Programme ergänzen ihre gemessenen Vorgaben (`PROGRAM_DEFAULTS`), dazu kommen Druckplatte (`default_plate`, `PROGRAM_PLATE`, `PLATE_TEMPERATURES`), `Foundation.nozzle_type`, `process_missing` und Gemessenes (`Foundation.measured`, auf dem Raster der Probe: `measured_on`, Rückfall `Foundation.unmeasured`); die Stufe wählt den Prozess des Herstellers (`for_stage`), nur wo keiner passt, liegen ihre Werte über dem Standardprozess (`STAGE_PATHS`, `Foundation.staged`); `plate_temperatures`, `offers_plates`; `effective` (Grundlage plus Abweichung), `written_paths` (was die Übergabe davon schreibt), `findings` (Platte, unlesbares Profil, nicht zuordenbare Düsenvariante). Für PrusaSlicer löst `prusa_chain` Drucker, Prozess und Filament des Bündels auf (`PrusaChain`), `PRUSA_PROCESS` und `PRUSA_PROGRAM_DEFAULTS` lesen sie zurück |
| `prusa_conditions.py` | PrusaSlicers Verträglichkeitsbedingungen mit eigenem Parser, ohne `eval` (Regel 10); `slicer_profiles._prusa_fits` bindet damit Prozesse und Filamente an den Drucker |
| `slicer_keys.py` | Wie eine Solidon-Einstellung in **jedem** Slicer heißt; die Prädikate je Familie; Düsenart-Fassungen (`NOZZLE_KIND_KEYS`); Konsolengrenzen (`CONSOLE_LIMITS`) |
| `slicer_profiles.py` | Die Profile eines installierten Slicers; ein Durchgang liest jede Datei einmal (`ProfileDocuments`); `_prusa_store` hält den Prusa-Bestand, bis sich eine Bündeldatei ändert; `identity` (Kennung in einer Auswahl); `machine_for_name` löst das aktive Profil eindeutig auf; `machine_vendor` liest den belegten Hersteller aus Profil oder Herstellerordner; `match_filament` wählt die Filament-Vorgabe: Vorwahl der Maschine, Vorschlag des Modells (`suggested_filaments`, bei der Orca-Familie aus dem Modellprofil `machine_model`), dann Generic oder die Marke des Druckers (`brand_of` aus `filament_vendor`) vor jeder Fremdmarke, die schlichteste Ausführung, erst dann die Namenslänge; `same_printer_model` gruppiert Düsenvarianten nach Hersteller und Modell (Modellfeld oder `model_name`); `sister_variant` wählt die Schwester einer Düse für `match` und `machine_with_nozzle` (nutzt einen gelesenen Bestand, gibt die Kennung zurück); `stage_process` und `standard_process` ordnen Stufe und Standardprozess zu (`STAGE_WORDS`); `variant_index` löst Namen und Extruderkennung für jedes Profil getrennt auf; `filament_readback` liefert Materialwerte samt Status der Variantenzuordnung, `filament_values` nur die eindeutig zugeordneten Werte; Prusa-Profile passen nur zum Drucker ihres Bündels (`SlicerProfile.vendor`) |

## Drucker aus dem gewählten Slicer

`slicer_profiles.discover_printers` leitet aus vollständigen Maschinenprofilen
Bauraum, Druckkontur, Sperrzonen, Düse und den Nullpunkt der Maschine
(`PrinterProfile.bed_origin`, Curas `machine_center_is_zero`) ab, ohne sie zu
speichern. Stabile
Kennungen unterscheiden Programm, Hersteller und Profil unabhängig vom
Installationspfad. Bekannte Hardwarezusätze bleiben nur bei exakt passendem
Modell und gleicher Düse erhalten; native Maße haben Vorrang. Der strikte
Profilauflöser verwirft fehlende Eltern und nicht auswertbare Cura-Formeln.
Erst die bestätigte Auswahl übernimmt ein Druckerprofil in den Nutzerbestand.

Cura-Maschineninstanzen bleiben über `SlicerProfile.cura_instance` und die
portable Auswahlkennung `cura-instance:<ID>` von gleich benannten
Werksdefinitionen getrennt. `chosen_printer` ordnet die aktive Instanz zu;
alte Kennungen werden nur über den historischen Hash aus Programmmarke,
nativer Instanzkennung, Hersteller und gespeichertem Druckernamen zugeordnet;
zusätzlich muss die Cura-Druckerdefinition exakt übereinstimmen. Ähnliche
Namen oder Definitionen reichen nicht (`matches_saved_cura_printer`).
`resolve_profile` liest DefinitionChanges, Düsenvariante und Nutzercontainer.
Die Übergabe übernimmt daraus Hardwarewerte sowie Start- und Endcode. Ein
fehlender oder unvollständiger gespeicherter Stapel fällt nicht auf Werkswerte
zurück. Bei gleich benannten Profilen verschiedener Slicer bleibt die vom
Nutzer gewählte Druckerkennung maßgeblich.

Eine gefundene Cura-Instanz oder -Definition bleibt die Maschine, auch wenn
Solidon eine andere Düse gewählt hat: Die Düse ist dort ein Wert, kein eigenes
Profil (`_nozzle_is_a_value`); `match` wendet die Familienregel nur auf
Profile mit Düsenvarianten an, und `write_config` schreibt Solidons Durchmesser
als `machine_nozzle_size`. Den Ursprung behält die Maschine
(`CuraMachine.origin_at_centre`, Regel in `dateiformat.md`). `cura_instance_is_present`
trennt eine entfernte Instanz von einem vorhandenen, aber unvollständigen
Stapel; beide Fehler behalten den vollständigen Druckernamen. Der Anzeigename
der aktiven Maschine kommt aus `machine_instances/*.global.cfg`, nicht aus der
internen Instanzkennung.

Curas Jerk-Steuerung folgt der gewählten Definitions- und Containerkette.
Bekannte Abhängigkeiten werden aufgelöst, eigene Rollen und Schalter gehen
vor. `resolve_profile(cura_motion=True)` prüft die Bewegungswerte erst für
die konkrete Übergabe; Druckerliste und Bettlesen bleiben davon unabhängig.
Unbekannte aktive Werte halten CLI und Fensterprofil mit derselben Handlung
an. Beide schreiben denselben aufgelösten Bestand. Extrudercontainer beachten
das geerbte `settable_per_extruder`; globale Schalter bleiben global. Verglichen
werden wirksame Rollen; ausgeschaltete Druck- oder Leerfahrtwerte bleiben
ohne Wirkung und ohne rohe Formeln in der strikten Ausgabe.

## Auf dem Herstellerprofil schreibt die Übergabe nur die Abweichung

Materialarten werden in `slicer_keys` gelesen und geschrieben:
`normalise_filament_type` vereinheitlicht native Namen für Vorwahl und
Rücklesung, `filament_type(..., flavour)` schreibt die Form des Zielprogramms.
Ohne auflösbares Filamentprofil nennt `Foundation.material_from_table` die
Materialherkunft; `slicer.filament_from_table` trägt sie in den Exportbericht.

Kammerwerte verwenden `slicer_keys.native_key` beim Schreiben, Rücklesen,
Aufteilen und Prüfen. `normalise_chamber` löst den alten Plural vor eigenen
Werten auf. `Foundation.chamber_control` kommt ausschließlich aus der
Maschine; unbekannt bleibt `None`. `manufacturer.chamber_limitation` begründet
das gesperrte Druckfeld, das Vorschlagangebot und den Übergabebefund. Nur bei
belegter Heizung und positivem Sollwert setzt die Orca-Übergabe den nötigen
Filamentschalter.

`write_config` und `project_settings` fragen `base_settings`; liegt ein
lesbarer Herstellerprozess darunter, gehen nur die Pfade aus `chosen` und
`accepted` hinaus (`as_mapping(paths=)`, `by_section(paths=)`), dazu das
Gemessene, `curr_bed_type` und die Objektmarken. Ein Filament ohne
Herstellerunterlage bekommt je Dokument Solidons ganzen Satz. Ohne
Herstellerprozess schreibt Solidon alles und die Betttemperatur auf jede Platte
(`_with_every_plate`), mit einem an die gewählte (`SlicerSetup.plate`, sonst
`default_plate`; `_on_the_plate`). Druckdialog,
`MainWindow.effective_print_settings` (`_FoundationWorker`) und Menüexport
legen dieselbe Grundlage unter (`print_settings.on_base`). PrusaSlicer bekommt
über `prusa_values` die ganze Kette samt Abweichung (in `write_config` für die
Konsole, in `writer._plate_config` für die Beilage), ohne Drucker des Bündels
Solidons ganzen Satz; „Automatisch" als Haftung heißt dort und bei Cura die Art
aus Solidons Tabelle, bei passender Prusa-Grundlage die Art des Profils.
`effective_adhesion` ist die gemeinsame Auflösung für Dialog und Übergabe;
`handed_over_adhesion_kinds` nennt die Arten, deren Maße hinausgehen (samt
`native_adhesion_kinds` einer Prusa-Grundlage), der Dialog zeigt genau sie.
Die Maße je Art stehen einmal in `print_settings.ADHESION_PATHS`.
`foundation_findings` meldet in Slicen und Export.

**Ohne Herstellerprofil bekommt jede Rolle Solidons Wert**: PrusaSlicer volle
Füllung und Lücken (`solid_infill_speed`, `gap_fill_speed`) und
`machine_limits_usage = ignore` (keine erfundenen Beschleunigungen), die
Orca-Familie dieselben Tempi und die Bahnbreite aller fünf Rollen. Bambus
Absage liest `_result_reason` aus `result.json`, nur vom letzten Lauf;
`_result_written` fragt, ob der Lauf sie abgelegt hat, und `slice_model` gibt
das der Orca-Familie als `finished` mit (Bambu endet manchmal nicht danach).

## Brim-Abstand

`AdhesionSettings.brim_gap` bezeichnet den Abstand am korrigierten Fuß.
`manufacturer.native_brim_gap` übersetzt den belegten Bezug für Konsole und
Projekt-/Objektwerte, `part_brim_gap` je Teil (Creality: Fußkorrektur des
Teils); Grenzen und Rückwege stehen in der Export-Herleitung.

## Die Lüfterkurve

Alle drei Familien regeln den Bauteillüfter über der Schichtzeit (oben bis zur
Mindestzeit, unten ab einer Schwelle): `CoolingSettings` mit `fan_speed`,
`minimum_fan_speed`, `fan_below_layer_time`, `minimum_layer_time`, übersetzt in
`slicer_keys`. `handover._fan_curve_in_order` deckelt den unteren Wert auf den
oberen — die eine Stelle für Profildatei, Beilage und Gegenprobe;
`slicer_profiles` liest beide Enden und die Schwelle zurück; Cura:
`manufacturer.cura_fan_curve`.

## Die vier Gegenproben nach dem Lauf

Vor dem Konsolenlauf prüft `slice_model` die Exportnetze der gewählten Platte
auf Höhe, drehbare Grundfläche und eine Anordnung auf einer Platte.
`PlateRun.meshes` hält den vorbereiteten Netzsatz, sonst lesen begrenzte
Importleser; Stützsperren zählen nicht als Druckteile. Ein Bauraumgrund hält
vor dem Prozessstart mit Handlung an.

`prepare_slicer_meshes` liefert Writer und Vorprüfung denselben Exportnetzsatz.
Ohne Konsolenanordnung (`arranges_on_cli`) wird jede Platte bei Bedarf gepackt
(Prusa: `--dont-arrange`), sonst nur gedreht, was ungedreht nicht passt; findet
sich keine Lage, hält es an, und Creality Print braucht `CREALITY_ARRANGE_EDGE`
Rand (`_check_creality_edge`). `arrangement_holds` prüft Kontur, Sperrzonen und
Höhe, auch im Fenster. Die Außenkante der ersten Schicht rechnet
`build_area.rim_of` (Orca-Auto-Brim bis `ORCA_AUTO_BRIM_MAX`, Stützfuß aus
`Foundation.support_foot`, unbekannt: Befund, Skirt), auch für den Rat.

| Prüfung | Frage |
|---|---|
| `off_the_bed` | Liegt der Druck im Bauraum? |
| `too_short` | Ist das ganze Modell darin, oder wurde unten abgeschnitten? |
| `verify_settings` | Hat der Slicer die geschriebenen Werte übernommen? |
| `spools_left_out` | Sind **alle übergebenen Spulen** gedruckt worden? |

`verify_settings` erhält Familie und Programmmarke: Prusa und Orca schreiben
vollständige Blöcke, fehlende Druckwerte sind deshalb Befunde. Belegte
Umbenennungen werden vor dem Vergleich übersetzt; reine `nil`-Overrides
bleiben Vererbung. Randart, Wandfolge und Stützart werden ebenfalls verglichen.

Die vierte fragt `expected_tools` aus `threemf.tools_in_use`; ohne sie entfällt
der Vergleich, ohne Filamentprofile je Spule sagt es `unreachable_overrides`
vorher. `crashed` (Regel in `dateiformat.md`) lässt eigene Fehlercodes wie
Bambus `-100` Absagen bleiben.

Curas innere Vollschichten fahren mit `speed.infill` (`speed_topbottom`),
die sichtbare Oberseite mit `speed.top_surface` (`speed_roofing`).
`as_mapping` aktiviert dafür genau eine Dachschicht, sofern obere Schichten
vorhanden sind, und bindet auch das Bügeltempo an die Oberfläche. So gelten
dieselben Rollen in der Konsole und im importierbaren Fensterprofil.

## Warum `slicer_keys.py` existiert

Drei Familien übersetzen (Warum im Moduldocstring): `prusa` (PrusaSlicer,
SuperSlicer), `orca` (OrcaSlicer, Bambu Studio, ElegooSlicer, Creality Print
ab 6, Anycubic Slicer Next), `cura` (CuraEngine). `flavour_of` ist die einzige
Stelle, an der ein Programm eine Familie wird (`FLAVOUR_BY_NAME`); alles andere
ist `other` — Datei nur ins Fenster (§29), STL um den Ursprung, jedes Prädikat
„nein“, `slice_model` und `write_config` sagen mit Vorschlag ab
(`_refuse_untranslated`, `only_opens`). Gleiche Familie heißt nicht gleicher
Stand: Was ein Programm nicht kennt, steht je Programmmarke in
`NOT_TAKEN_BY_PROGRAM` und `PROGRAM_ALIASES` (`takes(…, program)`,
`for_program`), was es nicht ausgibt, in `OMITTED_FROM_GCODE`. Rat
(`writer.part_advice`, `split_for_parts`), Beilage (`prusa_values`) und Dialog
fragen es; Bestand in `tests/data/superslicer_3mf_keys.json`.
Aufzählungen übersetzt `PROGRAM_VALUES` je Programm; nicht verfügbare Wahlen
stehen mit Ersatz und Grund in `NOT_OFFERED_BY_PROGRAM`. Dialog, Rat, Platte
und Objektwerte fragen denselben Bestand. `tests/data/slicer_values.json`
hält die unabhängig gemessenen Aufzählungswerte für den Wächter fest.

## Stolperfallen

### Stützsperre und Cura

Alle Slicer lesen technische Modellkopien und schreiben im privaten Arbeitsordner.
Unter Windows sind diese Pfade ASCII; ein 8.3-Alias darf nicht wieder aufgelöst
werden. Die Druckdatei gelangt danach atomar ins ursprüngliche Unicode-Ziel.
Cura erhält zusätzlich Blocker und vollständige Definitionsketten mit technischen
Namen (`handover._prepare_cura_cli`); nur Vererbung und Extruderzug-Verweise ändern
sich in den Kopien. Originaldateien und Herstellerprofile bleiben unverändert.

- **Die Stützsperre** (`support.block_channels`, Regel in `dateiformat.md`):
  `writer._support_blocker` fragt zuerst die Schichten des Prüfberichts
  (`slice.findings.remembered_analysis`), sonst schneidet es einmal mit
  `detail="support"` und extrudiert die Kanalscheiben mit `manifold3d`
  (`BLOCKER_SIMPLIFY`, `BLOCKER_MARGIN`); abbrechbar bis in den Schnitt
  (`write_assembly(cancelled=)`, `_PlateJob.cancelled`).
- **Cura bekommt je Teil ein Netz**: neben dem zusammengelegten STL je Teil
  und je Sperre ein STL und die Netzliste `<name>.meshes.json`
  (`write_cura_meshes`); `_command` liest sie (`cura_meshes`) und setzt je Netz
  `-l` mit seinen Werten, die Sperre mit `anti_overhang_mesh=true`;
  die Werte je Netz kommen aus `writer._part_values` (Rücknahme je Netz, `handover.PartSplit`).
  Curas Fenster bekommt dasselbe als 3MF (`writer._cura_window`,
  `threemf.write_assembly(cura=True)`), angefordert vom Fenster-Arbeiter
  des Druckdialogs (`_PlateJob.for_window`), mittig auf dem Bett der
  Maschine, die in Cura aktiv ist (`CuraActiveMachine.bed`). Ist dort ein
  anderer Drucker aktiv, nennt `cura_active_printer_mismatch` beide; dieselbe
  Definition mit demselben Bett gilt als derselbe Drucker (`_same_cura_machine`).
- **CuraEngine bekommt seine Maschine aus der Druckerdefinition**
  (`_cura_machine`): mit `PrinterProfile.cura_definition` und installierter
  Datei `-j`, sonst `fdmprinter`; Start- und Endcode aus der Kette, gefüllt von
  `_filled`, je ein `-s` (`solidon_cura.txt` trägt keine Umbrüche);
  `_temperature_switches`; `_cura_motion_values` übernimmt numerische
  Bewegungswerte, `_cura_limited_accelerations` begrenzt Platte und Netze;
  eigene Kürzungen reisen als `SlicerConfig.findings` in den Bericht.
  Fensterprofile und Objektwerte verwenden dieselbe Grenze der aktiven
  Instanz (`cura_window_motion`); ohne Definition `slicer.cura_printer_unknown`.
- **Cura übernimmt Einstellungen nur als Profil** (`cura_profile_beside`,
  Befund `handover.cura_profile`). Die Qualitätsstufe kommt vom Drucker, der in
  Cura aktiv ist, für Düse und Spule seines ersten Fachs
  (`slicer_profiles.cura_active_machine`: `cura.cfg` → Maschinenstapel →
  Definition, Extruderstapel Platz 5 die Düse, Platz 4 das Material;
  `configured_filaments`); ohne Drucker keine Datei, sondern
  `handover.cura_profile_unbound`.
- **Cura kennt keine Lüfterpause**: `_cura_fan_start` setzt Anfangslüfter null
  und die Höhe hinter der Pause (auch fürs Fenster), `_full_fan_layer` rechnet
  `cool_fan_full_layer`; ab zwei Schichten nennt `slicer_keys.limitation` einen
  Satz (`LIMITED`), den Rest misst `fan_in_off_layers` im G-Code.

### Profile, Spulen, Farben

- **Profile**: Die Filamenterhebung ist abbrechbar, nie halb. Vererbt wird über
  **alle** Profilwurzeln des Slicers, auch in Erkennung, Vergleich und
  Druckdialog, die Familie je Vorfahr neu bestimmt; Orca löst Erbbasis,
  `include`, eigene Werte, fehlende oder zyklische Vorlagen verhindern das
  Schreiben; Kompatibilität gilt auch aus unsichtbaren Erbbasen.
  `profile_by_name` gibt eine native Identität (Prusa mit
  `SlicerProfile.section`), die über `profile_source` reist; `profile_file`
  nur, wo ein Pfad verlangt ist. `resolve_profile` löst Prusa-Bündel, INIs,
  Cura-Definitionen und Material-XML als Daten (Prusa-Werte INI-kodiert mit
  literalem `\n`; Cura-Formeln nie ausgeführt; Material ohne Maschine nur aus
  den allgemeinen XML-Feldern; Update-Caches sind kein Bestand);
  `filament_values` liefert Solidon-Feldpfade.
- **Spulen**: `settings_for_slot` löst jede Spule gegen ihre Materialart, über
  dem Herstellerprofil, eigene Werte darüber — gleich für Schreiben, Beilage
  und Gegenprobe; eine fremde lokale Spule erbt keine Startsequenzen. Eine
  gebundene Variante, die im aktiven Düsenprofil fehlt oder mehrdeutig ist,
  wird nicht geerbt: alle Wege schreiben dieselben Projektwerte und melden
  `slicer.filament_variant_unresolved` mit Rückweg zum Druckdialog. Orca
  bekommt je Spule `filament_shrink` (sonst `100%`) und in allen
  Filamentprofilen eines Laufs dieselben Schlüssel (`_with_equal_keys`).
  `bind_slot_profiles` bindet alte Positionen an der ursprünglichen Szene;
  `configured_slots`: leeres Tupel heißt keine Wahl, nur `None` die alte Folge
  — gleich für Export und Verbrauch.
- **Plätze und Farben**: `threemf.assembly_slots()` ergänzt benutzte, nicht
  deklarierte Plätze neutral, nie erbt einer über Werkzeug null eine Spule;
  `slots_for_object` nimmt nur ohne Liste die alte Körperangabe, die eine volle
  Abwahl mitentfernt. Die Werkzeugnummer steht auch als `extruder`-Metadatum,
  an jedem Objekt, auch ohne Spule (das des neutralen Platzes; Creality Print
  lässt ein Objekt ohne sie auf der Konsole ohne Werkzeug), bemalte Dreiecke tragen `paint_color` und `slic3rpe:mmu_segmentation` (`p1`
  allein wählt nichts), alle in einer Folge samt Lücken. Mehrfarbige Spulen:
  `filament_multi_colour`, `filament_colour_type` „1" nur wo nötig, in
  `_RECOMPUTED`.

### Was hinausgeht, stimmt

- **Druckvorschläge je Objekt** vor der Formatwahl: STL warnt mit dem
  Vorschlag, 3MF nennt die mitgeschriebenen Abweichungen. **Geometrieblöcke**
  ersetzen nur ganze `<mesh>`-Platzhalter, Namen bleiben XML-maskiert, die
  Gegenprobe liest zurück. **Kein Zeilentrenner** verlässt `values_for`, an der
  Schreibstelle wird nachgeprüft.
- **`SlicerConfig.written`** hält die ausgegebenen Sollwerte samt Listen je
  Werkzeug, gegen sie prüft der G-Code; teilbezogene Prusa-Werte stehen in
  `Metadata/Slic3r_PE_model.config`. Nicht unterstütztes Mehrmaterial wird
  vorher benannt; jede weitere Filamentidentität zählt, dieselbe an mehreren
  Körpern nicht.
- **Creality Print** bekommt in Konsole und Fenster
  (`_for_the_creality_window`) eine Kopie ohne den einzelnen `plate`-Block aus
  `Metadata/model_settings.config`, nur bei
  belegter einzelner Platte; sonst bleibt alles ganz. Ab 7.3 rechnet die Konsole
  nur mit `--cli` und `--need-gcode-file`, ohne `--arrange` (`_creality_cli`),
  und ordnet eine Platte dort selbst an; eine Fassung, die
  `--cli` ablehnt, bekommt den alten Aufruf. Das Fenster fragt nach dem
  Drucker und nimmt dessen Profile (`window_findings`).
- **Reinigungsturm:** Die vier Orca-Konsolen ergänzen fehlende Koordinaten
  nach Crealitys bekanntem Modus oder ohne Modus unten mit Rand für Breite und Brim,
  neben Sperrflächen (rechteckiges Bett, 0 oder 90 Grad). Kundenkoordinaten
  bleiben; Unbekanntes wird nicht geraten. Die Turmfläche prüft der G-Code.

### Die Prüfung vor dem Export

- **Sie läuft vorher** — Wasserdichtheit, Bauraum, Wandstärken — mit Befunden
  samt Vorschlag (Regel 17), kein abgebrochener Export.
- **`check_before_export` nimmt die Szene** für die zwei Fragen aus §29, die
  kein Körper allein beantwortet (`scene.fits.check`,
  `scene.evaluate.check_thin_walls`): gefragt an der Szene, geantwortet über
  die Auswahl — eine Passung, deren andere Hälfte nicht mitgeht, wird trotzdem
  aufgelöst, sonst käme „Merkmal verloren"; ohne Szene gar nicht (Regel 21).
  `export → scene` ist eine **träge** Kante
  (`tests/test_core_package_direction.py`). Kollision und Netznäherung wie in
  der Auswertung; leere Verschneidung oder unbelegte Lage ist kein Befund, ein
  Abbruch gibt keinen halben Bericht, eine Passung zählt für jeden gewählten
  Partner, Unbeteiligte bekommen nichts.
- **`checked` nimmt einen Bericht entgegen**, statt ihn zweimal zu erheben;
  eine **leere** Liste ist eine Antwort — geprüft wird auf `None`.
- **Bett**: `wants_bed_coordinates` gilt der Ausgabe, `needs_bed_translation`
  der Eingabe (CuraEngine versetzt ein zentriertes STL selbst). Wohin, sagt
  `build_area.machine_shift` — 3MF-Platzierung (`bed_centre`), Prusas
  Bettform, Curas Ursprung und die Gegenprobe `off_the_bed` ohne Bett in der
  Druckdatei. Curas Fenster bekommt immer das halbe Bett der aktiven
  Maschine. Ein
  gescheiterter Anordnungsversuch gilt nur seinem Auftrag, erst eine
  ausdrückliche Ablehnung wird gemerkt; unbrauchbare Bettkonturen sind eine
  Warnung, ein belegter Übertritt geht vor.

## Grenzen

Prusas Erstschichtabsage wird vor der Ausgabekürzung gelesen
(`_empty_first_layer_error`); eine erste Schicht unter anderthalb Bahnen
nennt die Wandbahnen, auch für Orca (`_first_layer_narrower_than_a_line`).
Der native Name bleibt wörtlich und
muss eindeutig zur vorbereiteten Platte gehören; ungebundene Meldungen
bieten keine Handlung an einer zufällig gewählten Szeneauswahl.

- **Kein G-Code wird geschrieben** (§22). Das ist Sache des Slicers.
- Kennzahlen aus Schichtanalyse und G-Code bleiben getrennt (Regel 14).


## Der Raftkontakt

`adhesion.raft_gap` bleibt vom Stützabstand getrennt; `None` bewahrt die
Slicer-Vorgabe, null ist ein Wert. `raft_gap_active` entscheidet je Familie;
native Herkunft und Cura-Kopplung: Herleitung.
