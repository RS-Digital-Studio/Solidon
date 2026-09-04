---
name: sollprobe-liest-den-fremden-commit
description: "Die Umfangsprüfung nach dem Commit an HEAD zu machen misst im geteilten Baum einen fremden Commit — sie meldet Dateien, die man nie angefasst hat."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 4e2b249b-1d42-4020-bb0e-bdcf350ef625
  modified: 2026-09-03T22:53:50.515Z
---

Am 30.08.2026 meldete meine Sollprobe nach `afebc431` die Datei
`tests/test_directory_docs.py` mit 58 Zeilen — eine Datei, die ich nie
angefasst hatte. Für zwei Sekunden sah es aus, als hätte mein Commit fremde
Arbeit mitgenommen.

Hatte er nicht. Zwischen meinem Commit und der Prüfung war ein fremder Commit
gelandet, und `HEAD` zeigte auf **den**. Der eigene stand schon eine Stelle
tiefer und war sauber: `git show --numstat afebc431` → genau eine Datei.

Der Befehl war `git show --numstat --format="%h %s" HEAD` — in derselben
Befehlszeile wie der Commit, also Millisekunden danach. Das genügt.

**Why:** Das ist [[index-altert-zwischen-lesen-und-commit]] in der
Kontrollvariante — dort verfälscht die Zeit den **Commit**, hier die
**Prüfung**. Beide Male ist `HEAD` kein fester Punkt, sondern eine Frage, die
bei jedem Aufruf neu beantwortet wird. Der Fehlalarm ist dabei der harmlosere
Ausgang: Wer ihm glaubt, sucht einen Fehler, den es nicht gibt, und im
schlimmsten Fall „repariert" er einen fremden Commit. Verwandt mit
[[geteilter-baum-misst-zeitpunkt]] und
[[fremde-zwischenstaende-verfaelschen-messungen]].

**How to apply:** Unmittelbar nach dem Commit den eigenen Hash festhalten
(`MEIN=$(git rev-parse HEAD)`) und jede Nachkontrolle gegen **den** fahren —
Umfangsprobe, `--numstat`, `--stat`. Nie gegen `HEAD`. Dasselbe gilt für
`git show HEAD` beim Vorlesen der eigenen Commit-Meldung. Meldet eine
Sollprobe eine fremde Datei, ist die erste Frage nicht „was habe ich falsch
gemacht", sondern `git log --oneline -3`: Steht der eigene Commit dort nicht
mehr an erster Stelle, hat die Probe jemand anderen gemessen.

**Und der Fall ohne Fehlalarm, der gefährlicher ist: zwei eigene Messungen,
die sich widersprechen.** Am 04.09.2026 las ich `git show HEAD:tests/test_toolchain.py`
und fand eine Zeile nicht, die im Baum stand — ein Beleg dafür, dass HEAD einen
roten Wächter trug. Zur Bestätigung baute ich zwei Minuten später einen
Probe-Worktree auf HEAD und fuhr den Wächter dort: **grün**.

Beide Messungen waren sauber. Dazwischen hatte eine fremde Sitzung genau diese
Reparatur committet, und „HEAD" bedeutete beim zweiten Mal einen anderen Stand
(`b02a2110` → `fd2c852f`). Der Schluss, zu dem ich fast gekommen wäre — „HEAD
war doch grün, die Zeile ist Kosmetik" — hätte einen echten Blocker als
Nichtigkeit abgelegt: Sechs Tests wären in der CI rot geworden.

Das ist die unauffälligere Bauart, weil der übliche Reflex hier in die falsche
Richtung zeigt. Widersprechen sich zwei eigene Messungen, sucht man den
**Messfehler** — nicht die Bewegung des Gegenstands. Im geteilten Baum ist die
Bewegung aber die häufigere Erklärung, und der Test darauf ist eine Zeile:
`git rev-parse HEAD` vor und nach der Messreihe, oder gleich beide Messungen
gegen denselben festgehaltenen Hash.

Zwei Nachträge von 15, die denselben Fall am selben Abend unabhängig
aufgeschrieben hatte (ihre Notiz ist zugunsten dieser gelöscht):

* **`HEAD~2` ist genauso beweglich wie `HEAD`** — es zählt Positionen, nicht
  Urheber. Wer den vorletzten eigenen Commit nachsehen will, nimmt auch dort
  den Hash.
* **Der billigste Beleg steht schon da:** die Zeile, die `git commit` selbst
  ausgibt („1 file changed, 58 insertions(+)"). Sie entsteht über den gerade
  erzeugten Commit und kann gar nichts anderes meinen — wer sie liest, braucht
  die Nachprüfung nur noch für das, was sie nicht zeigt (die Dateinamen).
