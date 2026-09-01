# `app/examples/` — die Beispielprojekte

**Erzeugt**, nicht von Hand gepflegt: `tools/make_examples.py` baut sie
(§37.2, §2.2).

## Wozu sie da sind

Sie tragen die ersten fünf Minuten (§2.3). Der Startbildschirm bietet sie an,
`app/core/tour.py` führt hindurch, und `app/core/examples.py` liest sie.

## Rechte

Für die elf in `LICENSE` einzeln benannten, von RS Digital erzeugten
P3D/SVG-Paare behält RS Digital das Urheberrecht. Die dortige
Nutzungsfreigabe erlaubt Bearbeiten, Drucken, Export und die private oder
gewerbliche Nutzung eigener Ergebnisse, aber keine unveränderte Weitergabe
der ursprünglichen Vorlagen. Eingebettete Geometrie aus dem eigenen
MIT-Referenzkorpus in `tests/data/` behält ihre MIT-Rechte. Eine neue Quelle
oder ein neues Beispiel muss vor dem Erzeugen als eigene oder anderweitig
freigegebene Geometrie belegt und in `ASSET-RIGHTS.toml` ausdrücklich ergänzt
sein. Importierte Inhalte Dritter und frühere Tripo-Ausgaben erben diese
Freigabe nie.

Die Rechtefreigabe ist keine Aussage über Druckbarkeit, Festigkeit oder sichere
Verwendung. Mitgelieferte Beispiele werden zusätzlich in der
Produktsicherheitsakte mit ihrer Zweckgrenze, Version und Prüfung geführt.

## Was das für Änderungen heißt

- **Eine Projektdatei hier wird nicht bearbeitet.** Wer ein Beispiel ändern
  will, ändert `tools/make_examples.py` und lässt es neu bauen.
- Ändert sich das **Dateiformat**, müssen die Beispiele neu gebaut werden —
  sie sind keine Migrationsbelege. Die stehen in `tests/data/projects/` und
  bleiben absichtlich alt.
- Ändert sich ein **Baustein** im Maß, meldet das Öffnen es (§24.4). Ein
  Beispiel, das diese Meldung auslöst, ist ein veraltetes Beispiel.

Die Touren dazu prüft `tests/test_tour.py`, die Projekte selbst
`tests/test_examples.py`.
