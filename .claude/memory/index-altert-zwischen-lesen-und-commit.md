---
name: index-altert-zwischen-lesen-und-commit
description: "Ein korrekt aus HEAD gelesener privater Index nimmt fremde Arbeit zurück, wenn zwischen read-tree und commit ein fremder Commit fällt — die Minuten fürs Prüfen genügen."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: cc0c50ad-6ea5-4d75-b0d4-2e514a473ea3
  modified: 2026-08-30T16:26:44.880Z
---

Am 30.08.2026 nahm mein Commit `c36627e9` 47 Zeilen aus `app/ui/style.py` und
`tests/test_style.py` zurück — die Arbeit von 72 aus `6c1b28ee`.

**Der private Index war richtig.** Er war mit `read-tree HEAD` frisch gelesen
und trug per `update-index --add` genau meine dreizehn Dateien; `git diff
--cached HEAD --numstat` zeigte vor dem Commit exakt diese dreizehn und keine
fremde. Der Fehler lag nicht im Index, sondern **zwischen** zwei Befehlen.

Zwischen `read-tree` und `commit` lagen die Minuten fürs Nachrechnen und für
die Commit-Meldung. In denen hat 72 committet. Ein Index ist ein
**vollständiger Baum, kein Diff** — was seither dazukam, nimmt er beim
Schreiben zurück, ohne dass irgendein Befehl davor es hätte anzeigen können.

**Why:** Die Prüfung `git diff --cached HEAD` beantwortet die Frage „ist mein
Index sauber?" — und sie beantwortet sie ehrlich für den Zeitpunkt, an dem sie
läuft. Der Commit passiert später. Zwischen beiden liegt in einem Baum mit
fünf Sitzungen ein realer Zeitraum, und je gründlicher man prüft, desto größer
wird er. Das ist die Umkehrung der üblichen Erwartung: **Sorgfalt vergrößert
das Fenster, statt es zu schließen.**

Der Riss zeigt sich in der Zeile, die man ohnehin liest: `git commit` meldete
„15 files changed" bei dreizehn im Index. Der Zeilenvergleich bestätigte es
(840 statt 839 Zusätze, 98 statt 51 Rücknahmen) — die Rücknahmen sind der
Verräter, nicht die Zusätze.

**How to apply:**

* `git read-tree HEAD` **unmittelbar** vor `git commit` — kein Prüfen, kein
  Nachrechnen, keine Meldung dazwischen. Die Commit-Meldung vorher schreiben,
  in eine Datei, und mit `-F` übergeben.
* Nach jedem Commit `git show --numstat --format="" HEAD` lesen und die Zahl
  der Dateien mit der eigenen vergleichen. Die Meldung von `git commit` nennt
  sie selbst — „N files changed" gegen die eigene Zahl ist eine Sekunde.
* Fällt es auf: **vorwärts heilen, nie reverten.** Der Arbeitsbaum trägt die
  fremde Arbeit weiter, denn ein Commit über `GIT_INDEX_FILE` fasst ihn nicht
  an. Vor dem Heilen `git diff <fremder-commit> -- <dateien>` fahren: leer
  heißt, der Baum ist genau ihr committeter Stand und kein halber.
* Der Betroffenen sofort schreiben, mit beiden Hashes und dem Beleg, dass ihr
  Stand vollständig war. Sie sieht es sonst im Log und muss raten.

Verwandt, aber ein anderer Mechanismus: [[geteilter-index-haelt-alten-stand]]
(der Haupt-Index war von Anfang an alt), [[commit-o-nimmt-den-dateistand]] (der
Index hält fremde Dateien heraus, nicht den fremden Stand einer gemeinsamen),
[[privater-index-fester-name]] und [[parallele-sitzungen-solidon3d]].
