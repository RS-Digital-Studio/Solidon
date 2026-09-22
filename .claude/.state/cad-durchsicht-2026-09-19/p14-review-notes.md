# P1.4 — unabhängige Gegenprüfung der räumlichen Zuordnung

Lesender Stand zu `p14-entry-plan.md`, `matching.py`, den zuständigen Karten
und Bauplan §21.2/§21.3. Ausgangscommit: `69efc1cdf`. Installiert sind
SciPy 1.18.1 und NumPy 2.5.3. Keine Produktänderung, kein Benchmark, keine
Fensterdatei und keine vollständige Testsammlung. Die eigenen Sonden und
Ausgaben stehen neben dieser Notiz unter `p14-review-*`.

## Ergebnis und sichere Empfehlung

Räumliche Vorauswahl ist möglich, wenn sie nur beweisbar ausgeschlossene
Paare entfernt. Die anschließende Kostenformel, Schwellenbehandlung,
Rivalensuche und Ergebnisreihenfolge bleiben erhalten. Die allgemeine
Zerlegung in lokale Zuordnungsprobleme erhält zwar den mathematisch
optimalen Wert, aber nicht zwingend die bisher vergebenen Kennungen.

Der kleinste sichere schnelle Weg ist ein **Zertifikat an der kleineren
globalen Seite**. Es erfasst auch ein zusammenhängendes Raster mit vielen
räumlichen Nachbarn, sofern jeder alte Eintrag seinen eindeutigen Partner
hat. Scheitert das Zertifikat, übernimmt der vollständige bisherige globale
Solver einschließlich aller Strafzeilen und Strafspalten. Nur die verbleibende
Konfliktmatrix global zu lösen genügt nicht.

Der Numerikbearbeiter hat dieses Vorgehen bereits übernommen: ein erster
begrenzter Kostenpass sammelt Minima und Partner; bei Zertifikat reicht ein
zweiter Pass für die Rivalen, sonst füllt er die vollständige Strafmatrix.
Die Kostenformel wird dabei nicht kopiert.

## 1. Was die Komponentenzerlegung wirklich beweist

Sei `M=KIND_PENALTY`, `T=MATCH_THRESHOLD` und `r=min(n_old,n_new)`.
Kanten mit `c>T` werden vor dem Solver zu M. Jede vollständige rechteckige
Zuordnung hat die Kosten

```
r*M - Summe(M-c) über ihre akzeptablen Kanten.
```

Der zweite Term ist ein gewichtetes Matching ausschließlich im Graphen
der Kanten mit `c<=T`. Er zerfällt über dessen Zusammenhangskomponenten.
Da `M>T` gilt, lässt sich eine optimale lokale Teilzuordnung durch
Strafpaare vervollständigen; sonst gäbe es zwischen freien Knoten noch eine
verbessernde akzeptable Kante. Lokale rechteckige Solver mit demselben M
erreichen deshalb einen global optimalen Wert in reeller Arithmetik.

Dieser Beweis verlangt keine neue Kardinalitätsregel und keine unendlichen
Kosten. Er beweist aber keine identische optimale Paarung bei Gleichständen
und auch keine bestimmte Reihenfolge der verworfenen Strafpaare.

### Tatsächlicher Kennungswechsel durch einen Gleichstand

Gleiche Bohrungsart, Achse und Durchmesser; Körperbezug null, Diagonale 1:

```
alte x-Zentren: [0, 1, 1, 1]
neue x-Zentren: [0, 0, 1]
```

Die echte aktuelle Kostenformel ergibt null innerhalb der beiden Gruppen
und 12,5 dazwischen. Nach dem unveränderten Schwellenfilter:

```
     0  0  M
     M  M  0
     M  M  0
     M  M  0
```

Global meldet `match` **`old_2 -> new_2`**, komponentenweise dagegen
**`old_1 -> new_2`**. Die jeweilige Zuordnung steht in `mapping`, nicht in
`ambiguous`: Die bestehende Rivalensemantik betrachtet nur Alternativen
innerhalb derselben alten Zeile. Mehrere alte Zeilen mit demselben einzigen
neuen Kandidaten kann sie nicht symmetrisch ausdrücken.

Damit ist eine rein lokale Nachbildung der alten Tie-Regel allgemein
unmöglich: Dieselbe lokale Komponente aus drei alten und einem neuen Eintrag
bekommt je nach fremden globalen Strafpaaren eine andere gewählte alte ID.
Eine lokale Sortierregel kennt diesen Kontext nicht.

Bei einem anderen 3×3-Beispiel ändert sich nur die erste Wahl in einer schon
mehrdeutigen Kandidatenliste. Solche Reihenfolgen könnten als ausdrückliche
Vertragsänderung vereinheitlicht werden. Das behebt aber den vorherigen
Kennungswechsel nicht. Für diesen Abschnitt ist der globale Rückfall kleiner
und sicherer als eine neue Mehrdeutigkeitssemantik oder ein Cachewechsel.

### Selbst Grad eins kann die Reihenfolge ändern

4×3, allein `old_0 -> new_0` akzeptabel, alle anderen Paare kosten M:

- Global: `orphaned=(old_3, old_1, old_2)`.
- Nur akzeptable Komponente: `orphaned=(old_1, old_2, old_3)`.

Der bisherige Abschluss stellt unzugeteilte alte Zeilen vor zugeteilte
Strafpaare. Ein optionaler Grad-eins-Direktweg ist daher nur vollständig
reihenfolgetreu, wenn `n_old<=n_new` oder alle neuen Spalten gültig zugeteilt
sind. Der Numerikbearbeiter hatte dieselbe Grenze bereits benannt; die
unabhängige Sonde bestätigt sie.

## 2. Stärkeres Zertifikat für den Alltag

Zunächst dieselbe Orientierung wie beim globalen Solver wählen:

- `n_old<=n_new`: jede alte Zeile.
- `n_old>n_new`: jede neue Spalte, als Zeile der transponierten Matrix.

Das Zertifikat verlangt:

1. **Jede** Zeile dieser kleineren Seite hat mindestens einen akzeptablen
   Kandidaten; isolierte Zeilen werden nicht aus der Prüfung weggelassen.
2. Sie besitzt einen strikt billigsten akzeptablen Kandidaten.
3. Die ausgewählten Gegenpartner sind paarweise verschieden.

Dann ist die Summe aller Zeilenminima erreichbar und jede andere Paarung
teurer. Insbesondere erzwingt das die akzeptierte Paarung auch bei einem
verbundenen Kandidatengraphen. Es wird keine neue lokale Optimierungs-
bibliothek und kein wiederholter Solveraufruf zum Nachweis benötigt.

Auch der konkrete Float-Rechenweg ist hier abgesichert: Der untersuchte
SciPy-Solver beginnt jede neue kleinere Zeile mit unverändert nulligen
Spaltenpotentialen. Ihr striktes Minimum ist noch frei. Die erste Suchrunde
endet deshalb sofort dort. Nur diese Zeile und die Zielspalte werden
berührt; deren Potentialänderung ist eine Zahl minus dieselbe Zahl, also
null. Induktiv entsteht weder ein alternierender Pfad noch eine Auslöschung
mit M. Das gilt für nichtnullige Zeilenminima ebenso wie für das Raster mit
Kosten null. Die zur installierten Version passende Primärquelle wurde
nachgelesen: [SciPy v1.18.1, rectangular_lsap.cpp](https://raw.githubusercontent.com/scipy/scipy/v1.18.1/scipy/optimize/rectangular_lsap/rectangular_lsap.cpp).

Voraussetzung sind dieselben gespeicherten Float-Paarkosten. Ein zusätzlicher
Abstand über `AMBIGUITY_FLOOR` ist ein zulässiges konservativeres Zertifikat;
der direkte Ablaufbeweis selbst benötigt nur ein striktes Minimum. Die
bestehende Rivalenprüfung darf nicht entfallen: Bei transponierter
Zuordnung ist ein gewähltes Spaltenminimum nicht notwendig das Zeilenminimum
dieser alten ID.

"Alle Zeilen **mit Kandidaten**" wäre für diesen konkreten Ablaufbeweis
zu schwach. Eine zusätzlich verarbeitete isolierte Strafzeile kann die
Potentiale und den globalen Kontext ändern. Solche Fälle gehen vollständig
zur Referenz zurück, sofern nicht das engere Grad-eins-Zertifikat greift.

## 3. Konservative Raumfiltergrenze

Zu indizieren sind genau die relativen Positionen aus `feature_vector`,
einschließlich seiner Zentrierung und `max(diagonal, EPS_GEOM)`. Ein
algebraisch umgestellter Weltkoordinatenabstand ist numerisch nicht dieselbe
Eingabe. Die Positionskosten sind nichtnegativ; überschreiten sie die
Annahmeschwelle, kann keine Achsen- oder Maßkomponente das Paar retten.

Eine ungepufferte euklidische Baumabfrage ist dennoch falsch:

```
delta = (0.04800000000000001, 0.064, 0)
alte Matrix-Positionskosten = 1.0
query_ball_point(..., r=0.08) = kein Kandidat
```

Die unabhängige Sonde enthält weitere Richtungen mit demselben Fehler.
Die alte Kostenrechnung akzeptiert den Grenzfall; der Baum darf ihn nicht
vorher entfernen.

### Kleine arithmetische Hülle

Mit `u=2^-53`, `P=POSITION_TOLERANCE`, `T=MATCH_THRESHOLD`, `R=P*T`
und normalen Zahlen nahe der Ausschlussgrenze folgt aus dem akzeptierten
gerundeten Quotienten:

```
norm_float <= R/(1-u)
sqrt(sum_float) <= R/(1-u)^2
abs(delta_float_i) <= R/(1-u)^(5/2)
```

Die positive Summe der gerundeten Quadrate ist nicht kleiner als ein
einzelner Summand. Rückgang zur exakten Koordinatendifferenz und eine
unabhängige Rundung des Baumabstands sind konservativ durch
`R/(1-u)^5` abgedeckt. Bei den aktuellen Konstanten nahe R=0,08 sind diese
entscheidenden Rechnungen normal; unterlaufende winzige andere Komponenten
können keinen großen Abstand verbergen.

Diese eine Grenze lässt sich mit Standardbibliotheks-`Fraction` exakt
berechnen und gerichtet nach oben in Float umrechnen. Aktueller Wert:
**`0.08000000000000006`**. Eine `p=inf`-Abfrage dieser Würfelhülle enthält
alle akzeptablen euklidischen Paare; anschließend entscheidet ausschließlich
die ursprüngliche vollständige Kostenformel. Die Probe bestätigt sämtliche
gefundenen Grenzfälle mit dieser Hülle. Es ist keine geänderte Fach- oder
Fertigungstoleranz. Nichtendliche normierte Vektoren gehen zum bisherigen
Rechenpfad, statt still aus der Kandidatenmenge zu verschwinden.

## 4. Kosten-, Schwellen- und Rivalenvertrag

- Alle Komponenten der bisherigen Paarkosten gemeinsam benutzen. Die
  skalare `cost`-Norm ist historisch eine 1D-Norm, `_cost_matrix` verwendet
  eine Reduktion über die letzte Achse. Algebraische Gleichheit allein
  erlaubt keinen ungeprüften Austausch dieser Float-Auswertungen am Rand.
  Insbesondere liest `resolve` die skalare Referenz. Falls gemeinsame
  Helfer eingeführt werden, muss der bisherige Normmodus erhalten oder die
  Änderung ausdrücklich belegt werden.
- Vor dem Solver `c>T` weiterhin in M umwandeln; `c==T` bleibt zulässig.
  Ein Rohwert 1,01 ist bei einem zugeteilten Wert 0,9 kein Rivale, obwohl er
  unter dessen numerischem Rivalenlimit läge: Der alte Ablauf prüft die
  bereits geschwellte Matrix. Die Sonde hält diesen Fall fest.
- Rivalen beziehen sich auf den **wirklich zugeteilten** Wert, nicht auf
  das billigste Element der Zeile. Die tatsächlichen Zentren
  alt `[0.032,-0.04]`, neu `[0,0.096]`, Diagonale 1 ergeben
  `[[0.4,0.8],[0.5,1.7]]`. Global wird die Kreuzpaarung gewählt. Ein
  einzelner Nächster-Nachbar-Schritt verlöre einen zulässigen Partner.
- Alte/neue Reihenfolge bleibt die Einfügereihenfolge ihrer Kennungen.
  Unsortierte Baumtreffer dürfen weder Tie-Priorität noch die Reihenfolge
  der Rivalenliste bestimmen. Globale Zeilenindices vor dem Abschluss
  wieder in dieselbe Reihenfolge bringen.
- `taken` enthält wie bisher nur tatsächlich gemappte neue IDs. Ein bloß
  mehrdeutiger zugeteilter Kandidat ist dadurch noch nicht verbraucht.
- Dichte oder konkurrierende Fälle dürfen nicht durch eine feste Anzahl
  Nachbarn abgeschnitten werden. Der vollständige Referenzrückfall bleibt
  erlaubt und muss abbrechbar angebunden sein. Die Releasegrenze für
  Merkmalsanzahl und Speicherbedarf bleibt unverändert.

## 5. Nachweise und Abnahmegrenze

- `p14-review-probe.txt`: eigener anfänglicher Sondenfehler, Exit 1 wegen
  fehlendem `Feature.params`; kein Produktbefund.
- `p14-review-probe-02.txt`: Exit 0, vollständige kleine topologische Suche
  findet den tatsächlichen Kennungswechsel.
- `p14-review-cases.txt`, `p14-review-cases-02.txt` und
  **`p14-review-cases-03.txt`**: jeweils Exit 0. Letzter Stand enthält echte
  Featurekosten, rechteckige Zuordnung, Wechsel der ID, reine Wahlreihenfolge,
  Grad-eins-Verwaisungsreihenfolge, abgeschwellte Rivalen und Grenzpunkte
  einschließlich der konservativen Baumhülle.

Es gibt keinen gemessenen Leistungs- oder Speichergewinn aus diesen Sonden.
Die funktionale Integration mit mehr als tausend realen Merkmalen, Cache,
Herkunft, Wiederöffnung und History liegt beim Elternagenten. Ebenso ersetzt
diese Notiz keine Gegenprüfung des erst anschließend implementierten Codes.

Die frühen Sonden mit gepatchtem `_cost_matrix` belegen den oben benannten
Ausgangscommit. Der nachfolgende neue Matcher besitzt bewusst andere interne
Einstiege. Für dessen unabhängigen Abschluss ist
`p14-review-final-probe.py` angelegt; sie verwendet die vorhandene
historische `complete_reference` aus `tests/test_spatial_matching.py` und
vergleicht Featureeingaben am wirklichen Matcher. Während der laufenden
Produktänderungen wurde sie nicht ausgeführt.

## 6. Unabhängiger Abschluss des implementierten Stands

Nach dem ausdrücklichen Freeze des Bearbeiters wurden `matching.py`, die
neue `test_spatial_matching.py` und der zugehörige Kartenabschnitt erneut
gelesen. Der implementierte Direktweg verwendet das oben bewiesene
kleinerseitige Zertifikat. Er setzt keine beliebige lokale Tie-Regel ein.
Fehlende oder konkurrierende Minima führen zum vollständigen globalen
Solverkontext. Auch Zweitminima aus späteren Kostenblöcken und die
transponierte Zuordnung werden korrekt gesammelt.

Die arithmetische Würfelhülle ist genau mit `Fraction` und gerichteter
Floatkonversion umgesetzt. Der selektive Kostenweg behält auch bei einem
einzigen Kandidaten ein Batcharray; `_vector_norm` erhält dagegen für
`cost` und `resolve` die historische 1D-Reduktion. Im Ergebnisabschluss
werden dieselben geschwellten Rivalen, die zugeteilte Referenzkostenzahl,
globale Indexreihenfolge und ausschließlich tatsächlich gemappte neue
Kennungen verwendet. Nichtendliche Vektoren nehmen den ursprünglichen
vollständigen Fehler-/Strafkostenweg.

**Eigener direkter Prozess: Exit 0**, Protokoll
`p14-review-final-probe.txt`. Alle 16 Prüfpunkte bestanden:

1. Echter globaler Gleichstand behält dieselbe alte ID.
2. Grad-eins-Fall behält auch die Reihenfolge verwaister IDs.
3. Eine isolierte Zeile auf der kleineren Seite benutzt den vollständigen Kontext.
4. Konkurrierende Kandidaten werden nicht gierig einzeln zugeordnet.
5. Strikte, nichtnullige freie Minima umgehen den Solver.
6. Derselbe Nachweis gilt nach Transposition.
7. Ein Minimum im späteren Kostenblock wird gefunden.
8. Dasselbe gilt nach Transposition.
9. Ein gleiches Minimum erst im nächsten Block bleibt ein wirklicher Tie
   und benutzt den vollständigen Solver.
10. Der zuvor vom ungepufferten Baum verlorene Schwellenpunkt bleibt erhalten.
11. NaN in der Position bewahrt den ursprünglichen Fehlerweg.
12. NaN in der Achse bewahrt denselben Fehlerweg.
13. Eine unendliche Position liefert dieselbe Verwaisungs-/Frischauskunft.
14. Abbruch nach einer echten Paarkostenrechnung liefert kein Ergebnis.
15. Abbruch nach dem echten globalen Solver liefert kein Ergebnis.
16. Abbruch während des echten Vergleichs einer gespeicherten Antwort wird weitergereicht.

Die Vergleiche verwenden die bereits vorhandene unabhängige vollständige
Testreferenz, keinen weiteren selbstgebauten Solver. Bei den zehn
Zuordnungsvergleichen wurde zusätzlich geprüft, ob genau der erwartete
globale Solverweg benutzt beziehungsweise ausgelassen wurde und die
Eingabemerkmale unverändert blieben.

Endhash SHA256 `app/core/perceive/matching.py`:
`D47348C813D5273CFA4B2B396A18846DCD1AB819FCF2DB8D8A64F52A702D73CE`.

Endhash SHA256 `tests/test_spatial_matching.py`:
`2E3DC9BFC75314AF6933CEE1CA4B0C2EDBAF783C43E4ABE31C9165F76BD8E341`.

Der Bearbeiter bestätigt 123 bestandene Matching-/Raumfälle und
Ruff/Format/mypy jeweils Exit 0. Sein `final-focused.txt` wurde gelesen;
dies ist kein eigener wiederholter Testlauf des Reviewers.

**Kein weiterer belegter Fehler im geprüften Stand offen.** Die zu Beginn
gefundenen Planfallen werden durch den konservativen Rückfall beziehungsweise
die arithmetische Raumhülle vermieden. Lebenszyklus, echte Geometriekorpora,
Gesamttor und Releasegrenze bleiben die gesonderten Nachweise des
Elternagenten. Durch den Reviewer wurde keine Produktdatei geändert.
