# Durchsicht der CI-Optimierung und Fortsetzung (24.09.2026, abends)

Zweite Hälfte des Auftrags aus `../ergebnis.md`: Codex' Umsetzung
durchgesehen, Befunde behoben, die Kernsuite aufgeteilt. Windows 11,
CPython 3.14.7, Arbeitsbaum geteilt mit drei weiteren Sitzungen. Alle
Zeiten sind lokal gemessen; eine CI-Laufzeit behauptet dieser Bericht nicht
(CI-08). Das JUnit des Kernlaufs (2,2 MB) liegt nicht bei; die daraus erzeugte
Tabelle ist `tests/data/ci_core_durations.json`.

## Kernsuite je Test

`pytest -n 8 -m "not performance and not windowed and not rendered"
--durations=0 --junitxml=…`: 16 575 Fälle, 3036 s Rechenzeit, 584 s Wand
(`kernlauf-je-test.txt`; die 7 roten Fälle stammten aus parallelen Arbeiten).
Ein Fall trug 319 s — `test_seal_geometry[12.0]`, die zehn längsten 22 %.

## Wandmessung

`seal_probe.py` zerlegt den Fall: 378 s in `local_wall_thickness`
(`seal-vorher.txt`), weil `geom.mesh.ray_hits_batch` seit RM-050 jeden Strahl
gegen jedes Dreieck rechnete — 45 368² Paare. Mit der räumlichen Vorauswahl
und fester Reichweitenverdopplung 151 s (`seal-halbe-reichweite.txt`), mit
Reichweite je Strahl 24 s bei gleicher Wandstärke (`seal-nachher.txt`,
`seal-profil.txt`: 171 Mio. statt 2,06 Mrd. Paare).

`mutation.py` nimmt jede der drei Sicherungen einzeln heraus
(Übernahmegrenze, Randzugabe, Stücklänge); alle drei Mutanten werden von
`test_each_safeguard_of_the_ray_preselection_decides_a_constructed_case` rot
(`gegenprobe.txt`). Der Zufallsvergleich allein war dafür zu gutmütig.

`bausteinnachweis.txt`: `tools/check_part_ranges.py --all --jobs 4`, Exit 0,
199 s, 35 von 35 bestanden. In `part_ranges.toml` änderten sich nur
Fingerabdruck und Datum.

## Aufteilung

Drei Kernteile über die ganze Sammlung: 16 669 Fälle ohne Teilung, 6796 +
5015 + 4858 mit `--ci-shard 0/3 … 2/3`, keiner doppelt, keine Datei in zwei
Teilen. `worksteal-messung.txt`: Teil 0/3 mit `-n 4`, `load` gegen
`worksteal` in beiden Reihenfolgen, 356 → 206 s und 213 → 160 s. Die roten
Fälle darin folgen den Dateizeiten paralleler Sitzungen, nicht der Verteilung.

## Befunde an Codex' Stand

- Die Fensterausgabe stand nur in Artefakt-Dateien; im CI-Protokoll stand
  bei einem Fehler nichts, der Schrittbericht fehlte. Behoben im Läufer.
- `test_ci_preserves_the_first_failed_process_exit` fuhr den Shellblock im
  Repository-Wurzelordner; `mkdir -p reports/core` hinterließ bei jedem Lauf
  ein leeres `reports/`.
- `test_baseline_names_the_measured_successful_job_and_all_original_files`
  hielt Lauf-ID, Dateizahl und `test_ui.py`-Sekunden fest — Ist-Zustand statt
  Zusage; jede neu erzeugte Tabelle wäre rot geworden.
- Der Workflow-Kopf verlor Wissen (Push nur Ubuntu, Signierweg); die Aussage
  „öffentlich, kostet nichts" war ohnehin veraltet. `tools/check_message.py`
  nannte einen zusammengelegten Testnamen. Die Fensterverträge installierten
  PHP ohne Bedarf.
- `ui_split_vs_head.py`: Der UI-Umzug war gegen eine Arbeitskopie verglichen,
  nicht gegen HEAD. Gegen HEAD sind alle verschobenen Funktionen AST-gleich;
  in `test_ui.py` liegen daneben acht fremde neue Tests und eine fremd
  geänderte Funktion, die nicht zum Umzug gehören.

## Unabhängige Review und Nacharbeit (25.09.2026)

`review-unabhaengig.md` ist der vollständige Bericht eines zweiten Prüfers
über den ganzen Stand. Er bestätigt Beweis, Aufteilung und Paketsperre und
fand einen Fehler, drei Risiken und elf Hinweise. Umgesetzt:

- **3.1** Die Nachfrist für entkommene Nachfahren griff nicht:
  `Popen.__exit__` schloss den Leser, während der Kopierfaden darin
  blockierte. Die Leitung geht jetzt an den Faden über; Test mit echtem
  Enkel (Bericht nach 1,3 s statt nach dessen 30 s).
- **3.2** Ein Schreibfehler an Konsole oder Protokoll beendete das Leeren der
  Leitung; jetzt fällt nur das Ziel weg. **3.3** `::stop-commands::` um die
  Prüfausgabe. **3.4** Die Meldung zu Abbaufehlern nennt Einträge statt Fälle.
- **1.2** Negatives `minimum_travel` rechnet voll; **1.5** Strahlen der Länge
  null bekommen `inf` ohne Rechnung; **1.4** Tests für Rundengrenze, Abbruch,
  Treffer hinter dem Ursprung und die neue Halbe-Auswahl-Regel.
- **1.1** Vollkörper: Erreicht die Auswahl einer Gruppe die Hälfte aller
  Dreiecke, rechnen deren Strahlen gemeinsam voll. Stärkeres Wachstum (4)
  und größere Zellen wurden gemessen und verworfen (`bausteine-wachstum-2-4.txt`,
  `zellbreite.txt`): Beide kosten die dünnwandige Schnur mehr, als sie den
  Kugeln sparen. Die verbleibende Grenze — bis etwa das Anderthalbfache des
  Vollvergleichs an Vollkörpern, die 35 Bausteine zusammen gleich — steht an
  `RAY_CULL_PAIRS` und in `geom/CLAUDE.md`; ein echter räumlicher Index ist
  ein Registerpunkt.
- **1.3, 2.1, 2.2, 7.1, 7.2** Doku, Tabellenherkunft, Konzeptwiderspruch und
  Aufrufbeispiel berichtigt. **4.1** Die Tests eines Teils laufen auch nach
  rotem mypy. **4.2** `overwrite: true` für wiederholte Jobs. **4.3** Die
  Artefaktgrenze von 100 steht in `auslieferung.md`. **5.1** `step_block`
  endet an jedem Schritt. **6.1** Die zusammengelegten Tests in
  `test_translations.py` und `test_parts.py` melden alle Befunde
  (`merge_probe.py`: beide Befunde im selben Bericht).

## Entwicklungstor

`entwicklungstor.txt`: Suite 16 640 bestanden, 3 rot — alle aus parallelen
Arbeiten (neue Texte ohne Katalog, `repair(progress=…)`, der
Bausteinnachweis nach einer fremden Änderung an `geom/intersections.py`);
Ruff, Format und mypy Exit 0. mypy für die CI-Werkzeuge zusätzlich mit
`--platform linux` und `--platform darwin` Exit 0.
