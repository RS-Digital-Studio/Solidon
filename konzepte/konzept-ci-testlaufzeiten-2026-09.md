# Kürzere CI-Läufe bei unverändertem Prüfvertrag

Stand: 24.09.2026. Von Robert beauftragt: erst dieses Konzept, danach die
vollständige Umsetzung. Der laufende Umsetzungs- und Abnahmestand gehört in
`ROADMAP.md`; dieses Dokument beschreibt Entscheidungen und Nachweise.

## 1. Ziel und Ausgangslage

Die Rückmeldung der CI soll früher kommen, ohne Zusicherungen, Plattformen
oder Fehlerausgänge zu verlieren. Grundlage sind Bauplan §31 (Messung),
§37.2 (Auslieferung) und §38 (Fehler und Isolation) sowie die Trennung von
Entwicklung und Release in `AGENTS.md`.

Gemessen im erfolgreichen Lauf
[35982366247](https://github.com/RS-Digital-Studio/Solidon/actions/runs/35982366247),
Commit `0895c4a69eb6adcb03834ee7f005087dcc3c2c6d`:

| Schritt | Zeit |
|---|---:|
| Kerntests Ubuntu | 25:38 |
| Kerntests macOS ARM | 41:33 |
| Kerntests Windows | 31:35 |
| Windows-Fensterdateien, anschließend | 42:10 |
| Davon `test_ui.py`, 659 Fälle | 11:05 |
| Abhängigkeiten je Plattform | 0:37 bis 1:14 |

Die Windows-Gruppe sammelt 92 Dateien. Zwei laufen als plattformübergreifende
Fensterverträge, die anderen 90 seriell. Rund 38 Minuten liegen innerhalb
der pytest-Sitzungen. Abhängigkeitsinstallation und Sammlung sind deshalb
nicht der erste Hebel. Die damaligen rund 79 Minuten bis zum Paketbau sind
die Vergleichsbasis, keine unveränderliche Zeitvorgabe für andere Runner.

Die Kernsuite wurde in der Durchsicht vom 24.09.2026 lokal je Test gemessen
(16 575 Fälle, `-n 8`, JUnit): 3036 s Rechenzeit, davon ein einziger Fall
319 s — `test_seal_geometry[12.0]`, eine Wandmessung, die seit dem
VTK-Ausbau (RM-050) jeden Strahl gegen jedes Dreieck rechnete. Die zehn
längsten Fälle trugen 22 Prozent. Ein Fall dieser Länge bestimmt, wann ein
Kernjob frühestens fertig ist, gleich wie viele Worker er hat.

## 2. Verbindliche Regeln

| Kennung | Zusage | Dauerhafte Absicherung |
|---|---|---|
| CI-01 | Kein Test fällt durch die Aufteilung weg oder läuft in zwei Gruppen — weder bei den Fenstergruppen noch bei den Teilen der Kernsuite. Neue Dateien werden automatisch aufgenommen. | Partitionstests mit unbekannten Dateien, vollständiger Vereinigung und leeren Schnittmengen; `--ci-shard` gegen die echte Sammlung; Teilmatrix gleich `0 … N−1` |
| CI-02 | Jeder Fensterdateilauf erhält einen frischen Prozess; Qt-Abbau und Garbage Collection bleiben erhalten. | Prüfung der gestarteten Befehle und Prozessausgänge |
| CI-03 | Fenster laufen nur im bisherigen Release-Umfang; Leistung bleibt lokal beim Release, `rendered` bleibt aus CI ausgeschlossen. | Workflow- und Marker-Verträge, einschließlich `tests_only` |
| CI-04 | Kernmatrix und native Typprüfung bleiben auf den bisherigen Plattformen. Die zwei speziellen Fensterverträge bleiben auf Windows, Linux und macOS. | Prüfung der tatsächlichen Jobmatrix und Aufrufe |
| CI-05 | Paketbau braucht sämtliche erforderlichen erfolgreichen Qualitäts-, Kern- und Fensterjobs. Abbruch, leere Auswahl, Sammlungsfehler oder fehlender Bericht ergeben kein Grün. | Negative Fälle des Runners und Prüfung der Paketabhängigkeiten |
| CI-06 | Berichte nennen Auswahl, echte Prozessausgänge, Testzahlen und Zeiten; auch bei Fehlern werden vorhandene Berichte hochgeladen. | Berichtstests und `always()`-Artefaktschritte |
| CI-07 | Gemeinsame Vorbereitung verändert keine Eingabe eines anderen Tests. Determinismus vergleicht weiterhin zwei unabhängig gebaute Ergebnisse. | Kopien für veränderliche Daten, unveränderte Zusicherungen und gezielte Gegenproben |
| CI-08 | Laufzeitgewinn wird nur für einen abgeschlossenen vergleichbaren Lauf behauptet. Lokales Entwicklungstor und Release-Abnahme bleiben getrennt. | Nachweis mit Commit, Plattform, Befehl, Exit und Berichtspfad |

Änderungen an diesen Zusagen benötigen eine bewusste Fortschreibung dieses
Konzepts und der zuständigen Regeldatei. Tests dürfen nicht gestrichen,
abgewählt oder abgeschwächt werden, um eine Laufzeitvorgabe zu erreichen.

## 3. Zielaufteilung der CI

Unabhängig starten ein gemeinsamer Stiljob, die bisherige Kernmatrix und
beim Release die Fensterjobs. Ruff und Format werden einmal ausgeführt;
mypy bleibt auf jeder Plattform, weil es Plattformzweige unterschiedlich
prüft — einmal je Plattform, nicht je Teil.

Die zwei plattformübergreifenden Fensterverträge bekommen eine eigene Matrix.
Die übrigen Windows-Dateien werden in drei Gruppen verteilt, jeweils seriell
mit einem Prozess je Datei. Die Kernsuite läuft je Plattform in drei Teilen:
Jeder Teil sammelt die ganze Suite und behält mit `--ci-shard I/N` nach der
Markerwahl seine Dateien; mypy läuft einmal je Plattform im Teil 0. Die
Worker eines Teils verteilen mit `--dist worksteal`: lokal an Teil 0/3 mit
vier Workern in beiden Reihenfolgen 354 → 206 s und 213 → 160 s. Über die
ganze Sammlung ergeben die drei Teile dieselben 16 669 Fälle wie ein Lauf
ohne Teilung, keinen doppelt und keine Datei geteilt (24.09.2026). Beide
Aufteilungen teilen dieselbe Verteilung (`tools/ci_shards.py`). Eine
gemeinsame Paketabhängigkeit wartet auf alle erforderlichen Jobs. Es gibt
keinen spekulativen Paketbau und keine Änderung an Signierung oder
Veröffentlichung.

Die Auswahl stammt weiterhin aus Pytests Fixture-Graphen und Markern.
Je eine versionierte Laufzeittabelle für Fenster und Kern beeinflusst
ausschließlich die Reihenfolge und Verteilung, niemals die Mitgliedschaft;
neu erzeugt wird sie aus den JUnit-Berichten eines abgeschlossenen Laufs. Neue oder umbenannte Dateien
bekommen eine konservative Ersatzschätzung und werden immer aufgenommen.
Längste Dateien werden zuerst der bisher leichteren Gruppe zugeordnet;
gleiche Zeiten werden über den Pfad aufgelöst. Beide Gruppen berechnen
denselben vollständigen Plan. Veraltete Zeitschätzungen kosten höchstens
Balance, niemals Abdeckung.

Der bestehende isolierte Läufer wird für diesen CI-Pfad erweitert, statt
eine zweite Shell-Schleife mit eigener Fehlerzählung zu pflegen. Er schreibt
je Datei JUnit und ein Protokoll sowie eine strukturierte Gesamtübersicht.
Ein fehlendes oder beschädigtes JUnit-Ergebnis ist bei Exit 0 ein Fehler.
Nichtnull bleibt auch dann ein Fehler, wenn vorher Tests bestanden haben.
Die Kerntests erhalten ebenfalls JUnit und `--durations`. Die Ausgabe jedes
Fensterprozesses steht zugleich im CI-Protokoll, je Datei als einklappbare
Gruppe, eine rote Datei als Anmerkung am Lauf, die Übersicht im
Schrittbericht: Ein Bericht, der nur als Artefakt existiert, fehlt genau
dann, wenn der Job an seiner Frist endet.

Der Versionswächter ohne Constraints läuft weiter wöchentlich. Handstarts
können ihn ausdrücklich zuschalten; standardmäßig wird er nicht zusätzlich
zum eigentlichen Auftrag gestartet. Die Beschreibung von `tests_only` nennt
die tatsächlichen drei Prüfplattformen und verspricht keinen Intel-Mac-Lauf,
den die bisherige Kernmatrix nicht enthält.

## 4. Aufräumen der Tests

### 4.1 Große Fensterdatei

`test_ui.py` wird entlang fachlicher Bereiche aufgeteilt. Gemeinsame Fixtures
und Hilfen kommen in ein Testhilfsmodul; importierte Testfunktionen dürfen
nicht erneut gesammelt werden. Vor und nach dem Umzug werden Fallnamen samt
Parametern und Markern verglichen, nur der Dateipfad darf sich ändern.
Auch Referenzen anderer Tests und die Bereichskarte ziehen nach.

Im gemeinsamen Arbeitsbaum werden bereits vorhandene fremde Änderungen
erhalten. Während jemand dieselben Funktionen bearbeitet, werden diese
Abschnitte nicht verschoben. Stabile Themen können zuerst herausgelöst
werden; ein vollständiger Umzug ist kein Selbstzweck.

### 4.2 Statische Prüfungen

Quelltexte, ASTs und extrahierte Übersetzungsschlüssel werden innerhalb einer
Prüfsitzung gemeinsam gelesen. Der Cache gehört zu den Testhilfen, nicht in
die Anwendung. Tests mit veränderten Quellen erhalten frische Eingaben.
Kataloge bleiben einzeln geprüft. Wo xdist einen Cache je Worker duplizieren
würde, wird die gemeinsame Extraktion in einer zusammenhängenden Prüfung
genutzt. Ausschlussverzeichnisse werden vor dem Traversieren übersprungen.

### 4.3 Geometrie und UI-Vorbereitung

Identische Bausteinvorgaben werden für Merkmals- und Determinismusverträge
gemeinsam vorbereitet; zwei unabhängige Bauten bleiben die Untergrenze.
Werte aus dem Prüfling ersetzen keinen unabhängigen Sollwert.

Reine Anzeige- und Zustandstests erhalten kleine, eindeutig geeignete Szenen,
statt für jede Zusicherung eine STL einschließlich Erkennung neu zu importieren.
Die Import-, Erkennungs-, Vorschau- und Anschlussprüfungen behalten ihren
echten Weg. Veränderliche Fenster, Sitzungen und Szenen werden nicht global
geteilt. Welche Fälle geeignet sind, wird am vollständigen Testinhalt geprüft.

Garbage Collection, native Fensterfreigabe und Eventloop-Abbau werden zunächst
nur gemessen. Ohne reproduzierbaren Nachweis wird daran nichts verkürzt.
Weitere Kandidaten wie PHP-Server oder native B-Rep-Kopien werden erst nach
einem belegten relevanten Zeitanteil umgestellt.

### 4.4 Ein Ausreißer wird an seiner Ursache behoben

Ein einzelner langer Fall ist zuerst eine Frage an den Code, nicht an die
Aufteilung: Er bestimmt das Ende seines Jobs, und dieselbe Rechnung wartet
beim Kunden. Der Test selbst wird dafür nicht verkleinert. Die Wandmessung
aus §1 wählt seit dem 24.09.2026 die Dreiecke je Strahlgruppe räumlich vor
(`geom/mesh.ray_hits_batch`); jedes gerechnete Paar trägt dieselben Bits wie
zuvor, belegt durch einen bitgleichen Vergleich, drei konstruierte Fälle mit
Gegenprobe und den vollständigen Bausteinnachweis (35 von 35, unveränderte
Ergebnisse). Der Fall fiel lokal von 319 s auf 24 bis 34 s.

## 5. Umsetzung und Abnahme

1. Konzept und dauerhafte Verweise anlegen; Anfangsstand der betroffenen
   Dateien und aktuelle Testauswahl sichern.
2. Bericht und deterministische Aufteilung am isolierten Läufer bauen.
   Kleine echte Kindprozesse prüfen Erfolg, Fehler, Timeout, leeren Lauf,
   fehlenden Bericht und Abbruch nach erfolgreicher Testmeldung.
3. Workflow umstellen; Vertragsprüfungen lesen genaue Jobblöcke statt zufälliger
   globaler Texttreffer. Negative Varianten müssen die Wächter auslösen.
4. Statische Mehrfacharbeit und Bausteinaufbau reduzieren. Betroffene
   Kernprüfungen vorher/nachher mit Dauerauswertung vergleichen.
5. Stabile UI-Themen herauslösen und geeignete Anzeige-Fixtures verkleinern;
   Sammlung auf gleiche Fälle, Parameter, Marker und Fixture-Auflösung prüfen.
6. Betroffene Kern-/Strukturtests, Ruff, Format und mypy prüfen; vor dem Commit
   das gemeinsame Entwicklungstor für den tatsächlich gemeldeten Stand.
7. Beim nächsten autorisierten Release die gesamte Fenstergruppe und die
   bisherige Plattformmatrix fahren. Erst deren erfolgreiche Berichte belegen
   die Release-Abnahme und den realen CI-Zeitgewinn.

Ohne Releaseauftrag werden weder ein Release-Lauf noch Paketbau oder
Veröffentlichung ausgelöst. Eine noch nicht gefahrene Fenster- oder
CI-Laufzeitabnahme bleibt ausdrücklich offen, auch wenn ihre Infrastruktur
und die Entwicklungstests bereits fertig sind.

## 6. Erwarteter Nutzen und Grenzen

Die Entkopplung allein ergibt aus dem Ausgangslauf eine rechnerische Wartezeit
von ungefähr 47 statt 79 Minuten bis zum Paketbau; dann bestimmt macOS mit
seinem Kern den kritischen Pfad. Mit drei Kernteilen je Plattform, drei
Windows-Fenstergruppen und dem behobenen Ausreißer rechnen die Tabellen je
Teil 906 s lokale Kernzeit und je Fenstergruppe 793 s Windows-Zeit; auf die
Runner des Ausgangslaufs übertragen sind das etwa 15 Minuten für einen
macOS-Kernteil und 18 Minuten für eine Fenstergruppe, jeweils mit
Einrichtung. Das sind Planwerte ohne Garantie. Mehr Runner reduzieren
Wartezeit, nicht automatisch gesamte Rechenzeit — jeder Teil installiert und
sammelt für sich. Solange das Repository privat ist, laufen ohnehin keine
Jobs; die Rechenzeit zählt erst im öffentlichen Release-Fenster, und dort
kostet sie nichts. Rechenzeit sinkt durch vermiedene Mehrfacharbeit und
behobene Ausreißer, deren Wirkung gesondert gemessen wird.
