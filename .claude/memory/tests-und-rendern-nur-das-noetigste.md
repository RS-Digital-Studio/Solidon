---
name: tests-und-rendern-nur-das-noetigste
description: Roberts Anweisung vom 02.09.2026 — je Schritt nur die betroffenen Tests fahren und nur die Bilder neu erzeugen, die sich ändern; das volle Tor bleibt für den Commit.
metadata:
  type: feedback
---

Robert am 02.09.2026, wörtlich: „neues zu tests, wenn du sachen änderst führe
nur die betroffenen tests aus" und später „auch merken tests das nötigste und
rendern nur das nötigste, wenn sinnvoll".

**Why:** Die volle Suite braucht im geteilten Lauf fünf Minuten und das
Schloss; dreimal am Tag für jeden Zwischenschritt kostet mehr, als es
findet. Ein Bilderlauf über 54 Bildschirmfotos in sechs Sprachen dauert
länger als die Änderung, die eines davon betrifft. Was Robert nicht will:
dass „nur das Nötigste" zur Schätzung nach Gefühl wird — genau so kamen
viermal an einem Tag deutsche Bezeichner ins Tor.

**How to apply:** Je Schritt `tools/affected_tests.py` (liest den
Importgraphen: mittelbare Importeure, Baumleser, Tests, die eine geänderte
Textdatei beim Namen nennen; `--why`, `--split`, `--run`). Meldet es „das ist
die Suite" (Änderung an `i18n`, `types.py`, `errors.py`, `log.py`), dann
direkt das Tor. Vor dem Commit bleibt `/pruefen` — die Auswahl sagt, was eine
Änderung sicher berührt, das Tor sagt, ob der Stand trägt. Bilder und
Handbuch: **nur vor einem Release, und nur, was sich geändert hat** — Roberts
Nachsatz vom selben Nachmittag („bilder und handbücher nur bei release … und
wenn sich daran was geändert hat"). Kein Filter je Bildschlüssel; die Einheit
ist die Sprache (`make_figures.py <sprache>`), und der volle Lauf gehört zu
einem Release, bei dem sich die Oberfläche geändert hat. „Wenn sinnvoll"
heißt: bei einer Änderung an einer Grundlage ist die Suite das Nötigste. Siehe [[architektur-sonde-type-checking]] und
[[zwei-laeufe-nach-jeder-code-aenderung]].
