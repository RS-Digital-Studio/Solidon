# Review RM-620 (F:\sl-mischtemp, Zweig slicer/mischtemperatur)

Umfang: `git -C F:/sl-mischtemp diff` vollständig (14 Dateien, +85), Basis HEAD = origin/main 204025590, keine unversionierten Dateien, alles gehört zu RM-620. Mitgelesen: Fehlerzweig von `slice_model`, `errors.py`, Fehlerhandlungen von Druckdialog und Hauptfenster, `arrange_bed`, Regeln auslieferung/uebersetzung/kern/druckerwahl/zwillinge/dateiformat, Quelltext der fünf Orca-Abkömmlinge über `gh api`.

Ausgeführt (nur gezielt, keine Suite): die vier Orca-Absage-Tests in `test_print_settings.py` (4 grün), `test_changelog.py` + `test_translations.py` (275 grün, 1 übersprungen), `test_roadmap.py` (18 grün), `test_errors.py` + `test_slicer_failure_actions.py` (411 grün), dazu die Sonde `scratchpad/rm620_probe.py` (Ausgabe `rm620_probe_out.txt`).

## Mittel

### M1 — „Druckeinstellungen öffnen“ öffnet einen zweiten Druckdialog und führt nicht zu den Filamenten; der Knopf für „getrennte Platten“ fehlt

`app/core/export/handover.py:6733-6738`, `suggestions=(OPEN_PRINT_SETTINGS, CHOOSE_SLICER, EXPORT_ONLY, SHOW_SLICER_OUTPUT)`.

- Der Fehler erscheint nur im offenen Druckdialog: einziger UI-Aufrufer von `slice_model` ist `app/ui/print_settings_dialog.py:1836`, gezeigt über `show_error(problem, self)` in `:9056`.
- Ohne `constraint` reicht der Dialog `open_print_settings` an das Hauptfenster weiter (`print_settings_dialog.py:4624-4635`, `:4649-4658`). Dort `main_window.py:25598` → `action_print_settings` baut und startet einen **zweiten** `PrintSettingsDialog` (`main_window.py:9042`, `:9062`) über dem ersten. Was der Kunde dort ändert, schreibt `:9075-9076` ins Projekt, und der darunterliegende Dialog überschreibt es danach wieder. Die Suite kennt die Falle: `tests/test_slicer_failure_actions.py:378` heißt „…never_opens_nested_dialog“, `:398` zeigt, dass ein Fehler ohne `constraint` beim Elternhandler landet.
- Filamente werden im Druckdialog gar nicht gewählt: `print_settings_dialog.py:3047-3052` („Das Material wird hier nicht mehr gewählt, sondern berichtet“), gewählt wird im Filamentwähler links (`material_link` → `filamentsRequested`, `:3059-3064`; `main_window.py:8560-8580`).
- Weil `OPEN_PRINT_SETTINGS` kein `primary` trägt (`errors.py:169`), führt `CHOOSE_SLICER` (`errors.py:283`, `style.leading_action`, `style.py:820-828`). Der halbfette Hauptknopf nennt damit einen Weg, den der Satz nicht nennt.
- Sonde: `angeboten: ['open_print_settings', 'choose_slicer', 'export_only', 'show_output']`, `Hauptknopf: choose_slicer`, Klick auf *Druckeinstellungen öffnen* im Druckdialog → `Hauptfenster.action_print_settings`.

Die bessere Handlung gibt es schon. `ARRANGE_ON_BED` (`errors.py:242`, primary) startet `arrange_bed`, dessen `by_material` („Nach Filament trennen“) als Vorgabe an ist (`app/core/geom/prepare_ops.py:21179-21187`, `BY_MATERIAL_DOC` `:20706-20710`: „Legt Teile aus verschiedenen Filamenten auf verschiedene Platten“). Sobald der Drucker weniger Düsen hat als Filamentgruppen, trennt es (`app/core/geom/prepare.py:3474-3485`, `app/core/export/writer.py:858-872`; Test `tests/test_prepare.py:1850`). Der Knopf ist im Hauptfenster (`main_window.py:25521`, `_arrange_after_error` `:26363-26402`, nur `spacing` wird vorbelegt, `by_material` bleibt an) und im Druckdialog (`after_dialog`, `print_settings_dialog.py:4598-4623`) verdrahtet. Der Zwilling `ORCA_PATHS_CROSS` bietet ihn genauso an. Ein einzelnes Teil, das beide Filamente trägt, bleibt zusammen. Dann meldet die Op „es war nichts zu verschieben“, und Strg+Z nimmt den Schritt zurück.

Fix: `suggestions=(replace(ARRANGE_ON_BED, label=_("Nach Filament auf Platten verteilen")), CHOOSE_SLICER, EXPORT_ONLY, SHOW_SLICER_OUTPUT)`, mit der neuen Beschriftung in fünf Katalogen (oder unverändert `ARRANGE_ON_BED`). `OPEN_PRINT_SETTINGS` fällt weg. Für „andere Filamente“ wahlweise eine eigene Handlung (`choose_filaments`), im Dialog an `filamentsRequested.emit()` und im Hauptfenster an `_focus_filaments` gehängt; sonst bleibt es Satz. Im Test die führende Handlung (`arrange_on_bed`) prüfen und `open_print_settings` ausschließen.

### M2 — Unter Linux und macOS greift die neue Erkennung nie (gilt auch für die zwei Zwillinge)

`handover.py:6718-6721` mit `signed_exit_code` `:7720-7722`.

Die Orca-Abkömmlinge enden unter POSIX mit `int main(...) { return CLI().run(argc, argv); }` (AnycubicSlicerNext `src/OrcaSlicer.cpp`, Zweig ohne `_MSC_VER`). −62 kommt dort deshalb als Exit-Status 194 an. `signed_exit_code(194) == 194`, und die Sonde liefert für 194 „Der Slicer hat keine Druckdatei geschrieben.“ Ebenso −50 → 206 und −101 → 155. Anycubic Slicer Next läuft laut `app/core/export/slicer_keys.py:997-1000` auf allen drei Plattformen. Der Changelog-Punkt stimmt damit nur unter Windows. `dateiformat.md` („Ein Absturz ist keine Absage“) trennt POSIX und Windows für den Absturz schon, für die Absagen fehlt diese Trennung.

Fix für alle drei Zwillinge zusammen (`zwillinge.md`, auch Ursache 4 „Name statt Eigenschaft“, vgl. Kommentar `handover.py:6598-6604` „es entsteht, wenn die zweite dazukommt“): ein Prädikat wie `orca_refused(exit_code, code) -> bool: return exit_code in {code, code & 0xFFFFFFFF, code & 0xFF}`. Das braucht kein `sys.platform`. Die drei Abfragen laufen darüber. Die Tests (neu und Zwillinge) werden über `returncode ∈ {4294967234, 194}` usw. parametrisiert.

## Niedrig

### N1 — Regel 21: Der Satz behauptet eine Ursache, die −62 nicht eindeutig trägt

Ab OrcaSlicer 2.4.2 (veröffentlicht, hier installiert) heißt −62 auch „Invalid recommended nozzle temperature range“. Belege: `Print.cpp@v2.4.2` 1152, 1199-1201, 1242-1244 → `ret.type = STRING_EXCEPT_FILAMENTS_DIFFERENT_TEMP` 1277 → `OrcaSlicer.cpp@v2.4.2` 6077-6078. Außerdem urteilt hier nur der eine Slicer: Vier andere rechneten dieselbe Platte, und Anycubics eigene `resources/info/filament_info.json` führt PETG sogar als `high_low_compatible`. „Die Filamente … brauchen zu verschiedene Temperaturen“ klingt deshalb nach einer Eigenschaft des Materials. Beim Zwilling `ORCA_PATHS_CROSS` steht die Regel: „der Satz nennt beide“.

Fix etwa: „Der Slicer druckt die Filamente dieser Platte nicht zusammen, weil ihre Temperaturbereiche in seinen Profilen nicht zueinander passen. Legen Sie die Teile auf getrennte Platten, wählen Sie andere Filamente oder einen anderen Slicer.“ Fünf Kataloge neu übersetzen und an der Konstante beide Bedeutungen nennen.

### N2 — Ein aussichtsloser zweiter Slicerlauf

`handover.py:6605-6632`. Im Normalfall (`keep = arrangement_holds(...)`, `print_settings_dialog.py:1313`) startet bei −62 ein zweiter vollständiger Lauf ohne `--arrange 0`. Die Temperaturprüfung in `Print::validate` hängt nicht von der Lage ab, der Kunde wartet also zweimal auf dieselbe Absage. Fix: den Rückfall auslassen, wenn der erste Lauf mit `ORCA_MIXED_TEMPERATURES` endete (über das Prädikat aus M2). Test: `_run_slicer` läuft mit `keep_arrangement=True` genau einmal.

### N3 — Changelog-Übersetzungen

- `changelog/es.md:58`: „el motivo y la salida“.
- `changelog/pt.md:57`: „o motivo e a saída“.

Beide kollidieren mit den Knöpfen „Ver la salida del slicer“ und „Ver a saída do slicer“ (Katalog „Ausgabe des Slicers ansehen“) und lesen sich als „Grund und Slicer-Ausgabe“. Besser „qué hacer“ bzw. „o que fazer“. `changelog/en.md:57`: „filaments with too different temperatures“ ist holprig; der Katalog sagt schon „temperatures that are too far apart“. Längen sind in Ordnung (172 bis 189 Zeichen).

### N4 — Archiveintrag

`ROADMAP-ARCHIV.md:44095-44112`. Der Nachweis hat kein Datum und nennt weder Tor noch Durchsicht noch „Changelog: ja“ (vgl. RM-602 und RM-582). „Behoben“ zählt die Handlungen von M1 auf und nennt „in der Orca-Familie“ ohne die Plattformgrenze aus M2. Nach den Fixes nachziehen.

## Geprüft ohne Befund

- Regel 20: neuer Text über `_()`, in allen fünf Katalogen an sortierter Stelle.
- Regel 17: Vorschläge vorhanden (Qualität siehe M1).
- Regeln 1, 6, 7, 22: nicht berührt bzw. eingehalten.
- Nur die Orca-Familie: `setup.flavour == "orca"`. Die Abbildung steht in `slicer_keys.FLAVOUR_BY_NAME`: OrcaSlicer, Bambu Studio, ElegooSlicer, Creality Print, Anycubic Slicer Next. Alle fünf Quellbäume definieren `CLI_FILAMENTS_DIFFERENT_TEMP -62` in `src/libslic3r/Utils.hpp`. Prusa und Cura sind ausgeschlossen.
- `crashed(4294967234)` ist False, die Reihenfolge der Abfragen stimmt.
- Glossare (pieza/pièce/pezzo/peça, placa/plateau/piatto/placa), gerade Apostrophe.
- Changelog: offener Abschnitt `## 0.6.0` (kein Tag v0.6.0), allgemein formuliert, Ursache in v0.5.3 (`git tag --contains b79f8a07e`).
- Archivform: Index und Anker wie bei den Nachbarn, `test_roadmap` grün. RM-620 steht nicht im Register und ist sonst nirgends vergeben.

## Urteil

Nein. Erst M1 und M2 beheben, N1 bis N4 gleich mit. Danach ist der Stand landungsreif.
