# Review RM-589 — „Bohrungen und Stifte passen ohne Nacharbeit“

Prüfling: Worktree `F:\sl-loecher`, Zweig `einstellungen/loecher-rm589`, Commit
`e8c785abd`, `git diff origin/welle2...HEAD` (Basis `a9e4d3f64`), 33 Dateien. Jede
Zeile des Diffs gelesen, dazu die berührten Funktionen im Zusammenhang
(`handover.object_keys`, `cura_profile_beside`, `writer.part_advice`/`_part_values`/
`_values_for`/`_unserved`/`write_assembly`, `manufacturer.base_settings`/`_read_process`/
`part_brim_gap`, `print_settings.resolve`/`legacy_choices`, `serialise.print_settings_*`,
`advise.advise`/`plate_paths`/`for_part`, Dialog `_AdviceWorker`, `_advice_context`,
`_offered_entries`), Regeln `druckrat.md`, `dateiformat.md`, `kern.md`, `tests.md`,
`zwillinge.md`, `uebersetzung.md`, `auslieferung.md`, `druckerwahl.md`.

## Schwer

### S1 Solidons eigener Satz schreibt Einzug und Lochausgleich jetzt ungefragt — doppelter Fuß als Standardfall, Curas Maschinenwerte überschrieben, Kalibrierschleife

`app/core/knowledge/print_settings.py:312-314` setzt `elephant_foot` im eigenen Satz
auf den Materialwert, `app/core/export/slicer_keys.py:580-581` (dazu 260, 410) schreibt
ihn und `hole_offset` (Vorgabe `0.0`, `app/core/types.py:1268`) bei jeder Übergabe ohne
Herstellerprozess: Cura (Konsole und Fenster), PrusaSlicer ohne Bündeldrucker,
Orca-Familie ohne lesbaren Prozess und jede 3MF ohne Slicer. Vorher stand keiner der
Schlüssel in den Tabellen (`git show origin/welle2:…/slicer_keys.py`: 0 Treffer).

- **(a) Doppelter Fuß ohne Klick.** Ein Teil mit *Elefantenfuß ausgleichen* bekommt in
  Cura zusätzlich `xy_offset_layer_0 = -0.2` (PETG): erste Schicht 0,4 statt 0,2 mm je
  Seite eingezogen. Bisher schrieb Solidon nichts, CuraEngine nahm 0, und das Ergebnis
  stimmte. Jetzt stimmt es nur, wenn der Kunde den Vorschlag übernimmt
  („Übernommen wird auf Klick, nie von allein“, `druckrat.md`). Beleg, Sonde
  `rv589/probe_cura_export.py`: `allowances A=('foot',)`, Rat nicht übernommen →
  Platte `'-0.2'`, `fuss.meshes.json` ohne Objektwert. Genau die Kunden, die in 0.5.x
  mit Cura gegen den Fuß nur diesen Schritt hatten, drucken jetzt schlechter.
- **(b) Curas Fenster bekommt Werte, die der aktiven Maschine gehören.**
  `cura_profile_beside` (`handover.py:7743-7746`) legt `as_mapping(…, "cura")` ins
  `.curaprofile`, jetzt mit `xy_offset_layer_0` und `hole_xy_offset = 0` (Sonde
  `probe_cura.py`). In Cura 5.13 setzen 75 von 706 Druckerdefinitionen über ihre Kette
  einen der beiden, etwa die Ultimaker-Familie `-wall_line_width_0 / 5 + xy_offset`,
  AnkerMake M5 `hole_xy_offset 0.2`, UltiMaker S8 `0.075`, Voron 2, VzBot `-0.3`. Dazu
  kommen 70 Qualitätsprofile. Bisher galt dort der Maschinenwert; jetzt verliert z. B.
  ein M5 seinen Lochausgleich (0,4 mm im Durchmesser) auf allen Löchern. Die Lösung dafür
  gibt es schon: `_without_curas_own_fan_curve` (`handover.py:7623-7638`, RM-228) lässt
  solche Werte im Fenster weg, solange sie nicht gewählt sind. Siehe auch
  `dateiformat.md`: „Wo Curas Werksprofile anders setzen als `fdmprinter`, gilt das
  Werksprofil“.
- **(c) Kalibrierschleife.** Der Prüfkörper wird in Cura mit `-material.elephant_foot`
  gedruckt. Gemessen wird der Rest, und der Rest wird der neue `elephant_foot` und damit
  der nächste Einzug. Nach einer Kalibrierung ist der Fuß wieder da, nach der nächsten
  wieder weg. Die Begründung sagt es selbst („sein Wert wäre der Rest, nicht der ganze
  Fuß“, `konzepte/begruendungen/regel-druckrat.md:583-584`).

**Fix:** Im eigenen Satz nichts Ungefragtes schreiben. `resolve` lässt `elephant_foot`
auf 0 wie bisher und wie die Programmvorgaben; das Fenster nennt beide Pfade nur bei
`settings.explicit`, wie die Lüfterkurve. Den Rat je Teil (`_from_allowances`) und das
neue Feld behalten. Wer den Materialeinzug für Cura will, bekommt ihn als **Vorschlag**
an Teilen ohne Modellausgleich und klärt vorher die Kalibrier-Semantik (M1). Danach den
zweiten Satz des ersten Changelog-Punkts und
`test_without_a_maker_profile_the_foot_comes_from_the_material` anpassen; der Test
schreibt das Verhalten fest. Neuer Test: Cura-Export mit Fuß-Teil ohne Übernahme schreibt
dem Teil keinen Einzug; Fensterprofil ohne Wahl ohne die beiden Schlüssel.

## Mittel

### M1 Bei kalibriertem Material nimmt der Rat den Ausgleich weg, mit dem kalibriert wurde

`app/core/slice/advise.py:1654-1685`. Der Toleranz-Testkörper (`fit_ladder`) wird über
das Herstellerprofil gedruckt, also mit dessen `xy_hole_compensation` und
`elefant_foot_compensation`. „Spiel für Schiebesitz“, „Lochkorrektur“ und „Elefantenfuß“
im Kalibrierdialog (`app/ui/dialogs.py:432-440`) sind deshalb der Rest hinter dem
Slicer-Ausgleich. Diese Prämisse steht in der eigenen Begründung (s. S1c). Modell und
Hersteller treffen das Ziel dann nur zusammen. Der Rat „→ 0“ macht das Loch um 2·s enger
und lässt den Fuß um s stehen (CC2 0,1, MK4S 0,2 mm je Seite).
**Fix:** `_from_allowances` nur, wenn `profile.material.calibrated` falsch ist (`advise`
hat das Profil, je Spule `process.profile`), oder die Kalibrierung ausdrücklich ohne
Slicer-Ausgleich drucken: Der Prüfkörper bekommt dieselben Objektwerte null, und Dialog
und Handbuch sagen es. Test: kalibriertes Material → kein Vorschlag.

### M2 `allowances_for` zählt Schritte statt Löcher mit Materialzugabe — falsche Gründe, fehlende Fälle, Zwilling zu `parts.ops.cuts`

`app/core/scene/fits.py:355-411`. Der Docstring verspricht „Löcher tragen Spiel oder
Lochkorrektur aus dem Materialprofil“. Die Sonden `probe_false.py` und `probe_parts.py`
zeigen etwas anderes:

- **Zu viel:** `thread_exact` (*Schraube erstellen*, ein Bolzen) → `('holes',)` → Rat
  „Das Spiel der Bohrungen steht schon im Modell.“ an einer Schraube.
  `insert_snap_fit` (aufsetzender Haken, `parts.ops.cuts` → `False`) → `('holes',)`.
  `insert_heatset_m4`: Loch aus der Einsatztabelle ohne Materialspiel. Dazu zählt die
  Kette ein gebohrtes Loch weiter, wenn es danach mit `plug_hole` verschlossen ist (der
  Kommentar 356-358 meint das Gegenteil) oder ohne Haken nachgebohrt wurde, ebenso
  `field_cut` mit Haken bei eckiger Form (dort gleicht `field_ops` nicht aus).
- **Zu wenig:** abtragende Bausteine mit Materialspiel außerhalb von `FITTING_OPS`, etwa
  `insert_latch` (`negative`: „dieselbe Form, aber mit Spiel“), `insert_snap_connector`
  (`kind="bore"`) und `insert_foot` (`kind="pocket"`). Dazu kommen aufsetzende Teile,
  deren Bohrung das Spiel trägt (`insert_printed_nut`, `insert_hinge_eye`,
  `insert_barrel_hinge`, `insert_rod_connector`). Sie alle bekommen keinen Rat, und der
  doppelte Ausgleich bleibt.
- **Zwilling:** Die Richtung liest der Code selbst aus `metadata["param"]["subtractive_on"]`.
  `knowledge.parts.ops.cuts(spec, values)` gibt es genau dafür („ohne diese Funktion
  hätte jede ihre eigene Version“). Sie beachtet auch `spec.subtractive`, und daran
  scheitert hier der Haken (`zwillinge.md`).

**Fix:** Für Bausteinschritte `parts.ops.cuts` nehmen. „holes“ an einer Eigenschaft
festmachen: ein Schritt, dessen Materialspiel (`PLAY_FIELD`/`compensate`) eine
Innenkontur formt, am besten als Angabe am `PartSpec` statt als Handliste.
`thread_exact`, `snap_fit` und den Wärmeeinsatz dort herausnehmen; `FITTING_OPS` bleibt
für `fit_kinds_for`. Tests: Dübel als Bohrung und Mutternfalle → `holes`; Haken und
Schraube → leer.

### M3 Der Dialogweg ist ohne Anschlusstest

Die Allowances werden im Dialog an drei Stellen übergeben (`app/ui/print_settings_dialog.py:1614, 1735,
1796`, `7858-7864`, `7992`, `8094`); einziger Test ist eine Attrappe
`_part_allowances=dict` (`tests/test_print_settings.py:8239`). Der Export ist durch
`test_a_part_that_compensates_itself_keeps_its_brim_at_the_foot` gedeckt. Im Dialog
bliebe die Suite grün, wenn `_part_allowances()` leer liefe oder den falschen Körper
nennte („Anschluss“, `tests.md`: geänderte Oberfläche bringt ihren Fenstertest).
**Fix:** Fenstertest nach dem Vorbild `test_a_built_fit_counts_like_an_entered_one`:
zwei Körper, *Elefantenfuß ausgleichen* an einem. Dann nennt `_part_allowances()` genau
diesen Körper, und die Zeile `layers.elephant_foot` trägt nur seinen Namen.

## Leicht

- **L1 `PROGRAM_DEFAULTS` kennt die neuen Schlüssel nicht** (`app/core/export/manufacturer.py:492-531`).
  Laut Sonde `probe_chains2.py` nennt die Kette keine `elefant_foot_compensation` in
  folgenden Prozessen: 19 MK3S-Prozesse (plus Snapmaker Artisan) in OrcaSlicer 2.4.2 und
  ElegooSlicer, 21 in Creality Print 7.2. `xy_hole_compensation` fehlt dort in 27
  bzw. 556 Prozessen. Die Grundlage behält dann den Materialwert, der Slicer nimmt seine
  Vorgabe: Der Dialog zeigt einen falschen Wert, und „→ 0“ ändert nichts (`dateiformat.md`:
  „Gedruckt wird, was der Slicer liest“; „Ein Vorschlag, der beim Slicer nichts ändert,
  wird nicht angeboten“). **Fix:** Programmvorgaben wie am 27.09. messen (Konsole, leerer
  Prozess) und für die fünf Programme eintragen.
- **L2 Regel 6:** `app/core/export/handover.py:1357` prüft `foot and …`, also einen
  Wahrheitswert auf einer Fließkommazahl. **Fix:** `foot is not None and not is_zero(foot)`.
- **L3 Feldtexte** (`app/core/knowledge/print_fields.py:156-157, 258-260`, alle
  Kataloge):
  - „… gehört hier null hin“ fordert eine Null für die ganze Platte (eigene Wahl gilt
    der Platte) und nimmt damit allen anderen Teilen den Ausgleich. Das widerspricht dem
    „je Teil“ der Begründung. Besser: „Gleicht das Modell schon aus, schlägt Solidon für
    dieses Teil null vor.“
  - Die Suche findet „Erste Schicht einziehen“ weder unter „Elefantenfuß“ noch unter
    „elephant foot“, und „Löcher weiten“ nicht unter „Lochkorrektur“ (Wort des
    Kalibrierdialogs) oder „Lochausgleich“ (Sonde `probe_search.py`). Jeder Slicer nennt
    die Einstellung „Elephant foot compensation“. **Fix:** Die Begriffe in die Sätze
    aufnehmen, in allen sechs Sprachen.
- **L4 Unterlagen:**
  - Der Kopf von `konzepte/recherche-slicer-einstellungen-2026-10.md:3-7` führt RM-589
    noch als offen; `konzepte/README.md` sagt „gebaut“.
  - `ROADMAP-ARCHIV.md:46265` „Cura glich weder Fuß noch Loch aus“ gilt nur für
    CuraEngine mit den sieben eingebauten Definitionen (S1b).
  - Die Begründung (`regel-druckrat.md:585`) nennt als eigenen Satz nur Cura und
    PrusaSlicer; Orca-Familie ohne Prozess und 3MF ohne Slicer fehlen (Sonde: Orca-Satz
    `elefant_foot_compensation='0.2'`).
  - Die Brim-Regel je Teil und der eigene Satz sind Übergaberegeln
    (`.claude/rules/druckrat.md:114-117`). Sie gehören nach `dateiformat.md` bzw.
    `app/core/export/CLAUDE.md` „Brim-Abstand“ (109-113, dort fehlt RM-589).
  - Changelog: „Ohne Profil des Herstellers, etwa bei Cura“ ist für Cura-Kunden falsch
    (sie wählen dort das Druckerprofil des Herstellers) und fällt mit S1 ohnehin.
- **L5 SuperSlicer-Lücke ohne Registerpunkt** (`app/core/export/slicer_keys.py:1162-1165`).
  Die mitgelieferten Profile von SuperSlicer 2.5 setzen `first_layer_size_compensation`
  -0,1 bis -0,3 (16 Profile) und `hole_size_compensation` -0,03/-0,05. Solidon kann sie
  nicht auf null setzen, der doppelte Ausgleich bleibt dort. Offene Arbeit gehört ins
  Register von `ROADMAP.md`. **Fix:** Registerpunkt, oder Programmschlüssel mit
  Vorzeichenwechsel abbilden.
- **L6 Fehlende Tests:**
  - Die Rücklesung `elefant_foot_compensation` aus dem Prusa-Bündel (`manufacturer.py:1378`,
    `1436-1437`) prüft niemand. Ohne die Zeile bleibt alles grün; der Slicertest setzt
    den Plattenwert als eigene Wahl. Eine Zeile in
    `test_prusas_bundle_is_read_back_like_the_orca_family` genügt (MK4S: 0,2).
  - Positivfall `FITTING_OPS` siehe M2.

## Bestätigt

- **Vorzeichen und Einheiten:** Orca/Prusa `elefant_foot_compensation` positiv =
  Einzug, Cura `xy_offset_layer_0` über `_negated` negativ, ohne `-0`. `hole_xy_offset`
  und `xy_hole_compensation` positiv = weiter, je Seite. Das Material weitet im
  Durchmesser, der Slicer je Seite, und die Texte halten das auseinander.
- **Echter Slicer, hier nachgefahren:** `test_a_part_that_compensates_itself_is_not_compensated_again`
  ist für OrcaSlicer, PrusaSlicer und Cura grün (zweimal). Mitgeschrieben: Objektwerte
  `elefant_foot_compensation=0`, `xy_hole_compensation=0`, `brim_object_gap=0.25` an A,
  nichts an B, keine Abweichung der Gegenprobe. Der Test misst A gegen B und wäre ohne
  Objektwerte rot (0 statt 0,2/0,3); die Sollwerte kommen aus der eigenen Konstruktion.
- **`object_keys`:** Die Brim-Logik stimmt mit und ohne `brim_use_efc_outline`. Mit
  Crealitys Absenkung (RM-318) kommt sie nicht ins Gehege, und
  `_lowered_foot_findings` schweigt zu Recht bei Fußkorrektur aus dem Rat.
- **Export-Anschluss:** `_part_values` reicht `allowances_for` weiter; der Merker von
  `part_advice` hat sie im Schlüssel, `_advice_context` im Dialog ebenso. Ohne
  Weitergabe ginge der Wert über `_unserved` an alle Teile, und der neue Exporttest wäre
  rot.
- **Bambu:** Die Kreisausgleichung ist im Standard aus (`enable_circle_compensation: 0`).
  Polyholes schaltet kein Herstellerprofil der Orca-Familie ein. Unter Bäumen und für
  Resin bleibt der Rat leer.
- **Formate:** Kein Formatsprung nötig. Alte Dateien lesen das fehlende Feld als 0, das
  ist keine Wahl (`legacy_choices` vergleicht auch die Dataclass), danach gilt die
  Grundlage. Ältere Programme verwerfen unbekannte Pfade (`_known_paths`).
- **Konsistenz:** `PART_PATHS` gleich `MEASURED_PART_PATHS`. Bei Prusa und SuperSlicer
  wird ausgefiltert (`takes`, `for_program`). `plate_paths` macht die neuen Pfade nicht
  plattenweit.
- **Texte:** Gründe ≤ 60 Zeichen, Changelog ≤ 200 (längster fr 190), Operationsnamen in
  allen Sprachen wie im Katalog, Glossar eingehalten.
- **Regeln:** 1–5 und 9–22 ohne Verstoß; 6 siehe L2; 7 siehe S1 (feste 0 überschreibt
  Maschinenwerte); 8 nicht berührt. Bezeichner englisch.

## Gelaufen

Gezielt, kein volles Tor:

| Lauf | Ergebnis |
|---|---|
| `test_advise.py`, `test_changelog.py`, `test_language_rules.py`, `test_directory_docs.py`, `test_shared_constants.py` | 635 bestanden, 4 übersprungen |
| `test_manufacturer.py`, `test_slicer_part_settings.py` | 313 bestanden |
| `test_print_settings.py`, `test_translations.py` | 1019 bestanden, 4 übersprungen (Resin), 13 abgewählt |
| `test_print_settings_ui.py`, `test_interface_limits.py` ohne Fenster | 137 bestanden, 374 abgewählt |
| Slicertest (OrcaSlicer, PrusaSlicer, Cura) | 3 bestanden, zweimal |
| ruff check und format auf den 15 `.py` | sauber |

Nicht gelaufen: mypy, Fenstertests, Slicertest für Bambu Studio, ElegooSlicer, Creality
Print und Anycubic Slicer Next (Angabe des Umsetzers). Sonden und Ausgaben liegen unter
`%TEMP%\claude\F--3D-Druck\6d004019-0ef1-44d0-8062-699c55490a5e\scratchpad\rv589\`.
Am Worktree wurde nichts geändert.

## Urteil

**Nicht rein.** Mit S1 druckt Cura (und jeder eigene Satz) ein Teil mit *Elefantenfuß
ausgleichen* standardmäßig schlechter als vorher, und Curas Fenster bekommt
Maschinenwerte überschrieben. Dazu kommen M1–M3. Rat, Objektwerte, Brim und
Slicertests sind tragfähig; nach dem Fix von S1 und M1–M3 reicht eine Nachprüfung.
