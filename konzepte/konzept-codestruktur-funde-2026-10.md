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
Wirkung beim Kunden: möglich, wenn eine der Verbotsprüfungen in `render/`
heute einen Verstoß übersieht. Stand: [RM-723](../ROADMAP.md#rm-723).

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
öffentlich machen, wenn zwei Erzeuger es brauchen. Stand: [RM-724](../ROADMAP.md#rm-724).

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
zu viel. Stand: [RM-725](../ROADMAP.md#rm-725).

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
Stand: [RM-726](../ROADMAP.md#rm-726).

### CS-10 Namenslisten überspringen Fehlendes stumm

**Art:** Stabilität.

- `scene/evaluate.py` `_step_ways` liest `sys.modules.get(name)` für jeden
  Eintrag aus `_STEP_WAY_MODULES` und überspringt ein fehlendes Modul ohne
  Meldung; der Merkschlüssel eines Schritts verlöre dann still Funktionen.
- `tests/conftest.py` `_pin_ui_widgets` holt `getattr(module, "MainWindow",
  None)` und überspringt `None`; ohne Pin droht der native Abriss, den der
  Docstring dort beschreibt.

Vorschlag: W6 des Konzepts sofort, unabhängig vom Umbau — jeder Name löst auf
und trägt etwas bei, sonst Fehler. Stand: [RM-727](../ROADMAP.md#rm-727).

### CS-11 Kopfkopien entziehen sich Patches

**Art:** Fehler.

In 54 Fällen hält ein Modul per `from M import N` eine eigene Kopie eines
Namens, den Tests an `M` patchen, etwa `features.detect` in
`scene/evaluate.py`. Ein Patch auf `M.N` erreicht die Kopie nicht.

Vorschlag: je Paar prüfen, ob ein Test die Wirkung in der Kopie erwartet;
wenn ja, dort über das Modul zugreifen (`features.detect`) oder den Patch
umsetzen. W2 macht neue Fälle rot. Stand: [RM-728](../ROADMAP.md#rm-728).

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
Kommentar entfällt. Stand: [RM-729](../ROADMAP.md#rm-729).

### CS-13 `tools/matrix_unit.py` läuft in keiner Suite

**Art:** Stabilität.

Das Werkzeug greift über Modulaliasse zu (`handover.detect` und weitere, um
Zeile 370, 378, 785). Bräche ein Name, fiele es erst beim nächsten
Matrixlauf auf.

Vorschlag: W5 deckt die Zugriffe statisch; zusätzlich ein Rauchtest, der das
Modul importiert. Stand: [RM-730](../ROADMAP.md#rm-730).

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
eine `WorkerLeash` besitzen, bis zum Ende ihres Tests (`_PinOnImport`,
`_pin_ui_widgets`, `_windows_live_until_their_test_ends`). Der Mechanismus ist
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

