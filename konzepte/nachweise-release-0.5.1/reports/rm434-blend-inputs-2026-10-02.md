# RM-434: Eingangsprüfung vor dem Entwurfsbudget

Fachnachweis vom 02.10.2026. Der Fix und seine abgegrenzten Testhunks sind
unabhängig freigegeben. Zentrales Entwicklungstor und Hauptzweigübernahme
stehen noch aus. Ein fremder Typfehler und sein grüner Nachlauf sind unten belegt.

Die Vorbereitung führte B02 zunächst als RM424. Beim zentralen Abgleich war
diese Nummer bereits auf `origin/main` für den Bettursprung von Orca-/Prusa-
Maschinen vergeben. B02 heißt deshalb jetzt RM434; die ursprünglichen
Laufprotokolle und historischen Quellbelege behalten ihre damalige Bezeichnung.

## Reproduzierter Fehler

`blend_union` ruft im Entwurf zuerst `draft_grid` auf. Dessen gemeinsamer
Helfer `_grid` las bislang die rohen Bounds vor der Volumen-/Dichtheitsprüfung
in `blend_bodies`. Bei einem leeren Netz sind die Bounds `None`: Ein leeres
erstes, zweites oder beide Eingangsnetze verursachten `TypeError` ohne
Handlungsvorschlag. Der Feinweg sagte bereits mit `NotManifoldError` und den
vorhandenen Reparaturhandlungen ab.

Die bisherige Prüfung steht jetzt unverändert am Beginn von `_grid` und
damit vor Bounds und Rasterbudget in beiden Wegen. Fehlertyp, übersetzter
Text und Handlungen bleiben erhalten. Feldrechnung, Rasterformeln und
Toleranzen ändern sich nicht. `blend_union` erhält Cacheversion **4** statt 3.

## Tatsächlicher Testanschluss

Der neue Fall
`test_blending_refuses_invalid_inputs_before_planning_the_grid_or_field`
in `tests/test_missing_ops.py` führt die registrierte Operation mit echtem
`OpContext` aus. Seine 18 Kombinationen prüfen:

- Leeres Netz, offener Würfel und geschlossene Würfeltopologie mit Nullhöhe.
- Jeweils erster, zweiter oder beide Eingänge in `draft` und `fine`.
- Fachliche Absage mit Reparieren, Stellen zeigen und Abbrechen.
- Keinen Aufruf von `distance_field`; unveränderte Eingangskoordinaten und
  Dreiecksindizes. Jede unerwartete Rückfrage scheitert.

Sechs bestehende Fälle ergänzen den Nachgang: drei Körperpaare unter dem
Entwurfsbudget, gröberer Entwurf ausschließlich oberhalb des Budgets,
fachliche Absage an ein zu feines Raster und an einen Körper ohne Volumen.
Damit ist der gültige Budgetvertrag aus RM379 weiter geprüft.

## Gelesene Rot- und Grünbelege

Die vollständigen lokalen Protokolle liegen in `tmp/b02-blend-20261002/`.

| Protokoll | Tatsächlicher Ausgang |
|---|---|
| `red-fixture-corrected.txt` | 3 fehlgeschlagen, 15 bestanden, 142 abgewählt; 1,03 s, Exit 1. Ausschließlich die drei leeren Entwurfseingänge scheitern am beschriebenen `TypeError` |
| `green.txt` | 18 bestanden, 142 abgewählt; 0,45 s, Exit 0 |
| `invalid-and-budget.txt` | 24 bestanden, 153 abgewählt; 14,34 s, Exit 0 |
| `ruff.txt`, `ruff-all.txt` | Eigene zwei Dateien sowie damaliger Gesamtbaum ohne Ruff-Befund, jeweils Exit 0 |
| `format.txt`, `diff-check.txt` | Zwei Dateien formatiert, eigene Diffprüfung sauber, jeweils Exit 0 |
| `mypy.txt` | Exit 1: fremder Fehler `app/core/export/handover.py:895`, Zugriff auf `.settings` bei `Foundation \| None`; dem zuständigen Bearbeiter gemeldet |
| `mypy-after-owner-fix.txt` | Nach dessen Korrektur: `mypy app/core/geom/blend.py` ohne Fehler in einer Quelldatei, Exit 0; Handover-Datei vor und nach dem Lauf unverändert |
| `documents-final.txt` | 32 Roadmap-/Kartenfälle bestanden, 1,48 s, Exit 0 |

Der gezielte Mypy-Nachlauf prüfte Handover mit SHA256
`29cef52643b52b09dea3a0592bf32021ceb6d83d0addc2ae18c1c1eb2e57dfcf`.
Der frühere rote Lauf bleibt als historischer Befund erhalten; der Nachlauf
ist keine vollständige Typprüfung des gemeinsamen Baums.

Der erste Lauf `red.txt` hatte zusätzlich sechs Aufbaufehler: Die Sonde fragte
bei Nullvolumen `raw.volume` und löste dadurch eine Warnung der
Schwerpunktrechnung aus. Vor jeder Produktänderung wurde ausschließlich der
Wächter auf den vorhandenen `MeshData.volume`-Vertrag umgestellt. Erst der
erneute Lauf mit drei tatsächlichen Fehlern ist der maßgebliche Rotbeleg.
Die 18 neuen Fälle sind im 24er-Nachgang enthalten; Zahlen werden nicht addiert.

## Review und Übernahmegrenze

Der unabhängige Review hat alle eigenen Zeilen und die tatsächlichen
Protokolle gelesen. Die Freigabe umfasst genau die drei Hunks in `blend.py`
und in `test_missing_ops.py` den `Quality`-Import sowie den neuen
parametrisierten Testblock. Der fremde Hilfsprozess-/Entlüftungsfall und
sein Import bleiben eine andere Einheit. Eine Kartenänderung ist nicht nötig:
Die vorhandene Modulbeschreibung bleibt richtig, die öffentliche Schnittstelle
und die Validierungsregel sind unverändert.

Das sind Kernprüfungen ohne Fenster, Renderer oder Leistungsmessung. Ein
nativer Kundenweg, der ein leeres Szenenobjekt bis zu diesem Aufruf bringt,
wurde nicht neu belegt. Der feine Exportanschluss B01 wird getrennt unter
RM352 bearbeitet. Die fachliche Freigabe ist kein grünes vollständiges Tor
und kein Commit-/Pushnachweis.
