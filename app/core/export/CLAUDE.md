# `app/core/export/` — hinaus

Dateien schreiben, Plattenbelegung, Übergabe an den Slicer (§29).

Die Regeln stehen in `.claude/rules/dateiformat.md`.

## Die Karte

| Datei | Rolle |
|---|---|
| `writer.py` | Export und **die Prüfung, die davor läuft** (§29, §16.3); `default_scheme` nennt das Namensmuster, nach dem ohne eigene Angabe benannt wird — das Fenster zeigt es im Dateidialog (RM-141). `mesh_for_export` vernetzt einen exakten Körper so fein, wie das Verfahren des Druckers es verlangt (`Profile.export_deflection`: ein Achtel des kleinsten Details, gedeckelt von der Zahl des Kerns — FDM bleibt bei 0,05 mm, ein Resin-Drucker mit 50-µm-Pixeln bekommt 0,006), an allen drei Stellen des Schreibers; `export.tessellated` nennt das Maß. Bei einem Resin-Drucker lässt `write_assembly` den FDM-Satz fallen: keine Haftungs- und Filamentbefunde, keine Beilage |
| `threemf.py` | 3MF **schreiben** — ein Körper oder eine Baugruppe, mit Farbgruppen und Slicer-Beilagen (§20, §29); `AssemblyPart.support_blocker` legt eine Stützsperre an — für die Orca-Familie als eigenes Teil (`support_blocker` in `model_settings.config`), für PrusaSlicer als Bereich im Netz (`SupportBlocker` in der Prusa-Beilage, dazu `slic3rpe:Version3mf`), je nach `blocker_as_part`. Gelesen wird in `ingest/threemf.py` |
| `handover.py` | Übergabe an den Slicer (§29, §28.1) |
| `manufacturer.py` | **Die Grundlage aus dem Herstellerprofil**: `base_settings` liest Prozess, Filament und Maschine des gewählten Slicerprofils in Solidons Felder zurück (`ORCA_PROCESS`, dazu `slicer_profiles.FILAMENT_READBACK`), mit den eingebauten Vorgaben der vier Orca-Programme (`PROGRAM_DEFAULTS`, gemessen), der Druckplatte (`default_plate`, `PLATE_TEMPERATURES`) und dem Gemessenen (`Foundation.measured`); über dem Standardprozess die Werte der gewählten Stufe (`STAGE_PATHS`, `Foundation.staged`); die Platten, für die das Filament eine Betttemperatur nennt (`plate_temperatures`), ob der Drucker eine Plattenwahl hat (`offers_plates`); `written_paths` sagt, was die Übergabe davon schreibt, `findings`, was der Kunde über Platte und unlesbares Profil wissen muss |
| `slicer_keys.py` | Wie eine Solidon-Einstellung in **jedem** Slicer heißt |
| `slicer_profiles.py` | Die Profile finden, die ein installierter Slicer mitbringt; ein Durchgang liest jede Datei einmal (`ProfileDocuments`, geteilt von Auswahl, Namensindex und Erbkette) |

STEP geht über `brep/step.py`, nicht von hier.

**Auf dem Herstellerprofil schreibt die Übergabe nur die Abweichung**
(Bauplan §29, Konzept `konzept-herstellerprofil-als-grundlage-2026-09`).
`write_config` und `project_settings` fragen für die Orca-Familie
`manufacturer.base_settings`; liegt ein lesbarer Herstellerprozess darunter,
gehen aus `PrintSettings` nur die Pfade in `chosen` und `accepted` hinaus
(`as_mapping(paths=)`, `by_section(paths=)`), dazu das Gemessene,
`curr_bed_type` und die Objektmarken. Jedes Dokument entscheidet für sich:
Ein Filament ohne Herstellerunterlage — eine lokale Spule anderen Typs —
bekommt Solidons ganzen Satz. Ohne Herstellerprozess schreibt Solidon wie
vor dem 27.09.2026 alles, und die Betttemperatur auf jede Platte
(`_with_every_plate`); mit einem gilt die gewählte Platte
(`SlicerSetup.plate`, sonst `manufacturer.default_plate`), und eine eigene
Betttemperatur bekommt deren Schlüssel (`_on_the_plate`). Der Druckdialog,
`MainWindow.effective_print_settings` (im `_FoundationWorker`) und der
Menüexport legen dieselbe Grundlage unter die eigene Wahl
(`print_settings.on_base`). Was ohne Partner nicht wirkt, geht mit ihm
(`COUPLED_PATHS`: Haftungsart mit allen Maßen, Lüfter-Obergrenze mit dem
unteren Ende); „Automatisch" als Haftung heißt bei PrusaSlicer und Cura
die Art aus Solidons Tabelle (`_adhesion_for`). Die Gegenprobe hält die
eigenen Werte und eine Stichprobe der Grundlage (`FOUNDATION_SAMPLE`,
Listen je Düsenvariante über `_printed`); `foundation_findings` meldet
Platte und unlesbares Profil in Slicen und Export.

**Die Stützsperre reist nur mit, wenn sie übernommen ist**
(`support.block_channels`) — und nur in der direkten Übergabe
(`write_assembly(for_slicer=True)`): bei der Orca-Familie und PrusaSlicer in
der 3MF, bei Cura als eigenes Netz (`_cura_meshes`, siehe unten).
`writer._support_blocker` schneidet das Teil dafür einmal mit
`detail="support"`, fragt `analysis.model_support` und `channel_space` und
extrudiert die Kanalscheiben mit `manifold3d` — vorher um `BLOCKER_SIMPLIFY`
vereinfacht, danach um `BLOCKER_MARGIN` aufgeweitet; der Befund
`export.support_blocker` sagt, wo. Der Schritt ist abbrechbar:
`write_assembly(cancelled=)` reicht den Abbruch bis in den Schnitt, und der
Druckdialog gibt ihn über `_PlateJob.cancelled` mit. Eine gespeicherte 3MF trägt sie nicht:
Sie ist das Projekt des Kunden und keine Übergabe. Welche Schreibweise welche
Familie liest, entscheidet `slicer_keys.helpers_as_parts` bzw.
`takes_mesh_settings`; die Regel und die Messung dazu stehen in
`.claude/rules/dateiformat.md`.

**Cura bekommt je Teil ein Netz.** Für CuraEngine schreibt `write_assembly`
neben das zusammengelegte STL (die Datei, die Curas Fenster öffnet) je Teil
ein STL und jede Sperre als eigenes, dazu die Netzliste
`<name>.meshes.json` (`handover.write_cura_meshes`). `_command` liest sie
(`handover.cura_meshes`, geprüft: nackte Dateinamen daneben, einzeilige Werte)
und setzt je Netz `-l` und seine Werte gleich dahinter — die Sperre mit
`anti_overhang_mesh=true`. An den Teilen setzt Stufe E des Konzepts
`support_enable` je Teil; die Stelle steht in `writer._cura_meshes`.

Die Erhebung eingelegter Slicerfilamente nimmt einen `CancelToken` an.
Orca-Dateisuche, Namensindex und Vererbung sowie Prusa-Dateien und Abschnitte
prüfen ihn zwischen ihren Schritten; auch das Einsammeln vor dem Sortieren
bleibt abbrechbar. Ein Abbruch liefert keinen unvollständigen Profilbestand.

Der SCAD-Ausgabeweg von CLI und Bausteinkatalog läuft über
`writer.export_part_scad`: erst `activation.require(EXPORT)`, dann die
Textkonvertierung. Damit liegt er in derselben vom Manifest gedeckten Grenze
wie die anderen Exporte. `knowledge.parts.scad.to_scad` bleibt als Teil der
MIT-Bibliothek unabhängig verwendbar.

Objektbezogene Druckvorschläge werden vor der Formatwahl ausgewertet. Eine
STL-Übergabe meldet nicht übertragbare Werte als Warnung mit dem konkreten
Vorschlag; sie behauptet keine angewendete Einstellung. 3MF nennt die
tatsächlich mitgeschriebenen Abweichungen als Information.

Geometrieblöcke ersetzen ausschließlich vollständige `<mesh>`-Platzhalter.
Titel, Körper- und Materialnamen bleiben XML-maskierte Nutzerdaten, selbst
wenn sie eine der zufälligen Geometriemarken enthalten. Die Gegenprobe liest
die erzeugte 3MF wieder ein und prüft Namen, Materialien und Geometrie.

`threemf.assembly_slots()` ergänzt tatsächlich verwendete, aber nicht
deklarierte Materialplätze neutral. Export, globales Zusammenlegen und
Verbrauchsplanung benutzen diese gemeinsame Liste. Fehlende Plätze dürfen
keine bekannte Spule durch einen pauschalen Rückfall auf Werkzeug null erben.
`slots_for_object` erhält deklarierte Slots unverändert und übernimmt nur bei
vollständig fehlender Slotliste eine ausdrücklich gespeicherte alte
Körpermaterialart. Beratung und Export benutzen dieselbe Sicht; eine
vollständige Materialabwahl entfernt deshalb auch die alte Körperangabe.

Baugruppen schreiben die globale Werkzeugnummer zugleich als native
`extruder`-Objektmetadaten für Orca/Bambu und Prusa. Bemalte ganze Dreiecke
tragen `paint_color` und `slic3rpe:mmu_segmentation`; Standard-`p1` allein
wählt in diesen Slicern kein Filament. Alle drei Darstellungen benutzen
dieselbe globale Reihenfolge einschließlich der Lücken einer Teilplatte.

`bind_slot_profiles` übernimmt alte Profilpositionen an der ursprünglichen
vollständigen Szene in `slot_profile_bindings`. `configured_slots` verwendet
anschließend diese Identitäten; ein leeres gebundenes Tupel hat ausdrücklich
keine Profilwahl. Nur `None` liest noch die alte Positionsfolge. Export und
Verbrauchsplanung benutzen dieselbe Auflösung, auch nach Abwahl, Undo,
Plattenwechsel oder Auswahl-Export.

`handover.values_for` prüft sämtliche zusammengeführten Einstellungen auf
Zeilentrenner, bevor sie den gemeinsamen Weg verlassen. Damit gilt dieselbe
Grenze für Slicer-Konfigurationen und eingebettete Prusa-3MF-Einstellungen.
Nach dem Ergänzen von Profilwerten wird an der Schreibstelle erneut geprüft.

Profilvererbung wird mit sämtlichen Profilwurzeln des gewählten Slicers
aufgelöst: Nutzerprofile können von installierten Profilen erben. Diese
Wurzeln gehören auch in Filamenterkennung, Materialvergleich und Auslesen
der Werte im Druckdialog; der Ordner der Blattdatei allein reicht nicht.

Nach dem Übergang aus einem Nutzerprofil in den Herstellerbestand wird die
Familie für jeden weiteren Vorfahren neu bestimmt. Orca-/Bambu-Profile werden
in der Reihenfolge Erbbasis, `include`-Vorlagen, eigene Werte aufgelöst;
fehlende oder zyklische Vorlagen verhindern das Ausschreiben. Die Auswahl
liest Kompatibilitätsangaben auch aus unsichtbaren Erbbasen.

`profile_by_name` liefert eine native Profilidentität; bei Prusa gehört
`SlicerProfile.section` zum Pfad. `resolve_profile` löst Prusa-Bündel und
eigene INIs einschließlich Mehrfachvererbung sowie Cura-Definitionen und
Material-XML als Daten auf. Prusa-Werte bleiben INI-serialisiert, einschließlich
der literalen `\n` in G-Code. `filament_values` akzeptiert diese Profilobjekte
oder einzelne Dateien und liefert Solidon-Feldpfade. Prusa-Update-Caches
sind kein aktiver Bestand. Cura-Formeln werden nicht ausgeführt; solche Werte
bleiben unbekannt, Materialwerte ohne Maschinenkontext kommen ausschließlich
aus den allgemeinen XML-Feldern.

Die Übergabe erhält diese Identität über `profile_source` bis zum Auslesen
der Slotwerte. `profile_file` reduziert sie ausschließlich für Schnittstellen,
die tatsächlich einen Dateipfad verlangen.

`settings_for_slot` löst jede Spule gegen ihre eigene Materialart auf,
berücksichtigt mit `setup` das vollständige Herstellerprofil und legt
ausdrückliche Spulenwerte darüber. Gemeinsame Prozesswerte bleiben
erhalten. Schreiben, eingebettete 3MF-Einstellungen und Gegenprobe benutzen
dieselbe Auflösung. Eine lokale Spule anderen Typs erbt keine Startsequenzen
aus dem allgemeinen Filamentprofil des Projekts.
Orca-Filamentprofile tragen je Spule `filament_shrink`: ohne Herstellerwert
den neutralen Slicerstandard `100%`, vorhandene Herstellerwerte bleiben stehen.
Die vollständige Liste ist auch für lokale Spulen nötig, da Bambu sie beim
Schneiden ungeprüft je Filament indiziert. Aus demselben Grund tragen alle
Filamentprofile eines Laufs **dieselben Schlüssel** (`_with_equal_keys`):
Eine Spule anderen Typs erbt das Herstellerprofil nicht und käme mit einem
Drittel der Schlüssel; die Orca-Familie indiziert dann ins Leere und reißt
ohne Meldung (`0xC0000409`). Was einem Profil fehlt, kommt aus dem ersten
Profil des Laufs, das den Schlüssel führt — nur Startsequenzen,
Überhangschwellen des Lüfters und Vorschubwerte, denn Temperaturen, Kühlung
und Materialwerte schreibt `_orca_filament` ohnehin je Spule.

Ein mehrfarbiges Filament (`MaterialSlot.extra_colours`) geht an die
Orca-Familie als `filament_multi_colour` — alle Farben in einer Zeichenkette
mit Leerzeichen, die erste zugleich in `filament_colour` — und
`filament_colour_type` „1" (Abschnitte, kein Verlauf). Die zwei Schlüssel
stehen nur, wo eine Spule mehrere Farben hat; in der Projektdatei dann für
jede Spule der Platte, weil dort je Extruder eine Liste steht. Beide gehören
zu `_RECOMPUTED`: Der G-Code führt sie nicht. `ingest/threemf.py` liest
denselben Schlüssel zurück. Prusa und Cura kennen eine Farbe je Filament und
bekommen die erste.

`SlicerConfig.written` hält die tatsächlich ausgegebenen Sollwerte, auch
Listen je Werkzeug. Die G-Code-Gegenprobe vergleicht diese Werte vollständig
und meldet keine Abweichung gegen eine überholte Projektvorgabe.
Teilbezogene Prusa-Einstellungen stehen in
`Metadata/Slic3r_PE_model.config`, Orca-Einstellungen in dessen eigener
Beilage. Ein nicht unterstützter Mehrmaterialumfang wird auch ohne manuelle
Spulenüberschreibungen vor der Übergabe benannt. Dabei zählt jede weitere
Filamentidentität, auch bei gleichem Materialtyp und gleichen Druckwerten;
mehrere Körper mit derselben Filamentidentität ergeben keine zusätzliche Spule.

Creality Print bekommt im CLI eine temporäre 3MF-Kopie ohne den einzelnen
`plate`-Block aus `Metadata/model_settings.config`: Dieser Block löst in
7.2.2.5483 bei mehreren Filamenten einen Absturz aus. Nur eine nachweislich
einzelne Platte darf so übergeben werden; mehrere oder unlesbare Plattenblöcke
bleiben vollständig. Objektwerkzeuge, Namen, Farben, Geometrie und alle übrigen
Beilagen bleiben erhalten. **Das Fenster bekommt dieselbe Datei**
(`_for_the_creality_window`): Fenster und Konsole teilen den Absturz, und ein
Kunde, dem die Konsole eine gerettete Datei gab, soll im Fenster nicht an der
ungeretteten scheitern. Die Originaldatei, der allgemeine Mehrplattenexport
und andere Slicer benutzen die vollständige Datei.

**CuraEngine bekommt seine Maschine aus der Druckerdefinition.**
`write_config` fragt `_cura_machine`: Trägt der Drucker eine
`PrinterProfile.cura_definition` und führt die Installation die Datei, lädt
`_command` sie mit `-j` (davor `-d` mit den Ordnern `definitions` und
`extruders`; CuraEngine löst die Erbkette und die Extruderzüge selbst auf),
sonst `fdmprinter` mit `fdmextruder` wie bisher. Start- und Endcode kommen aus
der Kette, ihre Platzhalter füllt `_filled` aus Solidons Werten und den
Vorgabewerten der Kette, und sie reisen als je ein `-s` mit Umbrüchen —
`solidon_cura.txt` trägt keine. `_temperature_switches` schaltet
`material_bed_temp_prepend`/`material_print_temp_prepend` ab, wo der
Startcode die Temperatur selbst setzt. Ohne Definition sagt es
`machine_missing` (`slicer.cura_printer_unknown`). Die Regeln dazu stehen in
`.claude/rules/dateiformat.md`.

**Cura übernimmt Einstellungen nur als Profil.** Seine Kommandozeile liest
Werte, das Fenster nicht; `cura_profile_beside` legt deshalb neben das Modell
eine `.curaprofile` (Qualitätsänderungen im Containerformat, das Curas
`CuraProfileReader` liest: `setting_version` aus der installierten
`fdmprinter.def.json`, Wahrheitswerte als `True`/`False`, `quality_type` aus
den Stufen des Druckers, der in Cura aktiv ist, für Düse und Spule seines
ersten Fachs), und der Befund `handover.cura_profile` sagt, wo man sie
importiert. Den aktiven Drucker liest `slicer_profiles.cura_active_machine`
aus Curas Konfigurationsordner (`cura.cfg` → Maschinenstapel → Definition,
Extruderstapel Platz 5 die Düse, Platz 4 das Material), die eingelegten
Materialien `configured_filaments` aus denselben Stapeln. Ohne eingerichteten
Drucker entsteht keine Datei, sondern `handover.cura_profile_unbound`.

**Ohne Herstellerprofil bekommt jede Rolle Solidons Wert** (RM-191):
PrusaSlicer schreibt Solidon
volle Füllung und Lücken (`solid_infill_speed`, `gap_fill_speed`) und setzt
`machine_limits_usage = ignore`, damit die Zeitschätzung nicht mit
erfundenen 1 500 mm/s² rechnet; die Orca-Familie bekommt dieselben zwei
Geschwindigkeiten und die Bahnbreite für alle fünf Rollen. Bambu Studio sagt
seine Absage nicht auf der Konsole, sondern in `result.json` neben der
Druckdatei (`return_code`, `error_string`); `_result_reason` hängt sie an die
Ausgabe, nur aus dem Lauf, der gerade war.

Im selben CLI-Weg werden fehlende Reinigungsturmkoordinaten nach Crealitys
Herstellermodus, Bettkontur und Turmbreite initialisiert. Das ersetzt die sonst
fehlende Fensterinitialisierung für rechteckige Betten bei 0 oder 90 Grad.
Explizite Koordinaten aus Maschinen-, Prozess- oder eingebetteten 3MF-Profilen
bleiben erhalten, auch wenn nur eine Achse vorgegeben ist. Unbekannte Modi und
andere Konturen oder Winkel werden nicht geraten. Die geschriebenen Koordinaten
gehen bei tatsächlich mehreren im G-Code verwendeten Werkzeugen in die
Einstellungsgegenprobe ein: Creality nullt den inaktiven Einfilament-Turm. Dabei
zählt die rückgelesene Werkzeugnutzung, nicht die Zahl deklarierter Spulen oder
eine möglicherweise unbekannte Eingangsbelegung. Ausdrückliche Sollwerte werden
immer verglichen; die Bauraumprüfung bleibt unverändert.

## Die Lüfterkurve

Alle drei Familien regeln den Bauteillüfter über der Schichtzeit: bis zur
Mindestzeit je Schicht mit dem oberen Wert, ab einer Schwelle mit dem unteren,
dazwischen linear. `CoolingSettings` führt dafür `fan_speed`,
`minimum_fan_speed`, `fan_below_layer_time` und `minimum_layer_time`;
`slicer_keys` schreibt sie je Familie unter ihren Namen:

| Solidon | Orca-Familie (Filamentprofil) | PrusaSlicer | Cura |
|---|---|---|---|
| `fan_speed` | `fan_max_speed` | `max_fan_speed` | `cool_fan_speed` → `cool_fan_speed_max` |
| `minimum_fan_speed` | `fan_min_speed` | `min_fan_speed` | `cool_fan_speed_min` |
| `minimum_fan_speed` > 0 | `reduce_fan_stop_start_freq` | `fan_always_on` | — (Cura hält den unteren Wert immer) |
| `fan_below_layer_time` | `fan_cooling_layer_time` | `fan_below_layer_time` | `cool_min_layer_time_fan_speed_max` |
| `minimum_layer_time` | `slow_down_layer_time` | `slowdown_below_layer_time` | `cool_min_layer_time` |

`handover._fan_curve_in_order` deckelt den unteren Wert am Anfang von
`as_mapping` auf den oberen — die eine Stelle für Profildateien, 3MF-Beilage
und Gegenprobe. Die Rücklesetabellen in `slicer_profiles` lesen beide Enden
und die Schwelle aus Herstellerprofilen zurück; eine Spule mit eigenem Profil
fährt so Elegoos 50…100 % statt eines festen Werts. Eine Projektdatei ohne
`minimum_fan_speed` und `fan_below_layer_time` behält ihren einen alten
Lüfterwert als oberes Ende und ergänzt unteres Ende und Schwelle beim Öffnen
aus dem Material des Projekts bzw. der Spule — über `print_settings.fan_curve`,
dieselbe Herleitung wie bei einem neuen Projekt, gedeckelt auf das obere Ende
(`serialise._group_from_data`); ohne Formatsprung, weil ein älteres Programm
die zwei Schlüssel still übergeht. Gemessen am 23.09.2026 mit ElegooSlicer,
OrcaSlicer, PrusaSlicer und CuraEngine; die Regel dazu steht in
`.claude/rules/dateiformat.md`.

## Die vier Gegenproben nach dem Lauf

`slice_model` fragt vier Mal, ob die Druckdatei den Auftrag wirklich enthält.
Jede sieht etwas, das die anderen durchlassen:

| Prüfung | Frage |
|---|---|
| `off_the_bed` | Liegt der Druck im Bauraum? |
| `too_short` | Ist das ganze Modell darin, oder wurde unten abgeschnitten? |
| `verify_settings` | Hat der Slicer die geschriebenen Werte übernommen? |
| `spools_left_out` | Sind **alle übergebenen Spulen** gedruckt worden? |

Die vierte fragt gegen `expected_tools`, und das kommt aus
`threemf.tools_in_use` — den Werkzeugen, die die **Flächen** einer Platte
benutzen, nicht den deklarierten Slots. Ein Körper darf einen Slot tragen, den
keines seiner Dreiecke benutzt; gegen die Deklaration geprüft, meldete jeder
solche Druck eine verlorene Spule. Ohne `expected_tools` entfällt der
Vergleich, und für Familien ohne Filamentprofile je Spule schweigt sie ganz —
dort sagt `unreachable_overrides` dasselbe schon vor dem Lauf.

`crashed` unterscheidet einen Prozessabsturz von einer regulären Absage des
Slicers, damit die Fehlermeldung den tatsächlichen Prozessausgang benennt.
POSIX zählt Signale negativ, Windows meldet einen `NTSTATUS` mit Fehlerschwere
und freiem reserviertem Bit 28. Als DWORD gelieferte eigene Fehlercodes wie
Bambus `-100` bleiben reguläre Absagen, auch wenn ihre Zahl größer ausfällt.

## Warum `slicer_keys.py` existiert

Weil dieselbe Einstellung in Cura, PrusaSlicer, OrcaSlicer und ElegooSlicer
vier verschiedene Namen hat. Eine Übersetzungstabelle an einer Stelle ist der
Preis dafür, dass §29 überhaupt einlösbar ist — verstreute Sonderfälle wären
es nicht.

Drei Familien übersetzen: `prusa` (PrusaSlicer, SuperSlicer),
`orca` (OrcaSlicer, Bambu Studio, ElegooSlicer, **Creality Print** ab Version 6)
und `cura` (CuraEngine). `FLAVOUR_BY_NAME` ordnet über den Dateinamen zu;
`flavour_of` ist die einzige Stelle, an der ein Programm zu einer Familie wird
— und was es nicht kennt, ist seit RM-071 die vierte Familie `other`: ein
Programm, das die Datei nur ins Fenster bekommt (§29, zweite Übergabeart;
ChituBox, Lychee, die Hersteller-Slicer der Resin-Drucker). `detect` wirft
nicht mehr; jedes Prädikat antwortet für `other` mit „nein“, es bekommt STL
um den Ursprung, `slice_model` und `write_config` sagen mit Vorschlag ab
(`_refuse_untranslated`), und `only_opens` ist die Frage dazu.

## Der Slicer wird gerufen, nie mitgeliefert

**Keine GPL-Abhängigkeit** (Regel 15). Ein externer Aufruf ist erlaubt, ein
mitgeliefertes Binärprogramm nicht. Deshalb sucht `slicer_profiles.py`, was
installiert ist, statt etwas mitzubringen.

## Die Prüfung vor dem Export

`wants_bed_coordinates` beschreibt die ausgegebenen Maschinenkoordinaten;
`needs_bed_translation` beschreibt getrennt die Eingabe. CuraEngine versetzt
ein zentriertes STL selbst, Prusa- und Orca-Projekte erhalten versetzte Punkte.
Ein fehlgeschlagener Anordnungsversuch gilt nur für seinen Auftrag. Erst eine
ausdrückliche Ablehnung der CLI-Option wird für weitere Aufträge gemerkt.

Unbrauchbare Bett- und Sperrkonturen der Druckdatei bleiben als Warnung im
Prüfbericht. Ein gleichzeitig nachgewiesener Bauraumübertritt hat Vorrang und
trägt den Profilrückfall oder die ausgelassene Sperre als Einzelheit mit.

Cura kennt keine Lüfterpause, nur einen Hochlauf vom Anfangslüfter bis zu
einer Höhe. `_cura_fan_start` schreibt beides (Anfangslüfter null, Höhe in
der Mitte der ersten Schicht nach der Pause) auf die Einstellungsseite, damit
auch das Cura-Fenster es bekommt; `_full_fan_layer` rechnet daraus für die
Konsole Curas Formel für `cool_fan_full_layer`. Für null und eine Schicht ist
das die Pause selbst, ab zwei laufen die Schichten dazwischen an — nur dann
nennt `slicer_keys.limitation` vorher einen Satz (`LIMITED`). Kurze Schichten
kühlt Cura auch in der Pause stärker; das hängt an der Schichtzeit und zeigt
erst die Druckdatei. Nach dem Slicen misst deshalb `fan_in_off_layers` den
Lüfterstart (`GcodeAnalysis.fan_start`) und meldet ihn mit Herkunft G-Code,
statt vorher pauschal zu warnen.

Sie läuft **vorher**, nicht nachher: Wasserdichtheit, Bauraum, Wandstärken.
Was sie findet, ist ein Befund mit Handlungsvorschlag (Regel 17) — kein
abgebrochener Export.

**Zwei der fünf Fragen aus §29 stehen in keinem einzelnen Körper**, und
deshalb nimmt `check_before_export` seit dem 12.09.2026 die Szene entgegen
(RM-140): Eine verletzte Passung steht zwischen zwei Merkmalen
(`scene.fits.check`), eine Wand unter der Mindeststärke zwischen einer Bohrung
und dem Mantel um sie herum (`scene.evaluate.check_thin_walls`, RM-127). Die
Prüfung sah bis dahin nur die **Auswahl**, und damit lagen diese zwei Zeilen
des Bauplans seit je brach.

Gefragt wird an der ganzen Szene, geantwortet über die Auswahl: Eine Passung,
deren zweite Hälfte nicht mit exportiert wird, muss dennoch aufgelöst werden —
sonst käme „Merkmal verloren" zurück, und das ist eine andere Aussage. Ohne
Szene bleiben beide Fragen ungestellt; ein Aufrufer, der keine hat, bekommt
den Bericht, den er belegen kann, und keinen erfundenen (Regel 21). Der Import
liegt dafür in der Funktion — `export → scene` ist eine **träge** Kante und
steht so in `tests/test_core_package_direction.py`.

`check_before_export(..., cancelled=...)` reicht denselben Abbruchvertrag an
die aktuelle Körperprobe aus `scene.fits.check` weiter. Kollision und
gemischte Netznäherung werden wie in der Auswertung berichtet — eine leere
Verschneidung und eine unbelegte Einbaulage sind kein Befund (21.09.2026);
ein Abbruch liefert keinen halben
Exportbericht. Eine Passungsbeziehung wird für jeden ausgewählten Partner
gemeldet, auch wenn nur der Stift und nicht die im Befund fokussierte Öffnung
exportiert wird. Unbeteiligte Körper übernehmen diesen Befund nicht.

**Und `checked` nimmt einen Bericht entgegen, statt ihn zweimal zu erheben.**
Die Oberfläche prüft, zeigt, fragt und schreibt erst dann (siehe
`app/ui/CLAUDE.md`); die Prüfung ist der teure Teil, und ein zweites Ergebnis
wäre auch ein zweiter Zustand. Eine **leere** Liste ist dabei eine Antwort und
kein fehlender Wert — geprüft wird auf `None`.

## Grenzen

- **Kein G-Code wird geschrieben** (§22). Das ist Sache des Slicers.
- Kennzahlen aus Schichtanalyse und G-Code bleiben getrennt (Regel 14).
