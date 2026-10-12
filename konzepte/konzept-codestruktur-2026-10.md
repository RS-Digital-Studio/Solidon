# Konzept: Codestruktur — kürzere Dateien, mehr Ordner, eine Karte je Ordner

Stand der Messung: welle5 `f850ef25c` (main `732bde46d` plus welle5), 11.10.2026.
Auftrag: Robert, über die Sitzung „Koordination 0.6.0 Übergabe“ — nur denken und
schreiben, kein Umbau. Jede Zahl unten ist gemessen (Zeilenzählung, `ast`,
`git log`, `tools/docs_scan.py`, mypy- und Qt-Proben); geschätzt ist nur, was
ausdrücklich so heißt. Die Zahlen zu den Komponenten in 3.3 und W5 stammen
von main `ee6b810fe` (dort 895 Methoden an `MainWindow`). Geprüft von
`konzept`- und `solidon3d-review`-Agenten in fünf Runden; ihre Funde sind
eingearbeitet, die Berichte liegen unter
`.claude/.state/drache-2026-10-08/berichte-2026-10-10/codestruktur-*.md`.

## 1 Ergebnis

Solidon hat unter `app/` 490 288 Zeilen in 377 Dateien. Das Problem sind nicht
zu viele Dateien, sondern wenige riesige: Die 14 Dateien über 5 000 Zeilen
tragen 168 082 Zeilen, ein Drittel des Codes, und an ihnen wird am meisten
geändert. `app/ui/main_window.py` allein hat 29 614 Zeilen, eine Klasse mit 892
Methoden, und wurde seit dem 01.09. in 394 Commits angefasst.

Der Vorschlag:

- **Zielgrenze 2 000 Zeilen je Datei**, weil eine Sitzung so viel auf einmal
  liest. Der Bestand bekommt eine Sperrklinke statt einer Wand: Eine große
  Datei bekommt keine neue Funktion, Methode oder Klasse mehr, neuer Code geht
  in ein neues Modul.
- **Zuerst sechs Wächter und ein Verschiebewerkzeug.** Sie fangen, was beim
  Verschieben still bricht: Patches, die ins Leere greifen, Quelltextprüfungen,
  die verschobenen Code nicht mehr sehen, späte Importe, die niemand prüft,
  und Namenslisten, die ein fehlendes Modul stumm überspringen.
- **Dann Verschiebeschritte**: je große Datei ein Paket unter demselben
  Namen, ohne Rückexport, mit eigener Karte. Das Werkzeug belegt, dass jede
  Definition unverändert angekommen ist (`ast.dump` vorher gleich nachher);
  druckgleich, weil sich kein Rechenweg ändert.
- **Großklassen der Oberfläche** werden in Komponenten mit eigenem Zustand
  zerlegt, nach den Mustern von `DrawFlow` und `PlacementHost`. Das behebt die
  Ursache — eine Klasse mit 892 Methoden —, nicht nur die Dateilänge. Die
  zentralen Methoden (`__init__`, `_build_*`) werden vorher je Bereich
  geordnet; danach beweist das Werkzeug jeden Schnitt gegen eine erklärte
  Ersetzungsliste, und jede Komponente gibt beim Abbau selbst frei.
- **Einfach, an der Wurzel, kein Workaround** gilt für jeden Schritt und
  jeden Fix (3.1, Regel 9).
- **Was bei der Gelegenheit auffällt**, wird nicht im Verschiebe-Commit
  verbessert, sondern als Fund mit Beleg in einer eigenen Konzeptdatei
  festgehalten und gleich danach in eigenen Commits behoben. Jeder Schritt
  sucht dabei gezielt nach fünf Arten: Leistung, Stabilität, Fehler,
  Zwillinge, Aufräumen.
- **Abgelehnt** sind Neuschreiben, Fassaden, Ordner nach Technikschicht,
  Testunterordner, ein großer Umbauzweig und Dateisperren (Abschnitt 5).

## 2 Bestand

### 2.1 Größe

| Bereich | Dateien | Zeilen | > 1 000 | > 2 000 | > 5 000 | > 10 000 | größte |
|---|---|---|---|---|---|---|---|
| `app/` | 377 | 490 288 | 123 | 58 | 14 | 5 | 29 614 |
| `tools/` | 87 | 54 336 | 17 | 3 | 0 | 0 | 4 238 |
| `tests/` | 475 | 554 094 | 140 | 70 | 19 | 3 | 24 745 |

Die großen Dateien und ihr Aufbau (oberste Ebene, `ast`):

| Datei | Zeilen | Klassen | größte Klasse: Zeilen, Methoden | Funktionen oben |
|---|---|---|---|---|
| `app/ui/main_window.py` | 29 614 | 34 | `MainWindow` 26 529, 892 | 52 |
| `app/core/geom/prepare_ops.py` | 24 191 | 38 | — (23 Ops) | 444 |
| `app/ui/viewport.py` | 18 997 | 21 | `Viewport` 13 975, 445 | 82 |
| `app/core/perceive/features.py` | 16 530 | 25 | — | 334 |
| `app/ui/panels.py` | 12 319 | 24 | `FeaturePanel` 3 000, 100 | 100 |
| `app/ui/print_settings_dialog.py` | 9 779 | 21 | `PrintSettingsDialog` 6 966, 239 | 25 |
| `app/core/export/handover.py` | 9 174 | 8 | — | 211 |
| `app/ui/sketch_editor.py` | 8 785 | 8 | `SketchCanvas` 4 420, 164 | 40 |
| `app/core/scene/evaluate.py` | 7 414 | 10 | — | 101 |
| `app/ui/session.py` | 7 042 | 19 | `Session` 5 296, 195 | 27 |
| `app/core/slice/analysis.py` | 6 833 | 8 | — | 142 |
| `app/ui/placement_flow.py` | 6 165 | 5 | `PlacementFlow` 4 556, 116 | 31 |
| `app/core/geom/repair.py` | 5 699 | | | |
| `app/core/export/slicer_profiles.py` | 5 540 | | | |

Darunter folgen 44 Dateien zwischen 2 000 und 5 000 Zeilen, angeführt von
`app/ui/op_dialog.py` (4 818), `app/core/geom/prepare.py` (4 538),
`app/core/brep/edit.py` (4 460) und `app/ui/dialogs.py` (4 414). In `tests/`
ist `test_ui.py` mit 24 745 Zeilen die größte Datei.

Die vier großen UI-Klassen genauer:

| Klasse | Methoden | gesetzte Attribute | Signale | `super()` | größte Methoden (Zeilen) | Median |
|---|---|---|---|---|---|---|
| `MainWindow` | 892 | 335 | 2 | 3 | 1 020, 898, 550, 438 | 16 |
| `Viewport` | 445 | 289 | 46 | 10 | 916, 356, 246, 208 | 17 |
| `PrintSettingsDialog` | 239 | 184 | 5 | 6 | 310, 301, 247, 180 | 17 |
| `Session` | 195 | 69 | 34 | 1 | 427, 216, 182, 98 | 15 |

Die Methodennamen verraten den Zuschnitt nicht (`MainWindow`: `action` 50,
`show` 42, `sculpt` 21, `start` 20, `part` 17, `preview` 16 …); er muss aus dem
Attributgraphen kommen (Abschnitt 4.2).

### 2.2 Was die Größe heute kostet

**Lesen.** Eine Sitzung liest höchstens 2 000 Zeilen am Stück.
`main_window.py` braucht 15 Lesevorgänge, `prepare_ops.py` 13. In der Praxis
liest niemand die Datei, sondern sucht mit `grep` — und sieht dann die
Nachbarschaft einer Fundstelle nicht, die eine Änderung mittragen müsste.

**Änderungsdichte.** Seit dem 01.09. gab es 3 789 Commits ohne Merges. Auf die
großen Dateien entfallen, ebenfalls ohne Merges:

| Datei | Commits seit 01.09. |
|---|---|
| `app/ui/main_window.py` | 394 |
| `app/core/geom/prepare_ops.py` | 267 |
| `app/ui/panels.py` | 205 |
| `app/ui/print_settings_dialog.py` | 169 |
| `app/ui/viewport.py` | 164 |
| `app/core/perceive/features.py` | 145 |

Jeder zehnte Commit ändert `main_window.py`. Bei drei Maschinen und mehreren
Sitzungen je Welle ändern fast alle Zweige dieselben sechs Dateien.

**Karten am Anschlag.** Die Grenze je Karte ist 25 KB (25 600 Byte,
`tests/test_directory_docs.py`):

| Karte | Byte |
|---|---|
| `app/core/scene/CLAUDE.md` | 25 599 |
| `app/core/perceive/CLAUDE.md` | 25 567 |
| `app/core/geom/CLAUDE.md` | 25 507 |
| `app/core/export/CLAUDE.md` | 25 502 |
| `app/ui/CLAUDE.md` | 24 997 |
| `app/core/slice/CLAUDE.md` | 22 974 |

Fünf der sechs Karten haben weniger als 700 Byte Luft. Ein neues Modul lässt
sich dort nur noch eintragen, wenn etwas anderes gekürzt wird. Ein Ordner mehr
ist eine Karte mehr mit eigenem Budget.

**Regeln am Anschlag.** Die Grenze je Regel ist 30 KB (30 720 Byte): `kern.md`
30 687, `operationen.md` und `dateiformat.md` je 30 714, `tests.md` 30 692,
`ansicht.md` 30 566, `zeichenflaeche.md` 30 154. Dieselbe Ursache: Eine Regel
gilt über `paths:` für eine riesige Datei und muss alles enthalten, was
irgendwo darin gilt.

**Ladelast am Anschlag.** Gezählt wie `test_directory_docs` (Wurzel, eigene
Karte, Regeln über `paths:`; rot ab mehr als 160 KB):

| Datei | KB | Luft | was lädt |
|---|---|---|---|
| `app/ui/main_window.py` | 160 | 469 Byte | ui-Karte, fenster, grenzen, oberflaeche, wartezeit, zwillinge |
| `app/ui/placement_flow.py` | 160 | 964 Byte | ui-Karte, ansicht, griffe, oberflaeche, wartezeit, zwillinge |
| `app/core/scene/serialise.py` | 152 | | |
| `app/ui/viewport.py` | 146 | | ui-Karte, ansicht, griffe, kamera, oberflaeche, zwillinge |
| `app/core/geom/repair.py` | 145 | | |
| `app/ui/panels.py`, `op_dialog.py` | 141 | | ui-Karte, fenster, grenzen, oberflaeche, vorderseite, zwillinge |

Ein Absatz mehr in `fenster.md` oder `wartezeit.md` macht die Suite rot.
Zählt man, wie Codex liest, alle Karten auf dem Weg mit (dazu `app/CLAUDE.md`,
2 708 Byte), liegen beide schon heute über 160 KB: 163,2 und 162,7 KB.

### 2.3 Kopplung

- **Private Querimporte in `app/`:** 304 Namen, davon 204 aus `app.i18n`
  (Übersetzungshelfer, unkritisch). Die übrigen rund 100 konzentrieren sich auf
  `perceive/features.py` (31 Namen; allein `perceive/helix.py` holt 8),
  `brep/kernel.py` (6), `slice/analysis.py` (6), `geom/faces.py` (5),
  `geom/prepare_ops.py` (4). Dazu kommen späte Importe in Funktionen, etwa
  `from app.core.geom.prepare_ops import _reject_oversized` in `face_ops.py`.
- **Tests holen 708 private Namen**, am meisten aus `perceive/features` (73),
  `scene/evaluate` (66), `ui/panels` und `ui/print_settings_dialog` (je 48),
  `geom/prepare_ops` (32), `ui/main_window` (28).
- **Tests rufen `setattr` 4 761 Mal**: 3 137 Mal auf ein Modul, 1 509 Mal auf
  ein Objekt oder eine Klasse, 115 Mal mit einem Pfad als Text (88 davon auf
  `app.`). Je Modul gezählt (Modulobjekt, Text und `mock.patch`, Alias je
  Funktion aufgelöst) zielen auf `features` 123 Patches, auf `main_window` 166,
  auf `session` 73, auf `print_settings_dialog` 72, auf `viewport` 39. Die
  meisten Patches auf UI-Module treffen Namen, die das Modul selbst nur
  importiert: bei `main_window` 158 der 166 (`show_error` 45,
  `confirm_unsaved` 14, `check_before_export` 12), bei
  `print_settings_dialog` 54 der 72. 25 Patches nutzen `raising=False`.
- **Kopfkopien:** In 54 Fällen hält ein anderes Modul per
  `from M import N` eine eigene Kopie eines Namens, etwa `features.detect` in
  `scene/evaluate.py`. Ein Patch auf `M.N` erreicht diese Kopie nicht — heute
  schon, und nach jeder Teilung öfter.
- **Quelltextprüfungen in Tests** lesen Code als Text: 17 Stellen in sieben
  Dateien lesen `app/ui/*.py` oder `perceive/*.py` flach über `glob("*.py")`,
  eine weitere `agent/`, mindestens acht weitere lesen über
  `Path(modul.__file__)`. Fast alle sind Verbotsprüfungen der Art
  `assert not culprits`.

Patches, Kopfkopien und Quelltextprüfungen sind das eigentliche Risiko jedes
Verschiebens (Abschnitt 4.1). Zwei Patches sind schon heute wirkungslos
(Funddatei, CS-9).

### 2.4 Was an Pfaden und Modulnamen hängt

| Mechanismus | Bindung | Folge beim Verschieben |
|---|---|---|
| `app/core/bootstrap.py`, `_OPERATION_MODULES` | Modulnamen; ihre Reihenfolge ist die Registerreihenfolge; Register füllen nur hier, nie als Nebenwirkung eines Paketimports | an die Stelle eines geteilten Moduls treten seine Teile in heutiger Reihenfolge |
| Träge Pakete: `app/core/lazy.py`, `core/CLAUDE.md` Muster 1, Wettlauftest in `tests/test_core_isolation.py` | Paket-`__init__` laden nichts | das `__init__` eines neuen Pakets ist ein Docstring |
| Lazy-Exporte `scene/__init__.py` („evaluate“), `agent/__init__.py` | Modulnamen als Text | nachziehen, wenn `evaluate` geteilt wird |
| Merkschlüssel im Lauf: `scene/evaluate.py` `_STEP_WAY_MODULES`, `perceive/matching.py` `_MATCH_WAYS` | Modulnamen und Funktionsnamen als Text; `_step_ways` überspringt ein fehlendes Modul stumm | nach der Teilung von `features` stünde keine Erkennungsfunktion mehr im Schlüssel — W6 |
| `tests/conftest.py`, Lebensdauer-Pin `_PinOnImport` / `_pin_ui_widgets` | `app.ui.main_window`, `app.ui.viewport`; fehlt `MainWindow` am Modul, wird stumm nichts gepinnt | nativer Abriss 0xc0000374 in der Suite — W6, im selben Commit nachziehen |
| `pyproject.toml`, mypy-Ausnahmen je Modul | `perceive.features`, `geom.repair`, `geom.prepare` namentlich; Untermodule erben sie nicht | im selben Commit auf die Teilmodule |
| `tests/test_registry_consistency.py` | wählt Module über ihre Op (`inspect.getmodule(spec.fn)`) | ein Helfermodul ohne Op (`shared.py`) fiele heraus; die Prüfung nimmt das ganze Paket |
| `.claude/rules/*.md`, `paths:` | Dateipfade, 18 Nennungen großer Dateien | im selben Commit auf `<paket>/**/*.py` |
| Karten `CLAUDE.md` | Modulnamen, Abschnitte | neue Karte im Paket, alte Karte kürzt auf einen Verweis |
| `.claude/agents/*.md` | `solidon3d-schicht.md` nennt `export/handover.py`, `solidon3d-review.md` `prepare_ops.py` | nachziehen, dann `tools/sync_agents.py` |
| `app/core/activation/integrity.py`, `BOUNDARY_FILES`; Spec `module_collection_mode = "py"` | `scene/history.py`, `export/writer.py`, `export/handover.py`, `agent/session.py` | nicht im ersten Zug (Abschnitt 4.4) |
| Bereichsnachweis, `knowledge/parts/range_proof.py` | Quelltext und relativer Pfad jeder Datei im Abdruck: `_SHARED` (`geom/intersections`, `brep/profiles`, `knowledge/standards`, `parts/*`) und die `geom`-Module, die Bausteine importieren (`lathe`, `transform`, `contours`, `geom/prepare` über `fasteners.py`); `boolean` und `mesh` sind ausgenommen; der Abdruck folgt Importen nicht weiter (nicht transitiv) | wer eine dieser Dateien verschiebt, fährt den Neunachweis der betroffenen Bausteine; beim Teilen hält der Zuschnitt die importierte Funktion (bei `geom/prepare` `ray_hits_along`) mit ihren Helfern in einem Modul, sonst deckt der Abdruck sie nicht mehr |
| `packaging/solidon3d.spec` | `collect_submodules("app.core")` | Kernpakete folgen von selbst, die UI über ihre Importe |
| CI-Aufteilung: Laufzeittabellen `tests/data/ci_*_durations.json` (`tools/ci_shards.py`), Pfadfilter in `build.yml` | Testdateinamen und Pfade | nur bei Testaufteilung; `test_ci_runner` und `test_packaging` melden es |
| `tests/test_core_package_direction.py`, `PACKAGES` | dritte Pfadstufe unter `app/core/` | Unterpakete frei; ein neues Kernpaket braucht einen Eintrag |
| Quelltextprüfungen in Tests (2.3) | flaches `glob("*.py")`, `Path(modul.__file__)` | sehen verschobenen Code nicht mehr und bleiben grün — W4 |
| `tools/affected_tests.py` | Importgraph; `glob(` ist nicht als Baumleser erkannt | folgt dem Importgraphen von selbst, Baumleser über W4 |
| Späte Importe und Modulaliasse in `tools/` | mindestens neun Werkzeuge holen `MainWindow`, etwa `make_figures.py`, `make_guides.py`, `make_gallery.py`, `make_web_images.py`, `run_ui_audit.py`, `window_bench.py`; `make_video.py` und `make_workshop_videos.py` holen das private `_feature_item`; `matrix_unit.py` greift über `handover.detect` zu und läuft in keiner Suite; mypy prüft nur `app` | brächen erst beim Release in `/erzeugen` — W5 |
| Wörtliche Pfade und Dateinamen in Tests | `main_window.py` mindestens 15 Stellen, `viewport.py` 11; `Path(main_window.__file__).parent` liegt nach der Teilung eine Ebene tiefer; Verbotstests über einen Dateipfad (`test_shared_hosting_removed.py`) | im selben Commit; ein Pfad zeigt danach auf alle Dateien des Pakets, nicht auf `__init__.py` — W4 |
| Bauplan | `ui/viewport`, `ui/sketch_editor`, `ui/panels` als Modulnamen; §11.3 nennt `app/core/slice/analysis.py` mit Endung | Modulnamen bleiben gültig; `analysis.py` zu teilen braucht eine Bauplanänderung mit Ansage |
| Logger und `caplog` | `app.ui.placement_flow` (3), `app.core.scene.evaluate` (8) | greifen über die Loggerhierarchie weiter, solange das Paket den Namen behält |
| Eigene Bausteine der Kunden (§24.5) | `<Nutzerdaten>/parts/*.py` importieren aus `app.core.knowledge.parts` und `geom` | was sie erreichen können, bleibt, wo es ist; wandert doch etwas, Hinweis im Changelog |
| Sprachregel | Datei- und Ordnernamen englisch | neue Namen englisch |
| Cache und Projektdatei | keine Modulpfade: Schlüssel über `__qualname__`, Plattencache ohne `pickle` | keine Formatnummer, kein Cache-Sprung |

Kein Zustand beim Kunden kennt einen Modulpfad; im Repository tun es der
Bereichsnachweis und die CI-Laufzeittabellen, im laufenden Prozess die
Merkschlüssel. Ohne Befund geprüft: Loggernamen (`record.name` wird nirgends
verglichen), Hooks, Skills, Workflows, der Kernprozess (`kernel_jobs` arbeitet
mit Auftragsnamen) und die Handbucherzeugung (sammelt über das Präfix
`app.core.`).

## 3 Zielbild

### 3.1 Ordnungsregeln

1. **Eine Datei, ein Thema, höchstens 2 000 Zeilen.** Die Zahl ist keine
   Geschmacksfrage: So viel liest eine Sitzung in einem Zug, und eine
   Änderung, die man ganz gelesen hat, übersieht weniger.
2. **Ein Paket übernimmt den Namen der Datei, die es ersetzt.**
   `app/ui/viewport.py` wird `app/ui/viewport/`. So bleiben Bauplan, Logger,
   Roadmap-Einträge und das Vokabular der Sitzungen gültig.
3. **Das `__init__.py` eines neuen Pakets ist ein Docstring** — es importiert
   nichts und stellt nichts bereit, wie heute `geom`, `perceive` und
   `knowledge`. Jeder Importeur zeigt auf das Modul, das den Namen definiert.
   Ein Rückexport ließe `monkeypatch.setattr(paket, "_x", …)` stillschweigend
   ins Leere greifen; ohne ihn bricht derselbe Patch laut ab, weil
   `monkeypatch` bei fehlendem Attribut eine Ausnahme wirft — außer bei
   `raising=False`, das W2 deshalb rot macht. Die Registerreihenfolge hält
   `bootstrap._OPERATION_MODULES`.
4. **Geordnet wird nach Sache, nicht nach Technik.** Bohrungen, Langlöcher,
   Gewinde, Teilen — nicht `models/`, `helpers/`, `utils/`. Ein Modul
   `shared.py` je Paket ist erlaubt, wenn es nur hält, was mindestens zwei
   Geschwister brauchen.
5. **Ein Name, der sein Modul verlässt, ist öffentlich.** Was ein
   Geschwistermodul braucht, verliert den Unterstrich, in einem eigenen Commit
   direkt nach der Verschiebung. Tests dürfen weiter private Namen lesen.
6. **Neuer Code an einer großen Datei geht in ein neues Modul.** Die
   Sperrklinke (W1) lässt keine gelistete Datei eine neue Definition
   bekommen; das ist der Teil von „Herauslösen beim Anfassen“, der trägt
   (Abschnitt 5). Eine neue Handlung am Fenster ist eine neue Komponente nach
   3.3; eine bestehende Methode um einen fremden Fall zu verlängern, damit W1
   grün bleibt, ist ein Workaround (Regel 9).
7. **Jeder neue Ordner hat eine Karte** (`test_directory_docs` verlangt sie
   ohnehin): welche Module, welcher Datenfluss, wo man einsteigt, und mit
   welchem Commit das Paket aus welcher Datei entstand — damit `git log -L` und
   `git blame -C -C` am alten Pfad weitersuchen können. Die Karte des
   Elternordners kürzt den Abschnitt auf eine Zeile mit Verweis.
8. **Regeln schneiden ihre `paths:` auf das Paket zu,** und wo eine Regel nur
   einen Teil betrifft (zum Beispiel nur den Menüaufbau), auf dieses Modul.
   Das ist der eigentliche Gewinn bei der Ladelast; der Ordnerwechsel allein
   senkt sie nur in der Zählung (4.5).
9. **Einfach, an der Wurzel, kein Workaround** (Entscheidung Robert). Jeder
   Schnitt und jeder Fix nimmt die einfachste Lösung, die die Ursache
   beseitigt. Kein Sonderfall, keine Ausnahmeliste, die einen Fehler verdeckt
   oder wachsen darf (eine Bestandsliste, die nur Programmschritte ändern, wie
   die der Sperrklinke, ist keine), kein abgeschalteter oder nur meldender
   Wächter,
   keine unterdrückte Warnung, kein `try`/`except` um ein Symptom, kein `cast`
   und kein `Any`, um eine Typprüfung zu umgehen, keine Fixture, die einen
   Fehler im Code verdeckt. Liegt die Ursache außerhalb
   des Schritts, wird sie ein Fund oder Registerpunkt — kein Pflaster an der
   Stelle, an der sie auffällt. Ein bestehender Workaround im Code ist selbst
   ein Fund.

### 3.2 Zielordner

Die Schnitte folgen gemessenen Abschnitten und Registereinträgen; der
Feinschnitt fällt im Schritt selbst am Aufrufgraphen (Abschnitt 4.2).

**`app/core/geom/prepare_ops/`** — 23 Ops, 444 Funktionen, in Blöcken:

| Modul | Inhalt | heute, ungefähr |
|---|---|---|
| `drill.py` | `drill_hole` | 800 |
| `feature_move.py` | `move_feature`, `duplicate_feature` | 6 400, weiter zu teilen |
| `feature_pattern.py` | `pattern_feature` | 900 |
| `feature_remove.py` | `remove_feature` | 250 |
| `feature_rotate.py` | `rotate_feature` | 1 450 |
| `feature_resize.py` | `resize_feature` | 900 |
| `hole_resize.py` | `resize_hole` | 750 |
| `slot.py` | `slot_hole` | 5 600, weiter zu teilen |
| `ring.py` | Wulst und Kehle am Schaft | 600 |
| `thread.py` | Gewinde ändern und verschließen | 2 300, knapp zu teilen |
| `hole_finish.py` | `countersink_hole`, `plug_hole` | 450 |
| `body.py` | `hollow_object`, `compensate_first_layer`, `set_material`, `test_piece` | 1 450 |
| `split.py` | `split_bodies`, `split_pinned`, `cut_away`, `split_line` | 1 550 |
| `bed.py` | `orient_for_print`, `arrange_bed`, `check_collisions`, `check_join_path` | 900 |
| `shared.py` | was mindestens zwei Module brauchen | offen |

Die Zahlen sind die Abstände zwischen den Registereinträgen; meist stehen die
Helfer einer Op vor ihr. Nicht immer: `ring.py` und `thread.py` tragen keine
eigene Op, ihre Helfer werden aus `remove_feature` und `resize_feature`
gerufen — der Aufrufgraph entscheidet, nicht die Zeilennummer. In
`bootstrap.py` tritt an die Stelle von `app.core.geom.prepare_ops` die Liste
der Module **mit Ops** in heutiger Registerreihenfolge; `ring.py`, `thread.py`
und `shared.py` stehen nicht darin. W3 belegt, dass Menüs und Handbuch gleich
bleiben.

**`app/core/perceive/features/`** — 334 Funktionen, gemessene Abschnitte:
Grundlagen (Zeile 1–2 237), Gewinde (150), Lage zweier Merkmale (80),
Freiformen (150), **Bohrungen (11 900)**, Flächen (1 000), offene Kanten (200),
Komponenten (800). Die Bohrungen werden ein Unterpaket `features/bores/`, nach
Erkennungsart geteilt. Höchste Kopplung im Bestand (31 private Namen aus
`app/`, 73 aus Tests, 123 Patches) — deshalb erst als dritter Schritt.

**UI-Pakete:** `app/ui/main_window/`, `app/ui/viewport/`,
`app/ui/print_settings_dialog/`, `app/ui/sketch_editor/` (mit den
`draw_*.py`), `app/ui/placement_flow/`, `app/ui/panels/`, `app/ui/session/`.
`panels.py` hat schon 24 getrennte Klassen und wird ohne Kunstgriff je Klasse
oder Klassengruppe ein Modul. Die anderen tragen je eine Großklasse; deren
Teilung beschreibt 3.3.

**Später, nach demselben Muster:** `scene/evaluate.py`, `slice/analysis.py`
(Bauplan §11.3 mit Ansage), `geom/repair.py`, `export/slicer_profiles.py`,
`geom/prepare.py` (Neunachweis der Befestiger), `ui/op_dialog.py`,
`ui/dialogs.py`, `geom/edges.py`, `brep/edit.py`, `perceive/patterns.py`. Für
sie ist der Zuschnitt noch nicht gemessen; das gehört in den jeweiligen
Schritt.

### 3.3 Großklassen der Oberfläche

Eine Klasse mit 892 Methoden und 335 Attributen ist das eigentliche Problem,
nicht die Länge ihrer Datei. Zwei Wege standen zur Wahl:

- **Mixins je Bedienbereich** (`class MainWindow(PrintActions, …,
  QMainWindow)`): teilen die Datei, nicht die Klasse. Jedes Mixin darf weiter
  jedes der 335 Attribute lesen und schreiben, der gemeinsame Zustand liegt
  danach nur über mehr Dateien verstreut. Für mypy braucht es außerdem
  entweder eine abgeschaltete Fehlerklasse (`misc`, gemessen mit mypy 2.4.0
  strict) oder eine zweite Liste der ganzen Klassenoberfläche. Das ist ein
  Workaround: Er behebt das Symptom Dateilänge und lässt die Ursache stehen.
- **Komponenten mit eigenem Zustand und schmalem Wirtsprotokoll**: Ein
  Bedienbereich wird ein eigenes Objekt, das seine Attribute selbst hält und
  vom Fenster nur das bekommt, was es braucht. Vorbilder gibt es im Code:
  `DrawFlow`, `LocalRecognitionFlow` und `SealFlow` sind QObject-Kinder des
  Fensters und typisieren es; `PlacementHost(Protocol)` ist ein Protokoll, das
  „erhoben, nicht entworfen“ ist (sein Docstring) — es nennt genau die Member,
  die die Komponente anspricht, die erklärte Abhängigkeit, keine zweite Liste
  der Klasse. Die Fensterseite von `PlacementFlow` ist dagegen kein Vorbild:
  Sie nimmt das Fenster als `Any` und greift über `getattr(window, "<name>",
  None)` zu (CS-16).

**Entscheidung: Komponenten.** Sie beheben das Problem an der Wurzel, folgen
Mustern, die es im Code schon gibt, und brauchen weder eine abgeschaltete
Prüfung noch eine doppelte Liste, kein `cast` und kein `Any`.

**Vorarbeit: die zentralen Methoden zuerst.** Wenige Methoden berühren fast
den ganzen Zustand: `_build_central` 162 der 335 Attribute, `__init__` 103,
`_build_menus` und `_discard_gestures` je 40, `_update_actions` 32,
`wait_for_workers` 22, `release` und `closeEvent` je 13. Nach der Regel „Zustand
der Komponente ist, was nur ihre Methoden benutzen“ bliebe einer Komponente
sonst kaum eigener Zustand, und ihr Protokoll würde breit. Deshalb werden
diese Methoden vorher, in eigenen Commits, in Abschnitte je Bereich zerlegt
(`_build_central` ruft `_build_<bereich>` usw.). Das ist keine Verschiebung,
sondern eine Umordnung: belegt durch die Fenstertests und die Tab-Kette, deren
Reihenfolge an der Entstehung der Widgets hängt (`oberflaeche.md`), nicht durch
den Werkzeugbeweis. Danach nimmt ein Schnitt einen Abschnitt ganz mit.

**Wie es beweisbar bleibt.** Der Attributgraph (4.2, Punkt 1) zeigt je
Bereich die Methoden und die Attribute, die nur sie benutzen; die werden
Zustand der Komponente. Was der Bereich mit dem Rest teilt, erreicht er über
den Wirt.

**Bau einer Komponente.** Eine Komponente ist ein `QObject`-Kind ihres Wirts
— Voraussetzung für `weak_slot`, `QTimer(self)`, `isValid(self)` und
`session.disconnect(self)`. Der Wirt übergibt sich beim Bau zweimal: als
Protokoll (`host`) und als Qt-Elternteil (`parent`, bei Widgets als `QWidget`,
bei `Session` und `PlacementFlow` als `QObject` typisiert). Die Komponente
hält beide **schwach**, wie `WorkerLeash` seinen Besitzer: `_host` und
`_parent` sind Eigenschaften über einer schwachen Referenz, die laut
abbrechen, wenn der Wirt fort ist. So entsteht kein Ring zwischen Fenster und
Komponente, und ein freigegebenes Fenster stirbt an seiner letzten Referenz
wie heute (`leash.py`, Docstring von `WorkerLeash`). Das starke Halten, wie
`DrawFlow` es heute tut (`self.view = window`), ist nicht das Vorbild.

Daraus folgt eine erklärte Ersetzungsliste:

| im verschobenen Rumpf | wird |
|---|---|
| `self.<eigenes>` | bleibt |
| `self.<geteiltes>` | `self._host.<geteiltes>` |
| von Qt ererbtes Member des Wirts (`findChild`, `statusBar`, …), auch wenn die Komponente gleichnamig antwortet | `self._parent.<member>` bzw. `self._host.<member>`, nie über die Komponente |
| nacktes `self` als Qt-Elternteil (Widget, Menü, Aktion, Dateidialog, `show_error(…, self)`) | `self._parent` — auch bei eingebetteten Wirten wie `Viewport`, wo `window()` das Hauptfenster wäre |
| nacktes `self` als Besitzer (`weak_slot`, `WorkerLeash(self)`, `QTimer(self)`, `isValid(self)`, `weakref.ref(self)`) | die Komponente selbst |
| nacktes `self` als Ereignisfilter (`installEventFilter(self)`) oder als Wirt eines Flusses (`DrawFlow(self)`, `SealFlow(self, …)`) | zieht mit `eventFilter` bzw. dem Fluss in die Komponente, sonst `self._host` |
| `MainWindow.<methode>` als Klassenbezug | `<Komponente>.<methode>` |

Im Fenster und überall sonst werden verschobene Methoden und Attribute zu
`<fenster>.<komponente>.<name>` — als Zugriff, als Zuweisungsziel und als
Zeichenkette, in `app/`, `tools/` und `tests/` (W5). `getattr` und `hasattr`
mit fester Zeichenkette auf das Fenster — 18 Stellen im Fenster selbst, vier
in `shortcuts_window.py` (darunter `getattr(window, "_op_actions", None) or
{}`, das bei fehlendem Namen still keine Operation zeigt), neun in `tools/` —
werden vorher in eigenem Commit gewöhnliche Attributzugriffe, ohne Vorgabe.
Gemessen kommen im Fenster 332 Stellen mit nacktem `self` vor, 256
`connect(self.<m>)`, 87 Lambdas und 48 geschachtelte Funktionen mit `self`;
dynamisches `getattr(self, name)` gibt es nicht. Das Werkzeug beweist: Jede
Methode ist nach dem Schritt `ast`-gleich mit ihrer Fassung davor, nachdem
genau diese Ersetzung angewandt wurde. mypy prüft die Komponente gegen ihr
Protokoll und das Fenster dort, wo es sich als Wirt übergibt; eine Probe mit
einem typisierten Qt-Elternteil statt des Protokolls besteht mypy strict.

**Lebensdauer liegt außerhalb des Beweises.** Gleiche Rümpfe heißen nicht
gleiche Lebensdauer: `MainWindow.release` trennt die Sitzung mit
`self.session.disconnect(self)` — der Kommentar dort nennt den Absturz, der
den Ubuntu-Runner eine Woche lang traf —, und mindestens 36
Sitzungssignale sind mit Methoden des Fensters verbunden. Jede Komponente mit
Empfängern oder Arbeitern hat deshalb ein eigenes `release()`, das
`MainWindow.release` vor `session.disconnect(self)` ruft. Ein Test verlangt,
dass danach kein Sitzungssignal eine Komponente erreicht und dass das
freigegebene Fenster ohne `gc.collect` fort ist; die Probe in 4d misst das
zuerst am heutigen Fenster.

**Was im Fenster bleibt:** was keinen geschlossenen Bereich bildet, die
Signale, die Qt-Überschreibungen (ohne `__init__`: `MainWindow` 5, `Viewport`
9, `PlacementFlow` 1) und die Verdrahtung der Komponenten. Ob das unter 2 000
Zeilen fällt, zeigt erst der Attributgraph; was darüber bleibt, hält die
Sperrklinke, und jeder weitere Bereich, der sich herauslösen lässt, ist ein
Fund der Art Aufräumen.

**Was die Probe in Schritt 4d klärt:** Signale einer Komponente, Eigenschaft
und Setter, die über zwei Bereiche reichen (`PrintSettingsDialog.settings`),
und wie viel des Fensters der erste Bereich wirklich mitnimmt. Qt-Verbindungen
über Namen gibt es in den Großklassen nicht (kein `@Slot`,
`connectSlotsByName`, `invokeMethod`, `SLOT()`); Zugriffe über Zeichenketten
gibt es, und sie werden vorher gewöhnliche Zugriffe (oben).

### 3.4 Tests

`tests/` bleibt flach. CI-Aufteilung, Isolierlauf, `conftest.py`, Datenpfade
und die Karte hängen am flachen Ordner, und eine Testdatei je Testart ist dort
die Ordnung. Große Testdateien folgen ihrem Modul, wenn es geteilt wird —
`test_ui.py` (24 745) in Bereichsdateien zusammen mit den
`MainWindow`-Schritten, die Laufzeittabellen der CI-Aufteilung im selben
Commit. Neue Tests zu einer gelisteten Datei kommen in
`test_<thema>_<bereich>.py`.

## 4 Weg

### 4.1 Schritt 0: Wächter und Werkzeug, bevor eine Zeile wandert

**W1 Sperrklinke für Dateigrößen.** Keine Datei unter `app/`, `tools/` und
`tests/` überschreitet 2 000 Zeilen, außer den 131 heutigen (58 + 3 + 70). Für
diese steht in einer Liste die Zahl ihrer Definitionen — Funktionen, Methoden
und Klassen, auch geschachtelte. Die Zahl steigt nie: Eine gelistete Datei
bekommt keine neue Definition, neuer Code geht in ein neues Modul (Regel 6).
Zeilen in bestehenden Rümpfen sind der Fix-Fall und bleiben frei. Gemessen
wird damit genau, was Regel 6 verlangt, ohne Streuzahl als Puffer. Die Liste
ändern nur Schritte dieses Programms: Ein Ordnungsschritt (4c, CS-1) hebt die
Zahl seiner Datei um genau die Abschnitte, die er im Commit benennt; jeder
Verschiebe- und Komponentenschritt senkt sie. Sonst steigt sie nie, und sie
verdeckt keinen Fehler. Eine sofort harte Zeilengrenze würde 131 Dateien rot
machen, eine Zeilenklinke jeden Fix an `main_window.py`, wo rund zehn Commits
am Tag landen.

**W2 Patch-Ziele.** Für jeden Patch auf ein Modul `M` (`monkeypatch.setattr`
auch mit `raising=False`, `mock.patch("app.…")`, `mock.patch.object`) hält der
Wächter fest, wer den Namen `N` zur Laufzeit erreicht: Funktionen, die ihn über
die Globals von `M` lesen, und Module in `app/` und `tools/`, die ihn als `M.N`,
über `getattr` oder per spätem Import holen. Diese Menge ist vor und nach einem
Schritt gleich. Eine Kopfkopie `from M import N` eines gepatchten Namens und
jedes `raising=False` auf `app.*` sind rot, nicht nur gemeldet; Schritt 0
behebt die heutigen vorher (25 `raising=False`, die Kopfkopien aus CS-11).
Aliasse löst er je Funktion auf, nicht je Datei — derselbe Name meint in einer
Testdatei mal ein Modul, mal ein Fenster. Lesen nach einem Schnitt mehrere
Module denselben gepatchten Namen, wird nicht der Patch vervielfacht: Der
Zugriff wird an der Wurzel auf eine Stelle zusammengeführt (über das Modul
oder den Wirt der Komponente), in eigenem Commit **vor** dem Schnitt, und der
Patch zielt auf diese Stelle. Patches, die etwas
verbieten („darf nicht gerufen werden“), bekommen eine Gegenprobe, dass der
Aufruf ohne Patch erreicht wird. Ein Ziel, das sich statisch nicht auflösen
lässt, ist selbst ein Fund: Der Test wird so geschrieben, dass es sich
auflöst; eine Ausnahmeliste gibt es nicht. Der erste Lauf über den heutigen
Bestand findet schon wirkungslose Patches (CS-9); die werden zuerst behoben.

**W3 Registerabzug.** Ein Werkzeug schreibt jedes Feld jedes Registereintrags
von Ops und Bausteinen außer der Funktion selbst, in Registerreihenfolge, dazu
die `tr()`-Schlüssel, in eine Textdatei. Vor und nach jedem Kernschritt ist der
Abzug byte-gleich.

**W4 Quelltextprüfungen lesen rekursiv.** Quelltextsuchen über `app/` laufen
über einen gemeinsamen rekursiven Helfer in `tests/helpers.py`; ein flaches
`glob("*.py")` über `app/` ist in `tests/` und `tools/` verboten, ohne
Ausnahme. Für das flache Paket `activation` liefert der Helfer dieselbe Menge;
dass es flach bleiben muss, sichert ab W4 eine neue Zusicherung „keine
Unterordner“ in `test_licence_build.py` — heute gibt es sie nicht. Die Gegenprobe verlangt, dass die Suche
die Definitionsmodule von `MainWindow`, `Viewport` und der Merkmalserkennung
findet — nicht nur eine Mindestzahl Dateien wie heute in `test_leash.py`.
Prüfungen über `Path(modul.__file__)` nennen das Modul, das die gesuchte
Definition trägt; das Werkzeug zieht sie mit. `affected_tests` lernt `glob(`
als Baumleser.

**W5 Importe überall auflösbar.** Jedes `from app.… import N` und jeder
Zugriff `alias.N` auf ein Modul aus `app/` in `app/`, `tools/` und `tests/`,
auch innerhalb von Funktionen, muss sich statisch auflösen. Das fängt die
späten Importe und Modulaliasse in `tools/`, die mypy nicht sieht. Bei
Komponentenschritten sucht das Werkzeug zudem jeden verschobenen Namen als
Zugriff, als Zuweisungsziel und als Zeichenkette in `app/`, `tools/` und
`tests/` und schreibt ihn um; ein Rest ist rot. Das ist nötig, weil Tests und
Werkzeuge am Fenster vorbeigreifen: 2 246 Zugriffe auf Methoden, die nur
`MainWindow` hat, in 70 Testdateien, 149 `monkeypatch.setattr(window,
"<methode>")`, 152 Zuweisungen `window.<member> = …` (die nach einem Schnitt
still ein Attribut anlegten, das niemand liest), in `tools/` 52 Zugriffe in
13 Werkzeugen und 5 `getattr(window, "…")`. Eindeutig genug ist es: 866 der
889 eigenen Methodennamen kommen sonst in `app/` nicht vor; die übrigen 23
stehen mit ihrer Entscheidung in der Zuschnittliste; fehlt eine, bricht das
Werkzeug ab.

**W6 Namenslisten lösen auf.** Wo Code Modul- oder Funktionsnamen als Text
hält — `bootstrap._OPERATION_MODULES`, `_STEP_WAY_MODULES`, `_MATCH_WAYS`,
die Lazy-Exporte, der Lebensdauer-Pin in `conftest.py` —, löst jeder Name auf
und trägt etwas bei; das stumme Überspringen eines fehlenden Moduls wird ein
Fehler. Der Lebensdauer-Pin bekommt dafür eine Zuordnung Modul → Klasse statt
der Frage nach `MainWindow` und `Viewport` an jedem Modul, denn in
`app.ui.leash` fehlen beide planmäßig. Ein Test verlangt zudem, dass
`MainWindow` und `Viewport` nach dem Import gepinnt sind (`_suite_pinned`) —
solange der Pin besteht (CS-15).

**Verschiebewerkzeug** `tools/move_names.py`: verschiebt Definitionen nach
einer Zuschnittliste in neue Module, setzt die nötigen Importe, schreibt
Importe, Patch-Ziele (W2) und Quelltextleser (W4) in `app/`, `tools/` und
`tests/` um — auch Zugriffe über Modulaliasse (`handover.detect`) und Pfade
als Text, die danach auf alle Dateien des Pakets zeigen — und hält
`global`-Schreiber mit ihren Lesern zusammen (`scene/evaluate.py` hat 5,
`ui/panels.py` einen). Bei Großklassen wendet es die erklärte Ersetzungsliste
aus 3.3 an. Es **beweist** die Verschiebung: `ast.dump` jeder Definition ist
vorher und nachher gleich, nachdem die erklärten Änderungen angewandt sind —
Importe (auch unter `TYPE_CHECKING`), die Ersetzungsliste einer Komponente und
eine Umbenennungsliste im Commit; jede andere Abweichung ist rot. Gebaut auf
`ast` und `tokenize`, ohne neue Abhängigkeit — `rope` und
`libcst` müssten für die Patch-Ziele der Tests ohnehin ergänzt werden und
brächten Lizenzeintrag und feste Version. Mit eigenem Test an einer
Paket-Attrappe.

Schritt 0 ist selbst ein Registerpunkt mit Review; erst wenn er gelandet ist,
beginnt Schritt 1.

### 4.2 Muster jedes Verschiebeschritts

1. **Zuschnitt messen.** Bei Funktionsmodulen der Aufrufgraph (wer ruft wen,
   welche Helfer teilen sich mehrere Ops); bei Großklassen der Attributgraph
   (welche Methoden lesen und schreiben welche `self.`-Attribute, welche rufen
   einander). Ergebnis: eine Zuschnittliste, die zugleich der Entwurf der neuen
   Karte ist und bei Klassen je Methode ihre Komponente, deren erhobenes
   Wirtsprotokoll und die Ersetzungsliste nennt. Dieselbe
   Durchsicht sucht gezielt die fünf Fundarten der Funddatei: Leistung
   (gemessen, bevor sie eingetragen wird), Stabilität, Fehler, Zwillinge
   (`tools/twin_scan.py` über den Zuschnitt) und Aufräumen (toter Code fällt
   aus dem Aufrufgraphen heraus).
2. **Verschieben mit dem Werkzeug.** Der Schnitt ist ein Skript —
   Zuschnittliste plus Werkzeug — und lässt sich auf jedem Stand neu erzeugen.
   Hat ein anderer Zweig die alte Datei inzwischen geändert, trägt das Werkzeug
   dessen Diff je Definition ins neue Modul nach. Eine Sperre der Datei für
   andere Sitzungen gibt es nicht.
3. **Im selben Commit:** Bootstrap-Liste und die anderen Namenslisten (W6),
   Lebensdauer-Pin in `conftest.py`, mypy-Ausnahmen in `pyproject.toml`,
   `paths:` der Regeln, neue Karte, gekürzte Elternkarte, Agentendefinitionen
   samt `sync_agents.py`, bei Testaufteilung die CI-Laufzeittabellen. Wer
   Module über ihre Op auswählt (`test_registry_consistency`), nimmt danach
   das ganze Paket. Die Unterstriche nach Regel 5 folgen in einem eigenen
   Commit.
4. **Prüfen:** Beweis des Werkzeugs, W1 bis W6, betroffene Tests,
   Baumleser-Pflichtliste (`test_toolchain`, `test_finding_ways`,
   `test_finding_actions`, `test_hard_rules`, `test_errors`,
   `test_core_isolation`, `test_core_package_direction`,
   `test_interface_limits`, `test_value_labels`, `test_shared_constants`,
   `test_language_rules`, `test_registry_consistency`, `test_text_length`,
   `test_directory_docs`), ruff, format, mypy; bei UI-Schritten die
   Fenstertests, die `tools/ci_selection.py` für den Diff nennt (7.2); vor
   main das Tor.
5. **Review:** Der Beweis des Werkzeugs trägt die Aussage „nur verschoben“.
   `git diff --color-moved=zebra` bleibt der Blick des Reviews auf den Rest:
   Zuschnitt, Karte, Regeln, Beweisprotokoll des Werkzeugs.
6. **Funde festhalten und beheben.** Alles, was beim Messen, Verschieben oder
   im Review auffällt — Leistung, Stabilität, Fehler, Zwillinge, Aufräumen —,
   kommt mit Art und Beleg in die Funddatei
   (`konzepte/konzept-codestruktur-funde-2026-10.md`), je Schritt unter einer
   eigenen Überschrift, und wird in eigenen Commits direkt nach dem Schritt
   behoben: Fehler und Stabilität mit reproduzierendem Test zuerst, Leistung
   mit Messung vorher und nachher und druckgleich, Zwillinge nach der Pflicht
   ihrer Klasse. Was größer ist, wird ein Registerpunkt in `ROADMAP.md` mit
   Verweis auf den Fund. Der Verschiebe-Commit selbst bleibt beweisbar rein.
7. **Kurz halten.** Ein Schritt ist eine Datei oder ein Bereich einer Klasse,
   beginnt am besten direkt nach einem Wellenschnitt und steht vorher im
   Register von `ROADMAP.md`.

### 4.3 Reihenfolge

| Schritt | Datei | warum an dieser Stelle |
|---|---|---|
| 0 | W1 bis W6, Verschiebewerkzeug; vorher behoben: CS-2, CS-9, CS-10, CS-11, CS-12 und die 25 `raising=False` | ohne sie ist jeder spätere Schritt Handarbeit mit stillen Fehlern, und rote Wächter fänden zuerst den Bestand |
| 1 | `geom/prepare_ops.py` | zweitgrößter Brennpunkt (267 Commits), Kern ohne Qt, klare Op-Blöcke, 32 private Testimporte; Probe für Bootstrap-Liste und W3 |
| 2 | `ui/panels.py` | 24 Klassen, schon getrennt, keine Komponente nötig; Probe für ein UI-Paket |
| 3 | `perceive/features.py` | höchste Kopplung, deshalb erst mit erprobtem Werkzeug |
| 4a | Fensterseite von `PlacementFlow` (CS-16) | das Vorbild muss selbst ohne `Any` und `getattr` auskommen, bevor andere ihm folgen |
| 4b | Paket `app/ui/main_window/` | die 22 Arbeiterklassen und 52 Funktionen vor `MainWindow` ziehen rein verschiebbar in Sachmodule, die Klasse nach `window.py` |
| 4c | zentrale Methoden von `MainWindow` je Bereich ordnen | `__init__`, `_build_*`, `_update_actions`, `release`, `wait_for_workers`, `closeEvent`, `_discard_gestures` — belegt durch Fenstertests und Tab-Kette |
| 4d | erste Komponente | der Bereich mit der saubersten Grenze im Attributgraphen; Probe für Ersetzungsliste, Beweis, `release()` und Signale |
| 5 | weitere Komponenten aus `MainWindow` | je Bedienbereich ein Schritt, `test_ui.py` zieht mit |
| 6 | `ui/viewport.py`, `ui/print_settings_dialog.py`, `ui/sketch_editor.py`, `ui/session.py`, `ui/placement_flow.py` | je Großklasse ein oder mehrere Schritte nach demselben Muster |
| 7 | die Dateien aus „Später“ in 3.2 | nach Brennpunkt geordnet, je ein Schritt |
| 8 | `export/handover.py`, danach bei Bedarf die anderen Grenzdateien | eigener Schritt mit `solidon3d-auslieferung` (4.4) |

**Aufwand, geschätzt** in Arbeitstagen einer Sitzung, ungemessen:

| Posten | Tage |
|---|---|
| Schritt 0: Wächter, Werkzeug, vorher behobene Funde | 6–7 |
| Kerndateien und „Später“ (13 Dateien, je ½–1) | 7–13 |
| `MainWindow`: CS-16, Paket, zentrale Methoden, 14–18 Komponenten (mindestens 11, weil (26 529 − 5 000) / 2 000 = 10,8; Bereiche sind ungleich groß) | 21–26 |
| übrige Großklassen (`Viewport`, `PrintSettingsDialog`, `SketchCanvas`, `Session`, `PlacementFlow`): Ordnen und 14–16 Komponenten | 17–20 |
| `handover.py` mit Integritätsprüfung | 2–3 |
| **zusammen** | **53–69** |

Das sind elf bis vierzehn Wochen Arbeit einer Sitzung; mehrere Sitzungen
können verschiedene Dateien gleichzeitig nehmen. Schon die Posten der
Mixin-Fassung ergaben vier bis acht Wochen; den Rest bringen die Komponenten,
weil die Ursache behoben wird statt der Dateilänge. Nach der Probe in Schritt
4d wird neu geschätzt.

### 4.4 Grenzdateien

`scene/history.py`, `export/writer.py`, `export/handover.py` und
`agent/session.py` sind Teil der Integritätsprüfung der Aktivierung und werden
im Paket als Quelltext ausgeliefert. Wer `handover.py` (9 174 Zeilen) teilt,
macht jedes entstehende Modul zur Grenzdatei: `BOUNDARY_FILES`,
`module_collection_mode` in der Spec und der Abgleich im gebauten Paket ziehen
im selben Commit nach, geprüft am gebauten Artefakt. Das ist
Sicherheitsarbeit mit eigenem Review und kommt deshalb zuletzt; die anderen
drei Grenzdateien liegen unter 4 000 Zeilen und brauchen vorerst nichts.

### 4.5 Abnahme

**Je Schritt:**

- Bei Dateischritten: Die geteilte Datei ist weg; jedes neue Modul liegt
  unter 2 000 Zeilen oder steht in der Sperrklinke. Bei Komponentenschritten:
  Die Komponente steht im eigenen Modul unter 2 000 Zeilen, ihr Protokoll ist
  erhoben, sie gibt in `release()` frei, und die Zahl der Definitionen der
  Großklasse in der Sperrklinke ist gesunken.
- Der Beweis des Werkzeugs ist grün: jede Definition `ast`-gleich, nachdem
  die erklärten Änderungen angewandt sind (Importe, Ersetzungsliste,
  Umbenennungsliste), sonst nichts.
- Registerabzug byte-gleich, `tr()`-Kataloge unverändert, Bereichsnachweis ohne
  `stale`, W1 bis W6, Pflichtliste und Tor grün.
- Neue Karte vorhanden, Elternkarte gekürzt, `paths:` nachgezogen. Die
  Ladelast jeder berührten Datei, gezählt **mit allen Karten auf dem Weg** von
  der Wurzel bis zum Paket, ist nicht höher als vorher. `docs_scan` zählt
  heute nur die eigene Karte; nach einem Ordnerwechsel fiele dort die ui-Karte
  von selbst weg, und die Abnahme wäre ohne Wirkung erfüllt.
- Bei UI-Schritten vor dem Merge die Fenstertests lokal grün, die
  `tools/ci_selection.py` für den Diff nennt (7.2), nach dem Push die der CI;
  die Startzeit nach Bauplan §31 misst der nächste Release-Lauf, weil die CI
  Leistungstests ausschließt.
- Die Funde des Schritts stehen in der Funddatei, für jede der fünf Arten —
  auch „nichts gefunden“; kleine sind in eigenen Commits behoben, größere als
  Registerpunkt eingetragen.

**Für das Programm:** keine Datei unter `app/` über 5 000 Zeilen; keine Karte
über 90 % ihres Budgets; jede Datei aus `main_window` und `placement_flow`
mit allen Karten auf dem Weg höchstens 145 KB (heute 163,2 und 162,7 KB); die
Sperrklinke kürzer als heute.

## 5 Abgelehnt

- **Neuschreiben, und Verbesserungen im Verschiebe-Commit.** Mischt
  Verschiebung und Verhaltensänderung; der Beweis des Werkzeugs fiele weg, und
  „druckgleich“ würde von einer Eigenschaft der Methode zu einer Behauptung,
  die man messen muss. Was bei der Gelegenheit auffällt, wird deshalb nicht
  verworfen, sondern als Fund festgehalten (Entscheidung Robert): Leistung,
  Stabilität, Fehler, Zwillinge und Aufräumen, mit Beleg in
  `konzepte/konzept-codestruktur-funde-2026-10.md`, behoben in eigenen
  Commits direkt nach dem Schritt oder als Registerpunkt. Die Datei trägt
  schon die Funde aus Messung und Prüfung dieses Konzepts.
- **Nur Herauslösen beim Anfassen.** Für neuen Code richtig und als Regel 6
  übernommen. Als einziger Weg für den Bestand nicht: Bei 394 Commits in 41
  Tagen auf `main_window.py` würde die Datei in Dutzenden kleinen Schnitten aus
  parallelen Zweigen zerlegt, jeder mit eigenem Zuschnitt und ohne Beweis, und
  die großen, selten berührten Blöcke blieben für immer liegen.
- **Mixins für die Großklassen.** Teilen die Datei, nicht die Klasse, und
  verteilen den gemeinsamen Zustand von 335 Attributen nur über mehr Dateien.
  Für die Typprüfung bräuchten sie eine abgeschaltete Fehlerklasse oder eine
  zweite Liste der Klassenoberfläche — ein Workaround statt der Behebung an der
  Wurzel (3.3).
- **Fassaden unter altem Namen.** Lassen Patches stillschweigend ins Leere
  greifen, schaffen zwei Wege zu einem Namen und brechen das träge
  `__init__`.
- **Ordner nach Technikschicht** (`models/`, `services/`, `utils/`). Zerstreut
  ein Thema über mehrere Ordner; die Karten erklärten dann Technik statt Sache.
- **Neue Abstraktionen über das vorhandene Komponentenmuster hinaus**
  (Controller-Schichten, Befehlsobjekte, Ereignisbus). Größer als der Auftrag
  und nicht einfacher; das Muster von `PlacementFlow` genügt.
- **Tests in Unterordnern.** CI-Aufteilung, Isolierlauf und Karte hängen am
  flachen Ordner; der Gewinn ist klein.
- **Ein großer Umbauzweig.** Kollidiert über Tage mit jeder Sitzung, die an
  den sechs Brennpunktdateien arbeitet.
- **Eine Dateisperre während eines Schritts.** Robert hat Sperren zwischen
  Sitzungen ausgeschlossen; der wiederholbare Schnitt (4.2, Punkt 2) macht sie
  unnötig.
- **Eine sofort harte Grenze.** 131 Dateien wären rot; die Sperrklinke
  erreicht dasselbe Ziel, ohne die Arbeit anzuhalten.
- **Ein Refactoring-Werkzeug als Abhängigkeit** (`rope`, `libcst`). Für die
  Patch-Ziele der Tests ohnehin zu ergänzen, und jedes bringt einen
  Lizenzeintrag und eine feste Version mehr (Regel 22) für Arbeit, die `ast`
  und `tokenize` leisten.
- **Module im Abdruck des Bereichsnachweises nebenbei verschieben.** Jede
  Bewegung erzwingt den Neunachweis der Bausteine, die sie importieren; solche
  Module wandern nur gebündelt und mit eingeplantem Nachweislauf.

## 6 Kosten und Risiken

- **Konflikte mit paralleler Arbeit** sind der größte Preis. Gegenmittel:
  der wiederholbare Schnitt, Schritte direkt nach einem Wellenschnitt, je
  Schritt eine Datei.
- **Lokale Fenstertests vor jedem UI-Merge** kosten Zeit je Schritt. Ohne sie
  landeten UI-Schritte auf main, bevor ein Fenstertest läuft, und ein roter
  Lauf hielte alle Sitzungen auf; deshalb laufen sie (7.2).
- **Die Historie einer Zeile** findet `git log --follow` nach einer Teilung
  nicht mehr; `git blame -C -C` und `git log -L` finden verschobene Zeilen.
  Die Karte des Pakets nennt den Commit des Schnitts (Regel 7); in `tests.md`
  ist dafür kein Platz mehr (28 Byte Luft).
- **Komponenten sind mehr Arbeit als ein reines Verschieben.** Vorher werden
  die zentralen Methoden je Bereich geordnet, was der Werkzeugbeweis nicht
  abdeckt; jede Komponente braucht ihren Zuschnitt aus dem Attributgraphen,
  ihr Wirtsprotokoll, eine Ersetzungsliste und ein eigenes `release()`;
  Patches und Zugriffe in Tests ziehen von `window.methode` auf
  `window.<komponente>.methode` um. Dafür sinkt die Kopplung wirklich, und die
  Typprüfung bleibt vollständig. Wie viel von `MainWindow` übrig bleibt, ist
  erst nach dem Attributgraphen bekannt.
- **Rund 25 neue Karten** wollen gepflegt werden. `test_directory_docs`
  verlangt sie und prüft ihre Verweise; die Elternkarten werden dafür kürzer.
- **Alte Pfade außerhalb des Repositorys** (Erinnerungen auf drei Maschinen,
  Konzepte im Archiv) veralten. Wo ein Paket den Modulnamen übernimmt, bleibt
  der Name richtig; nur `….py`-Pfade werden falsch.
- **Eigene Bausteine der Kunden** importieren aus `knowledge.parts` und
  `geom`. Was sie erreichen können, bleibt an seinem Platz; muss doch etwas
  wandern, laden betroffene Bausteine mit einer Meldung nicht, und der
  Changelog sagt es.
- **Das Verschiebewerkzeug** kann selbst Fehler machen. Deshalb sein eigener
  Test, der `ast`-Beweis, W2, W4 und W6 als unabhängige Gegenproben und das Review.

## 7 Entscheidungen Robert (11.10.2026)

1. **Das Programm kommt, Beginn nach der Veröffentlichung von 0.6.0.** Es
   läuft nicht neben einer laufenden Welle. Die Schätzung stieg von den
   ursprünglich genannten drei bis vier auf elf bis vierzehn Wochen Arbeit
   einer Sitzung (4.3, mit Rechnung): Schon die alten Posten ergaben vier bis
   acht Wochen, den Rest bringen Komponenten statt Mixins. Robert hat das
   Programm mit dieser Schätzung bestätigt.
2. **Fenstertests vor dem Merge der Oberflächenschritte: ja.** Für die
   Schritte 2, 4 bis 6 und die UI-Dateien aus 7 laufen vor dem Merge lokal die
   Fenstertests, die `tools/ci_selection.py` für den Diff nennt. Das ist eine
   Ausnahme von „Fenster lokal nur beim Release“ nur für diese Schritte;
   sie kommt mit Schritt 0 in `AGENTS.md` („Arbeitsweise“) und `/liefern`.
   Grund: Ein Oberflächenschritt verschiebt Tausende Zeilen (`MainWindow`
   allein 26 000); bräche dabei etwas, wäre main rot und hielte alle
   Sitzungen auf.
3. **Einfach, an der Wurzel, kein Workaround** für jeden Schritt und jeden Fix
   (3.1, Regel 9). Daraus folgte die Entscheidung für Komponenten statt Mixins
   (3.3).
4. **Vorrang der Kundenpakete:** Die Kundenpakete des Funktionsdurchgangs
   (`konzept-funktionsdurchgang`, D0, D1, D9, D8, D3, D4) gehen vor die
   Schritte 4b bis 5 dieses Programms (Komponenten von `MainWindow`); Schritt 0
   bis 3 können daneben laufen. Ohne Datum: Beide Programme laufen in vier
   Phasen direkt hintereinander, jede sauber bis zu Ende, kein Schritt wird für
   einen Termin gekürzt (Robert, 12.10.; vorher galt der Vorrang bis zum
   25.11.).

Ohne Rückfrage festgelegt: Schritt 0 kommt zuerst und landet vor Schritt 1.
