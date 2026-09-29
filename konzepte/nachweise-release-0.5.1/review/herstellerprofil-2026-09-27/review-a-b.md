# Review Stufen A und B — Herstellerprofil als Grundlage

Arbeitsbaum: `F:\3D Druck.minigolf`, Zweig `minigolf-uebergabe`, Stand
`git diff HEAD` (HEAD `0ad19d4b0`) plus unversionierte Dateien
(`app/core/export/manufacturer.py`, `tests/test_manufacturer.py`,
`tests/data/projects/example_v36.p3d`,
`tests/data/projects/print_settings_v35.p3d`).
Maßstab: `konzepte/konzept-herstellerprofil-als-grundlage-2026-09.md`
Abschnitt 3 (A–L) und 4 (Stufen A, B), `AGENTS.md` Regeln 1–22.

Stand des Berichts: **abgeschlossen**. Zeilennummern gelten für den
Arbeitsbaum am 27.09.2026 **nach** den Korrekturen des Hauptstrangs zu F1
und F2 (Zwischenmeldung des Koordinators).

**Urteil: So kann es noch nicht rein.** F1 und F2 (Teil 1) sind behoben und
nachgeprüft. Offen sind fünf Fehler, an denen Werte zum Slicer gehen, die
niemand gewählt hat, oder eine Wahl verloren geht: F3 (Migration macht die
Stufentempi von 0.5.0 zur eigenen Wahl — 72 von 96 echten 0.5.0-Sätzen),
F4 (Skirt/Raft ohne ihr Maß wirkungslos), F5 („Automatisch" bei Cura =
nichts, bei Prusa = immer Brim), F6 (Menüexport schreibt den gespeicherten
statt des wirksamen Satzes), F7 (eigene Lüfter-Obergrenze, unteres Ende
bleibt höher).

Sonden liegen im Scratchpad der Sitzung
(`%USERPROFILE%\AppData\Local\Temp\claude\F--3D-Druck\69f96fd4-…\scratchpad\`,
`probe_*.py`); sie lesen nur, schreiben nichts ins Repository und liefen mit
umgebogenem `APPDATA`/`LOCALAPPDATA`.

---

## Fehler

### F1 — Rundung machte Grundlagewerte zur eigenen Wahl — **behoben, nachgeprüft**

Ursprünglicher Befund: `_collect` sammelte bei jeder Feldänderung alle Felder
ein; ein `QDoubleSpinBox` rundet auf seine `decimals`, und die Rücklesung
liefert Werte, die das Feld nicht trägt. Sonde `probe_base.py` an den
installierten Beständen: Bambu P1S `support.density` 0,168 → Feld 17 % →
0,17; Anycubic Kobra 2 `support.xy_gap` 0,252 → 0,25. Eine Änderung der
Wandzahl machte beide zur eigenen Wahl und schrieb
`support_base_pattern_spacing = 2.47059` bzw. `support_object_xy_distance =
0.25` über das Herstellerprofil.

Nachprüfung: `_collect` ist entfernt. Jeder Editor meldet sich über
`weak_slot(self, PrintSettingsDialog._editor_changed, field.path)`
(`app/ui/print_settings_dialog.py:5432`), `_editor_changed(path)`
(`:5572–5592`) macht nur dieses Feld zur eigenen Wahl und nur, wenn sich
der Wert vom Modell unterscheidet. Die Feldbereiche werden nur beim Bau
gesetzt (`:1226`, `:1242–1244`), programmatische Wertsetzungen laufen unter
`_loading` — ein Klemmen oder Runden erzeugt also keine Wahl mehr. Offen
bleibt nur der Nachweis: Ein Test, der „nur das berührte Feld wird Wahl"
an einer Grundlage mit `support.density = 0.168` festhält, geht nur als
Fenstertest und gehört damit in den Release-Lauf (dazu H4).

### F2 — Stufe auf dem Herstellerprozess wirkungslos — **Teil 1 behoben, nachgeprüft; Teil 2 siehe R6**

Nachprüfung Teil 1: `manufacturer.STAGE_PATHS` (`manufacturer.py:541–549`),
`_stage_values` (`:552–569`), `_runs_the_standard_process` (`:572–587`),
`Foundation.staged`; `written_paths` schreibt `staged` mit (`:686`). Die
Stufe legt ihre Abweichung von Solidons Standardstufe über den
Standardprozess der Maschine; ein selbst gewählter anderer Prozess bekommt
keine Stufe. Das trifft Entscheidung I (Rückfall). `tests/test_manufacturer.py`
`test_a_stage_lies_over_the_standard_process` und
`test_a_chosen_process_is_the_stage` laufen grün. Zwei Anmerkungen:

- Für einen `staged`-Pfad schreibt die Übergabe den Wert aus dem
  **übergebenen** Satz, nicht aus `foundation.settings`. Im Dialog ist das
  der wirksame Satz (richtig); im Menüexport ist es der gespeicherte
  (F6) — dort kann ein veralteter Wert unter einem `staged`-Pfad hinausgehen.
- `_runs_the_standard_process` vergleicht den Dateistamm
  (`handover._profile_name`) mit `default_print_profile`. Ein Profil, dessen
  Dateiname nicht seinem `name` gleicht (Benutzervorlagen), fällt still aus
  der Stufe heraus. Vorschlag: den `name` aus der Profildatei lesen
  (`slicer_profiles._read(...).name`) statt aus dem Pfad.

### F3 — Die Migration 35→36 macht die Stufentempi von 0.5.0 zur eigenen Wahl

**Stelle:** `app/core/scene/migrations.py:890–934`
(`_mark_own_print_settings`), `app/core/knowledge/print_settings.py:571–589`
(`legacy_choices`); Test `tests/test_manufacturer.py:91–102` mit
`tests/data/projects/print_settings_v35.p3d`.

**Beleg:** Sonde `probe_v050_dump.py` + `probe_v050_classify.py`: der Stand
`v0.5.0` per `git archive` in den Scratchpad, dort `resolve` für 8 Drucker ×
PLA/PETG/ABS × 4 Stufen und `print_settings_to_data` — genau der Satz, den
0.5.0 laut Entscheidung E ungefragt ins Projekt schrieb. Danach
`_mark_own_print_settings` aus dem Arbeitsbaum:

| | Sätze | mit „eigener Wahl" |
|---|---|---|
| Stufe Standard | 24 | 0 |
| Fein, Entwurf, Belastbar | 72 | **72** (je 5–8 Tempo-Pfade) |

Beispiel CC2 PLA „Fein": gespeichert 30/45/60/30/18 mm/s, Brücke 20,
Beschleunigung 5000 — heutige Auflösung 120/150/150/150/45, 40, 6250 —
Dataclass 40/60/80/40/20, 25, 8000. Der gespeicherte Wert gleicht keinem der
beiden Vergleiche, also gilt er als Wahl des Kunden
(`speed.outer_wall`, `inner_wall`, `infill`, `top_surface`, `first_layer`,
`bridge`, `acceleration`, bei Prusa auch `outer_wall_acceleration`). Nach der
Migration schreibt die Übergabe diese Tabellenwerte von 0.5.0 über jedes
Herstellerprofil, und der Dialog zeigt sie fett mit „Ihre Einstellung" —
genau das, was Entscheidung E ausschließen soll („Damit fallen die alten
Tabellenwerte heraus"). Die Ausnahme der 40 mm/s (RM-256) greift nur für die
Standardstufe, weil nur deren Werte die Dataclass-Vorgabe sind.

Die eingecheckte v35-Datei belegt das nicht: Sie trägt `app_version 0.5.0`,
aber heutige Werte (`speed.infill 119`, `travel 500`, `bridge 50`,
`acceleration 10000` — 0.5.0 schrieb 80/150/25/8000) und die Stufe
„standard". Der Test prüft damit, dass die heutige Auflösung sich selbst
gleicht.

**Vorschlag:** Die Einordnung braucht als dritten Vergleich den Satz, den
die schreibende Version erzeugt hat. Für 0.5.0 genügt eine eingefrorene
Tabelle der Stufenwerte (in 0.5.0 kamen die Tempi unverändert aus
`print_settings.toml`, `float(stage["speed_…"])`), z. B.
`knowledge/data/legacy/stages_0_5_0.toml`; ein Wert, der dem Wert seiner
gespeicherten Stufe in 0.5.0 gleicht, ist Grundlage. Dazu eine v35-Datei,
die wirklich von 0.5.0 stammt (mit `git archive v0.5.0` erzeugt, Stufe
„fine"), und der Test erwartet `chosen == {…}` ohne Tempo-Pfade.

### F4 — Eine Haftungsart ohne ihr Maß: „Skirt" und „Raft" wirken auf dem Herstellerprofil nicht, „Keine" behält dessen Skirt

**Stelle:** `app/core/export/handover.py:481–519` (`as_mapping` mit
`paths`), `:635–658` (`_only_chosen_adhesion`); `slicer_keys.py:419–426`
(Orca-Zeilen der Haftung).

**Beleg:** Sonde `probe_adhesion.py` am installierten ElegooSlicer
(CC2, „0.20mm Standard @Elegoo CC2 0.4 nozzle", „Elegoo PLA @ECC2"). Die
Grundlage liest `skirt_loops = 0` und `raft_layers = 0`. Nur
`adhesion.kind` als eigene Wahl, `write_config`:

| Wahl | `brim_type` | `skirt_loops` | `raft_layers` | gedruckt |
|---|---|---|---|---|
| none | no_brim | 0 | 0 | nichts |
| skirt | no_brim | **0** | 0 | **kein Skirt** |
| raft | no_brim | 0 | **0** | **kein Raft** |
| brim | outer_only | 0 | 0 | Brim |

Die Art geht als Schalter hinaus, ihr Maß ist aber Grundlage und bleibt beim
Hersteller. `_only_chosen_adhesion` nullt nur Schlüssel, die in `written`
stehen — auf dem Herstellerprofil also nie die Maße der nicht gewählten Art:
„Keine" behält bei einem Profil mit Skirt-Runden den Skirt. Die Wahl des
Kunden geht verloren (Prüfpunkt b); der Dialog zeigt dazu „Raft" mit
„Raft-Schichten 0", ohne Hinweis.

**Vorschlag:** Ist `adhesion.kind` ausdrücklich, gehört sein Maß als
gekoppelter Pfad dazu: `skirt` → `adhesion.skirt_loops`, `raft` →
`adhesion.raft_layers`; ist das Maß der Grundlage 0, beim Setzen der Art im
Dialog Solidons Tabellenwert als `with_choice` mitsetzen. Und die Maße der
nicht gewählten Arten bei ausdrücklicher Art immer als `"0"` schreiben
(außer bei `auto`, dessen Skirt dem Hersteller gehört). Test: Wahl „raft"
auf einer Grundlage mit `raft_layers = 0` schreibt `raft_layers > 0`.

### F5 — „Automatisch" als Haftung heißt bei CuraEngine „nichts" und bei PrusaSlicer „immer Brim"

**Stelle:** `app/core/export/slicer_keys.py:556–560` (Cura
`adhesion_type`, Rückfall `"skirt"`), `handover.py:650–658`
(`_only_chosen_adhesion` behält bei `auto` die Brimbreite und nullt den
Skirt); Dialogfeld `print_settings_dialog.py` `adhesion.kind` mit
`choices=("none", "auto", …)` und dem Satz „Automatisch entscheidet der
Slicer nach Teil und Material".

**Beleg:** Sonde `probe_adhesion.py`, `values_for` mit `adhesion.kind = auto`:
Cura bekommt `adhesion_type = skirt`, `skirt_line_count = 0` — keine Haftung;
PrusaSlicer bekommt `skirts = 0`, `brim_width = 5`, also an jedem Teil einen
Brim (Prusa-Vorgabe `brim_type = outer_only`). Der Dialog bietet
„Automatisch" jedem Slicer an; eine in der Orca-Familie getroffene Wahl
„auto" reist im Projekt zu Cura oder Prusa mit. Entscheidung J sagt „bei den
anderen die Vorgabe des Profils" — für Cura und Prusa ist das bis Stufe C/D
Solidons Tabelle (für PLA: Skirt, zwei Runden).

**Vorschlag:** Für Familien ohne `auto_brim` `auto` beim Schreiben auf die
Art der Grundlage abbilden (`resolve(...).adhesion.kind`), nicht auf den
Rückfall „skirt" mit genullten Runden; im Dialog „Automatisch" für diese
Familien ausweisen (wie `_mark_fields_this_slicer_ignores`) oder den Satz
anpassen. Test je Familie: `auto` ergibt dieselben Schlüssel wie die Art
der Tabelle.

### F6 — Der Menüexport schreibt ohne Herstellerprozess den gespeicherten Satz, nicht Grundlage plus Abweichung

**Stelle:** `app/ui/print_settings_dialog.py:1041–1078`
(`settings_for_export` gibt `document.print_settings` unverändert zurück),
Aufruf `app/ui/main_window.py:7753`; weiter `writer._plate_config`
(`writer.py:1461–1484`, PrusaSlicer: `values_for` über den ganzen Satz) und
`handover.project_settings` ohne Herstellerprozess (`paths is None` → alles).

**Beleg:** Nach Entscheidung A sind die Gruppenwerte ohne Herkunft eine
Momentaufnahme und werden „bei jeder Verwendung neu bestimmt". Dialog
(`on_base(stored, table)` bzw. `_rebase`) und Zahlenzeile
(`effective_print_settings`) tun das, der Menüexport nicht. Drei konkrete
Wege, auf denen dadurch Werte zum Slicer gehen, die niemand gewählt hat:

1. Projekt im Dialog mit ElegooSlicer gespeichert (gespeichert ist der
   wirksame Satz: Elegoos Wände, Tempi, Rückzug), später auf einem Rechner
   mit PrusaSlicer über *Exportieren* als 3MF → `Slic3r_PE.config` trägt
   Elegoos Werte als Solidons Satz.
2. Migriertes v35-Projekt (Stufe Standard, Tempi 40/60/80 nicht als Wahl
   eingeordnet) → PrusaSlicer bekommt 40/60/80, der Dialog zeigt die heutige
   Auflösung.
3. Orca-Familie mit Maschine, aber ohne Prozesswahl (`has_profile` falsch)
   → der ganze gespeicherte Satz geht hinaus.

Vor dem Umbau waren Dialog und Export sich wenigstens einig (beide
gespeichert); jetzt widersprechen sie sich. (Nur beim ersten 3MF-Export
ohne `inventory_project_id` schreibt `_inventory_settings`
(`main_window.py:6977–6983`) vorher den wirksamen Satz ins Dokument; danach
trägt jedes Projekt eine Kennung, und es gilt wieder der gespeicherte Satz.)

**Vorschlag:** Die Grundlage dort bestimmen, wo das Setup feststeht — im
Exportarbeiter nach `remembered_setup` (`main_window.py:1288ff.`, schon
außerhalb des Hauptthreads):
`settings = manufacturer.effective(stored, manufacturer.base_settings(profile, stored.quality, setup))`,
und `settings_for_export` gibt dafür das gespeicherte Dokument samt Stufe
weiter. Test: gespeicherter Satz mit abweichendem Nicht-Wahl-Wert, Export
nach Prusa schreibt den Tabellenwert.

### F7 — Eine eigene Lüfter-Obergrenze lässt das untere Ende beim Hersteller: unten 50 %, oben 20 %

**Stelle:** `app/core/export/handover.py:502` und `:522–536`
(`_fan_curve_in_order` deckelt das untere Ende im Satz, `as_mapping` mit
`paths` schreibt es aber nur, wenn `cooling.minimum_fan_speed` selbst
ausdrücklich ist).

**Beleg:** Sonde `probe_fan.py` am installierten ElegooSlicer (Elegoo PLA:
Grundlage oben 100 %, unten 50 %). Eigene Wahl `cooling.fan_speed = 0.2`
→ Filamentprofil `fan_max_speed = ["20"]`, `fan_min_speed = ["50"]`. Orca
rechnet die Gerade trotzdem (Docstring von `_fan_curve_in_order`): Lange
Schichten laufen mit 50 %, über der gewählten Obergrenze. Derselbe Weg nimmt
den übernommenen Vorschlag „Zugluft auf diesem Material" (`advise`,
`cooling.fan_speed = 0.2` bei ABS/ASA im offenen Bauraum) aus — wo das
Herstellerfilament ein höheres unteres Ende nennt, kühlt der Druck stärker,
als der Vorschlag verlangt.

**Vorschlag:** In `as_mapping` mit `paths`: Senkt `_fan_curve_in_order` das
untere Ende und steht `cooling.fan_speed` in `paths`, gehört
`cooling.minimum_fan_speed` (samt `reduce_fan_stop_start_freq`) dazu. Die
Kopplungen aus F4 und F7 an einer Stelle führen (`COUPLED_PATHS`), damit die
nächste nicht wieder fehlt. Test: Wahl 0,2 über einer Grundlage mit 0,5
unten schreibt beide Enden.

---

## Risiko

### R1 — Kaputte v35-Druckeinstellungen werden in der Migration zum Programmierfehler

**Stelle:** `app/core/scene/migrations.py:923–933`; Ladeweg
`app/core/scene/project.py:1640–1641` (Migration vor der Schemaprüfung des
aktuellen Formats) und `:1800–1806` (`PROGRAMMING_ERRORS` werden
durchgereicht).

**Beleg:** Sonde `probe_migration_edges.py`: `"layers": "x"` →
`AttributeError`, `"quality": ["fine"]` → `TypeError` — beide in
`PROGRAMMING_ERRORS`, also Fehlerbericht statt „Der Projektinhalt ist
beschädigt" mit Handlungsvorschlag. Vor dem neuen Schritt fing
`_validate_current_project_schema` nach der Migration dieselbe v35-Datei
sauber ab (`_nested_mapping` je Gruppe). `spool_bindings: [{}]` und
`"fan_speed": "voll"` enden als `KeyError`/`ValueError` und damit weiter
sauber.

**Vorschlag:** Vor dem Einlesen die Form prüfen und bei Abweichung `data`
unverändert zurückgeben — die Schemaprüfung nach der Migration meldet es
dann richtig: jede Gruppe ein `dict`, `quality` ein `str`,
`spool_bindings`/`slot_profile_bindings` Listen aus `dict`. Test mit
beschädigter v35-Datei: `load` wirft `ValidationError(constraint="damaged")`.

### R2 — Unbekannter oder mitgereister Drucker: die ganze Materialtabelle wird eigene Wahl

**Stelle:** `app/core/scene/migrations.py:926–931`.

**Beleg:** `profiles.make_profile(printer, material)` scheitert für einen
Drucker, den dieser Rechner nicht kennt — auch für einen **mitgereisten**
(`carried_profiles`, seit v30): `profiles.carry` läuft erst in der Sitzung
nach dem Laden (`app/ui/session.py:2076`), die Migration davor. Dann ist
`PrintSettings()` die Referenz. Sonde `probe_migration_edges.py`, CC2-PETG-Satz
unter unbekanntem Drucker: 16 Pfade eigene Wahl (alle Temperaturen,
Kühlung, Rückzug, Filamentwerte, erste Bahnbreite). Mit einem vom Kunden
gewählten Maschinenprofil (`_fits_the_printer`: „Nicht erkannt heißt ja")
gehen sie über das Herstellerfilament — der „PLA Lavendal"-Fall aus
Konzept 1.2. Die Sitzung selbst rechnet in diesem Fall mit
`profiles.scene_profile` (Standarddrucker, gleiches Material).

**Vorschlag:** Als Referenz `profiles.scene_profile(printer, material)`
nehmen — dieselbe Auflösung wie die Sitzung —, besser noch den
mitgereisten Drucker aus `data["carried_profiles"]` mit dem Prüfer von
`profiles.carry` lesen, ohne ihn zu registrieren. Test: v35 mit
`carried_profiles`-Drucker ordnet nur die abweichenden Werte ein.

### R3 — Weitere Leser rechnen mit dem gespeicherten Satz statt mit dem, was gedruckt wird

**Stelle:** `app/ui/session.py:1754` (`Session.profile` →
`for_process(..., document.print_settings)`), `app/core/scene/evaluate.py:402`,
`app/core/agent/analysis.py:80,89`, `app/core/perceive/digest.py:300`,
`app/ui/session.py:3454` (`split_margin`), `app/ui/main_window.py:7301`
(Vorbelegung `FilamentOverrideDialog`), `:7522` (Stützmaterial gegen
G-Code), `:7549` (Schätzung gegen G-Code), `:19263` (Abstand beim Einsetzen).

**Beleg:** Stufe A verlangt „wirksame Einstellungen überall (Dialog,
Prüfbericht, Statuszeile, Übergabe)", Entscheidung A: „jeder Leser
(Schichtanalyse, Schätzung, Plattenränder, Prüfbericht) bekommt … den, der
gedruckt wird". Diese Stellen lesen `document.print_settings` direkt. Die
Gruppenwerte dort sind der Stand des letzten Speicherns — nach einer
Prozesswahl ohne eigene Änderung bleibt `has_changes()` falsch, das Projekt
wird nicht geschrieben, und die Auswertung rechnet weiter mit Schichthöhe
und Bahnbreite des alten Prozesses, während Dialog und Übergabe den neuen
nehmen. Nach der Migration sind es die Werte von 0.5.0. Der Vergleich
„Schätzung gegen G-Code" (`:7549`) misst so gegen Tempi, die nicht gedruckt
wurden.

**Vorschlag:** Eine Stelle für den wirksamen Satz, die auch der Kern
bekommt: Die Sitzung hält die zuletzt bestimmte Grundlage
(`MainWindow._print_foundation` setzt sie), `Session.effective_print_settings()`
liefert `on_base(stored, foundation)`, und `evaluate`/`for_process`,
Digest, Agent und die vier Stellen im Hauptfenster lesen nur noch dort.

### R4 — Druckplatte: bei eigener Maschinenvorlage geraten, ohne Wahl, und eine Sperre ohne Ausweg

**Stelle:** `app/core/export/manufacturer.py:336–352` (`_machine_model`),
`:634` (`… or SINGLE_PLATE`); `SlicerSetup.plate` (`handover.py:176`) wird
von keiner Oberfläche gesetzt; `plate_refuses_filament` nur im Satz
`print_settings_dialog.py:5544–5547`.

**Beleg:**

- Sonde `probe_user_machine.py`: Bambu Studio, eigene Vorlage „Mein P1S"
  (erbt „Bambu Lab P1S 0.4 nozzle") → `plate = "High Temp Plate"`; das
  Herstellerprofil selbst → „Textured PEI Plate". `_machine_model` sucht die
  Modelldatei nur im Ordner der **Vorlage** (`user/…/machine`), Bambu führt
  `default_bed_type` aber nur im Modell. Die Übergabe schreibt dann
  `curr_bed_type = High Temp Plate` und liest die Betttemperatur dieser
  Platte. Das ist geraten (Regel 21); `SINGLE_PLATE` ist laut Kommentar für
  Drucker **ohne** Plattenwahl gedacht, greift aber auch, wenn die Maschine
  nur nicht lesbar ist (`machine_for` leer).
- Konzept H und Stufe B nennen die Plattenwahl im Dialog; sie fehlt. Damit
  läuft der Satz „Der Hersteller gibt diese Platte für dieses Filament nicht
  frei." ins Leere — Konzept F verlangt dazu die Handlung „Andere Platte
  wählen", und im Export gibt es gar keinen Befund; der Slicer bricht dann
  mit „does not support filament" ab. Gemessen am Bestand selten (Nullen für
  texturierte und glatte Platte: je 2 im OrcaSlicer-Bestand, 0 bei Bambu und
  Elegoo), bei „Cool"/„Engineering" häufig (370/310).

**Vorschlag:** `_machine_model` über die Profilwurzeln (`roots`) nach dem
Modell `printer_model` suchen, nicht nur neben der Vorlage; `SINGLE_PLATE`
nur, wenn weder Maschine noch Modell `support_multi_bed_types` nennen, sonst
keine Platte raten und einen Befund geben. Plattenwahl im Dialog bauen
(Stufe B), und `plate_refuses_filament` in `write_config`/`project_settings`
als `Finding` mit `suggestions` ausgeben.

### R5 — `Foundation.foreign` wird nirgends gezeigt: Der Dialog zeigt Solidons Rückfall statt des gedruckten Werts

**Stelle:** `app/core/export/manufacturer.py:15–19` (Modul-Docstring:
„`Foundation.foreign` nennt den Herstellerwert für die Anzeige"),
`:650–654`; `app/ui/print_settings_dialog.py` — kein Leser von `foreign`
(`grep foreign` in `app/ui/` leer).

**Beleg:** Sonde `probe_base.py`: SV06 `infill.pattern = crosshatch`,
`shell.outer_wall_first = "inner-outer-inner wall"`; Kobra 2
`speed.first_layer = "50%"`. Der Dialog zeigt „Gitter", Solidons
Wandfolge und Solidons Tempo; gedruckt wird der Herstellerwert. Entscheidung H
(„Jedes Feld zeigt den wirksamen Wert") und B („der Dialog zeigt den
Herstellerwert mit seinem Namen") sind hier nicht eingelöst; Docstring und
Regeldatei behaupten es.

**Vorschlag:** Für `foreign`-Pfade im Feld einen Zusatz „vom Hersteller:
crosshatch" (Tooltip und sichtbarer Text, Regel 18) und die Zeile als
„nicht übersetzbar" kennzeichnen; ein Wechsel im Feld macht den Wert zur
eigenen Wahl wie bisher.

### R6 — Ein Stufenwechsel verwirft die eigene Wahl und die übernommenen Vorschläge (Bestand; Begründung auf Wunsch)

**Stelle:** `app/ui/print_settings_dialog.py:5594–5614`
(`_quality_changed`), `:3249–3282` (`_resolved`).

**Einordnung:** Kein Rückschritt — vor dem Umbau war es genauso, und der
Docstring legt es fest. Ich halte es trotzdem für einen Fehler der
Begründung, nicht nur der Form:

1. Der Docstring stützt die fehlende Rückfrage auf Regel 19: „rücknehmbar
   ist es über die Stufe, aus der man kam". Das stimmt nicht. Zurück zur
   alten Stufe ergibt deren Werte, nicht die von Hand gesetzten; nach *OK*
   ist `set_print_settings` keine Transaktion (`session.py:2766ff.`), Strg+Z
   holt sie nicht zurück. Rücknehmbar ist nur der ganze Dialog über
   *Abbrechen*.
2. Mit `STAGE_PATHS` sagt der Code jetzt selbst, was eine Stufe ausmacht
   (Schichthöhe, erste Schicht, Wände, Deckschichten, Füllung) — „Tempo,
   Beschleunigung und Kühlung bleiben beim Hersteller". Eine eigene
   Düsentemperatur, eine Stützwahl oder ein übernommener Vorschlag „Stützen
   nötig" haben mit der Stufe nichts zu tun und gehen trotzdem verloren.
   Konzept A zählt „der Kunde hat den Wert selbst gesetzt" als Herkunft,
   Konzept I sagt über den Stufenwechsel nur „stellt das Prozessfeld".

**Vorschlag:** Beim Stufenwechsel nur die Wahl auf `STAGE_PATHS`
zurücknehmen (`without_choice`), alles andere über `on_base` behalten;
Docstring berichtigen. Wer die alte Regel behalten will, braucht nach
Regel 19 eine ehrliche Begründung ohne die Rücknahme-Behauptung.

### R7 — `MainWindow._print_foundation` sucht Slicer und löst Profile im Qt-Hauptthread auf

**Stelle:** `app/ui/main_window.py:19842–19867`, gerufen aus
`effective_print_settings` (`:19809ff.`) nach jeder Auswertung
(`_update_facts`, `:19890`).

**Beleg:** Der eigene Docstring nennt 0,5 s für `remembered_setup` und 0,1 s
für die Profile — bei jedem Wechsel des Schlüssels (Drucker, Material,
Stufe, Profilwahl) und beim ersten Lauf. `remembered_setup` →
`discover.find_program` (PATH, Registry, Ordner); genau diese Suche wurde im
Dialog am 13.09.2026 in `_SlicerWorker` verlegt, weil sie „auf einer
Maschine mit mehreren Slicern Sekunden" kostet
(`print_settings_dialog.py:2606–2612`, `app/ui/CLAUDE.md`). Dazu
`machine_for` → `machine_with_nozzle` (0,35 s je Aufruf, wenn die Maschine
als Name statt als Pfad gemerkt ist).

**Vorschlag:** Die Grundlage in einem Arbeiter bestimmen (wie
`_SlicerWorker`), bis dahin mit der Tabelle rechnen und die Zahlenzeile nach
Eintreffen erneuern; oder der Dialog reicht seine Grundlage beim Schließen
an das Hauptfenster weiter.

### R8 — Der Brim je Teil kommt in keinem echten Ablauf mehr; die Tests bauen einen Zustand, den es nicht gibt

**Stelle:** `app/core/export/writer.py:1048–1059` (`_part_settings` nimmt
nur Vorschläge mit `entry.path in settings.accepted`),
`app/core/slice/advise.py:1200–1230` (`for_part` nur bei
`adhesion.kind ∈ {"skirt", "auto"}`); Tests
`tests/test_export.py:2008ff.` (`with_accepted(settings, "adhesion.kind",
"skirt")`), `:2055ff.`, `:2239ff.`.

**Beleg:** Jeder Vorschlag zu `adhesion.kind` setzt `"brim"`
(`advise.py:608, 837, 856, 870, 1226`). Ist er übernommen, steht
`adhesion.kind = "brim"` in `accepted` — dann liefert `for_part` nichts.
Ist er nicht übernommen, filtert `_part_settings` ihn weg. Die Bedingung
„angenommen **und** noch Skirt/Auto" entsteht nur in den Tests. Folge für
RM-250: ohne Klick kein Brim (gewollt), mit Klick ein Brim an **allen**
Teilen der Platte (`brim_type = outer_only` im Prozess) — nicht „nur an den
Teilen, die ihn brauchen" (Entscheidung G, Changelog-Satz in Konzept §6).
`export.part_setting` kann im echten Ablauf nicht mehr entstehen.

**Vorschlag:** Bis Stufe E ehrlich benennen (Writer-Kommentar, RM-250 im
Register: „mit Übernahme plattenweit"), die Tests über den echten Weg
bauen (`advise.combine` + `advise.apply`) und das tatsächliche Ergebnis
prüfen; den Teil-Test als Vertrag für Stufe E kennzeichnen statt ihn mit
einem erfundenen Zustand grün zu halten.

---

## Hinweis

### H1 — Docstrings behaupten „dem Körper", der Code schreibt plattenweit (Stufe E ist nicht gebaut)

- `app/core/types.py:1455–1462` (`PrintSettings.accepted`): „weil ein
  Vorschlag dem Körper gilt, dessen Geometrie ihn verlangt".
- `app/core/knowledge/print_settings.py:519–523` (`with_accepted`): „er geht
  zum Slicer, und zwar dem Körper, der ihn verlangt".
- `print_settings.py:508–516` (`with_choice`): „meint die ganze Platte,
  nicht mehr den einen Körper".
- `tests/test_export.py:2008ff.` (Docstring): „so bekommt nur das Teil den
  Brim, das ihn braucht".

Heute gehen übernommene Vorschläge über `by_section(..., paths)` in das
Prozessprofil, also an die ganze Platte (R8). Vorschlag: „soll … gelten
(Entscheidung G, Stufe E)" und im Register vermerken. `test_manufacturer.py:36`
schreibt es schon richtig („soll dem Körper gelten").

### H2 — Regel 6: zwei Fließkommavergleiche mit `==`

`app/core/export/manufacturer.py:419` (`if number == 0.0`) und `:468`
(`if spacing == 0.0`). Beide prüfen eine aus Text gelesene Null, wirken also
richtig; die Regel kennt die Ausnahme aber nicht. Vorschlag:
`units.is_zero(number)` bzw. `is_zero(spacing)` — oder am Text entscheiden
(`text.strip() in ("0", "0.0")`), bevor gewandelt wird.

### H3 — Die Gegenprobe prüft die eigene Betttemperatur auf einer anderen Platte nicht

`handover.py:1536–1557` baut `expected` aus den Tabellenschlüsseln; die
eigene Betttemperatur steht nach `_on_the_plate` (`:2174–2189`) aber unter
`textured_plate_temp` o. ä. Geprüft wird stattdessen `hot_plate_temp` — der
Wert des Herstellers. Eine eigene Wahl, die der Slicer verwirft, fiele nicht
auf (Entscheidung K). Vorschlag: bei bekannter Platte den verschobenen
Schlüssel (`manufacturer.PLATE_TEMPERATURES[plate]`, samt
`_initial_layer`) in `expected` aufnehmen.

### H4 — Lambda-Ring an den *Zurücksetzen*-Knöpfen; `weak_slot` je Feld braucht den Release-Fensterlauf

`app/ui/print_settings_dialog.py:5374`:
`reset.clicked.connect(lambda _checked=False, path=field.path: self._reset_field(path))`
— der Knopf ist ein Kind des Dialogs und lebt so lange wie er; nach
`.claude/rules/wartezeit.md` („Ein Rückruf an ein eigenes Kind hält
schwach") ein Ring, der den Dialog bis zum Prozessende hält. Vorschlag: eine
`QButtonGroup` mit einem Empfänger als gebundene Methode (die Regel nennt sie
für Knöpfe einer Schleife die bessere Form) oder
`weak_slot(self, PrintSettingsDialog._reset_field, field.path)`. Dieselbe
Regel vermerkt, dass `weak_slot` je Knopf an der Werkzeugzeile
`test_widget_lifetime` dreimal mit einer Zugriffsverletzung abriss; die
Korrektur zu F1 verbindet jetzt 59 Editoren so. Das gehört ausdrücklich in
den Fensterlauf des Releases. (Bestand daneben: `:4430`
`box.activated.connect(lambda _i, position=index: …)`, derselbe Ring.)

### H5 — Neue Regel in `.claude/rules/dateiformat.md` sagt mehr, als der Code hält

- „Eine 0 °C des Herstellers sperrt die Platte für das Filament und wird nie
  überschrieben." — `_on_the_plate` schreibt eine eigene Betttemperatur in
  den Schlüssel der aufliegenden Platte, auch über eine Null des Herstellers.
- „Der Dialog zeigt den Herstellerwert" (über `Foundation.foreign`) — siehe
  R5.
- Der Abschnitt trägt einen Verifikationsstand („Gemessen am 27.09.2026 …
  0 Abweichungen"); nach `CLAUDE.md` gehört er in `ROADMAP.md`. Er deckt
  zudem eine von sechs Abnahmen der Stufe B (Konzept §4: Minigolf,
  Waschschüssel, Passungsteil × ElegooSlicer, Bambu Studio).

### H6 — Beispieldateien

`tests/data/projects/example_v36.p3d` trägt `print_settings: null` — die
Beispieldatei des aktuellen Formats übt `chosen`/`accepted` nicht aus; der
Rundlauf der neuen Felder hängt allein an Kerntests. Zur v35-Datei siehe F3.

### H7 — Titel und Kennung bleiben nach einem Druckerwechsel im Dialog stehen

`print_settings_dialog.py:3160ff.` (`_scene_profile_changed`) nimmt jetzt
bei `:3204` `on_base(self.settings, resolve(...))`; `on_base` trägt `id` und `title` aus
dem alten Satz mit (`print_settings.py:532–550`). Vorher kam beides frisch aus
`_resolved`. Folge: Prozess- und Filamentname („Solidon Standard · PLA") nach
einem Wechsel mit Materialänderung falsch beschriftet — die Verwechslung, vor
der `_orca_filament` selbst warnt. Vorschlag: `id`/`title` beim Wechsel aus
der neuen Auflösung übernehmen.

### H8 — Der Tooltip von „Automatisch" in Stützen und Haftung passt nicht

`explain_choices` hängt an jeden Eintrag `choice_note(value)`; für `auto`
steht in `app/ui/labels.py:1219` „Der passende Wert wird aus dem Zusammenhang
bestimmt und zieht von selbst mit." — gemeint für Operationsparameter. Für
die Druckeinstellungen heißt `auto` „die Art bestimmt das Profil des
Slicers". Vorschlag: feldbezogener Satz oder eigener Schlüssel.

### H9 — `EPS_SETTING` liegt in `knowledge/print_settings.py`, nicht bei den Vergleichsgrenzen

`print_settings.py:483`. Die Toleranzen für Vergleiche stehen sonst in
`app/core/units.py` (`EPS_GEOM`, `EPS_DISPLAY`, `EPS_MATCH_*`). Keine
Fertigungstoleranz (Regel 7 trifft nicht), aber eine Grenze außerhalb ihrer
zentralen Quelle. Vorschlag: nach `units.py` verschieben, `same_value` auf
`is_close(..., EPS_SETTING)`.

### H10 — `filament_usage` nimmt die Herkunftsmengen in den Abdruck eines Drucks

`app/core/filament_usage.py:213–224` entfernt Identitätsfelder aus
`print_settings_to_data`, aber nicht `chosen`/`accepted`. Derselbe Wert als
eigene Wahl und als übernommener Vorschlag ergibt zwei verschiedene Abdrücke
(„dürfen … keine zwei Drucke machen"). Vorschlag: beide Felder mit
entfernen.

### H11 — Stufe A gegenüber der Konzepttabelle

- Konzept §4, Stufe A: „`base_settings` mit Rücklesung **Orca und Prusa**",
  Abnahme „CC2/Bambu/Prusa … Schlüssel für Schlüssel". `manufacturer.py`
  liest nur die Orca-Familie („PrusaSlicer folgt mit seinem
  Herstellerbündel"); die Kerntests lesen einen nachgebauten CC2-Bestand.
  Sinnvoll auf Stufe C verschoben, aber im Register zu vermerken.
  (Die Sonde `probe_base.py` las CC2, P1S, SV06 und Kobra 2 ohne Fehler
  zurück.)
- Konzept H: „Unter der Kopfzeile steht die Grundlage in einem Satz" — der
  Satz steht im Kasten *Profile des Slicers*, der geschlossen aufgeht
  (`print_settings_dialog.py`, `collapsible(..., open_now=False)`).
- Bauplan §29 zählt „Ohne Herstellerprofil" CuraEngine auf, PrusaSlicer nicht
  — bis Stufe C gehört er dazu. §12 beschreibt `print_settings` noch als
  vollständige Angabe; dass nur `chosen`/`accepted` verbindlich sind und die
  Gruppen eine Momentaufnahme, steht nur in §29.

### H12 — *Werte übernehmen* ohne Herstellergrundlage macht Filamentwerte zu klebender eigener Wahl

`print_settings_dialog.py:4749–4755`: Ohne Herstellerprozess wird jeder Wert
des Filamentprofils `with_choice`. Wählt der Kunde später einen Prozess
(Herstellergrundlage) oder eine andere Spule, bleiben diese Werte eigene
Wahl und gehen über das neue Herstellerfilament — PLA-Temperaturen über
PETG. Der Kommentar dort („sonst kämen sie nie beim Slicer an") trifft nur
den späteren Export. Vorschlag: übernommene Filamentwerte an das Filament
binden (Slotübersteuerung) statt an den Projektsatz, oder beim Wechsel des
Filamentprofils die eigene Wahl an Filamentpfaden anbieten zurückzusetzen.
Mit Herstellergrundlage (`:4722–4743`) nimmt derselbe Knopf die ganze Gruppe
`filament` zurück — auch eine eigene Farbe (`filament.colour`), die kein
Filamentprofil zurückliest.

### H15 — Eine Spulenübersteuerung schreibt ihre ganze Gruppe über das Herstellerfilament

`handover.py:2153–2171` (`_for_the_slot`) nimmt für jede übersteuerte Gruppe
**alle** Pfade in die Abweichung auf. `SlotOverride` ist gruppenweise
(„vorbelegt mit den Projektwerten, ein Wert anders", `types.py:1288–1292`):
Wer an einer Spule nur die Düsentemperatur geändert hat, schreibt auch Bett,
erste Schicht und Kammer über das Herstellerfilament. Bei neuen
Übersteuerungen ist die Vorbelegung jetzt meist der Herstellerwert
(harmlos); Übersteuerungen aus 0.5.0 tragen Solidons Tabellenwerte und
werden von der Migration nicht eingeordnet. Vorschlag: `SlotOverride` eine
eigene Menge der geänderten Pfade geben (Formatschritt) oder beim Schreiben
nur Werte der Gruppe schreiben, die von der Grundlage des Slots abweichen.

### H13 — Stiller Rückfall bei unlesbarem Herstellerprofil

`manufacturer.py:625–629` (`except ExternalToolError`) und
`handover.profile_file` → `None` (nur `_log.warning`): Kann ein gewählter
Prozess nicht gelesen werden, schreibt die Übergabe wieder Solidons ganzen
Satz über das Herstellerprofil — ohne Befund. Der Dialog sagt nur „Ohne
Profil des Herstellers gelten Solidons Vorgaben", nicht warum. Vorschlag: ein
`Finding` mit `suggestions` (`CHECK_SLICER_PROFILE`), wenn ein **gewählter**
Prozess nicht lesbar ist.

### H14 — Bettemperatur der Grundlage bei fehlendem oder gesperrtem Plattenschlüssel

`manufacturer.py:475–525` (`_read_filament`): Die Schleife über
`FILAMENT_READBACK` liest `temperature.bed` zuerst aus `hot_plate_temp`.
Fehlt der Schlüssel der gewählten Platte im Filament oder steht er auf 0,
bleibt dieser Wert der **glatten** Platte stehen — die Grundlage zeigt dann
die Temperatur einer anderen Platte, als gedruckt wird. Vorschlag: bei
bekannter Platte `temperature.bed*` nur aus deren Schlüssel lesen, sonst
Solidons Wert behalten.

---

## Regelcheck (1–22)

Geprüft am geänderten Code; Regeln ohne Berührung sind nicht aufgeführt.

| Regel | Ergebnis |
|---|---|
| 1 Kein Qt im Kern | eingehalten — `manufacturer.py`, `print_settings.py`, `migrations.py`, `serialise.py`, `project.py`, `handover.py`, `writer.py`, `advise.py`, `types.py` ohne Qt-Import (grep); `handover` ↔ `manufacturer` nur verzögert importiert |
| 5 Verträge | `PrintSettings` wächst um zwei Felder mit Vorgabe (abwärtsverträglich); §9 führt `PrintSettings` nicht als Vertrag, §12/§29 siehe H11 |
| 6 Zahlen | H2 (`== 0.0`); `round()` in `manufacturer.py:507` (`_read_filament`) ist die Wandlung in das `int`-Feld, keine Anzeigerundung; `has_changes` vergleicht Tupel mit `!=` — unveränderte Werte, Identitätsvergleich wie vorher |
| 7 Toleranzen | keine Fertigungstoleranz neu; Vergleichsgrenze siehe H9 |
| 10–13 Sicherheit | kein `eval`, kein fremder Quelltext; Profile werden als JSON gelesen; `chosen`/`accepted` sind Punktpfade mit Schema (`project.py:1171–1179`: Liste, ≤ 512, `[a-z_]{1,32}\.[a-z_0-9]{1,64}`) und werden beim Lesen auf bekannte Pfade beschnitten (`serialise._known_paths`); kein absoluter Pfad ins Projekt (Plattenname und Profilnamen bleiben in den Geräteeinstellungen) |
| 14 Herkunft | Gegenprobe weiter `source="gcode"` |
| 15/22 Abhängigkeiten | keine neue |
| 17 Handlungsvorschlag | neue Ausnahmen nur Schema-`ValueError` (vom Ladeweg in `ValidationError` gewandelt); Verstoß im Ergebnis: R1 (Programmierfehler statt Meldung), H13 (Rückfall ohne Befund), R4 (Plattensperre ohne Handlung) |
| 18 Farbe | eingehalten — eigene Wahl: fette Beschriftung **und** sichtbarer Knopf *Zurücksetzen* mit Text, Tooltip und `accessibleDescription` |
| 19 Rückfrage | keine neue; zur Begründung des Stufenwechsels siehe R6 |
| 20 Feste Texte | eingehalten — 17 neue `tr()`/`_()`-Texte, alle in `en`, `es`, `fr`, `it`, `pt` vorhanden und nicht leer (AST-Sonde `probe_texts.py`); `" + "`, `" · "` sind Zeichen |
| 21 Nicht raten | R4 (`SINGLE_PLATE` auch bei unlesbarer Maschine), R2 (Rückfall der Migration); `_PLATE_NUMBERS` rät richtig nicht |
| Sprachregelung | Bezeichner in `app/` englisch, Docstrings und Kommentare deutsch mit echten Umlauten (Diff-Suche nach `ae/oe/ue`-Ersatz: kein Treffer); `tests/test_language_rules.py` grün |

---

## Geprüfter Umfang und Grenzen

**Gelesen:** der vollständige Diff aller 26 geänderten Dateien, die vier
neuen Dateien, die Aufrufer der neuen Funktionen in `app/` und die
betroffenen Karten und Regeln; Konzept Abschnitte 3 und 4.

**Tests gefahren (ohne Fenster, `-m "not windowed and not performance"`,
Ausgabe in Dateien, Exit-Code direkt gelesen):**

| Dateien | Ergebnis | Exit |
|---|---|---|
| `test_manufacturer.py`, `test_advise.py` | 52 passed | 0 |
| `test_print_settings.py` | 459 passed, 4 skipped, 6 deselected | 0 |
| `test_project.py`, `test_export.py` | 404 passed, 1 skipped | 0 |
| `test_language_rules.py`, `test_directory_docs.py` | 407 passed | 0 |
| `test_translations.py` | 130 passed, 1 deselected | 0 |

`ruff check` über die geänderten Dateien: grün; `ruff format --check` über
die sieben Hauptdateien: grün. mypy nicht selbst gefahren (liegt als
`mypy-a2.txt` für einen früheren Stand vor).

**Sonden (nur lesend, Scratchpad):** `probe_base.py` (Rücklesung CC2, P1S,
SV06, Kobra 2 an den installierten Beständen), `probe_v050_*.py`
(Einordnung echter 0.5.0-Sätze), `probe_migration_edges.py`,
`probe_adhesion.py`, `probe_fan.py`, `probe_user_machine.py`,
`probe_texts.py`. Kein Slicer wurde gestartet.

**Nicht geprüft:** Fenstertests (auch nicht die zu F1/H4), Leistung, ein
echter Slicerlauf der geschriebenen Dateien (Gegenprobe gegen G-Code),
PrusaSlicer- und Cura-Konsolenläufe. F4, F5 und F7 sind an geschriebenen
Konfigurationen belegt, nicht an G-Code.
