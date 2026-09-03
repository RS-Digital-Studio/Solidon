---
name: privater-index-schuetzt-die-kataloge-nicht
description: git commit -o nimmt den Dateistand — bei den Sprachkatalogen ist das der fremde Zwischenstand von drei Sitzungen.
metadata:
  type: feedback
---

Der private Index (`GIT_INDEX_FILE`) und `git commit -o -- <pfade>` halten
**fremde Dateien** heraus. Bei einer **gemeinsamen** Datei helfen sie nicht:
`-o` nimmt den Stand auf der Platte, und darin steht auch, was andere Sitzungen
dort hineingeschrieben und noch nicht committet haben.

Am 03.09.2026 zeigte `git diff --cached` für `app/i18n/locales/en.json` sechs
neue Zeilen, wo eine erwartet war. Fünf gehörten drei anderen Sitzungen —
Filamentwahl, Dialoge, Bohrungsoperation. Sie sind unter meiner Meldung
hinausgegangen.

**Why:** Die fünf Sprachkataloge sind die am stärksten geteilten Dateien des
Projekts. Fast jede Oberflächenarbeit fasst sie an, und der Vorab-Hook
verlangt sogar, dass sie *vor* dem Commit vollständig sind — also liegen dort
fast immer fremde Zeilen. Der Schaden ist klein (der Text ist übersetzt und
richtig), aber die Zuordnung geht verloren: Wer später fragt, warum ein Satz
so lautet, findet einen Commit, der von etwas anderem handelt.

**How to apply:** Die Zeilenzahl im `git diff --cached` **vor** dem Commit
gegen die eigene Erwartung halten — bei den Katalogen ist eine Abweichung die
Regel, nicht die Ausnahme. Wer nur den eigenen Eintrag will, baut den Blob aus
`git show HEAD:app/i18n/locales/<sprache>.json` plus der eigenen Zeile, wie bei
[[blob-commit-verliert-den-wettlauf]] beschrieben. Wer es mitnimmt, sagt es
denen, deren Zeilen es waren — sie sehen sonst einen leeren Katalogteil in
ihrem eigenen Diff und halten ihn für verloren.

Verwandt: [[commit-o-nimmt-den-dateistand]] — dort geht es um dieselbe Regel
für eine gemeinsame Codedatei; hier um die Datei, bei der sie fast immer greift.
