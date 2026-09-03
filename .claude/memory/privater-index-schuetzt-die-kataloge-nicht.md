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
Regel, nicht die Ausnahme.

**Und dann den Blob bauen statt den Dateistand zu nehmen** (3d-druck-7f,
03.09.2026, seitdem bei zwei Sitzungen in Gebrauch):

    git show HEAD:app/i18n/locales/<sprache>.json   → eigene Zeilen einfügen
    git hash-object -w --path <pfad>                → git update-index --cacheinfo

Dann liegt im Commit genau der eigene Anteil, auch wenn im Baum fünf fremde
Zeilen stehen. Der Beleg: Ihr Commit danach trug **null** Katalogzeilen, weil
der eigene Teil schon über fremde Commits draußen war — und genau das sollte er
zeigen. Dasselbe Verfahren wie bei
[[blob-commit-verliert-den-wettlauf]], nur hier für die Datei, bei der es fast
immer nötig ist. Wer es mitnimmt, sagt es
denen, deren Zeilen es waren — sie sehen sonst einen leeren Katalogteil in
ihrem eigenen Diff und halten ihn für verloren.

**Und den Urheber messen, nicht erschließen.** Am selben Tag habe ich drei der
fünf Zeilen der Sitzung zugeschrieben, die am nächstliegenden Gebiet arbeitete;
sie waren es nicht. Die Antwort steht in zwei Befehlen: `grep -rl "<der Satz>"
app --include=*.py` nennt die Datei, `session_board.py list` nennt die Sitzung,
die sie hält. Eine falsche Zuordnung kostet die Betroffene eine Messung und die
richtige den Hinweis.

Verwandt: [[commit-o-nimmt-den-dateistand]] — dort geht es um dieselbe Regel
für eine gemeinsame Codedatei; hier um die Datei, bei der sie fast immer greift.
