---
name: probe-worktree-altert
description: "Ein Baum aus einem Probe-Worktree ist ein vollständiger Zustand, keine Änderungsmenge — wird er übertragen, nimmt er jeden Commit zurück, der seit dem Abzweig kam."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 4e2b249b-1d42-4020-bb0e-bdcf350ef625
  modified: 2026-08-29T18:19:16.145Z
---

Ein Probe-Worktree von HEAD ist der richtige Weg, einen Commit zu bauen, dessen
Werkzeuge gegen den **Commit-Stand** laufen müssen statt gegen den Arbeitsbaum
(`extract`, `make_manual`, `stamp_assets`). Falsch ist der **Übertragungsweg**
`git read-tree <worktree-tree>`: Ein Baum ist ein vollständiger Zustand, keine
Menge von Änderungen. Landet zwischen dem Anlegen des Worktrees und dem Commit
ein fremder Commit, nimmt der übertragene Baum ihn stillschweigend zurück.

Am 29.08.2026 so passiert (`0210d228`): 52 Dateien, 1085 Zeilen und eine neue
Datei einer fremden Sitzung waren weg. Repariert mit `0b55ed63` — vorwärts,
Index aus `read-tree <fremder-commit>` plus den eigenen Blobs über
`git ls-tree -r <tree> -- <pfade> | git update-index --index-info`. Das ging
nur, weil beide Dateimengen sich in keiner Datei überschnitten; **vorher mit
`comm` über beide Namenslisten geprüft**.

**Why:** Der Index-Diff wurde vor dem Commit geprüft, wie abgesprochen — aber
gegen die Basis des Worktrees, und die war beim Commit zwei Commits alt. Eine
Prüfung gegen den Abzweigpunkt misst die Absicht, nicht die Wirkung.

**How to apply:** Unmittelbar vor dem Commit `git diff --cached HEAD --stat`
gegen den **aktuellen** HEAD lesen, und die Zahl mit der eigenen Ansage
vergleichen. Weicht sie ab, nicht committen. Nach dem Commit die gemeldete
Dateizahl lesen — `86 files changed` statt `34` ist der Alarm, und er steht in
der Ausgabe, die man ohnehin sieht. Siehe [[geteilter-baum-misst-zeitpunkt]],
[[commit-o-nimmt-den-dateistand]] und [[privater-index-fester-name]].
