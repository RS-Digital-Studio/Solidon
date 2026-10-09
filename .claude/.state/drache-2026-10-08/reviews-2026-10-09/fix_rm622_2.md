# Behebung Nachprüfung RM-622, zweite Runde (`F:/sl-turm`, auf `f597ffbd4`, nicht committet)

Alle Befunde aus `review_rm622_2.md` sind behoben, außer L5 (Begründung unten). Jede
Behebung hat einen Test. Die Gegenprobe lief als Mutation: Der Fix wurde im Code
zurückgenommen, der Test gefahren und der Stand wiederhergestellt
(`scratchpad/fix622/gegenprobe.py`). Alle zwölf Mutationen waren rot.

## Befunde

| Befund | Stand | Code | Test (Gegenprobe rot) |
|---|---|---|---|
| M1 Abgewählter Baum nimmt dem Gitter Abstand und untere Trennschicht | behoben | `advise.printed_style` und `DECIDING_PATHS` (`advise.py:963–980`), Kontakt mit ihr gefragt (`:1306`), neuer Parameter `declined` in `advise`/`for_part`/`_from_geometry`; Export: `declined` = Stützart nicht übernommen (`writer.py:1381`), Filter mit derselben Art (`:1419`); Dialog: `_AdviceWorker(declined=…)` (`print_settings_dialog.py:1443`, `:1582`, `:1588`), `_with_parts` ohne Abgewähltes (`:1734`), `_declined_advice` im Auftrag (`:7931`), Abwahl der Stützart fragt neu (`:8237`, `QTimer.singleShot`, weil der Neuaufbau die sendende Zeile löscht) | Export `test_print_settings.py:9424` (Sonde 8: Kinn bekommt 0,28 und 2); Arbeiter `test_print_settings_ui.py:11410`; Abwahl fragt neu und gehört zum Auftrag `:11462` |
| M2 Dialog fragt jeden Körper mit dem übernommenen Stil | behoben | `asked_for_contact` setzt auch `support.style` auf die Grundlage, wo sie je Teil geht (`handover.py:1469–1505`), Docstring | `test_print_settings_ui.py:11428` (Sonde 7 zweistufig: Zeilen 0,28 und 2 bleiben für den Tisch, Datei trägt sie) |
| M3 „organischer Baum?“ zweimal hergeleitet | behoben | `slicer_keys.limitation(…, organic)` fragt nur `style in organic` (`slicer_keys.py:1623`, `:1678`); der Dialog gibt die Menge des letzten Arbeiters (`_organic`, gesetzt in `_advice_ready` `:8084`, gelesen `:6553`); ohne Slicer entschieden: die Familie, `organic_styles(None, flavour=…)` gibt `{"tree"}` für Orca und Prusa (`handover.py:3149–3183`), Docstring entsprechend; Export und Arbeiter geben `flavour` mit | `test_print_settings.py:9486` (tree_hybrid, tree_slim, Elegoo „automatisch“, Orca-Kontrolle, ohne Slicer: Rat und Feld gleich), `:9281` (ohne Programm), `:9575` (angepasst, Menge aus `organic_styles`), Dialogfeld `test_print_settings_ui.py:11488` |
| L1 Schalter unter Bäumen still gegen den Hersteller | behoben | `handover.support_gaps_by_style` trennt die geschriebenen Abstände je Teil nach der Art, mit der es druckt (`handover.py:3051`); der Schalter fragt nur die außerhalb organischer Bäume (`writer.py:2802–2808`), ebenso der Konsolenweg ohne Beilage (`handover.py:6842`); `writer._gaps_between_layers` entfällt | `test_print_settings.py:9291` (Beilage ohne Schalter), `:9335` (Schalter nur unter Gitter), `:9403` (Teilung) |
| L2 PrusaSlicer nennt die Rundung unter Bäumen nicht | behoben | Rundungssatz hängt nicht mehr am Schalter (`writer.py:2829`); Docstring `has_independent_support_layers` (`slicer_keys.py:1600`) | `test_print_settings.py:9373` |
| L3 Leere Zusicherung | behoben | Attrappe führt `independent_support_layer_height: "0"`, Beilage zugesichert | `test_print_settings.py:9291` (rot unter der L1-Mutation) |
| L4 Prusa-Zweig von `organic_styles` ungeprüft | behoben | – | `test_print_settings.py:9256` (organic → tree und auto, snug, ohne Kette, `ExternalToolError`) |
| L5 Slicertest mit echtem Programm | nicht behoben | – | Begründung unten |
| L6 RM-622 weder im Register noch im Archiv | behoben | Archiv `ROADMAP-ARCHIV.md`: Verzeichniszeile oben und Abschnitt nach RM-582 mit Befund, Behebung und Nachweis; **Tor-Zahl als Platzhalter `TOR-ZAHL`**. Im Register von `ROADMAP.md` stand RM-622 nicht, dort war nichts zu streichen | `test_roadmap.py` grün |
| L7 Changelog verspricht die untere Trennschicht überall | behoben | Zweiter Satz in allen sechs `changelog/*.md` unter `## 0.6.0`, z. B. „Unter Baumstützen nur bei Slicern, die sie dort drucken.“; fr gekürzt auf 194 Zeichen (Grenze 200) | `test_changelog.py` grün |
| L8 Unterlagen ungenau | behoben | `regel-druckrat.md`: „innerhalb der Materialgrenzen“ statt „im Band“ (Turm und Cura); untere Trennschicht nennt die richtigen Programme; Absatz zum Schalter getrennt und berichtigt; neue Sätze zu abgelehnter Stützart, Dialog gegen Grundlage, ohne Programm, eine Auskunft für Feld und Rat. `advise.support_gap_target`: Turm `SupportMaterial.cpp`, Bäume organischer Generator (Orca `TreeSupport3D.cpp`), PrusaSlicer genannt | – |

**Nebenbei behoben:** Durch diesen Zweig importierten drei Testdateien Körper aus
`test_slice_findings.py`. `on_bed`, `brick`, `chin`, `chin_over_chest` und `column_table`
(vorher `table`) liegen jetzt in `tests/helpers.py`. Im Test von
`test_without_a_slicer_the_dialog_advises_for_its_actual_export` fehlte der Attrappe
`_declined_advice`; ergänzt.

**Regeln:** `druckrat.md` (Stützkontakt: `printed_style`/`declined`, Stützart gegen die
Grundlage, ohne Programm die Familie) und `dateiformat.md` (Schalter außer unter
organischen Bäumen). Das Budget von `dateiformat.md` war bis auf 5 Byte voll, deshalb sind
zwei Nachbarsätze gestrafft, ohne Inhalt zu verlieren. Neuer Stand: 30 710 Byte, druckrat
9 324 Byte. Eine Ergänzung in `app/core/export/CLAUDE.md` riss das Kartenbudget von 25 KB
und wurde zurückgenommen.

**Keine neuen Oberflächentexte.**

## L5: warum ohne Slicertest

Der vorhandene Slicertest (`test_real_slicers.py::test_a_cube_comes_back_…`) prüft nur, ob
ein Würfel mit Druckbewegungen zurückkommt. Für die Rundung unter Bäumen und die untere
Trennschicht müsste man die Kontaktebenen im G-Code je Programm finden: Merkmalsarten je
Programm, Lagen je Höhe auf dem Raster, Übergangslage bei Bambu. Diese Messung steht in
`.claude/.state/drache-2026-10-08/kontakt_je_teil.py` (420 Zeilen) und müsste als Testhilfe
nach `tests/` umziehen. Dazu kämen zwei Körper unter Baum und Gitter und Fälle für sechs
Programme in drei CI-Umgebungen. Mit wenig Aufwand deckt das kein bestehender Test ab.
Vorschlag: eine Registerzeile in `ROADMAP.md`, also ein Slicertest für Kontaktabstand und
untere Trennschicht unter Baum und Gitter, gegen ein Programmupdate.

## Sonden des Reviewers nach dem Fix

Sonde 7: Nach Übernahme nur der Stützart bleiben `z_gap 0,28 · Tisch` und `untere 2 · Tisch`
stehen, die Datei gibt dem Tisch 0,28 und 2. Sonde 8: Im Export bekommt das Kinn 0,28, 0,28
und 2. Sonde 4: Die Beilage ist ohne Schalter, Befund `export.support_gap_rounded`. Sonde 5
(Prusa): `export.support_gap_rounded` ist da. Sonde 2: Ohne Slicer gilt organisch `{"tree"}`
und der Rat 0,2. Die Feldaufrufe der Sonden 2, 3 und 5 nutzen die alte Signatur ohne
`organic`; die neuen Tests decken sie ab. Ausgabe: `scratchpad/fix622/sonden_nach.txt`.

## Prüfläufe (aus `F:/sl-turm`)

- ruff check über die neun geänderten Python-Dateien: Exit 0.
- ruff format --check: Exit 0, auch die Markdown-Dateien.
- mypy über die fünf geänderten App-Dateien: Exit 0. Laut Konfiguration prüft mypy nur `app`.
- `tools/affected_tests.py` meldet „439 von 444 Testdateien — das ist die Suite“, weil
  `tests/helpers.py`, `advise.py` und `handover.py` berührt sind. Mit `--run` wäre das das
  ganze Tor, also **nicht gefahren**. Gefahren habe ich stattdessen ohne Fenster, Renderer
  und Leistung, mit `-n 4`, 17 Dateien: `test_slice_findings`, `test_print_settings`,
  `test_export`, `test_slicer_part_settings`, `test_calibration`, `test_print_time`,
  `test_manufacturer`, `test_cache`, `test_directory_docs`, `test_roadmap`,
  `test_changelog`, `test_changelog_website`, `test_twin_scan`, `test_source_escapes`,
  `test_language_rules`, `test_rm484_raft_ui`, `test_print_settings_ui`. Ergebnis: Exit 1
  mit 4 Fehlern bei 2 485 bestanden und 8 übersprungen. Die vier Fehler (Attrappe ohne
  `_declined_advice`, Kartenbudget, fr-Changelog zu lang) sind behoben, die vier Tests
  danach grün: Exit 0, 52 bestanden.
- Gezielte Fenstertests in `test_print_settings_ui.py` zu RM-583, RM-622 und den neuen
  Fällen: Exit 0, 16 bestanden.
- Gegenproben: zwölf Mutationen, alle rot.
- Tor-Zahl für das Archiv: noch offen, im Text steht der Platzhalter `TOR-ZAHL`.
