---
name: commit-o-nimmt-den-dateistand
description: Der private Index hält fremde Dateien heraus, nicht den fremden Stand einer gemeinsamen — und die Zahl steht im eigenen Diff-Stat.
metadata:
  type: feedback
---

`git commit -o -- <pfad>` committet die Datei, **wie sie im Baum liegt** — samt
allem, was eine andere Sitzung darin ungespeichert stehen hat. Der private
Index (`GIT_INDEX_FILE`) schützt nur davor, dass fremde **Dateien** mitgehen.

Am 26.08.2026 in beide Richtungen zugeschnappt, innerhalb einer Stunde: Mein
Commit nahm 145 Zeilen aus `labels.py` mit, an denen 43 gerade schrieb; 46s
Commit nahm umgekehrt meinen `panels.py`-Eintrag mit.

**Why:** Der Schaden ist selten inhaltlich — HEAD war beide Male stimmig. Er
ist die Zurechnung, und schlimmer: eine **halbe** Einheit kann hinausreiten.
Meine 67 mitgenommenen `tr()`-Quellen machten `origin/main` rot, bis die
Kataloge nachkamen — ein Fenster, das der Urheber der Kataloge nicht geöffnet
hatte.

**How to apply:** Vor jedem `-o`-Commit ein Zweischritt, und die Reihenfolge
ist der ganze Punkt: **erst die eigene Zahl ansagen** („ich lösche zwei
Zeilen, füge keine ein"), **dann** `git diff HEAD --numstat -- <pfade>`
dagegenhalten. Wer erst die Zahlen liest, nickt den Istwert ab. Bei zwei
gelöschten Zeilen schreit „145 insertions" schon beim Ansagen.

Ist es passiert: History stehen lassen. Zuerst prüfen, ob eine halbe Einheit
hinausgeritten ist — das ist dringender als die Zurechnung —, dann den
Besitzer benachrichtigen, dann die Zurechnung im eigenen Folge-Commit
geradeziehen. Ausführlich in [[was-die-suite-nicht-findet]] benachbart; die
Regel steht in `.claude/rules/tests.md`.
