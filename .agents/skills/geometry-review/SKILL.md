---
name: geometry-review
description: >
  Prüft und diagnostiziert Solidon-Geometrie mit reproduzierbaren Eingaben,
  unabhängigen Sollwerten und Nachweisen für Netz- und exakten Kern. Benutzen
  bei falschen Operationsergebnissen, Rückfallketten, Abweichungen zwischen
  den Kernen und Geometrie-Reviews in der Sitzung. Abgeschlossen delegieren:
  Agent solidon3d-geometrie; eine neue Operation: /neue-op.
argument-hint: "[Operation, Datei oder beobachtetes Fehlbild]"
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

# Geometrie prüfen

Eine Diagnose grenzt ein, statt an Parametern zu drehen. Sie schreibt keine
Produktgeometrie um, solange keine Reparatur beauftragt ist.

## Reproduktionsfall und Vertrag

Operation, Eingaben und erwartetes Ergebnis eingrenzen; den betroffenen
Vertrag über `.agents/skills/bauplan/SKILL.md` lesen, dazu Karte und Regeln des Gebiets. Erfassen:
Stand und lokale Änderungen, Bibliotheksversionen, Einheit,
Objekttransformationen, Op-Parameter, Qualitätsstufe und Startwert. Alle
Aufrufer und den tatsächlich gewählten Rechenpfad kennen, bevor eine Ursache
feststeht. Für API-Fragen zuerst den installierten Code und die
Versionsbindung, bei Bedarf Context7 oder die offizielle Dokumentation — nie
Modelle oder Projektquelltext an einen Dokumentationsdienst senden.

Den kleinsten Fall bauen, der das Problem noch zeigt: Kette kürzen, Objekte
weglassen, Auflösung senken — die letzte Änderung, nach der der Fehler
verschwindet, ist die Spur. Grundlage ist ein Korpusfall aus `tests/data/`
oder ein analytischer Körper mit unabhängig berechenbarem Soll; den Sollwert
nie aus der Funktion ableiten, die geprüft wird. Vor einem Fix zeigt der
Regressionstest den Fehler am unveränderten Stand.

**Danach das echte Modell.** Eine selbst gebaute Platte hat die
Eigenschaften, die ihr Erbauer kennt; Kundenmodelle aus Roberts Sammlung
(`F:\3D Dateien`: STL, 3MF, STEP) haben Nähte, Float32-Ecken und
Merkmalsdichten, an denen die Fehler auffallen. Jede Verifikation läuft auch
dort; fehlt ein passendes Modell, sag, welches. Ein Kundenmodell kommt nur mit
Roberts Freigabe nach `tests/data/` — sonst läuft die Sonde außerhalb der
Suite, und ihr Ergebnis steht im Bericht.

## Messung passend zur Aussage

| Frage | Nachweis |
|---|---|
| Maße und Lage | Bounding Box, Volumen, relevante Abstände; lokale und Weltkoordinaten sowie Millimeter und Anzeigeeinheit auseinanderhalten. |
| Netz | Endliche Koordinaten, entartete Flächen, Normalen, Randkanten, Komponenten; Wasserdichtheit allein beweist weder fehlende Selbstdurchdringung noch Druckbarkeit. |
| Exakter Körper | Gültigkeit und geometrische Größen; Tessellierungsfehler getrennt vom Modellierungsfehler prüfen. |
| Topologie | Erwartete Körperzahl, Öffnungen und Zusammenhang aus dem Auftrag; mehrere Komponenten oder ein leeres Ergebnis können korrekt sein. |
| Attribute | Benannte Features, Provenienz, Materialslots und Referenzen an allen betroffenen Verbrauchern. |
| Wiederholbarkeit | Gleiche Eingaben, Qualitätsstufe und gespeicherter Startwert ergeben denselben zugesagten Zustand. |
| Passung | Eingebaute Lage, Schnittvolumen, Mindestabstand und gegebenenfalls Montageweg; eine beabsichtigte Überdeckung gesondert behandeln. |

Zuerst die Eingänge messen, dann die Operation verdächtigen: Viele Fehler „in
der Op“ sind Fehler im Netz davor. Fertigungstoleranzen kommen aus dem
Materialprofil; Vergleichs-, Schweiß- und Tessellierungsgrenzen aus den
zuständigen Funktionen in `app/core/units.py` und den Rechenkernen. Keine
Toleranz „ein bisschen hochdrehen“, bis ein Test grün wird, und kein
Sonderfall im Code für ein Modell.

## Häufige Ursachen

- Toleranz zu klein oder zu groß für die Modellgröße: `EPS_GEOM` ist fest,
  modellabhängige Grenzen liefern `match_tolerance` und `weld_tolerance`.
- Koplanare Flächen bei Booleschem — der klassische Fall für die Stufe
  `welded`.
- Zwei Körper, die sich nur berühren, statt sich zu überlappen.
- Löcher, die eine Wand tangieren, sodass die Kontur sich selbst berührt.
- Konturhierarchie beim Schnitt: äußere und innere Ringe falsch zugeordnet,
  und ein hohler Querschnitt kommt leer zurück.
- Einheiten: ein Modell in Zoll, als Millimeter gelesen.
- Nicht-Determinismus ohne Startwert: dasselbe Modell, zwei Ergebnisse.
- Der exakte Kern fehlt, und der Rückfall wurde nicht ausgewiesen.

## Beide Kerne und die Rückfallkette

Die aktuelle Verzweigung für exakte Körper und Netze lesen und beide
vergleichen, wenn die Operation beide unterstützt. Gleiche Dreieckslisten sind
dabei kein Kriterium; gemessen werden die zugesagten geometrischen und
semantischen Eigenschaften.

Die Kette der Booleschen am Netz steht in `app/core/geom/boolean.py`
(`FULL_CHAIN`, `DRAFT_CHAIN`). Versuchte Stufen und das tatsächlich verwendete
`solver`-Ergebnis erfassen; relevante Stufen in einem Test erzwingen, statt
darauf zu hoffen, dass ein Beispiel dort landet. Ein Voxel-Ergebnis verlangt
eigene Prüfungen für Maßabweichung, Vernetzung und Attributerhalt; fehlende
Slots oder Merkmalskennungen danach sind ein Befund, die Stufe allein noch
nicht seine Ursache.

Bei geänderten Ergebnissen die Cache-Abhängigkeiten prüfen (`cache_version`
der Op), bei Merkmalen auch Auswahl, Folgeschritte, Undo/Redo und Speichern
und Laden, soweit sie den Zustand verwenden. Die Testmenge richtet sich nach
der Wirkung, nicht nach der Dateigröße.

## Reparatur und Bericht

Eine beauftragte Reparatur geschieht im zuständigen Op- oder Kernpfad;
Eingangsobjekte und `OpContext.scene` bleiben unverändert. Abbruch, Fehler mit
Handlungsvorschlag und beide Qualitätsstufen mitprüfen, soweit betroffen. Das
Fehlerbild wird eine Testdatei, kein Sonderfall im Code. Die betroffenen Tests
über `.agents/skills/pruefen/SKILL.md` mit ausdrücklichen Dateipfaden.

Zu nennen: Reproduktionsfall und echtes Modell, Ursache, geänderte Pfade,
Messwerte mit Einheit und Toleranz, Solver-Stufe, Testzahlen, offene Grenzen
— und welche Behauptung auf dem Weg zurückgenommen wurde. Ein gültiges Netz
belegt keine Festigkeit oder Dichtheit, eine Simulation keinen echten Druck.
