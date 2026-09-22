# P1.3 — bündige Ebenenlage und unabhängige Körperprobe

Lesender Anschlussplan. Der eingefrorene Produktstand wurde hierfür nicht
geändert; die nachstehenden Nachweise sind noch auszuführen.

## Unveränderter fachlicher Vertrag

Bauplan §14 definiert `flush` durch Flächennormalen und Abstand. Der aktuelle
Prüfer normalisiert beide Normalen, vergleicht den Betrag ihres Skalarprodukts
gegen `EPS_ANGLE` und den senkrechten Ebenenabstand gegen `FIT_TOLERANCE`.
Gleiche und entgegengesetzte Normalen sind zulässig. Räumlich getrennte Flächen
in derselben Ebene bleiben bündig. Die Flächen müssen sich weder berühren noch
überdecken. Keine neue Kontaktbedingung, kein Materialspiel und keine neue
Messunsicherheit ergänzen.

Daneben erhält jede auflösbare bündige Beziehung einen ausdrücklich getrennten
Befund über die vollständigen Körper in ihrer aktuellen Lage:

- Zwei verschiedene Körper auf derselben Druckplatte werden so geprüft, wie
  sie tatsächlich in `SceneObject.mesh` vorliegen. Auch seitlich getrennte
  Körper sind hierfür eine gültige Lage. Es wird nichts automatisch bewegt.
- Unterschiedliche Platten belegen keine gemeinsame Lage. Ihre möglicherweise
  gleichen Koordinaten dürfen keine gegenseitige Kollision begründen.
- Null Überschneidungsvolumen belegt nur fehlende Volumenüberdeckung. Es beweist
  weder Kontakt der ausgewählten Flächen noch einen freien Montageweg.
  Flächen-, Kanten- und Punktkontakt dürfen gültige Nullergebnisse sein.
- Eine positive Überschneidung kann weit abseits der gewählten Flächen liegen.
  Darum werden immer die ganzen Körper geprüft.
- Zwei Merkmale desselben Körpers können weiterhin eine zulässige bündige
  Ebenenbeziehung bilden. Die zusätzliche Probe zwischen zwei Körpern ist
  hier nicht anwendbar; keine Selbstverschneidung als Kollision melden.

Die Ebenenaussage und die Körperaussage bleiben nebeneinander sichtbar. Ein
Ebenenfehler unterdrückt keine Körperkollision; ein Nullvolumen beseitigt keinen
Ebenenfehler. Nicht messbare Ebenen bleiben nicht messbar, auch wenn die
auflösbaren Körper unabhängig davon geprüft werden können.

## Kleinster Anschluss im bestehenden Code

1. `app/core/scene/fits.py::_check_one` beendet `flush` derzeit direkt nach
   `_check_flush`. Für diese Art die vorhandenen Ebenenbefunde sammeln und
   genau einen unabhängigen Körperbefund ergänzen. `_check_flush` behält
   seine Normalen-, Abstands- und Reihenfolgeregel unverändert.
2. Die vorhandene Eignungsprüfung `_pair_problem` und ihre Meldungen bleiben
   erhalten. Bei einem auflösbaren `flush`-Paar darf ihr Befund die unabhängige
   Körperprobe nicht vorzeitig abschneiden: Ebenenbefund plus Körperbefund
   zurückgeben. Fehlende Körper-/Merkmalsverweise bleiben beim vorhandenen
   `fit.missing_feature`; daraus entsteht keine Körperfreigabe. Die
   öffentliche Eignungsprüfung für das Anlegen einer Beziehung ändert sich
   dadurch nicht.
3. Den Verschneidungs-, Quellen- und Fehlerteil von `_check_geometry` als
   privaten gemeinsamen Helfer für zwei `FeatureRef` wiederverwenden. Die
   radiale Lageprüfung `_shared_pose` bleibt davor im radialen Aufrufweg.
   Der bündige Aufruf prüft stattdessen nur verschiedene Körper und dieselbe
   Platte. Keine künstlichen Loch-/Zapfenmerkmale, keine Achsen oder
   Einstecktiefen für Flächen erfinden.
4. Den bestehenden `geom.measure.body_overlap` unverändert verwenden. Er
   prüft native Körper auf privaten Kopien, gemischte Körper über den
   ausgewiesenen Netzzwilling und Netze unmittelbar mit `stages=("direct",)`.
   Keine zweite Verschneidung, kein Abstandssurrogat, keine Reparatur und
   kein Voxel- oder Jitterrückfall als Nachweis.
5. Abbruch vor und nach der Körperarbeit bleibt derselbe `CancelToken`.
   `OperationCancelled` und Programmierfehler propagieren unverändert;
   geometrische Kernfehler liefern `fit.geometry_failed`, niemals Null.
   Native Originalbytes, Netzarrays und Maßquellen bleiben unangetastet.

Öffentliche Signaturen, `Fit`, `Finding`, Cachecodec und Projektformat brauchen
keine Änderung. Keine neue Geometrie in Projektdateien speichern. Die
Quellenkennzeichnung bleibt `geometry_source = native | mesh | mixed`;
`overlap_mm3` bleibt eine ungerundete Volumenzahl in mm³. `intersects` beschreibt
ausschließlich die erfolgreich gemessene positive Volumenüberdeckung.
Bei nicht ausführbarer Probe fehlen beide Ergebniswerte vollständig.

Die vorhandenen Ergebniscodes reichen aus:

| Körperbefund | Code / Schwere |
|---|---|
| Nativ/nativ oder Netz/Netz, gültiges Nullvolumen | `fit.geometry_clear` / `info` |
| Nativ/nativ oder Netz/Netz, positive Überdeckung | `fit.collision` / `warning` |
| Gemischt, unabhängig vom Vorzeichen | `fit.geometry_approximate` / `warning` |
| Verschiedene Platten oder derselbe Körper | `fit.pose_unknown` / `warning` |
| Geometrieprüfung gescheitert | `fit.geometry_failed` / `warning` |

Bei `fit.pose_unknown` unterscheiden einfache bestehende `values` den Grund:
`reason = different_plates | same_body`. Die sichtbare Aussage nennt beim
gleichen Körper ausdrücklich die nicht anwendbare Zweikörperprobe. Das ist
keine Verletzung seiner bündigen Ebenenregel. Keine neue Codeklasse nur für
diesen Sonderfall nötig.

## Texte und sichtbare Übernahme

Die radialen Texte bleiben unverändert. Für `flush` braucht der gemeinsame
Helfer eigene Texte, weil „koaxial“, „Einstecktiefe“ und eine behauptete
„Einbaulage“ den Ebenenvertrag verengen würden. Konkrete deutsche Quellen:

1. **Verschiedene Platten:** „Diese Körper liegen auf verschiedenen
   Druckplatten. Für eine gemeinsame Körperprobe beide auf derselben Platte
   anordnen.“
2. **Derselbe Körper:** „Beide Flächen gehören zum selben Körper. Für eine
   Überschneidungsprobe zwischen zwei Körpern zwei verschiedene Körper
   wählen.“
3. **Nullvolumen:** „In der aktuellen Lage überschneiden sich die Körper
   nicht. Ein Flächenkontakt und der Montageweg sind damit nicht nachgewiesen.“
4. **Überdeckung:** „Die Körper überschneiden sich in der aktuellen Lage.
   Die gesamten Körper und ihre Platzierung prüfen.“
5. **Gemischt, Nullvolumen:** „Die Netznäherung zeigt in der aktuellen Lage
   keine Überschneidung. Ein Flächenkontakt und der Montageweg sind damit
   nicht nachgewiesen; die exakten Körper separat prüfen.“
6. **Gemischt, Überdeckung:** „Die Netznäherung zeigt eine Überschneidung in
   der aktuellen Lage. Die exakten Körper und die Auflösung der Näherung
   prüfen.“

Der vorhandene Text für `fit.geometry_failed` ist bereits allgemeingültig.
Alle sechs Quellen in einem Schritt über `_()` und die fünf Sprachkataloge
ergänzen; keine neuen Bedienelemente oder Parameter nötig. Die eingeschränkte
Aussage bleibt im Prüfbericht sichtbar, auch wenn die Körperprüfung `info`
ist. Ein Befund über die ganzen Körper darf durch seinen Merkmalsfokus keine
genaue Kollisionsstelle an der ausgewählten Fläche behaupten.

Bestehende Anschlüsse erhalten denselben Befund ohne zweite Berechnung:

- `scene.evaluate` prüft Passungen vor Cacheveröffentlichung und der
  abschließenden Fortschrittsmeldung. Diesen Abschlussblock nicht duplizieren.
- `export.writer` ruft denselben Passungsprüfer auf und behält eine Beziehung
  auch beim Export nur eines ihrer Partner im Bericht.
- Steckbrief und Agentenprüfung übernehmen bereits sämtliche `fit.*`-Befunde.
- `perceive.maps._fit_feature_levels` übernimmt Körperkollisionen als
  Verletzung, unbekannte/angenäherte Proben als offen und reine Information
  ohne Verletzungsmarkierung. Beide Partner werden über den Passungsnamen
  zugeordnet. Keine zusätzliche Analyseberechnung in Oberfläche oder Karte.

Die Szenenkarte erhält nach Umsetzung einen zusammenhängenden Absatz zur
Trennung von bündiger Ebenenregel und aktueller Körperprobe. Der Bauplan muss
für diesen Anschluss nicht zu einer Kontaktregel umgeschrieben werden.

## Unabhängige Gegenfälle vor der Umsetzung

Körperdaten jeweils unabhängig vom zu prüfenden Befund konstruieren. Für die
ersten vier Fälle ist A der Würfel `[0,10] × [0,10] × [0,10]` in mm; seine
gewählte obere Fläche liegt bei `z=10` und hat Normale `+Z`.

| Fall | Körper B und ausgewählte echte Fläche | Ebenenregel | Körperprobe |
|---|---|---|---|
| Seitlich getrennt, gleichorientiert | `[20,30] × [0,10] × [0,10]`, obere Fläche `+Z` | bündig | 0 mm³; weder Kontakt noch Montage behaupten |
| Vollflächiger Kontakt, entgegengesetzt | `[0,10] × [0,10] × [10,20]`, untere Fläche `−Z` | bündig | 0 mm³; gültiger Kontakt ist kein Kernfehler |
| Grundkörper kollidieren bei bündigen oberen Flächen | `[5,15] × [0,10] × [0,10]`, obere Fläche `+Z` | bündig | exakt 500 mm³ Überdeckung |
| Kleiner Abstand innerhalb bisheriger Prüfauflösung | `[0,10] × [0,10] × [10,20]` plus Z-Versatz `FIT_TOLERANCE / 2`, untere Fläche `−Z` | weiterhin bündig | 0 mm³; Prüfauflösung ist keine Kontaktgarantie |
| Unterschiedliche Platten | A und B mit gleichen Koordinaten, beide obere Fläche `+Z`, verschiedene `plate` | bisherige Ebenenaussage erhalten | unbekannte gemeinsame Lage; `body_overlap` wird nicht aufgerufen |
| Ebenenfehler und Kollision gleichzeitig | `[0,10] × [0,10] × [0.3,10.3]`, obere Fläche `+Z` | Abstand 0,3 mm verletzt | zusätzlich exakt 970 mm³ Überdeckung |

Für Nullvolumen, Kontakt und positive Überdeckung jeweils **Netz/Netz,
nativ/nativ und beide gemischten Reihenfolgen** prüfen. Die Quader liefern
eine unabhängig berechenbare Volumenreferenz ohne Kreiseinpassung oder
Tessellationsungenauigkeit. Trotzdem bleibt die gemischte Aussage ausdrücklich
eine Näherungsprobe. Eine erfolgreiche gemischte Nullprobe wird keine grüne
exakte Körperfreigabe.

Weitere eng passende Gegenfälle:

- Gleiche und entgegengesetzte Normalen sowie skalierte Normalen behalten
  ihre bisherigen Ebenenergebnisse. Ein gemeinsamer starrer Transform mit
  tatsächlicher Körper- und Merkmalsübernahme erhält beide Prüfaussagen.
- Reiner Kanten-/Punktkontakt bleibt ein gültiges Nullvolumen und bekommt
  keine Behauptung über Flächenkontakt.
- Zwei koplanare Merkmale desselben Körpers: kein Selbstkollisionsbefund;
  Ebenenregel bleibt erhalten, Zweikörperprobe ausdrücklich nicht anwendbar.
- Fehlende/ungültige Normalen: `fit.not_measurable` bleibt sichtbar;
  bei auflösbaren verschiedenen Körpern kann zusätzlich eine echte
  Körperkollision gemeldet werden. Fehlende Merkmalsreferenz bleibt Fehler.
- Offenes Netz, ungültiger nativer Körper und erzwungener Kernfehler:
  kein `geometry_clear`, kein Nullvolumen als Ersatz und kein Reparaturaufruf.
- Abbruch nach tatsächlich erfolgter nativer Arbeit: kein Endergebnis,
  unveränderte Originalbytes; Abbruch im Auswertungsabschluss veröffentlicht
  weder Cache noch Fertigmeldung. Vorhandene gemeinsamen Gegenproben nutzen.
- Ein echtes bündiges Dokument über Auswertung, Cachetreffer, Wiederöffnung,
  Undo/Redo einer Verschiebung und Export beider bzw. eines Partners:
  Ebene und Volumen werden aus dem jeweiligen aktuellen Zustand gemeldet.
- Karte, Steckbrief und Export übernehmen bei einem gleichzeitigen
  Ebenenfehler und Körperbefund beide Aussagen; keine Befundfilterung für Grün.

## Betroffene Tests und Abschluss

`tests/test_digest_and_fits.py::two_faces` verwendet aktuell zweimal denselben
Platzhalterwürfel bei voneinander unabhängigen Flächenparametern. Für den
öffentlichen vollständigen Prüfweg brauchen diese Fälle echte passend
angeordnete Körper mit dazugehörigen Flächen. Eine zusätzlich erkannte
Platzhalterkollision darf nicht pauschal aus dem Ergebnis gefiltert werden.
Die bestehenden Normalen-/Abstandserwartungen bleiben erhalten; erwartete
Körperbefunde werden ausdrücklich mitgeprüft. Reine algebraische Gegenfälle
können zusätzlich den vorhandenen `_check_flush` direkt prüfen.

Neue Körpergegenfälle gehören in die bestehende reine Kerndatei
`tests/test_fit_geometry.py`. Den gemeinsamen Dokument-/Cache-/Exportweg und
die Kartenübernahme dort bzw. in den bereits vorhandenen Kerntests gezielt
ergänzen. Zuerst die unabhängigen Fälle rot belegen, dann den Anschluss bauen.

Produktänderung nach Freigabe des eingefrorenen Standes eng auf `fits.py`,
die Szenenkarte, fünf Sprachkataloge und betroffene bestehende Kerntests
begrenzen. `measure.py`, `evaluate.py` und `writer.py` brauchen nach dem
vorliegenden Vertrag keine neue Implementierung, sondern Anschlussbelege.
Betroffene Kernprüfung über `tools/affected_tests.py`, Kataloge statisch
einsammeln/vergleichen, anschließend Ruff, Format und mypy. Fensterdateien
und Leistungsprüfungen bleiben ausschließlich der Release-Abnahme vorbehalten.

P1.3 darf erst nach diesem Anschluss auch den bündigen Prüfweg als mit
unabhängiger Körperprobe abgedeckt ausweisen. Dieser Plan ist kein Nachweis
einer bereits implementierten oder bestandenen Prüfung.
