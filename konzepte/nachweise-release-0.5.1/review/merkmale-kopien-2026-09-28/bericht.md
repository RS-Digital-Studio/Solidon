# Merkmale an Kopien und starr bewegten Körpern (28.09.2026)

Zweig `merkmale-an-kopien` (von `main` `cbef27715`), Endcommit `b9252ee36`, gepusht, Upstream gesetzt.

## Ursache

Die Erkennung überträgt eine Bewegung nur, wenn die Operation eine Matrix meldet (`OpResult.transform`) und die Ausgabe an derselben Stelle wie ihr Eingang steht. `orient_for_print` und `arrange_bed` arbeiten über der ganzen Szene und melden bei mehr als einem Körper keine Matrix, weil jeder Körper seine eigene hat. Die Musterkopien (`pattern`) ebenso. Also lief `detect` an jedem bewegten Netz vollständig neu.

`duplicate_object` selbst kostete nie etwas: Die Kopien tragen dasselbe Netzobjekt wie das Original, `detect` trifft den Merker. Teuer wurden die Kopien erst, als das Ausrichten sie bewegte. Am Minigolf-Satz war das zweite Ausrichten mit 14 von 18 Neuerkennungen der Hauptposten.

## Änderung

- `geom/transform.apply` vermerkt jede starre Bewegung ohne Spiegelung am Netz (`perceive.features.note_movement`): Abdruck des Eingangs und die Matrix. Bewegt eine Operation zweimal (Ausrichten: drehen, dann anordnen), wird zusammengesetzt, höchstens vier Vorfahren.
- `scene/evaluate._motion_of`: Meldet die Operation keine Matrix, fragt die Auswertung `features.moved_from(ausgabe, eingänge)`. Geglaubt wird erst nach `moved_twin` (dieselben Dreiecke, jede Ecke an der bewegten Stelle, 1e-7 mm). Danach geht die Ausgabe exakt den Weg einer gemeldeten Bewegung: `carry_detection`, nachgeführte Merkmale, `standing` für die örtliche Nachmessung großer Körper. Dieselbe Genauigkeit wie beim Verschieben, dieselbe Zuordnung (`matching`), dieselben Namen.
- Ein Netz, das selbst ein Eingang ist, gilt als unbewegt (`moved_from`). Ohne diese Sperre verschob ein durchreichender Schritt (*Überschneidungen prüfen* nach einer verschobenen Kopie) die Merkmale ein zweites Mal. Gefunden beim Bau, Gegenprobe rot (Namen gingen verloren).
- Spiegeln bekommt keinen Vermerk (Hand eines Gewindes wechselt, der Umlaufsinn dreht ohnehin, `moved_twin` schlüge fehl), Skalieren ist nicht starr. Beide erkennen weiter neu.
- Plattencache: der Vermerk reist als `moved_from` im Eintrag (`scene/cache._movement_to_disk/_from_disk`), additiv, kein `CACHE_FORMAT_VERSION`-Sprung, kein Projektformat-Sprung (bleibt 37).
- Exakte Körper unverändert: Sie werden nicht erkannt, `moved_object` führt ihre Merkmale in der Operation.

Merkmalskennungen: Eine Kopie ist ein eigenes Objekt; ihre Merkmale sind über `FeatureRef(objekt, merkmal)` eindeutig, gleiche Merkmalsnamen an Original und Kopie sind so gewollt (vorher wie nachher). Provenienz und Erzeuger bleiben, wie die Zuordnung sie vorher auch gab (Korpusvergleich unten).

Nicht angefasst: `app/core/scene/hashing.py`, das Register, `app/core/ingest/`. `app/core/knowledge/data/part_ranges.toml` ist neu gefahren (alle 35 bestanden), weil `geom/transform.py` im Abdruck jedes Bausteins steht — beim Zusammenführen mit anderen Zweigen, die dieselbe Datei neu fahren, einmal `python tools/check_part_ranges.py` auf dem Ergebnis.

## Tests (Test zuerst, Gegenprobe gegen `cbef27715`)

In `tests/test_matching.py`:

| Test | Stand `cbef27715` | neu |
|---|---|---|
| `test_copies_turned_for_print_keep_their_features_without_a_search` — Lochplatte laden, hochkant drehen, auf zwei duplizieren, druckoptimal ausrichten; gezählt werden `detect`-Aufrufe, die rechnen (Monkeypatch am Aufruf aus der Auswertung, Merker vorher leer); Arten, Zahl, Namen, Provenienz, Dreiecke je Merkmal, Mitte und Achse gegen die von außen (Kabsch) bestimmte Bewegung | rot: 3 Erkennungen statt 1 | grün |
| `test_arranging_copies_does_not_search_again` — drei Ausfertigungen, *Auf dem Bett anordnen* | rot: 4 statt 1 | grün |
| `test_a_reopened_project_carries_the_turn_from_the_disk_cache` — zweite Auswertung aus einem frischen Plattencache | rot: 3 statt 1 | grün; mit abgeschaltetem Schreiben des Vermerks rot (Mutation) |
| `test_a_step_that_passes_a_moved_copy_through_does_not_move_it_again` | — | grün; ohne die Sperre rot (Mutation) |
| `test_scaling_and_mirroring_search_again[scale_object, mirror_object]` — neu erkannt, kein Vermerk, Namen/Arten/Provenienz wie geladen | Verhalten gleich (nur der Import des neuen Namens fehlte) | grün |
| `test_a_movement_note_is_a_promise_not_a_proof` — Zusammensetzen zweier Bewegungen, falscher Eingang, falsche Matrix, kein Vermerk, Kettenlänge | — | grün |

In `tests/test_helix.py`: `test_a_turned_bolt_keeps_its_thread_and_a_mirrored_one_is_read_again` — M6-Bolzen gedreht: übertragen, bleibt rechts; gespiegelt: kein Vermerk, neu gelesen, links.

Bestehende Tests zu stabilen IDs und Übertragung (`test_matching.py` ganz, `test_local_detection.py`, `test_feature_patterns.py`, `test_evaluation.py`, `test_cache.py`) grün, im Tor enthalten.

## Messung am echten Modell

Roberts Projekt `F:\3D Dateien\Mini+Golf+All+Set-P1S_stls\falsch liegend.p3d`, nur gelesen, ohne Ergebnis-Cache ausgewertet (`load_operations()`, `evaluate(document, profile, sources=ProjectSources(project, base_dir=…))`). Sonden und Rohdaten in diesem Ordner (`sonde_minigolf.py`, `im_wechsel.py`, `sonde_wiederoeffnen.py`, `vorher-*.json`, `nachher-*.json`, `wiederoeffnen-*.json`). `vorher.json`/`nachher.json` ohne Nummer sind die ersten Probeläufe (der nachher-Lauf noch ohne die Durchreichsperre) und stehen nicht in der Tabelle.

Maschine: dieser i9, Python-Prozesse gebunden an Kerne 0–7, Kompilat `_chain` in beiden Bäumen. **Unter starker Fremdlast** (mehrere andere Sitzungen mit Fenstertests liefen parallel), deshalb zählt die CPU-Zeit des Prozesses; die Wandzeit schwankte zwischen 72 und 564 s. Je zwei Läufe im Wechsel vorher/nachher.

| | vorher (`cbef27715`) | nachher (`b9252ee36`) |
|---|---|---|
| Erkennungsläufe, die rechnen | 18 (Laden 3, erstes Ausrichten 1, zweites Ausrichten 14) | 3 (nur die drei Ladeschritte) |
| davon übertragen | 1 (Verschieben) | 16 (Ausrichten 1 + 14, Verschieben 1) |
| Zeit in `detect` | 251 s / 309 s | 67 s / 21 s |
| CPU-Zeit der ganzen Auswertung | 185 s / 190 s | 87 s / 70 s |
| Wandzeit (Fremdlast) | 388 s / 564 s | 349 s / 72 s |
| Wiederöffnen aus dem Plattencache (zweite Auswertung, Merker leer) | 273 s, 18 Erkennungen | 32 s, 3 Erkennungen |
| Merkmale am Endstand (16 Körper, 48 Merkmale: Namen, Art, Provenienz, Erzeuger, Dreiecke, Mitte) | — | 0 Unterschiede |

Robert maß am selben Projekt 441 s, davon 323 s in `detect`. Was nachher bleibt, ist die erste Erkennung je geladener Datei und die Suche von *Druckoptimal ausrichten* selbst.

Ein Unterschied im Bericht, gewollt: `perceive.freeform` stand vorher 24-mal, nachher 16-mal. Neu erkannt ließ derselbe Körper (`obj_1` bis `obj_4`) nach jeder Drehung eine andere Zahl Rundformen weg (37, 36, 35 — die Lageabhängigkeit aus RM-210), und `_without_repeats` behielt drei verschiedene Sätze je Körper. Übertragen bleibt es bei einem Satz mit 37.

## Korpusvergleich `tests/data/meshes`

`sonde_korpus.py`, `vergleich_korpus.py`, Ergebnis `korpus-vergleich.txt`. Je Datei (36) zwei Abläufe, beide Bäume, Merker leer, ohne Ergebnis-Cache:

- *kopieren*: laden, hochkant drehen, auf drei Ausfertigungen duplizieren, *Druckoptimal ausrichten* (Vorgaben), *Auf dem Bett anordnen*.
- *spiegeln*: laden, spiegeln (x), skalieren (1,5).

Ergebnis: 144 Körper, 1056 Merkmale verglichen (Name, Art, Provenienz, Erzeuger, Dreieckszahl, Mitte, Achse, Durchmesser; Lage auf 1e-4 mm), **0 Unterschiede**, Befunde und Halte gleich (ein Halt `NoFittingOrientationError` an `oversized.stl` in beiden). Erkennungsläufe *kopieren* 145 → 36, *spiegeln* 108 → 108.

## Tor

Alle Läufe über die venv, gebunden an Kerne 0–7 (eigener Starter, der die Prozessbindung vor dem Start setzt; Kindprozesse erben sie).

| Schritt | Ergebnis |
|---|---|
| `bash .claude/scripts/suite-getrennt.sh` | Exit 0 — 18003 passed, 36 skipped, 18039 von 18039 gelaufen, „Läufe mit Fehler: 0“ |
| `ruff check .` | Exit 0 |
| `ruff format --check .` | Exit 0 (1043 Dateien) |
| `mypy` | Exit 0 (330 Dateien) |
| `mypy --platform linux` | Exit 0 |
| `mypy --platform darwin` | Exit 0 |
| `tools/check_part_ranges.py --jobs 6` | Exit 0, 35 von 35 bestanden |

Der erste Torlauf war rot mit drei Befunden, alle behoben bzw. zugeordnet: Regelbudget `operationen.md` (30 KB) durch meinen Satz überschritten — gekürzt, der Satz zu Spiegeln/Skalieren steht jetzt knapp in `schichtanalyse.md`, die Begründung in `konzepte/begruendungen/karte-app-core-perceive.md`; Bereichsnachweise veraltet — neu gefahren; `test_labels_render_in_a_fresh_interpreter` lief in sein 120-s-Zeitlimit, während parallel die Sonden und fremde Fenstertests liefen — im zweiten Lauf grün, keine Beziehung zur Änderung (Renderer im Unterprozess).

Fenstertests und Leistungsprüfungen liefen nicht (Release).

## Unterlagen

`app/core/perceive/CLAUDE.md`, `app/core/scene/CLAUDE.md`, `app/core/geom/CLAUDE.md` (Karten), `.claude/rules/operationen.md` und `schichtanalyse.md` (Regel), `konzepte/begruendungen/karte-app-core-perceive.md` (Warum und Messung).

## Offene Fragen

1. **Die Suche von *Druckoptimal ausrichten* läuft je Kopie neu.** Nach dieser Änderung ist sie der größte Rest der Auswertung am Minigolf-Satz: vier gleiche Gövde-Körper, acht gleiche Schrauben, vier gleiche Kappen, jede Kopie rechnet `search` für dasselbe Netz. Ein Merker je Netzabdruck (gleiche Geometrie, gleiches Profil, gleiche Parameter → gleiche Lage) läge nahe. Nicht gebaut, weil es den Rechenweg einer Operation betrifft und sich mit der parallelen Arbeit an Prozesswerten im Speicherschlüssel überschneidet. Soll ich es als eigenen Punkt angehen?
2. `operationen.md` steht nach der Kürzung bei 30719 von 30720 Byte. Ein weiterer Satz braucht dort vorher eine Verdichtung.
3. Beim Zusammenführen: `part_ranges.toml` hängt am Wortlaut von `geom/transform.py`; bringt ein anderer Zweig dort Änderungen, einmal `tools/check_part_ranges.py` auf dem gemergten Stand.

## Vorschlag Changelog

- de: Beim Ausrichten, Anordnen und Kopieren behalten Teile ihre erkannten Merkmale, statt sie neu zu suchen; ein Projekt mit vielen Kopien öffnet dadurch in einem Bruchteil der Zeit.
- en: Orienting, arranging and copying keep a part's recognised features instead of searching for them again, so a project with many copies opens in a fraction of the time.
- es: Al orientar, organizar y copiar, las piezas conservan sus características reconocidas en lugar de buscarlas de nuevo; un proyecto con muchas copias se abre en una fracción del tiempo.
- fr : Orienter, disposer et copier conservent les caractéristiques reconnues d'une pièce au lieu de les rechercher à nouveau ; un projet avec de nombreuses copies s'ouvre en une fraction du temps.
- it: Orientare, disporre e copiare mantengono le caratteristiche riconosciute di un pezzo invece di cercarle di nuovo; un progetto con molte copie si apre in una frazione del tempo.
- pt: Orientar, organizar e copiar mantêm as características reconhecidas de uma peça em vez de as procurar novamente; um projeto com muitas cópias abre numa fração do tempo.
