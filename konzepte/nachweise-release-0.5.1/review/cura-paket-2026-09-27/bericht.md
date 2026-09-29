# Stufe D — CuraEngine bekommt seine Maschine (Bericht, fortlaufend)

Arbeitsbaum `F:\3D Druck.cura`, Zweig `cura-maschine`, abgezweigt von main
`cab9d6d30`. Konzept: `konzept-herstellerprofil-als-grundlage-2026-09.md`
(C, D, Stufe D); Befunde: `nachweise-herstellerprofil-2026-09/cura.md`.

Messwerkzeug: `cura_probe.py` in diesem Ordner — der Weg der Anwendung
(`lauf.imported_objects`, `lauf.advised`, `write_assembly`,
`handover.slice_model([pfad])` wie `_SliceWorker`), danach Auslesen des
G-Codes. Grundlinie: `vorher/` (git-archive-Kopie von `cab9d6d30`, damit
der sich ändernde Arbeitsbaum die Messung nicht verfälscht), nachher:
`nachher/`.

Modelle: Minigolf-Körper `F:\3D Dateien\Mini+Golf+All+Set-P1S_stls\obj_2_Gövde59.stl`,
Waschschüssel `F:\3D Dateien\HydroBowl+–+Smart+Fruit+&+Veggie+Washer (1)\washing bowl v1.stl`.
CuraEngine 5.13.0.

---

## Vorab gemessen

### CuraEngine löst die Erbkette selbst auf

Versuch (`scratchpad/erbkette/versuch.py`, Minigolf-Körper, Solidons 228 Werte):

| Aufruf | Ergebnis |
|---|---|
| `-j fdmprinter.def.json … -e0 -j fdmextruder.def.json` (heute) | `TARGET_MACHINE.NAME:Unknown`, fdmprinter-Startcode (`G28`, `G1 Z15`, `E3`) |
| `-j creality_k1max.def.json` ohne Suchpfad | Name „Creality K1 Max“ und K1-Max-Startcode kommen an (`creality_base`, `fdmprinter` liegen neben der Datei und werden gefunden); **aber** `Couldn't find definition file with ID: creality_base_extruder_0` / `creality_k1max_extruder_0` — die Extruderzüge liegen in `resources/extruders/` |
| `-d "<definitions>;<extruders>" -j creality_k1max.def.json` | keine Fehler, Extruderzüge geladen |
| `CURA_ENGINE_SEARCH_PATH="<definitions>;<extruders>"` | Extruderzüge **nicht** gefunden — die Umgebungsvariable trennt unter Windows nicht mit `;` |

Folge: Die Übergabe nimmt die Druckerdefinition mit `-d` für beide Ordner.
Die Extruderdefinition lädt CuraEngine aus `metadata.machine_extruder_trains`
selbst; ein zweites `-e0 -j fdmextruder.def.json` hätte ihre Vorgaben mit
denen von `fdmextruder` überschrieben und entfällt auf diesem Weg.

Was mit der Druckerdefinition zusätzlich gilt (`default_value` der Kette,
die Solidon nicht selbst schreibt; `scratchpad/erbkette/defaults.py`):

| Drucker | zusätzlich wirksam |
|---|---|
| K1 Max, SV06, Ender-3 V3 SE | Start-/Endcode, Maschinenname, Kopfumriss |
| Ender-3 V3 KE | dazu `material_print_temp_wait = false` |
| Kobra 2 | dazu `machine_gcode_flavor` (gleich), `machine_max_feedrate_*`, `top_bottom_pattern = zigzag` |
| Neptune 4 / 4 Plus | dazu `brim_gap 0.1`, `fill_outline_gaps false`, `minimum_interface_area 10`, `optimize_wall_printing_order true`, `z_seam_corner weighted`, Prime-Tower-Werte |

Die Maschinengrenzen stehen in den Cura-Definitionen fast überall als
`value` (ohne Anführungszeichen, also keine Formel) — CuraEngine liest sie
trotzdem nicht; es bleibt bei `fdmprinter`. Sie wirken nur auf die
Zeitschätzung.

### Materialverbrauch (B12, letzter Punkt)

Die Anwendung zeigt ihn bei Cura schon: `gcode._motion_fallback` rechnet die
Länge aus der E-Summe (Rückzug und Wiederförderung gleichen sich aus),
`GcodeMetrics.grams()` daraus die Masse, `gcode.findings_for` den Befund
`gcode.material` — gemessen am SV06-Lauf der Grundlinie: 18 359 mm, 54,8 g,
Quelle `motion`. `filament_g = null` im Prüfbericht war das Feld
`GcodeMetrics.filament_grams`, und das heißt „vom Slicer genannt“: Cura
nennt keine Gramm. Es bleibt deshalb leer (Herkunft, Regel 14 sinngemäß);
die Probe liest jetzt `grams()`. Kein Code geändert.

### Grundlinie (vorher, `cab9d6d30`)

Je Drucker PLA, Stufe Standard; „vorschlaege“ = alle Vorschläge übernommen wie im Druckdialog. „g“ ist leer, weil die Probe in dieser Reihe noch `filament_grams` las (siehe oben).

| Modell | Drucker | Lauf | Ergebnis | min | g | M190 | M109 | M420 S1 | START_PRINT | { im Kopf | M204 Schicht 1 | Leerfahrt S1 mm/s | Stütze m | Stützbew. | Modellbew. | Rollenfolge (Drittelschicht) | END_PRINT |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| bowl | centauri-carbon-2 | standard | ok | 559.7 |  | 1 | 1 |  |  |  | 5000,10000 | 125.0 | 0 | 0 | 1136529 | FILL>WALL-INNER>WALL-OUTER |  |
| bowl | centauri-carbon-2 | vorschlaege | ok | 1234.1 |  | 1 | 1 |  |  |  | 5000,10000 | 125.0 | 3229.5 | 409926 | 1138071 | SUPPORT>SUPPORT-INTERFACE>FILL>WALL-INNER>WALL-OUTER |  |
| bowl | creality-k1-max | standard | ok | 604.4 |  | 1 | 1 |  |  |  | 5000,10000 | 179.6 | 0 | 0 | 1136517 | FILL>WALL-INNER>WALL-OUTER |  |
| bowl | creality-k1-max | vorschlaege | ok | 1311.2 |  | 1 | 1 |  |  |  | 5000,10000 | 179.6 | 3222.4 | 405113 | 1138044 | SUPPORT>SUPPORT-INTERFACE>FILL>WALL-INNER>WALL-OUTER |  |
| bowl | elegoo-neptune-4 | standard | ok | 607.2 |  | 1 | 1 |  |  |  | 5000,6000 | 140.4 | 0 | 0 | 1136513 | FILL>WALL-INNER>WALL-OUTER |  |
| bowl | elegoo-neptune-4 | vorschlaege | ok | 1330.1 |  | 1 | 1 |  |  |  | 5000,6000 | 140.4 | 3229.3 | 415217 | 1138090 | SUPPORT>SUPPORT-INTERFACE>FILL>WALL-INNER>WALL-OUTER |  |
| golf | anycubic-kobra-2 | standard | ok | 100.2 |  | 1 | 1 |  |  |  | 700,2500,5000 | 16.9 | 0 | 0 | 277658 | WALL-INNER>WALL-OUTER>WALL-INNER>WALL-OUTER |  |
| golf | anycubic-kobra-2 | vorschlaege | ok | 100.2 |  | 1 | 1 |  |  |  | 700,2500,5000 | 16.9 | 0 | 0 | 277651 | WALL-INNER>WALL-OUTER>WALL-INNER>WALL-OUTER |  |
| golf | centauri-carbon-2 | standard | ok | 69.6 |  | 1 | 1 |  |  |  | 5000,10000 | 125.0 | 0 | 0 | 277658 | WALL-INNER>WALL-OUTER>WALL-INNER>WALL-OUTER |  |
| golf | centauri-carbon-2 | vorschlaege | ok | 69.6 |  | 1 | 1 |  |  |  | 5000,10000 | 125.0 | 0 | 0 | 277659 | WALL-INNER>WALL-OUTER>WALL-INNER>WALL-OUTER |  |
| golf | creality-k1-max | standard | ok | 73.5 |  | 1 | 1 |  |  |  | 5000,10000 | 179.6 | 0 | 0 | 277676 | WALL-INNER>WALL-OUTER>WALL-INNER>WALL-OUTER |  |
| golf | creality-k1-max | vorschlaege | ok | 73.5 |  | 1 | 1 |  |  |  | 5000,10000 | 179.6 | 0 | 0 | 277666 | WALL-INNER>WALL-OUTER>WALL-INNER>WALL-OUTER |  |
| golf | elegoo-neptune-4 | standard | ok | 73.2 |  | 1 | 1 |  |  |  | 5000,6000 | 140.4 | 0 | 0 | 277656 | WALL-INNER>WALL-OUTER>WALL-INNER>WALL-OUTER |  |
| golf | elegoo-neptune-4 | vorschlaege | ok | 73.2 |  | 1 | 1 |  |  |  | 5000,6000 | 140.4 | 0 | 0 | 277653 | WALL-INNER>WALL-OUTER>WALL-INNER>WALL-OUTER |  |
| golf | sovol-sv06 | standard | ok | 296.4 |  | 1 | 1 |  |  |  | 5000,8000 | 75.0 | 0 | 0 | 277659 | WALL-INNER>WALL-OUTER>WALL-INNER>WALL-OUTER |  |
| golf | sovol-sv06 | vorschlaege | ok | 296.4 |  | 1 | 1 |  |  |  | 5000,8000 | 75.0 | 0 | 0 | 277661 | WALL-INNER>WALL-OUTER>WALL-INNER>WALL-OUTER |  |


---

### Herstellerwerte für die neuen Druckerfelder (B2, B5, B7, B8)

Gelesen mit Solidons eigener Profilauflösung (`herstellerwerte.py`,
Ergebnis `herstellerwerte-*.json`). **Regel:** Jedes neue Feld kommt aus
**demselben Standardprozess wie die Tempi, die der Drucker schon trägt** —
sonst bezögen sich die Überhangstufen auf ein anderes Außenwandtempo als das,
mit dem Solidon druckt. Für Elegoo ist das ElegooSlicer, für Bambu Bambu
Studio, für Creality, Anycubic und Sovol der Bestand von OrcaSlicer (daher
stammen die Tempi vom 25.09.; für K1 und K1 Max sind Creality Print und
Orca gleich), für Prusa die Input-Shaper-Prozesse von PrusaSlicer, wie im
Auftrag verlangt.

| Drucker | Prozess | erste Schicht mm/s² | erste Bahn (× Düse) | Überhang 2/4, 3/4, 4/4 (mm/s → % Außenwand) |
|---|---|---|---|---|
| Centauri Carbon 2 | 0.20mm Standard @Elegoo CC2 | 500 | 0,5 mm → 1,25 | 50/30/10 bei 160 → 31/19/6 |
| Neptune 4, 4 Plus | 0.20mm Standard @Elegoo N4 / N4Plus | 500 | 1,25 | 31/19/6 |
| Bambu A1, A1 mini, P1S, X1C | 0.20mm Standard @BBL … | 500 | 1,25 | 50/30/10 bei 200 → 25/15/5 |
| Prusa MK4S | 0.20mm SPEED @MK4S 0.4 | 500 | 0,5 → 1,25 | 50/25/15 bei 170 → 29/15/9 |
| Prusa MINI+ | 0.20mm SPEED @MINIIS 0.4 | 500 | 1,25 | 25/20/15 bei 140 → 18/14/11 |
| Prusa XL | 0.20mm SPEED @XLIS 0.4 | 500 | 1,25 | 30/25/15 bei 170 → 18/15/9 |
| Creality K1, K1 Max | 0.20mm Standard @Creality K1 / K1Max (0.4 nozzle) | 1000 | 1,25 | 25/15/5 |
| Creality Ender-3 V3 | 0.20mm Standard @Creality Ender3V3 0.4 nozzle (Orca) | 500 | 1,25 | 25/15/5 |
| Ender-3 V3 SE (neu) | 0.20mm Standard @Creality Ender3V3SE 0.4 (Orca) | 500 | 0,46 → 1,15 | 20/15/10 bei 60 → 33/25/17 |
| Ender-3 V3 KE (neu) | 0.20mm Standard @Creality Ender3V3KE (Orca) | 1000 | 125 % → 1,25 | 50/35/10 bei 200 → 25/18/5 |
| Anycubic Kobra 2 | 0.20mm Standard @Anycubic Kobra2 (Orca) | 2000 | 0,8 → 2,0 | 20/15/10 bei 150 → 13/10/7 |
| Sovol SV06 | 0.20mm Standard @Sovol SV06 (Orca) | — (Prozess: 0 = keine Angabe) → 500 | 0,42 → 1,05 | 20/15/10 bei 25 → 80/60/40 |
| Allgemeiner 220 mm | — | 500 | 1,07 × Bahnbreite (wie bisher) | — → 50/25 |

PrusaSlicer führt Überhangtempi je Überdeckung (`overhang_speed_0` bei 0 %,
`_1` bei 25 %, `_2` bei 50 %, `_3` bei 75 %); Orcas Stufe 2/4 (25–50 %
Überhang = 75–50 % Überdeckung) bekommt das langsamere Ende, `_2`, 3/4 `_1`,
4/4 `_0`.

Creality Print 7.2 nennt für den Ender-3 V3 andere Werte als Orcas
Creality-Bestand (2000 mm/s², 0,55 mm, 30/20/10) und für den SE 60/30/10 bei
60 mm/s; genommen ist Orca, weil die Tempi dieser Drucker von dort stammen.

**Offener Widerspruch im Bestand (nicht von hier):** Die Tempi des MINI+
stammen aus dem abgelösten Prozess ohne Input Shaper (Außenwand 40 mm/s),
seine Stützgrenze (Paket 1) und die neuen Felder aus dem Input-Shaper-Prozess
(Außenwand 140 mm/s). Cura bremst Überhänge am MINI+ damit auf 18 % von
40 mm/s = 7 mm/s statt auf Prusas 25 mm/s. Die Tempi des MINI+ gehören
nachgezogen.

## Punkte

### 1. B1 — Start- und Endcode des Druckers

**Geändert.** `PrinterProfile.cura_definition` (types.py), gelesen und geprüft in
`profiles._printer_from_table` (nur `[A-Za-z0-9_]+`, weil daraus ein Pfad im
Definitionsordner wird und ein mitgebrachter Drucker aus einer fremden
Projektdatei kommt), eingetragen für `anycubic-kobra-2`, `creality-k1-max`,
`elegoo-neptune-4`, `elegoo-neptune-4-plus`, `sovol-sv06` (SE/KE mit B8, Punkt 8).
`handover._cura_machine` wählt die Druckerdefinition (sonst `fdmprinter`), liest
die Kette mit `slicer_profiles.resolve_values`, füllt Start- und Endcode
(`_filled`) und bestimmt die zwei Schalter (`_temperature_switches`, dieselbe
Regel wie `StartSliceJob.py`: Kommentare heraus, dann nach Temperatur-Platzhaltern
suchen). `write_config` legt die Schalter zu den Werten und die Codes in
`SlicerConfig.cura_machine`; `_command` setzt `-d "<definitions>;<extruders>"`
vor `-j <drucker>.def.json`, hängt Start- und Endcode als je ein `-s` an (mit
Umbrüchen — `solidon_cura.txt` trägt keine) und lässt `-e0 -j fdmextruder` weg,
wenn die Druckerdefinition ihren Zug selbst mitbringt. Neues Prädikat
`slicer_keys.machine_from_definition` (Cura). `machine_missing` sagt für Cura
jetzt `slicer.cura_printer_unknown`, wenn die Installation den Drucker nicht
führt (Kommentar „schweigt für Cura“ berichtigt); der Kommentar in
`_machine_keys` zu `MINX` ist richtiggestellt (der Kopf bleibt im
Konsolenbetrieb immer ein Platzhalter).

**Abweichung vom Auftrag, bewusst:** `{name}` und `{name, n}` sind reine
Textersetzung wie verlangt. Eine *Rechnung* im Platzhalter geht aber durch
Solidons eigenen Auswerter `app.core.expressions` (kein `eval`, Regel 10 nennt
genau diesen Weg), nur über Zahlen, die Solidon kennt. Grund, gemessen: Der
Endcode von `elegoo_neptune_4` (und des davon erbenden 4 Plus) trägt
`G1 X0 Y{machine_depth - 5}`. Mit reiner Textersetzung hielte jede
Cura-Übergabe an diese zwei Drucker an — ein Rückschritt gegenüber heute, und
die verlangte Messung am Neptune 4 wäre unmöglich. `{if …}`, `{print_time}`,
unbekannte Namen und alles außerhalb der Grammatik halten weiter an. Wer das
nicht will, löscht in `_filled` den Aufruf von `_arithmetic`; dann halten
Neptune 4 und 4 Plus an.

**Hashing:** `cura_definition` steht nicht in `profile_key`, sondern mit Grund
in `tests/test_cache.py::_PRINTER_FIELDS_NO_OPERATION_READS` („nur die
Cura-Übergabe, keine Geometrie“) — so steht es für alle Tempo- und
Übergabefelder, und genau das verlangt der Test (Schlüssel **oder** begründet).
Im Schlüssel entwertete das Feld ohne Anlass jeden Plattencache.

**Tests:** `tests/test_cura_machine.py` (neu, 21 Fälle, nachgebaute Installation
nach Cura 5.13; einer gegen die echte Installation, falls vorhanden):
Startcode des K1 Max mit Temperaturen, `-d` vor `-j`, kein `fdmextruder`;
Rechnung und `{name, 0}` und `print_temperature`; fünf Platzhalter, die
anhalten; fünf Fälle der Temperaturschalter (auch Platzhalter im Kommentar);
Centauri Carbon 2 mit `fdmprinter` und Befund; keine Definitionen → kein
Befund; ältere Installation ohne die Datei → wie unbekannt; vier ungültige
Kennungen; alle `cura_definition` der Tabelle sind installiert.
**Gegenprobe:** dieselbe Datei gegen `cab9d6d30` (git-archive-Kopie): 21 von 21
rot. `test_cura_and_prusa_are_not_warned…` heißt jetzt
`test_prusa_is_not_warned…` (Cura gehört dort nicht mehr hin);
`test_every_flavour_answers_every_property` kennt das neue Prädikat.

### 2. B2 — Erste Schicht mit eigener Beschleunigung (mit der Fahrbeschleunigung aus B11)

**Geändert.** `PrinterProfile.first_layer_acceleration` (types.py, gelesen über
`PRINTER_PACE_FIELDS`), eingetragen für alle benannten FDM-Drucker nach der
Tabelle oben (SV06: keine Herstellerangabe). In `handover._for_speeds`
`acceleration_layer_0 = min(Herstellerwert oder 500, acceleration_print)` und
`acceleration_travel_layer_0` gleich; `CURA_MIRRORED` hat eine eigene Zeile
`acceleration_layer_0 → acceleration_print_layer_0, acceleration_skirt_brim,
raft_base_acceleration`, und diese drei stehen nicht mehr unter
`acceleration_print`. Mitgenommen aus B11, weil Cura das eine aus dem anderen
rechnet: `acceleration_travel` spiegelt `acceleration_print` (der Eintrag in
`CURA_UNTOUCHED` entfällt, ebenso die Konstante `_TRAVEL_ACCELERATION = 5000`).
Curas Formel für die Leerfahrt der ersten Schicht,
`acceleration_layer_0 * acceleration_travel / acceleration_print`, ergibt
damit genau die Beschleunigung der ersten Schicht. Orca und PrusaSlicer
bekommen nichts (dort gilt das Herstellerprofil).

**Tests:** `test_the_first_layer_has_its_own_acceleration` (fünf Drucker, alle
vier Blätter und die Fahrt) — Gegenprobe gegen `cab9d6d30`: 5 von 5 rot;
`test_the_first_layer_is_never_faster_than_the_rest` (Deckel bei 300 mm/s²,
am alten Stand zufällig grün, weil dort alles der Druckbeschleunigung folgte).

### 3. B4 — Stützen wie im Werksprofil (nur Cura)

**Geändert.** `support_pattern` steht nicht mehr in der Cura-Tabelle: Cura
behält sein verbundenes `zigzag` (alle Werksprofile in Cura; Solidons
Kreuzmuster war an Orcas unverbundenem `rectilinear` begründet und bleibt
dort). `CURA_SUPPORT_CROSSINGS` entfällt damit. `_for_supports`: Linienabstand
Bahnbreite durch Dichte, beim Baum 0 (Curas Formel, der Baum trägt nur seine
Wand; `support_wall_count` 1 beim Baum, 0 bei `zigzag`, wie Curas Formel);
Blätter `support_roof_pattern`/`support_bottom_pattern = lines`,
`support_roof_line_distance`/`support_bottom_line_distance` = 3 × Bahnbreite
(ein Drittel dicht wie Creality und Elegoo); `minimum_support_area = 2` (B12).
`_for_speeds`: `speed_support = speed_support_infill = min(speed_print, 150)`,
Schnittstelle und ihre zwei Seiten `min(speed_wall_0, 80)`; der Spiegel
`speed_print → speed_support` entfällt. Die Regel in `dateiformat.md` sagt
jetzt, dass solche Werte dem Werksprofil folgen und ihre Herkunft tragen.

**Tests:** `test_supports_follow_the_factory_profiles`,
`test_a_slow_printer_keeps_its_slower_support` (neu);
`test_grid_supports_reach_every_slicer_as_a_grid` (Cura jetzt ohne Muster) und
`test_curas_zigzag_keeps_the_density_and_a_tree_carries_none` (ersetzt
`test_a_cura_grid_keeps_its_density`, das den Faktor zwei des Gitters
festschrieb). Gegenprobe gegen `cab9d6d30`: 4 von 4 rot.

### 4. B5 — Überhangwände bremsen

**Geändert.** `PrinterProfile.overhang_speed_factors` (Prozent des
Außenwandtempos für Orcas Stufen 2/4, 3/4, 4/4), gelesen über
`profiles._shares` (jeder Wert > 0, sonst derselbe Satz wie bei den Tempi),
eingetragen für alle benannten FDM-Drucker nach der Tabelle oben.
`handover._for_overhangs` schreibt `wall_overhang_angle` und
`wall_overhang_speed_factors`. Die Umrechnung ist am Quelltext von CuraEngine
5.13 abgeleitet (`FffGcodeWriter.cpp`, per `gh api` gelesen): Cura misst den
Überhang der Außenwandmitte gegen die um eine halbe Wandbreite geschrumpfte
Schicht darunter und teilt den Bereich zwischen `wall_overhang_angle` und
90 Grad in gleiche Winkelschritte, einen je Faktor. Eine Wand, die je Schicht
um den Bruchteil f der Bahnbreite auswandert, hat also den Winkel
`atan(f × Bahnbreite / Schichthöhe)`. Orcas Stufe 2/4 beginnt bei f = ¼ —
dort beginnt Curas erste Stufe (28° bei 0,42 auf 0,2 mm), und der letzte
Faktor gilt zweimal, damit die Grenzen passen: Cura 28/43/59/75°, Orca
28/46/58/64°. Ohne Herstellerstufen `[50,25]` ab demselben Winkel. Der
Vorschlag des Prüfberichts (45° bzw. Stützgrenze − 15) hätte Wände zwischen
28 und 45° ungebremst gelassen, die Orca bremst.

**Messung (CuraEngine 5.13, Minigolf-Körper, Centauri Carbon 2, Stand nach
Punkt 4):** Außenwandbewegungen mit 160 mm/s: 63 031, mit 49,6 mm/s: 12 078,
mit 30,4 mm/s: 7 257 — die Faktoren 31 und 19 % kommen als Prozent an. Vorher
nur 160. Dieselbe Messung zeigt die erste Schicht nur noch mit `M204 S500`
(vorher 5000 und 10 000). Druckzeit 76,7 statt 69,6 min.

**Tests:** `test_overhanging_walls_slow_down_like_at_the_manufacturer` (CC2,
K1 Max, allgemein), `test_the_overhang_steps_are_read_from_the_printer_table`
(auch die Absage bei 0). Gegenprobe gegen `cab9d6d30`: 4 von 4 rot.

### 5. B6, B11, B12 — Füllung nach den Wänden, Fahrwege, Naht, Volumenstrom

**Geändert.** `handover._factory_habits` (eine Stelle für die Werte, die
`fdmprinter` anders vorgibt als die Werksprofile in Cura):
`infill_before_walls = false` (B6); `retraction_combing_max_distance = 30`,
bei PETG und PETG-CF 10 (Materialkennung des Projekts; bei einer anderen
ersten Spule gilt das Projektmaterial — dokumentierte Grenze);
`retraction_hop_only_when_collides = true`; `travel_avoid_supports = true`
(B11; `acceleration_travel = acceleration_print` steht schon in Punkt 2);
`z_seam_corner = z_seam_corner_weighted` (B12). `material_max_flowrate`: die
Zeile ist aus der Cura-Tabelle gestrichen und `filament.max_flow` steht in
`NOT_TAKEN_BY["cura"]` (B12) — der Druckdialog bietet das Feld für Cura damit
nicht mehr als wirksam an; `UNREACHABLE`/`UNREACHED` in
`tests/test_print_settings.py` nennen den Grund. `minimum_support_area = 2`
kam mit Punkt 3.

**Tests:** `test_infill_comes_after_the_walls`,
`test_travel_moves_retract_after_a_while_and_avoid_supports` (PLA 30,
PETG 10), `test_the_seam_prefers_hidden_corners`,
`test_cura_is_not_offered_a_flow_limit_it_does_not_read`. Gegenprobe gegen
`cab9d6d30`: 5 von 5 rot. Die Messung im G-Code (Füllung hinter den Wänden)
steht in der Schlussmessung.

### 6. B7 — Leerfahrt der ersten Schicht, erste Bahnbreite

**Geändert.** `_for_speeds`: `speed_travel_layer_0 = max(Curas Formel,
min(speed_travel, 100))` (Konstante `_FIRST_LAYER_TRAVEL` mit Herkunft).
**Erste Bahnbreite — geprüft und entschieden: ja, aus einem Druckerfeld.**
`PrinterProfile.first_layer_line_factor` (Vielfaches der **Düse**, nicht mm:
der Druckdialog kopiert ein Profil mit anderer Düse, `replace(entry,
nozzle_diameter=…, extrusion_width=…)`, und die erste Bahn muss mitgehen),
eingetragen nach der Tabelle oben. `print_settings.resolve` ändert genau die
eine Zeile: `nozzle_diameter × first_layer_line_factor`, ohne Angabe wie
bisher `extrusion_width × 1,07`. **Begründung für `resolve` statt der
Cura-Zuordnung:** Die Cura-Zeile übersetzt `layers.first_layer_line_width`,
den der Kunde im Dialog selbst setzen kann; ein Druckerwert in der Zuordnung
überschriebe seine Wahl. In `resolve` ist er die Grundlage, die der Kunde
ändern kann. Folge für Orca und PrusaSlicer: Sie bekommen damit den Wert, den
ihr Herstellerprofil ohnehin trägt (0,5 statt 0,449 mm am CC2) — eine
Abweichung weniger, im Sinn des Konzepts.

**Tests:** `test_the_first_line_is_as_wide_as_at_the_manufacturer` (CC2 0,5,
Kobra 2 0,8, SV06 0,42, allgemein 0,449), `test_a_changed_nozzle_takes_the_first_line_along`
(0,6er Düse → 0,75), `test_the_first_layer_does_not_travel_at_walking_pace`
(Kobra 2 100, langsame Fahrt 80 bleibt 80, K1 Max Formel). Gegenprobe gegen
`cab9d6d30`: 5 von 6 rot (der allgemeine Drucker ist der unveränderte Rückfall).

### 7. B10 — Die Stützsperre als eigenes Netz (Commit `400dde0e2`)

**Geändert.** Für CuraEngine (neues Prädikat `slicer_keys.takes_mesh_settings`)
schreibt `writer._cura_meshes` neben das zusammengelegte STL je Teil ein Netz
(`<name>-part-<n>.stl`), jede Stützsperre als eigenes (`<name>-blocker-<n>.stl`)
und eine Liste `<name>.meshes.json` (`handover.write_cura_meshes`).
`handover.cura_meshes` liest die Liste und prüft sie (bloße Dateinamen neben dem
Modell, Einstellungsnamen `[a-z0-9_]+`, Werte einzeilig); `_command` setzt je
Netz `-l` und danach dessen `-s`, die Sperre mit `anti_overhang_mesh=true` —
ein `-s` nach `-l` gilt nur diesem Netz (`CommandLine.cpp`). Ohne Liste geht das
Modell wie bisher als ein Netz; eine Liste, die nicht hält, stoppt die Übergabe
mit „noch einmal slicen", statt ein anderes Modell zu schneiden (Regel 21).
`support.block_channels` steht nicht mehr in `NOT_TAKEN_BY["cura"]`,
`AS_GEOMETRY` beschreibt beide Wege. **Die Stelle für Stufe E** ist
`CuraMesh.settings` des Teils (Kommentar in `writer._cura_meshes`) — nicht
gebaut. Das zusammengelegte STL bleibt die Datei, die Curas Fenster öffnet;
dort kommt die Sperre nicht an, und der Exportbefund sagt es in einer eigenen
Cura-Fassung („im Cura-Fenster setzen Sie dafür selbst einen Stützblocker").

**Messung (CuraEngine 5.13, Waschschüssel, Vorschläge übernommen: `grid`,
Kanäle frei halten, Brim, 15 s; `sperre_probe.py`, Stand `400dde0e2`):**
derselbe Export zweimal geschnitten, einmal mit der Netzliste, einmal ohne
(dann das zusammengelegte STL wie vor Punkt 7).

| Drucker | Stütze m ohne → mit Sperre | Stützbewegungen | Druckzeit min | Außen-/Innenwand m | Haut m |
|---|---|---|---|---|---|
| K1 Max | 3439,5 → 2125,9 (−38 %) | 796 455 → 515 315 | 1244,1 → 1002,0 (−19 %) | 741,6/1452,9 → 741,5/1452,7 | 614,5 → 611,8 |
| Neptune 4 | 3436,1 → 2120,1 (−38 %) | 807 404 → 552 930 | 1314,4 → 1063,0 (−19 %) | 741,6/1452,9 → 741,5/1452,7 | 614,4 → 611,6 |
| Centauri Carbon 2 | 3439,7 → 2128,8 (−38 %) | 802 641 → 513 334 | 1195,5 → 946,9 (−21 %) | 741,6/1452,9 → 741,5/1452,7 | 614,5 → 611,8 |

Die Wände bleiben auf 0,1 m gleich; die Haut wird um 2,7 m (0,4 %) kürzer,
weil Decken über gesperrten Kanälen jetzt als Brücke statt auf Stütze liegen.
Die verbleibenden 2,1 km Stütze liegen außerhalb der Kanäle (Rand, Boden). Der
Prüfbericht nannte an seinem Modell 18 476 → 0 Stützbewegungen; hier sperrt
der Vorschlag nur die Kanäle, nicht alle Stützen.

**Tests:** `test_every_mesh_goes_in_with_its_own_values`,
`test_a_model_without_a_mesh_list_goes_in_as_it_is`,
`test_a_mesh_list_that_does_not_hold_stops_the_handover` (vier Fälle) in
`tests/test_cura_machine.py`; `test_cura_gets_every_part_and_the_blocker_as_meshes_of_their_own`,
`test_cura_gets_parts_without_a_blocker_when_none_is_taken`,
`test_a_saved_file_carries_no_blocker` (umbenannt) in `tests/test_export.py`;
die Prädikattabelle kennt `takes_mesh_settings`; `UNREACHABLE`/`UNREACHED` in
`tests/test_print_settings.py` nennen für Cura den Grund („reist als eigenes
Netz"). Der Fenstertest in `tests/test_print_settings_ui.py` heißt jetzt
`test_cura_takes_the_channel_advice_like_the_orca_family` und läuft erst beim
Release. **Gegenprobe** gegen `7dc143970` (Stand vor Punkt 7, Tests von
`400dde0e2`): 7 von 9 rot; grün bleiben der Rückfall ohne Liste und die
gespeicherte Datei ohne Sperre — beide sind unverändertes Verhalten.

**Tor:** Lauf 7 fand einen roten Test: `test_plan_references` las „(§1.5)" im
Verweis auf den Prüfbericht als Bauplan-Paragraphen. Umformuliert zu
„(Abschnitt 1.5)", danach der Test und die übrigen Textprüfungen grün
(471 Tests); das ganze Tor lief mit Punkt 8 wieder vollständig grün.

### 8. B8 — Ender-3 V3 SE und KE sind eigene Drucker (Commit `d99cd121d`)

**Geändert.** Zwei Einträge in `printers.toml` nach `[creality-ender3-v3]`,
Werte aus Orcas Creality-Standardprozessen (Tabelle oben; Temperaturgrenzen
aus Crealitys Datenblatt, SE 260/100 °C, KE 300/100 °C):

| | V3 SE | V3 KE |
|---|---|---|
| Bauraum | 220 × 220 × 250 | 220 × 220 × **240** (Creality, Creality Print und Cura; Orca 245) |
| Leerfahrt, Außen-/Innenwand, Füllung, Decke, erste Schicht, Brücke mm/s | 150, 60/90, 180, 50, 30, 100 | 400, 200/300, 300, 250, 50, 65 |
| Beschleunigung, Außenwand, erste Schicht mm/s² | 2500, 1000, 500 | 5000, 4000, 1000 |
| Volumenstrom PLA (flow_factor) | 18 → 1,5 | 18 → 1,5 |
| Stützgrenze | 60° (Orca und Creality Print: 30° zur Waagerechten) | 60° |
| erste Bahn, Überhangstufen | 1,15; 33/25/17 | 1,25; 25/18/5 |
| `cura_definition` | `creality_ender3v3se` | `creality_ender3v3ke` |

`printer_for` braucht keine Änderung: Der längste Titel gewinnt, also wird
„Creality Ender-3 V3 SE 0.4 nozzle" jetzt der SE statt des V3. Was ein neuer
Drucker sonst berührt, geprüft: Die Website nennt die Zahl der Druckerprofile
(`test_website`: Statistik und Fließtext, sechs Sprachen, Startseite und
Funktionsseite) — jetzt zwanzig, achtzehn davon FDM; die Karte
`app/core/knowledge/CLAUDE.md` („achtzehn FDM-Geräte"); das Handbuch erzeugt
seine Druckertabelle beim Release neu (`test_manual` prüft gegen die Tabelle,
nicht gegen die Datei). Keine Oberflächentexte (Druckertitel sind Namen),
keine neuen Felder, `test_cache` unberührt.

**Creality Print 7.2 weicht für den KE von Orcas Creality-Bestand ab**
(Füllung 270, Decke 200, Leerfahrt 300 mm/s, Außenwand 2000 mm/s², erste
Schicht 500 mm/s², erste Bahn 0,5 mm) und für den SE bei der ersten Bahn
(0,5 statt 0,46 mm); genommen ist wie verlangt Orca, wie beim V3.

**Messung (CuraEngine 5.13, Minigolf-Körper, Stand `d99cd121d`):**

| Drucker | Kopf der Druckdatei | M190/M109 | `{` | M204 Schicht 1 | Leerfahrt S1 mm/s | min |
|---|---|---|---|---|---|---|
| V3 SE | SE-Startcode: `M420 S1`, `M190 S60` und `M109 S215` aus den Platzhaltern, Spüllinie | 1/1 | nein | 500 | 100 | 165,1 |
| V3 KE | Cura setzt `M140/M190 S60` davor, KE-Startcode mit `M109 S215`, Spüllinie | 1/1 | nein | 1000 | 100 | 77,0 |
| V3 (CoreXZ, Cura kennt ihn nicht) | `fdmprinter`, Befund `slicer.cura_printer_unknown` | 1/1 | nein | 500 | 140,2 | 73,8 |

**Tests:** `test_the_ender3_v3_se_and_ke_are_printers_of_their_own` (je elf
Felder), `test_the_se_and_ke_start_with_the_code_of_their_definition` (gegen
die echte Installation: Zeilen des Startcodes, keine Klammer, beide Schalter)
in `tests/test_cura_machine.py`; `test_a_v3_se_or_ke_in_the_slicer_is_not_the_corexz_v3`
in `tests/test_slicer_profiles.py`. **Gegenprobe** (Tests vor den Einträgen):
6 von 7 rot; grün bleibt die Zeile „V3 bleibt V3".

### 9. B9 — Das Cura-Profil gehört dem Drucker, der in Cura aktiv ist (Commit `f9316c040`)

**Geändert.** `slicer_profiles.cura_active_machine` liest den eingerichteten,
aktiven Drucker: `cura.cfg` → `[cura] active_machine` → Maschinenstapel in
`machine_instances` (verglichen über `[general] id`, weil Cura den Dateinamen
kodiert) → Definition an letzter Stelle; erstes Fach → Düse (Stelle 5, Name aus
der Variantendatei) und Spule (Stelle 4, Materialart aus der Materialdatei).
`cura_quality_types(…, variant=, material_type=)` behält in einem Durchgang über
die Qualitätsdateien nur die Stufen, für die ein Profil dieser Düse und dieser
Materialart liegt (sonst alle — so macht es Cura, `MaterialNode._loadAll`);
`cura_quality_definition` nennt die Definition, unter der Cura die Qualitäten
führt. `handover.cura_profile_beside` nimmt daraus die Stufe mit der nächsten
Schichthöhe und schreibt die Qualitätsdefinition in das Profil; der Befund
nennt die Maschine (`values["machine"]`). **Ohne eingerichteten Drucker** (oder
ohne eine Stufe, die passt) entsteht keine Datei, sondern der Befund
`handover.cura_profile_unbound` (Warnung, Vorschlag „Einen anderen Slicer
auswählen"). Die Leser für aktive Maschine, Extruderstapel und Materialdateien
teilt sich die Funktion mit `configured_filaments` (`_cura_active_id`,
`_cura_trains`, `_cura_material_files`), statt sie ein zweites Mal zu schreiben.
Regel in `dateiformat.md` („Das Cura-Profil gehört dem Drucker, der in Cura
aktiv ist"), Karte in `app/core/export/CLAUDE.md`.

**Messung an der echten Installation (`profil_probe.py`):** je Drucker ein
Konfigurationsordner, wie Cura 5.13 ihn nach dem Einrichten schreibt (0,4er
Düse, generisches PLA), dann die Übergabe; ob Cura die Stufe annimmt und
zeigt, nachgelesen in den Qualitätsdateien der Installation.

| Drucker in Cura | vorher | nachher |
|---|---|---|
| K1 Max, Ender-3 V3 SE, V3 KE | `draft` → importiert, unsichtbar | `standard` (`creality_base`) → sichtbar |
| SV06 | `draft` → importiert, unsichtbar | `standard` (`sovol_base_planetary`) → sichtbar |
| Neptune 4 | `draft` → abgelehnt | `Elegoo_layer_020` → sichtbar |
| Centauri Carbon | `draft` → abgelehnt | `elegoo_cc_layer_020` → sichtbar |
| Kobra 2 (ohne eigene Stufen) | `draft` → sichtbar | `draft` (`fdmprinter`) → sichtbar |

Das deckt sich Zeile für Zeile mit dem Prüfbericht (Abschnitt 0.2). Auf
diesem Rechner ist in Cura kein Drucker eingerichtet; hier entsteht jetzt der
Befund statt einer Datei, die Cura ohne Drucker ohnehin nicht importiert.

**Tests:** `test_cura_names_its_active_machine_with_nozzle_and_spool`,
`test_cura_without_a_set_up_printer_names_no_machine`,
`test_cura_offers_only_the_qualities_of_nozzle_and_spool` in
`tests/test_slicer_profiles.py`;
`test_the_profile_takes_a_quality_of_the_printer_active_in_cura`,
`test_without_a_printer_in_cura_there_is_no_profile_but_a_way` in
`tests/test_export.py`; die zwei bestehenden Profiltests richten dafür einen
aktiven Drucker ein (`_cura_active`). **Gegenprobe** (Tests vor dem Code): 6 von
8 rot; grün bleiben der Extruderprofiltest und „nur Cura bekommt ein Profil",
beide unverändertes Verhalten.

---

## Schlussmessung (nachher)

`nachher/run.sh`: Stand `400dde0e2` (Punkte 1 bis 7) als git-archive-Kopie;
B8 und B9 ändern den Weg über die Kommandozeile für diese fünf Drucker nicht.
SE, KE und V3 am Stand `d99cd121d` (`nachher/run-se-ke.sh`). Die Sonde zählt
reine Z-Schritte (Schichtwechsel mit `speed_z_hop`) nicht mehr als Leerfahrt
der ersten Schicht; Grundlinie und Nachher sind mit derselben Auswertung neu
gelesen (`neu_lesen.py`, geslict wurde dafür nichts). Ganze Tabelle mit allen
Spalten: `nachher/tabelle.md`; Gegenüberstellung: `vergleich.md`.

| Modell | Drucker | Lauf | min | M190/M109 | M204 Schicht 1 | Leerfahrt S1 mm/s | Stütze m | Stützbew. | `{` | Rollenfolge nachher |
|---|---|---|---|---|---|---|---|---|---|---|
| bowl | centauri-carbon-2 | standard | 559,7 → 637,6 | 1/1 → 1/1 | 5000,10000 → 500 | 125 → 125 | 0 → 0 | 0 → 0 | nein | WALL-INNER>WALL-OUTER>FILL |
| bowl | centauri-carbon-2 | vorschlaege | 1234,1 → 947,0 | 1/1 → 1/1 | 5000,10000 → 500 | 125 → 125 | 3229,5 → 2128,8 | 409 926 → 513 331 | nein | SUPPORT>WALL-INNER>WALL-OUTER>FILL |
| bowl | creality-k1-max | standard | 604,4 → 710,2 | 1/1 → 0/0 | 5000,10000 → 1000 | 179,6 → 179,6 | 0 → 0 | 0 → 0 | nein | WALL-INNER>WALL-OUTER>FILL |
| bowl | creality-k1-max | vorschlaege | 1311,2 → 1002,0 | 1/1 → 0/0 | 5000,10000 → 1000 | 179,6 → 179,6 | 3222,4 → 2125,9 | 405 113 → 515 310 | nein | SUPPORT>WALL-INNER>WALL-OUTER>FILL |
| bowl | elegoo-neptune-4 | standard | 607,2 → 713,1 | 1/1 → 1/1 | 5000,6000 → 500 | 140,4 → 140,4 | 0 → 0 | 0 → 0 | nein | WALL-INNER>WALL-OUTER>FILL |
| bowl | elegoo-neptune-4 | vorschlaege | 1330,1 → 1063,1 | 1/1 → 1/1 | 5000,6000 → 500 | 140,4 → 140,4 | 3229,3 → 2120,1 | 415 217 → 552 926 | nein | SUPPORT>WALL-INNER>WALL-OUTER>FILL |
| golf | anycubic-kobra-2 | beide | 100,2 → 120,7 | 1/1 → 1/1 | 700,2500,5000 → 700,2000 | **16,9 → 100** | 0 | 0 | nein | WALL-INNER>WALL-OUTER |
| golf | centauri-carbon-2 | beide | 69,6 → 76,3 | 1/1 → 1/1 | 5000,10000 → 500 | 125 → 125 | 0 | 0 | nein | WALL-INNER>WALL-OUTER |
| golf | creality-k1-max | beide | 73,5 → 82,3 | 1/1 → 0/0 | 5000,10000 → 1000 | 179,6 → 179,6 | 0 | 0 | nein | WALL-INNER>WALL-OUTER |
| golf | elegoo-neptune-4 | beide | 73,2 → 81,9 | 1/1 → 1/1 | 5000,6000 → 500 | 140,4 → 140,4 | 0 | 0 | nein | WALL-INNER>WALL-OUTER |
| golf | sovol-sv06 | beide | 296,4 → 302,5 | 1/1 → 1/1 | 5000,8000 → 500 | 75 → 100 | 0 | 0 | nein | WALL-INNER>WALL-OUTER |
| golf | creality-ender3-v3-se | standard | – → 165,1 | – → 1/1 | – → 500 | – → 100 | 0 | 0 | nein | WALL-INNER>WALL-OUTER |
| golf | creality-ender3-v3-ke | standard | – → 77,0 | – → 1/1 | – → 1000 | – → 100 | 0 | 0 | nein | WALL-INNER>WALL-OUTER |
| golf | creality-ender3-v3 | standard | – → 73,8 | – → 1/1 | – → 500 | – → 140,2 | 0 | 0 | nein | WALL-INNER>WALL-OUTER |

**Gegen die Forderungen des Auftrags gelesen:**

- **Startcode da:** K1 Max `START_PRINT EXTRUDER_TEMP=215 BED_TEMP=60` und
  `END_PRINT`; Kobra 2, Neptune 4, SV06, SE, KE der Code ihrer Definition
  (Spüllinie; SV06 und SE mit `M420 S1`). Centauri Carbon 2 und V3 kennt
  Cura nicht: `fdmprinter` und der Befund `slicer.cura_printer_unknown`.
- **Keine `{` im G-Code:** an keinem Lauf, weder im Kopf noch dahinter.
- **Genau ein M190/M109 dort, wo der Startcode sie setzt:** Kobra 2,
  Neptune 4, SE je 1/1 aus dem Startcode (Curas eigene abgeschaltet); KE
  1/1, Bett von Cura, Düse aus dem Startcode; K1 Max 0/0, weil das Makro
  `START_PRINT` heizt; SV06 und CC2 1/1 von Cura, ihr Startcode setzt keine.
- **Beschleunigung der ersten Schicht vom Hersteller:** K1 Max 1000, Neptune 4,
  CC2, SE 500, KE 1000, Kobra 2 2000 (dazu 700: Cura nimmt je Rolle das
  Kleinere, und Solidons Außenwand fährt dort 700), SV06 500 (keine
  Herstellerangabe).
- **Kobra 2 fährt die erste Schicht nicht mehr im Schritttempo:** 16,9 → 100 mm/s.
- **Füllung nach den Wänden:** in jeder Schüssel-Schicht
  `WALL-INNER>WALL-OUTER>FILL` statt `FILL>WALL-INNER>WALL-OUTER`.
- **Sperre wirksam:** Abschnitt 7 (−38 % Stütze, Wände gleich).

**Stützbewegungen steigen, Stützlänge fällt.** Die Sonde zählt Bewegungen,
nicht Meter. Cura legt jetzt sein verbundenes `zigzag` statt Solidons Gitter
(Punkt 3), und dessen kurze Verbindungsstücke sind je eine Bewegung; die
Länge fiel um ein Drittel.

**Die Druckzeit steigt ohne Stützen, und zwar durch die Überhangbremse
(Punkt 4).** `ueberhang_zeit.py` rechnet aus dem G-Code, wie lange die
gebremsten Außenwände fahren und wie lange sie im vollen Außenwandtempo
gebraucht hätten (ohne Beschleunigung gerechnet, also eine Schätzung):

| Lauf | Druckzeit vorher → nachher | davon Überhangbremse |
|---|---|---|
| golf K1 Max | +8,8 min (+12 %) | +10,6 min |
| golf Kobra 2 | +20,5 min (+20 %) | +22,9 min |
| golf CC2 | +6,7 min (+10 %) | +8,7 min |
| golf Neptune 4 | +8,7 min (+12 %) | +8,4 min |
| golf SV06 | +6,1 min (+2 %) | +7,0 min |
| bowl K1 Max standard | +105,8 min (+18 %) | +113,3 min |
| bowl Neptune 4 standard | +105,9 min (+17 %) | +93,9 min |
| bowl CC2 standard | +77,9 min (+14 %) | +93,7 min |

Am Golfkörper fahren 25 von 182 m Außenwand unter dem halben Tempo (14 %),
an der Schüssel 146 von 741 m (20 %). Weil sie dort mit einem Viertel bis einem
Zwanzigstel des Tempos fahren, brauchen sie am Golfkörper fast so lange wie
alle übrigen Außenwände zusammen. Die übrigen Punkte sparen dagegen etwas
(Leerfahrt der ersten Schicht, breitere erste Bahn mit weniger Bahnen). Das
ist das Verhalten der Werksprofile, nicht ein Fehler der Übergabe: Orca bremst
dieselben Wände auf dieselben Tempi (Tabelle der Herstellerwerte). Mit Stützen
wird die Schüssel trotzdem kürzer (K1 Max 1311 → 1002 min), weil die Sperre und
die lockerere Stützdecke mehr sparen, als die Bremse kostet.

---

## Tor je Commit

`suite-getrennt.sh` (ohne Fenster und Leistung), ruff, ruff format, mypy; das
Ergebnis jeweils aus der Ausgabedatei gelesen (`tor/`).

| Commit | Punkt | Tor | ruff / format / mypy |
|---|---|---|---|
| `b5a18cbe0` | 1 (B1) | 17 636 bestanden, 56 übersprungen, 0 Läufe mit Fehler | grün |
| `8d6be2eed` | 2 (B2) | 17 642 / 56 / 0 | grün |
| `d2d4e8dab` | 3 (B4) | 17 644 / 56 / 0 | grün |
| `c39fe0f06` | 4 (B5) | 17 648 / 56 / 0 | grün |
| `47b6ca37f` | 5 (B6, B11, B12) | 17 653 / 56 / 0 | grün |
| `7dc143970` | 6 (B7) | 17 659 / 56 / 0 | grün |
| `400dde0e2` | 7 (B10) | 1 rot (`test_plan_references`, „§1.5" im Docstring), 17 666 bestanden; nach der Umformulierung die Textprüfungen grün (471) | grün |
| `d99cd121d` | 8 (B8) | 17 680 / 56 / 0 — schließt Punkt 7 ein | grün |
| `f9316c040` | 9 (B9) | 17 685 / 56 / 0 | grün |

Fenstertests und Leistungsprüfungen liefen nicht (nur beim Release), darunter
der umgeschriebene `test_cura_takes_the_channel_advice_like_the_orca_family`.

---

## Commits (Zweig `cura-maschine`, nicht gepusht, nicht gemergt)

1. `b5a18cbe0` Cura bekommt den Startcode seines Druckers
2. `8d6be2eed` Die erste Schicht fährt in Cura mit der Beschleunigung des Herstellers
3. `d2d4e8dab` Cura legt Stützen wie die Werksprofile
4. `c39fe0f06` Überhängende Wände bremsen in Cura wie beim Hersteller
5. `47b6ca37f` Cura füllt nach den Wänden und fährt Wege wie die Werksprofile
6. `7dc143970` Die erste Schicht fährt breite Bahnen und keine Leerfahrt im Schritttempo
7. `400dde0e2` Die Stützsperre erreicht Cura als eigenes Netz
8. `d99cd121d` Ender-3 V3 SE und KE sind eigene Drucker
9. `f9316c040` Das Profil für Curas Fenster passt zum Drucker, der in Cura eingerichtet ist

Beim Mergen zu beachten: main hat seit `cab9d6d30` drei Commits, einer davon
(`0ad19d4b0`) ändert `slicer_profiles.py` an `_names_the_printer` und
`match`; Punkt 9 ändert dieselbe Datei an anderen Stellen (Cura-Leser,
`cura_quality_types`). Die Website-Seiten (Punkt 8) und `printers.toml`
ändert main nicht.

## Neue Katalogtexte (alle fünf Sprachen übersetzt)

- Punkt 1: „Die Cura-Definition ist der Dateiname ohne „.def.json“: nur
  Buchstaben, Ziffern und Unterstriche." — „Der Start- oder Endcode dieses
  Druckers in Cura verlangt einen Wert, den Solidon nicht einsetzen kann.
  Ungefüllt bräche der Drucker den Druck ab." — „Cura kennt „{printer}“ nicht.
  Die Druckdatei beginnt deshalb ohne den Startcode des Herstellers, ohne
  Spüllinie und ohne Bettnetz."
- Punkt 7: „In „{name}“ liegen Decken in schmalen Kanälen. Beim Slicen sperrt
  Solidon dort die Stützen; im Cura-Fenster setzen Sie dafür selbst einen
  Stützblocker." — „Die Teile für Cura sind unvollständig geschrieben. Slicen
  Sie noch einmal, dann entstehen sie neu."
- Punkt 9: „In Cura ist kein Drucker eingerichtet, zu dem das Profil passt.
  Richten Sie Ihren Drucker in Cura ein und wählen Sie dann noch einmal „Im
  Slicer öffnen“."

## Offene Punkte, mit Grund

1. **Toter Eintrag im Druckdialog.** `_BY_HAND_IN_THE_SLICER[("cura",
   "support.block_channels")]` in `app/ui/print_settings_dialog.py` wird nicht
   mehr erreicht, seit Cura die Sperre nimmt (Punkt 7). Die Datei war
   ausdrücklich gesperrt; Eintrag und Katalogtext können beim Mergen fallen.
2. **Curas Fenster bekommt die Sperre nicht.** „Im Slicer öffnen" gibt Cura
   das zusammengelegte STL; der Befund sagt dem Kunden, dass er den
   Stützblocker selbst setzt. Ein Weg dorthin wäre eine 3MF für Curas Fenster
   mit der Sperre als Objekt samt `anti_overhang_mesh` in Curas eigenen
   Objekteinstellungen — nicht gebaut, gehört zu Stufe E.
3. **Eigener Auswerter für Rechnungen in Platzhaltern** (Punkt 1, Abweichung
   vom Auftrag, begründet): ohne ihn hielten Neptune 4 und 4 Plus an.
4. **SV06: Curas Startcode setzt `M201 X500 Y500` und `M204 P500`.** Die
   Definition stammt aus der Gemeinschaft (`sovol_base`), nicht von Sovol; am
   Drucker gelten danach höchstens 500 mm/s², Curas Zeitschätzung weiß das
   nicht. Im Cura-Fenster ist es genauso. Ob Solidon diesen Code übernimmt
   („Der Anfahrcode bleibt der des Herstellers"), entscheidet Robert.
5. **MINI+: Tempi und neue Felder aus zwei verschiedenen Prozessen**
   (Abschnitt Herstellerwerte). Nicht von hier; die Tempi gehören nachgezogen.
6. **Creality Print 7.2 fährt SE und KE anders als Orcas Creality-Bestand**
   (Punkt 8); genommen ist Orca wie verlangt und wie beim V3.
7. **Kämmgrenze nach dem Projektmaterial**, nicht nach der ersten Spule
   (Punkt 5, dokumentierte Grenze).
8. **Druckzeit.** Die Überhangbremse verlängert Drucke mit vielen Überhängen
   um bis zu rund ein Fünftel (Schlussmessung); gewollt, aber sichtbar.
9. **Register.** Die Punkte 1, 2 und 4 gehören ins Register von `ROADMAP.md`;
   hier nicht eingetragen, weil die Release-Sitzung dieselbe Datei führt.
10. **Handbuch und Website-Upload** ziehen die zwei neuen Drucker beim Release
    nach (Druckertabelle wird erzeugt; die Startseiten sind hier schon
    angepasst).

## Changelog 0.5.1 (nur Verhalten, das in v0.5.0 steckte)

Geprüft mit `git tag --contains` am Commit, der das alte Verhalten einführte:
Cura-Konsole mit `fdmprinter` `7fe222679`, gespiegelte Beschleunigung und
Stützmuster `5537ae25a`, erste Bahn × 1,07 `f4f6e639d`, Ender-3 V3
`ae7e5cb33`, `.curaprofile` `56f700002`, Volumenstromzeile `5537ae25a` — alle
in `v0.5.0`. Die Kanalsperre (`1db1dbfdd`, 26.09.2026) ist nach v0.5.0
entstanden; für Punkt 7 gibt es deshalb keinen eigenen Satz.

- Mit Cura beginnt der Druck jetzt mit dem Startcode Ihres Druckers, wie beim Hersteller. Kennt Cura den Drucker nicht, sagt Solidon es Ihnen.
- Mit Cura fährt die erste Schicht jetzt mit der Beschleunigung aus dem Profil des Herstellers statt mit der vollen Druckbeschleunigung.
- Stützen aus Cura entstehen jetzt nach dem Muster der Werksprofile: zusammenhängend, mit lockerer Decke und gemäßigtem Tempo.
- Mit Cura fahren überhängende Wände jetzt langsamer, wie beim Hersteller. Drucke mit vielen Überhängen dauern dadurch bis zu rund 20 Prozent länger.
- Mit Cura druckt die Füllung jetzt nach den Wänden, und Leerfahrten meiden Stützen und ziehen auf langen Wegen das Filament zurück.
- Die erste Schicht druckt jetzt so breite Bahnen wie das Profil Ihres Druckers, an der 0,4er Düse meist 0,5 mm. Mit Cura fährt sie dazwischen nicht mehr im Schritttempo.
- Neu sind der Creality Ender-3 V3 SE und der V3 KE. Bisher bekam ein SE die Werte des viel schnelleren Ender-3 V3.
- Das Profil für das Cura-Fenster passt jetzt zu dem Drucker, der in Cura eingerichtet ist. Bisher lehnte Cura es bei manchen Druckern ab oder zeigte es nicht an.
- Den Volumenstrom bietet der Druckdialog für Cura nicht mehr als Einstellung an, denn Cura liest ihn nicht.
