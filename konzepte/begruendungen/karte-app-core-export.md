# Begründungen zu `app/core/export/CLAUDE.md`

> Stand 27.09.2026. Aus der Karte verschoben, als sie auf Module, Einstiege
> und die einzuhaltenden Verträge verdichtet wurde. Die Karte steht dort;
> hier stehen die ausführlichen Beschreibungen, Messwerte und Anlässe ihres
> Tages — wörtlich, gegliedert nach den Überschriften der Karte. Die Absätze
> stammen aus der letzten gesicherten Fassung vor der Verdichtung (`main`);
> „Früher unter …“ nennt den Abschnitt, in dem ein Absatz dort stand.
>
> Der Abschnitt „Der Slicer wird gerufen, nie mitgeliefert“ steht in der Karte
> als Satz im Kopf; die Absätze, die früher alle unter „Die Karte“ standen,
> ordnet die Karte jetzt nach Gebieten; vier davon stehen unter
> „Stolperfallen“.

## Vorspann

Dateien schreiben, Plattenbelegung, Übergabe an den Slicer (§29).

Die Regeln stehen in `.claude/rules/dateiformat.md`.

*Früher unter „Die Karte“.*

STEP geht über `brep/step.py`, nicht von hier.

*Früher unter „Der Slicer wird gerufen, nie mitgeliefert“.*

**Keine GPL-Abhängigkeit** (Regel 15). Ein externer Aufruf ist erlaubt, ein
mitgeliefertes Binärprogramm nicht. Deshalb sucht `slicer_profiles.py`, was
installiert ist, statt etwas mitzubringen.

## Die Karte

| Datei | Rolle |
|---|---|
| `writer.py` | Export und **die Prüfung, die davor läuft** (§29, §16.3); `default_scheme` nennt das Namensmuster, nach dem ohne eigene Angabe benannt wird — das Fenster zeigt es im Dateidialog (RM-141). `mesh_for_export` vernetzt einen exakten Körper so fein, wie das Verfahren des Druckers es verlangt (`Profile.export_deflection`: ein Achtel des kleinsten Details, gedeckelt von der Zahl des Kerns — FDM bleibt bei 0,05 mm, ein Resin-Drucker mit 50-µm-Pixeln bekommt 0,006), an allen drei Stellen des Schreibers; `export.tessellated` nennt das Maß. Bei einem Resin-Drucker lässt `write_assembly` den FDM-Satz fallen: keine Haftungs- und Filamentbefunde, keine Beilage |
| `threemf.py` | 3MF **schreiben** — ein Körper oder eine Baugruppe, mit Farbgruppen und Slicer-Beilagen (§20, §29); `AssemblyPart.support_blocker` legt eine Stützsperre an — für die Orca-Familie als eigenes Teil (`support_blocker` in `model_settings.config`), für PrusaSlicer als Bereich im Netz (`SupportBlocker` in der Prusa-Beilage, dazu `slic3rpe:Version3mf`), je nach `blocker_as_part`. Gelesen wird in `ingest/threemf.py` |
| `handover.py` | Übergabe an den Slicer (§29, §28.1); `prusa_values` schreibt für PrusaSlicer die Kette seines Bündels samt Abweichung, für Konsole und 3MF-Beilage |
| `manufacturer.py` | **Die Grundlage aus dem Herstellerprofil**: `base_settings` liest Prozess, Filament und Maschine des gewählten Slicerprofils in Solidons Felder zurück (`ORCA_PROCESS`, dazu `slicer_profiles.FILAMENT_READBACK`), mit den eingebauten Vorgaben der vier Orca-Programme (`PROGRAM_DEFAULTS`, gemessen), der Druckplatte (`default_plate`, `PLATE_TEMPERATURES`) und dem Gemessenen (`Foundation.measured`); über dem Standardprozess die Werte der gewählten Stufe (`STAGE_PATHS`, `Foundation.staged`); die Platten, für die das Filament eine Betttemperatur nennt (`plate_temperatures`), ob der Drucker eine Plattenwahl hat (`offers_plates`); `written_paths` sagt, was die Übergabe davon schreibt, `findings`, was der Kunde über Platte und unlesbares Profil wissen muss. Für PrusaSlicer löst `prusa_chain` Drucker, Prozess und Filament des Bündels auf (`PrusaChain`), `PRUSA_PROCESS` und `PRUSA_PROGRAM_DEFAULTS` lesen sie zurück, samt Tempi in Prozent, erster Schicht, Stützwinkel „automatisch" und Rückzug am Filament |
| `slicer_keys.py` | Wie eine Solidon-Einstellung in **jedem** Slicer heißt |
| `slicer_profiles.py` | Die Profile finden, die ein installierter Slicer mitbringt; ein Durchgang liest jede Datei einmal (`ProfileDocuments`, geteilt von Auswahl, Namensindex und Erbkette). Den Prusa-Bestand hält `_prusa_store` über Aufrufe hinweg, solange keine Bündeldatei sich ändert; `identity` ist die Kennung eines Profils in einer Auswahl |
| `prusa_conditions.py` | PrusaSlicers Verträglichkeitsbedingungen (`printer_model=~/…/ and nozzle_diameter[0]!=0.8`) mit eigenem Parser, ohne `eval` (Regel 10); `slicer_profiles` bindet damit Prusa-Prozesse und -Filamente an den Drucker (`_prusa_fits`) |

Der SCAD-Ausgabeweg von CLI und Bausteinkatalog läuft über
`writer.export_part_scad`: erst `activation.require(EXPORT)`, dann die
Textkonvertierung. Damit liegt er in derselben vom Manifest gedeckten Grenze
wie die anderen Exporte. `knowledge.parts.scad.to_scad` bleibt als Teil der
MIT-Bibliothek unabhängig verwendbar.

## Auf dem Herstellerprofil schreibt die Übergabe nur die Abweichung

*Früher unter „Die Karte“.*

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
unteren Ende); „Automatisch" als Haftung heißt bei PrusaSlicer ohne Bündel
und bei Cura die Art aus Solidons Tabelle (`_adhesion_for`), über Prusas
Bündel die Vorgabe des Profils. Für PrusaSlicer schreibt `prusa_values` die
aufgelöste Kette von Drucker, Prozess und Filament samt Abweichung — in
`write_config` für die Konsole, in `writer._plate_config` für die Beilage;
ohne Drucker des Bündels Solidons ganzen Satz wie bisher. Die Gegenprobe
hält die eigenen Werte und eine Stichprobe der Grundlage
(`FOUNDATION_SAMPLE`, bei PrusaSlicer `PRUSA_FOUNDATION_SAMPLE` und
`PRUSA_IDENTITY`; Listen je Düsenvariante über `_printed`);
`foundation_findings` meldet Platte und unlesbares Profil in Slicen und
Export.

**Ohne Herstellerprofil bekommt jede Rolle Solidons Wert** (RM-191):
PrusaSlicer schreibt Solidon
volle Füllung und Lücken (`solid_infill_speed`, `gap_fill_speed`) und setzt
`machine_limits_usage = ignore`, damit die Zeitschätzung nicht mit
erfundenen 1 500 mm/s² rechnet; die Orca-Familie bekommt dieselben zwei
Geschwindigkeiten und die Bahnbreite für alle fünf Rollen. Bambu Studio sagt
seine Absage nicht auf der Konsole, sondern in `result.json` neben der
Druckdatei (`return_code`, `error_string`); `_result_reason` hängt sie an die
Ausgabe, nur aus dem Lauf, der gerade war.

## Stützsperre und Cura

*Früher unter „Die Karte“.*

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

*Früher unter „Die Prüfung vor dem Export“.*

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

## Profile, Spulen, Farben

*Früher unter „Die Karte“.*

Die Erhebung eingelegter Slicerfilamente nimmt einen `CancelToken` an.
Orca-Dateisuche, Namensindex und Vererbung sowie Prusa-Dateien und Abschnitte
prüfen ihn zwischen ihren Schritten; auch das Einsammeln vor dem Sortieren
bleibt abbrechbar. Ein Abbruch liefert keinen unvollständigen Profilbestand.

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

`bind_slot_profiles` übernimmt alte Profilpositionen an der ursprünglichen
vollständigen Szene in `slot_profile_bindings`. `configured_slots` verwendet
anschließend diese Identitäten; ein leeres gebundenes Tupel hat ausdrücklich
keine Profilwahl. Nur `None` liest noch die alte Positionsfolge. Export und
Verbrauchsplanung benutzen dieselbe Auflösung, auch nach Abwahl, Undo,
Plattenwechsel oder Auswahl-Export.

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

Ein mehrfarbiges Filament (`MaterialSlot.extra_colours`) geht an die
Orca-Familie als `filament_multi_colour` — alle Farben in einer Zeichenkette
mit Leerzeichen, die erste zugleich in `filament_colour` — und
`filament_colour_type` „1" (Abschnitte, kein Verlauf). Die zwei Schlüssel
stehen nur, wo eine Spule mehrere Farben hat; in der Projektdatei dann für
jede Spule der Platte, weil dort je Extruder eine Liste steht. Beide gehören
zu `_RECOMPUTED`: Der G-Code führt sie nicht. `ingest/threemf.py` liest
denselben Schlüssel zurück. Prusa und Cura kennen eine Farbe je Filament und
bekommen die erste.

## Was hinausgeht, stimmt

*Früher unter „Die Karte“.*

Objektbezogene Druckvorschläge werden vor der Formatwahl ausgewertet. Eine
STL-Übergabe meldet nicht übertragbare Werte als Warnung mit dem konkreten
Vorschlag; sie behauptet keine angewendete Einstellung. 3MF nennt die
tatsächlich mitgeschriebenen Abweichungen als Information.

Geometrieblöcke ersetzen ausschließlich vollständige `<mesh>`-Platzhalter.
Titel, Körper- und Materialnamen bleiben XML-maskierte Nutzerdaten, selbst
wenn sie eine der zufälligen Geometriemarken enthalten. Die Gegenprobe liest
die erzeugte 3MF wieder ein und prüft Namen, Materialien und Geometrie.

`handover.values_for` prüft sämtliche zusammengeführten Einstellungen auf
Zeilentrenner, bevor sie den gemeinsamen Weg verlassen. Damit gilt dieselbe
Grenze für Slicer-Konfigurationen und eingebettete Prusa-3MF-Einstellungen.
Nach dem Ergänzen von Profilwerten wird an der Schreibstelle erneut geprüft.

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

Die Konsolen von OrcaSlicer, ElegooSlicer, Bambu Studio und Creality Print
bekommen fehlende Reinigungsturmkoordinaten aus `_orca_cli_tower_position`.
Crealitys bekannter Herstellermodus bleibt maßgeblich. Ohne Modus beginnt der
Turm bei rechteckigen Betten unten, bei 0 Grad links und bei 90 Grad rechts:
Die gedrehte Tiefe wächst nach links. Der Rand beträgt die vorhandenen 15 mm
Freiraum zuzüglich der nativen Brimbreite. Passt bereits die bekannte Breite
mit beiden Rändern nicht oder verbrauchen die Ränder die andere Bettachse,
bleiben die Koordinaten aus; ein geklemmter Wert würde keinen Platz schaffen.

Sperrflächen der Maschine (`bed_exclude_area`) rücken den Anfang quer zur
Tiefe hinter sich, mit demselben Rand (`_beside_the_exclusions`): Bambu P1S,
P1P, X1 und X1 Carbon sperren vorn links 18 mal 28 mm, genau dort, wo der Turm
sonst begann. In der Slicer-Matrix (RM-312) reichte er am P1S mit Bambu Studio
bis x = 17,2 mm hinein, und Solidons G-Code-Prüfung meldete den eigenen Turm
als `gcode.off_the_bed`; nach der Regel beginnt er bei x = 36. Weil die Tiefe
erst der Slicer kennt, zählt jede Sperrfläche, die quer zur Tiefe die
Turmbreite samt Rand überlappt. Eine unlesbare Sperrfläche oder ein Turm, der
neben keiner passt, lässt die Lage beim Slicer.

Fehlt `prime_tower_brim_width`, gilt der Herstellerstandard **3 mm** aus
`PrintConfig.cpp`: [OrcaSlicer v2.4.0](https://raw.githubusercontent.com/OrcaSlicer/OrcaSlicer/v2.4.0/src/libslic3r/PrintConfig.cpp),
[ElegooSlicer](https://raw.githubusercontent.com/elegooofficial/ElegooSlicer/main/src/libslic3r/PrintConfig.cpp),
[Bambu Studio v02.02.01.60](https://raw.githubusercontent.com/bambulab/BambuStudio/v02.02.01.60/src/libslic3r/PrintConfig.cpp)
und [Creality Print](https://raw.githubusercontent.com/CrealityOfficial/CrealityPrint/master/src/libslic3r/PrintConfig.cpp)
setzen ihn mit `ConfigOptionFloat(3.)`. Die installierten Orca- und
Elegoo-Fassungen bestätigen ihn im G-Code auch ohne Schlüssel im Prozess.
Ein ausdrücklich negativer Wert bezeichnet dagegen eine automatische Breite;
ohne bekannten Herstellermodus bleibt er ebenso wie ein ungültiger Wert ohne
ergänzte Position.

Explizite Koordinaten aus Maschinen-, Prozess- oder eingebetteten 3MF-Profilen
bleiben erhalten, auch wenn nur eine Achse vorgegeben ist. Unbekannte Modi und
andere Konturen oder Winkel werden nicht geraten. Die Initialposition ist
keine Platzgarantie: Tiefe, Rippen und Reinigungsvolumen bestimmen die
tatsächliche Turmfläche erst beim Slicen; Bauraum und Sperrflächen prüft
danach weiterhin die G-Code-Bauraumprüfung. Die geschriebenen Koordinaten gehen bei tatsächlich
mehreren im G-Code verwendeten Werkzeugen in die
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

Bei Cura legt `manufacturer.cura_fan_curve` unteres Ende und Schwelle aus der
Druckerdefinition in die Grundlage (`CURA_FAN_PATHS`), auch je Spule
(`handover._resolve_slot`); das Fensterprofil nennt beide nur als eigene Wahl
(`handover._without_curas_own_fan_curve`), damit Curas Formel und
Qualitätsstufe gelten (RM-228).

## Die vier Gegenproben nach dem Lauf

**Maskierte Anführungszeichen.** `verify_settings` und `profile_differences` gleichen `\"` und `"` nur bei
Schlüsseln ab, die mit `_gcode` enden. Bei anderen Einstellungswerten bleibt
ein wörtlicher Backslash erhalten.

`slice_model` fragt vier Mal, ob die Druckdatei den Auftrag wirklich enthält.

Vor dem Prozessstart prüft es den unveränderten Netzsatz der einzelnen Platte.
`_prepare_plate` verwendet dafür `mesh_for_export`, dieselbe feinere Vernetzung
wie der Schreiber. `_SliceWorker` reicht genau diesen Satz weiter. Wer nur
Dateipfade übergibt, verwendet die begrenzten STL-/3MF-Leser beziehungsweise
Curas Netzliste ohne Hilfskörper. Ein bloßer Versatz sperrt den Lauf nicht;
`size_excess` prüft mögliche Z-Drehungen. Wenn der vorhandene Packweg für
mehrere Teile keine Anordnung auf einer Platte findet, lautet die Meldung
genau so: Die Heuristik beweist keine mathematische Unmöglichkeit.

Auch der positive Wert aus `size_excess` ist allein kein Beweis: Das Raster
prüft ganze Grad, und ein Sperrzonen-Sentinel bedeutet nur eine erfolglose
Platzierungsprobe. Vor der harten XY-Absage gilt deshalb die Schranke aus
`size_excess_uncertainty`: Bei Winkelraster h ändert sich die Breite gegenüber
der nächsten Probe höchstens um `2 D sin(h/4)`, mit D als XY-Diagonale des
Hüllquaders. Nur ein darüber hinausgehender Überstand belegt Nichtpassen.
Kleine Restüberstände bleiben unentschieden und dürfen zum Slicer. Die Höhe
wird getrennt gemessen. Die 3MF-Vorprüfung lässt abgeschaltete Build-Instanzen
aus; beim normalen Import bleiben sie editierbar.

Jede sieht etwas, das die anderen durchlassen:

| Prüfung | Frage |
|---|---|
| `off_the_bed` | Liegt der Druck im Bauraum? |
| `too_short` | Ist das ganze Modell darin, oder wurde unten abgeschnitten? |
| `verify_settings` | Hat der Slicer die geschriebenen Werte übernommen? |
| `spools_left_out` | Sind **alle übergebenen Spulen** gedruckt worden? |

`too_short` zählt mit den Netzen der Platte nur, was über der gedruckten
Höhe noch eine Bahnbreite trägt (`_printable_above`): Eine Oberkante, die als
Schneide ausläuft, druckt ein Slicer mit festen Bahnbreiten nicht. An
`bottom-single.stl` (Slicer-Matrix, RM-312) endeten ElegooSlicer, Bambu
Studio und SuperSlicer bei 78,0 statt 78,49 mm, und der Befund schickte den
Kunden mit *Auf das Bett legen* zu einem Teil, das auf dem Bett lag.

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

## Gemeinsame Netze und Anordnung für die Konsole

`prepare_slicer_meshes` vernetzt einmal je ausgewähltem Körper. Der Writer
und die spätere Bauraumprüfung bekommen dieselben Netzinstanzen. PrusaSlicer,
SuperSlicer und CuraEngine brauchen eine fertige Lage; die vier Programme der
Orca-Familie ordnen selbst an. Diese Eigenschaft steht in `arranges_on_cli`.

Eine bereits passende Platte bleibt unverändert. Andernfalls sucht der Writer
aufrechte Z-Drehungen und packt die Teile mit der vorhandenen Anordnung auf
genau eine Platte. Die reale Druckkontur, Sperrflächen und freigegebene Höhe
entscheiden. Verschoben werden nur Exportkopien; Szenenobjekte, Materialslots
und benannte Merkmale bleiben erhalten. Jede Projektplatte wird getrennt
behandelt. Curas Stützsperren folgen derselben exportierten Lage und erhalten
den Maschinenversatz genau einmal.

Die gepackte Lage hält nur, wenn der Slicer sie nicht wieder verwirft.
SuperSlicer 2.5 ordnet auf der Konsole ohne `--dont-arrange` jede Eingabe
selbst an, auch eine 3MF mit gültiger Lage, und zwar bis an den Bettrand ohne
Platz für die Skirt: In der Slicer-Matrix (RM-312) lief sie am MINI bei
y = -1,41 mm vom Bett, obwohl Solidons Anordnung 8,7 mm Rand ließ. PrusaSlicer
2.9 hielt die Lage auch ohne den Schalter und nimmt ihn an. Gesetzt wird er
wie `--arrange 0` der Orca-Familie nur bei haltender Anordnung.

Die Orca-Familie ordnet auf der Konsole selbst an, verschiebt dabei aber nur.
Die Größenprüfung vor dem Lauf lässt ein Teil durch, das gedreht auf das Bett
passt; ungedreht sagte der Slicer dann mit -50 ab. In der Slicer-Matrix
(RM-312) war das eine Schüssel von 240 mal 200 mm, die auf das 220er-Bett von
K1 und Kobra 2 nur um rund 14,5° gedreht passt. Deshalb dreht
`_turned_for_cli` die Exportkopie eines solchen Teils mit denselben
Kandidaten wie die Packung (`_cli_turns`); was ungedreht irgendwo Platz hat,
bleibt unberührt, denn die Lage gehört dort dem Slicer. Creality Print 7.3
ordnet auf der Konsole selbst neu an und verlangt dabei gemessen gut einen
Millimeter Rand je Seite (0,9 mm reichten nicht, 1,25 mm schon); ein Teil,
das das Bett bis auf weniger füllt, sagt es weiter mit -50 ab.

Eine Drehung sucht zuerst eine Lage, um die der Rand der Haftung
(`rim_reach`) noch auf dem Bett liegt, erst dann eine ohne ihn. Die erste
passende Drehung lag sonst knapp am Rand: drill-holder.3mf (185 mal 34,6 mm)
stand am MINI 1,4 mm davor, SuperSlicers Skirt lief 2,2 mm über das Bett,
obwohl schräg gestellt 12 mm frei waren (RM-312). Druckdialog und Schreiber
geben denselben Rand mit, sonst planten sie zwei Netzsätze.

Eine erfolglose Suche beweist keine mathematische Unmöglichkeit. Die Meldung
sagt daher, dass keine Anordnung gefunden wurde, und bietet die vorhandene
projektweite Anordnung oder die Druckerwahl an. Der Abbruch wird vor und nach
dem synchronen Packer geprüft. Der normale Datei- und Fensterweg wird nicht
automatisch gepackt; das gemeinsame Prädikat zur Lageübernahme berücksichtigt
aber auch dort Druckkontur, Sperrzonen und nutzbare Höhe. Ein bekannter
Bauraumgrund hält vor dem Prozessstart an; Datei- und Fensterübergabe behalten
ihren Berichtweg.

**Die Orca-Familie ordnet an, aber sie dreht nicht** (04.10.2026, RM-281
Nachtrag). Die Waschschüssel aus dem Korpus (240 auf 200 mm) passt auf
220 auf 220 mm nur schräg, mit 0,15 mm Rand. Gerade übergeben lehnten Creality
Print (K1) und OrcaSlicer (Kobra 2) sie ab; die Vorprüfung ließ sie durch, weil
der Überstand von 0,12 mm unter der Unsicherheit des Winkelrasters lag. Seitdem
packt Solidon eine Platte auch für die Orca-Familie selbst, sobald ein Teil nur
gedreht passt, und gibt die Lage vor; OrcaSlicer rechnete die schräg
übergebene Schüssel mit `--arrange 0`, den Brim schnitt es am Bettrand ab.
Creality Print nimmt über die Konsole keine Lage an und ordnet selbst an — mit
Abstand zum Rand: abgelehnt mit 0,15, 0,53 und 0,79 mm, gerechnet mit 1,04 und
1,25 mm (`CREALITY_ARRANGE_EDGE`). Darunter sagt `_check_creality_edge` vor dem
Lauf ab und bietet Verkleinern, einen anderen Slicer oder Drucker an.

## Die Prüfung vor dem Export

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

`wants_bed_coordinates` beschreibt die ausgegebenen Maschinenkoordinaten;
`needs_bed_translation` beschreibt getrennt die Eingabe. CuraEngine versetzt
ein zentriertes STL selbst, Prusa- und Orca-Projekte erhalten versetzte Punkte.
Ein fehlgeschlagener Anordnungsversuch gilt nur für seinen Auftrag. Erst eine
ausdrückliche Ablehnung der CLI-Option wird für weitere Aufträge gemerkt.

Unbrauchbare Bett- und Sperrkonturen der Druckdatei bleiben als Warnung im
Prüfbericht. Ein gleichzeitig nachgewiesener Bauraumübertritt hat Vorrang und
trägt den Profilrückfall oder die ausgelassene Sperre als Einzelheit mit.

## Grenzen

Bauraumfehler aus dem Schneideauftrag tragen einen Index in dessen Netzsatz.
`PlateRun.object_ids` ordnet diesen Index den eingefrorenen Szenenobjekten zu;
ohne eindeutige Zuordnung werden Teilen und Verkleinern nicht angeboten.
Der Druckdialog merkt Szenenhandlungen vor und gibt sie erst nach seinem
Abschluss an das Hauptfenster zurück. Vor der Meldung, beim Klick und bei
der Rückgabe wird der Druckkontext erneut verglichen. Ein älterer Auftrag
darf weder die aktuelle Auswahl noch eine inzwischen geänderte Szene bearbeiten.

Ein gleichzeitig abgebrochener Auftrag unterdrückt die nachlaufende Absage
im Arbeiter und vor der Anzeige. Die Bauraumhandlung „Verkleinern …“ öffnet
den vorhandenen Skalierdialog am ganzen betroffenen Körper; sie verspricht
keinen aus den Nennmaßen errechneten Faktor. Runde Bettkonturen und eine
begrenzte nutzbare Druckhöhe lassen sich daraus nicht sicher ableiten.
„Anordnen“ verwendet die vorhandene projektweite Operation; die Meldung
nennt deshalb ausdrücklich alle Projektteile. Ein Undo stellt deren vorherige
Platten und Lagen wieder her.

- **Kein G-Code wird geschrieben** (§22). Das ist Sache des Slicers.

- Kennzahlen aus Schichtanalyse und G-Code bleiben getrennt (Regel 14).

## Benutzte Filamente und alte Profilplätze (§29)

`threemf.merge_slots` übernimmt nur Filamentidentitäten mit Flächen. Seine
Option `include_unused=True` rekonstruiert ausschließlich die alte vollständige
Reihenfolge für `handover.bind_object_profiles`. Diese Bindung geschieht vor
Plattenwahl und Werkzeugneunummerierung, auch am unveränderlichen Auftrag des
Druckdialogs. Session, Dialog, Writer und Verbrauchsvorbereitung benutzen
denselben Helfer. Bereits vorbereitete Verbrauchsaufträge behalten ihre
damaligen Werkzeugnummern für das Rücklesen ihrer Druckdatei. Ein
gespeichertes Profil folgt danach seiner Identität; eine unbenutzte Deklaration
wird dadurch nicht zu einem benutzten Filament. Notwendige Werkzeuglücken eines
mehrteiligen Auftrags bleiben neutrale Plätze; fehlende Deklarationen benutzter
Flächen werden weiterhin ergänzt. Die Eingabeszene wird dabei nicht verändert.

## Objektwerte und native Rollen

Die Familie allein belegt keine Objektfähigkeit. `_part_paths` verwendet
die gemessene Programmmarke; ohne sie gilt die konservative Schnittmenge
der Familienmitglieder. `PartSplit.native` hält die wirksamen
Plattenrollen für Rücknahme und Begrenzung bereit. `_speed_roles` und
`_acceleration_roles` verwenden dieselbe Ableitung für Platte und Objekt.
Unbekannte Prusa-Programmmarken beachten beide gemessenen Kleinperimeter-
Vorgaben; vorhandene langsamere Rollen werden nicht beschleunigt.

Cura koppelt die erste Bahnbreite global an die reguläre Breite. Deshalb
bleibt `layers.line_width` dort plattenweit. Dichte und Stützschalter werden
mit ihren tatsächlich wirksamen Netzabhängigkeiten geschrieben. Ein global
nicht erfüllbarer Stützstil behält seinen Befund und erweitert nicht den
Stützschalter auf unbeteiligte Körper. Kanalsperren bleiben körperbezogen.
SuperSlicers fehlender Wandgenerator bedeutet Classic, Prusas Arachne.


## Ausdrücklich gewählte Prusa-Dateien (§29)

Die Erhebung darf beschädigte ungewählte Dateien überspringen. Die Auflösung
eines gewählten Profils verlangt dagegen ein lesbares Dokument und den
gewählten Abschnitt. Gültige Leere bleibt ein Delta; Lesefehler gehen über die
vorhandene Herstellergrundlage samt Befund in den vollständigen Drucksatz.
Der Profilcache beobachtet zusätzlich genau die gewählte Datei, auch außerhalb
der Bestandswurzeln. Ihr Ordner wird dadurch keine weitere Suchwurzel.

Der Cache speichert keinen Abbruchschalter. Jeder Abruf führt seinen Schalter
durch Lesen und Vererbung; ein nachgelesenes Dokument samt Namensindex wird
erst vollständig unter der bestehenden Sperre übernommen.


## Brim-Abstand am tatsächlichen Fuß (§29)

`AdhesionSettings.brim_gap` meint den Abstand am korrigierten Fuß. Die
Herstellergrundlage trägt den nativen Fußversatz für Konsole und Projekt-/
Objektwerte. Orcas aktiver Bezug zur korrigierten Kontur benötigt keinen
zusätzlichen Versatz. Unbekannter Bezug oder nativ nicht darstellbarer Abstand
hält mit dem Rückweg zu den Druckeinstellungen an. Creality Print legt den Brim um die
Erstschichtgruppen vor der Fußkorrektur (`Brim.cpp`, `firstLayerObjGroups`),
nimmt `brim_object_gap` nur von 0 bis 2 und kennt kein `brim_use_efc_outline`;
die Fußkorrektur ist dort aber ein Objektwert. Je Teil senkt
`manufacturer.part_brim_gap` deshalb die Korrektur genau dieses Teils auf den
gewünschten Abstand und schreibt nativ null; der Export sagt es mit
`export.brim_foot_lowered`. Gemessen an den Fahnenstangen (RM-318): Mittellinien
0,4676/0,4691 mm bei 0,50 mm Bahn, der breite Körper behält seine Korrektur.
Für die ganze Platte bleibt die Absage, denn die Korrektur aller Teile zu
senken ist keine Antwort auf einen Brim-Abstand. Ein inaktiver gespeicherter
Haftungswert bleibt ohne Wirkung. Unveränderte Herstellerwerte behalten ihre
native Schreibweise und verändern keine Fußgeometrie.

## Native Erstschichtabsagen

Ein Slicerprozess kann regulär enden und trotzdem keine Materialbahnen
erzeugen. Seine konkrete Ursache wird vor der allgemeinen Absage gelesen.
Die begrenzte vollständige Ausgabe bleibt für die Protokollhandlung erhalten;
Ursache und folgende Objektzeile müssen aus demselben Ausgabestrom stammen.
Ungültiges UTF-8 oder widersprüchliche Namen erlauben keine Objektbindung.
Eine tatsächlich extrudierende Druckdatei behält den Erfolgsweg.

Namen werden nicht normalisiert: Leerraum, Großschreibung und Zeichen gehören
zum Namen. Nur doppelte, leere oder mehrzeilige Namen erhalten in der privaten
CLI-Kopie eine eindeutige Kennzeichnung. `PlateRun.name_bindings` verbindet
genau diese ausgegebenen Namen mit den eingefrorenen Szenenkennungen. Das
Projekt und seine Materialzuordnung bleiben unverändert.

**Eine erste Schicht, schmaler als anderthalb Bahnen, ist eine eigene
Ursache** (`_first_layer_narrower_than_a_line`, Slicer-Matrix RM-312):
`Cat_2.stp` steht auf Stegen von höchstens 0,6 mm. Mit fester Bahnbreite
(Herstellerprozess des Centauri Carbon 2, MINI-Profil von SuperSlicer) legt der
Slicer dort keine Schleife; ElegooSlicer endet mit -100 und „found error“ ohne
Grund, SuperSlicer mit „no extrusions in the first layer“. Mit Arachne druckten
beide, ein Brim änderte nichts. Gefragt wird erst nach einer Absage, am
Querschnitt auf halber Höhe der ersten Schicht, nach innen um drei Viertel einer
Erstschichtbahn versetzt; die Meldung nennt die Wandbahnen und den Raft statt
*Auf das Bett legen*, und *Druckeinstellungen öffnen* hebt die Zeile der
Wandbahnen hervor. Bei veränderlicher Bahnbreite bleibt die Absage aus RM-483.

**-101 heißt: Bahnen kreuzen sich** (`ORCA_PATHS_CROSS`, Bambus
`CLI_GCODE_PATH_CONFLICTS`). Die Orca-Familie verwirft damit eine fertig
geschnittene Platte; an `chufang.3mf` (Slicer-Matrix RM-312) stieß nach der
eigenen Anordnung des Slicers der Reinigungsturm an ein Teil. OrcaSlicer sagt
auf der Konsole nur „found error“, Creality Print nennt Turm und Teil im
Protokoll, Bambu Studio den Turm in `result.json`. Der Satz nennt beide
Möglichkeiten und lässt die Ausgabe sagen, welche es war.



## Der Raftkontakt hat eine eigene Herkunft

Der Luftabstand zwischen Raft und Körper ist `adhesion.raft_gap`. Er ist kein
anderer Name für `support.z_gap`: Hersteller können beide Abstände unabhängig
vorgeben. Prusa und Orca lesen und schreiben `raft_contact_distance`, Cura
schreibt `raft_airgap`. Ein unbekannter Wert bleibt `None` und schreibt keinen
Schlüssel; ein ausdrücklich gewählter Abstand von null wird geschrieben.
Ohne belegte Grundlage wird keine Zahl als Herstellerwert angezeigt.

Die Aktivierung gehört zur Haftung und folgt `raft_gap_active`. Bei Prusa und
Orca erzeugt `raft_layers=0` keinen Raft. Curas `raft_surface_layers=0`
entfernt dagegen nur die Deckschichten, nicht die Raftbasis. Ein positiver
nativer Orca-Wert für `raft_layers` hat Vorrang vor seinem gleichzeitig
gespeicherten `brim_type`; dafür zählt ausschließlich die belegte Profilzahl,
nie die Schichtvorgabe der Dataclass.

Curas Definitionsleser bewahrt für `raft_airgap` und `layer_0_z_overlap` die
native Herkunft, bevor unbekannte Ausdrücke aus den Zahlenwerten entfallen.
Bei einer Maschineninstanz ergänzen dieselben Containerleser DefinitionChanges,
Variante, Qualität, Intent, Qualitätsänderungen und Nutzerwerte in ihrer
wirksamen Stapelreihenfolge. Es entsteht keine allgemeine Übernahme fremder
Prozesswerte. Die Kontakt-Herkunft bleibt getrennt von Extruder-Hardware und
der über `cura_motion` angeforderten Jerk-Auflösung.

Eine feste native Überlappung bleibt fest, auch wenn der Kunde den Raftabstand
ändert. Nur die ausdrücklich erkannte Kopplung `raft_airgap / 2` wird mit dem
neuen Abstand nachgeführt. Andere oder unbelegte Beziehungen halten die eigene
Raftwahl mit einem Handlungsvorschlag an; Profilformeln werden nie ausgeführt.
Ein einzelner lesbarer Kontaktwert macht aus Cura keine vollständig belegte
`Foundation`. Ohne solche Grundlage bleibt die Anzeige bei der Slicer-Vorgabe,
während eine ausdrückliche Raftwahl an die Übergabe gelangt.

Der Abstand wird an der ersten tatsächlich extrudierten Körperschicht in
Druckreihenfolge beurteilt: Bahnhöhe abzüglich ihrer Schichthöhe und der
Raftoberkante. Die niedrigste spätere Körperbahn ist dafür ungeeignet, weil
ein Slicer die Folgeschicht absenken kann. Native Schichtrundung und eine
unabhängige Stützschichthöhe bleiben Eigenschaften des gewählten Slicerprofils.

## Curas Lüfterkurve

Bei Cura kommen unteres Ende und Schwelle der Lüfterkurve aus der
Druckerdefinition (`manufacturer.cura_fan_curve`), nicht aus Solidons
Materialkurve: Deren PLA-Schwelle von 80 s hob den Lüfter schon in der ersten
Schicht an (RM-228).

## Die Außenkante der ersten Schicht (RM-312)

`build_area.rim_of` (früher `writer.rim_of`) rechnet, wie weit die erste Schicht über ein Teil
hinausreicht, und `check_adhesion_on_bed` warnt, wenn das über den Bettrand
oder in eine Sperrfläche geht. Drei Bausteine, jeder belegt:

- **Auto-Brim der Orca-Familie.** `configBrimWidthByVolumeGroups` in
  OrcaSlicers `Brim.cpp` (aus Bambu Studio übernommen) rechnet die Breite aus
  Höhe, Flächenträgheit und Wärmelänge der ersten Schicht und kappt bei
  18 mm, unabhängig von `brim_width`. ElegooSlicer legte am Rack 14,7 mm statt
  5 mm. Entscheidung zu RM-312: Steht der Brim beim Herstellerprofil auf
  „automatisch“, rechnet die Warnung mit 18 mm und bietet *Brim-Breite
  festlegen* an; wählt der Kunde „Brim“ oder übernimmt einen Vorschlag,
  schreibt Solidon `outer_only` mit Breite, und der Slicer wählt nichts mehr
  selbst. Zwischen zwei Teilen bleibt es bei der Brimbreite des Profils
  (`adhesion_margin`, Entscheidung J).
- **Stützfuß.** `raft_first_layer_expansion` verbreitert die erste Raft- und
  Stützschicht. Gelesen aus der Kette, sonst die gemessene Programmvorgabe
  (`manufacturer.SUPPORT_FOOT_DEFAULTS`: Orca, Elegoo, Creality 2 mm, Prusa
  und SuperSlicer 3 mm). Bambu Studio schreibt `-1`, Cura führt den Schlüssel
  nicht: unbekannt, und `arrange.support_foot_unknown` sagt das, statt eine
  Zahl zu schätzen. Gezählt wird der Fuß, sobald Stützen an sind — wo die
  Stütze das Bett berührt, weiß erst der Slicer.
- **Skirt.** Abstand und Bahnen aus dem Profil, außen um Brim oder Stützfuß.
  Prusa und Orca drucken ihn neben einem Brim, solange Solidon die
  Haftungsart nicht schreibt; schreibt es eine, nullt
  `handover._only_chosen_adhesion` die übrigen. Cura druckt nur eine Art.

Dieselbe Außenkante gibt `slicer_rim` der Drehung für die Konsole
(`_fit_cli_mesh`) als Rand mit, in Druckdialog und Schreiber gleich.
