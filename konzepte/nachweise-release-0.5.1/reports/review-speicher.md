# Review: Zweig `speicher-ohne-prozesswerte` (28.09.2026)

Endcommit `23bd961d4`, Basis `cbef27715`, ein Commit, 13 Dateien. Geprüft
unabhängig für die Release-Sitzung 0.5.1, nur lesend im Hauptbaum; Läufe in
eigenen Arbeitsbäumen (`wt-revspeicher` am Endcommit, `wt-revspeichermerge`
als nicht committete Probe-Zusammenführung mit `origin/main` = `6eacc1a63`),
beide danach entfernt.

**Urteil: mergebar ja.** Im heutigen Stand liest keiner der zwölf
freigestellten Schritte einen Prozesswert, direkt oder über Hilfsfunktionen;
ein falscher Treffer ist nicht zu finden. Die Wache, die das künftig sichern
soll, hat eine Lücke (F1), die vor dem Tag mit einem fertigen Patch
geschlossen werden sollte. Roberts gemessene Wartezeit nach „Im Slicer
öffnen“ bleibt nach dem Merge im Wesentlichen bestehen (F2).

---

## 1. Wie entschieden wird, wer die Prozesswerte liest

- **Ein Attribut am Register**: `OperationSpec.reads_process`
  (`app/core/registry/registry.py:687`), `register_op(reads_process=True)`
  (`:1044`). **Vorgabe: liest.** Eine neue, nicht eingestufte Operation
  behält die Prozesswerte im Schlüssel und rechnet nach einer Änderung neu.
- **Eine Liste im Test**: `_STEPS_WITHOUT_PROCESS` (`tests/test_cache.py:611`);
  `test_only_proven_steps_leave_the_process_values_out` (`:630`) verlangt, dass
  die freie Menge des Registers genau diese Liste ist, und dass fünf benannte
  Leser (`:639`) die Vorgabe behalten.
- **Eine Wache**: `_ProcessGuard` bricht beim Lesen jedes Prozesswerts ab
  (Schichthöhe, Bahnbreite, Überhanggrenze, `smallest_detail`, die sechs
  abgeleiteten Eigenschaften am Profil, die Materialprobe);
  `test_a_step_without_process_values_never_reads_one` lässt die freigestellten
  Schritte daran laufen. Dass sie dabei nicht jede Listenzeile erreicht, ist F1.
- Im Schlüssel (`hashing._profile_parts`): Prozesswerte sind genau die drei
  Felder, die `profiles.for_process` setzt (`app/core/knowledge/profiles.py:826–833`),
  dazu `minimum_wall_thickness` und `overhang_limit_degrees`. Ein Schlüssel ohne
  Prozesswerte trägt die Marke `without-process` und ist kürzer; er kann einem
  vollen nie gleichen. Der volle Schlüssel ist bytegleich zur alten Formel
  (Filamentbuchungen, `filament_usage.py:248`; Test gegen die alte Formel).

**Einstufung aller 142 registrierten Operationen** (Liste am Arbeitsbaum aus
dem Register erzeugt): 12 frei, 130 mit Vorgabe. Alle in der Aufgabe genannten
Leser behalten die Vorgabe: *Druckoptimal ausrichten* (Überhangwinkel,
Bahnbreite, halbe Schichthöhe, `smallest_first_layer`), die Teilungen samt
Auto Split, *Aushöhlen*, *Skalieren* und *Auf Maß bringen*
(`smallest_printable_volume`), *Auf dem Bett anordnen*, *Textur aufbringen*
(`smallest_detail`, `layer_height`), Beschriftung, alle Bausteine. Passungen
mit `auto:`-Toleranz lesen Materialfelder, die fest im Schlüssel jedes Schritts
stehen; ihre Prüfung (`check_fits`) und die Wandprüfung (`check_thin_walls`
über `analysis_limits`) laufen am Endstand jeder Auswertung mit dem aktuellen
Profil (`evaluate.py:1215–1263`), nicht unter einem Schrittschlüssel. Die
Stützsperre ist keine Operation, sie entsteht in der Übergabe
(`export/handover.py`). Die Schichtanalyse ist keine Operation.

### Die zwölf freigestellten Schritte, am Code nachgelesen

| Schritt | liest vom Profil | Beleg |
|---|---|---|
| `load` | nur `printer.build_volume` | `ingest/ops.py:319` (glTF-Plausibilität), `:681` (Einheitenfrage); `threemf`, `read_model`, `normalise`, `_group_on_bed`, `bed_offset` ohne Profil (`loader.py`, `threemf.py` ohne jeden Profilzugriff) |
| `load_step` | nichts | `step_ops.py` ohne `ctx.profile`; Tessellation mit der Konstante `kernel.DEFLECTION = MAX_FACET_SAG` (`brep/kernel.py:46`), nicht mit `Profile.export_deflection` |
| `load_outline` | nichts | `outline.extrude(payload, suffix, height, width, contours)` |
| `duplicate_object`, `rename_object`, `delete_object` | nichts | `scene/ops.py:41–143` |
| `pattern` | nur `build_volume` | `scene/ops.py:347`, `:387` |
| `translate_object`, `rotate_object` | Druckfläche, Sperrzonen, Druckhöhe, Bauraum | `_held_on_bed` (`geom/ops.py:135`) → `build_area` (`:37`, `:68–74`) → `prepare.back_onto_bed` (`prepare.py:2796`) → `placement_offset`, `arrange_on_bed` (`:2570`), `check_build_volume` (`:2916`), `_overfull`, `_fits_alone`, `_runs_into` → `check_collisions` ohne Profil |
| `mirror_object`, `place_on_bed`, `place_group_on_bed` | nichts | `geom/ops.py:623–647`, `:1052–1062`; `transform.py` ohne Profilzugriff |

Kein `isinstance` gegen Profiltypen im Kern, kein breites `except` auf diesen
Wegen: Die Wache kann dort nicht umgangen werden. `main` hat seit der Basis auf
diesen Wegen nur `loader.moved_findings` (Rand einer Öffnung) und den
3MF-Leser (Stückgrößen) geändert, beides ohne Profilzugriff.

### Was nach dem Schritt geschieht

`_with_features` bekommt kein Profil (`evaluate.py:985–1033`). Der Objekthash
entsteht aus dem Schrittschlüssel (`:1094`) und bleibt bei freien Schritten
jetzt über eine Prozessänderung gleich. Seine Verbraucher: Anzeigenetz
(`viewport.py:6726`, `:7061`, `:7945`), Vorschaubilder (`panels.py:1804`),
Kantenbindung (`edge_binding.py:144`), Schlüssel späterer Schritte. Alle sind
reine Geometrie; kein Verbraucher vergleicht Hashes, um eine prozessabhängige
Anzeige auszulassen. Die Analysekarten schlüsseln mit dem vollen Profil
(`main_window.py:13288–13299`). Die Merker je Netz (`features.remembered`)
sind nach Geometrie geschlüsselt, `autosplit._room_across` nach dem ganzen
Drucker.

---

## 2. Funde, nach Schwere

### Blockiert den Merge

Keine.

### Vor dem Tag

**F1. Die Wache läuft über eine zweite, von Hand geführte Liste, nicht über
`_STEPS_WITHOUT_PROCESS`.**

- `tests/test_cache.py:720–736`: Die Fälle der Wache sind ein Literal mit zwölf
  Namen. `:737ff` prüft nur `case in _STEPS_WITHOUT_PROCESS`, nicht die
  Gegenrichtung. `:834–836`: Der letzte Zweig ist ein bloßes `else`, das jeden
  unbekannten Fall wie `place_group_on_bed` behandeln würde.
- Die Unterlagen sagen das Gegenteil: `registry.py:702` („lässt jede davon an
  einem Profil laufen“), `app/core/scene/CLAUDE.md:143` („das jede davon an
  einem wachenden Profil laufen lässt“),
  `konzepte/begruendungen/karte-app-core-scene.md:481`. Wer nach der Karte
  einen Schritt freistellt, trägt ihn in Register und Liste ein und bekommt
  keinen Wachlauf.
- **Beleg (Gegenproben im eigenen Arbeitsbaum):**
  - G2: `orient_for_print` in Register und Liste frei: rot nur, weil es unter
    den fünf fest benannten Lesern steht (`:639`); die Wache lief weiter über
    zwölf Fälle.
  - G3: `apply_texture` (liest `printer.smallest_detail`,
    `texture_ops.py:525`, und `printer.layer_height`, `:552`) in Register und
    Liste frei: `tests/test_cache.py` 170 bestanden,
    `test_texture.py` + `test_texture_ops.py` + `test_registry_consistency.py`
    1125 bestanden, Exit 0.
  - Dass daraus ein echter falscher Treffer würde, zeigt die Sonde
    `F:\3D Druck.review-051\sonden\revspeicher\test_zz_revspeicher_sonde.py`
    (zum Fahren nach `tests/` eines Arbeitsbaums kopieren, nicht einchecken):
    Lochplatte laden, Rippe mit Teilung 1,04 mm (schmalste Stelle 0,52 mm) auf
    die Oberseite, dann Bahnbreite 0,42 → 0,62 mm. Mit G3 kam der
    Texturschritt aus dem Speicher (0 Aufrufe), die Auswertung lief ohne
    Befund durch; am Zweigstand rechnet er neu und sagt ab
    (`op.apply_texture.ValidationError`), wie er soll.
  - Der Fall trifft den üblichen Weg: Er braucht eine Kette davor, die ihren
    Schlüssel behält, also genau Laden, Kopieren, Verschieben. Mit
    `create_box` davor rechnete die Sonde auch mit G3 neu.
- Dazu, gleiche Familie: `tests/test_cache.py:827` nimmt auch
  `transform.nudged_onto_bed` an, obwohl der Kommentar darüber den Weg über
  `arrange_on_bed` zusagt. Heute läuft dieser Weg (G4: `arrange_on_bed` liest
  zur Probe die Bahnbreite → Wache für Verschieben und Drehen rot); die
  Zusicherung hält ihn nicht fest.
- **Fix:** `F:\3D Druck.review-051\reports\review-speicher-waechter.patch`
  (nur `tests/test_cache.py`): Fälle aus `sorted(_STEPS_WITHOUT_PROCESS)`,
  letzter Zweig ausdrücklich `elif case == "place_group_on_bed"`, sonst
  `pytest.fail(f"{case} is exempt but has no guarded run here")`, und
  `assert "transform.rearranged_on_bed" in codes`. Fallnamen bleiben gleich.
  Geprüft: am Zweigstand 170 bestanden; mit G3 rot
  (`[apply_texture] is exempt but has no guarded run here`); `ruff check` und
  `ruff format --check` sauber; greift unverändert auf dem zusammengeführten
  Stand.
- **Schwere: vor dem Tag, blockiert den Merge nicht.** Die zwölf von heute
  sind richtig und laufen alle an der Wache. Aber der Bericht des Zweigs nennt
  in Frage 3 `arrange_bed` und `set_material` als nächste Kandidaten, und die
  Unterlagen versprechen einen Schutz, den der Test nicht leistet.

### Nach 0.5.1

**F2. Die gemessene Wartezeit bleibt, und die offene Frage steht in keinem
Register.**

- Kundensicht: Laut Messung des Zweigs (Bericht, Tabelle „Im Wechsel“) sinkt
  die zweite Auswertung am Minigolf-Satz nicht messbar; über 98 % sind die
  beiden `orient_for_print`-Schritte, die die drei Werte zu Recht lesen.
  Einlesen und Kopieren entfallen (bei großen 3MF-Baugruppen sind das
  Sekunden), das Symptom „gut 2 min nach *Im Slicer öffnen*“ nicht. Der
  vorgeschlagene Changelog-Satz des Berichts sagt das ehrlich; er darf nicht
  zu „schneller nach dem Druckdialog“ werden.
- Die offenen Fragen stehen nur in
  `output/review/speicherschluessel-2026-09-28/bericht.md`; `/output/` ist
  ignoriert (`.gitignore:61`). Im Register von `ROADMAP.md` (`origin/main`
  durchsucht) steht nichts dazu. Projektregel: offene Arbeit steht dort und
  nirgends sonst.
- Spur zur offenen Frage (am Code gelesen, **nicht am Lauf belegt**): Die
  Sitzung wertet mit dem wirksamen Profil aus (`Session.evaluation_profile`,
  `app/ui/session.py:1767–1779`, `effective=True`), `_evaluate` überschreibt
  Schichthöhe und Bahnbreite aber wieder mit den gespeicherten Einstellungen
  (`app/core/scene/evaluate.py:403`, ohne `effective`). `evaluation_follows`
  (`session.py:1781–1795`) vergleicht dagegen die wirksamen Werte. Und
  `_plate_job` schreibt beim ersten Öffnen ohne `inventory_project_id` die
  Einstellungen des Dialogs ins Projekt
  (`app/ui/print_settings_dialog.py:6905–6907`). Weichen die wirksame und die
  gespeicherte Schichthöhe oder Bahnbreite voneinander ab, ändert erst dieser
  Schreibvorgang die Werte der Auswertung, und jeder Leser rechnet neu. Das
  Auswertungsprofil wird damit an zwei Stellen mit verschiedenen Regeln
  hergeleitet, ein Zwilling im Sinne von `zwillinge.md`.
- **Fix:** RM-Eintrag im Register mit dieser Spur, der Messung und den Fragen
  1 bis 3 des Berichts, gern mit dem Merge; die Arbeit selbst nach 0.5.1.

---

## 3. Weitere Prüfpunkte ohne Fund

**`CACHE_FORMAT_VERSION` 31 → 32.** Ältere Einträge verwerfen sich dreifach:
Die Version steht in jedem Schlüssel (`hashing.py:159`), der Plattenleser
verwirft ein anderes `format_version` (`cache.py:762`), und jede Fassung hat
ihren Ordner (`paths.py:94`: `APP_VERSION` + Kernstempel + Stempel der eigenen
Bausteine), fremde räumt `drop_other_versions` (`cache.py:686`). Einträge aus
0.5.0 liegen in deren Ordner und würden auch sonst nicht treffen;
Zwischenstände aus Quellen haben ihren eigenen Stempelordner. Unter allen
Remote-Zweigen trägt nur dieser 32 (die übrigen 31, ein alter Zweig 28); keine
Doppelbelegung.

**Merge mit RM-212.** `git diff aa82afdff 48f5231c3 -- app/core/scene/hashing.py`
ändert nur Importe (`array`, `Buffer`, kein `numpy`) und `_index_bytes`; der
Zweig ändert Moduldocstring, `_profile_parts`, `profile_key`, `operation_hash`.
Keine Überschneidung. Probe-Zusammenführung mit `origin/main` `6eacc1a63`:
automatisch, beide Seiten vorhanden (`array("q")`, `Buffer`, kein
`numpy`-Import; `process=`, `CACHE_FORMAT_VERSION = 32`, zweimal
`process=spec.reads_process`). RM-212 baut keine eigenen Schlüssel (der
Hilfsprozess rechnet Netzkernaufrufe, keine Schritte). Auch die Änderungen von
`main` an `test_cache.py` (Import aus `tests.helpers`, Randtest) laufen
sauber zusammen. Tests und mypy am zusammengeführten Stand grün (Abschnitt 5).

**Regeldurchgang** (`/regelcheck`, am Diff): Regel 1 kein Qt; 2 und 3 nicht
berührt; 4 kein neuer Schritt, nur ein Registerattribut; 5 §9 und §10 führen
die Registerfelder nicht abschließend (`reads_other_bodies` fehlt dort
ebenso), kein Vertragsbruch; 6 kein Fließkomma-`==` (`kind is _FIXED`
vergleicht Wahrheitswerte); 7 bis 9 nicht berührt; 10 bis 15 nicht berührt;
16 bis 20 keine Oberfläche, kein Agent, keine neue Ausnahme, kein neuer Text;
21 nicht berührt; 22 keine Abhängigkeit. Bezeichner englisch, Kommentare
deutsch mit Umlauten. `OperationSpec` wird überall mit Schlüsselwörtern gebaut
(`registry.py:1068`, zwei Tests), das neue Feld in der Mitte verschiebt
nichts.

**Handwerk.** Kein stilles `except`, keine neue Datei, keine Rechnung im
Hauptthread. Die Tests prüfen ihre Voraussetzungen mit (Änderung erreicht das
Profil, erste Auswertung erkennt, geänderte Werte zugesichert); Sollwert des
vollen Schlüssels ist die alte Formel mit benannter Herkunft.
Projektformat bleibt 37, `migrations.py`, `serialise.py`, `project.py`
unberührt.

---

## 4. Gegenproben

| Probe | Änderung im eigenen Arbeitsbaum | Ergebnis | erwartet |
|---|---|---|---|
| G1 | `orient_for_print` `reads_process=False` nur im Register | 4 rot: Listentest und alle drei Dialogfälle (`orient_for_print` 0 statt 1 Aufruf) | rot |
| G2 | G1 und Eintrag in `_STEPS_WITHOUT_PROCESS` | 4 rot (über `:639` und die Dialogfälle); Wache weiter nur 12 Fälle | rot |
| G3 | `apply_texture` frei in Register und Liste | `test_cache.py` 170 grün; Textur- und Registertests 1125 grün | **rot erwartet, grün: F1** |
| Sonde + G3 | Bahnbreite 0,42 → 0,62 mm nach Laden und Textur | Textur aus dem Speicher, keine Absage | falscher Treffer belegt |
| Sonde am Zweigstand | dieselbe Folge | Textur rechnet neu, `ValidationError` | richtig |
| G4 | `arrange_on_bed` liest `extrusion_width` | Wache für Verschieben und Drehen rot | rot |
| alter Schlüssel | `process=True` an beiden Stellen in `evaluate.py` | 3 Dialogfälle rot | rot |
| Fix + G3 | Patch aus F1, dann G3 | `[apply_texture]` rot | rot |

Alle Proben wurden zurückgenommen; die Arbeitsbäume sind entfernt.

## 5. Läufe

Gebunden (`/affinity FFFFF0FF`), Protokolle in `F:\3D Druck.review-051\laeufe\`,
Ergebnis aus der Zeile `EXIT`. Fenster- und Leistungstests nicht gefahren
(nur beim Release); kein Gesamttor, nur gezielte Dateien.

| Protokoll | Stand | Umfang | Ergebnis |
|---|---|---|---|
| `rev-sp-1` | `23bd961d4` | `test_cache`, `test_registry_consistency`, `test_resin`, `test_gesture_ops`, `test_filament_usage`, `test_agent_mirror`, `test_directory_docs`, `test_language_rules`, `test_native_references`, `test_print_settings` | 2421 bestanden, 7 übersprungen, 6 abgewählt (Fenster), Exit 0 |
| `rev-sp-2` | `23bd961d4` | die 7 neuen Tests einzeln | 20 von 20 gesammelt und bestanden (STEP nicht übersprungen), Exit 0 |
| `rev-sp-ruff`, `rev-sp-format` | `23bd961d4` | `ruff check .`, `ruff format --check .` | sauber, 1043 Dateien, Exit 0 |
| `rev-sp-mypy-win`, `-linux`, `-darwin` | `23bd961d4` | `mypy`, `--platform linux`, `--platform darwin` | je 330 Dateien ohne Befund, Exit 0 |
| `rev-sp-merge` | Probe-Merge mit `6eacc1a63` | wie `rev-sp-1` plus `test_texture_ops` | 2528 bestanden, 7 übersprungen, 6 abgewählt, Exit 0 |
| `rev-sp-merge2` | Probe-Merge | `test_evaluation`, `test_edge_binding`, `test_matching_answers`, `test_revision`, `test_way_one`, `test_acceptance_p0`, `test_examples` | 343 bestanden, 2 abgewählt, Exit 0 |
| `rev-sp-merge-mypy`, `-ruff` | Probe-Merge | `mypy --platform linux`, `ruff check` der berührten Dateien | 333 Dateien ohne Befund, Exit 0 |
| `rev-sp-g1` … `rev-sp-fix2` | Proben | siehe Abschnitt 4 | wie dort |

Gelesen, nicht ausgeführt: der ganze Diff; die zwölf Schritte samt
Aufrufgraph; `evaluate._evaluate` von der Schlüsselbildung bis zum Ablegen;
`types.Profile`; `profiles.for_process`, `for_object`, `analysis_limits`;
die Verbraucher der Objekthashes; die Merker je Netz; die Wege von „Im Slicer
öffnen“ bis `set_print_settings` (für F2, ohne Lauf).

---

**Mergebar: ja.** F1 als eigener Commit gleich nach dem Merge
(`reports/review-speicher-waechter.patch`), F2 als Registereintrag.
