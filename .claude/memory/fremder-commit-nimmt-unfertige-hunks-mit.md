---
name: fremder-commit-nimmt-unfertige-hunks-mit
description: "Ein Peer-Commit kann unfertige eigene Hunks aus dem geteilten Baum mitnehmen — nach jedem fremden Commit HEAD auf die eigenen Marker prüfen, bevor Paare gegen ihn gebaut werden"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 1ca7314c-d749-4b85-aac6-9da0d8f5da54
  modified: 2026-09-15T04:12:34.610Z
---

Am 15.09.2026 um 05:45 nahm der fremde Commit 4f1c49b5 (Langloch drehen) aus dem
geteilten Arbeitsbaum meine unfertigen Hunks mit: tests/test_prepare.py mit **zwei
Kopien** derselben neuen Tests und einem dritten Helfer gleichen Namens (F811,
ValueError am HEAD), dazu actions.py und test_feature_panel.py **ohne** den
zugehörigen Kern in prepare_ops.py. HEAD war rot und inkonsistent, und meine
Paare passten nicht mehr auf ihn (die Anker standen doppelt). Ein zweiter fremder
Merge (80ead405e) nahm zwei der drei Dateien wieder zurück.

**Why:** Wer `git add <datei>` auf eine Datei mit fremden Hunks macht, committet
alles darin — die Regel „nur eigene Hunks stagen" gilt für jede Sitzung, aber
nicht jede hält sie. Und ein Blob, der gegen HEAD gebaut wird, misst den HEAD
seines Baus (siehe [[geteilter-index-nach-fremdem-commit-veraltet]]).

**How to apply:** Unfertige Arbeit im geteilten Baum klein halten und zügig
committen. Vor jedem Blob-Bau `git log -1` lesen und den HEAD auf die **eigenen
Marker** greppen (Funktionsnamen, Testnamen): Steht schon etwas davon drin, sind
die Anker anders — Paare gegen den echten HEAD neu erzeugen, doppelte Blöcke mit
einem eigenen Entfernungspaar wörtlich aus HEAD herausnehmen. Den Commit-Lauf
so bauen, dass er HEAD-Kopien und Paare **im selben Lauf** erzeugt
(`commit19.sh`-Muster). Danach im Nebenbaum am reinen HEAD nachfahren. Peers
benachrichtigen, wenn ihr Commit fremde Hunks trägt — mit Commit-Kennung.
Verwandt: [[datei-die-vor-dem-patch-modifiziert-war-geht-nur-als-blob]],
[[heredoc-frisst-den-backslash]] (viermal an einem Morgen: Python mit `\\n` nur
als Datei über Write, nie als Heredoc).
