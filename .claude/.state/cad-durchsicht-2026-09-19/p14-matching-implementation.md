# P1.4 – räumliche Vorauswahl und unveränderte Zuordnungssemantik

Implementierter, für die unabhängige Endprüfung eingefrorener Stand.
Eigene Pfade:

- `app/core/perceive/matching.py`
- neuer zusammenhängender Matching-Abschnitt in `app/core/perceive/CLAUDE.md`
- neue `tests/test_spatial_matching.py`

`tests/test_matching.py` bleibt unverändert und wurde als bestehender
Verbrauchervertrag mitgeprüft. Root besitzt die tatsächlichen
1056-Flächen-Projektlebenszyklen; `policy_review` besitzt alle
Aufruferanschlüsse in Auswertung, lokaler Wahrnehmung und Vorbereitung.
Keine Bearbeitung von Website, ROADMAP, Merkmalsobergrenze oder fremden
Dateien. Kein Commit und kein Push durch diesen Unteragenten.

## Öffentliche Anschlüsse

```python
match(old, new, centre, diagonal, old_centre=None, *, check_cancelled=None)
resolve(saved, candidates, detected, centre, diagonal, *, check_cancelled=None)
```

Beide optionalen Callbacks sind `Callable[[], None] | None`; bestehende
Aufrufe behalten ihre Positionsparameter. Derselbe Operationsabbruch läuft
durch Vektoraufbereitung, Baumabfragen, kleine Kostenblöcke, vor/nach dem
Solver und bis vor das Ergebnis. Gespeicherte Antworten prüfen ihn vor und
während des Kandidatenvergleichs sowie vor ihrer Rückgabe. Eine erfolgte
Teilrechnung ergibt bei Abbruch keine Teilantwort.

## Gemeinsame Kostenformel

`feature_vector` bleibt unverändert: derselbe Körperbezug, dieselbe
Diagonale, dieselben Lage-/Achs-/Größenwerte. `_vector_costs` ist die einzige
produktive Herleitung der Positions-, Achs- und relativen Größenkosten.
Einzelpaar `cost`, vollständige `_cost_matrix`, selektive Paare und
gespeicherte Fingerabdrücke in `resolve` benutzen sie gemeinsam.

Dabei bleibt eine numerisch relevante historische Unterscheidung erhalten:
Die alte Skalarrechnung von `cost`/`resolve` benutzt `np.linalg.norm(v)`,
die alte Matrixrechnung `np.linalg.norm(v, axis=-1)`. `_vector_norm`
entscheidet am tatsächlich entstandenen Differenz-/Summenarray: eindimensional
bleibt Skalarreduktion, jede Batchform bleibt Batchreduktion. Auch ein
selektiver Einzelkandidat hat die Form `(1,3)` und rechnet somit wie die
entsprechende alte Matrixzelle. Es wird keine algebraisch neu zentrierte
Positionsformel für den Suchbaum eingeführt.

Die vollständige alte Formel und Ergebnisbildung stehen ausschließlich als
unabhängige Testreferenz in `complete_reference`; sie benutzen nicht den
neuen Kostenhelfer. Zusätzliche analytische Komponentenfälle belegen
Positionskosten 1, relative Größenkosten, richtungslose Achsen und gerichtete
Flächennormalen. Ein Vergleich von zwei neuen Produktaufrufern allein wäre
dafür kein unabhängiger Beleg.

## Konservative räumliche Vorauswahl

Der vorhandene träge `cKDTree` aus `core.deferred` erhält die bereits
gerundeten neuen Positionsvektoren. Er wird blockweise mit Maximumsnorm
(`p=inf`) abgefragt. Es gibt weder eine Nachbarzahlgrenze noch eine neue
fachliche Annahmetoleranz; jeder räumlich mögliche Kandidat wird mit der
unveränderten gemeinsamen Kostenformel geprüft. Unterschiedliche Arten
bleiben Strafpaare.

Die Suchhülle besitzt eine hergeleitete reine Rundungsreserve. Mit
`u=eps(float)/2` und `R=POSITION_TOLERANCE*MATCH_THRESHOLD` wird einmal
pro Aufruf `Fraction(R-Faktoren)/(1-u)^5` exakt gebildet und überprüft nach
oben in einen Float umgerechnet. Gemeint ist das Produkt der beiden
ursprünglichen Floatfaktoren als rationale Zahlen, nicht erst deren
gerundetes Floatprodukt. Der Exponent umfasst die Rundungen aus Division,
Wurzel, individuellem Quadrat und dem Übergang zur unabhängig gerechneten
Koordinatendifferenz der Baumabfrage. Im Bereich der festen Grenze R=0,08
sind diese Größen normal darstellbar. Eine positive Summe kann das
gerundete Quadrat einer einzelnen ausschlaggebenden Komponente nicht
verkleinern; winzige unterlaufende andere Komponenten verstecken deshalb
keinen räumlich ausgeschlossenen Kandidaten.

Der reale Gegenpunkt `(0.04800000000000001, 0.064, 0)` bleibt erhalten:
Die bisherige Kostenmatrix akzeptiert ihn mit 1,0, obwohl eine gewöhnliche
euklidische Baumabfrage mit Radius 0,08 ihn verlieren kann. Endgültige
Annahme bleibt ausschließlich `cost <= MATCH_THRESHOLD`. Nicht endliche
normierte Vektoren nehmen den bisherigen vollständigen Rechen-/Fehlerpfad,
statt durch den Suchbaum unbemerkt zu verschwinden.

## Zertifikat statt veränderter Gleichstandsentscheidung

Der erste selektive Durchgang bestimmt auf der **kleineren globalen
Solverseite** für jede Zeile Minimum, Zweitminimum und Partner. Bei mehr
alten als neuen Merkmalen ist dies die transponierte Sicht. Ein direkter
Weg ist nur erlaubt, wenn gleichzeitig gilt:

1. Jede Zeile dieser kleineren Seite besitzt einen angenommenen Partner.
2. Ihr bester Wert ist strikt kleiner als der zweitbeste Wert.
3. Alle gewählten Partner sind paarweise verschieden.

Der vorhandene globale SciPy-Solver findet dann in jeder ersten
Augmentierungsrunde das strikte Minimum auf einer noch freien Spalte.
Kein Alternierungspfad und keine Strafkostenarithmetik erzeugen einen
anderen Kontext. Das Zertifikat umfasst auch räumlich zusammenhängende
Raster mit vielen möglichen Nachbarn und nichtnulligen besten Kosten.
Es setzt keine getrennten Zusammenhangskomponenten voraus.

Die ausgewählten Paare werden in der ursprünglichen globalen
Zeilenreihenfolge verarbeitet. Ein zweiter selektiver Durchgang bestimmt
die Rivalen gegen die **zugeteilte** Kostenzahl; eindeutige optimale Paarung
ist kein Ersatz für die bestehende Mehrdeutigkeitsregel. Ein strikter
bester Treffer kann also weiterhin eine Rückfrage auslösen. Rivalen folgen
der ursprünglichen Spalten-/Kennungsreihenfolge.

Scheitert auch nur ein Zertifikatsbestandteil, wird die vollständige globale
Matrix mit derselben Strafe für abgelehnte Paare aufgebaut. Ein zweiter
selektiver Durchgang setzt darin die möglichen angenommenen Originalkosten.
Danach läuft derselbe globale Solver. Es gibt keinen Solver nur über den
Konfliktrest und keine eigenständige lokale Tie-Regel. Das bewahrt auch die
Reihenfolge verwaister IDs: Der bisherige Vertrag stellt unzugeteilte alte
Zeilen vor global zugeteilte, aber abgelehnte Strafpaare.

Der belegte Gegenfall bleibt deshalb unverändert: alte x-Lagen
`[0,1,1,1]`, neue x-Lagen `[0,0,1]`. Eine naive Komponentenzerlegung hätte
`old_1→new_2` gewählt, während der bisherige globale Kontext
`old_2→new_2` vergibt. Derselbe Sachverhalt wird in transponierter Form
geprüft. Der Rückfall erhält beide Male die ganze Matrixform.

## Arbeitsumfang und Grenzen

Die Kandidatenkosten werden nicht vollständig zwischengespeichert. Der
erste Durchgang hält lineare Minima-/Partnerfelder, der zweite bestimmt
Rivalen oder belegt die notwendige Rückfallmatrix. Baumabfragen und
Paarkosten bleiben mit `VECTOR_ROWS` blockweise begrenzt. Im dichten,
nicht zertifizierten Fall bleiben quadratischer Speicher und der globale
Solver bewusst bestehen; es gibt keine willkürliche Abschneidung.

Ein einzelner laufender nativer Baum- oder Solveraufruf wird nicht intern
unterbrochen; der Callback wird unmittelbar davor und danach geprüft.
Zwischen den eigenen Blöcken bleibt er durchgehend angeschlossen.
Die Größe dieser Aufrufe und die unveränderte `FEATURE_LIMIT_COUNT` gehören
zur späteren Release-Leistungsprüfung. Weder die 1056er Funktionstests noch
ihre normalen pytest-Laufzeiten sind eine Anhebung oder Leistungsfreigabe.

## Direkte Kern- und Statikbelege

Die roten Vorstufen wurden direkt im Werkzeugausgang festgehalten:

| Zustand | Direkter Ausgang |
|---|---|
| neue `match`-Abbruchfälle vor API-Erweiterung | Exit 1, 2 fehlgeschlagen; fehlendes Keyword |
| API am Eingang vorhanden | Exit 0, 2 bestanden |
| Raumweg/innerer Abbruch vor Umsetzung | Exit 1, 2 fehlgeschlagen / 13 bestanden; globale Matrix trotz isolierter Paare und fehlender innerer Abbruch |
| erste gemeinsame Matching-/Raumprüfung | Exit 0, 98 bestanden |
| verbundene Raster, Tie-, Schwellen- und echte Suchabbrüche | Exit 0, 117 bestanden |
| neuer gespeicherter-Antwort-Abbruch vor `resolve`-API | Exit 1, 1 fehlgeschlagen / 35 bestanden; fehlendes Keyword |
| vollständiger eigener Endlauf | Exit 0, **123 bestanden** |

Endprotokoll:
`C:/Users/rober/AppData/Local/Temp/solidon-spatial-matching-766ff8647d0e46b2a0807f088a97a8bb/final-focused.txt`.

Direkte Endbefehle und Ausgänge:

```text
python tools/affected_tests.py tests/test_matching.py tests/test_spatial_matching.py --run
Exit 0 — 123 passed
python -m ruff check app/core/perceive/matching.py tests/test_spatial_matching.py
Exit 0
python -m ruff format --check app/core/perceive/matching.py tests/test_spatial_matching.py
Exit 0
python -m mypy app/core/perceive/matching.py
Exit 0
git diff --check -- app/core/perceive/matching.py app/core/perceive/CLAUDE.md tests/test_spatial_matching.py
Exit 0
```

Die 40 neuen Fälle ergänzen die 83 bestehenden Matchingfälle: analytische
Kostenkomponenten, 1056 getrennte Paare, verbundene 1056er Raster in beiden
Richtungen ohne globale Matrixallokation, globale Gleichstände und gierige
Gegenfälle, rechteckige Ausgabeordnung, striktes Minimum mit ehrlichem
Rivalen, unabhängige vollständige Referenz an deterministischen gemischten
Kosten, mehrere Kandidatenblöcke, Randschritte per `nextafter` in
verschobenen Bezugsrahmen, nicht endliche Daten und Abbruch nach tatsächlicher
Baumabfrage, Paarkostenrechnung, Solverarbeit sowie gespeichertem Vergleich.

SHA-256 von `matching.py` beim Freeze:
`D47348C813D5273CFA4B2B396A18846DCD1AB819FCF2DB8D8A64F52A702D73CE`.

Die unabhängige Endprüfung durch `exact_transform_kernel` ist grün.
Seine unveränderten eigenen Sonden ergeben direkten Exit 0 mit 16
Prüfpunkten: globale Tie-ID/Orphan-Reihenfolge, isolierte kleinere Seite,
Konkurrenz, nichtnullige zertifizierte Minima einschließlich Transposition,
späte Blockminima und Gleichstände, Baumgrenze, NaN/Inf-Referenzweg sowie
echte Abbrüche in Paarkosten, Solver und `resolve`. Der erwartete Solverpfad
wurde jeweils funktional beobachtet; Eingabemerkmale blieben unverändert.
Der Endhash stimmt überein. Keine weiteren belegten Befunde.
Mathematische Prüfung und Abschluss stehen in `p14-review-notes.md`,
die unabhängige ausführbare Sonde in `p14-review-final-probe.py`.
Den globalen Gesamtgate und die drei Bearbeiterpakete führt Root zusammen.
Keine Fensterdatei oder Leistungsprüfung lief in diesem Paket.
