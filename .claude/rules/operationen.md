---
paths:
  - "app/core/geom/**/*.py"
  - "app/core/registry/**/*.py"
  - "app/core/scene/**/*.py"
---

# Regeln für Operationen

Eine Operation ist die einzige Stelle, an der Geometrie entsteht oder sich
ändert — auch nicht „kurz" im Viewport, auch nicht im Agenten (Regel 2).

## Vollständig oder gar nicht

Keine Op ohne Registereintrag, Parameterschema, Geometrietest und übersetzte
Texte. Die acht Schritte stehen als Checkliste in `AGENTS.md`; `/neue-op`
führt sie durch. Der Registereintrag braucht `name`, `title`, `category`,
`params`, `reversible`, `consumes`/`produces`, `applies_to`, `deterministic`,
`doc`, optional `shortcut`.

`tests/test_registry_consistency.py` parametrisiert über das Register: eine
unvollständige Op fällt dort auf, ein doppeltes Kürzel auch.

## Parameter

Jeder Parameter hat Titel, Vorgabe, Einheit, Grenzen und einen `doc`-Satz, der
sagt, was er bewirkt — nicht, wie er heißt. Vorderseite des Dialogs: die zwei
bis drei Werte, die man tatsächlich ändert. Alles Weitere hinter „Weitere
Einstellungen" (§2.4).

Toleranzen verweisen ins Materialprofil (`auto:<material>`), nie als Zahl.
Wo ein Projektparameter passt, steht keine Streuzahl.

## Boolesche Operationen

Die Rückfallkette (§17.2) hat fünf Stufen, und die erreichte Stufe gehört in
`solver`:

| Stufe | Verfahren | Vermerk |
|---|---|---|
| 1 | direkt | `direct` |
| 2 | verschweißen, Toleranz erhöhen, erneut | `welded` |
| 3 | minimale Störung der Eingangsgeometrie | `jittered` (+ Startwert) |
| 4 | voxelbasiert rechnen, zurück vernetzen | `voxel` |
| 5 | Abbruch mit Befund und Handlungsvorschlag | — |

Stufe 4 kostet Genauigkeit und wird im Prüfbericht ausgewiesen, nie
stillschweigend verwendet. In Entwurfsqualität endet die Kette nach Stufe 2.
Nach `voxel` ist die Materialslot-Zuweisung neu zu übertragen — die Vernetzung
wurde ersetzt (§20).

## Beide Qualitätsstufen

`ctx.quality` kennt Entwurf und Fein. Entwurf ist das, womit iteriert wird und
worin der Agent arbeitet; Fein gilt beim Export und im finalen Prüfbericht.
Eine Op, die beide gleich behandelt, sollte das bewusst tun.

## Befunde

Findings zurückgeben, nicht selbst protokollieren. Der Prüfbericht setzt sie
zusammen, der Agent liest sie über `read_report`.

## Test

Kennzahlen gegen eine Datei aus `tests/data/`, nicht gegen ein selbst
erzeugtes Ergebnis. Bei Geometrie zuerst der Test, dann die Umsetzung. Ein
neues Fehlerbild wird eine Testdatei, kein Sonderfall im Code.
