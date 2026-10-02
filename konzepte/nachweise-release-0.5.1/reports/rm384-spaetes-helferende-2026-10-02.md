# RM-384: Die nächste Rechnung sammelt einen inzwischen beendeten Helfer ein

Stand der lokalen Entwicklungsprüfung: 02.10.2026. Nach dem zentralen Zweitreview ist der Konstruktoranschluss gezielt nachgebessert, geprüft und unabhängig ohne weitere Befunde freigegeben. Das damals noch ausstehende zentrale Entwicklungstor und die spätere Integration sind im datierten Integrationsnachtrag dieses Berichts dokumentiert. Die folgenden lokalen Gegenlaufzahlen bleiben Nachweise ihres jeweiligen Prüfstands.

## Befund und Korrektur

Der Ausgangsbefund aus `review-3fd3b1ace.md`, Fund 6, wurde mit der ursprünglichen Sonde erneut bestätigt: Ein beim Stoppen noch lebender Helfer blieb auch nach seinem späteren Ende im Pool gesperrt; drei weitere öffentliche Rechnungen sagten ab. Die Sonde verwendet eine Prozessattrappe. Sie misst keine tatsächliche Windows-Tötungsfrist.

`kernel_process._Pool` trennt jetzt eine dauerhafte Start-/Helferabsage von noch unbestätigten Stopps. Vor der Pfadwahl in `run`, vor einer Reservierung und vor dem lokalen Rückfall sammelt er inzwischen tote Stoppreste über den vorhandenen Stopweg ein. Solange ein solcher Helfer lebt, bleibt die Sperre erhalten, auch während eines erneuten Stopversuchs. Ein fortdauernder Absagegrund wird beim Einsammeln nicht gelöscht.

Die Reservierung hält ihre Generation bereits vor dem Einsammeln fest. Ein paralleles `shutdown` kann dadurch keinen alten Aufruf in den neuen Bestand einschleusen. Kandidaten werden einzeln beansprucht; eine unerwartete Ausnahme beim ersten Kandidaten lässt den nächsten aufräumbar. Der bestehende Stopweg schließt die Verbindung, tritt dem Prozess bei und gibt die Elternbindung frei. Ein bestätigtes Ende zählt nur einmal.

Das unabhängige Review fand zwei Anschlusslücken im ersten Entwurf. Der lokale Pfad behält seine zweite Stoppsperre nach der Pfadentscheidung. Außerdem werden ein wirklicher Bereitschaftsfehler und eine dauerhafte Helferabsage vor dem möglicherweise ebenfalls scheiternden Stoppen festgehalten. Zusätzliche Tests durchlaufen hierfür die öffentlichen `run`-/`take`-Wege.

Der zentrale Zweitreview fand nach der ersten lokalen Freigabe einen weiteren P2: Ein im Konstruktor auftretender Startfehler ging beim ebenfalls fehlgeschlagenen Stoppen als Ursache und Fehlstartzählung verloren. Das späte Ende konnte deshalb einen neuen Start trotz erschöpftem Kontingent erlauben. Der erweiterte Ressourcenfall bestätigt dies über echte nachfolgende `run`-/`take`-Wege.

Der Konstruktor hält jetzt die ursprüngliche Ursache über beide Stopfehlertypen fest. Der Pool zählt nur die schon bisher als erwartete Startfehler klassifizierten Ursachen, mit der vor dem Start erfassten Generation. Unerwartete Ursachen werden nicht pauschal zur Startabsage. Ist das Kind beim Cleanup schon tot, wird der ursprüngliche Startfehler weitergegeben. Der lebende Bestand und seine Stoppsperre bleiben erhalten.

## Abgedeckte neue Entwicklungsfälle

Alle neuen Fälle verwenden Prozessattrappen und Ereignisse. 14 Fälle führen den echten `_Helper`-Konstruktor und Stopcode mit nachgestellten Prozess-/Verbindungsgriffen aus; sie prüfen die tatsächliche Ressourcenfreigabe des Codes, ohne ein Betriebssystemkind zu starten.

| Test in `tests/test_kernel_process.py` | Fälle | Zusicherung |
|---|---:|---|
| `test_pool_late_stop_end_recovers_without_shutdown` | 3 | Nächste lokale Rechnung, Arbeiterrechnung beziehungsweise `take` nach bestätigtem Ende wieder nutzbar; der Arbeiter benutzt wirklich einen neuen Helfer |
| `test_pool_late_stop_end_releases_the_real_helper_once` | 14 | Normaler Fall, erwarteter OSError und unerwarteter LookupError, beide lebenden Stopfehlertypen und bereits beim Cleanup totes Kind; jeder Fall bis zum nächsten echten Arbeiter-/take-Auftrag, ursprüngliche Ursache, Startkontingent, Einmalfreigabe und Shutdown-Reset |
| `test_pool_reaps_dead_orphans_while_a_live_orphan_keeps_the_kernel_locked` | 1 | Tote Reste werden gesammelt; der verbleibende Lebende sperrt weiter; danach steht die ganze Kapazität bereit |
| `test_pool_late_stop_end_keeps_a_permanent_disabling_cause` | 2 | Dauerhafte Absage und erschöpftes Startkontingent bleiben nach dem Aufräumen wirksam |
| `test_pool_retry_of_a_live_failed_stop_never_unlocks_the_kernel` | 1 | Ein lebender, gerade erneut gestoppter Helfer erlaubt keinen lokalen Rückfall |
| `test_pool_reservation_before_reaping_does_not_cross_shutdown_generation` | 1 | Eine alte Reservierung bleibt nach gleichzeitigem Shutdown überholt |
| `test_pool_reaping_failure_does_not_strand_an_unvisited_dead_helper` | 1 | Eine unerwartete erste Ausnahme lässt den noch unbesuchten Kandidaten für den nächsten Aufruf frei |
| `test_pool_local_choice_checks_a_stop_error_from_the_path_decision` | 2 | Ein zwischen Frühprüfung und lokaler Wahl entstandener Stopfehler erreicht Haupt- und Arbeiterfaden |
| `test_pool_lasting_refusal_survives_a_failed_stop_on_public_run` | 1 | Die wirkliche dauerhafte Absage über `run` bleibt nach verspätetem Ende bestehen |
| `test_pool_ready_failures_survive_failed_stops_on_public_take` | 1 | Jeder wirkliche Bereitschaftsfehler zählt trotz gleichzeitig verweigertem Stopp; nach dem Kontingent folgt der lokale Rückfall |

Zusammen 27 neue Fälle; der Ressourcenfall wurde im Konstruktor-Nachgang von zwei auf 14 Fälle erweitert. Der vorhandene Generationsfall wurde gezielt angepasst: Am jetzt früheren Absagezeitpunkt ist genau ein alter Helfer noch lebend im Besitz. `shutdown` sammelt genau diesen ein; danach ist er tot. Die bisherige Zusicherung, dass seine verspätete Absage keinen neuen Bestand deaktiviert, bleibt bestehen.

## Tatsächliche Gegenläufe und Endstand

Die vollständigen JUnit-Berichte wurden auf Testfehlschläge, Setup-/Teardownfehler und Überspringungen ausgewertet. Für die Pool- und Gegenläufe sind zusätzlich Quellenhashes jeweils vor und nach dem Lauf erfasst.

| Lauf | Ergebnis | Aussage |
|---|---|---|
| Ursprünglicher Code, bereinigte erste 11 neuen Fälle | 11 fehlgeschlagen, 0 Setup-/Teardownfehler/Skips, Exit 1 | Die ursprüngliche Dauersperre und ihre Kontrollflüsse werden tatsächlich verworfen |
| Lokaler Pfad ohne zweite Stoppsperre | 2 fehlgeschlagen, 0 Setup-/Teardownfehler/Skips, Exit 1 | Beide öffentlichen Aufruflagen erkennen den übersehenen Stopfehler |
| Absage-/Startzählung erst nach `discard` | 2 fehlgeschlagen, 0 Setup-/Teardownfehler/Skips, Exit 1 | Beide realen Anschlusswege erkennen den verlorenen dauerhaften Grund |
| Alle 15 neuen Fälle vor dem zentralen Konstruktor-Nachgang | 15 bestanden, 0 Fehler/Skips, Exit 0 | Kein Rückfall wird nur durch identische Attrappenergebnisse verdeckt |
| Ganze Kerneldatei vor Anpassung des bestehenden Generationsfalls | 93 bestanden, 1 fehlgeschlagen, 1 Fenstertest abgewählt, Exit 1 | Der alte Test erwartete an seinem verschobenen Wartepunkt irrtümlich null eingesammelte Helfer |
| Ganze Kerneldatei vor dem zentralen Konstruktor-Nachgang | 94 bestanden, 0 Fehler/Skips, 1 Fenstertest abgewählt, Exit 0 | Historischer Modullauf; er deckte den später gefundenen Konstruktoranschluss noch nicht ab |
| Erweiterte 14 Ressourcen-/Anschlussfälle vor dem Konstruktorfix | 10 fehlgeschlagen, 4 bestanden, 0 Setup-/Teardownfehler/Skips, Exit 1 | Vier falsche Neustarts, vier verlorene Ursachen und zwei verschluckte unerwartete Ursachen werden tatsächlich verworfen |
| Erweiterte 14 Ressourcen-/Anschlussfälle nach dem Konstruktorfix | 14 bestanden, 0 Fehler/Skips, Exit 0 | Beide Stopmodi, Originalursachen, Startkontingent, öffentliche Folgeaufträge und Reset geprüft |
| Alle 27 neuen Fälle am kanonischen Nachgangstand | 27 bestanden, 0 Fehler/Skips, Exit 0 | Nach Ruff-Formatierung gemeinsam bestanden; Quell-/Testhashes unverändert |
| Ganze Kerneldatei am kanonischen Nachgangstand | 106 bestanden, 0 Fehler/Skips, 1 Fenstertest abgewählt, Exit 0 | Alle Entwicklungsfälle gemeinsam bestanden; Quell-/Testhashes unverändert während des Laufs |
| Sprachregelung, Kerntrennung und harte Regeln | 854 bestanden, Exit 0 | Separater Entwicklungswächterlauf im gemeinsam bearbeiteten Baum; kein vollständiges Tor |
| Ruff, Format und begrenzter Diffcheck | jeweils Exit 0 | Eigene Quell-/Testdateien |

Sechs zusätzliche Fehlerkontrollen verändern ausschließlich das geladene Modul im jeweiligen isolierten Testprozess. Produktdateien bleiben dabei unverändert. Jede Variante scheitert an den Zusicherungen derselben Tests:

| Absichtlich falsches Verhalten | Betroffene Fälle | Tatsächliches Ergebnis |
|---|---:|---|
| Pfadwahl vor dem Einsammeln merken | 1 | Lokaler statt gefordertem Helferweg: Testfehlschlag |
| Dauerhaften Absagegrund beim Einsammeln löschen | 2 | Helfer statt gefordertem lokalem Rückfall: beide Testfehlschläge |
| Lebenden Wiederholungsstopp von der Sperre ausnehmen | 1 | Geforderter Stopfehler bleibt aus: Testfehlschlag |
| Generation erst nach dem Einsammeln lesen | 1 | Überholte Reservierung erzeugt einen neuen Helfer: Testfehlschlag |
| Alle Kandidaten vor dem ersten Stoppen beanspruchen | 1 | Zweite Rechnung wirft unerwartet `KernelHelperStopError` im Testkörper |
| Besitz entfernen, ohne den echten Stopcode aufzurufen | 14 | Zehn späte-Ende-Fälle schlagen fehl, weil der gehaltene Elternbindungsgriff nicht freigegeben wird; die vier bereits im Konstruktor beendeten Kontrollen bestehen |

Alle sechs Kontrollen wurden am kanonischen Konstruktor-Nachgangstand wiederholt: zusammen 16 erwartete Testfehlschläge und vier passende grüne Kontrollen, jeder Kontrollprozess Exit 1; keine Setup-/Teardownfehler oder Skips. Quell-/Testhashes vor und nach jedem Kontrollprozess sind unverändert und entsprechen der Endstandstabelle. Die ursprünglichen früheren Kontrollen ergaben acht Testfehlschläge am Teststand `e69bae2afa029b7fce97d27a3974d4b3bce156d9adcd99ce5e4cff32fad80f58` und Quellenstand `9ff06eaeb32b89f4eaaf650ce117bbf237a20a8c0cfb95039acbe054c28d4e96`; diese historischen Resultate bleiben vom aktuellen Nachweis getrennt.

Historische eigene Aufbaufehler sind nicht Freigabebelege: Der erste Vorherlauf ließ eine einmalig werfende Stoppattrappe im Teardown aktiv; ein anschließender mechanischer Einrückungsversuch verursachte einen Sammlungsfehler. Erst der bereinigte frische Vorherlauf ergab genau elf Testfehlschläge ohne diese Fehler. Eine Ruff-Formatabweichung der eigenen Reaper-Bedingung wurde vor dem damaligen Modullauf korrigiert. Im Konstruktor-Nachgang wurden eine eigene Zeilenlänge und die Python-3.14-Formatierung vor dem kanonischen Lauf korrigiert. Die frühere unabhängige Freigabe war hinsichtlich der Konstruktorursache unvollständig; der zentrale Zweitreview hat diese Lücke aufgedeckt. Ein eigener wiederaufgenommener Dokumentaufbau hatte zudem die Nachweisindexzeile und den RM298(d)-Integrationsnachtrag jeweils doppelt ergänzt. Beide identischen Dopplungen wurden gezielt entfernt. Die Dokumentwächter erkennen solche inhaltlichen Dopplungen nicht; ihre reine Grünmeldung ersetzt den unabhängigen Dokumentreview nicht.

## Reproduktion und Freigabegrenze

```powershell
.venv\Scripts\python.exe -m pytest -q tests/test_kernel_process.py -m "not windowed and not rendering and not performance and not rendered" --junitxml=kernel.xml
.venv\Scripts\python.exe tools/affected_tests.py app/core/geom/kernel_process.py tests/test_kernel_process.py
```

Die Importgraph-Auswahl umfasst 356 von 381 Testdateien und wird vom Werkzeug ausdrücklich als Suite/Tor eingestuft. Deshalb erfolgt das vollständige Entwicklungstor zentral am stabilen, zur Übernahme ausgewählten Stand. Ein Modullauf im gleichzeitig bearbeiteten Hauptbaum ersetzt diesen Nachweis nicht.

| Datei | SHA-256 des geprüften Endstands |
|---|---|
| `app/core/geom/kernel_process.py` | `17a71e75b3a1d31a9fda09111dc5528516aeb850d7dc52fdb2e8827180e0f4d0` |
| `tests/test_kernel_process.py` | `f174d569340f09180a0ccaa786f4d171d60781f663d4fde83af2e1020c3b183e` |

Eigenreview und unabhängiger vollständiger Quell-/Testnachreview einschließlich aller drei P2-Korrekturen und des vorhandenen Generationsfalls sind ohne offene Befunde abgeschlossen. Der unabhängige Reviewer hat die tatsächlichen JUnit-/Rohbelege und stabilen Endstandshashes geprüft, selbst keine Tests ausgeführt und keine Dateien geändert. Die frühere unvollständige Freigabe ersetzt diesen Nachreview nicht.

Das bestätigt die nachgestellten Kontrollflüsse. Eine wirkliche Überschreitung der Windows-Stoppfrist, Linux/macOS, der Fenstertest RM-380, Leistungsmarken und das gebaute Paket sind hier nicht nachgewiesen. Die weiter offenen Teilaufgaben des Gesamtpunkts RM-298 behalten ihre eigene Abnahme.

## Integrationsnachtrag 02.10.2026

RM384 ist als nachgestellter Kontrollflussfehler abgeschlossen. Die Korrektur
liegt mit `686abf9e63ed8708d15fdc642add170cb1d2c14f` auf `main` und dem tatsächlichen
Remote-Hauptzweig. Nach dem Abgleich der zwischenzeitlichen Remote-Änderungen
wurden das Tor wiederholt und die Übernahme getrennt geprüft.

| Nachweis | Tatsächlich verifizierter Stand |
|---|---|
| Fixcommit(s) | `686abf9e63ed8708d15fdc642add170cb1d2c14f` |
| Tatsächlicher Remote-Hauptzweig und Abstammung | `4cf460e87f8d93e2d950602c9fe25ce34e6b5eb9`; getrennte Abfragen von `HEAD`, `origin/main` und `git ls-remote origin refs/heads/main` ergaben am 02.10.2026 um 11:52:21 UTC denselben vollständigen Stand; `git merge-base --is-ancestor` für den Fixcommit gegen alle drei Ziele jeweils Exit 0 |
| Ausgewählter Wiederholungs-Torstand | `commit-tor-abschlussrunde-47-v2-final` |
| Vollständiges Entwicklungstor | 19.269 bestanden, 62 übersprungen |
| Suite / Ruff / Format / mypy | Exit 0 / Exit 0 / Exit 0 / Exit 0 |
| Rohbelege, JUnit und endgültige Exit-Werte | `bash .claude/scripts/suite-getrennt.sh`: 19.269 bestanden, 62 übersprungen, 412,39 s, Exit 0; `python -m ruff check .`, `python -m ruff format --check .` und `python -m mypy` jeweils Exit 0. Zentraler Rohlog und die vier Exit-JSONs sind lokal unter `tmp/review-seit-0.5.1-2026-10-01/commit-tor-abschlussrunde-47-v2-final/` erhalten. Dieser zentrale Torlauf erzeugt kein JUnit; die lokalen JUnit-Belege `kernel-file-constructor-final.xml`, `new-cases-constructor-final.xml`, `constructor-cause-before.xml`/`constructor-cause-after.xml` und `counter-final-*.xml` gehören getrennt zu den im Bericht ausgewiesenen Kontrollfällen |
| Unveränderter Prüfstand und Zuordnung der RM384-Hashes | zentraler Vorher-/Nachhervergleich `changed_during_gate: []`; bei der getrennten Integrationsprüfung um 11:52:21 UTC stimmten übernommener Git-Blob und Arbeitsbaum für `kernel_process.py` und `test_kernel_process.py` bytegleich zu den im portablen RM384-Bericht vollständig genannten finalen lokalen SHA256 |
| Quellhash am übernommenen RM384-Stand | `17a71e75b3a1d31a9fda09111dc5528516aeb850d7dc52fdb2e8827180e0f4d0` |
| Testhash am übernommenen RM384-Stand | `f174d569340f09180a0ccaa786f4d171d60781f663d4fde83af2e1020c3b183e` |
| Unabhängiger Dokumentabschlussreview | 02.10.2026: unabhängig freigegeben nach Abgleich der tatsächlichen Git-/Tor-/JUnit-Belege und aller neun eigenen Hunks; beide Dokumentnachgänge korrigiert, Nachprüfung ohne weitere Befunde |

Die historischen 94/15 Fälle, die ursprünglichen acht Fehlkontrollen und die
erste unvollständige Freigabe werden durch diesen Nachtrag nicht ersetzt.
Der kanonische lokale Nachgang bleibt getrennt zugeordnet: 10 rot/4 grün →
14 grün, alle 27 neuen Fälle grün, 106 Modul-Entwicklungsfälle grün bei einem
abgewählten Fenstertest; sechs Gegenvarianten mit 16 erwarteten Testfehlschlägen
und vier passenden grünen Kontrollen ohne Setup-/Teardownfehler oder Skips.

Der [Archivabschluss](../../../ROADMAP-ARCHIV.md#rm-384) bewahrt außerdem die
fremde Nachprüfung vom 02.10.2026 am älteren Stand `7f0de659d`. Deren Aussage
über die damals noch bestehende Sperre nach `d9f830aec` ist ein Vorherbefund;
sie wird nicht zur Aussage über den hier übernommenen Fixstand gemacht.

Dieser Abschluss bestätigt die nachgestellten Kontrollflüsse und die geprüfte
Integration. Echte native Windows-Killlatenz, eine wirkliche Überschreitung der
Stoppfrist beziehungsweise ein tatsächlich verspätetes OS-Kindende sind weiterhin
nicht nachgewiesen. POSIX-Speicherbesitz, ENOSPC/SIGBUS, Crashbereinigung,
Linux/macOS, Paketwege und Paketrauchtestfrist, Fenster-/Rendererabnahmen
(einschließlich RM380) sowie §31-Leistungsabnahmen bleiben offen.
[RM298](../../../ROADMAP.md#rm-298) bleibt als Gesamtpunkt offen. Es gibt keinen
Release- oder Laufzeitnachweis aus diesem Entwicklungsabschluss.
