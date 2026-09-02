---
name: gekillter-lauf-schreibt-weiter
description: Eine Hülle, deren pytest-Kinder beendet wurden, läuft weiter und schreibt in dieselben Dateien wie der Neustart — zwei Läufe, ein Protokoll, kein lesbares Ergebnis.
metadata:
  type: feedback
---

Am 02.09.2026 endete ein Torlauf mit „Schloss Exit=127", und ich startete ihn
neu. Der erste Lauf war aber nicht tot: Beendet worden waren nur seine
pytest-Prozesse (eine Nachbarsitzung räumte ihre eigenen Waisen ab und traf
meine mit), die Bash-Hülle darum fuhr die restlichen Fensterdateien und die
Leistungstests weiter — und schrieb sie in dieselben Protokoll- und
Ergebnisdateien, die der zweite Lauf gerade neu angelegt hatte. Ich las das
Ende des ersten Laufs („Sammelgruppe lief nicht, Exit 127") und hielt es für
den zweiten; erst „6517 passed in 52:26" an anderer Stelle derselben Datei
widersprach.

**Why:** Der Exit-Code der Hülle sagt nichts über die Prozesse darunter, und
eine gemeinsame Ausgabedatei macht zwei Läufe ununterscheidbar — jede Zeile
sieht echt aus und gehört vielleicht dem anderen.

**How to apply:** Vor einem Neustart die Prozessliste lesen, nicht die
Meldung der Hülle: Lebt noch ein Prozess mit dem Skriptnamen, ist der Lauf
nicht vorbei. Jeder Lauf schreibt in einen eigenen Ordner mit Zeitstempel im
Namen (`tor2.sh`, `fenster.sh`); eine feste Datei wie `tor_suite.txt` wird
nie wiederverwendet. Und wer eine Zusammenfassung liest, prüft, ob sie zu
dem Lauf passt, den er meint — die Laufzeit in der Zeile verrät es. Siehe
[[fremde-zwischenstaende-verfaelschen-messungen]] und
[[temp-dateien-sind-maschinenweit]].
