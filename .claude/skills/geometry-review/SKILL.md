---
name: geometry-review
description: >
  Prüft und diagnostiziert Solidon-Geometrie mit reproduzierbaren Eingaben,
  unabhängigen Sollwerten und Nachweisen für Mesh- und B-Rep-Pfade. Benutzen
  bei falschen Operationsergebnissen, Rückfallketten, Geometrie-Reviews und
  Abweichungen zwischen Kernen; neue Ops über neue-op anlegen.
---

# Geometrie prüfen

## Reproduktionsfall und Vertrag

Grenze Operation, Eingaben und erwartetes Ergebnis ein. Lies über `/bauplan`
den betroffenen Vertrag, dann die zuständigen `CLAUDE.md`-Karten und Regeln.
Die Diagnosehinweise in `.claude/agents/solidon3d-geometrie.md` ergänzen diesen
Ablauf; sie beauftragen nicht automatisch einen weiteren Agenten.

Erfasse Version beziehungsweise Commit und lokale Änderungen, Bibliotheksfassungen,
Einheit, Objekttransformationen, Op-Parameter, Qualitätsstufe und Startwert.
Ermittle alle Aufrufer und den tatsächlich gewählten Rechenpfad, bevor du eine
Ursache festlegst. Für API-Fragen zuerst installierten Code und Versionsbindung
prüfen, bei Bedarf Context7 oder die offizielle Bibliotheksdokumentation.
Keine Modelle oder Projektquelltexte an einen Dokumentationsdienst senden.

Baue den kleinsten Fall, der das beobachtete Problem noch zeigt. Nutze einen
geeigneten Korpusfall aus `tests/data/` oder einen analytischen Körper mit
unabhängig berechenbarem Soll. Leite den Sollwert nicht aus derselben Funktion
ab, die geprüft wird. Vor einem Geometrie-Fix muss der Regressionstest den
Fehler am unveränderten Stand zeigen.

## Messung passend zur Aussage

| Frage | Nachweis |
|---|---|
| Maße und Lage | Bounding Box, Volumen, relevante Abstände; lokale und Weltkoordinaten sowie Millimeter und Anzeigeeinheit auseinanderhalten. |
| Mesh | Endliche Koordinaten, entartete Flächen, Normalen, Randkanten, Komponenten; Wasserdichtheit allein beweist weder fehlende Selbstdurchdringung noch Druckbarkeit. |
| B-Rep | Gültigkeit des exakten Körpers und geometrische Größen; Tessellierungsfehler getrennt vom Modellierungsfehler prüfen. |
| Topologie | Erwartete Körperzahl, Öffnungen und Zusammenhang aus dem Auftrag; mehrere Komponenten oder ein leeres Ergebnis können korrekt sein. |
| Attribute | Benannte Features, Provenienz, Materialslots und Referenzen an allen betroffenen Verbrauchern prüfen. |
| Wiederholbarkeit | Gleiche Eingaben, Qualitätsstufe und gespeicherter Startwert ergeben denselben zugesagten Zustand. |
| Passung | Eingebaute Lage, Schnittvolumen, Mindestabstand und gegebenenfalls Montageweg; beabsichtigte Überdeckung einer Presspassung gesondert behandeln. |

Maßtoleranzen für die Fertigung kommen aus dem Materialprofil; numerische
Vergleichs-, Schweiß- und Tessellierungsgrenzen aus den zuständigen Funktionen
und Konstanten in `app/core/units.py` und den jeweiligen Rechenkernen. Keine
willkürliche Toleranzerhöhung, um einen roten Test grün zu machen.

## Parallele Pfade und Rückfall

Lies die aktuelle Verzweigung für exakte Körper und Netze. Vergleiche beide,
wenn die Operation beide unterstützt; gleiche Dreieckslisten sind dabei kein
sinnvolles Gleichheitskriterium für unterschiedlich tessellierte Körper.
Miss stattdessen die zugesagten geometrischen und semantischen Eigenschaften.

Für die Mesh-Booleschen Operationen steht die Kette in
`app/core/geom/boolean.py`: `FULL_CHAIN` und `DRAFT_CHAIN`. Erfasse die
versuchten Stufen und das tatsächlich verwendete `solver`-Ergebnis. Erzwinge
relevante Rückfallstufen in einem Test, statt darauf zu hoffen, dass ein
Beispiel zufällig dort landet. Ein Voxel-Ergebnis verlangt eigene Prüfungen
für Maßabweichung, Vernetzung und Attributerhalt.

Prüfe bei Änderungen an gecachten Ergebnissen die Cache-Abhängigkeiten und
Versionierung; bei Features auch Auswahl, nachfolgende Ops, Undo/Redo und
Speichern/Laden, soweit diese den betroffenen Zustand verwenden. Erweitere
die Testmenge nach der tatsächlichen Wirkung, nicht nach der Dateigröße.

## Reparatur und Bericht

Eine Diagnose allein schreibt keine Produktgeometrie um. Bei beauftragter
Reparatur erfolgt die Änderung im zuständigen Op-/Kernpfad; Eingangsobjekte
und `OpContext.scene` bleiben gemäß Vertrag unverändert. Prüfe auch Abbruch,
Fehler mit Handlungsvorschlag und beide Qualitätsstufen, soweit betroffen.

Lasse die betroffenen Tests über `/pruefen` mit ausdrücklichen Dateipfaden
laufen. Nenne Reproduktionsfall, Ursache, geänderte Pfade, Messwerte mit Einheit
und Toleranz, Solver, Testzahlen und offene Grenzen. Ein gültiges Netz belegt
keine physische Festigkeit oder Dichtheit; eine Simulation keinen echten Druck.
