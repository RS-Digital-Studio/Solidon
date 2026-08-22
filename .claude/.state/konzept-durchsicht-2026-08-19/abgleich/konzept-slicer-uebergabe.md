# Abgleich: .claude/konzept-slicer-uebergabe.md

**Geprüft am:** 19.08.2026 gegen `main` (b0415d6)
**Letzte Änderung des Konzepts:** 9c420bf, 07.08.2026 23:44 (Umbenennung Formwerk → Solidon)
**Erstfassung:** 99900c6, 05.08.2026
**Zwölf Tage und rund 260 Commits später geprüft.**

Zusammenfassung: **stimmt 4 · überholt 8 · falsch 2 · unprüfbar 1** (15 interne
Behauptungen). Der ElegooSlicer ist auf dieser Maschine installiert
(`C:/Program Files/ElegooSlicer/elegoo-slicer.exe`), also ließen sich auch die
Behauptungen prüfen, die einen Profilbestand brauchen.

Der Grundfehler des Dokuments ist nicht eine falsche Einzelzahl, sondern seine
Bauform: §1 („Was Solidon heute schon kann"), §2 („Drei Lücken, gemessen") und
§3 („Was im Modell fehlt") stehen im **Präsens** und beschreiben den Stand vom
05.08.2026, während §5 dieselben Lücken Stufe für Stufe als **umgesetzt**
abhakt. Wer das Dokument von vorn liest, liest drei Kapitel lang einen
Zustand, den das fünfte Kapitel widerruft.

---

## 1. slicer_keys: „50 Zuordnungen für Orca"

**Urteil: überholt**

**Beleg:**
```
.venv/Scripts/python.exe -c "from app.core.export.slicer_keys import TABLES; ..."
prusa 54 · orca 57 · cura 47
Counter({'process': 37, 'filament': 20})
```
`app/core/export/slicer_keys.py:230-306` (ORCA), `:142-200` (PRUSA),
`:319-378` (CURA).

**Stattdessen:** „57 Zuordnungen für Orca (37 Prozess, 20 Filament), 54 für
Prusa, 47 für Cura."

---

## 2. „Achtzehn von fünfzig Werten landen im falschen Profil" (§2.1, §7 Punkt 1)

**Urteil: überholt**

Als historische Messung des Standes vor Stufe 1 ist die Aussage plausibel und
durch die 14+4 aufgezählten Schlüssel gedeckt. Sie steht aber im Präsens
(„landen", „kommen beim Slicen nicht an") und wird in §7 Punkt 1 noch einmal
im Präsens wiederholt: „heute meldete er achtzehn, wenn jemand hinsähe."

**Beleg:**
- `tests/test_print_settings.py:903` `test_every_orca_setting_sits_in_the_profile_it_claims`
  läuft gegen den installierten Bestand und ist **grün**:
  `pytest tests/test_print_settings.py -q -k orca_setting` → `1 passed`
  (nicht übersprungen — der Slicer liegt vor).
- Die vier Maschinenschlüssel sind durch `filament_*`-Entsprechungen ersetzt:
  `slicer_keys.py:296-299` (`filament_retraction_length`, `filament_retraction_speed`,
  `filament_z_hop`, `filament_wipe`, alle Abschnitt `filament`).
- Die Abnahme ist erfüllt: `ROADMAP.md:3227-3240` „Vollständige Verifikation
  des Gewürzsets (07.08.2026) … Die Gegenprobe (`handover.verify`) meldet bei
  allen vier **null Abweichungen**."

**Stattdessen:** „Achtzehn von damals fünfzig Werten landeten im falschen
Profil — behoben mit Stufe 1, abgesichert durch
`test_every_orca_setting_sits_in_the_profile_it_claims`, und am 07.08.2026
gegen den ElegooSlicer gemessen: null Abweichungen." §7 Punkt 1 gehört von der
Abnahmeliste in eine Erledigt-Zeile.

---

## 3. `handover._RECOMPUTED` nimmt vier Filamentwerte von der Gegenprobe aus (§2.1)

**Urteil: überholt**

**Beleg:** `app/core/export/handover.py:1146-1156`:
```
_RECOMPUTED = frozenset({
    "filament_colour", "nozzle_diameter", "bed_shape",
    "first_layer_speed", "brim_type", "wall_sequence", "support_type",
})
```
`filament_density`, `filament_cost` und `filament_max_volumetric_speed` stehen
nicht mehr darin — geändert in 9c59e3a (05.08.2026, „Temperatur und Kühlung
standen im Prozessprofil, gelesen werden sie im Filament"), also noch am Tag
der Erstfassung des Konzepts.

**Stattdessen:** „`_RECOMPUTED` nahm die Filamentwerte einmal von der
Gegenprobe aus, mit der falschen Begründung, der Slicer rechne sie um — er
bekam sie nie. Heute stehen dort nur noch Werte, die der Slicer wirklich
umformt (Farbe zur Liste, Düsendurchmesser, Bettform)."

---

## 4. „`slicer_profiles.PROFILE_DIRS` kennt `machine` und `process`" (§2.2, §1 Tabelle)

**Urteil: überholt**

**Beleg:** `app/core/export/slicer_profiles.py:45-49`:
```
PROFILE_DIRS = {"machine": "machine", "process": "process", "filament": "filament"}
```
`DEFAULT_KINDS = ("machine", "process")` (`:267`) — Filamente werden nur auf
Verlangen gelesen, das ist die in Stufe 2 beschriebene Absicht, nicht die
alte Lücke. `handover._command` übergibt `--load-filaments`
(`handover.py:831`), `write_config` schreibt je Slot ein Filamentprofil
(`handover.py:415-428`).

Das Dokument widerspricht sich hier selbst: **§1 Tabelle** führt
`export/slicer_profiles.py` weiter mit „Maschine und Prozess", **§2.2** ist
mit „Das Filamentprofil fehlt ganz" überschrieben, **§5 Stufe 2** sagt
„umgesetzt".

**Stattdessen:** §1 Tabelle: „Maschine, Prozess und Filament, Erbkette der
Verträglichkeit". §2.2 in die Vergangenheit setzen: „Das Filamentprofil fehlte
ganz — nachgetragen in Stufe 2."

---

## 5. „Solidons `material.petg`: Düse 240/245 °C, Bett 80/80 °C, Volumenstrom 12 mm³/s, kein Pressure Advance" (§2.3)

**Urteil: falsch** (in einer von vier Zahlen)

**Beleg:** `app/core/knowledge/data/print_settings.toml:129-145`:
```
[material.petg]
nozzle = 240 · nozzle_first_layer = 245 · bed = 80 · bed_first_layer = 80
max_flow = 10.0
```
Aufgelöst: `print_settings.resolve(make_profile('centauri-carbon-2','petg')).filament.max_flow` → `10.0`.
`12.0` ist der Wert von **PLA** (`print_settings.toml:126`).
`git log -L 129,148:app/core/knowledge/data/print_settings.toml` zeigt nur zwei
Commits: die Anlage ohne `max_flow` und 2989261 (01.08.2026), der ihn mit
**10.0** einträgt — die Zahl 12 war für PETG nie im Repository, auch nicht am
Tag, an dem das Konzept geschrieben wurde.

Düse, Bett und „kein Pressure Advance" stimmen: `grep -rn pressure_advance app/`
findet keine Fundstelle.

**Nebenbefund:** Derselbe Zahlendreher steht auch im Code — der Docstring von
`app/core/export/handover.py:722-731` schreibt „ein Volumenstrom von 10 mm³/s
statt 12". Auch dort gehört die Zeile korrigiert; beim Translucent-Profil gibt
es beim Volumenstrom gar keinen Unterschied (beide 10).

**Stattdessen:** In der Tabelle §2.3 die Zeile „Volumenstrom | 10 mm³/s | 10
mm³/s | **5 mm³/s**" — der Unterschied liegt nur beim PRO, und dort um das
Doppelte.

---

## 6. „Solidons Materialtabelle weicht in dreizehn Werten vom Herstellerprofil ab" (§6a)

**Urteil: überholt** (heute zwölf)

**Beleg:** `handover.profile_differences` gegen den installierten Bestand,
`Elegoo PETG @ECC2` — das Profil, das Solidon laut §6a selbst wählt:
```
count = 12
close_fan_the_first_x_layers: 2 statt 3; fan_max_speed: 50 statt 40;
fan_min_speed: 50 statt 10; filament_density: 1.27 statt 1.25;
filament_flow_ratio: 0.95 statt 0.98; filament_max_volumetric_speed: 10 statt 11;
hot_plate_temp: 80 statt 70; hot_plate_temp_initial_layer: 80 statt 70;
nozzle_temperature: 240 statt 250; nozzle_temperature_initial_layer: 245 statt 250;
overhang_fan_speed: 100 statt 90; slow_down_layer_time: 8 statt 12
```
Die im selben Satz genannten Beispiele stimmen: „240 gegen 250 °C an der Düse
und 80 gegen 70 °C am Bett".

**Stattdessen:** „Solidons Materialtabelle weicht in zwölf Werten von
`Elegoo PETG @ECC2` ab (Stand 19.08.2026, ElegooSlicer-Bestand), darunter
240 gegen 250 °C an der Düse und 80 gegen 70 °C am Bett."

---

## 7. „Alle fünf Stufen sind als ‚umgesetzt' markiert" (§5)

**Urteil: stimmt** — und die Markierung trägt, jede Stufe ist im Code
nachweisbar.

**Beleg je Stufe:**
- **Stufe 1** — `slicer_keys.Entry.section` (`slicer_keys.py:43-50`),
  `handover.write_config` schreibt Prozess- und Filamentprofil getrennt
  (`handover.py:404-428`), `--load-filaments` (`handover.py:831`), kein
  Maschinenprofil für Orca (nur `_machine_keys` in die Werte, keine Datei).
- **Stufe 2** — `PROFILE_DIRS` mit `filament` (`slicer_profiles.py:45`),
  `resolve_values` (`:355`), `match_filament` (`:474`), `DEFAULT_KINDS` ohne
  Filamente (`:267`), `profile_differences` (`handover.py:722`).
- **Stufe 3** — `ShellSettings.wall_generator` / `.precise_outer_wall` /
  `.ironing` (`app/core/types.py:411-418`), `SpeedSettings.bridge` /
  `.acceleration` / `.outer_wall_acceleration`
  (`knowledge/print_settings.py:206-208`); Zuordnung in allen drei Tabellen,
  soweit der Slicer die Sache kennt (`slicer_keys.py:152-159`, `:244-251`,
  `:328-335`).
- **Stufe 4** — `AssemblyPart.settings` (`export/threemf.py:125`),
  `_settings_xml` schreibt `model_settings.config` (`:224-245`),
  `advise.for_part` (`slice/advise.py:668`), `handover.object_keys`
  (`handover.py:184`).
- **Stufe 5** — `writer.plates_by_material` (`export/writer.py:357`),
  `check_adhesion_clearance` (`:219`), `check_filament_changes` (`:305`).

**Einschränkung zu Stufe 3:** „mit Vorgaben je Qualitätsstufe" gilt nur für die
drei Geschwindigkeitswerte (`print_settings.toml`, je Stufe
`speed_bridge`/`acceleration`/`outer_wall_acceleration`). `wall_generator`,
`precise_outer_wall` und `ironing` haben eine feste Vorgabe in der Datenklasse
(`types.py:411-418`, `wall_generator = "arachne"`), keine Stufenvorgabe.

**Stattdessen:** Satz halten, den Halbsatz „mit Vorgaben je Qualitätsstufe" auf
die Geschwindigkeiten einschränken.

---

## 8. „`MaterialProfile.hole_compensation` geht bisher nur in die Hashsumme ein; es gibt keine Op, die ihn anwendet" (§5 Stufe 3)

**Urteil: falsch**

Der Wert wird an zwei Stellen angewandt, beide älter als das Konzept:

**Beleg:**
- `app/core/geom/prepare.py:68` `bore_diameter(nominal, profile, compensate)`
  rechnet ihn auf den Nenndurchmesser; `:143` benutzt ihn im Schnitt. Die Op
  dazu ist `drill_hole` (`app/core/geom/prepare_ops.py:191`) mit dem Parameter
  `compensate` (`:182`, durchgereicht `:214`). Eingeführt in 4c888f6
  (28.07.2026), also **zehn Tage vor** dem Konzept.
- `app/core/knowledge/profiles.py:205-212`: `_FIT_FIELD` bildet die Passungsart
  `"thread"` auf `hole_compensation` ab — eine Gewindepassung löst ihre
  Toleranz daraus auf (`resolve_tolerance`, `:214`). Eingeführt in ae7e5cb
  (27.07.2026).
- Test: `tests/test_prepare.py:47-56`
  `test_a_bore_is_cut_larger_than_nominal` prüft
  `bore_diameter(5.0, profile, compensate=True) == 5.0 + petg.hole_compensation`.

Richtig bleibt der **Schluss** des Absatzes: den Wert zusätzlich an den Slicer
zu geben (`xy_hole_compensation`) hieße zweimal kompensieren — genau die
Begründung, die einen Absatz höher beim Elefantenfuß steht.

**Stattdessen:** „**Lochkorrektur.** `MaterialProfile.hole_compensation` wendet
die Geometrie schon an: `bore_diameter` rechnet ihn auf jede Bohrung der Op
`drill_hole`, und eine Gewindepassung löst ihre Toleranz daraus auf. Ihn
zusätzlich an den Slicer zu geben hieße, zweimal einzuziehen — dieselbe
Begründung wie beim Elefantenfuß."

---

## 9. „Die Op `compensate_elephant_foot` … laut eigenem Docstring ‚genau das, was die Elefantenfuß-Kompensation eines Slicers tut'" (§5 Stufe 3)

**Urteil: stimmt** (mit einer Namensungenauigkeit)

**Beleg:** Die Funktion heißt `compensate_elephant_foot`
(`app/core/geom/prepare.py:323`), ihr Docstring: „Eine gerade Stufe, keine
Schräge — genau das tut auch die ‚Elefantenfuß-Kompensation' eines Slicers"
(`:333-335`). Die **registrierte Op** heißt `compensate_first_layer`
(`app/core/geom/prepare_ops.py:499`, Titel „Elefantenfuß ausgleichen"), sie
ruft die Funktion (`:516`).

**Stattdessen:** „Dafür gibt es die Op `compensate_first_layer`, die über
`compensate_elephant_foot` in der Geometrie arbeitet und laut deren Docstring
…" — sonst sucht der Leser im Register nach einem Namen, der dort nicht steht.

---

## 10. „Die Regel ‚Fläche, auf der etwas gleiten soll' aus dem `Fit` abzuleiten steht noch aus; heute ist es ein Schalter im Dialog" (§5 Stufe 3)

**Urteil: überholt**

**Beleg:** `app/core/slice/advise.py:524-545`, `_from_fits`:
```python
if "flush" in kinds and not settings.shell.ironing:
    advice.append(SettingAdvice(path="shell.ironing", value=True, ...
        reason=_("Eine bündige Passung legt zwei Flächen aufeinander. Gebügelt "
                 "gleitet die obere, statt auf den Bahnkanten zu sitzen.")))
```
Docstring derselben Funktion: „eine bündige Passung legt zwei Flächen
aufeinander, und die obere ist dann eine Gleitfläche. Die will gebügelt
werden." Eingeführt in a28bd00, 07.08.2026 **10:13** — also gut dreizehn
Stunden **vor** der letzten Änderung am Konzept (9c420bf, 23:44). Nachgezogen
in `ROADMAP.md:417-419` („Bügeln aus der Passung abgeleitet … nur `flush` löst
den Vorschlag aus").

**Stattdessen:** „Die Regel ‚Fläche, auf der etwas gleiten soll' folgt seit
a28bd00 aus dem `Fit`: `advise._from_fits` schlägt Bügeln vor, wenn eine
bündige Passung im Spiel ist — bei Schiebesitz, Presssitz oder Gewinde nicht."

---

## 11. „`arrange_bed` legt 5 mm zwischen zwei Körper, bei 3 mm Skirt-Abstand braucht es 6 … das steht in der Roadmap" (§6a Fund 3)

**Urteil: überholt** — die Zahl stimmt, der offene Punkt ist geschlossen.

**Beleg:**
- Der Vorgabewert steht unverändert: `app/core/geom/prepare.py:403-404`
  `arrange_on_bed(..., spacing: float = 5.0, ...)`, aufgerufen aus der Op
  `arrange_bed` (`prepare_ops.py:1100-1116`).
- Die Begründung, warum die Operation es nicht selbst wissen kann, steht heute
  wörtlich im Docstring (`prepare.py:412-419`) — das Konzept ist dort in den
  Code eingezogen.
- **Der Punkt ist erledigt:** `ROADMAP.md:410-413`
  „- [x] Anordnung und Plattenhaftung zusammenbringen — der Dialog des
  Anordnens öffnet mit dem Abstand, den die Haftung verlangt (zweimal den
  Rand), vorbelegt und änderbar." Umsetzung:
  `app/ui/main_window.py:4958-4982`, `_spacing_for`:
  `needed = 2.0 * adhesion_margin(settings)` … `return {"spacing": max(default, needed)}`.
- Dazu, ebenfalls neu und für diesen Fund entscheidend: `ROADMAP.md:2373-2399`
  („Paket 2 der Durchsicht: die Platte kommt an") — vorher war die ganze
  Anordnung folgenlos, weil die Orca-Familie in der Vorgabe neu anordnet;
  seither reist die Platzierung im 3MF mit und `--arrange 0` wird gesetzt,
  wenn `writer.arrangement_holds` zustimmt.

**Stattdessen:** „*Die Anordnung kannte den Haftungsrand nicht.* `arrange_bed`
legt 5 mm zwischen zwei Körper, bei 3 mm Skirt-Abstand braucht es 6. Behoben
in der Oberfläche: der Dialog des Anordnens öffnet mit dem doppelten
Haftungsrand als Abstand. Die Operation kennt die Druckeinstellung weiterhin
nicht und soll es nicht."

---

## 12. „In der Suite gibt es keinen echten Slicer-Lauf; `verify` läuft nur bei einem echten Lauf" (§2.1, §7)

**Urteil: stimmt**

**Beleg:** Kein Test startet ein Slicer-Programm. `handover.slice_model`
kommt in Tests nur auf Fehlerwegen vor (`tests/test_print_settings.py:929`
fehlendes Modell, `:942` verschobenes Programm,
`tests/test_licence_boundary.py:142`/`:218` Lizenzgrenze). Die Gegenprobe wird
gegen einen **mitgeschriebenen** G-Code-Ausschnitt geprüft
(`tests/test_print_settings.py:639-694`, Konstante `ECHTER_GCODE`), nicht
gegen einen frischen Lauf. Der einzige Test, der den installierten Bestand
anfasst, liest Profildateien und startet nichts
(`tests/test_print_settings.py:888-920`).

**Zu ergänzen:** Der echte Lauf ist inzwischen gemacht und protokolliert —
`ROADMAP.md:3227-3240`, vier Teile, `verify` meldet null Abweichungen. Er ist
nur nicht Teil der Suite und wird es auch nicht.

**Stattdessen:** Satz halten, Nachsatz anfügen: „Der Lauf von Hand ist gemacht
und in der Roadmap festgehalten (07.08.2026, vier Teile, null Abweichungen);
in die Suite gehört er nicht."

---

## 13. „Die Spülmenge in Gramm bleibt draußen" (§5 Stufe 5)

**Urteil: stimmt**

**Beleg:** `app/core/export/writer.py:344-354` — der Befund
`arrange.filament_changes` trägt `values={"layers": shared, "changes": shared * 2}`
und sonst nichts. `grep -rn "Spülvolumen\|flush_volume\|purge" app/ --include=*.py`
findet keine Fundstelle. Auch der Docstring (`:316-319`) begründet es so.

---

## 14. Gewürzset-Messwerte: 282/516/1256 mm², 22,0/5,4/67,6 mm, 110 Schichten, 220 Wechsel (§3, §6a)

**Urteil: unprüfbar** — die Vorlagen liegen nicht im Repository.

**Beleg:** `C:/Users/rober/Documents/Solidon/3D Drucker` existiert auf dieser
Maschine nicht (`test -d` → FEHLT); CLAUDE.md führt den Ordner ausdrücklich als
„nicht im Repository". Ohne die vier STL lässt sich weder `advise.for_part`
noch `check_filament_changes` wiederholen.

**Teilweise gedeckt** durch die Roadmap, unabhängig geschrieben:
- `ROADMAP.md:398-401`: „Brim gehört unter die Deckelbasis mit 282 mm²
  Standfläche, nicht unter die Streuscheibe mit 516"
- `ROADMAP.md:392-395`: „110 gemeinsame Schichten und 220 Wechsel, wenn ein
  68-mm-Behälter neben einem 22-mm-Deckel steht"
- `ROADMAP.md:3232-3236`: Druckzeiten und Gewichte der vier Teile aus dem
  echten Lauf.
Nicht gegengelesen sind 1256 mm² für den Behälter und die drei Höhen auf die
Zehntelstelle.

**Stattdessen:** Die Messwerte behalten, aber datieren und die Quelle nennen —
„gemessen am 05.08.2026 an den vier STL aus Projekt 08 des Ordners
`3D Drucker` (nicht im Repository)". Eine Zahl ohne Datum liest sich sonst wie
eine, die man nachrechnen könnte.

---

## 15. „Der ‚nil'-Fund wurde behoben: 17 Meldungen wurden 13" (§6a Fund 2)

**Urteil: überholt**

Die Behebung selbst steht: `handover.profile_differences`
(`app/core/export/handover.py:753-758`) überspringt Werte aus `_NO_STATEMENT`
mit der Begründung „``nil`` ist keine Gegenaussage, sondern eine
Nicht-Aussage". Die Zahl 13 stimmt nicht mehr — dieselbe Messung ergibt heute
**12** (siehe Punkt 6). Zwischen dem Konzept und heute hat sich Solidons Seite
geändert (`filament_max_volumetric_speed` fällt beim Translucent-Profil ganz
aus der Liste).

**Stattdessen:** „… behoben; vier solche Zeilen fielen weg. Beim `Elegoo PETG
@ECC2` bleiben heute zwölf echte Unterschiede."

---

## Widersprüche innerhalb des Dokuments

1. **§1 Tabelle gegen §5 Stufe 2.** „Profile des Slicers finden |
   `export/slicer_profiles.py` | Maschine und Prozess" — Stufe 2 sagt
   fünfzig Zeilen weiter, `slicer_profiles` kenne „jetzt auch `filament/`".
   Der Code gibt Stufe 2 recht (`slicer_profiles.py:45-49`).
2. **§2.2 Überschrift gegen §5 Stufe 2.** „Das Filamentprofil fehlt ganz" im
   Präsens gegen „umgesetzt".
3. **§2.1 gegen §5 Stufe 1.** „Solidon schreibt alles in **ein** Prozessprofil
   und lädt `--load-settings machine;process`" gegen „`write_config` schreibt
   … Prozess- und Filamentprofil getrennt".
4. **§7 Punkt 1 gegen §5 Stufe 1 und die Roadmap.** Die Abnahmebedingung
   „ein Lauf, bei dem `verify` keine Abweichung meldet" ist am 07.08.2026
   erfüllt worden (`ROADMAP.md:3239`), der Text nennt sie noch offen und
   behauptet „heute meldete er achtzehn".
5. **§3 Tabelle gegen §5 Stufe 3.** Die Liste „Was im Modell fehlt" führt
   `wall_generator`, `precise_outer_wall`, Bügeln, `bridge_speed`,
   Beschleunigungen — alle sechs sind in Stufe 3 nachgetragen und stehen
   heute in `types.py:411-418` und `print_settings.py:206-208`. Offen aus
   dieser Liste sind nur noch Pressure Advance, `brim_object_gap` und
   `bridge_flow`.
6. **§2.3 gegen die eigene Quelle.** Die Tabelle nennt für Solidons PETG
   12 mm³/s; die Datei sagt seit dem 01.08.2026 10,0 — die Zeile war schon
   beim Schreiben falsch.

---

## Was seit dem 07.08. dazugekommen ist und im Dokument fehlt

Das Dokument beschreibt den Weg zum Slicer als geschlossen. Zwei Bausteine,
die seither dazukamen, gehören in §1 und in Stufe 1/2, sonst liest §1 sich
weiterhin vollständig und ist es nicht:

- **`handover.project_settings`** (`handover.py:438 ff.`, eingeführt 1e705be,
  13.08.2026, „Die 3MF trug die Geometrie und ließ die Temperatur zu Hause"):
  eine exportierte 3MF trägt ihre Druckeinstellungen selbst, aufgesetzt auf
  System-Prozess- und -Filamentprofil.
- **Die Platzierung reist mit** (`ROADMAP.md:2385-2399`): Matrix am `<item>`
  des 3MF plus `--arrange 0`, abgesichert durch `writer.arrangement_holds`.
  Vorher war jede Aussage über die Platte folgenlos — das betrifft §5 Stufe 5
  und §6a Fund 3 unmittelbar.
- **Filamentwahl je Material** (`app/ui/settings.py:47`
  `slicer_base_filament`, dazu `slicer_filament_per_material`, 17dcd65,
  13.08.2026): Stufe 2 sagt noch „der Dialog zeigt sie zur Auswahl und merkt
  sie sich" — er merkt sie sich inzwischen je Material.

## Externe Zahlen, die ich nebenbei nachgemessen habe

Nicht mein Auftrag, aber der Slicer lag vor:

- **Bestätigt:** Elegoo PETG Translucent 255/255 °C, 70/70 °C, 10 mm³/s,
  Pressure Advance 0,052; Elegoo PETG PRO 240/240 °C, 70/70 °C, 5 mm³/s,
  PA 0,1 (`resolve_values` über die beiden Profildateien).
- **Bestätigt:** „fünfundfünfzig Werte aus vier Dateien" — `resolve_values`
  liefert für beide Profile genau 55 Werte.
- **Bestätigt:** alle vier genannten Profilnamen existieren im Bestand
  (`.../profiles/Elegoo/{machine,process,filament}/ECC2/`).
- **Schief formuliert:** „5962 Profile mit Filamenten gegen 3887 ohne". Gemessen:
  `find_profiles(..., kinds=('machine','process'))` → **3888**, mit Filamenten
  → **9852**, Filamente allein also 5964. Gemeint ist „5964 Filamentprofile
  gegen 3888 Maschinen- und Prozessprofile" — so steht es auch im Code
  (`slicer_profiles.py:262-266`), nur mit den alten Zahlen 5962/3887.
