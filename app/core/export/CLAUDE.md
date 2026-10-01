# `app/core/export/` — hinaus

Dateien schreiben, Plattenbelegung, Übergabe an den Slicer (§29). Die Regeln
stehen in `.claude/rules/dateiformat.md`; Herleitungen in
`konzepte/begruendungen/karte-app-core-export.md`. STEP geht über
`brep/step.py`. Der Slicer wird gerufen, nie mitgeliefert (Regel 15).

## Die Karte

| Datei | Rolle |
|---|---|
| `writer.py` | Export und **die Prüfung, die davor läuft** (§29, §16.3): `check_before_export`, `default_scheme` (Namensmuster, im Dateidialog), `mesh_for_export` an allen drei Stellen des Schreibers, `export_part_scad` (erst `activation.require(EXPORT)`); bei Resin lässt `write_assembly` den FDM-Satz fallen (keine Haftungs- und Filamentbefunde, keine Beilage); `part_advice` ist der Rat je Körper und Spule (auch für die Zeile im Druckdialog), mit den übernommenen Werten je Teil bis zum Fixpunkt gefragt, `_part_values` schreibt daraus Objekt- oder Netzwerte |
| `threemf.py` | 3MF **schreiben** — Körper oder Baugruppe, Farbgruppen, Slicer-Beilagen (§20, §29), `AssemblyPart.support_blocker` je nach `blocker_as_part`; gelesen wird in `ingest/threemf.py` |
| `handover.py` | Übergabe an den Slicer (§29, §28.1): `write_config`, `project_settings`, `values_for`, `slice_model` und seine Gegenproben, `prusa_values`; `split_for_parts` trennt übernommene Werte in plattenweite und solche je Teil (`PartSplit`, `CURA_PER_MESH`; `PartSplit.accepted_per_part` trägt die Übernahmen in den Rat je Teil); `settings_for_slot` liest gebundene Bambu-Filamente mit derselben aktiven Variante, `_resolve_slot` hält Rücklesen, Ausgabe und Befund zusammen; eine nicht zuordenbare Variante verwirft das gebundene Profil und schreibt Projektwerte; in gemischten 3MFs löst `project_settings` je Slot nur ausdrücklich variantengebundene Bambu-Felder (`BAMBU_FILAMENT_VARIANT_SETTINGS`) bei passender Variantenanzahl auf; Profilvektoren anderer Semantik bleiben auch bei gleicher Länge vollständig; `_followers_not_faster` vergleicht Tempovorschläge mit dem aktiven Prozesswert; `slot_processes` nennt je Spule eines Körpers Profil und Einstellungen, `chosen_slot_profiles` die gewählten Filamentprofile |
| `manufacturer.py` | **Die Grundlage aus dem Herstellerprofil**: `base_settings` liest Prozess, Filament und Maschine des gewählten Slicerprofils in Solidons Felder zurück (`ORCA_PROCESS`, `slicer_profiles.FILAMENT_READBACK`); Bambu-Listen löst es über den vollständigen Variantennamen aus Extrudertyp und `nozzle_volume_type` auf, jedes Prozess-, Maschinen- und Filamentprofil mit seinem eigenen Variantenindex und Extruder (`_variant_selection`, `_variant_values`); mehrdeutige Varianten fallen auf Solidons Tabelle zurück. Die vier Orca-Programme ergänzen ihre gemessenen Vorgaben (`PROGRAM_DEFAULTS`), dazu kommen Druckplatte (`default_plate`, `PLATE_TEMPERATURES`) und Gemessenes (`Foundation.measured`, auf dem Raster der Probe: `measured_on`, Rückfall `Foundation.unmeasured`); die Stufe wählt den Prozess des Herstellers (`for_stage`), nur wo keiner passt, liegen ihre Werte über dem Standardprozess (`STAGE_PATHS`, `Foundation.staged`); `plate_temperatures`, `offers_plates`; `effective` (Grundlage plus Abweichung), `written_paths` (was die Übergabe davon schreibt), `findings` (Platte, unlesbares Profil). Für PrusaSlicer löst `prusa_chain` Drucker, Prozess und Filament des Bündels auf (`PrusaChain`), `PRUSA_PROCESS` und `PRUSA_PROGRAM_DEFAULTS` lesen sie zurück |
| `prusa_conditions.py` | PrusaSlicers Verträglichkeitsbedingungen mit eigenem Parser, ohne `eval` (Regel 10); `slicer_profiles._prusa_fits` bindet damit Prozesse und Filamente an den Drucker |
| `slicer_keys.py` | Wie eine Solidon-Einstellung in **jedem** Slicer heißt; die Prädikate je Familie |
| `slicer_profiles.py` | Die Profile eines installierten Slicers; ein Durchgang liest jede Datei einmal (`ProfileDocuments`); `_prusa_store` hält den Prusa-Bestand, bis sich eine Bündeldatei ändert; `identity` (Kennung in einer Auswahl); `stage_process` und `standard_process` ordnen Stufe und Standardprozess zu (`STAGE_WORDS`); `variant_index` löst Namen und Extruderkennung für jedes Profil getrennt auf; `filament_readback` liefert Materialwerte samt Status der Variantenzuordnung, `filament_values` nur die eindeutig zugeordneten Werte; Prusa-Profile passen nur zum Drucker ihres Bündels (`SlicerProfile.vendor`) |

## Drucker aus dem gewählten Slicer

`slicer_profiles.discover_printers` leitet aus vollständigen Maschinenprofilen
Bauraum, Druckkontur, Sperrzonen und Düse ab, ohne sie zu speichern. Stabile
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

## Auf dem Herstellerprofil schreibt die Übergabe nur die Abweichung

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
aus Solidons Tabelle (`_adhesion_for`), im Bündel die des Profils.
`foundation_findings` meldet in Slicen und Export.

**Ohne Herstellerprofil bekommt jede Rolle Solidons Wert**: PrusaSlicer volle
Füllung und Lücken (`solid_infill_speed`, `gap_fill_speed`) und
`machine_limits_usage = ignore` (keine erfundenen Beschleunigungen), die
Orca-Familie dieselben Tempi und die Bahnbreite aller fünf Rollen. Bambus
Absage liest `_result_reason` aus `result.json`, nur vom letzten Lauf;
`_result_written` fragt, ob der Lauf sie abgelegt hat, und `slice_model` gibt
das der Orca-Familie als `finished` mit (Bambu endet manchmal nicht danach).

## Die Lüfterkurve

Alle drei Familien regeln den Bauteillüfter über der Schichtzeit (oben bis zur
Mindestzeit, unten ab einer Schwelle): `CoolingSettings` mit `fan_speed`,
`minimum_fan_speed`, `fan_below_layer_time`, `minimum_layer_time`, übersetzt in
`slicer_keys`. `handover._fan_curve_in_order` deckelt den unteren Wert auf den
oberen — die eine Stelle für Profildatei, Beilage und Gegenprobe;
`slicer_profiles` liest beide Enden und die Schwelle zurück.

## Die vier Gegenproben nach dem Lauf

| Prüfung | Frage |
|---|---|
| `off_the_bed` | Liegt der Druck im Bauraum? |
| `too_short` | Ist das ganze Modell darin, oder wurde unten abgeschnitten? |
| `verify_settings` | Hat der Slicer die geschriebenen Werte übernommen? |
| `spools_left_out` | Sind **alle übergebenen Spulen** gedruckt worden? |

Die vierte fragt `expected_tools` aus `threemf.tools_in_use`; ohne sie entfällt
der Vergleich, ohne Filamentprofile je Spule sagt es `unreachable_overrides`
vorher. `crashed` (Regel in `dateiformat.md`) lässt eigene Fehlercodes wie
Bambus `-100` Absagen bleiben.

## Warum `slicer_keys.py` existiert

Drei Familien übersetzen (Warum im Moduldocstring): `prusa` (PrusaSlicer,
SuperSlicer), `orca` (OrcaSlicer, Bambu Studio, ElegooSlicer, **Creality
Print** ab Version 6), `cura` (CuraEngine). `flavour_of` ist die einzige
Stelle, an der ein Programm eine Familie wird (`FLAVOUR_BY_NAME`); alles andere
ist `other` — Datei nur ins Fenster (§29), STL um den Ursprung, jedes Prädikat
„nein“, `slice_model` und `write_config` sagen mit Vorschlag ab
(`_refuse_untranslated`, `only_opens`).

## Stolperfallen

### Stützsperre und Cura

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
  Maschine, die in Cura aktiv ist (`CuraActiveMachine.bed`).
- **CuraEngine bekommt seine Maschine aus der Druckerdefinition**
  (`_cura_machine`): mit `PrinterProfile.cura_definition` und installierter
  Datei `-j`, sonst `fdmprinter`; Start- und Endcode aus der Kette, gefüllt von
  `_filled`, je ein `-s` (`solidon_cura.txt` trägt keine Umbrüche);
  `_temperature_switches`; ohne Definition `slicer.cura_printer_unknown`.
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
  `Metadata/model_settings.config` (Absturz mit mehreren Filamenten), nur bei
  belegter einzelner Platte; sonst bleibt alles ganz. Fehlende
  Reinigungsturmkoordinaten ergänzt der Konsolenweg nach Herstellermodus,
  Bettkontur und Turmbreite (rechteckig, 0 oder 90 Grad); ausdrückliche
  bleiben, Unbekanntes wird nicht geraten; bei mehreren benutzten Werkzeugen
  prüft die Gegenprobe sie. Ab 7.3 rechnet die Konsole nur mit `--cli` und
  `--need-gcode-file`, ohne `--arrange` (`_creality_cli`); eine Fassung, die
  `--cli` ablehnt, bekommt den alten Aufruf. Das Fenster fragt nach dem
  Drucker und nimmt dessen Profile (`window_findings`).

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
  der Eingabe (CuraEngine versetzt ein zentriertes STL selbst). Ein
  gescheiterter Anordnungsversuch gilt nur seinem Auftrag, erst eine
  ausdrückliche Ablehnung wird gemerkt; unbrauchbare Bettkonturen sind eine
  Warnung, ein belegter Übertritt geht vor.

## Grenzen

- **Kein G-Code wird geschrieben** (§22). Das ist Sache des Slicers.
- Kennzahlen aus Schichtanalyse und G-Code bleiben getrennt (Regel 14).
