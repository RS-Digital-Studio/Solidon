# P1.4b – integrierte Antwort-, Auswertungs- und Oberflächengrenze

## Basis und Abgrenzung

P1.4a ist mit `d483e1477` und dem Fortschrittsnachweis `ee16040e7`
committet und nach `origin/main` gepusht. Das erfolgreiche Entwicklungstor
steht in `solidon-cad-spatial-final-09bbe40b46b145739c314f68cdbd0705`:
12.737 bestanden, 26 übersprungen, Ruff/Format/mypy jeweils Exit 0.
Der davor fehlgeschlagene Lauf bleibt als solcher erhalten; die Korrektur
betraf den veralteten Abbruchparameter eines Testdoubles.

P1.4b ersetzt die bisher zufällige Identität in Konkurrenzgruppen durch
vollständige, körperbezogene Entscheidungen. Der mathematische Vertrag,
die unabhängige Gegenprüfung und die Antwortenstruktur stehen in
`p14b-contract-review.md`, `p14b-numerics-review.md` und
`p14b-answer-contract.md`. Der gemeinsame Matcher und Resolver bleiben die
einzige geometrische Kostenquelle.

## Root-Anschluss

- `match_decisions.py` bildet vollständige Zusammenhangsgruppen und prüft
  jede Wahl gegen den gesamten aktuellen Anspruchsgraphen. Kein Kandidat
  gehört gleichzeitig einer Gruppe und einem freigegebenen Außenpaar.
- Eine gespeicherte Gruppe wird vollständig geometrisch und hinsichtlich
  ihrer Anspruchskanten wiedererkannt. Explizite Nichtfortführung bleibt
  gespeichert. Ungültige oder nicht unterscheidbare Gruppen fragen erneut.
- Vorhandene Gruppen haben Vorrang vor früheren `legacy`-Einzelantworten.
  Der spätere Verlust eines Gruppenbelegs aktiviert keine ältere Antwort.
- `_answer_matches` hält Zuordnungen, Befunde und Aufzeichnungen lokal,
  bis alle Gruppen eines Körpers entschieden sind. Die Auswertung sammelt
  zusätzlich sämtliche Körperantworten vor der Operationsveröffentlichung.
- Die Rückfrage trägt Körpernamen, alten Bezug und die Folge der
  Nichtfortführung. Die Vorschau enthält wirkliche aktuelle Geometrie,
  Merkmale und Originaldreiecke. Alte Ausgabehashes reisen dort nicht mit.
- Die UI zeigt die Frageausgabe ausschließlich vorübergehend im Viewport,
  wartet auf die aufgebaute Szene und entwertet Fragen bei Projektwechsel,
  neuem Auftrag, Abbruch und Fensterabbau. Fensterfälle wurden geschrieben,
  ausschließlich statisch geprüft und nicht ausgeführt.
- Der native allgemeine Neuwahlweg bleibt ausdrücklich offen: Geometrisch
  konkurrierende verwendete native Bezüge halten an; Netzantworten sind
  kein pauschaler Topologiebeleg. `carried_face_slots` aus P2.1 überträgt
  Filamente und ist kein allgemeiner Feature-ID-Nachweis.

## Belegte Nachbesserungen

Die unabhängige Antwortprüfung fand eine akzeptierte Teilgruppe, einen
bereits reservierten ungewählten Kandidaten und einen NaN-Rivalen, der eine
Antwort freigab. Reproduktionen bleiben in `p14b-answer-review.md` und den
zugehörigen Sonden erhalten. Die Gruppengrenzen und der gemeinsame Resolver
sind vorwärts korrigiert. Zuletzt waren 19 reine Entscheidungstests sowie
12 echte Antwort-/Mehrkörperfälle grün. Frühere rote Entwürfe enthielten
außerdem falsche Test-API-Annahmen; diese wurden am tatsächlichen Aufrufer
korrigiert, keine fachlichen Zusicherungen gestrichen.

Die Folgecache-Sonde liefert einen weiteren echten Fehler:
`p14b-follow-cache-two-claims.txt`, direkter Exit 1. Zwei alte Bohrungen
bei Y ±3 mm werden zwei neue bei X ±3 mm. Bei vertauschter vollständiger
Wahl bleibt der Namenssatz gleich; der warme Folgecache setzt seine
Markierung fälschlich weiterhin bei X = −3 mm, der frische Lauf bei +3 mm.
Der erste Sondenentwurf mit einem alten Anspruch bewies diesen Fehler
nicht und endete zusätzlich an einer falschen Diagnose-ID; er bleibt
gesondert in `p14b-follow-cache-red.txt` und zählt nicht als Produktbeleg.

Der enge Fix bindet deshalb die tatsächlich veröffentlichten Merkmale
über den gemeinsamen Featurecodec in den Objekthash ein. Der Rohkörpercache
bleibt von Rückfrageantworten unabhängig. Der vollständige Test führt echte
Bohrungen, warme Folgeauswertung, gespeicherte Wahl, Undo/Redo und Wiederöffnung
mit Plattencache zusammen. Der integrierte Nachlauf mit Auswertung,
Antworten, Abbruch und den 1056-Flächen-Lebensläufen besteht **104 Fälle**,
direkter Exit 0. Die unveränderte unabhängige Cache-Sonde ist ebenfalls grün:
`p14b-follow-cache-two-claims-green.txt`, Exit 0. Beide Rohkörper kommen
weiter aus dem Cache; die Markierung rechnet nach anderer Wahl neu.

Der Undo-Teil fand zusätzlich, dass bereits bestätigte Gruppen ohne den
gerade zurückgenommenen Verbraucher übersprungen wurden. Die Grenze steht
jetzt vor einer neuen Frage, nicht vor der Wiedererkennung: Gültige
gespeicherte Entscheidungen gelten weiter, ungeklärte unreferenzierte
Gruppen bleiben ungefragt frisch. Der ursprüngliche Undo-Sollwert bleibt
im Test bestehen. Das gemeinsame Entwicklungstor folgt nach dem Freeze.

## Parallelbereich und Prüfgrenze

Die andere Sitzung erhält P2.5-Vorbereitung ausschließlich unter
`konzepte/nachweise-cad-p2-5/`; der Prompt liegt in
`prompt-parallel-p2-5.md`. P2.7 hat dort belastbare Machbarkeitsnachweise,
aber keinen abgeschlossenen Produktionsanschluss. `website/` bleibt
unangetastet. Keine Release-, Fenster- oder Leistungsprüfung ist erfolgt.

`prepare_competition_gate.py` friert die ausdrücklichen eigenen Pfade ein.
Das gemeinsame Entwicklungstor und der private Commit folgen erst auf den
vollständig grünen integrierten Stand; bisher ist P1.4b nicht committet.

## Erster gemeinsamer Torlauf

`solidon-cad-competition-final-a6dc3c5d55474c549c8459fdc368a757` endet mit
direktem Exit 1: 2 fehlgeschlagen, 12.968 bestanden, 26 übersprungen,
553,89 Sekunden. Ruff, Format und mypy jeweils Exit 0. Zwei Prüfanschlüsse
werden vorwärts korrigiert: Der reine Schließablauf-Test führt die neue
Rückfrage-Abbruchmethode in seiner Attrappe nicht mit; der Verpackungstest
verlangt ein zum Entwicklungsstand aktuelles lokales Release-Manifest.
Das alte gebaute Manifest bleibt unverändert, der echte Manifestprüfer wird
stattdessen mit einem isolierten aktuellen sowie manipulierten Beispiel
geprüft. Dieser rote Lauf bleibt erhalten und wird nicht als grün umgedeutet.

## Gemeinsamer Entwicklungsnachweis P1.4b

Gate `C:\Users\rober\AppData\Local\Temp\solidon-cad-competition-final-789c0cf656654dc395e84d2ce8513a4d`: 12971 bestanden, 26 übersprungen. Kernsammlung, Ruff, Format und mypy jeweils direkter Exit 0. Produktcommit `fe17cd3bc6e04c8463fb234fe5b89f4f7aa92b24` umfasst nur die 36 ausdrücklichen eigenen Pfade. Fenster-/Leistungsprüfungen wurden nicht ausgeführt. Der native Neuwahlanschluss bleibt P1.4c. Push mit Exit 0; Remote/main und lokales HEAD sind als `859b75e0ee0d081c8339313757666ac674d845b1` bestätigt. Der Dokumentationsnachlauf besteht 152 Fälle mit Exit 0. Die separate Manifestkorrektur trägt `930ccbbc531156abb7894c531fd1826d1160187a`. Die Einzelwerte stehen in `p14b-published.json`.
