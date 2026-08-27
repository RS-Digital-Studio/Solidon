# `app/examples/` — die Beispielprojekte

**Erzeugt**, nicht von Hand gepflegt: `tools/make_examples.py` baut sie
(§37.2, §2.2).

## Wozu sie da sind

Sie tragen die ersten fünf Minuten (§2.3). Der Startbildschirm bietet sie an,
`app/core/tour.py` führt hindurch, und `app/core/examples.py` liest sie.

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
