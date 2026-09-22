---
name: parallele-sitzung-baut-dasselbe-feature
description: "Vor dem Bau eines Features die Zweige, Worktrees und laufenden Sitzungen fragen — Robert vergibt dieselbe Sache manchmal in zwei Sitzungen; am 22.09.2026 entstand die Mustererkennung zweimal"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 7708995f-8153-4da1-9385-1fa5f014d252
  modified: 2026-09-22T04:43:36.514Z
---

Am 22.09.2026 habe ich auf Roberts Bemerkung am Halter („das wabenmuster
kennen wir immer noch nicht") die Mustererkennung im Hauptbaum gebaut
(`patterns.py`, zehn Tests, Korpusprobe) — während die Sitzung
„CAD-Umsetzung" dieselbe Sache als RM-207 auf dem Zweig `rm-207-muster`
mit breiterem Umfang baute (acht Texturstile, Entfernen/Ändern). Das Register
in `ROADMAP.md` auf main kannte RM-207 nicht; der Punkt stand nur auf dem
Zweig. Robert entschied: der Zweig trägt es, meine Fassung liegt zum
Vergleich auf `muster-ringe` (b09fb2d4) — **und der Zweig fällt, sobald
`rm-207-muster` in main ist** (Robert, 22.09.2026: „Deinen Baum kannst du
dann entfernen wenn die andere es macht"): lokal und auf origin löschen.

**Why:** Robert arbeitet mit mehreren Sitzungen zugleich und vergibt eine
Sache manchmal zweimal, ohne es zu merken. Zwei Umsetzungen kosten einen
halben Tag und beim Merge eine dritte; das Register auf main sieht die
Arbeit eines Zweigs nicht.

**How to apply:** Vor dem Bau eines Features, das mehr als eine Datei
anfasst: `git branch -a` und `git worktree list` lesen (ein Zweig
`rm-NNN-…` oder ein Worktree `F:\3D Druck.rm-NNN` heißt: jemand baut es),
und `ListAgents` fragen, welche Sitzungen laufen — bei Zweifel eine kurze
Nachricht an die Sitzung, bevor die erste Datei entsteht. Wer in demselben
Baum wie eine andere Sitzung schreibt, committet nur mit Pathspec und
nimmt eigene Hunks per gezielter Ersetzung zurück, nie per `git checkout`
auf eine Datei mit fremden Hunks (siehe [[zweite-sitzung-im-selben-baum]],
[[fremder-commit-nimmt-unfertige-hunks-mit]]).
