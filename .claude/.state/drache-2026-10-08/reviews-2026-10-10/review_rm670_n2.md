# Zweite Nachprüfung RM-670 (`F:/solidon-claude-e`, Zweig `claude/lauf-e`, HEAD `409c205d2`) — solidon3d-review, 10.10.2026

04:13–04:51. Gegenstand: `786ff615f` (Behebung N1–N3) und `57850bbe1..409c205d2` (`once_per_read`,
`_once_per_stock`). Worktree sauber, keine fremden Änderungen. Scratch: `scratchpad/rv670n/`.

Gelesen: `git diff 786ff615f..409c205d2` ganz (Code, Regel, Tests), aus `786ff615f` die Teile zu N1–N3
(`_ChosenSetup`, `_stock_now`, `_chosen_with_stock`, `_FoundationWorker._in_one_read`,
`_ExportWorker._assembly_in_one_read`, `_adopt_renewed_choice`, `_READ_BELOW`, `_CURA_STOCK_FOLDERS`,
`_all_files`, `stock_signature`, `_prusa_files`), dazu `_held`, `_held_now`, `_keep`, `_holding_signature`,
`_top_level`, `profile_roots`, `user_roots`, `_family`, `_store_roots`, `_names_in`, `_chain`,
`machine_model`/`_machine_model_in`/`_machine_model_beside`, `_cura_installed`, `_cura_own_containers`,
`_cura_machine_instances`, `cura_resources`, `_kind_of`, `manufacturer.base_settings`/`_base_settings`,
`Foundation`, alle Aufrufer von `machine_model`, `base_settings`, `once_per_read`, `_once_per_stock` und alle
Lesedurchgänge (`single_read()` in `handover`, `writer`, `main_window`, `print_settings_dialog`).

Ausgeführt — am Worktree nichts geändert (pytest mit `-p no:cacheprovider`, `PYTHONDONTWRITEBYTECODE=1`,
gepinnt `/affinity FFFFF0FF`; Sonden und Mutationen liegen im Scratch und kommen über `PYTHONPATH`):
- Grundlauf `test_slicer_profiles.py`, `test_print_settings_ui.py`, `test_export_background.py`,
  `test_ui_export.py` ohne Fenster-, Render- und Leistungsmarken: **456 passed, 378 deselected, Exit 0**.
- 14 Mutationen über das Plugin `rvmut.py` (Quelle einer Funktion im Speicher geändert und per `exec` in den
  Modulnamensraum gesetzt, Methoden am Klassenobjekt ersetzt), je derselbe Testsatz.
- Sonde `test_stale_probe.py` (17 Fälle an Bestandskopien aus `cc2_stock` mit eigenem Kontoordner,
  `system/` und Modelldatei, Cura aus `_family_stock`) und `test_real_probe.py` (4 Fälle am echten
  ElegooSlicer 1.5.3.5: Installation aus `C:\Program Files` nur gelesen, Roberts `user\default` als Kopie aus
  `scratchpad/rm670/env`). Je Fall: Merker mit zwei Exporten füllen, ändern, dann der nächste 3MF-Export
  über `_ExportWorker._assembly()` mit Merker gegen einen ohne jeden Merker (`SETTLE_NS` unendlich, kein
  Lesedurchgang, `forget_holdings`) — Datei (Bytes, ZIP-Uhr fest), Grundlage, Befunde; danach beruhigt
  noch einmal. Läufe: Fixture 17 Fälle, 14 gleich (die drei übrigen unten erklärt); echter Bestand
  **4 passed, Exit 0** (772 s, `_derived` hielt 84 Einträge für den ElegooSlicer).

**Ergebnis: 0 schwer, 0 mittel, 3 leicht. N1–N3 behoben und je durch einen Test gehalten. Der Merker hält
den Bitgleich-Vertrag in allen Änderungsfällen, die die Signatur erfassen soll.**

## 1. N1–N3 aus der Nachprüfung — behoben

| Punkt | Am Code | Gegenprobe (Mutation → rot) |
|---|---|---|
| N1 leere Vorwahl ohne Signatur | `_ChosenSetup.stock` (`app/ui/main_window.py:1480-1492`); `_stock_now` vor dem Lesen, derselbe Slicer wie `remembered_setup` (`:1495-1511`, `print_settings_dialog.py:424-431`); Grundlagenarbeiter fragt `current()` (`:1587`) | `current()` wie vorher an `setup` gebunden: rot `test_an_empty_choice_expires_when_the_printer_is_created_in_the_slicer`, `test_a_remembered_choice_expires_with_its_slicer_stock` |
| N2 Fenster übernimmt die neue Wahl | `renewed` (`:1987-1999`); `_adopt_renewed_choice` übernimmt nur zum jetzigen Schlüssel und rechnet die Grundlage nach (`:10531-10550`) | `renewed` nie gesetzt: rot (2 Tests); Export ohne `current()`: rot (2); Grundlagenarbeiter ohne `current()`: rot (1); `_adopt_renewed_choice` leer: rot `test_the_window_adopts_the_choice_an_export_renewed` |
| N3 Cura und Prusa zählen Programmeinstellungen | Cura nur die Ordner der ersten Ebene aus `_CURA_STOCK_FOLDERS` (`slicer_profiles.py:2539-2547`, `:3444-3447`), Prusa über `_prusa_signature` (`:3346-3347`), `_prusa_files` ohne oberste Ebene des Konfigurationsordners (`:3709`) | Cura wieder ganzer Ordner: rot `test_curas_store_ignores_its_log_and_sees_a_new_machine`; Prusa über `_holding_signature`: rot und oberste `*.ini` wieder drin: rot, je `test_prusas_signature_leaves_out_downloads_and_program_settings` |

Was Curas Leser öffnet, liegt vollständig in `_CURA_STOCK_FOLDERS` (`_cura_trains` liest `extruders/`,
`cura_active_machine` liest `cura.cfg`, wird aber nirgends gehalten).

## 2. Veraltete Stände durch `_once_per_stock`

**Signatur des Bestands** (`_holding_signature`, `slicer_profiles.py:3351-3396`): Programmdatei (realpath,
Zeit, Größe); je eigener Wurzel (`user/<Konto>`, `system/`, Curas Versionsordner) ihr Name und jede Datei
mit Endung `.json/.cfg/.fdm_material/.ini` unter einem Artordner (Orca: `machine/process/filament`
irgendwo, `casefold`; Cura: die Ordner der ersten Ebene); die Installation nur mit realpath und oberster
Ebene (Dateien mit Zeit und Größe, Ordner beim Namen). Dazu im Schlüssel `discover.cache_generation()`.
Was gehalten wird, gehört dem Programm, unter dessen Wurzel der Ordner liegt (`_root_owners`, lexikalisch
über `Path.is_relative_to`; unter Windows ohne Groß-/Kleinschreibung); was unter keiner bekannten Wurzel
liegt (auch `…/ElegooSlicer/user` aus `_store_roots`), gilt nur im Durchgang.

| Fall | nächster Export = ohne Merker? |
|---|---|
| eigenes Profil mit dem Namen einer Basis (Fixture und echter ElegooSlicer) | ja, sofort und beruhigt |
| eigenes Profil gelöscht | ja |
| Name im Profil geändert (Fixture und echt) | ja |
| Datei umbenannt (Fixture und echt) | ja |
| `inherits` geändert (Fixture und echt) | ja |
| Modelldatei unter `system/` ersetzt | ja |
| Modelldatei der Installation ersetzt, mit Update der Programmdatei | ja |
| Update verschiebt eine Basis in eine neue Datei, Programmdatei neu | ja |
| Cura: Drucker dazu, Drucker entfernt, Containerwerte, Container getauscht, Update | ja (alle fünf) |
| zwei Änderungen im selben Takt, gleiche Größe, Export dazwischen | ja — die Beruhigung hält (Gegenprobe unten) |
| Modelldatei der Installation ersetzt, Programmdatei gleich | **nein** (Platte `Textured PEI Plate` statt `High Temp Plate`) — L2 |
| Basis der Installation verschoben, Programmdatei gleich | nein — Grenze wie bei `_holdings` |
| Name geändert bei gleicher Größe und von Hand zurückgesetztem Zeitstempel | nein — Grenze jeder Signatur aus Pfad, Zeit, Größe |

Die zwei Fälle „Programmdatei gleich“ sind die dokumentierte Annahme (`_holding_signature`, Docstring): Am
ElegooSlicer tragen `elegoo-slicer.exe` und `ElegooSlicer.dll` die Bauzeit des Pakets (19.08.), und
`resources/profiles/Elegoo.json` auf der obersten Ebene trägt die Fassung (`01.05.03.05`); ein Update ändert
beides. Übrig bleibt die Hand im Programmordner. **Netzlaufwerk und anderer Pfad**: Die Zuordnung ist
lexikalisch; eine andere Schreibweise desselben Ordners findet keinen Eigentümer und rechnet im Durchgang
(langsamer, nie veraltet). Gröbere Zeitstempel (FAT 2 s, Freigaben mit 1 s) deckt `SETTLE_NS = 2 s`; eine
Freigabe, deren Uhr der lokalen um mehr als 2 s nachgeht, öffnete das Fenster für zwei Änderungen im selben
Takt wieder — dieselbe Grenze wie bei `_holdings`, kein neuer Befund.

## 3. Nebenläufigkeit — ohne Befund

Sonde `test_threads_probe.py` (gepinnt, 2 passed, Exit 0): zwei Fäden mit je sechs 3MF-Exporten über
`_ExportWorker._assembly()` und ein dritter mit sechs Vorwahl-Durchgängen (`find_profiles` aller Arten,
`base_settings`, `machine_model`), gleichzeitig gestartet. Ohne Änderung: 12 Dateien, alle gleich der ohne
Merker gelesenen, `_derived` hielt danach 8 Einträge. Mit einer eigenen Basis, die ein Faden mittendrin
anlegt: zwei Fassungen der Datei (vorher, nachher), der erste Export nach dem Ende aller Fäden gleich der
frisch gelesenen; keine Ausnahme in keinem Faden.

- `once_per_read` liegt im fadenlokalen `_SINGLE_READ`: Export- und Grundlagenarbeiter teilen nichts.
- `_derived` und `_root_owners` nur unter `_HOLDINGS_LOCK` (Lesen, Ablegen, Verdrängen); gerechnet wird
  außerhalb. Halbe Einträge gibt es nicht: Das innere Dict wird unter der Sperre ergänzt und gelesen.
- Ein Wert, der nach einer Änderung gerechnet, aber unter der älteren Signatur abgelegt wird, trifft nur
  einen Durchgang, dessen Signatur ebenfalls vor der Änderung entstand — und der läse frisch dasselbe. Ein
  Fehler wird nicht abgelegt (`compute` wirft vor dem Ablegen).
- Gehaltene Werte sind unveränderlich oder werden nie verändert: `Foundation` ist `frozen`; Namensindizes,
  Cura-Auflistungen und Modell-Dict ändert kein Aufrufer (Suche nach Zuweisungen und `update/pop/setdefault`
  an `indexes[...]`, `index`, `model`, `foundation.*` in `app/core/export/`: nur `index.update(indexes[...])`
  in `_cura_definition_values`, das in ein eigenes Dict kopiert).
- `_held` wartet auf ein laufendes Lesen; ein Lesen wartet selbst nie (`_orca_profiles`, `_cura_profiles`
  rufen kein `_held`), also kein Zyklus. Der Grundlagenarbeiter kann während des Wartens nicht abbrechen —
  vorher las er im selben Fall selbst, ebenso unabbrechbar.
- Im Oberflächenfaden läuft ein Durchgang (`PrintSettingsDialog._profiles_found`); dort erhebt
  `_once_per_stock` jetzt die Signatur (ElegooSlicer rund 0,1–0,24 s CPU) statt Namensindizes und Modellsuche
  (rund 0,5 s) — weniger als vorher.
- Randfall ohne praktische Folge: Zwei Installationen derselben Familie mit gemeinsamem Konfigurationsordner
  (Orca stabil und Nightly) überschreiben sich `_root_owners`; nur bei gleichzeitigen Durchgängen beider
  könnte eine Modelldatei von A unter Bs Signatur landen.

## 4. Bitgleich-Vertrag und Testqualität

- **Zähltests sind scharf**: Mit `once_per_read` ohne Wirkung (Stand vor `f80d5d1d7`) sind
  `test_a_3mf_export_derives_the_foundation_once[orca|prusa|cura]` rot, mit `_once_per_stock` ohne Halten
  (Stand vor `1d4f7d3de`) `test_a_second_3mf_export_lists_no_stock_folder_again[orca|cura]` und
  `test_inheritance_indexes_hold_across_passes_until_the_stock_changes`; beide mit Wächter gegen leer
  (`len(asked) > 1`, `assert first`).
- **Der Bytetest** (`test_the_remembered_stock_writes_the_file_a_fresh_read_writes`) ist als Vertragstest
  richtig grün an beiden alten Ständen, aber stumpf gegen veraltete gehaltene Ordner (L1).
- Größte Abweichung mit gegen ohne Merker in den erfassten Fällen: keine — Datei, Grundlage und Befunde
  gleich.

## Leicht

### L1 Die Schutzlogik des neuen Merkers prüft kaum ein Test, und der Bytetest sieht keinen gehaltenen Ordner

Stellen: `app/core/export/slicer_profiles.py:183-220` (`_once_per_stock`); `tests/test_print_settings_ui.py`
(`_family_stock`: `user_roots` leer für Orca und Prusa, `cc2_stock` ohne Modelldatei;
`_change_family_stock` ändert Werte und die Programmdatei); `tests/test_slicer_profiles.py:5716-5762`.

Beleg (Mutationen, je 456 Tests):

| Mutation in `_once_per_stock` | Suite | Sonde |
|---|---|---|
| Signatur ignoriert | rot nur `test_inheritance_indexes_hold_across_passes_until_the_stock_changes` | 9 von 16 Fällen andere Datei (eigene Basis, Name, Datei umbenannt, Modelldatei in `system/` und nach Update, Update verschiebt Basis …) |
| ohne Beruhigung (`SETTLE_NS`) | **grün** | „zwei Änderungen im selben Takt“: andere Datei (am HEAD gleich) |
| Beruhigung an der Uhr nach dem Rechnen | **grün** | — |
| Stand der Programmsuche ignoriert | **grün** | — |

Die vier Zwillinge (`_held`, `_prusa_store`, `_prusa_models`, `_program_folders`) haben je einen Test für die
Uhr vor dem Lesen und `_held` einen für `forget_cache` (N5, L3, N6); der fünfte Merker hat keinen
(`zwillinge.md`). Der Bytetest ändert nach dem Merken nur Werte, die jeder Durchgang ohnehin frisch liest, und
die Programmdatei: Er bleibt grün, auch wenn `_derived` die Signatur gar nicht prüft — seine Zusicherung „der
nächste Export sieht den geänderten Bestand“ prüft den Merker nicht.

Fix: In `test_slicer_profiles.py` neben dem Indextest drei kurze Tests nach dem Muster von
`test_the_settle_time_is_taken_before_the_read` und `test_a_new_search_forgets_the_held_stock`: Uhr knapp
unter `SETTLE_NS` → der zweite Durchgang baut den Index neu; langsames `_names_in`, das die Uhr über
`SETTLE_NS` schiebt → nicht gehalten; `discover.forget_cache()` → neu gebaut. Den Bytetest für Orca um einen
Kontoordner erweitern (eigener Prozess über eine eigene Zwischenstufe, Modelldatei) und nach dem Merken dort
ändern, ohne die Programmdatei anzufassen (eigene Basis mit Basisnamen, Name im Profil) → Datei gleich der
frisch gelesenen; Vorlage `scratchpad/rv670n/test_stale_probe.py` (`_orca`, `_base_name`, `_renamed_name`,
`test_two_changes_in_one_tick`).

### L2 Die Modelldatei hält ihre Werte, nicht nur ihren Ort

Stellen: `slicer_profiles.py:4820-4862` (`machine_model` hält das gelesene Dict unter der Signatur), gegen
`.claude/rules/druckerwahl.md:94-100` („denn sie sagen nur, welches Profil wo liegt; Werte liest jeder
Durchgang aus den Dateien“) und den Kommentar an `_derived` (`:166-175`); der Docstring von `machine_model`
sagt „Im Lesedurchgang einmal je Maschine“, gehalten wird über Durchgänge.

Beleg: Sonde „Modelldatei der Installation ersetzt, Programmdatei gleich“ — nächster Export mit Merker
`plate='Textured PEI Plate'`, ohne Merker `'High Temp Plate'`, Datei verschieden. Unter der Annahme des
Merkers (die Installation ändert sich nur mit einer neuen Fassung) gleichwertig, aber die Regel verspricht
mehr, und es kostet fast nichts, sie zu halten.

Fix: `_once_per_stock` hält den Pfad (`_machine_model_path(...) -> Path | None`), `machine_model` liest ihn je
Durchgang über `once_per_read(("machine_model", …), lambda: _load(path) or {})`; Docstring anpassen. Oder die
Regel ehrlich machen — dann aber auch den Kommentar an `_derived`.

### L3 Kleinigkeiten in Unterlagen des Merkers

- Seit `ab30280cb` hält `_once_per_stock` auch Curas Auflistung (`_cura_installed`,
  `_cura_own_containers`). Die drei Stellen, die sagen, was über den Durchgang hält, nennen nur Namensindizes
  und Modelldatei: `single_read` (`slicer_profiles.py:120-125`, dort „der Orca-Familie“), der Kommentar an
  `_derived` (`:166-168`) und die Regel (`.claude/rules/druckerwahl.md:97-100`). Die Regel zählt danach auf,
  was über Aufrufe hält („nur … `_prusa_store` und … `_holdings`“, `:100-103`), ohne `_derived`. Je ein
  Halbsatz.

## Geprüft ohne Befund

- `once_per_read`-Schlüssel: `Profile`, `QualityPreset`, `SlicerSetup` sind eingefroren und vergleichen alle
  Felder (kein `compare=False`); die Grundlage hängt nur an ihnen und am Bestand des Durchgangs.
- Cura-Auflistungen halten nur Kennung → Datei; Containerwerte liest `changes()` je Durchgang.
- `_root_owners` wächst nur mit Wurzeln bekannter Programme; `forget_holdings` leert `_derived` und
  `_root_owners`.

**Kann landen.** N1–N3 sind behoben und gehalten, der Merker liefert in allen 18 Änderungsfällen, die seine
Signatur erfassen soll, dieselbe Datei wie ein Lesen ohne Merker — am Fixture wie am echten ElegooSlicer.
L1–L3 sind leicht und gehören vor dem Merge noch dazu (Tests und Unterlagen, L2 wenige Zeilen); eine weitere
Prüfrunde braucht es dafür nicht.
