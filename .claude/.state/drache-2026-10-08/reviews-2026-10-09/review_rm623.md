# Review RM-623 (`F:/sl-grundlage`, Zweig `slicer/fenstergrundlage`, ungesichert gegen `372d6fbd9`) — solidon3d-review, 09.10.2026

Umfang: `git -C F:/sl-grundlage diff` vollständig (11 Dateien, +197/−10, keine unversionierten
Dateien im Worktree): `handover.standard_choice`, `remembered_setup`, zwei neue Tests in
`test_manufacturer.py`, ein neuer und ein geänderter in `test_ui_export.py`, Changelog in sechs
Sprachen, Archiveintrag. Dazu gelesen: die Vorwahl des Druckdialogs (`_take_profiles`,
`_slicer_machine_for_project`, `_fill_processes`, `_fill_filaments`, `_refresh_bed_plate_context`,
`_nozzle_changed`, `_remember_slicer_choice`, `_ProfileWorker`), `machine_for`, `_fits_the_printer`,
die benutzten Funktionen in `slicer_profiles.py` (`find_profiles`, `match`, `machine_with_nozzle`,
`_of_kind`, `match_filament`, `_chain`, `single_read`), beide Aufrufer in `main_window.py` samt
Grundlagenschlüssel, Ablösung und Schließen, `writer._plate_settings`, `test_real_slicers._preselected`,
`tools/matrix_unit.prepared`, die Bestandstests um `remembered_setup` in `test_print_settings_ui.py`;
Regeln kern, dateiformat, druckerwahl, oberflaeche, fenster, wartezeit, zwillinge, tests,
auslieferung, uebersetzung; Bauplan §29.

Ausgeführt, alles nur lesend:
- Zwei Sonden im Scratchpad (`probe_rm623.py`, `probe_rm623_cpu.py`) gegen Roberts
  ElegooSlicer-Bestand: `standard_choice` gemessen, `find_profiles` gezählt. Die Maschine stand dabei
  bei 100 % CPU (drei Tore parallel). Die Wandzeiten (40–78 s je Aufruf) sagen deshalb nichts; die
  CPU-Zeiten unten sind eine Obergrenze.
- Roberts `settings.json` gelesen (nur die Slicerfelder).
- Gezielte Tests aus `F:/sl-grundlage`: die fünf neuen und geänderten Fälle (5 passed, Exit 0) und die
  Bestandstests um `remembered_setup` in `test_print_settings_ui.py` (21 passed, Exit 0).
- `git fetch -q origin` (nur Remote-Refs): Der Zweig liegt 13 Commits hinter main; in den berührten
  Dateien hat main nur eine Changelog-Zeile in einem anderen Abschnitt, kein Konflikt zu erwarten.

Nichts geändert, nichts committet.

**Ergebnis: 0 schwer, 4 mittel, 4 leicht.** Roberts Fall ist gelöst — die Sonde bestätigt für
`centauri-carbon-2` „Elegoo Centauri Carbon 2 0.4 nozzle“, „0.20mm Standard @Elegoo CC2 0.4 nozzle“
und „Elegoo PLA @ECC2“ (PETG: „Elegoo PETG @ECC2“).

## Mittel

### M1 Jede Grundlage und jeder 3MF-Export ohne gemerkte Wahl liest den ganzen Bestand — die Maschinen zweimal, je Stufe neu, ohne Abbruch

Stellen: `app/core/export/handover.py:521–524`; `handover.py:451–453` → `slicer_profiles.py:2096–2102`;
`app/ui/print_settings_dialog.py:415–432`; Aufrufer `app/ui/main_window.py:1320–1329`, `:1651–1655`,
`:24283–24311`, `:27597–27601`, `:27831–27837`.

Beleg:
- `standard_choice` liest vor jeder Prüfung `find_profiles(…, ("machine", "process", "filament"))`,
  auch dort, wo am Ende `None` steht (Vorgabedrucker `generic-220`, Resin, ein Drucker, den der Bestand
  nicht kennt). Im Export folgt dann noch `tools.slicer_program()` (`main_window.py:1652–1655`).
  Vorher endete `remembered_setup` ohne gemerkte Maschine sofort.
- `machine_for(replace(setup, machine_profile=""), …)` reicht `machine_with_nozzle` kein `available`,
  das liest die Maschinen ein zweites Mal (`slicer_profiles.py:2099`). Sonde: CC2-Projekt zwei
  `find_profiles`-Aufrufe, MK4S-Projekt einer.
- Gemessen an Roberts ElegooSlicer (CC2/PLA, CPU unter Volllast): `standard_choice` 7,6 s CPU, davon
  `find_profiles` aller drei Arten 5,8 s, der zweite Maschinenlauf 1,0 s, die Zuordnung danach 0,8 s.
  In `single_read()` 5,9 s (4,6 / 0,9 / 0,5). Kalt wird es mehr: `filament_picker.slicer_filaments`
  misst am selben Bestand für Programmsuche und Filamentprofile 26,6 s beim ersten und 4,3 s bei jedem
  weiteren Mal (`filament_picker.py:571–574`).
- Bezahlt wird das je 3MF-Export (`_assembly`) und je Wechsel des Grundlagenschlüssels. Der enthält die
  Stufe (`main_window.py:24289`), obwohl `standard_choice` nicht an ihr hängt. Abgelöste
  Grundlagenarbeiter laufen ohne Abbruch zu Ende (`_retire`, `:24307`), schnelle Wechsel stapeln volle
  Lesedurchgänge. Schließen wartet auf sie („Solidon beendet die laufende Aufgabe …“, `:27597–27601`,
  `:27831–27837`); der Abbruch des Exports greift erst in `write_assembly`.
- Kundensicht: Wer im Druckdialog noch keine Maschine gemerkt hat — Robert heute eingeschlossen —,
  wartet bei jedem 3MF-Export Sekunden länger. Nach jedem Material- oder Stufenwechsel springt die
  Zahlenzeile erst Sekunden später von Solidons Tabelle auf den Hersteller und stößt eine zweite
  Auswertung an (`main_window.py:24331–24337`).

Warum es zählt: `druckerwahl.md:80` „Ein Lesedurchgang je Antwort“; `wartezeit.md:163` „Die
Exportvorbereitung ist abbrechbar … Arbeiter ohne Abbruch begründen die Grenze im Docstring“.

Fix, mit Messung vorher und nachher an der Sonde:
1. `machine_for` um `available` erweitern und im Zweig ohne Maschine an `machine_with_nozzle` reichen;
   `standard_choice` gibt `found` mit. Der zweite Lauf entfällt.
2. Erst nur die Maschinen lesen (gemessen rund 1 s CPU statt 5–6 s), darauf `machine_for` und `match`;
   Prozesse und Filamente nur lesen, wenn eine Maschine feststeht. Was der Bestand nicht kennt, endet
   dann nach einem Bruchteil.
3. Die Folgefragen in `slicer_profiles.single_read()`.
4. Nicht je Stufe: Im Hauptfenster das Setup aus `remembered_setup` je Schlüssel ohne Stufe merken und
   dem Grundlagenarbeiter mitgeben; `for_stage` bleibt je Stufe. Dasselbe Setup kann der Export
   bekommen, statt es neu herzuleiten — dann rechnen Zahlenzeile und Datei sicher mit derselben Wahl.
5. Ein `CancelToken` bis in die Schritte von `standard_choice`; der Export reicht `self.cancelled`, der
   Grundlagenarbeiter wird beim Ablösen und Schließen abgesagt. Sonst die Grenze in den Docstrings von
   `_FoundationWorker` und `_assembly` begründen.

### M2 Vierte Herleitung derselben Vorwahl — mit dem Dialog schon auseinandergelaufen, ohne Wächter

Stellen: `handover.py:511–516` („Dieselbe Reihenfolge wie der Dialog“) und `:549` („derselbe Rückfall
wie im Dialog“) gegen `print_settings_dialog.py:4816–4820`, `:5084–5131`, `:5185–5209`, `:5408–5416`,
`:5691–5731`; dazu `tests/test_real_slicers.py:48–77` (`_preselected`) und `tools/matrix_unit.py:346–388`
(`prepared`), beide „wie der Druckdialog sie vorwählt“.

Abweichungen, am Code:
- **Platte:** Der Dialog nimmt `slicer_bed_plate`, sobald Drucker und Slicer passen, auch bei leerer
  Maschine (`_refresh_bed_plate_context`, `:4816–4820`). Der neue Zweig von `remembered_setup` gibt
  `plate=""`, also die Standardplatte. Eine andere Platte heißt ein anderer Temperaturschlüssel
  (Fixture: `hot_plate_temp` 55, `textured_plate_temp` 60).
- **Filament:** Der Dialog nimmt das gemerkte Filament je Material, wenn es zur Maschine passt
  (`:5693–5705`); `standard_choice` nimmt immer die Grundausführung der Materialart. Ein gemerktes
  „PETG PRO“ wird im Export zum schlichten PETG, und laut `match_filament` fährt PRO 240 °C bei halbem
  Volumenstrom (`slicer_profiles.py:4046–4048`).
- **Prozess:** Der Dialog nimmt einen gemerkten passenden Prozess und fällt zuletzt auf den ersten der
  Liste (`max(index, 0)`, `:5416`), `standard_choice` auf keinen (`:565`).
- **Düse:** Steht der Slicer auf derselben Maschine mit anderer Düse, übernimmt der Dialog dessen Düse
  in den Drucker (`:5117–5120` → `_nozzle_changed`); `standard_choice` behält die Düse des Projekts und
  nimmt die Schwestervariante (`machine_for` → `machine_with_nozzle`). Für den Export richtig, aber
  nirgends als Entscheidung benannt.
- Erreichbar ist „Maschine leer, Rest gemerkt“ im Feld: `_nozzle_changed` leert nur die Maschine
  (`:3568–3574`). Roberts `settings.json` steht so (Maschine und Prozess leer, Filament
  `…\Elegoo PLA @0.2 nozzle.json` für PLA, Platte leer). Bei ihm passt das 0,2er-Filament nicht zur
  0,4er Maschine, deshalb trifft es seinen Fall nicht.
- `_preselected` und `prepared` kennen weder die eingestellte Maschine des Slicers noch die einzige
  Maschine noch den Typrückfall.

Warum es zählt: `zwillinge.md` (Regel; „Woher sie kommen“ 3: „Ein Kommentar ‚dieselbe wie …‘ ist kein
Teilen“). Changelog und Archiv versprechen „was der Druckdialog … vorschlägt“.

Fix: `standard_choice` nimmt gemerkten Prozess, gemerktes Filament und gemerkte Platte als Vorzug — sie
gelten, wenn sie zur gewählten Maschine passen, wie im Dialog —, und `remembered_setup` reicht sie, wenn
`_remembered_profiles_match` gilt. Düse und „kein Prozess statt des ersten“ als entschiedene Abweichung in
den Docstring. `_preselected` und `prepared` rufen `standard_choice` (siehe M4). Für den Dialog die
Vorwahl aus derselben Funktion oder ein Test, der `_take_profiles` und `standard_choice` auf demselben
Bestand mit je zwei Maschinen, Prozessen und Filamenten vergleicht; geht beides nicht in diesem Schritt,
ein Registerpunkt in `ROADMAP.md`.

### M3 Der neue Kerntest unterscheidet keine der Regeln, die er nennt

Stellen: `tests/test_manufacturer.py:591–609`, Fixture `bestand` `:488–573`.

Beleg: Die Fixture hat genau eine wählbare Maschine, einen Prozess und ein Filament (die `…_common`
sind Erbbasen; der MK4S-Test stützt sich genau darauf). Zugeordnete Maschine, eingestellte Maschine und
„die einzige“ ergeben dieselbe Datei, ebenso Standardprozess und erster Prozess, Materialart und erstes
Filament. Die Zusicherung `speed.outer_wall == 160.0` mit der Meldung „die Grundlage ist Elegoos
Prozess, nicht Solidons Tabelle“ trifft auch die Tabelle: `print_settings.resolve(cc2, "standard")` und
`manufacturer.base_settings(cc2, "standard", None)` geben 160,0 (gemessen). Ungeprüft bleiben die
eingestellte Maschine (`current`), der Prozess außerhalb der passenden (`handover.py:541–544`), der
Typrückfall (`:548–561`), ein Material ohne Profil und PrusaSlicer.

Warum: `tests.md:389` „Zwei Felder mit gleichem Wert machen jeden Test grün, der nur eines liest“;
„Ein Sollwert trägt seine Herkunft“.

Fix: eine Fixture-Variante mit einer zweiten Maschine (CC2 0.2 oder ein anderer Drucker), einem zweiten
Prozess, der im Alphabet vor „0.20mm Standard“ steht („0.12mm Fine @CC2“), und „Elegoo PETG @ECC2“
(vor PLA) — jede falsche Regel träfe eine andere Datei. Statt `outer_wall` zusichern:
`foundation.settings.shell.wall_count == 2` (Fixture `wall_loops` 2, Tabelle 3, gemessen) oder
`foundation.has_profile`. Dazu je ein Fall: eingestellte Maschine (`slicer_profiles.chosen_machine`
gepatcht wie in `test_real_slicers.py:176`), Material ohne Profil → `base_filament == ""`, ein
PrusaSlicer-Bündel.

### M4 Kein Slicertest mit echtem Programm für die neue Wahl

Stellen: der Diff bringt keinen `@pytest.mark.slicer`-Fall; `tests/test_real_slicers.py:48–77`.

Beleg: Die Slicerauswahl wählt `test_real_slicers.py`, weil sich `handover.py` ändert — dort ruft aber
nichts `standard_choice`, `_preselected` leitet die Wahl selbst her (M2). Unter Linux (AppImage: Bestand
aus `system/`; Flatpak: aus dem Sandkasten) und auf beiden Macs läuft die neue Funktion damit nirgends.
Der Nachweis im Archiv ist eine Sonde an Roberts ElegooSlicer unter Windows.

Warum: `tests.md:30` „Neues bringt seinen Test für diese Auswahl mit … eine Änderung an
Slicerübergabe, Profilen, Druckerwahl … ihren Slicertest mit echtem Programm“ (Entscheidung Robert).

Fix: `_preselected` auf `standard_choice` umstellen, mit Zusicherung „nicht `None`“ und „Maschine gehört
dem Drucker“. Dann fahren alle sieben Programme aus `PROGRAMS` die Wahl auf Linux und beiden Macs; vor
dem Merge `slicer-auswahl.yml` auf dem Zweig.

## Leicht

### L1 Fehler nach dem Lesen des Bestands sind nicht gefangen — der Export kann an einem fremden Profil scheitern

Stellen: `handover.py:520–527` (gefangen nur `find_profiles` und `machine_for`) gegen `:528–561`;
`slicer_profiles.py:3749–3757`.

Beleg: `match`, `processes`, `match_filament`, `filaments` und `type_of` lösen Erbketten auf, und `_chain`
wirft `ExternalToolError` bei einem fehlenden oder fehlerhaften `include` auch ohne `strict`. Bambu
Studio führt 1529 Profile mit `include` (gezählt in `C:\Program Files\Bambu Studio\resources\profiles`).
Im Export landet das über `_ExportWorker.work` in `failed` (`main_window.py:1596–1598`): Die 3MF
scheitert an einem Profil, das niemand gewählt hat — bei `match_filament` genügt eines der passenden
Filamente. Vorher las dieser Weg den Bestand gar nicht. Im Grundlagenarbeiter wird es `crashed`.

Warum: Der Bestand ist eine Zugabe (Dialog, `_profiles_failed`); `filament_picker.slicer_filaments`
fängt aus genau diesem Grund breit („ein fremder Bestand scheitert auf viele Arten“,
`filament_picker.py:579–584`).

Fix: die ganze Wahl in den `try`, `AppError` und `OSError` fangen, Warnung ins Protokoll, `None`. Dazu
eine Testdatei mit einem passenden Profil, dessen `include` fehlt.

### L2 Die einzige, unbekannte Maschine gilt für jeden Drucker

Stellen: `handover.py:533–539` mit `_fits_the_printer` (`:467–471`, `:496–499`: „Nicht erkannt heißt ja“)
gegen den Docstring `:515–516`.

Beleg: Besteht der Bestand aus einer einzigen eigenen Maschine („Mein Drucker“), bekommen auch ein
MK4S-Projekt und ein Resin-Projekt sie samt Prozess, ohne dass jemand sie sieht; der Dialog zeigt sie
wenigstens. Der Docstring verspricht `None`, „wo der Bestand den Drucker nicht kennt“, §29 nennt für
diesen Fall Solidons Tabellen. Selten — nur ein Bestand mit genau einer wählbaren Maschine, etwa ein
AppImage mit nur einem eigenen Drucker —, aber ungeprüft.

Warum: Regel 21; Bauplan §29 („Ohne Herstellerprofil — … ein Drucker, den sein Bestand nicht kennt …“).

Fix: auf die einzige Maschine nur zurückfallen, wenn sie diesem Drucker zugeordnet ist
(`printer_for(…, prefer=mine) == mine`), oder die Entscheidung im Docstring benennen. In beiden Fällen
ein Test mit einer unbekannten einzigen Maschine.

### L3 Drei Bestandstests sind jetzt aus einem anderen Grund grün

Stellen: `tests/test_print_settings_ui.py:4254` („anderer Drucker, nichts gilt“), `:4391` („anderer
Slicer, nichts gilt“), `:4324–4328` (die Fälle `valid=False` mit gefundenem Programm).

Beleg: Diese Fälle laufen jetzt durch das echte `standard_choice` mit `Path("elegoo-slicer.exe")` und
ergeben `None` nur, weil dieser Pfad keinen Bestand hat. Die Meldungen beschreiben den alten Vertrag;
mit einem Bestand würden sie rot, obwohl der Code dann richtig wäre. Gelaufen: grün.

Warum: `tests.md`, „Prüft dieser Test eine Zusage — oder den Ist-Zustand?“

Fix: wie im neuen Test `handover.standard_choice` durch einen Rekorder ersetzen und zusichern, dass er
mit dem Projektdrucker gefragt wird und die gemerkte Maschine nicht weiterreist; Meldungen auf den neuen
Vertrag.

### L4 Unterlagen ziehen nicht nach

Stellen: `main_window.py:1296–1298` („… die Auflösung der Profile ein Zehntel“), `:1647–1649` („sie
kostet eine knappe halbe Sekunde“); `.claude/rules/dateiformat.md:272–277` oder `druckerwahl.md`;
`app/core/export/CLAUDE.md:15`.

Beleg: Ohne gemerkte Wahl kostet `remembered_setup` jetzt den Bestand (M1). Die Entscheidung „ohne
gemerkte Wahl gilt die Vorwahl des Dialogs“ steht in keiner Regel, und die Karte nennt die neue
öffentliche Auskunft nicht — die nächste Sitzung baut sonst die fünfte Herleitung (M2).

Fix: beide Docstrings mit den Kosten, die nach M1 bleiben; eine Zeile in `dateiformat.md` unter „Auf dem
Herstellerprofil wird nur die Abweichung geschrieben“ oder in `druckerwahl.md`; `standard_choice` in die
Zeile von `handover.py` in der Karte.

## Geprüft ohne Befund

- **Hauptthread:** Beide Aufrufer laufen im Arbeiter — `_FoundationWorker.work`
  (`main_window.py:1320–1329`) und `_ExportWorker._assembly` aus `work` (`:1556–1598`, gestartet über
  `_leash.start`). Sonst ruft in `app/` niemand `remembered_setup` oder `standard_choice`; die übrigen
  Treffer sind Tests.
- **Fehlerwege `find_profiles` und `machine_for`:** gefangen (`ExternalToolError`, `OSError`), Warnung,
  `None` — der Export schreibt dann wie vorher. Der Rest steht in L1.
- **Regeln 1–22:** kein Qt im Kern; kein neuer Oberflächentext; keine neue Ausnahme; Kennungen als Pfade
  stehen nur im `SlicerSetup` des Laufs, wie die gemerkten aus `UiSettings`, und reisen in keine
  Projektdatei; keine neue Abhängigkeit; Bezeichner englisch, Docstrings deutsch mit Umlauten. Regel 21
  siehe L2.
- **Stufe:** Beide Aufrufer legen `manufacturer.for_stage` auf das Ergebnis (`main_window.py:1324–1328`,
  `:1660`); `base_process` ist der Standardprozess, wie `dateiformat.md:272` es verlangt.
- **Ohne mitgegebene Einstellungen und an Resin:** `writer._plate_settings` gibt bei `settings=None`
  nichts aus (`writer.py:2813–2814`); die neue Wahl schreibt kein Profil in eine Datei, die keines tragen
  soll.
- **Leere Mengen:** kein Bestand, keine Maschine, kein passender Prozess, kein Filament der Materialart
  ergeben `None` bzw. `""`.
- **Gegenprobe der neuen Tests, am Code:** `test_the_standard_choice_takes_no_machine_of_another_printer`
  wäre ohne `_fits_the_printer` rot (die einzige Maschine gehört dem CC2);
  `test_without_a_fitting_choice_the_export_takes_the_dialogs_choice` wäre mit dem alten
  `remembered_setup` in beiden Parametern rot.
- **Changelog:** sechs Sprachen, gleiche Gruppe und Stelle, 150–179 Zeichen (Grenze 200), Kundensprache;
  „gemerkt“ ist im Changelog eingeführt. Als Behebung zu Recht: Der Grundlagenarbeiter kam mit
  `aed31c787`, enthalten in v0.5.1 bis v0.5.3. Das Versprechen „was der Druckdialog vorschlägt“ hängt an
  M2.
- **Archiv:** Befund, Ursache und Nachweis passen zum Code; die Sonde bestätigt die genannte Wahl.

## Kundensicht

Vorher ging eine 3MF ohne gemerkte Profilwahl ohne Herstellerprozess hinaus, der Slicer füllte mit
seinen eigenen Vorgaben, und Zahlenzeile und Prüfbericht rechneten mit Solidons Tabelle. Jetzt trägt die
Datei Maschine, Prozess und Filament des Herstellers, und das Hauptfenster rechnet damit — ein klarer
Gewinn. Der Preis steht in M1: Sekunden Wartezeit je Export und je Material- oder Stufenwechsel, beim
Schließen ein Wartesatz. Wer eine Platte oder eine besondere Spule gewählt hatte und danach die Düse
wechselte, bekommt im Export etwas anderes als im Dialog (M2). Ein Weg hinaus besteht immer: Druckdialog
öffnen, wählen, schließen — danach gilt die gemerkte Wahl.

## Urteil

So nicht nach main: Erst M1 bis M4 beheben, L1 bis L4 im selben Zug, und das Behobene noch einmal
durchsehen lassen.
