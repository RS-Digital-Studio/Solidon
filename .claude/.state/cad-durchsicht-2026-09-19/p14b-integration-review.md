# P1.4b – unabhängiger Anschlussreview

Gelesen wurden der eingefrorene Auswertungs-/Antwortanschluss in
`scene/evaluate.py`, `perceive/match_decisions.py`, die echten Geometrie-
und Mehrkörperfälle in `test_matching_answers.py` sowie die neue
Frageweitergabe in `ui/session.py`, `main_window.py` und `dialogs.py`.
Maßstab ist `p14b-answer-contract.md`. Die bereits vom jeweiligen Owner
ausgeführten Kernsammlungen wurden nicht erneut gestartet. Kein Fenster-
oder Leistungslauf fand statt.

## Auswertung und vollständige Antworten

- `_answer_matches` führt Änderungen zunächst auf einer privaten Mapping-
  Kopie und in lokalen Befund-/Antwortsammlungen. Eine spätere falsche
  Antwort oder ein Abbruch veröffentlicht weder eine Teilgruppe noch den
  fertigen ersten Teil einer anderen Gruppe desselben Körpers.
- `mapping_with_decisions` verlangt die ganze aktuelle Konfliktgruppe,
  vollständige Entscheidungen und getrennte Außenziele. Auch ein nicht
  gewählter Gruppenkandidat darf nicht schon außen vergeben sein. Der
  vorhandene injektive Übernahmevertrag bleibt zusätzlich am Übernehmer.
- Die Ausgabeschleife sammelt Antworten neben `prepared_objects` und
  veröffentlicht sie erst nach erfolgreicher Vorbereitung aller Körper.
  Ein Fehler im zweiten Körper lässt den letzten vollständigen Szenenzustand
  stehen. `OperationCancelled` läuft unverändert bis zum Arbeiterabbruch.
- Die temporäre Szene enthält die wirklichen aktuellen Operationsausgaben
  und die soeben erkannten Merkmale des befragten Körpers. Verbrauchte
  Eingänge werden wie im tatsächlichen Veröffentlichungsweg ersetzt.
  Alte Hashes der neuen Ausgabekörper sind ausdrücklich ausgeschlossen;
  unangetastete andere Körper behalten ihre Hashes.
- Kandidaten sind körperqualifiziert. Der Callback wird im `finally`
  unmittelbar nach jeder Frage mit `(None, ())` geleert, auch bei einer
  Ausnahme aus dem Frageweg. Folgefragen erhalten keine alten Kandidaten
  oder Vorschauen aus diesem Kontext.
- Wiederverwendung prüft den ganzen aktuellen Anspruchsgraphen. Bereits
  körperbezogen beantwortete alte IDs fallen nach Ungültigwerden ihrer
  Gruppe nicht auf überholte `legacy`-Einzelantworten zurück. Zwei Körper
  mit demselben alten Namen teilen keinen unqualifizierten Altentscheid.
- Nicht fortgeführte Namen bleiben durch die vorhandenen Reservierungs-
  und Umbenennungswege gesperrt. Die Entscheidung entfernt weder Geometrie
  noch spätere Verweise.

Hieraus folgt kein allgemeiner nativer ID-Beleg: Bei referenzierter nativer
Konkurrenz hält der neue Anschluss ehrlich an. Die ausdrückliche allgemeine
native Referenzneuwahl bleibt offen. `carried_face_slots` ist Filamenthistorie,
keine Freigabe zum Übernehmen beliebiger Feature-IDs.

## Vorschau und Arbeiterlebensdauer

Die Session bindet Fragen an den beim Arbeiterstart erfassten Projektstand
und die Arbeiteridentität. Eine alte Anfrage wird vor dem Anzeigen sowie
vor Übernahme ihrer Antwort geprüft. Die temporäre Szene geht ausschließlich
an `Viewport.show_scene`; sie löst keinen `_on_scene`-Abschluss aus.
`last_result`, Dokument, Bericht, Verlauf und Dirty-Zustand werden dabei
nicht zum ungeklärten Operationsresultat.

Die Freigabe verlangt `is_scene_applied` für genau diese Vorschau. Button,
Enter, Doppelklick und `accept()` teilen die Bereitschaftsgrenze; Abbrechen
bleibt erreichbar. Nach dem Dialog werden kurzlebige Signalbindungen und
Markierungen entfernt. Die gültige aktuelle Szene wird vor `reply`
wieder eingereiht. Die vorhandene Viewportgeneration verhindert, dass ihr
späterer Aufbau ein jüngeres gültiges Ergebnis überschreibt. Nach einem
Projektwechsel wird keine alte Szene eingereiht.

Fehler beim Aufbauen, im Ansichtsarbeiter, im Dialog oder beim Wiederherstellen
geben die wartende Frage zuerst mit Abbruch frei und gehen dann an die
vorhandene Fehleranzeige. Fensterabbau beendet die Frage vor dem Warten
auf seine Arbeiter.

## Zwei belegte Anschlussbefunde

1. Der anfängliche Fragetext enthielt nur den alten Merkmalsnamen. Bei den
   zwei echten Ausgaben `Links` und `Rechts` mit gleichem altem Namen waren
   die Texte identisch. Auch die vertraglich geforderte Erklärung der offenen
   Folgeverweise bei „Nicht weiterführen“ fehlte. Roots Korrektur wurde
   nachgelesen: Körperzeile und Folgehinweis stehen jetzt am gemeinsamen
   Frageweg; der bestehende Mehrkörpertest verlangt `Links`/`Rechts` und
   den Folgehinweis. Katalog- und Laufnachweise bleiben beim Owner.
2. Eine bereits offene Frage wurde durch `cancel_evaluation` oder den
   Nachlaufzweig in `evaluate_async` nicht aktiv geschlossen: Nur Token/
   Nachlaufmerker änderten sich, während `ask_from_worker` auf das
   Antwort-Ereignis wartete. Die bisherige `projectChanged`-Meldung kommt
   bei `_changed` noch vor dieser Entwertung. Eine Antwort wäre später
   verworfen worden, der alte Dialog hielt den Arbeiter aber bis zu einer
   manuellen Reaktion fest.

Der zweite Befund ist im UI-Umfang korrigiert: `Session.questionInvalidated`
meldet die bereits erfolgte Token-/Nachlaufänderung an dieselbe kurzlebig
gebundene `check_context`-Prüfung. Es entsteht kein zweiter Frage- oder
Vorschauzustand. Kommt die Entwertung vor dem Signalanschluss, greifen die
Zustandsprüfungen vor `exec`; kommt die Antwort vor `Event.wait`, bleibt
das gesetzte Ereignis erhalten. Im `finally` wird auch die neue Verbindung
gelöst. Importfragen ohne zugehörigen Auswertungsarbeiter werden dadurch
nicht zum fremden Auswertungsabbruch.

Sechs zusätzliche Fenster-Parameterfälle sind geschrieben: Cancel und
Nachlauf jeweils während Konstruktion, Szenenaufbau und offenem Dialog.
Sie benutzen den echten Session-Frageweg und prüfen Antwort vor dem
Event-Warten, gültige Szenenwiederherstellung, leeren Kontext und gelöste
Signalbindung. Zusammen mit den zuvor geschriebenen Fällen sind es
**24 neue Fenster-Parameterfälle, ausdrücklich nicht ausgeführt**.

Abschließende direkte Prozesse zum UI-Stand, alle **Exit 0**:
Ruff über vier Pythondateien, Formatprüfung über vier Dateien, mypy über
die drei UI-Module und AST-Parsing von vier Dateien ohne Produkt-/Testimport.
Protokollordner:
`C:/Users/rober/AppData/Local/Temp/solidon-p14b-question-cancel-d725f4ff4e534f3ab4c02f715e8e9d78/`.
Es gibt durch den Cancel-Fix keine neuen übersetzbaren Texte.

## Nachreview der effektiven Antwortbindung im Folgecache

Roots belegter Cachefix wurde anschließend ausschließlich lesend geprüft.
Keine Wiederholung der vom Owner gemeldeten 104 Kernfälle oder der
unveränderten fremden Gegenprobe. Gelesene Hashes:

- `hashing.py`: `0CECC5AE558AB4A0B777D3080AF737C391D9B62032AA76D49B3979935F501FE4`
- `cache.py`: `74363EC23D585A1F72261EB64037521847BCDEBBADAA97BA35EBAFBCA2FB4772`
- `evaluate.py`: `97BC750C2041A8A431396D1FEC27EB130B65C4D16166DD362CA8B4E2EFD70E27`

Kein weiterer Befund in diesem abgegrenzten Diff:

- Der gemeinsame öffentliche `cache.feature_to_data` enthält sämtliche
  aktuellen `Feature`-Felder sowie alle vier `SurfacePatch`-Felder.
  Der Mapping-Schlüssel wird zusätzlich zur Feature-ID gehasht. Die
  tatsächlich gewählte Fläche, Maße, Herkunft, Erzeuger, Erkennbarkeit,
  Maßquellen und ursprüngliche Teilträgerindices sind somit erfasst.
- Die vorhandene kanonische Darstellung erhält volle Floatwerte, sortiert
  Mappings und behandelt JSON-Listen und Tupel gleich. Merkmalnamen werden
  sortiert und ihre festen Teilhashes nacheinander gebunden. Es entsteht
  keine zweite Gesamt-JSON aller Merkmale. Ein leerer und ein weggelassener
  Merkmalsbestand bedeuten dieselbe leere Bindung.
- Der einzige Produktaufrufer übergibt die **veröffentlichten** Merkmale
  nach Zuordnung und Reservierungsbehandlung. Der rohe Operationshash darf
  weiterhin ohne Antworten sein: Die Zuordnung wird auch nach seinem
  Cachetreffer erneut geprüft, ihr effektives Ergebnis entwertet danach die
  Folgeschritte. Cacheversion 20 verwirft frühere Einträge beider Ebenen.
- Abbruch wird vor der Rechnung, vor und nach jedem Feature-Codec und
  unmittelbar vor Rückgabe geprüft. Ein Teilhash wird nicht zurückgegeben.
  Dieser Rechenweg speichert nichts; die Auswertung hält Hashes/Antworten
  bis zur vollständigen Operationsvorbereitung lokal und schreibt erst nach
  den erfolgreichen Abschlussprüfungen neue Cacheeinträge.
- Der verschobene Verweisfilter ist semantisch richtig: Eine schon explizit
  bestätigte und noch vollständig wiedererkannte Gruppe bleibt nach Undo
  des einzigen Verbrauchers gültig. Nur eine **neue** Frage braucht einen
  aktuellen Verweis; unbekannte unreferenzierte Gruppen erhalten keine
  erfundene Identität.

Der neue Folgecache-Test enthält die tatsächliche maßgebundene Folgegeometrie,
unterschiedliche bestätigte Zielbindungen, Warmcache, Undo/Redo und einen
neuen Plattencache nach Speichern/Öffnen. Seine Ausführung bleibt der belegte
Owner-Nachweis. Der hier geprüfte Stand ist für das gemeinsame Entwicklungstor
freigegeben; Fenster- und Leistungsabnahme bleiben davon getrennt.
