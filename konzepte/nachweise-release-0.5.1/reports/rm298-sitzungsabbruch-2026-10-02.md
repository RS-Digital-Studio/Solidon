# RM298(e): Bestätigtes Arbeiterende vor synchroner Auswertung

Stand: 02.10.2026. Die Fehlerklassenkorrektur ist erneut unabhängig
freigegeben. Auswertungsmodul und Sprachprüfung sind frisch geprüft.
Zentrales Entwicklungstor und tatsächliche Commit-/Pushintegration dieser
Einheit werden gesondert fortgeschrieben.

## Kundenfehler und chirurgische Korrektur

`Session.evaluate_now` setzte das gemeinsame Abbruchsignal zurück, obwohl
sein alter Auswertungsarbeiter noch lief. Es erklärte das alte Ergebnis
für überholt, forderte aber kein Ende an. Gleichzeitig konnte eine alte
Kernfrage unbegrenzt ohne Antwortempfänger warten und nach einem Reset
wieder als aktuell erscheinen.

Vier eigene Quellhunks in `app/ui/session.py` ändern genau diese Anschlüsse:

1. Benannte Grenzen für die alte Endbestätigung und den Fragenpoll:
   `SYNC_EVALUATION_END_WAIT_MS = 10_000`, `QUESTION_CANCEL_POLL_S = 0.05`.
   Die Endgrenze folgt der vorhandenen Sitzungsabbau-/Idle-Vorgabe, der
   Poll dem vorhandenen Abbruchpolling. Der Poll ist keine Antwortfrist.
2. `evaluate_now` hält den bisherigen Arbeiter lokal, löscht eingereihte
   Nachläufe und das Nutzerabbruchkennzeichen, kennzeichnet den alten Auftrag
   als überholt und fordert dessen Abbruch an. Es invalidiert Fragen und
   bestätigt mit `worker.wait` das Ende. Erst danach setzt es den Token
   zurück und beginnt den vorhandenen feinen synchronen Lauf.
3. `question_is_current` nutzt für den Auswertungsarbeiter `_stale`, damit
   auch ein überholter Auftrag nach dem Reset ungültig bleibt.
4. `ask_from_worker` prüft den Auftrag wiederkehrend während `Event.wait`
   und nochmals nach der Antwort. Verfall beendet eine unbeantwortete Frage
   mit `OperationCancelled`; eine aktuelle Frage darf auf den Nutzer warten.

Ein nicht bestätigtes Ende startet keine neue Rechnung: Arbeiterbezug,
gesetzter Abbruch, bestehendes Ergebnis und Fragenstand bleiben gehalten.
Es gibt keinen globalen Idle-Weg, keine Ereignisschleife und keine erzwungene
Threadbeendigung. Die vorhandenen Endslots behalten ihre Zuständigkeit für
Leine, Busy-Anzeige und tatsächlichen Abbau; späte Ergebnisse/Nachläufe
ändern den Nachfolger nicht.

## Korrigierter Fehlervertrag und fünf Kataloge

Die erste Umsetzung verwendete `InternalError` mit übersetztem Kundentext.
Der konkrete Regelwächter
`test_no_internal_error_speaks_to_the_customer` beanstandete diese Einordnung.
Der Prüfwächter blieb unverändert; die Quelle verwendet jetzt den vorhandenen
`UserError` mit eigener passender Überschrift und `suggestions=(CANCEL,)`:

- Überschrift: „Die neue Berechnung kann noch nicht starten.“
- Detail: „Die vorherige Berechnung wurde nicht rechtzeitig beendet.
  Die neue Berechnung wurde deshalb nicht gestartet.“

Beide deutschen Schlüssel stehen über `tr()` in der Quelle und gezielt
in jedem Katalog aus `app/i18n/locales/`: `en`, `es`, `fr`, `it`, `pt`.
Außer diesen zwei Werten wurde kein Katalogwert geändert. Die tatsächlichen
Einfügehunks und die erhaltenen alten Werte sind gesichert. Es entsteht
keine neue Ausnahmeart; der vorhandene Fehleranschluss bietet Abbrechen
an und verspricht keinen ungeprüften Neustart.

`own-source-hunks-first-reviewed.json` und der erste unabhängige Review
bleiben historische Belege der damals falschen Fehlerwahl. Der korrigierte
Stand steht in `own-source-hunks.json`; `error-kind-correction.json` hält
die enge Berichtigung fest. Die ursprünglichen Entwurfsentscheidungen
werden nicht nachträglich als schon richtig ausgegeben.

## Sechs tatsächliche Entwicklungsfälle

Die sechs neuen Funktionen in `tests/test_evaluation.py` binden die echten
Session-Methoden an einen vorbereiteten Namespace. Echt bleiben
`CancelSignal`, `AskRequest` einschließlich `reply`/`answered`, die
Auftragsprüfungen und ein Python-Faden mit Ereignissen. Worker-/Signal-/
Historienaußengrenzen und die synchrone Ergebniserzeugung sind gestellt.
Kein Fall erzeugt eine Qt-Anwendung, einen Qt-Arbeiter oder ein Fenster.

| Fall | Verlangter tatsächlicher Anschluss |
|---|---|
| Ende vor Reset | Abbruch und Invalidierung, bestätigtes Ende, erst danach Reset und genau ein feiner synchroner Lauf |
| Alte Frage ohne Empfänger | Wirklich abgegebene unbeantwortete Frage endet beim Ersetzen ohne Antwort oder Qt-Ereignisschleife |
| Späte Frage nach Reset | Die zuvor gültige Frage bleibt auch nach Reset und verspätetem `reply` ungültig |
| Nachlauf und alte Slots | Kein Zusatzlauf oder gemeldeter Nutzerabbruch; echte aktuelle Nutzerabbrüche bleiben erhalten |
| Ende unbestätigt | Fehler mit Handlung, derselbe gehaltene Arbeiter/Abbruch/Ergebnisstand; kein Reset und keine neue Rechnung |
| Antwort `None` | Aktueller Auftrag liefert exakt `QuestionDeclined`, überholter Auftrag exakt `OperationCancelled`; keine gespeicherte veraltete Antwort |

Der Fadentest beobachtet die echte Frage vor dem Ersetzen und verlangt ihr
Ende ohne Empfänger. Erst im `finally`, nach sämtlichen Zusicherungen oder
deren Fehlschlag, ermöglicht eine echte `reply(None)` den Prüfabbau. Diese
Abbauhilfe kann keinen vorherigen Erfolg erzeugen. Unerwartete andere
Arbeiter-/Idle-Wartewege scheitern ausdrücklich.

## Tatsächliche Läufe und Grenzen

Interpreter `.venv/Scripts/python.exe`, Python 3.14.7. Rohtext und JUnit
werden je Lauf getrennt gespeichert; Ergebnis-JSON enthält Auswahl, Exit,
Testkörperfehler, Aufbau-/Abbaufehler, Skips und Hashes vor/nach dem Lauf.
Fenster-, Renderer- und Leistungsfälle sind abgewählt; die Fehlervertrags-
Nachprüfung wählt zusätzlich `rendered` ausdrücklich ab.

| Lauf | Bestanden | Testkörperfehler | Aufbau-/Abbaufehler | Skips | Exit |
|---|---:|---:|---:|---:|---:|
| Gegenlauf der sechs Fälle vor dem Produktfix | 0 | 6 | 0 | 0 | 1 |
| Sechs Fälle nach Umsetzung und eigener Ruff-Berichtigung | 6 | 0 | 0 | 0 | 0 |
| Historischer Modulnachlauf mit damaligem RM327-Gegenfall | 187 | 1 | 0 | 0 | 1 |
| Korrigierte Fehlerklasse: sechs Fälle und unveränderter Fehlerwächter | 7 | 0 | 0 | 0 | 0 |
| Frischer vollständiger Auswertungsmodulnachlauf | 190 | 0 | 0 | 0 | 0 |
| Frische Sprach-/Katalogprüfung nach beiden neuen Schlüsseln | 628 | 0 | 0 | 0 | 0 |

Der historische Modulfehler betrifft
`test_the_final_report_replaces_a_count_without_changing_the_number_of_findings`.
Er wird nicht als grüner Modulabschluss oder als Fehler der sechs neuen
Abbruchfälle ausgegeben. Seine Rohdateien werden beim frischen Nachlauf
nicht überschrieben.

Alle Quell-/Testhashes blieben je aufgeführtem Lauf stabil. Die Testdatei
erhielt zwischen den Läufen koordinierte RM327-Ergänzungen; ein frühes
Ganzdatei-SHA wird deshalb nicht als späterer Laufstand ausgegeben.

| Lauf | `app/ui/session.py` | `tests/test_evaluation.py` |
|---|---|---|
| Gegenlauf | `c5a88805c9ee24322059676b59360f23193cff3ece0500f1c3e3ef46e9905e26` | `b8a3fd0376381ca957f69e3b1049b86693e917ab0ab0d5c9dcc574224109da88` |
| Erste endgültige Sechsfallgruppe | `6e02bcba68b5c7ef258dac72517f32451ee63a8d800d6bda06123a0fca18b8bd` | `d46a29a23b6dd2be2b02e4ed9c408845a23c1b39a9113101274021c78730941d` |
| Fehlervertrags-Nachprüfung | `9a21b3c8878d8848b7d996dcb62b050a109e119276536d0f7955fe6cbbc53a74` | `feedc1ae8fe6fab6cfc66af7caf204db6603f3ee58e57f3d37c7e2e30251a94d` |

Der dritte stabile Hash der Fehlervertrags-Nachprüfung ist
`tests/test_errors.py`:
`1bdc97890ea3678adb0361b6f91bbb4528e22a0f2e81394f288a05dd880289c8`.
Die ersten mechanischen Prüfungen verlangten eigene Ruff-Korrekturen am
neuen Testanhang; die finale sechsfallige Gruppe lief danach erneut grün.
Ruff, eigene Formatbereiche und reine Importgraph-Auswahl sind dokumentiert.
Die reine Importgraph-Auswahl ist dokumentiert; das zentrale
Entwicklungstor steht noch aus. Die Auswahl ist kein ausgeführter
Gesamtlauf.

## Frischer Nachlauf und erneuter unabhängiger Review

`whole-module-final.txt`/`.xml`/`-result.json` belegen den vollständigen
frischen Entwicklungsnachlauf: **190 bestanden, Exit 0, keine Fehler
oder Skips**. Vier Hashes bleiben stabil: Session und Testdatei wie in
der Fehlervertrags-Nachprüfung, außerdem `scene/evaluate.py` auf
`2fde00c231bc70a224bc74205388445266d4953dbb56193d9c475717047e4a6f`
und `geom/mesh.py` auf
`0c4c56b6a1d8ff244c5db7f87f15ee837559bafce147f49dce86865c252ac978`.
Die fremden RM327-Hunks werden dadurch nicht Teil dieser eigenen Einheit.

`translations-final.txt`/`.xml`/`-result.json` belegen nach beiden neuen
Katalogschlüsseln **628 bestanden, Exit 0, keine Fehler/Skips**;
Sessionquelle und alle fünf Kataloghashes sind davor/danach identisch.
Der erste Sprachlauf vor dem zusätzlichen Überschriftenschlüssel bleibt
als historischer eigener Lauf erhalten. Finale Ruff- und Formatprüfung
beider eigener Dateien sowie lesender Diffcheck enden jeweils mit Exit 0.
Es wurde keine Datei durch Formatierung verändert.

Der neue unabhängige Produktionsreview `/root/rm298_lifecycle_review`
gibt die vier eigenen Source-Hunks, sechs vollständig gelesenen Fälle,
beide Schlüssel in allen fünf Katalogen und den tatsächlichen allgemeinen
UI-Fehler-/Frageanschluss mit **JA ohne weitere konkrete Funde** frei.
Er ist auf die korrigierte Fehlerwahl bezogen und getrennt von der
historischen Erstfreigabe. Der Bericht
`independent-corrected-production-review-20261002.md` hat SHA256
`e5f6295ecfaf907e463629475b27a9dd3e0823efd4c0d3d3ad903cc8d760b1a4`.
Die acht geprüften Quell-/Test-/Katalogdateien sind bytegleich in
`sealed-for-handoff/` gesichert; `sealed-handoff-source.json` hält ihre
Identität und die finalen statischen Prüfergebnisse fest. Weitere
Export-/Sliceranschlüsse sind als eigene B01-Einheit abgestimmt.

## Nachweise und verbleibende Abnahme

Örtlicher Ordner:
`tmp/review-seit-0.5.1-2026-10-01/rm298-sitzungsabbruch-20261002-7db5/`.

- `before`, `after-final`, `whole-module`, `error-contract-final`: jeweils
  Rohtext, JUnit und `-result.json`;
- `own-source-hunks.json`, `own-test-hunks.json`, beide eigene Kataloghunk-
  Listen samt Einfügenachweisen für die genaue Änderungsgrenze;
- `run_cases.py`, `check_error_contract.py`, `check_changes.py` für die
  tatsächlichen Prüfaufrufe; `check_changes.py` bewahrt den historischen
  Modulgegenlauf bei einem gesondert benannten finalen Lauf;
- `fix_error_kind.py` und `error-kind-correction.json` für die konkrete
  Berichtigung nach dem Regelbefund.

Diese Gruppe beweist den logischen Lebenszyklus-/Fragenanschluss. Native
Qt-Signalzustellung, sichtbare Busy-/Fehleranzeige, Fensterverhalten und
Abbruchlatenz sind Releaseprüfungen. Ein grüner Entwicklungsfall ersetzt
keine davon. RM298 bleibt insgesamt `[~]`; Plattform-, Paket- und
Leistungsreste werden nicht durch diese Session-Korrektur geschlossen.
