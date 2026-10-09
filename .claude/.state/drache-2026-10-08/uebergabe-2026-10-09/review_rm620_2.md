# Nachprüfung RM-620 (F:\sl-mischtemp, Zweig slicer/mischtemperatur), zweite Runde

Umfang: `git -C F:/sl-mischtemp diff` vollständig (14 Dateien, +119/−12). Basis HEAD = origin/main 204025590, keine unversionierten Dateien. Maßstab ist der erste Bericht `review_rm620.md`.

Ausgeführt habe ich nur gezielte Läufe, keine Suite:
- `test_text_length`, `test_translations`, `test_changelog`, `test_roadmap`: 303 grün, 1 übersprungen, Exit 0.
- Orca-Absagen und Nachbarn in `test_print_settings.py`: 11 grün.
- `test_errors` und `test_slicer_failure_actions`: 411 grün.
- Gegenprobe `scratchpad/rm620_gegenprobe.py` in vier Varianten. Es ist ein pytest-Plugin, das nur zur Laufzeit eingreift. Der Prüfbaum ist danach unverändert.

## Niedrig

### N5: Der neue Test hält N2 nicht fest

`tests/test_print_settings.py:3242` ruft `slice_model` ohne `keep_arrangement` auf. Die Vorgabe ist `False` (`handover.py:6416`), und `wanted_arrangement = keep_arrangement and …` (`:6532`) ist damit falsch. Die Bedingung des Rückfalllaufs (`:6605-6612`) bricht deshalb ab, bevor der Wächter in `:6611` gefragt wird. `assert len(runs) == 1` (`:3250`) ist so immer wahr.

Die Gegenprobe zeigt es:
- **A, unverändert:** grün. `orca_refused` wird nur aus 6679, 6698 und 6714 gerufen, nie aus 6611.
- **B, Wächter zur Laufzeit entfernt:** weiterhin grün (2 passed).
- **C, mit `keep_arrangement=True`, ohne Wächter:** rot an `:3250`, „die Temperaturprüfung hängt nicht an der Anordnung“.
- **D, mit `keep_arrangement=True`, mit Wächter:** grün, und alle übrigen Zusicherungen halten.

Im Produkt greift der Wächter, denn der Druckdialog übergibt `keep_arrangement=keep` (`print_settings_dialog.py:1313`, `1331`, `1365`, `1841`). Der Code ist richtig, nur nicht gegen einen Rückfall geschützt. Regel: `.claude/rules/tests.md:372-377` („Die Gegenprobe“).

Fix: In `:3242` `handover.slice_model(model, print_settings.resolve(profile), profile, setup, keep_arrangement=True)` schreiben. Damit stimmt auch „dazu ein einziger Slicerlauf bei −62“ in `ROADMAP-ARCHIV.md:44117`. In derselben Nachweiszeile die Durchsicht auf zwei Runden nachziehen und die Tor-Zahl eintragen, sobald der laufende Lauf fertig ist (Form wie RM-582, `:44093`).

### N6: Die Schreibweisen eines Absagecodes fehlen in der Regel

`.claude/rules/dateiformat.md:464-467` („Ein Absturz ist keine Absage“, lädt für `app/core/export/**`) nennt nur `crashed()`. Die Falle aus M2 betraf drei Erkennungen auf einmal: Eigene Codes kommen unter Windows als DWORD und unter Linux und macOS als Byte an, und `signed_exit_code` allein liest nur die Windows-Form. Steht das nur im Docstring von `orca_refused`, wird die nächste Erkennung wieder mit der alten Bauart geschrieben. Die Projektregel verlangt nach einer Musteränderung, `.claude/rules/` nachzuziehen (`CLAUDE.md`, „Arbeitsweise hier“).

Fix: ein Satz unter der Überschrift, etwa „Absagecodes der Orca-Familie kommen unter Windows als DWORD, unter Linux und macOS als Byte (−62 als 4294967234 oder 194); verglichen wird über `orca_refused`, `signed_exit_code` allein sieht nur Windows.“ Den Grund mit RM-620 unter dieselbe Überschrift in `konzepte/begruendungen/regel-dateiformat.md:573`.

## Nebenbefund außerhalb des Diffs (bestand schon vorher, hält die Landung nicht)

`crashed` (`handover.py:7749-7753`) erkennt POSIX-Signale nur als negative Zahl. Orca und Bambu Studio laufen als Flatpak über ihren Starter (`handover.py:4581-4583`, `4594-4595`). Im Vordergrund ersetzt sich `flatpak run` durch bwrap (`flatpak-run.c:4080`), und bwrap meldet einen Signaltod als 128+n (`bubblewrap.c:436-437`). Ein SIGSEGV kommt dort als 139 an, und der Kunde liest „Der Slicer hat keine Druckdatei geschrieben“ statt „abgestürzt“. Das gehört ins Register, nicht zu RM-620.

## Geprüft ohne Befund

- **M1:** Die Vorschläge stehen in `handover.py:6730`. `ARRANGE_ON_BED` ist `primary` (`errors.py:242`), und `leading_action` nimmt die erste primäre Handlung (`style.py:820-828`), also ist „Auf dem Bett anordnen“ der Hauptknopf. `OPEN_PRINT_SETTINGS` ist weg, der Test sichert beides zu. Die Beschriftung bleibt zu Recht: `filament_groups` trennt nur, wenn es mehr Gruppen als `max(1, nozzles)` gibt (`prepare.py:3482-3485`). Am Kobra 2 mit einer Düse kommen PLA und PETG also auf eigene Platten. Bei zwei oder mehr Düsen nennt der Satz den Weg von Hand. Der Zwilling `ORCA_PATHS_CROSS` ist genauso gebaut.
- **M2:** `orca_refused` (`:7714-7721`) ergibt `{−62, 4294967234, 194}`, `{−50, 4294967246, 206}` und `{−101, 4294967195, 155}`. Alle drei Erkennungen (`:6679`, `:6698`, `:6714`) und der Wächter (`:6611`) laufen darüber. Unter Flatpak kommt die Byteform an, weil bwrap `WEXITSTATUS` unverändert durchreicht (`bubblewrap.c:427-428`).
- **Andere Aufrufer von `signed_exit_code`:** Es gibt nur die Protokollzeile `:6656`. Unter POSIX steht dort 194, und das ist der echte Exit-Status, also kein Fehler. Dazu kommen konstante Zusicherungen in den drei Tests. Sonst vergleicht in `app/` nichts einen Slicer-Rückgabewert (grep `returncode|exit_code`).
- **Kollisionen:** Stirbt der Prozess direkt an einem Signal, liefert Python eine negative Zahl. Die fängt `crashed` (`:6660`) vor den Orca-Prüfungen ab, die negative Form in `orca_refused` erreicht das Produkt also nie. Über einen Wrapper wird ein Signal zu 128+n. Damit trifft nur 155 = 128+27 (SIGPROF, Linux und macOS) eine Byteform, und an SIGPROF stirbt ein Slicer praktisch nie. 194 und 206 bräuchten die Signale 66 und 78, die es nicht gibt (Linux endet bei 64, macOS bei 31). Unter Windows liefert die Orca-CLI nur Codes ≤ 0 als DWORD. Solidons eigener Abbruch über `taskkill /T /F` und `Popen.kill` (`process.py:560-591`) endet mit 1 und greift ohnehin erst nach Abbruch oder geschriebenem Ergebnis. Untereinander kollidieren die CLI-Codes nicht, weil −1 bis −110 kürzer ist als 256.
- **N1:** Der Satz hat 25 Wörter in 2 Sätzen und liegt damit genau an der Grenze (`test_text_length.py:50`, grün). Er schreibt das Urteil dem Slicer und seinen Profilen zu (Regel 21), und die Konstante nennt beide Bedeutungen des Codes.
- **N2 im Code:** richtig (Variante D). Offen ist nur der Test, siehe N5.
- **N3:** es „qué hacer“, pt „o que fazer“, en „whose temperatures are too far apart“. Der Punkt steht unter `## 0.6.0` / „Drucken und Übergabe an den Slicer“.
- **N4 und Archivform:** Datum, Plattformgrenze, Tests, Review, Tor und Changelog sind drin. Der Index steht oben, der Rumpf hinter RM-582, mit zwei Ankern wie bei den Nachbarn; `test_roadmap` ist grün.
- **Übersetzungen:** in allen fünf Katalogen, an sortierter Stelle. Die Anrede folgt dem Bestand: es „elija“, pt „escolha“, it „scegli“, fr „choisissez“. Im Französischen steht vor dem Doppelpunkt ein gewöhnliches Leerzeichen wie in 967 anderen Einträgen. Die Glossarwörter für Platte und Teil stimmen. „Temperaturbereich“ war vorher in keinem Katalog übersetzt, es gibt also nichts, womit es kollidieren könnte. Vom Satz der ersten Runde ist kein verwaister Schlüssel geblieben.
- **Regeln:** 17 (vier Handlungen), 20 (`_()`, fünf Kataloge), 21 (siehe N1) halten. Zwillingsregel 4 betrifft Familiennamen statt Eigenschaft, nicht das Lesen von Rückgabewerten.

## Urteil

Nein, so noch nicht: Erst kommen die eine Testzeile (N5) und der Regelsatz (N6) dazu. Beides ist niedrig, danach ist der Stand ohne weitere Runde landungsreif.
