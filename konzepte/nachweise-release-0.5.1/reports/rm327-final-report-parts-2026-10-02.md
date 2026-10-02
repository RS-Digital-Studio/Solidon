# RM-327: Teilezahl im fertigen Bericht erhalten und nachführen

Fachnachweise vom 02.10.2026. Die gezielten neuen Fälle und bestehenden
Anschlusskontrollen sind grün. Code und Dokumentation sind unabhängig
freigegeben. Das zentrale Entwicklungstor und die tatsächliche
Hauptzweigübernahme fehlen noch; zwei spätere Wächter des gemeinsamen Baums
sind unten mit ihrem tatsächlichen roten Ergebnis festgehalten.

## Der reproduzierte Fehler

Zwei kreuzende Langlöcher teilen einen 20-mm-Würfel zunächst in zwei, dann
vier Teile. Eine halbe Brücke verbindet zwei Viertel: Drei lose Teile bleiben.
Der frühere Abschlussfilter strich jedoch beide Bohrungswarnungen, weil ihre
ursprünglichen Zahlen zwei und vier nicht mehr zur neuen Zahl drei passten.

Umgekehrt blieben fünf tatsächlich ausgegebene Warnungen bestehen, nachdem
ihre Geometrie wieder zu einem Materialteil vereinigt war:
`label.fell_apart`, `texture.fell_apart`, `parts.hanging_loose`,
`blend.still_apart` und `sketch.join_apart`.

Ein weiterer Anschlussfehler betraf reine Wertänderungen: Der abschließende
Bericht wurde nur ersetzt, wenn sich die Anzahl seiner Zeilen änderte.
Ein erneuertes Finding mit einer anderen Zahl konnte dadurch verloren gehen.

## Umsetzung und bewusst getrennte Messgrößen

`bore.splits_the_body` erhält am belegten mehrteiligen Endstand ein neues
Finding mit aktuellem `values['count']`. Bei einem belegten Materialteil fällt der
Hinweis weg; bei unbekanntem Körper oder unbewiesener Zahl bleibt er erhalten.
Die fünf ergänzten Codes folgen derselben Einteilprüfung. Die endgültigen
Findings werden auch bei unveränderter Zeilenanzahl in den Bericht übernommen.

Die Werte des rohen Operationsbefunds werden dabei kopiert und bleiben im
Cache unverändert. Der Abschluss erfolgt auch nach Cachetreffern; weder
Operations-Cacheversion noch Projektformat ändern sich. Erst nach der
Aktualisierung folgt die bestehende Entdopplung. Unterschiedliche Orte,
Konturen und Merkmalziele werden durch diesen Fix nicht zusammengelegt.

Eine Materialzahl ist keine Schalenanzahl. Deshalb erhält nur die ausdrücklich
benannte Untermenge `MATERIAL_PART_CODES` die neue Prüfung. Die übrigen alten
`ONE_PIECE_CODES`, ihre `COUNTED_PARTS`-Vergleiche und die bisherige
Kleinteilzählung behalten ihre Bedeutung. Getrennte Merker halten beide
Auskünfte je Körper auseinander. Eine Gegenkontrolle verwendet zwei hohle
Körper: zwei Materialteile, aber vier Netzkomponenten.

## Was einen Materialzählwert belegt

Native Körper verwenden ihre Solid-Zahl; offene Formen oder null Solids
werden nicht als ein Materialteil ausgegeben. Das ist die bestehende native
Topologieauskunft, keine zusätzliche Gültigkeits- oder Überlappungsprüfung.
Für Netze bündelt
`repair.material_part_count` vorhandene Prüfungen:

- Verschweißen auf einer privaten Kopie, auch bei unverschweißten STL-Daten.
- Geschlossene, konsistent gerichtete Schalen.
- Vollständige vorhandene Selbstschnitt- und Kontaktprüfung.
- Zuordnung durch `material_part_families`: Eine negative Innenhaut gehört
  zum äußeren Materialkörper; eine freie positive Insel darin zählt extra.

Für Kontakte gilt die vorhandene Helferdefinition einschließlich ihrer
Abgrenzung von bloßem Kanten- oder Eckkontakt; der Fix führt keine neue
Kontaktklassifikation ein.

Ein erschöpftes Prüfbudget oder ein nicht belegter Zustand liefert `None`.
Andere Fehler werden nicht als Ungewissheit versteckt; Abbruch bleibt Abbruch.
Der Auswertungstoken reicht durch den neuen Weg bis zum kalten
`component_labels`-Aufruf im vorhandenen Hilfsprozess. Die Schlussprüfung liegt
vor der Veröffentlichung neuer Cacheeinträge und der Fertigmeldung.

## Echte Operationsfolge und getrennte Anschlusskontrollen

Die Brückenfolge verwendet die registrierten Operationen an beiden Kernen
und in `draft` sowie `fine`. Die Teilbrücke ist 7 × 20 × 4 mm groß und liegt
bei x = 6,5 mm. Nach dem Vereinigen sind drei Teile vorhanden. Ein zweiter
Lauf nutzt die fünf Operationscacheeinträge; Undo nimmt Brücke und Vereinigung
zurück und stellt vier Teile her, Redo wieder drei. Eine volle Brücke führt
zu einem Teil und entfernt den Hinweis; ihr Undo bringt die Warnung zurück.
Die rohen Bohrungsbefunde behalten durchgängig ihre ursprünglichen Werte
zwei und vier. Der fertige Hinweis gehört weiter zum tatsächlichen Schritt
und bietet dessen Handlung zum Korrigieren an.

Die fünf anderen Warnungen werden zuerst über ihre tatsächlichen registrierten
Ausgeber erzeugt. Eine registrierte Vereinigung mit einem Hüllquader um die
jeweilige Ausgabe erzeugt den einteiligen Endstand. Mehrteilige und unbekannte
Gegenkontrollen erhalten die ursprünglichen Befundwerte. Eine zusätzliche
Gegenkontrolle erzeugt zunächst den allgemeinen Zerfallshinweis; mit dem
tatsächlichen Ausgeberbefund entfällt dieses Echo. Dies sind gezielte
Ausgeber-/Vereinigungs-/Endfilterfälle, keine fünf vollständigen Bedienabläufe.

Den Fehler bei unveränderter Berichtsanzahl trennt ein kleines eigenes
Testregister mit echten Netzen ab: Es übernimmt einen tatsächlich erzeugten
Bohrungsbefund und fügt einen getrennten dritten Würfel hinzu. Der Bericht
muss genau eine Zeile mit `count=3` enthalten, kalt wie warm. Dieser
Anschlussfall ersetzt nicht die vollständige registrierte Brückenfolge.

Weitere Anschlusskontrollen belegen die getrennte Einmalzählung von Material
und Netzkomponenten, offene native Formen sowie geschlossene Formen ohne
Solid. Der tatsächliche Auswertungsabschluss wird kalt und warm während der
Materialprüfung abgebrochen: Er veröffentlicht weder einen Teilbericht noch
neue Cacheeinträge und meldet keinen erfolgreichen Abschluss.

## Gelesene Rot- und Grünbelege

| Protokoll | Tatsächlicher Ausgang |
|---|---|
| `report-red-final-fixture.txt` | 14 fehlgeschlagen, 3 bestanden, 1217 abgewählt; 10,19 s, Exit 1. Tatsächliche Brückenfolge, fünf Ausgeber, Hohlraum/Inneninsel und reine Berichtsänderung rot; drei unveränderte Altzählerkontrollen grün |
| `invalid-shell-red.txt` | Fünf fälschlich geheilte Einzelschalen: offen, inkonsistent, negativ, volumenlos und selbstkreuzend; 5 fehlgeschlagen, 221 abgewählt; 0,92 s, Exit 1 |
| `report-adoption-red.txt` | Genau eine veraltete Zahl bei weiterhin einer Zeile; 1 fehlgeschlagen, 33 bestanden, 380 abgewählt; 1,02 s, Exit 1 |
| `first-direct-green.txt` | 50 bestanden, 1410 abgewählt; 4,03 s, Exit 0 |
| `direct-complete.txt` | 56 bestanden, 1420 abgewählt; 5,61 s, Exit 0 |
| `affected-direct-final.txt` | 155 gezielte neue und bestehende Fachfälle bestanden, 1473 abgewählt; 7,63 s, Exit 0 |
| `cards-final.txt` | 14 Kartenprüfungen bestanden; 3,00 s, Exit 0 |
| `language-final.txt` | 610 Sprach-/Werteprüfungen bestanden, 56 abgewählt; 53,05 s, Exit 0 |
| `mypy-final-after.txt` | Drei Produktdateien ohne Typfehler, Exit 0; der erste Lauf hatte den inzwischen korrigierten lokalen Zählvariablentyp beanstandet |
| `format-final-after.txt` | Sieben Pythondateien bereits formatiert, Exit 0 |
| `documents-final.txt` | 32 Roadmap-/Kartenprüfungen bestanden; 8,10 s, Exit 0 |
| `core-contracts-final.txt` | 356 bestanden, 1 fehlgeschlagen; 58,25 s, Exit 1. `test_no_internal_error_speaks_to_the_customer` beanstandet den übersetzten `InternalError` in `app/ui/session.py:4536`, außerhalb dieser Einheit |
| `ruff-final-after.txt` | Exit 1: Nach dem parallel abgestimmten Catch-Wechsel bleibt in `repair.py:37` ein unbenutzter `OperationCancelled`-Import. Der frühere Ruff-Lauf war grün; er ersetzt diese spätere Prüfung nicht |

Die Läufe überschneiden sich; ihre Fallzahlen werden nicht addiert. Die
vollständigen lokalen Protokolle stehen unter `tmp/rm327-20261002/`, die
dauerhaften Gegenfälle in den vorhandenen Dateien `test_slot_features.py`,
`test_prepare.py`, `test_repair.py` und `test_evaluation.py`.

`report-red.txt` war der erste Zwischenstand mit zwölf fehlgeschlagenen und
fünf bestandenen Fällen. Der endgültige Rotbeleg verstärkt die
Hohlraumvorbedingung, sodass auch die zwei zuvor zufällig grünen Fälle den
Fehler zeigen. Die 16 Aufbaufehler in `filter-stage.txt` waren dagegen Fehler
der Testsonde beim Zugriff auf die Provenienz und zählen nicht als Produktbeleg.

Die beiden roten Wächter wurden der zuständigen Sitzung zugeordnet. Diese
hat beide Stellen vorwärts korrigiert; deren erneute Abschlussprüfung steht
noch aus. Der RM327-Executor hat die fremden Stellen nicht verändert. Der Importgraph nennt
358 von 383 Testdateien; deshalb ersetzt die gezielte Fachregression das
zentrale Entwicklungstor ausdrücklich nicht.

Der unabhängige Vorabreview begrenzte die Materialzählung auf die sechs
beauftragten Codes und verlangte die tatsächliche Tokenweitergabe bis zum
Zusammenhangslauf. Der Abschlussreview hat die eingefrorenen eigenen
Produkt-, Test- und Kartenhunks vollständig gelesen und ohne offenen Befund
freigegeben. Auch die beiden kleinen Schlusskorrekturen — getrennte lokale
Zählvariablen und der genaue Kartentext für `values['count']` — wurden erneut
gelesen. Der getrennte Dokumentreview hat diesen Bericht, den RM327-Abschnitt
und die zugehörigen Registerzeilen ebenfalls freigegeben.

## Abnahmegrenze

Dies sind Prüfungen ohne Fenster, Renderer oder Leistungsmessung. Sie belegen
keine native Fensterabnahme und kein vollständiges Entwicklungstor.
Die erneuten Wächter und tatsächlicher
Commit-/Pushbeleg werden nach ihren eigenen Ergebnissen ergänzt.
