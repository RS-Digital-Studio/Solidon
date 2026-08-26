---
name: temp-dateien-sind-maschinenweit
description: Alle Sitzungen schreiben ihre Torläufe in dieselben $TEMP-Dateien — eine fremde oder eigene alte Zahl sieht aus wie die aktuelle.
metadata:
  type: feedback
---

`/pruefen` nennt feste Dateinamen (`$TEMP/g1.txt` … `g5.txt`), und `$TEMP` ist
für alle Sitzungen derselbe Ordner. Wer den eigenen Lauf auswertet, liest
womöglich einen fremden — oder seinen eigenen von vor einer Stunde.

Am 26.08.2026 beides an einem Tag: Ich habe `g4code.txt` gelesen und
ausgewertet, ohne zu merken, dass sie vierzig Minuten alt war (mein erster
Lauf); der zweite lief noch und hatte seine Codes noch nicht geschrieben.
a2 fand kurz darauf eine dritte Messung in seiner eigenen Ausgabedatei.

**Why:** Eine Zahl in der eigenen Datei sieht aus wie die eigene. Die
Zeitstempel-Prüfung fällt niemandem ein, solange nichts merkwürdig aussieht —
und wenn etwas merkwürdig aussieht, ist es schon ausgewertet.

**How to apply:** Den Sitzungsnamen in den Dateinamen:
`$TEMP/ce-suite.txt`, `$TEMP/ce-codes.txt`. Und beim Lesen einer Ausgabedatei,
die man nicht in derselben Minute geschrieben hat, **zuerst den Zeitstempel**:
`ls -la --time-style=+%H:%M:%S`. Verwandt mit
[[messwerkzeug-misst-sich-selbst]] — hier ist das Werkzeug nicht falsch, nur
die Datei gehört jemand anderem.
