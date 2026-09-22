# P1.4b – unabhängiges Review des Konkurrenzvertrags

## Umfang und Ergebnis

Rein lesendes Review von `p14-competing-identities-plan.md`, insbesondere
Abschnitten 1/2, gegen den aktuellen `matching.py`-Vertrag und die bisherigen
P1.4-Gegenbeispiele. **Keine Tests, Sonden oder Produktänderungen.** Die
Tabellen unten sind mathematische Gegenbeispiele, keine neu beobachteten
SciPy-Ausgaben. Ihre spätere Ausführung muss die wirklichen Batchkosten und
Fließkommagrenzen gesondert festhalten.

Der vorgesehene gemeinsame, injektive Antwortabschluss ist richtig. Der
vorgeschlagene Anlass und Gruppenschluss sind noch nicht vollständig:

- Beim Öffnen eines bisher festen alten Anspruchs müssen dessen weitere
  möglichen Ansprüche erneut berücksichtigt werden. Ein Schluss allein
  über bereits vorhandene `ambiguous`-Listen verliert Alternativen.
- Selbst wiederholte Besitzer-Spaltenvergleiche mit der bisherigen lokalen
  Kostenschranke übersehen gleichwertige alternierende Gesamtzuordnungen.
  Solche Gleichwertigkeit kann sogar **ohne irgendeinen bisherigen Seed**
  bestehen. Ein unverändert leerer Rivalenbestand ist daher kein Zertifikat.
- Eine exakte notwendige Kostenhülle aus unabhängigen Zeilenminima kann den
  konservativen Gesamtgraphen wesentlich verkleinern. Sie benötigt weder
  einen neuen Kostensolver noch duale Potenziale. Sie beweist keine
  Gleichwertigkeit jeder enthaltenen Kante.
- Reine alternierende Graphreichweite kann darin weitere unveränderliche
  Paare erkennen. Der anschließende Umgang mit den bewusst vorsichtigen
  bisherigen lokalen Rivalen bleibt eine getrennte fachliche Frage.

## 1. Kleine Gegenbeispiele

`P` bedeutet den vorhandenen Strafwert nach Abweisung; nur Kosten ≤ 1 sind
geometrische Kandidaten. Die Rivalengrenze ist unverändert
`B(c)=1.25 c+0.05`. Alle Merkmale können dieselbe Art, Achse und Größe
haben, so dass nur der eindimensionale Positionsabstand beiträgt.
Die angegebenen Positionen sind in Einheiten `0.08 · Körperdiagonale`.

### A. Öffnen eines Besitzers muss dessen weitere Ansprüche öffnen

| Alt \ Neu | x | y |
|---|---:|---:|
| a | 0.25 | 0.75 |
| b | 0.25 | P |
| c | P | 0.75 |

Realisierung: neu x=0, y=1; alt a=0.25, b=−0.25, c=1.75.
Die beiden abgewiesenen Rohabstände sind 1.25 und 1.75.

Eine optimale Ausgangszuordnung ist `a→x, c→y`, Kosten 1.0; b ist zunächst
unzugeteilt. a hat keinen Zeilenrivalen, denn 0.75 > B(0.25)=0.3625.
b konkurriert gleich gut um x und öffnet a/b.

Nun muss **a→y** nachgeführt werden. Es konkurriert gleich gut mit c→y.
Die Alternative `b→x, a→y` kostet ebenfalls 1.0. Ohne Nachprüfung des
neu geöffneten a bleibt c fälschlich fest. Die richtige offene Anspruchsmenge
ist `{a,b,c}`, mit `a:{x,y}`, `b:{x}`, `c:{y}`.

Ein einmaliger Scan der anfänglich verwaisten Zeilen und anschließend nur
Zusammenhang über vorhandene Listen genügt nicht. Bei der Gruppenbildung
die ursprünglichen Paare und Kosten zunächst als unveränderliche Referenz
behalten; erst nach Abschluss aus dem veröffentlichten Mapping entfernen.

### B. Alternierende Gleichwertigkeit ohne lokalen Konfliktanlass

| Alt \ Neu | x | y |
|---|---:|---:|
| a | 0.125 | 0.375 |
| b | P | 0.75 |
| c | 0.5 | 1.0 |

Realisierung: neu x=0, y=0.5; alt a=0.125, b=1.25, c=−0.5.
Der abgewiesene Rohabstand ist 1.25. Die Annahmeschwelle 1.0 bleibt
einschließlich ihres Randes gültig.

`M={a→x,b→y}` und `M'={c→x,a→y}` kosten beide **0.875**.
Dennoch öffnet die vorgeschlagene Regel ausgehend von M nichts:

- a→y liegt mit 0.375 über B(0.125)=0.20625;
- b hat neben y keinen angenommenen Kandidaten;
- c→x liegt mit 0.5 über B(0.125);
- c→y liegt mit 1.0 über B(0.75)=0.9875.

Alle drei alten Identitäten müssen offenbleiben. Eine bloße
Besitzer-Spaltentoleranz oder ein Abschluss erst nach einem vorhandenen
Zeilenrivalen kann das nicht leisten. Hier gleicht der Gewinn eines
verschobenen Anspruchs den Verlust an anderer Stelle aus.

### C. Ein einzelnes freies Minimum ist kein Festhaltebeweis

| Alt \ Neu | x | y |
|---|---:|---:|
| a | 0 | 0.5 |
| b | 0.5 | 1.0 |

Realisierung: neu x=0, y=0.5; alt a=0, b=−0.5.
Das Paar a→x ist sogar in seiner Zeile **und** Spalte strikt am billigsten.
Beide vollständigen Zuteilungen kosten trotzdem 1.0. Die Fortführung von a
ist ohne zusätzlichen Identitätsbeleg nicht fest.

Das P1.4a-Zertifikat betrifft sämtliche Minima der kleineren Solverseite
mit verschiedenen Partnern. Es darf nicht zu einem lokalen Ein-Paar-
Zertifikat abgeschwächt werden. Eine wirkliche native Historienabbildung
oder gemeinsam bestätigte Entscheidung wäre ein anderer Beleg; ein
geometrischer Nullabstand allein ist keine solche Historie.

### D. „Nahe unverändert“ braucht eine präzise Grenze

| Alt \ Neu | x | y |
|---|---:|---:|
| a | 0 | 0.03125 |
| b | 0.03125 | 0 |

Die eigene strikte Minimumzuordnung ist injektiv. Trotzdem erklärt schon
der vorhandene `AMBIGUITY_FLOOR=0.05` beide Zeilen für mehrdeutig.
„Bisherige Zeilenrivalen unverändert“ und „alle unveränderten nahen Zwillinge
ohne Frage“ sind deshalb nicht gleichzeitig erfüllbar.

Präzise Zusage für dieses Paket: **Keine zusätzlichen Rückfragen allein
wegen akzeptierter räumlicher Nachbarschaft.** Ein bisher klar getrennter
unveränderter Rasterfall bleibt still. Innerhalb der bereits bestehenden
Unterscheidungsgrenze bleiben Fragen bestehen, sofern kein wirklicher
zusätzlicher Identitätsbeleg vorliegt. Keine neue Nullkosten-Ausnahme.

## 2. Eine kleinere konservative Kostenhülle

Die vorhandene geschwellte Matrix C auf die kleinere, vollständig
zugeteilte Solverseite orientieren: q Zeilen, p Spalten, q ≤ p.
Für jede Zeile r sei `m_r=min_j C[r,j]`, und

`L = Σ_r m_r`, `U = Σ_(r,j)∈M C[r,j]`, `G = U−L`.

M ist die **vollständige** vorhandene Solverzuordnung, einschließlich
Strafpaaren. Nicht `MatchResult.mapping` verwenden: Dort fehlen bereits
mehrdeutige und abgewiesene Paare. L ist eine Untergrenze, weil jede
vollständige Zuteilung genau einen Eintrag jeder kleineren Zeile braucht.
U ist jedenfalls eine obere Grenze durch eine tatsächlich mögliche
Zuteilung, auch wenn der numerische Solver einen optimalen Tie anders wählt.

Wenn eine vollständige Zuteilung die Kante `(r,j)` enthält, kostet sie
mindestens `L−m_r+C[r,j]`. Folglich gilt:

**`C[r,j]−m_r > G` schließt diese Kante aus jedem globalen Optimum aus.**

Das ist nur eine notwendige Bedingung. Unterhalb der Grenze dürfen
Spaltenkonkurrenz und alternierende Kosten weiterhin eine Rolle spielen.
Die Hülle ersetzt keine bewiesene optimale Zuordnung.

### Numerischer und fachlicher Anschluss

- Die schon berechneten Floatkosten sind die Referenz; keine zweite Norm-
  oder Geometrieformel. Für U/L die binären Floatwerte exakt summieren,
  etwa als `Fraction`; keine gewöhnliche Subtraktion großer Strafsummen.
- Pro Zeile `m_r+G` exakt bilden und auf die größte darstellbare Floatzahl
  **≤** diesem Wert abrunden. Danach ist der vektorisierte Floatvergleich
  gegen diese Grenze exakt derselbe Mengenentscheid. Das vermeidet eine
  rationale Rechnung je Paar. Eine Konversion auf die nächstgelegene Zahl
  braucht gegebenenfalls einen Schritt `nextafter(...,−∞)`.
- Die endgültigen Geometriekanten verlangen weiterhin `C[r,j]≤1`.
  Strafwerte werden nie zu wählbaren Identitäten. Nichtendliche Werte folgen
  dem vorhandenen Fehlervertrag und sind kein Abweisungsbeweis.
- U und L beziehen sich auf denselben ursprünglichen vollständigen Kontext.
  Keine heimliche neue Kardinalitäts- oder Strafkostenregel.
- Die bisherigen lokalen Zeilenrivalen sind zusätzliche fachliche
  Kandidaten, auch wenn ihre gemeinsame Fortführung teurer wäre. Sie
  dürfen nicht mit dieser globalen Optimalitätshülle weggefiltert werden.

Beim unveränderten Raster gilt U=L. Nur wirkliche Minimumkanten können
über die Hülle einen globalen Konkurrenzfall verbreitern. Eine lokale
Nullkostenkonkurrenz nimmt ihre konkurrierenden alten IDs mit; weiter
entfernte unveränderte Rasterpaare bleiben isoliert. Beispiel B ergibt
auf der kleineren Seite die Zeilen x/y mit L=0.5 und U=0.875;
G=0.375 erhält insbesondere c→x und damit den zuvor übersehenen Wechsel.

### Verbleibende Breite bei Strafpaaren

Eine vollständig strafbelegte kleinere Zeile bläht G **nicht** auf:
gewähltes P und Zeilenminimum P heben sich exakt auf. Ein Hall-Defizit kann
G dagegen um P aufblähen, weil einzeln billige Zeilen denselben Partner
brauchen. Beispiel:

```
      x  y  z
 a    0  P  P
 b    0  P  P
 c    P  0  P
```

Hier sind alle Zeilenminima null, aber eine vollständige Zuordnung muss ein
Strafpaar enthalten: L=0, U=P. Bei angeschlossenen dichten Bereichen kann
die Hülle dann nahezu alle angenommenen Kanten behalten. Das gilt auch,
wenn der verursachende Bereich geometrisch getrennt von vielen sonst klaren
Paaren liegt. Die globale Hülle bleibt **sicher**, aber möglicherweise breit.
Keine Lokalitätszusage daraus ableiten und im ersten Schritt keine neuen
Komponenten-Strafkontexte erfinden. Der Produktdeckel/Release-Nachweis bleibt.

## 3. Gewählte alternierende Graphgrenze ohne neuen Kostensolver

Die gewählte Eingrenzung benötigt keine dualen Kosten oder neue
Optimierungsbibliothek. Ausgangspunkt ist die vorhandene angenommene
partielle Zuordnung M und die Kostenhülle H:

- ungewählte Hüllenkanten richten sich **alt→neu**;
- gewählte Paare richten sich **neu→alt**.

Bei maximaler angenommener Paarzahl bestehen die Unterschiede zweier
gleich großer Matchings aus alternierenden Zyklen und geraden
alternierenden Wegen. Die Wegenden liegen auf derselben bipartiten Seite;
ein Ende ist in M frei. Daraus folgen drei mögliche Wechselbereiche:

1. gerichtete Zyklen, feststellbar durch starke Zusammenhangskomponenten;
2. gerichtete Reichweite ab unzugeteilten alten Knoten;
3. umgekehrte Reichweite ab unzugeteilten neuen Knoten.

Ein gewähltes Paar außerhalb dieser Bereiche kann in **keinem** Matching
gleicher maximaler Paarzahl innerhalb H wechseln. Damit kann es erst recht
in keinem globalen Optimum wechseln. Das ist der gesuchte sichere Bereich
außerhalb alternierender Konkurrenz, obwohl der ungerichtete Hüllengraph
weiter verbunden sein kann. Innerhalb dieser Bereiche bleibt die Hülle
konservativ; die Graphprüfung behauptet keine Kostengleichheit.

Voraussetzung ist maximale angenommene Paarzahl. Beim aktuellen Deckel
dominiert P=1e6 den gesamten angenommenen Kostenanteil deutlich; der
vorhandene vollständige Solver liefert diesen Umfang. Wer die Graphgrenze
als eigenständiges Zertifikat verwendet, kann außerdem das Fehlen eines
augmentierenden Wegs frei-alt→frei-neu prüfen. Bei widersprechendem Befund
nicht trotzdem feste Paare freigeben. Keine eigene Reparatur des Solvers.

Diese Graphanalyse ist kleiner als ein neuer Residualkostensolver mit
Potenzialen. Sie braucht eigene funktionale Belege für beide rechteckigen
Richtungen, Zyklen, Wege und isolierte Strafknoten, bevor sie implementiert
als fertig gilt. Eine enthaltene Alternative kann weiterhin teurer sein:
Die Reichweite belegt gleiche Paarzahl, nicht gleiche Kostensumme. Bei
Hall-Defiziten kann auch dieser Abschluss breit bleiben.

## 4. Eindeutiger Besitzer-/Anspruchsschluss

Die folgenden Mengen werden aus den festen Originalkosten aufgebaut, bevor
irgendein Paar aus M entfernt oder eine Nutzerantwort übernommen wird.
Sie sind eine lokale Berechnung, kein zusätzliches persistiertes Modell.

**A – konservativer globaler Partnersupport.** Enthält alle angenommenen
M-Paare. Eine ungewählte Kante aus H kommt hinzu, wenn ihre beiden Enden
in derselben starken Zusammenhangskomponente liegen, beide ab einem freien
alten Knoten erreichbar sind oder beide einen freien neuen Knoten erreichen
können. Das sind genau die oben beschriebenen kardinalitätserhaltenden
Wechselwege in H. Alle global optimalen Partnerschaften sind in A enthalten;
über die Kostengleichheit zusätzlicher Paare wird nichts behauptet.

**Feste Referenzen statt wachsender Schranken.** Für jeden alten bzw. neuen
Knoten mit incidenten A-Kanten den größten dort vorkommenden Originalwert
festhalten: `u_old(a)=max C[a,j]` und `u_new(j)=max C[a,j]`.
Bei einem isolierten festen Paar ist das seine ursprüngliche Kostenzahl.
Bei global offenen Partnern umfasst der Wert auch die anderen erhaltenen
Komplettierungen. Das ist konservativ und erhält die ursprünglichen
Zeilenrivalen unabhängig davon, welcher globale Tie zuerst gewählt wurde.
Diese Referenzen wachsen anschließend **nicht** mit den lokalen Rivalen.
Wo A leer ist, gibt es keinen solchen Referenzwert; P wird keiner.

**R – lokale Zeilenansprüche.** Für a mit definiertem `u_old(a)` alle
angenommenen Kanten `C[a,j]≤B(u_old(a))` behalten. Dazu gehören insbesondere
sämtliche ursprünglichen Zeilenrivalen und das gewählte Paar. Die etwas
größere Grenze bei global offenen Zeilen vereinigt deren mögliche
Referenzsituationen ausdrücklich; sie ist keine neue Formtoleranz.

**Q – zusätzliche Ansprüche gegen bereits mögliche Besitzer.** Für a alle
angenommenen Kanten zu j mit definiertem `u_new(j)` und
`C[a,j]≤B(u_new(j))` vormerken. Diese Kanten öffnen einen ansonsten sicher
untergebrachten alten Anspruch **nicht** allein durch Nähe. Sie werden nur
für einen unzugeteilten oder bereits anderweitig geöffneten alten Anspruch
aktiv. Genau diese Aktivierungsgrenze schützt unveränderte freie Partner.

**Anfangs offene alte Knoten:**

1. alle alten Beteiligten eines nichttrivialen Wechselbereichs von A,
   insbesondere auch allein durch Beispiel B und nicht erst nach einem
   bisherigen Zeilenrivalen;
2. alle alten Knoten mit einem lokalen R-Anspruch auf einen anderen als
   ihren gewählten Partner;
3. unzugeteilte alte Knoten mit wenigstens einem Q-Anspruch.

**Fixpunkt:** Für jeden neu offenen alten Knoten a sämtliche Kanten
`A(a) ∪ R(a) ∪ Q(a)` in die offene Kandidatenmenge nehmen. Für jedes so
beanspruchte neue Ziel j alle in A belegten möglichen alten Besitzer
aufnehmen; dazu gehört stets sein bisheriger M-Besitzer, falls vorhanden.
Neu hinzugekommene alte Knoten durchlaufen denselben vollständigen Schritt.
Ein Ziel ohne solchen Besitzer ist ein aktueller freier Kandidat. Ein
ungeöffneter alter Knoten wird nicht allein deshalb aufgenommen, weil er
auch räumlich nah bei j liegt und anderswo seinen freien Partner hat.

Die Menge wächst monoton über endlich viele vorhandene IDs/Kanten;
Referenzkosten, Annahmeschwelle und A bleiben fest. Eine Warteschlange und
Besuchsmengen genügen. Beispiel A nimmt beim Öffnen von a auch dessen
y-Anspruch und dadurch c mit. Beispiel B öffnet ohne lokalen Seed.
Außenliegende feste Ziele können am Ende nicht in einer offenen Liste
stehen: Ihr Besitzer wäre durch denselben Abschluss aufgenommen worden.

Danach die offenen Gruppen aus dieser abgeschlossenen bipartiten Auskunft
bilden und erst jetzt die entsprechenden M-Paare aus dem Ergebnis-Mapping
entfernen. Außerhalb bleiben die gewählten Paare erhalten. Sie wechseln in
keiner global optimalen Komplettierung und werden von keinem nach diesem
Vertrag aktivierten lokalen Anspruch getroffen.

Dieser Schluss ist bewusst konservativ: Die Hülle kann nichtoptimale
Komplettierungen enthalten; deren feste Referenzoberwerte können zusätzliche
Fragen auslösen. Das ist die benannte Nachfragegrenze. Es ist keine Freigabe
für beliebige spätere bedingte Alternativen nach einer Nutzerwahl.
Solche neuen Ziele müssten wieder gemeinsam geprüft werden und dürfen
außerhalb reservierte Paare nicht still auflösen.

## 5. Minimaler MatchResult- und Antwortvertrag

Die vorhandenen vier Felder reichen; ihre Aussagen müssen präziser werden.

| Feld | Erforderliche Aussage |
|---|---|
| `mapping` | Freigegebene alte→neue Paare. Gültige IDs, angenommene Kanten, injektive Zielwerte. Kein noch offener Konkurrenzanspruch wird hierdurch entschieden. |
| `ambiguous` | Alte Identitäten, deren Fortführung bzw. Nichtfortführung offen ist. Auch **ein** neuer Kandidat ist zulässig, wenn mehrere alte IDs um ihn konkurrieren. Nichtleere aktuelle Kandidatenlisten; keine Ziele, die außerhalb der abgeschlossenen Gruppe bereits fest reserviert sind. |
| `orphaned` | Alte Identitäten, die in der aktuellen freigegebenen Antwort nicht fortgeführt werden. Keine Identität hier ablegen, deren Fortführung innerhalb der offenen Konkurrenz noch möglich ist. |
| `fresh` | Neue Merkmale ohne derzeit freigegebenen alten Namen: weiterhin alle neuen IDs außerhalb der Zielmenge von `mapping`, einschließlich offener Kandidaten. Der alte Docstring „niemand erwartet“ ist dafür zu stark. |

Die alten IDs bilden eine disjunkte vollständige Aufteilung in Mapping,
offene Identität und Nichtfortführung. Offene neue Kandidaten können mehreren
alten IDs gehören, freigegebene neue Ziele höchstens einer. Die Gruppe
entsteht aus der abgeschlossenen bipartiten Auskunft; keine zweite dauerhafte
ID-Sammlung. Reservierte alte Namen bleiben bis zum Ende für Neubenennung
gesperrt, einschließlich bewusst nicht fortgeführter und offener Namen.

`ambiguous={a:(x,),b:(x,)}` bedeutet: Die **Identität** von x ist offen.
Es bedeutet weder zwei mögliche Kopien von x noch eine automatisch lösbare
Einzelauswahl für a. Die Gruppe kann a→x, b→x oder keine Fortführung
bestätigen. Nur eine referenzierte alte ID herauszufiltern und damit zu
bevorzugen wäre erneut eine unbelegte Entscheidung.

Abschnitt 2 des Plans trifft den richtigen Abschluss:

1. Alle Entscheidungen zunächst lokal sammeln, einschließlich ausdrücklicher
   Nichtfortführung. Keine Änderung an `matched.mapping` nach jeder Teilfrage.
2. Nur Gruppenpaare anbieten, existierende aktuelle Ziele und Außenreservierungen
   berücksichtigen. Keine fehlende Antwort als Verwerfen interpretieren.
3. Den gesamten Entscheidungssatz auf zulässige Paare und Injektivität prüfen.
   Eine Auswahl a→x,b→x bleibt ungültig; niemals „letzte Antwort gewinnt“.
4. Erst danach Mapping, offene/verwaiste IDs und frische Namen gemeinsam
   aktualisieren. Namen und Erzeuger müssen dieselbe freigegebene Zuordnung
   lesen. Eine abschließende Vertragsprüfung gehört vor **beide** Wege
   `inherit_originators` und `apply_mapping`.
5. Gespeicherte Fingerabdrücke sind gemeinsam zu prüfende Vorschläge.
   Übereinstimmung eines Fingerabdrucks ist noch keine Reservierung.
   Abbruch veröffentlicht weder halbe Gruppenantworten noch halbe Objekte.

Eine vollständig unreferenzierte offene Gruppe braucht keine Frage, erbt
aber auch keine beliebige alte ID. Wirkliche native Historienbelege oder
gemeinsam bestätigte Antworten dürfen reservieren, müssen jedoch selbst
injektiv sein. Eine native Viele-zu-eins-Historie wäre gerade keine
automatisch eindeutige Identität.

## Empfehlung für den nächsten Schritt

Den Plan nicht nur um einen einmaligen Gegenscan unzugeteilter Zeilen
ergänzen. Zuerst A–D als unabhängige funktionale Fälle festhalten, danach
die globale notwendige Kostenhülle und den vollständigen Konkurrenzabschluss
umsetzen. Hüllengrenzen exakt aus den vorhandenen Floatkosten bilden.

Die alternierende Graphgrenze und der explizite Fixpunkt aus Abschnitt 4
gehören zum gewählten Schnitt. Sie bewahren feste Paare außerhalb der noch
möglichen Wechsel und aktivierten lokalen Ansprüche. Bei Hall-Defiziten
kann der konservative offene Bereich trotzdem sehr groß werden. Ohne die
Kostenhülle wären bei einem einzigen örtlichen Konflikt sogar alle
akzeptiert verbundenen Rastermerkmale betroffen.

Keine neue duale Optimierungsrechnung, keine Nachbarzahlgrenze, keine
pauschale Nullkostenfreigabe und keine Behauptung, offene Hüllenkandidaten
seien bereits als exakt gleich teuer bewiesen. Ein späterer engerer
Optimalsupport-Nachweis ist ein eigener möglicher Ausbau.
