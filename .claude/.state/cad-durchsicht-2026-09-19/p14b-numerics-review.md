# P1.4b – unabhängiger mathematischer Abschlussreview

Gelesener eingefrorener Stand: `matching.py`, SHA-256
`C5A448641B00D24A2C095D1A82AE57D2C84550C39600B09F25CBE920D5636CD6`,
`test_matching_competition.py`, die erhaltene Kosten-/Solverreferenz in
`test_spatial_matching.py` und `p14b-numerics-implementation.md`.
Maßstab ist der endgültige `p14b-contract-review.md`.
Keine Produktänderung durch den Reviewer; keine Wiederholung der 153 bereits
gelaufenen Fälle, keine Fenster- oder Leistungsprüfung.

## Konkurrenzrechnung

Kein zusätzlicher Befund in der neuen Hüllen-/Graph-/Anspruchsrechnung:

- `_hull_limits` benutzt die vollständige Solverantwort einschließlich
  Strafpaaren. Die genaue Summe der ausgewählten binären Floatwerte minus
  der genauen Summe der Minima ist auch bei transponierter Rechteckmatrix
  richtig; die Reihenfolge der summierten Paare ist dafür unerheblich.
  Die Umwandlung von `m_r + U − L` in die größte nicht größere Floatzahl
  trifft exakt den notwendigen Kantenentscheid. Keine Toleranz wird erhöht.
- Jedes gewählte Paar bleibt in der Hülle: Sein Mehrbetrag über dem
  Zeilenminimum ist höchstens die Summe aller nichtnegativen Mehrbeträge.
  Auch eine numerisch nicht optimal gewählte, aber vollständige zulässige
  Solverantwort liefert eine sichere obere Grenze U. Die Hülle verliert
  dadurch keine wirklich optimale Alternative.
- `_global_support` richtet ungewählte Kanten alt→neu und gewählte neu→alt.
  SCC, Vorwärtsreichweite ab freien alten und Rückwärtsreichweite ab freien
  neuen Knoten erfassen die kardinalitätserhaltenden Zyklen und Wege.
  Ein augmentierender Weg wird ausdrücklich abgewiesen. Der aktuelle
  Produktdeckel zusammen mit der Strafdominanz bleibt Voraussetzung für
  die Verbindung zum ursprünglichen vollständigen Solverkontext.
- Der matrixfreie Weg verlangt weiterhin sämtliche strikt besten Minima
  der kleineren Seite und verschiedene Partner. Er macht keine sichere
  Einzelpaarbehauptung aus einem nur örtlichen Minimum. Auch dort prüft
  der zweite Kostenpass unzugeteilte alte Ansprüche gegen die festen
  Besitzergrenzen.
- `_open_claims` bildet Referenzoberwerte ausschließlich aus A. R und Q
  werden vor dem Schluss berechnet und wachsen nicht durch zuvor
  hinzugefügte Rivalen. `_close_claims` öffnet die globalen Wechselbereiche,
  alten Zeilenrivalen und unzugeteilten Q-Ansprüche; geöffnete A-Besitzer
  durchlaufen anschließend ihre vollständigen eigenen Ansprüche. Ein
  außen fest gebliebenes Ziel kann deshalb nicht in einer offenen Liste
  stehen. Q-Nähe allein öffnet keinen ansonsten freien sicheren Partner.
- Alte IDs werden disjunkt veröffentlicht. Ein einzelnes Ziel mit mehreren
  alten Ansprüchen bleibt ausdrücklich offen. Ursprüngliche Partner stehen
  nur zuerst in der Anzeigeliste; ihre Reihenfolge ist kein Identitätsbeleg.
  `require_injective` greift vor beiden Übernahmewegen.
- Die neuen Schleifen geben den vorhandenen Abbruchcallback weiter und
  verändern keine Features oder Quellnetze. Die eigene Testsammlung deckt
  die begrenzten Graphhelfer auch durch vollständige kleine Enumeration
  gegen ihre mathematische Mengenaussage ab; sie vergleicht nicht bloß zwei
  Aufrufe derselben Implementation.

Die konservative Restbreite ist dokumentiert: Hall-Defizite können U−L
vergrößern; kardinalitätserhaltender Support beweist nicht gleiche Kosten
jeder enthaltenen Paarung. Daraus entsteht keine höhere Produktionsgrenze
und kein Leistungsnachweis.

## Belegter gemeinsamer Resolverfehler

Der ursprüngliche Einzelresolver prüfte die berechneten Kosten nicht auf
Endlichkeit. `best > MATCH_THRESHOLD` und `rival <= limit` sind bei NaN
beide falsch. Dadurch konnte ein ungültiger aktueller Kandidat selbst
gewinnen oder als nicht vergleichbarer Rivale einen anderen Kandidaten
scheinbar eindeutig machen. Das verletzt die Wiederverwendungsgrenze für
gespeicherte Gruppen, obwohl die neue Konkurrenzrechnung selbst korrekt
arbeitet.

Die unabhängige enge Sonde liegt unter
`C:/Users/rober/AppData/Local/Temp/solidon-p14b-matcher-review-49abf3e6327c46f198935ee8ff8743ea/resolve_probe.py`.
`resolve-red.txt` hält den unmittelbaren **Exit 1** auf obigem Hash:

| Kandidaten | Unabhängiges Soll | Beobachtet |
|---|---|---|
| gültiger Einzelkandidat | `good` | `good` |
| gültiger Kandidat, danach NaN-Rivale | keine Wiedererkennung | `good` |
| NaN-Rivale, danach gültiger Kandidat | keine Wiedererkennung | `unknown` |

Der Fix wurde auf dem eingefrorenen Hash
`D76E399DB89F5B14BE3EE4EEED03F2F56543DF3D66855358C4ABDF7BE2F2FC95`
unabhängig nachgelesen. Er verwendet die gemeinsame
`match_records.valid_fingerprint(..., legacy=True)`-Prüfung und den
vorhandenen Vektor-/Kostenweg. Körperbezug, aktuelle Lage, vorhandene
Richtung und berechnete Werte müssen endlich und tatsächlich vergleichbar
sein. Ein nicht vergleichbarer gleichartiger Rivale sperrt die gesamte
Wiedererkennung; er wird weder zu einem schlechten Kandidaten noch
übersprungen. Historische optionale Abdruckfelder behalten ihren Vertrag.

Die unveränderte Sonde wurde einmal wiederholt: `resolve-after.txt`,
unmittelbarer **Exit 0**. Der gültige Einzelkandidat bleibt `good`; beide
Reihenfolgen mit NaN-Rivale liefern nun `None`. Das ursprüngliche rote
Protokoll bleibt erhalten. In diesem abgegrenzten Nachreview ist kein
weiterer Befund offen. Die 117 vom Owner gemeldeten gezielten Fälle und
seine statischen Prüfungen wurden nicht erneut ausgeführt.
