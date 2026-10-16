# Funde zur Codestruktur — was bei der Gelegenheit auffällt

Begleitdatei zu `konzept-codestruktur-2026-10.md` (Entscheidung Robert,
11.10.2026): Was beim Messen, Verschieben oder im Review auffällt, wird nicht
im Verschiebe-Commit geändert, sondern hier mit Beleg festgehalten und in
eigenen Commits behoben; was größer ist, wird ein Registerpunkt in
`ROADMAP.md` mit Verweis auf den Fund. Ein Fund ist erst erledigt, wenn sein
Commit oder sein Registerpunkt hier steht.

Festgehalten wird **alles** aus fünf Arten, nicht nur, was die Struktur
betrifft. Jeder Schritt sucht gezielt nach jeder Art (Konzept 4.2, Punkt 1):

| Art | Was dazu gehört | Wie gesucht | Wie behoben |
|---|---|---|---|
| **Leistung** | Laufzeit und Speicher: Schleifen je Element statt Feldrechnung, doppelte Berechnung, fehlender oder falsch geschlüsselter Merker, unnötige Kopien, Arbeit im Qt-Hauptfaden | beim Lesen des Zuschnitts; eingetragen wird nur mit Messung vorher | Messung nachher, druckgleich nach Bauplan §11.2, Plattformregeln aus `kern.md`; wird ohne Rückfrage umgesetzt |
| **Stabilität** | Abrisse, Hänger, Lebensdauer von Qt-Objekten und Fäden, Wettläufe, stummes Überspringen, was erst später oder auf einer anderen Plattform bricht | Aufrufgraph, Fäden und Signale des Zuschnitts, W6 | reproduzierender Test zuerst, dann der Fix |
| **Fehler** | falsches Verhalten in Anwendung, Werkzeugen oder Prüfungen — eine Prüfung, die nichts prüft, ist ein Fehler | beim Lesen, W2, W4, die Gegenproben | reproduzierender Test zuerst, dann der Fix |
| **Zwillinge** | dieselbe Auskunft an mehr als einer Stelle hergeleitet (`.claude/rules/zwillinge.md`) | `tools/twin_scan.py` über den Zuschnitt, dazu die Kopfkopien aus W2 | die Pflicht der Klasse aus `zwillinge.md`: zusammenführen oder die Abweichung entscheiden |
| **Aufräumen** | toter Code (aus dem Aufrufgraphen), veraltete Kommentare und Zahlen, lange Funktionen, unnötige Kopplung, private Namen über Modulgrenzen | Aufrufgraph und Attributgraph des Zuschnitts | eigener Commit; Verhalten unverändert, belegt durch die betroffenen Tests |

Stand der Belege: welle5 `f850ef25c`. Zeilennummern altern; maßgeblich ist die
genannte Definition.

**Unabhängig vom Programm** sind CS-2, CS-3, CS-6, CS-9, CS-10, CS-11, CS-12,
CS-13, CS-14, CS-15 und CS-16: Darunter sind Prüfungen, die heute immer grün
sind oder Teile des Baums nicht lesen, und drei Workarounds, hinter denen ein
Fehler oder ein möglicher Absturz beim Kunden steht. Sie werden mit der Abgabe dieses Konzepts Registerpunkte,
gleich ob das Programm kommt. Die übrigen folgen dem Programm.

## Wie behoben wird

**Einfach, an der Wurzel, kein Workaround** (Entscheidung Robert, Konzept
3.1 Regel 9). Jeder Fix nimmt die einfachste Lösung, die die Ursache
beseitigt. Kein Sonderfall, keine Ausnahmeliste, kein abgeschalteter Wächter,
keine unterdrückte Warnung, kein `try`/`except` um ein Symptom, keine Fixture
und kein Patch, die einen Fehler im Code verdecken. Jeder Fund nennt deshalb
seine **Ursache**, nicht nur die Stelle, an der er auffiel. Liegt die Ursache
außerhalb des Schritts, wird sie ein eigener Fund oder Registerpunkt. Ein
bestehender Workaround im Code oder in der Suite ist selbst ein Fund — der Art,
deren Ursache er verdeckt.

## Aufbau eines Funds

Je Fund: Nummer `CS-<n>`, Art (Leistung, Stabilität, Fehler, Zwillinge,
Aufräumen), Ort, Beleg (gemessen, mit Befehl oder Zahl), Ursache, Vorschlag,
Wirkung beim Kunden (falls eine), Stand (offen, Commit, RM-Nummer). Neue Funde kommen
unten an, je Schritt unter einer eigenen Überschrift; Nummern werden nicht
wiederverwendet. Findet ein Schritt in einer Art nichts, steht das dort als
Satz — „nichts gefunden“ ist ein Ergebnis, „nicht gesucht“ keines.

## Funde aus Messung und Prüfung des Konzepts

Gezielt gesucht wurde hier nach Fehlern, Stabilität und Aufräumen; Leistung und
Zwillinge nicht. Die Suche nach allen fünf Arten beginnt mit Schritt 1.

### CS-1 Funktionen über 300 Zeilen

**Art:** Aufräumen.

39 Funktionen und Methoden unter `app/` haben 300 Zeilen oder mehr. Die
längsten:

| Zeilen | Definition |
|---|---|
| 1 484 | `scene/evaluate.py` `_with_features` |
| 1 218 | `scene/evaluate.py` `_evaluate` |
| 1 020 | `ui/main_window.py` `MainWindow._build_central` |
| 916 | `ui/viewport.py` `Viewport.__init__` |
| 898 | `ui/main_window.py` `MainWindow._build_menus` |
| 829 | `ui/sketch_editor.py` `SketchPanel.__init__` |
| 706 | `ui/style.py` `stylesheet` |
| 688 | `ui/placement_flow.py` `PlacementFlow.redraw` |
| 633 | `slice/gcode.py` `analyze_lines` |
| 623 | `export/writer.py` `write_assembly` (Grenzdatei) |
| 581 | `ui/op_dialog.py` `__init__` |
| 555 | `slice/advise.py` `_from_geometry` |
| 550 | `ui/main_window.py` `MainWindow.run_operation` |
| 547 | `perceive/features.py` `_fitted` |
| 543 | `export/handover.py` `slice_model` (Grenzdatei) |

Vorschlag: nach dem Verschiebeschritt der jeweiligen Datei in benannte
Teilschritte zerlegen (Aufbau-Methoden in Abschnitte je Bereich, die beiden
`evaluate`-Funktionen in ihre Phasen). Bei `evaluate`, `analysis`, `gcode` und
`advise` liegt der Rechenweg darin: druckgleich belegen (Korpuslauf vorher und
nachher). Die zwei Grenzdateien nur zusammen mit 4.4 des Konzepts.
Stand: offen.

### CS-2 Quelltextprüfungen lesen `app/ui/` flach

**Art:** Fehler.

17 Stellen in sieben Testdateien lesen `app/ui/*.py` oder `perceive/*.py`
über `glob("*.py")`; die über `app/ui/` sehen damit `app/ui/render/`
(11 Dateien) schon heute nicht: `test_leash.py` 477, 950, 1101 (1147 ist
deren Gegenprobe, CS-12); `test_style.py` 510, 912, 917, 1200, 1370;
`test_ui.py` 15991, 16869; `test_value_labels.py` 756;
`test_widget_lifetime.py` 426, 584; `test_native_keys.py` 419. Dazu
`test_features.py` 2999 über `perceive/` und `test_translations.py` 1763 über
`agent/`. Fast alle sind Verbotsprüfungen (`assert not culprits`).

Vorschlag: je Stelle entscheiden, ob `render/` absichtlich fehlt; wenn ja,
nennt die Prüfung ihren Geltungsbereich samt Grund im Test, ein flaches `glob`
bleibt trotzdem verboten; sonst liest sie rekursiv. Danach gilt W4 des
Konzepts.
Wirkung beim Kunden: keine gefunden; im Abnahmelauf von Q ohne Fenster
(23 650 passed, die 92 Roten alle vorbestehend) meldete keine umgestellte
Prüfung einen Verstoß unter `render/`; ihre Fensterfälle fährt die CI nach
main. Stand: behoben in Paket Q (über welle5 `46308b77b`): alle 26 flachen
Leser — die 17 oben, `test_translations`, `activation`, der Bauordner des
Lizenzmoduls und `test_style.py`
`test_every_layout_of_a_dialog_keeps_the_grid` — lesen über
`tests/source_tree.python_files` rekursiv (`d6b9ee31c`); das Prüfmodul bleibt
flach, ein Modul im Unterordner hält den Bau an (`1d5c77c74`). W4
`tests/test_source_readers.py` verbietet flaches `glob` über ein Paket und
prüft jede umgestellte Prüfung an einem Verstoß im Unterpaket (`63d399303`;
Auflöser seit `1c1bd1313` in `tools/tree_reads.py`); am Stand davor 26 rot,
danach 0. W4 griff seither zweimal an neuen Stellen (`aad7c27f6`,
`8d2367bb6`). [RM-723](../ROADMAP-ARCHIV.md#rm-723).

### CS-3 Späte Importe in `tools/` prüft niemand

**Art:** Stabilität.

mypy prüft nur `app` (`pyproject.toml`, `files = ["app"]`). Späte Importe in
Erzeugern brechen deshalb erst beim Release in `/erzeugen`:
`tools/make_video.py` 2241 und `tools/make_workshop_videos.py` 1694 holen das
private `app.ui.panels._feature_item`; mindestens neun Werkzeuge holen
`MainWindow`, etwa `make_figures.py` 636, `make_guides.py` 1828,
`make_gallery.py` 212, `make_web_images.py` 710, `run_ui_audit.py` 494,
`window_memory.py` 107, `window_bench.py` 263, `make_video.py` ab 3373 und
`make_longform_video.py` 65 (Kopfimport).

Vorschlag: W5 des Konzepts (statische Importprüfung für `app/`, `tools/`,
`tests/`, auch in Funktionen) unabhängig vom Umbau einführen; `_feature_item`
öffentlich machen, wenn zwei Erzeuger es brauchen. Stand: behoben für die
Prüfung — W5 (`tests/test_import_resolution.py`, Paket R `51672538f`, scharf
seit `f65d9b925`) löst jeden späten Import und jeden Modulalias in `tools/`
statisch auf. `_feature_item` bleibt privat, `make_video.py` und
`make_workshop_videos.py` holen es weiter; öffentlich wird es im
Verschiebeschritt von `panels.py` (Regel 5, wie CS-7).
[RM-724](../ROADMAP-ARCHIV.md#rm-724).

### CS-4 Die Ladelast wird nur als Untergrenze gezählt

**Art:** Fehler.

`tools/docs_scan.py` `load_for` zählt die Wurzel, die eigene Karte und die
Regeln, nicht die Karten darüber. Codex liest nach `AGENTS.md`,
„Paketstruktur“, alle Karten vom Wurzelordner bis zum Verzeichnis. Für eine
Datei in `app/core/geom/` fehlt in der Zählung damit `app/core/CLAUDE.md`
(17 204 Byte).

Vorschlag: `load_for` zählt alle Karten auf dem Weg, und `LOAD_LIMIT_KB` wird
an der neuen Zählung neu begründet; sonst misst der Wächter weniger, als eine
Sitzung tatsächlich lädt. Stand: offen.

### CS-5 Karten und Regeln ohne Luft

**Art:** Aufräumen.

Fünf Karten haben weniger als 700 Byte bis zur Grenze von 25 600
(`scene` 1, `perceive` 33, `export` 98, `geom` 93, `ui` 603); die Regeln
`operationen.md` und `dateiformat.md` haben 6 Byte, `kern.md` 33, `tests.md`
28. Jede Ergänzung erzwingt dort heute eine Kürzung an anderer Stelle.

Vorschlag: mit den Verschiebeschritten entlasten (neue Karten, engere
`paths:`); bis dahin keine Ausnahme der Grenzen. Stand: offen, folgt dem
Programm.

### CS-6 `affected_tests` erkennt `glob(` nicht als Baumleser

**Art:** Fehler.

`tools/affected_tests.py`, `_TREE_READERS` kennt `rglob`, `walk_packages`,
`iterdir`, `iter_modules`, aber nicht `glob(`. Eine Testdatei, die den Baum
über `glob` liest, wird bei einer Änderung nur gewählt, wenn sie das Modul
auch importiert.

Vorschlag: `glob` aufnehmen; der Preis ist laut Kommentar höchstens ein Test
zu viel. Stand: behoben in Paket Q (über welle5 `46308b77b`): `glob` zählt als
Baumleser, auch über den lesenden Helfer (`3b327c94c`); seit `02532e1f1` wird
nach dem aufgelösten Lesebereich gewählt (`tools/tree_reads.py`).
[RM-725](../ROADMAP-ARCHIV.md#rm-725).

### CS-7 Private Namen über Modulgrenzen

**Art:** Aufräumen.

Rund 100 private Namen werden in `app/` über Modulgrenzen importiert, davon
31 aus `perceive/features.py` (allein `perceive/helix.py` holt 8),
6 aus `brep/kernel.py`, 6 aus `slice/analysis.py`, 5 aus `geom/faces.py`.

Vorschlag: im Verschiebeschritt der Quelldatei nach Regel 5 öffentlich machen
(eigener Commit); bis dahin nichts tun. Stand: folgt dem Programm.

### CS-8 Bauplan nennt einen Dateipfad

**Art:** Aufräumen.

Bauplan §11.3 nennt `app/core/slice/analysis.py` mit Endung; die Modullisten
der Phasen nennen sonst Modulnamen ohne Endung (`ui/viewport`,
`ui/sketch_editor`, `ui/panels`).

Vorschlag: mit Ansage auf den Modulnamen ohne Endung umstellen, spätestens im
Schritt, der `analysis.py` teilt. Stand: offen.

### CS-9 Zwei Patches sind heute wirkungslos

**Art:** Fehler.

- `tests/test_first_run.py` (um Zeile 552–560) ersetzt
  `filament_picker.configured_spools` und sichert `assert_not_called()` zu.
  Der einzige Aufrufer hält eine eigene Kopie
  (`app/ui/filament_inventory.py`, Kopfimport Zeile 62, Aufruf um 1174); der
  Patch erreicht ihn nie, die Zusicherung ist immer grün.
- `tests/test_spatial_matching.py` (Zeile 122) verbietet
  `matching._cost_matrix`. Diese Funktion (`perceive/matching.py`, Zeile 180)
  ruft niemand; sie steht nur als Zeichenkette in `_MATCH_WAYS` (Zeile 942).

Vorschlag: den ersten Patch auf das lesende Modul setzen und mit einer
Gegenprobe belegen, dass der Aufruf ohne Patch erreicht wird; `_cost_matrix`
entfernen oder wieder benutzen und `_MATCH_WAYS` nachziehen —
`tests/test_matching.py` (Zeile 22 und 180) ruft die Funktion direkt und zieht
mit. Danach W2.
Stand: behoben. a) Paket P1 (über welle5 `07f707f22`): Das Verbot steht auf
der Bindung, die das Lager liest (`filament_inventory.configured_spools`,
`3cb4f8d8e`); die Gegenprobe `tests/test_first_run_spools.py` sichert ohne
Patch genau einen Aufruf außerhalb des Oberflächenfadens zu (`3cb4f8d8e`,
`fbd0a5100`, `7723483b6`); der Bekanntfall in `test_code_index.py` hält, dass
das Verbot an der Bindung des Lesers steht (`e3320525d`, `f0fae781a`).
b) Paket P2 (über welle5 `1019bc88b`): `_cost_matrix` ist wieder der Eintritt
in den dichten Solverweg, `_assignment` liest sie über das Modul, ein Spion
belegt den Weg ohne Patch (`4c915e009`); 96 von 96 Zuordnungsfällen
bytegleich, davon 42 an sieben echten Modellen; `_MATCH_WAYS` nennt nur noch
Gelesenes (W6 d, `ff37fc086`). W2 d) ist seit `6948c76e3` scharf.
[RM-726](../ROADMAP-ARCHIV.md#rm-726).

### CS-10 Namenslisten überspringen Fehlendes stumm

**Art:** Stabilität.

- `scene/evaluate.py` `_step_ways` liest `sys.modules.get(name)` für jeden
  Eintrag aus `_STEP_WAY_MODULES` und überspringt ein fehlendes Modul ohne
  Meldung; der Merkschlüssel eines Schritts verlöre dann still Funktionen.
- `tests/conftest.py` `_pin_ui_widgets` holt `getattr(module, "MainWindow",
  None)` und überspringt `None`; ohne Pin droht der native Abriss, den der
  Docstring dort beschreibt.

Vorschlag: W6 des Konzepts sofort, unabhängig vom Umbau — jeder Name löst auf
und trägt etwas bei, sonst Fehler. Stand: behoben. `_step_ways` (Paket P2,
`ff37fc086`, über welle5 `1019bc88b`) importiert jeden Eintrag aus
`_STEP_WAY_MODULES` und verlangt eine eigene Funktion; ein fehlendes Modul
bricht mit `ModuleNotFoundError`, eines ohne eigene Funktion mit
`InternalError` ab (Wertschlüssel `8ee7855a5`), auch aus `evaluate()`; die
934 Wege sind elementweise dieselben, Kosten 43 → 58–62 µs je Auswertung.
Wächter W6 `tests/test_name_lists.py`. Der Pin (Paket P1, `01a6db635`,
`1ee80d596`, über welle5 `07f707f22`): `UI_PINS` ordnet Modul und Klasse zu,
`pin_ui_widgets` bricht bei fehlender Klasse den Import ab,
`pin_loaded_ui_modules` überspringt nur ungeladene Module; Wächter
`tests/test_suite_pin.py`. `_pin_ui_widgets` gibt es nicht mehr.
[RM-727](../ROADMAP-ARCHIV.md#rm-727).

### CS-11 Kopfkopien entziehen sich Patches

**Art:** Fehler.

In 54 Fällen hält ein Modul per `from M import N` eine eigene Kopie eines
Namens, den Tests an `M` patchen, etwa `features.detect` in
`scene/evaluate.py`. Ein Patch auf `M.N` erreicht die Kopie nicht.

Vorschlag: je Paar prüfen, ob ein Test die Wirkung in der Kopie erwartet;
wenn ja, dort über das Modul zugreifen (`features.detect`) oder den Patch
umsetzen. W2 macht neue Fälle rot. Gemessen im Plan zu Schritt 0: 226
Kopfkopien statt 54 (Abschnitt „Schritt 0“). Stand: in Paket K (erzeugter
Schnitt `move_names copies`), Stand folgt. [RM-728](../ROADMAP.md#rm-728).

### CS-12 Die Gegenprobe der Oberflächensuche zählt nur Dateien

**Art:** Fehler.

`tests/test_leash.py` `test_the_sweep_over_the_surface_finds_files_to_read`
verlangt 20 oder mehr Dateien unter `app/ui/`; ihr Kommentar nennt den Stand
52, heute sind es 86. Wird `main_window.py` ein Paket, bleibt die Zahl über 20
und die Prüfung grün, obwohl die größte Datei fehlt.

Gleiche Bauart: `test_features.py` 3005 verlangt nur zehn oder mehr Dateien
unter `perceive/`.

Vorschlag: W4 — beide Gegenproben verlangen die Definitionsmodule von
`MainWindow`, `Viewport` und der Merkmalserkennung; die veraltete Zahl im
Kommentar entfällt. Stand: behoben in Paket Q (über welle5 `46308b77b`): Die
Gegenproben verlangen statt einer Mindestzahl Definitionsdateien —
`test_leash` die von `MainWindow`, `Viewport`, `Renderer` und eine Datei im
Unterpaket, `test_features` die von `detect`, `test_style` die von
`make_primary` in der Grundmenge (`d6b9ee31c`); die dritte Stelle,
`test_print_disclosure.py` (`> 30`), verlangt die Datei mit
`is_utc_timestamp` (`890a12512`). Die Zahl bleibt nur Grundmengenbeleg. W4
hält es (`test_the_sweeps_follow_a_definition_into_a_package` schneidet
`main_window.py` und `features.py` zum Paket, `test_a_flat_sweep_is_red`,
`63d399303`). Die Zählprobe `< 50` gleicher Bauart in `tools/function_list.py`
ersetzte D0 durch die Prüfung auf die Definitionsmodule (`6f6abe84a`).
[RM-729](../ROADMAP-ARCHIV.md#rm-729).

### CS-13 `tools/matrix_unit.py` läuft in keiner Suite

**Art:** Stabilität.

Das Werkzeug greift über Modulaliasse zu (`handover.detect` und weitere, um
Zeile 370, 378, 785). Bräche ein Name, fiele es erst beim nächsten
Matrixlauf auf.

Vorschlag: W5 deckt die Zugriffe statisch; zusätzlich ein Rauchtest, der das
Modul importiert. Stand: behoben. „Läuft in keiner Suite“ stimmte schon am
Belegstand nicht: `tests/test_delivery_matrix_review.py` (`_load_module`) und
`tests/test_delivery_tools.py` laden `tools/matrix_unit.py` ohne Marker, also
im Tor. Die Aliaszugriffe in Funktionen, die diese Tests nicht rufen
(`handover.detect`, `handover.standard_choice`, `handover.slice_model`), löst
W5 statisch auf (`test_import_resolution.py`, scharf seit `f65d9b925`).
Gegenprobe (Paket U, Wegwerfbaum an `a25ac8cb2`): `handover.detect` in Zeile
370 umbenannt → `test_every_attribute_of_an_own_module_resolves` rot mit
`tools/matrix_unit.py:370`, 1 failed, 4 passed, EXIT=1; unverändert 5 passed,
EXIT=0. [RM-730](../ROADMAP-ARCHIV.md#rm-730).

### CS-14 `_BoundedBehavior` überspringt Überschreibungen seiner Träger

**Art:** Fehler.

Das einzige Mixin in `app/` (`app/ui/labels.py`, `_BoundedBehavior`) schreibt
`self: Any` und ruft acht Methoden fest verdrahtet als
`NumberSpin.<methode>(self, …)` (`stepBy`, `valueFromText`, `validate`,
`interpretText`, `keyPressEvent`, `focusOutEvent`, `hideEvent`, `showEvent`).
An `BoundedLengthSpin(_BoundedBehavior, LengthSpin)` überspringen diese
Aufrufe jede Überschreibung von `LengthSpin`; `showEvent` musste deshalb in
`BoundedLengthSpin` von Hand nachgebaut werden. Die nächste Überschreibung in
`LengthSpin` fiele still aus. `self: Any` verdeckt das — ein Workaround.

Ursache: Das Begrenzen ist als Mixin neben die Klassenlinie gelegt statt in
sie hinein. Ein Protokoll als Selbsttyp hilft nicht: mypy strict meldet an
jedem `NumberSpin.<m>(self, …)` `[arg-type]` (Probe). Vorschlag: eine
Klassenlinie — das Ablehnen gehört in `NumberSpin`, kooperativ über `super()`,
`LengthSpin` erbt es; ob es dort immer gilt oder erst nach gesetzten Grenzen
(`name_limits`), entscheidet der Fix mit Test. Danach entfällt der Nachbau von
`showEvent`. Stand: [RM-731](../ROADMAP.md#rm-731).

### CS-15 Fenster ohne geordneten Abbau reißen den Prozess

**Art:** Stabilität.

`tests/conftest.py` pinnt `MainWindow`, `Viewport` und elternlose Dialoge, die
eine `WorkerLeash` besitzen, bis zum Ende ihres Tests (`_PinOnImport` über
`UI_PINS` — bis Schritt 0 `_pin_ui_widgets` —,
`_windows_live_until_their_test_ends`). Der Mechanismus ist
dort benannt: Ein Fenster, das mit seiner letzten Referenz mitten im Lauf
stirbt, wird ohne geordnetes `release` abgebaut und reißt den Prozess mit
0xc0000374 (Heap-Beschädigung); der Produktcode hält Besitzer bewusst nicht
zyklisch, deshalb hält die Suite sie.

Offen ist die Produktseite: ob die Anwendung einen Abbau ohne `release`
ausschließt — beim Sprachwechsel, bei einem zweiten Fenster, bei einem
eigenständigen Viewport, bei elternlosen Dialogen mit Arbeitern. Vorschlag:
jeden dieser Wege an der Anwendung prüfen; wo einer ohne `release` abbaut,
ist es ein Absturz beim Kunden und wird an der Wurzel behoben (der Weg ruft
`release`), nicht durch einen Pin. Stand: [RM-732](../ROADMAP.md#rm-732).

### CS-16 `PlacementFlow` greift über `Any` und Zeichenketten aufs Fenster

**Art:** Fehler.

`PlacementFlow.__init__(dialog: PlacementHost, window: Any, …)`
(`app/ui/placement_flow.py`) typisiert das Fenster nicht und spricht es über
`getattr(self.window, "<name>", None)` an: `slot_drag_takes_the_accept`,
`announce`, `_apply_placed_feature`, `overlay` (zweimal), dazu dreimal
`self.window._clear_preview()`. Wird eine dieser Methoden umbenannt oder zieht
sie in eine Komponente, liefert `getattr` still `None` — dann übernimmt etwa
ein wartender Langlochzug nicht mehr, und weder mypy noch ein Test sieht es.
Die Dialogseite (`PlacementHost`) ist dagegen sauber erhoben.

Ursache: Die Fensterseite wurde nie als Vertrag erklärt. Vorschlag: wie bei
`DrawFlow` das Fenster unter `TYPE_CHECKING` als `MainWindow` typisieren oder
ein zweites, erhobenes Protokoll für genau diese Member; die `getattr`-Zugriffe
werden gewöhnliche Aufrufe. Vor Schritt 4 des Konzepts, weil `PlacementFlow`
dort Vorbild ist. Stand: [RM-733](../ROADMAP.md#rm-733).

## Schritt 0

Stand der Belege: welle5 `a25ac8cb2`. Gesucht haben die Pakete R, W13, P1,
P2, Plattform, M, Q, R2, das Restpaket CS0 und — für CS-35, CS-36, CS-39,
CS-40 — die Restpakete A und C und der CI-Fix, je in allen fünf Arten.
CS-41 bis CS-44 meldeten die Pakete U und K nach dem Einfrieren; sie bleiben
offen bis nach 0.6.1 ([RM-813](../ROADMAP.md#rm-813)).

**Leistung.** CS-23 (der Auflöser kostete jeden Arbeiter 33,5 s und 1,9 GB,
jetzt 0,97 s und 125 MB). Im eigenen Gebiet ohne Nummer behoben: Die Auswahl
von `affected_tests` las und parste Dateien mehrfach (Review 2 von Q, F-6);
`93f5808f8` liest jede einmal, Auswahl an zehn Auslösern bitgleich, als Skript
35 bis 50 % weniger CPU.

**Stabilität.** CS-25 (Sammlung im Prozess hinterließ Haken und
Profilvariablen), CS-29 (Fakes nach einem Komponentenschnitt, offen für 4d),
CS-35 (Zeitgrenze beendete nur den Starter der bash), CS-39 (OrcaSlicer unter
Last), CS-40 (Schriftfälle hingen an der Reihenfolge). Ohne Nummer behoben:
`tests.conftest` war ein zweites Exemplar der conftest — zweiter Import-Haken,
zweiter Temp-Ordner, Profilvariablen mitten im Lauf umgebogen (P1,
`01a6db635`); neu gesammelte Testmodule blieben in `sys.modules` (Q,
`f75499898`, erweitert in `93f5808f8`).

**Fehler.** CS-18, CS-20, CS-21, CS-24, CS-27, CS-28, CS-31, CS-32, CS-34,
CS-36, CS-37, CS-38; offen nach 0.6.1 CS-42. Aus dem Plan (`plan-cs0.md` §1,
§5):

- Zwei reine Quelltextprüfungen forderten `qt_app` an
  (`test_no_worker_is_started_past_the_leash`,
  `test_every_default_button_of_the_surface_goes_through_make_primary`) und
  liefen deshalb nur im Fensterlauf, nie im Tor (§1.1). Behoben in
  `9af771975`; der Markerausdruck des Tors sammelt und fährt beide.
- `raising=False` auf `app.*`: nicht 25 wie in RM-722, sondern 12 (§1.6, E2),
  am Code 13 mit CS-24. Gestrichen: neun in P1 (`088585c88`, `d00b38ad1`),
  drei in Q (`352c73029`), eine mit CS-24 (`5bc1c2c01`); die 13 auf `sys`,
  `ctypes`, `subprocess` und `HTTPError` bleiben (E2). W2 b) ist seit
  `77653a311` scharf.
- `affected_tests` war nicht transitiv (E5): Ein Test, der über einen Helfer
  wie `tools/code_facts.py` liest, wurde bei einer Änderung unter `app/` nicht
  gewählt. Behoben in Q (`3b327c94c`, seit `02532e1f1` nach aufgelöstem
  Lesebereich).
- Umfang von CS-11 (§1.4): 226 Kopfkopien (182 in `app/`, 44 in `tools/`) zu
  78 Namen statt 54; R zählte am Code 302 (254 und 48) zu 89 Originalen in 149
  Haltern, das Inventar von R2 309 (W2 c), `617cac547`); K schlägt 89 Familien
  vor. Behoben wird es in K (CS-11).

Ohne Nummer behoben: Das Verbot auf `sign_release.run` erreichte keinen
Aufruf (R, `6948c76e3`, W2 d) seitdem scharf); der Wächter gegen die echte
Programmsuche übersah sie unter einem örtlichen Alias (P1, `d00b38ad1`);
W2 e) urteilte über eine halb gebaute Tabelle der Aufrufstellen
(`code_index._call_sites`), und das Verbot auf `mesh.fetch` in
`test_function_seams.py` erreichte kein Backend, weil der Dataclass `fetch`
beim Klassenbau bindet (beide `08e6aff1c`).

**Zwillinge.** CS-22, CS-30, CS-33 (die bash und die sh der Suite kamen aus
vier Suchen, jetzt aus `tests/shell_helpers.py`). Im Fix mitbehoben: CS-27
(M suchte `hasattr` selbst neben dem Auflöser), CS-35 (`start_bounded` statt
zweier gleichlautender Startwege in `run_limited`/`run_stream_limited`), CS-36
(`ISOLATED_KEYRING` eine Quelle statt eigener Fassung in `native_binding`).
Ohne Nummer behoben: Bau und Test des Lizenzmoduls rechneten die Modulnamen
getrennt (`extension_modules()`, `1d5c77c74`); beide Speicher des Auflösers
ersetzten ihre Datei je selbst (`4fe5be8c1`). In P2 gesucht und nichts
gefunden; die alte `_cost_matrix` war ein toter zweiter Rechenweg, jetzt gibt
es einen (CS-9).

**Aufräumen.** CS-17, CS-19, CS-26; offen nach 0.6.1 CS-41, CS-43, CS-44.
Aus dem Plan:

- Ort des Helfers gegen W1 (E4): Der rekursive Leser steht in
  `tests/source_tree.py`, nicht in `tests/helpers.py`, das in W1 steht (heute
  126 Definitionen) und rund 200 Importeure hat (`d6b9ee31c`). Konzept 4.1
  (W4) ist nachgezogen.
- D0-Kennungen mit Modulstamm (E10, §1.7): `RAW_WINDOW_PACKAGES` hatte 26
  Schlüssel `<stamm>.<funktion>`; ein geteiltes UI-Modul hätte die Urteile
  verwaisen lassen. In D0 behoben (`c163ec199`): Kennungen heißen
  `meldung:<funktion>`, W6 h) prüft den Anschluss ohne Stamm.
- Zählprobe `< 50` in `tools/function_list.py` (Bauart CS-12, §1.7): in D0
  ersetzt durch die Definitionsmodule von `MainWindow`, `Viewport`,
  `SettingsDialog` bzw. `Action`, `History`, `Registry` (`6f6abe84a`).
- D0-Dateien knapp an der Grenze (§1.7), heute: `app/ui/guide_targets.py`
  1 996 Zeilen, `tests/test_function_report.py` 1 972,
  `tests/test_guide_targets.py` 1 969, `tools/file_acceptance.py` 1 966,
  `tools/function_bench.py` 1 929, `tools/function_list.py` 1 881. Die im Plan
  als geteilt angenommenen `function_list`, `function_bench` und
  `test_function_bench` hat D0 selbst unter die Grenze gebracht. W1 macht jedes
  Wachstum über 2 000 rot; neue Definitionen gehen dann in eine neue Datei
  (Regel 6).

Ohne Nummer, offen für Schritt 1 und 4d (Paket M, Neue Punkte 8, 9, 12, 13; [RM-813](../ROADMAP.md#rm-813)):
`importlib.reload` und `dir()` auf `slicer_keys`/`advise` und 32 Aufruftexte in
`tools/` brauchen beim Schnitt ihrer Datei einen Handfix oder `[[name_lists]]`;
Methoden mit `self.sender()` (sechs in `main_window.py`, elf lesende und sechs
erreichende im `PrintSettingsDialog`) wandern erst mit dem Sender als Argument;
75 `getattr`, 3 `hasattr` und 12 Namensraumlesungen über offene Namen sowie
`self.__dict__` in `main_window.py` verlangen vor einem Komponentenschnitt
eine Annotation oder Erklärung. Im Gebiet von W13 in Fehler, Stabilität,
Leistung und Zwillingen nichts weiter gefunden.

### CS-17 Die Registrierungsfolge hat keinen öffentlichen Leser

**Art:** Aufräumen.

Konzept 3.1, Regel 3 macht die Reihenfolge der Register zum Vertrag, aber
`Registry.all()` und `PartRegistry.all()` sortieren nach Namen; W3
(`tools/registry_dump.py`) las deshalb die privaten `Registry._ops` und
`PartRegistry._parts`. Ursache: Die Folge war nur intern gehalten, nie als
Schnittstelle erklärt. Gebaut: `in_registration_order()` an beiden Registern,
`registered()` liest sie, die privaten Zugriffe sind fort. Tests zuerst
(vorher 2 rot, `AttributeError`), Gegenprobe mit beiden Methoden auf `all`
rot, W3-Abzug bytegleich. Keine Wirkung beim Kunden. Stand: behoben in
`791aa2e6c` (Paket W13, über welle5 `fb532ab67`).

### CS-18 Der Auflöser liest keine Skripte in Zeichenketten

**Art:** Fehler.

`tools/code_index.py` (Paket R) las nur Code, nicht den Text, den Tests an
`python -c` geben. Beleg: `parts.PartRegistry` stand für den Index ohne Bezug;
erst die Streichung des Lazy-Exports machte den Subprozess in
`tests/test_core_isolation.py:384` rot (P2, RP2-5); im Baum stehen 571 als
Python lesbare Zeichenketten, die `app.` nennen. W2 und W5 waren dort blind,
ein umbenannter Name bräche erst im Kindprozess. Gebaut: `tools/code_scripts.py`
liest jedes Skript hinter `-c` mit Python-Kopf als Modul `__main__`; Bezüge
zählen als `script:<art>`, ein fehlender Name ist ein W5-Fund
(`test_every_reference_in_a_script_for_python_c_resolves`). Am festen Baum
`ceb161a9f`: 100 Skriptstellen, 230 Skriptbezüge, 0 Funde, 8 Stellen nicht
faltbar (vier sind keine Skripte, vier kommen aus einem Helfer in
`test_process.py`). Gegenprobe `test_code_scripts.py` am Stand davor 6 von 7
rot; der Eigen-Scan in `test_name_lists.py` entfiel (`7af6eaf93`). Keine
Wirkung beim Kunden. Stand: behoben in `696ba3132` (Paket R2, über welle5
`55a03913a`).

### CS-19 33 Lazy-Exporte bezieht niemand über ihr Paket

**Art:** Aufräumen.

`_EXPORTS` und `__all__` in sechs Kernpaketen (`activation`, `agent`, `brep`,
`knowledge.parts`, `registry`, `scene`). Beleg: W6 e) mit „trägt bei =
bezogen“ am Stand davor 6 rot; Einzelprüfung über Index, Textsuche und
Subprozess-Skripte: 31 ohne Bezug, 2 belegt (`activation.Licence`,
`knowledge.parts.PartRegistry`, beide aus Skripten in `test_core_isolation.py`).
Ursache: Exporte wurden angelegt, ohne dass jemand sie über das Paket bezog,
und nichts prüfte das. Gebaut: 31 gestrichen, die Definitionen bleiben in den
Untermodulen; `agent` ist ein reines Docstring-`__init__`; W6 e) in
`tests/test_name_lists.py` verlangt einen Bezug. Entscheidung Koordinator: Der
Paketimport von `register_part`, `PartChange`, `PartSpec` ist keine Zusage für
eigene Bausteine (kein Kundentext nennt ihn, Bauplan §24 nennt keinen
Importweg). Wirkung beim Kunden: keine. Stand: behoben in `e7debe995`
(Paket P2, über welle5 `1019bc88b`).

### CS-20 Eine reine Teständerung wählt die Baumleser nicht

**Art:** Fehler.

`tools/affected_tests.py` wählte Baumleser nur bei einer Änderung unter
`app/` oder `tools/` (`if touches_code:`). Beleg (Paket Plattform): eine neue
Testdatei und ein neuer Helfer unter `tests/` wählten nur die zwei
Pakettestdateien, nicht `test_toolchain.py` (private Querimporte),
`test_size_ratchet.py` (W1 zählt `tests/`) und `test_directory_docs.py`.
Ursache: Die Regel kannte `tests/` nicht als gelesenen Baum. Gebaut: zuerst
wählte jede Python-Änderung alle Baumleser (`f10546ae4`, 152 Testdateien für
`test_wording.py`, in der CI 47 Fensterprozesse); nach Review 1 (RQ-1) nur die
Leser, deren aufgelöster Bereich `tests/` einschließt (`02532e1f1`); am Ende 39
Testdateien und 2 Fensterprozesse (F-11, F-12, `93f5808f8`). Keine Wirkung
beim Kunden. Stand: behoben in `f10546ae4` und `02532e1f1` (Paket Q, über
welle5 `46308b77b`).

### CS-21 Der Ordnerweg überspringt Module unter `tests.`

**Art:** Fehler.

Der Ordnerweg von `tools/affected_tests.py` zählte nur Module unter `app/`
und `tools/`. Beleg (Review Plattform, RPL-1):
`tests/test_packaging_platform.py` liest `WORKFLOW.parent.glob("*.yml")`, wurde
aber für `fenster-auswahl.yml`, `mac-netz.yml` und
`windows-signed-installer.yml` nicht gewählt (11 von 14 Auslösern); an der
Basis nur zufällig über `tools.ci_selection`. Den Ordner nennt
`tests/packaging_helpers.py`, und den übersprang der Weg. Ursache: Lesende
Helfer unter `tests/` waren nicht vorgesehen. Gebaut: Testdateien und Helfer
unter `tests/`, die den Ordner nennen, zählen (`f8ea19c40`), über den
aufgelösten Pfad (`5200d551d`), seit `93f5808f8` je lesender Einheit
(`tools/data_reads.py`). Keine Wirkung beim Kunden. Stand: behoben in
`f8ea19c40` (Paket Q, über welle5 `46308b77b`).

### CS-22 Die Suite sucht ihre bash an zwei Stellen verschieden

**Art:** Zwillinge.

`tests/packaging_helpers.workflow_shell` und `tests/helpers.bash_executable`
beantworteten dieselbe Frage verschieden. Beleg (RPL-4): `workflow_shell` nahm
einen WSL-Starter aus `System32`, Gegenprobe `wsl` 81 von 88 Workflowfällen
rot, `bash_executable` verwarf ihn; `workflow_shell` suchte nur unter
`PROGRAMFILES`, nicht neben `git` und nicht in der Installation je Nutzer.
Ursache: zwei Quellen für eine Auskunft. Gebaut: `tests/shell_helpers.py` mit
`bash_executable(*, keep_path=False)` als einzige Quelle — eigenes Modul,
weil ein Finder in `packaging_helpers.py` über `helpers.py` bei einer Änderung
an `tools/make_linux_packages.py` 258 statt 88 Testdateien gewählt hätte;
`workflow_shell` ruft `bash_executable(keep_path=True)`. Test
`test_a_wsl_starter_ahead_of_git_in_the_search_path_never_runs_the_ci_blocks`
vorher rot. Keine Wirkung beim Kunden. Stand: behoben in `e763e85a1` (Paket
Plattform, über welle5 `0d4cc43db`); dritte und vierte Suche CS-30, CS-33.

### CS-23 Der Auflöser kostet jeden Arbeiter 33 s und 1,9 GB

**Art:** Leistung.

`tools/code_index.shared()` (Paket R) baute in jedem Prozess den ganzen
Auszug. Beleg: `test_value_labels` lief nach `test_import_resolution` im
selben Prozess nach 20 min erst bei 29 % (P2); der Index hielt 9,58 Mio.
verfolgte Objekte, ein volles `gc.collect()` kostete 1,91–2,05 s, und
`tests/conftest.py` ruft es je Test zweimal, sobald eine `QApplication` lebt
(nachgestellt 4,39 s je Test, rund 23 min für die Datei); im Tor bauten vier
von acht Arbeitern je einen Index, je rund 2 GB mehr, Spitze 6,9 GB (Review 2
von P2). Ursache: kein gemeinsames Ergebnis je Baumstand. Gebaut:
`tools/code_store.py` — ein Bau je Baumstand unter Betriebssystemsperre, ein
Datensatz je Datei, die übrigen Prozesse lesen das Ergebnis, Auszüge erst auf
Frage. Am festen Baum `ceb161a9f`: warm 33,5 s und 1 905 MB → 0,97 s und
125 MB je Arbeiter, Abzug in sieben Läufen gleich. Das zunächst gesetzte
`gc.freeze` fiel nach Review 1 (`edb1b132b`): Der Index ist klein geworden, ein
volles `gc.collect()` kostet ohne es 51–63 ms. Keine Wirkung beim Kunden.
Stand: behoben in `011196166` (Paket R2, über welle5 `55a03913a`); Stempel des
geladenen Codes `595cfebde`.

### CS-24 `raising=False` auf `registry._KERNEL_INSTALLED`

**Art:** Fehler.

`tests/test_kernel_switch.py:531`, seit `ca9f933a7` (D0, 13.10.), nach der
Zählung des Plans entstanden. Beleg: W2 b) meldete die Stelle (P1); der Name
steht auf Modulebene (`app/core/registry/registry.py:186`), ein Patch mit
`raising=False` bliebe bei einem umbenannten Namen still grün. Ursache: ein
Patch, der einen fehlenden Namen anlegt statt abzubrechen; keinem Paket
zugeordnet. Gebaut: `raising=False` gestrichen, W2 b) 4 → 3, mit Q scharf
(`77653a311`). Keine Wirkung beim Kunden. Stand: behoben in `5bc1c2c01`
(Paket P1, über welle5 `07f707f22`).

### CS-25 Eine Sammlung im Prozess hinterlässt Import-Haken und Profilvariablen

**Art:** Stabilität.

`tools/list_windowed_tests._collect` stellte `sys.modules` und `sys.path`
zurück, nicht `sys.meta_path` und `os.environ`; pytest führt dabei
`tests/conftest.py` ein zweites Mal aus. Beleg (P1): nach
`test_slicer_selection.py::test_markdown_the_application_reads_is_named_where_the_selection_looks`
zwei `_PinOnImport`-Haken und `APPDATA` auf einem neuen Ordner; der erste
Identitätsfall von `test_suite_pin.py` war deshalb rot. Ursache: unvollständige
Rückstellung. Gebaut: `_collect` stellt Haken und Umgebung zurück; Fall
`test_ci_runner.py::test_a_collection_in_the_process_leaves_import_hooks_and_environment_as_they_were`
vorher rot. Gleiche Bauart danach in Q: gesammelte Testmodule blieben in
`sys.modules` (`f75499898`, `93f5808f8`). Keine Wirkung beim Kunden. Stand:
behoben in `7d5cd8cc3` (Paket P1, über welle5 `07f707f22`).

### CS-26 Was K vor dem erzeugten Schnitt von Hand umschreibt

**Art:** Aufräumen; Fehler bei den umbenannten Kopien.

Trockenprobe `move_names copies` am echten Baum (Paket M, 88 Familien). Übrig
für Handarbeit: 23 Stellen in neun Dateien (gefaltete Patch-Stellen über
mehrere Halter, ein Modul als Parameter einer Fixture, ein Modul in einem mit
`None` vorbelegten Global, ein Patch auf eine Kopie in einem über den Pfad
geladenen Modul), vier Kopien unter neuem Namen (`MAX_ANSWER_BYTES: Final =
MAX_FILE_BYTES` u. a.; sie folgen einem Patch auf das Original schon heute
nicht) und zwei f-String-Zeilen, die durch `branding.APP_VERSION` zu lang
würden (`tools/check_frozen_start.py:220`, `tools/make_download.py:1167`).
Ursache: Formen, die das Werkzeug nicht sicher umschreibt; es weist sie mit
Ausweg ab. Vorschlag: vor dem Schnitt von Hand; bei den umbenannten Kopien
entscheiden, ob der Leser das Original liest oder eine eigene Zahl führt.
Keine Wirkung beim Kunden. Stand: in Paket K, Stand folgt.

### CS-27 Der Auflöser zählt `hasattr(M, "N")` nicht als Bezug

**Art:** Fehler.

`tools/code_index.py` übersprang `hasattr` (`if ref.kind == "hasattr":
continue`). Beleg (Paket M): Nach einem Schnitt antwortete ein solches
`hasattr` still `False`; M suchte die Form deshalb selbst
(`test_move_names_forms.py`, Fall `hasattr-auf-kopie`) — ein Zwilling des
Auflösers. Ursache: `hasattr` galt als Frage nach Abwesenheit, nicht als
Bezug. Gebaut: `hasattr(M, "N")` ist Bezug und Leser, sobald `N` existiert,
auch unter anderem Namen in derselben Datei (`has = hasattr`,
`builtins.hasattr`); ein überdecktes `hasattr` zählt nicht (`6290ed30f`).
Gegenprobe `tests/test_code_queries.py` am Stand davor 2 rot; Inventar am
festen Baum gleich. M stellt `getattr` und `hasattr` seitdem über genau einen
Weg um (`4e45b12da`). Keine Wirkung beim Kunden. Stand: behoben in
`454a20ce2` (Paket R2, über welle5 `55a03913a`); Alias aus einem anderen
Modul: CS-34.

### CS-28 Ein Original hinter gleichnamigem trägem Export ist als Pfad nicht patchbar

**Art:** Fehler.

Der träge Export `evaluate` des Pakets `app.core.scene` verdeckt das Modul
`app/core/scene/evaluate.py`. Beleg (Paket M): `"app.core.scene.evaluate.evaluate"`
endet zur Laufzeit bei der Funktion, nicht beim Modul, weil pytest und `mock`
über `getattr` gehen; die erste copies-Trockenprobe hielt an vier Haltern an,
die `evaluate` direkt aus dem Modul importieren. Ursache: Modul und
exportierte Funktion tragen denselben Namen. Gebaut im Werkzeug: Der
Leseweg führt über das träge Paket, ein Patch mit Modulausdruck zielt über
`importlib.import_module`, ein Pfad als Text wird mit diesem Ausweg
abgewiesen (`test_a_hidden_original_is_read_through_its_lazy_package`, Fall
`verdecktes-original-als-text`). Keine Wirkung beim Kunden. Stand: im
Werkzeug abgefangen in `d03b4bac1` (Paket M, über welle5 `c27074291`); die
Namensgleichheit selbst bleibt offen, [RM-813](../ROADMAP.md#rm-813).

### CS-29 Nach einem Komponentenschnitt bekommt ein Fake auf dem Wirt die Komponente

**Art:** Stabilität.

Komponentenmodus von `tools/move_names.py`. Beleg (Paket M):
`monkeypatch.setattr(Wirt, "m", fake)` wird
`monkeypatch.setattr(Komponente, "m", fake)`; ein `fake`, das sein erstes
Argument als Fenster benutzt, bekommt danach die Komponente. Der Beweis bleibt
grün, weil der Klassenbezug erklärt ist. Ursache: Das Werkzeug schreibt das
Ziel des Patches um, nicht die Annahme des Fakes über sein erstes Argument.
Vorschlag: solche Tests je Komponentenschnitt als Handfix nach dem Schnitt
(Plan 3.6 Punkt 3). Keine Wirkung beim Kunden. Stand: offen, gehört zu
Schritt 4d, [RM-813](../ROADMAP.md#rm-813).

### CS-30 `test_suite_script.py` sucht die bash ein drittes Mal

**Art:** Zwillinge.

`tests/test_suite_script.py:32` setzte `BASH = shutil.which("bash")`, ohne
Rückfall und ohne WSL-Prüfung. Beleg: Unter dem `PATH` einer PowerShell (Git
nur mit `cmd`) liefen an welle5 53 Fälle grün und 28 wurden übersprungen,
obwohl `bash_executable()` im selben Lauf `Git\bin\bash.exe` fand. Ursache:
dritte Quelle für die Auskunft aus CS-22. Gebaut: `BASH` kommt aus
`tests/shell_helpers.bash_executable`; der Wächter
`test_only_the_shell_helpers_look_for_bash` war am Stand davor rot. Danach 82 von 82
grün unter beiden `PATH`. Keine Wirkung beim Kunden. Stand: behoben in
`7c8349857` (Patch aus Restpaket B im Restpaket CS0, über welle5
`4d4a46307`); Folge: CS-35.

### CS-31 `affected_tests` sieht Op-Module ohne Importkante nicht

**Art:** Fehler.

Fünf Module unter `app/` hatten im Importgraphen keine Testdatei dahinter:
`geom.chamber_ops`, `geom.closure_ops`, `geom.counter_form_ops`, `scene.ops`
(nur als Text in `bootstrap._OPERATION_MODULES`) und `knowledge.parts.panels`
(über `parts/builtin.py`). Beleg (Paket Q): Eine Änderung an `chamber_ops.py`
wählte `test_chamber_ops.py`, `test_closure_ops.py` und `test_counter_form.py`
nicht. Ursache: Ops werden über das Register gerufen, nicht importiert;
Modulnamen als Kante wären die Suite gewesen (474 von 525). Gebaut
(Entscheidung Koordinator): Op- und Bausteinnamen aus
`register_op(name=…)`/`register_part(name=…)` als Kante zu den Testdateien, die
sie als Zeichenkette nennen (`7add837f6`; ohne Argumentnamen von
`parametrize`, `f4030a9a4`), dazu Prüfungen über das ganze Register und die
Beispielprojekte (`f04dbe8b3`) sowie angelegte Schritte, Projektdateien und
`insert_<baustein>` (`25afedde1`). Gegen die Ausführung gemessen
(`sys.monitoring`, 990 Paare aus Testdatei und Op-Modul): vorher 142
verfehlt, danach 0. Keine Wirkung beim Kunden. Stand: behoben in `7add837f6`
bis `25afedde1` (Paket Q, über welle5 `46308b77b`).

### CS-32 Anwendungsmodule, die den eigenen Baum lesen, geben das nicht weiter

**Art:** Fehler.

`app/i18n/extract.py` liest `PACKAGE_DIR.rglob("*.py")` für die
`tr()`-Schlüssel, `app/core/manual.py` geht mit `walk_packages` über
`app.core`. Beleg (Paket Q): `test_registry_dump.py` hängt über
`tools/registry_dump.py` an `extract.py` und wurde bei einem neuen `tr()` unter
`app/ui` nicht gewählt. Dieselbe Regel pauschal auf `app/` wäre die Suite
gewesen (386 Dateien mehr), weil `paths.py` und `knowledge/parts/user.py`
`*.py` im Nutzerordner suchen. Ursache: Leserweitergabe galt nur unter
`tests/` und `tools/`. Gebaut: Lesestellen unter `app/` zählen nur mit einem
Ordner im Repository und gehen nur an Module unter `tools/` und `tests/`
weiter (`db7329424`); eine Quelle, die über ihren Pfad gelesen wird
(`extract.EXTRA_SOURCES`), wählt ihre Leser (`93f5808f8`). Keine Wirkung beim
Kunden. Stand: behoben in `db7329424` (Paket Q, über welle5 `46308b77b`).

### CS-33 `test_packaging.py` sucht `sh` mit eigenem Rückfall

**Art:** Zwillinge.

`tests/test_packaging.py` `_posix_shell` suchte `sh` im Suchpfad, sonst nur
unter `PROGRAMFILES\Git\usr\bin`, nicht neben dem Git aus dem Suchpfad und
nicht in der Installation je Nutzer. Beleg (Restpaket CS0): der neue Fall
gegen den alten Finder 2 von 2 rot; der erweiterte Wächter am Stand davor rot mit
`test_packaging.py` und `test_suite_script.py`. Ursache: vierte eigene
Shell-Suche, Bauart CS-30. Gebaut: `posix_shell()` neben `bash_executable()` in
`tests/shell_helpers.py`, beide über einen Finder; `_posix_shell` entfernt;
der Wächter heißt `test_only_the_shell_helpers_look_for_bash_or_sh` und liest
Aufrufe über `ast`, seit `4a2e16bbf` und `17b055fca` über den Auflöser in
jeder Schreibweise; Sperrklinke `test_packaging.py` 202 → 201. Keine Wirkung
beim Kunden. Stand: behoben in `c61745352` (Restpaket CS0, über welle5
`4d4a46307`).

### CS-34 Ein Alias von `getattr` oder `hasattr` aus einem anderen Modul bliebe unsichtbar

**Art:** Fehler.

`tools/code_index.py` faltet `has = hasattr` nur in der eigenen Datei; zieht
ein anderes Modul den Alias per Import, entginge der Bezug. Beleg (R2, zu
CS-27): im Baum heute 0 solche Aliasse; sie aufzulösen hieße 17 852 Aufrufe
importierter Funktionen als Kandidaten zu führen. Ursache: Faltung je Datei.
Gebaut (Entscheidung Koordinator): ein Wächter statt einer Auflösung —
`Index.query_aliases()` nennt jeden Alias auf Modulebene, den ein anderes
Modul bezieht; `test_no_module_draws_an_alias_of_getattr_or_hasattr_from_another_one`
am echten Baum 0, Gegenprobe an einer Attrappe. Nach Review 1 geht der Wächter
auch über den Ergebnisspeicher (Mutation M2 vorher 144 passed, danach 4 rot).
Keine Wirkung beim Kunden. Stand: behoben in `617cac547` und `d428b995f`
(Paket R2, über welle5 `55a03913a`).

### CS-35 Eine Zeitgrenze der Suite beendet nur den Starter der bash

**Art:** Stabilität.

`tests/test_suite_script.py` `run_while_moving` beendete mit `child.kill()`
nur `Git\bin\bash.exe`; `usr\bin\bash.exe` darunter lief weiter. Dieselbe Lücke
hatten sieben `subprocess.run(…, timeout=…)` über die bash aus Git
(`test_tool_review_regressions.py` 5, `test_supply_chain.py` 1,
`test_delivery_tools.py` 1). Beleg: vier verwaiste Schreibschleifen seit
15.10., je 200–250 MB in `%TEMP%\pytest-of-rober`; jeder Lauf von
`test_a_run_that_neither_calls_nor_writes_is_stopped_as_hanging` hinterließ
eine; mit `capture_output` kam `subprocess.run` bei 1 s Grenze erst nach
1 200 Runden zurück. Ursache: Abbruch nur des direkten Kindes; seit CS-30
kommt die bash über den Starter. Gebaut: `app.core.process.start_bounded`
(angehalten starten, an ein Jobobjekt binden, fortsetzen) als eine Quelle,
auch für `run_limited` und `run_stream_limited`; `terminate_process_tree`
schließt das Jobobjekt; die sieben Aufrufe gehen über
`tests/process_helpers.run_bounded`. Test am Stand davor mit dem Starter rot
(„aufrufe.txt wächst nach dem Abbruch weiter: 12 → 50 Byte“). Keine Wirkung
beim Kunden. Stand: behoben in `27c56448c` (Restpaket C, über welle5
`b8f8296a1`).

### CS-36 Werkzeuge mit isoliertem Profil nehmen den Schlüsselbund des Nutzers mit

**Art:** Fehler.

Neun Funktionen unter `tools/` bogen die Nutzerordner um, ohne
`PYTHON_KEYRING_BACKEND` (`check_frozen_start.environment_for`,
`check_part_ranges._isolate`, `check_print_equal._isolated`,
`make_feature_images.main`, `make_guides._take`, `make_web_images.take_screens`,
`make_workshop_videos.main`, `native_runs.isolate_supervisor`,
`registry_dump._own_profile`). Beleg (Restpaket C): Der Chatdialog in den
Website-Bildern zeigte, ob im Tresor des Erzeugerrechners ein Schlüssel liegt;
der Wächter am Stand davor 5 von 6 rot. Ursache: `PROFILE_VARIABLES` ohne
Schlüsselbund, eine eigene Fassung in `native_binding`. Gebaut:
`app.core.paths.ISOLATED_KEYRING` neben `PROFILE_VARIABLES` als eine Quelle,
jede Stelle setzt sie mit; Wächter `tests/test_keyring_isolation.py` (mindestens
12 Fundstellen, je Bauart eine Gegenprobe, ein Kindprozess fragt die
Attrappe). Keine Wirkung im Produkt; erzeugte Bilder hingen vom Erzeugerrechner
ab. Stand: behoben in `159da97c9` (Restpaket C, über welle5 `b8f8296a1`);
W5 sieht den Wächter seit `08e6aff1c`.

### CS-37 Die Wurzel-`conftest.py` fehlt in `_EVERYTHING`

**Art:** Fehler.

Die Wurzel-`conftest.py` lädt für jede Sitzung `load_operations()`. Beleg
(Review 2 von Q, N-1): `affected([conftest.py])` wählte 34 von 543
Testdateien, nur Leser und Nenner. Ursache: `_EVERYTHING` in
`tools/affected_tests.py` kannte nur `tests/conftest.py`. Gebaut:
`"conftest.py"` in `_EVERYTHING`, Fall `test_the_root_conftest_selects_every_test`,
Mutation rot. Keine Wirkung beim Kunden. Stand: behoben in `93f5808f8`
(Paket Q, über welle5 `46308b77b`).

### CS-38 Was `tests/conftest.py` je Test ausführt, wählt nur seine Importeure

**Art:** Fehler.

Haken und autouse-Fixtures wirken auf jeden Test ohne Importkante. Beleg
(Review 2 von Q, N-2): Die Spur zeigt `tools/list_windowed_tests.py` (20 von
20 Dateien), `app/ui/settings.py` (13), `app/ui/labels.py` (12),
`app/ui/__init__.py` (3) über Fixtures und Haken der conftest ausgeführt, ohne
dass die Auswahl die Testdatei wählte; 48 von 4 181 Paaren verfehlt. Gebaut
(Entscheidung B): `ImportGraph.per_test` — was eine `conftest.py` je Test
ausführt (Haken, autouse-Fixtures samt angeforderten Fixtures und gerufenen
Funktionen, Modulebene, Wirkungsimporte), aus der Datei abgeleitet, wählt jede
Testdatei darunter; was sie nur lädt, wählt seine Importeure, bei sonst leerer
Auswahl die Gruppe. Preis: `app/ui/settings.py` 254 → 543 Testdateien.
Begründung in `konzepte/begruendungen/regel-tests.md`. Keine Wirkung beim
Kunden. Stand: behoben in `93f5808f8` (Paket Q, über welle5 `46308b77b`).

### CS-39 Der Baumwandfall mit OrcaSlicer ist unter Last nicht stabil

**Art:** Stabilität.

`tests/test_real_slicers.py`, Fall tree walls [orcaslicer]. Beleg (CI-Fix):
zweimal rot in `-n 4`-Läufen (`G1 F2418 != F2416` an Index 139, 84 Bewegungen
Unterschied), allein grün; im aufbewahrten Lauf Turm mit einer Wand 13 087
Bewegungen, mit zwei 13 171; 16 Probeläufe derselben Platte je 13 171; 3MF und
Konfigurationsblock bis auf „filament used“ gleich. Ursache: OrcaSlicer legt
organische Bäume selten anders; keine Rundung, kein Profil, keine Zeitgrenze
auf unserer Seite, ein Rot vorher ist nicht erzwingbar. Gebaut: Der Fall
vergleicht zwei Wände mit bis zu drei Läufen einer Wand (`25d925cb7`), nach
Review 2 beidseitig, die Meldung nennt die Bewegungszahlen aller Läufe
(`2fe2dadc8`). Keine Wirkung beim Kunden. Stand: behoben in `25d925cb7` und
`2fe2dadc8` (CI-Fix, über welle5 `e7765e809`).

### CS-40 Schriftmessende Fälle in Tour und Beschriftungen hängen an der Reihenfolge

**Art:** Stabilität.

`tests/test_tour.py` (2 Fälle) und `tests/test_wrapped_captions.py` (2 Fälle)
fielen nur im gemeinsamen Arbeiter, je Datei allein grün (Tour 45,
Beschriftungen 10). Beleg (Restpaket A, Review 2 F2a/D, D7): Läuft
`test_placement_dimensions.py` vorher im selben Prozess, sind beide rot (Tour
216 > 214; Beschriftungen 12 statt 14). Das Tor fährt Fensterdateien je
Prozess und sah es nicht. Ursache: Die Fälle messen Text in der Ersatzschrift,
und die misst nach einem Fall, der die Prüfschrift geladen und entfernt hat,
anders. Gebaut: Beide Dateien messen in der gebündelten Schrift
(`bundled_font`, in `test_tour.py` über eine autouse-Fixture); danach je Datei
und im Paar nach `test_placement_dimensions.py` grün (113 und 78 passed).
Keine Wirkung beim Kunden. Stand: behoben in `989a4fe32` (Restpaket A, über
welle5 `3f84a4c3c`; beim Merge blieb die Kartenhöhe aus welle5, die
gebündelte Schrift aus A).

### CS-41 Ein Docstring in `test_ui.py` nennt den alten Pin

**Art:** Aufräumen.

`tests/test_ui.py:21623` sagt im Docstring, die Suite halte Fenster früherer
Tests über `_pin_ui_widgets` am Leben. Beleg (Paket U, Neue Punkte): Seit P1
heißt der Pin `_PinOnImport` und läuft über `UI_PINS`; `_pin_ui_widgets` gibt
es nicht mehr. Ursache: Der Umbau in P1 zog den Docstring nicht nach.
Vorschlag: den Namen tauschen, wenn der Schnitt die Datei anfasst. Keine
Wirkung beim Kunden. Stand: offen nach 0.6.1,
[RM-813](../ROADMAP.md#rm-813).

### CS-42 Ein beim Import abgeleiteter Wert folgt einem Patch am Original nicht

**Art:** Fehler (Bauart CS-11).

`app/core/scene/project.py` rechnet beim Import
`MAX_ARCHIVE_UNPACKED_BYTES = 2 * loader.MAX_FILE_BYTES` und daraus
`MAX_PROJECT_FILE_BYTES` (Zeilen 85 und 86; `MAX_LINKED_SOURCE_BYTES` in
Zeile 127 übernimmt den ersten). Beleg (Paket K, Neue Punkte 2): Ein Ersatz an
`loader.MAX_FILE_BYTES` erreicht keinen der Werte; W2 c) erkennt nur reine
Kopien (`from M import N`, `X = M.N`) und sieht den abgeleiteten Ausdruck
nicht. Ursache: Der Wert entsteht einmal beim Import. Vorschlag: W2 c) auf
Ausdrücke auf Modulebene erweitern, die einen gepatchten Namen lesen, und die
Funde entscheiden wie die vier Kopien unter neuem Namen aus CS-26. Keine
Wirkung beim Kunden, die Werte sind zur Laufzeit gleich. Stand: offen nach
0.6.1, [RM-813](../ROADMAP.md#rm-813).

### CS-43 Der Schnitt bindet an 18 Stellen ein Modul lokal unter zweitem Namen

**Art:** Aufräumen.

War eine Kopie in einer Funktion importiert, setzt `tools/move_names.py` den
Modulimport an dieselbe Stelle (dieselbe Ladezeit) und übergeht die Bindung,
die die Datei auf Modulebene schon hat. Beleg (Paket K, Neue Punkte 3;
`scan_aliases.py` gegen den Stand vor dem Schnitt): 18 Stellen, etwa
`tests/test_solid_ownership.py` siebenmal `kernel` neben `brep_kernel` und
`app/core/geom/lid.py` `_hinge_plan` `shapes` neben `parts_shapes`.
Funktional gleich. Ursache: Das Werkzeug sucht keine vorhandene
Modulbindung. Vorschlag: im Werkzeug eine sichtbare Modulbindung derselben
Ladezeit wiederverwenden und die 18 Stellen neu erzeugen. Keine Wirkung beim
Kunden. Stand: offen nach 0.6.1, [RM-813](../ROADMAP.md#rm-813).

### CS-44 Das Werkzeug meldet vervielfachte Ersetzungen nicht

**Art:** Aufräumen.

Ersetzte ein Test zwei Kopien desselben Originals, stehen nach dem Schnitt
von `tools/move_names.py` zwei wortgleiche Patch-Zeilen. Beleg (Paket K, Neue
Punkte 4): zehn Funktionen, von Hand behoben in `ff972d188`. Ursache: Der
Beweis kennt beide Patch-Stellen und ihr gemeinsames Ziel, das Protokoll nennt
das Paar nicht. Vorschlag: `move_names` meldet solche Paare im Protokoll,
damit der nächste Schnitt sie nicht übersieht. Keine Wirkung beim Kunden.
Stand: offen nach 0.6.1, [RM-813](../ROADMAP.md#rm-813).
