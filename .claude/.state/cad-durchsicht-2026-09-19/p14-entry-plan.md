# P1.4 – Einstieg nach dem Formabweichungspaket

Lesender Stand während der unabhängigen P1.6-Gegenprüfung; keine Umsetzung.

## Tatsächlicher heutiger Anschluss

`matching.match` erzeugt eine volle alte×neue Kostenmatrix über
`_cost_matrix`, ersetzt Werte oberhalb `MATCH_THRESHOLD` durch
`KIND_PENALTY`, führt die gemeinsame ungarische Zuordnung aus und prüft die
Rivalen jeder zugeteilten Zeile. `cost` ist die vorhandene Einzelpaarreferenz;
`test_matching.py` vergleicht schon alle Matrixelemente mit dieser Formel.
Position wird im eigenen Körperbezug normiert, Achsen und gerichtete
Flächennormalen sind verschieden. Die P1.6-Trägernachführung bleibt dieselbe.

`scene.evaluate.FEATURE_LIMIT_COUNT = 1000` begrenzt sowohl den nativen
Übernahmezweig als auch die Netzerkennung vor dem Anschluss. Ein neuer
Algorithmus nur unterhalb von `matching.match` hebt diese Schranke noch
nicht auf. Weitere Verbraucher, besonders `relations`, begründen heutige
Arbeitsmengen ebenfalls mit dieser Grenze. Allein die Kostenmatrix zu
beschleunigen beweist deshalb keine höhere tragfähige Gesamtgrenze.

## Vorgesehener enger Weg

1. Bestehende Ergebnissemantik als Referenz sichern: unverändert, verschoben,
   verschiedene Arten, Größen-/Achsgrenzen, rechteckige Zuordnung,
   verschwundene/neue Merkmale, wirklich symmetrische und dichte Fälle.
2. Mit dem bestehenden SciPy/NumPy-Satz vorfiltern. Nur Kandidaten verwerfen,
   deren nichtnegative Positionskomponente die Annahmeschwelle sicher
   überschreitet. Numerische Randfälle müssen erhalten bleiben; keine
   neue fachliche Erkennungstoleranz und keine bloße Nächster-Nachbar-Wahl.
3. Zusammenhangskomponenten des zulässigen bipartiten Kandidatengraphen
   unabhängig zuordnen, solange derselbe globale Annahme- und
   Rivalenvertrag bewiesen bleibt. Fehlende Kandidaten sind verwaist/frisch;
   Kollisionen mehrerer alter Ansprüche brauchen weiterhin die gemeinsame
   Zuordnung. Dichte Komponenten dürfen nicht still abgeschnitten werden.
4. Die vorhandene Kostenformel gemeinsam benutzen. Keine zweite Formel in
   einem schnellen Sonderweg. Funktionale Referenzvergleiche und
   Abbruchweitergabe bis zu jedem tatsächlichen Auswertungsaufrufer.
5. Über tausend Merkmale funktional mit tatsächlicher Szene, Erzeugern,
   Quellen/Trägern, Cache, Wiederöffnung und Historie prüfen, ohne diese
   Fälle als Leistungsnachweis auszugeben.

## Noch zu entscheidende Eintrittsbedingung

Die Konzeptforderung, `FEATURE_LIMIT_COUNT` anhand Laufzeit und Spitzenbedarf
zu erhöhen, bleibt an die ausdrückliche Release-Prüfung gebunden. Während
der Entwicklung werden weder heimlich Laufzeiten gemessen noch aus einem
grünen Funktionstest eine höhere sichere Obergrenze behauptet. Vor einer
Anhebung müssen auch die übrigen Verbraucher und der dichte Gegenfall
abgenommen sein. Bis dahin ist eine funktionale Algorithmusverbesserung
ein implementierter Teil von P1.4, keine fertige Gesamtfreigabe.
