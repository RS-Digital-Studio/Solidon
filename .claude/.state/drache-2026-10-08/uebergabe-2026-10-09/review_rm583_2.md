# Nachprüfung RM-583 (zweite Runde)

Worktree `F:\sl-stuetzen`, Zweig `einstellungen/stuetzabstand`, HEAD `936def3fc` (Merge von origin/main auf `adb99b83f`).

**Umfang.** `git -C F:/sl-stuetzen diff` vollständig (35 Dateien, +718/−227). Aus `adb99b83f` dazu die Matrix-Werkzeuge (N1).

**Vorgehen.** Nur lesend. Die Skripte liegen in `scratchpad\rv2\` (`rounds.py`, `label.py`, `pingpong.py`, `parts.py`, `calibrated.py`, `cura_warn.py`) und liefen mit `-B` und umgebogenen Nutzerordnern. Der Baum ist unverändert; keine Suite, keine Slicer.

## Stand der Funde aus Runde 1

| Fund | Stand |
|---|---|
| M1 | Die Zeile ist zurück, aber die Liste kommt nicht mehr zur Ruhe (H1) |
| M2 | behoben (`first`/`last`, `round(…, 4)`, Test mit sieben Fällen) |
| M3, L8 | behoben: Konstante entfernt, Doku zurück, beide Schlüssel unter `known`, Prusa-Zeile, Ausschluss nur für `prusaslicer` |
| M4 | behoben: geschriebene Abstände, Befund gegen den Herstellerprozess, Turm aus der Grundlage. Neuer Widerspruch: N1 |
| M5 | behoben: Formular der Gruppe; kein Detailfeld ist `front`, und jede Gruppe hat ein Formular |
| N1 | behoben in `adb99b83f`: `filament_type(MATERIAL, flavour)`, Material in Laufkennung und Umgebung |
| N2 | behoben, auch je Teil: `advise.apply` markiert als übernommen, also greift `_contact_density` |
| N3 | Gemischte Platte: Jede der drei Bedingungen macht den Test ohne sich rot. Pilz auf dem Bett und Cura bei feinen Schichten sind getestet. `slice_model` bleibt ungeprüft (L4) |
| L1, L3, L5, L7, L10, L11 | behoben |
| L2 | behoben bis auf die Bahnbreite (L6) |
| L4 | behoben, aber kalibrierte Profile verlieren den Rat (M1) |
| L6 | Turm aus der Grundlage, Cura über `limitation`. Der Cura-Satz kommt jetzt zu oft (M2) |
| L9 | teilweise behoben (L1) |

## Hoch

### H1: Der getrennte Kontaktrat im Druckdialog kommt nie zur Ruhe und nennt in Runde 2 das falsche Teil

**Stelle:**

- `app/core/slice/advise.py:388-391` (`separate`), aufgerufen in `app/ui/print_settings_dialog.py:1574`.
- Der Rat je Körper und Spule entsteht an `self.settings` (`:1540-1550`), die Teile benennt `_with_parts` (`:1709`, `:1713`).
- Gegenstück: `app/core/export/writer.py:1390`. `part_advice` fragt je Körper ohne `separate` und gegen `split.base`.

**Was falsch ist.** Dialog und Export fragen verschieden:

- Der Dialog fragt jeden Körper gegen den Plattenwert samt Übernahme.
- Der Export fragt gegen die Grundlage und gibt jedem Teil seinen eigenen Wert.

Bei Pfaden, deren Rat in beide Richtungen geht, liefert `separate` deshalb nach jeder Übernahme die Gegenzeile. `rounds.py` stellt den Ablauf nach: alle Zeilen übernehmen, neu fragen, wie `_apply_advice` → `_refresh_advice`.

- **Tisch + Kinn, Trennschicht 0,2/3:** Runde 1 bringt `0,2 → 0,5` und `3 → 2`, Runde 2 `0,5 → 0,2` und `2 → 3`. So geht es weiter bis Runde 5.
- **PLA + PETG, 0,15er Schicht, Abstand 0,2:** `0,2 → 0,15`, dann `0,15 → 0,21`, dann `0,21 → 0,15` und so fort.

„Nichts einzuwenden“ kommt nie, und jede Gegenzeile ist vorbelegt.

- **Falsches Teil an der Zeile** (`label.py`, Grundlage aus Solidons Tabelle 0,5/2). Runde 2 zeigt „Lücke 0,2 → 0,5“ und nennt den Tisch als Teil, obwohl der Tisch 0,2 verlangt. Der Grund: `_with_parts` nennt jeden Körper, dessen Rat den Pfad trägt, gleich mit welchem Wert. Deshalb bleibt auch die Anycubic-Zeile aus Runde 1 (beide Körper weichen ab) ohne Teile und zeigt 0,28 für alle.
- **Cura druckt den Wechsel mit** (`pingpong.py`, `parts.py`). Die Lücke nimmt Cura nur für die ganze Platte; `_part_paths("cura")` enthält `support.interface_spacing` nicht.
  - Ohne `separate` kam nach der dichten Übernahme keine Zeile mehr.
  - Jetzt folgt `0,2 → 0,5` für das Kinn. Wird sie übernommen, bekommt auch der Tisch unter seiner flachen Decke die lockere Trennschicht.
- **Spulen eines Körpers.** Der Dialog legt je Spule eine Gruppe an (`:1540-1550`), und `combine` kann Spulen nicht von Körpern unterscheiden.
  - Ein Körper mit PLA- und PETG-Spule bekommt bei 0,15 mm Schicht die Zeile 0,15. Der Docstring sagt das Gegenteil: „Innerhalb eines Teils … der Wert, der alle einschließt“.
  - `part_advice` fragt den Körper ohne `separate` und schweigt.
  - `_unserved` (`writer.py:1596-1628`) legt die 0,15 dann an jedes Teil, auch an die PETG-Spule, mit dem Befund „Gilt für alle Teile …“.

**Warum es zählt.**

- Kundensicht: Eine Liste, die nach jedem Übernehmen das Gegenteil vorschlägt, lässt den Kunden raten.
- Bei Cura wird falsch gedruckt.
- zwillinge.md: Dialog und Export beantworten dieselbe Frage verschieden.

**Fix.** Den Kontaktrat im Dialog so fragen wie der Export:

1. Je Körper über seine Spulen ohne `separate` zusammenführen.
2. Gegen `split_for_parts(self.settings, …).base` fragen, wie es `_accepted_targets` schon tut.
3. `separate` nur für `CONTACT_PATHS ∩ handover._part_paths(flavour, program)` verwenden.
4. Eine Zeile nur anbieten, wenn der Wert der abweichenden Körper vom aktuellen Wert abweicht.
5. In `_with_parts` nur Körper nennen, deren Wert dem der Zeile gleicht.

Tests:

- Zwei Runden (übernehmen, neu fragen) ergeben keine Kontaktzeile, für Orca und Cura.
- Cura mit Tisch + Kinn und dichter Platte ergibt keine Zeile.
- Ein Körper mit PLA- und PETG-Spule ergibt keine Abstandszeile.

Dazu den Satz in `druckrat.md` nachziehen („jede Abweichung eine Zeile“).

## Mittel

### M1: Ein vor 0.6.0 kalibriertes PLA oder PETG bekommt keinen Stützrat

**Stelle:** `app/core/knowledge/profiles.py:331-334` zusammen mit `:369`.

**Was falsch ist.**

- `_load_materials` ersetzt einen Eintrag der Nutzerdatei als Ganzes.
- `calibration.apply` hat ihn bisher ohne die neuen Felder geschrieben.
- Seit „fehlt heißt unbekannt“ liest `calibrated.py` für so ein PLA und PETG: Faktor, Min und Max `None`, Kühlung `False`, Ziel `None`.

Damit gibt es weder Abstandsrat noch volle Kühlung, und zwar gerade bei den Kunden, die kalibriert haben. In `adb99b83f` griffen hier noch die PLA-Vorgaben.

**Fix.** Beim Lesen fehlende Schlüssel eines Nutzereintrags aus dem mitgelieferten Eintrag derselben Kennung ergänzen, wie `print_settings._load` es macht („Je Eintrag, nicht je Datei“). Test: Eine Nutzerdatei ohne `support_gap_*` liefert die Werte aus `[pla]`.

### M2: Cura warnt bei jeder Übergabe in Entwurf und Fein, auch ohne Stützen

**Stelle:** `app/core/export/slicer_keys.py:1129` (`LIMITED["cura"]`) mit `:1635-1645`. Gemeldet wird über `handover.setting_limitations` (`handover.py:4527-4545`) als Warnung mit der Handlung `CHECK_SLICER_PROFILE`.

**Was falsch ist.** `limitation` prüft nur, ob `z_gap / layer` ganzzahlig ist. Ob gestützt wird und ob der Kunde den Wert gewählt hat, fragt es nicht. Solidons eigene Vorgabe von 0,2 ist bei 0,28 und 0,12 mm Schicht kein Vielfaches.

**Beleg** (`cura_warn.py`, SV06 und CC2, PLA, Stützart `none`): Bei `draft` und `fine` kommt jedes Mal die Warnung „Cura rechnet den Abstand in ganzen Schichten zu 0,28 mm.“, bei `standard` und `strong` nicht.

Zwei weitere Mängel am selben Befund:

- „Maschinenprofil prüfen“ führt nicht zum Ausweg.
- Der Satz nennt das Feld nicht; im Bericht steht nur „den Abstand“.

**Fix.**

- Nur melden, wenn gestützt wird.
- Die Cura-Grundlage auf ein Vielfaches der Schichthöhe der Stufe setzen, in `base_settings` wie bei der Lücke (etwa `support_gap_target(…, "cura")`).
- Im Satz das Feld nennen (*Abstand oben und unten*) und als Handlung `OPEN_PRINT_SETTINGS` mit dem Feld geben.
- Test: Cura `draft`/`fine` mit Vorgaben und ohne Stützen ergibt kein `slicer.setting_not_transferred` für `support.z_gap`.

## Niedrig bis mittel

### N1: Gemischte Platte mit Turm: zwei Befunde widersprechen sich

**Stelle:** `app/core/export/writer.py:2763-2764`.

**Was falsch ist.** `support_layers_findings` kommt unabhängig vom Turm. Am CC2 schaltet der Herstellerprozess die eigene Stützschichthöhe ab und den Turm ein. Mit PLA und PETG sagt der Export dann zugleich:

- „druckt die Stütze in eigener Schichthöhe“
- „rundet … auf ganze Schichten“

Nach `normalize_fdm_2` (`scratchpad\bambu_PrintConfig.cpp:7962-7967`) stimmt nur der zweite Satz. Die Tests sehen die Kombination nicht: Der Plattentest hat keinen Herstellerprozess, der Befundtest keine Platte.

**Fix.** Bei gemischter Platte mit Turm nur `export.support_gap_rounded` melden, sonst `support_layers_findings`. Test mit `_native_process` (eigene Höhe aus, Turm an) und gemischter Platte.

Zwei Reste aus L6 bleiben ungesagt:

- „Je Objekt“ mit mehreren Objekten: Der Turm fällt weg, also rundet nichts; der Befund kommt trotzdem.
- Zeitraffer „glatt“ mit einem Filament: Der Turm bleibt, es wird gerundet, aber ohne Befund.

## Niedrig

### L1: Begründung und Archivtext behaupten weiter mehr, als die Sonde zeigt

**Stelle:** `konzepte/begruendungen/regel-druckrat.md:462-469`, gleichlautend im Abschnitt „Nachweis“ von `scratchpad\archiv-rm583.md`.

Gegen `scratchpad\kontakt\pla\*\ergebnis.json`:

- „0,2 mm höher als am Bezug“: Anycubic liegt 0,3 höher (0,4 gegen 0,1).
- „oben liegen mehr Trennschichten“: Creality hat 6 gegen 6.
- „unten keine statt zwei bis drei (Bambu ein Rest gegen drei)“: Bambu misst 5,0 gegen 2,0, der Creality-Bezug 6. Prusa und SuperSlicer wurden umgekehrt gemessen (Ziel 8 bzw. 3 gegen 0).
- „Cura trifft die Abstände genau“: Cura misst 0,6 gegen 0,4 bei geschriebenen 0,4/0,2. Nur der natürliche Lauf zeigt 0,2/0,2.

**Fix.** Je Programm die gemessenen Zahlen nennen oder „geschrieben … gegen …“ schreiben.

### L2: Der `#:`-Block von `FILAMENT_READBACK` hängt am Alias `Readback`

**Stelle:** `app/core/export/slicer_profiles.py:4518-4529`. Das ist derselbe Fehler wie in M3 bei `NOT_TAKEN_BY_PROGRAM`.

**Fix.** Den Alias samt seiner Doku-Zeile über den Block setzen.

### L3: Veralteter Docstring

**Stelle:** `app/core/export/handover.py:3086-3087`, „sagt `frees_support_layers` vor der Trennung je Teil“. Gefragt wird jetzt nach der Trennung, an Platte und Objektwerten bzw. aus der Beilage.

### L4: Tests

- **`slice_model` ungeprüft.** Kein Test prüft, dass `slice_model` den Schalter aus der Beilage liest und in den Prozess schreibt. Ohne `free_support_layers=free_support_layers` in `handover.py:6659` bliebe alles grün. Der Rahmen dafür steht schon in `test_the_console_gets_the_same_plate_as_the_file` (`tests/test_print_settings.py:3457`, `_run_slicer`, `--load-settings`).
- **Ungeprüfte Behauptung.** Der Docstring von `test_whole_layers_stay_inside_the_material_band` sagt „Eine halbe Schicht rundet auf“ (`tests/test_slice_findings.py:1461`), aber kein Fall prüft es: Bei PLA und 0,04 mm entscheidet `first`, und mit `round()` bliebe der Test grün. Den Satz streichen oder einen Fall mit einem Faktor x,5 bauen.

### L5: Changelog

**Stelle:** `changelog/de.md:82` und die fünf Übersetzungen: „Abstand und Trennschichten richten sich nach Material und Schichthöhe“. Die Trennschicht richtet sich aber nach der Fläche darüber (dicht unter flachen Decken, locker an Details), nicht nach dem Material.

### L6: Cura-Lücke bei geänderter Bahnbreite

**Stelle:** `app/core/export/manufacturer.py:2294` gegen `handover.py:1862`.

**Was falsch ist.** Die Grundlage zeigt 2 × die Bahnbreite der Stufe, geschrieben werden 3 × die aktuelle. Wer die Bahnbreite ändert oder einen Rat dazu übernimmt, sieht eine andere Lücke, als gedruckt wird.

**Fix.** Ohne Wahl `width + settings.support.interface_spacing` schreiben oder die Grundlage aus der geschriebenen Breite rechnen.

## Geprüft ohne Befund

**Regeln:**

- 17: keine neue Ausnahme. `_frees_in_project` fängt nur Unlesbares ab und fällt auf die Platte zurück.
- 20: Alle neuen Sätze gehen über `_()` und stehen in allen fünf Katalogen. Die Feldtitel im Changelog stimmen mit den Katalogen überein.
- 21: Fehlt ein Schlüssel, nehmen `prints_a_tower` und `support_layers_findings` die Programmvorgabe: Turm aus, eigene Höhe an (`bambu_PrintConfig.cpp:6003`, `:6256`).
- 6: Auf Fließkomma nur `is_close` bzw. `isclose`, kein `==`.

**Budgets:** `dateiformat.md` 30 715 von 30 720 Byte, Export-Karte 25 595 von 25 600, `druckrat.md` 31 Byte kleiner. Die Last je Quelldatei sinkt um 25 Byte.

**Zwillinge Schreiben/Rücklesen je Familie:**

- Orca: oben und unten für Abstand und Lücke, gelesen wird oben.
- Prusa: oberer und unterer Abstand; −1 unten heißt „wie oben“ über `_bottom_layers`. Den Lüfter bekommt nur SuperSlicer, `_full_cooling` steht in beiden Rücklesern.
- Cura: Höhen und Schalter nur noch in `_for_supports`, `support_interface_enable` aus oben oder unten. Die Dichte 1/3 ist in `cura_motion` und `_contact_density` dieselbe.

**`_frees_in_project` gegen `write_assembly`:** Die Beilage trägt „1“ nur bei Ja, sonst den Herstellerwert oder nichts. Der Rückfall kann nur Ja sagen, wo dieselbe `split.plate` schon Ja ergab.

**M2-Rechnung:** PLA 0,08 → 0,16, PETG 0,1 → 0,2, PLA 0,075 → 0,15, PLA 0,28 → 0,28.

**Kalibrierung schreiben:** `calibration.py:156` und `_as_table` lassen `None` weg.

**Kann das so rein?** Nein. Zuerst H1 (Kontaktzeilen kommen nie zur Ruhe und nennen teils das falsche Teil, bei Cura falscher Druck), M1 (kalibrierte Profile ohne Rat) und M2 (Cura-Warnung bei jeder Übergabe in zwei Stufen) beheben, jeweils mit einem Test, der ohne den Fix rot ist.
