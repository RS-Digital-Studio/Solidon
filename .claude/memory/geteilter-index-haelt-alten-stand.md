---
name: geteilter-index-haelt-alten-stand
description: "Der geteilte Index kann einen Stand vor HEAD halten — dann zeigt git status fremde Arbeit an, wo der Arbeitsbaum identisch mit HEAD ist."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 7fe92054-2daa-4d76-92ed-67a2464096bd
  modified: 2026-08-27T18:21:14.263Z
---

`git status` zeigte am 27.08.2026 fünf Dateien als `MM` — ROADMAP.md,
`app/core/geom/difference.py`, `standards.toml`, `test_difference.py`,
`test_parts.py`. Gelesen als „eine Nachbarsitzung arbeitet gerade daran". War
es nicht: Der **Index** hielt einen Stand *vor* dem letzten Commit
(`7e5b1df6`), der Arbeitsbaum war bei allen fünf **identisch mit HEAD**.

Erkennbar an der Symmetrie der beiden Diffs: `git diff --cached --stat` zeigte
278 Zeilen als gelöscht, `git diff --stat` genau dieselben 278 als hinzugefügt.
Das ist kein Doppelfund, das ist ein Index, der zurückliegt.

**Warum:** Wer dort `git commit` ohne privaten Index fährt, committet 278
Zeilen fremder Arbeit **als gelöscht** — und der Diff sieht aus wie eine
Aufräumung. Zwei Sitzungen sind an einem Tag darüber gestolpert, eine davon
hatte vorher `--numstat` gelesen und nur „plausible Zeilenzahlen" gesehen,
weil die Zahlen ja stimmen; falsch ist das Vorzeichen.

**Wie anwenden:** Bevor man ein `MM` für fremde Arbeit hält, die eine Zeile
fahren, die es entscheidet:

```
for f in <pfade>; do git diff --quiet HEAD -- "$f" && echo "$f == HEAD"; done
```

Steht dort `== HEAD`, gehört die Datei niemandem — der Index ist alt. Aufräumen
mit `git reset -- <pfade>` (nur Index, Arbeitsbaum unberührt); danach prüfen,
dass der Arbeitsbaum unverändert ist. Privater Index bleibt trotzdem Pflicht,
solange der Baum geteilt ist — siehe [[privater-index-fester-name]] und
[[commit-o-nimmt-den-dateistand]]. Verwandt:
[[parallele-sitzung-im-arbeitsbaum]], [[geteilter-baum-misst-zeitpunkt]].
