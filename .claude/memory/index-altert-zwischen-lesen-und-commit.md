---
name: index-altert-zwischen-lesen-und-commit
description: "Ein korrekt aus HEAD gelesener privater Index nimmt fremde Arbeit zurück, wenn zwischen read-tree und commit ein fremder Commit fällt — die Minuten fürs Prüfen genügen."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: cc0c50ad-6ea5-4d75-b0d4-2e514a473ea3
  modified: 2026-09-03T22:46:41.548Z
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

**Und die Regel „unmittelbar davor" reicht nicht, weil ein Befehl
dazwischenliegt, den man nicht sieht: der pre-commit-Hook.** Am 30.08.2026
nahm `73e3060d` d5s Fortschreibung an ROADMAP-Zeile P9 zurück — obwohl genau
nach Vorschrift gearbeitet war: `read-tree HEAD`, sieben `update-index`,
sofort `commit`, kein Prüfen, kein Nachrechnen. Der Hook fährt Sprachprüfung
und Kataloge, das dauert Sekunden bis Minuten, und er läuft **nachdem** der
Index steht. Dieses Fenster lässt sich nicht wegkürzen: Es ist kein Fehler in
der Arbeitsweise, sondern ein Rennen, das jeder Commit eingeht.

Was bleibt, ist die Prüfung **danach**, und die ist billig: die eigene
Dateizahl gegen `git show --numstat --format="" HEAD`. Sieben erwartet, acht
bekommen — die achte war fremd, und der ganze Fall stand in einer Zeile.

**Und ein gefangener erster Wettlauf schützt nicht vor dem zweiten.** Am
31.08.2026 nahm `4c51a81a` 45 Zeilen aus `texture_ops.py` und 107 aus seinem
Test zurück — obwohl ich den Index **zweimal** frisch gelesen hatte. Beim
ersten Mal fiel der Wettlauf am Guard auf (acht Dateien statt sechs,
`ROADMAP.md` und `orientation.py` darunter), ich las neu, der Guard zeigte
sechs. Genau in dem Fenster zwischen dieser Prüfung und dem Commit fiel der
nächste fremde Commit.

Das ist die gefährlichere Lage, weil sie sich wie Sorgfalt anfühlt: Wer einen
Wettlauf gefangen hat, hält den zweiten Bau für abgesichert — und hat in
Wahrheit nur bewiesen, dass Wettläufe in diesem Baum gerade häufig sind.
**Ein Guard, der nichts findet, sagt nichts über die nächste Sekunde.**

Dieser Fall ist außerdem der Beleg, dass die Notiz nicht am Inhalt scheitert:
Sie stand vollständig hier, mit genau der Anweisung, die gefehlt hat. Was
fehlte, war kein Satz, sondern dass jemand sie vor dem Commit aufschlägt —
dieselbe Sorte Lücke wie bei [[baustein-begriff-je-sprache]], nur ohne den
Trost, dass die Warnung schlecht platziert gewesen wäre.

**Und der alte Index verfälscht nicht nur den Commit, sondern die Frage
danach.** Am 04.09.2026 meldete `git diff HEAD` in `.claude/memory/` drei
gelöschte Dateien, 56 Rücknahmen — darunter eine Notiz, die eine Stunde vorher
wiederhergestellt worden war. Sie war nicht weg: Sie lag im Baum, bytegleich
mit HEAD. Der Haupt-Index führte sie als gelöscht, weil mit privatem Index
committet worden war, und **`git diff HEAD` zieht den Index als Zwischenspeicher
heran** und zeigt dessen Löschung mit.

Das trifft ausgerechnet die Frage, die vor einem Release am häufigsten gestellt
wird: „Liegt noch etwas Halbes im Baum?" Sie wird mit `git diff HEAD`
beantwortet, und die Antwort ist in einem Baum mit privaten Commits falsch —
sie meldet Löschungen, die keine sind. Wer ihr folgt, sucht nach verschwundener
Arbeit, die nie verschwunden war.

Die tragende Frage vergleicht **Inhalt gegen HEAD-Blob, ohne den Index zu
fragen** (`git show HEAD:<datei>` gegen die Datei, oder `git diff --no-index`).
So gemessen blieben von den drei gelöschten null übrig.

Es ist derselbe Mechanismus wie oben, eine Ebene weiter: Der veraltete Index
nimmt beim Schreiben fremde Arbeit zurück **und** beim Lesen fremde Arbeit
vorweg. Der zweite Fall kostet kein Byte, nur Zeit — und Vertrauen in die
eigene Messung, was vor einem Tag teurer sein kann.

**How to apply:**

* `git read-tree HEAD` **unmittelbar** vor `git commit` — kein Prüfen, kein
  Nachrechnen, keine Meldung dazwischen. Die Commit-Meldung vorher schreiben,
  in eine Datei, und mit `-F` übergeben.
* **Und beides in eine Schleife, die bei `cannot lock ref` neu ansetzt.** Am
  03.09.2026 zweimal gemessen, beide Male scheiterte Versuch 1 und Versuch 2
  ging durch:

      for v in 1 2 3 4 5; do
        git read-tree HEAD && git add -- $D
        git commit -F msg.txt -o -- $D > log 2>&1 && break
        grep -q "cannot lock ref" log && continue
        break   # ein anderer Fehler, der wiederholt sich nicht weg
      done

  Was sie leistet: Git **erkennt** den Wettlauf selbst, wenn HEAD sich
  während des Commits bewegt — also im Fenster des pre-commit-Hooks, das oben
  als das unvermeidbare beschrieben ist. Es meldet dann
  `cannot lock ref 'HEAD': is at <neu> but expected <alt>` und schreibt
  **nichts**. Der Schaden entsteht erst, wenn man diesen Fehlschlag für
  „nichts passiert" hält und weiterarbeitet.

  **Was sie nicht leistet, und das ist der Punkt:** Fällt der fremde Commit
  *vor* dem Start meines `git commit`, ist HEAD während des Commits stabil,
  git meldet nichts, und der veraltete Index nimmt die fremde Arbeit zurück —
  genau der Fall `c36627e9` oben. Die Schleife verkleinert das Fenster auf die
  Zeit zwischen `read-tree` und dem Ref-Schreiben; sie schließt es nicht. Die
  Nachkontrolle über `git show --numstat` bleibt deshalb Pflicht.
* Nach jedem Commit `git show --numstat --format="" HEAD` lesen und die Zahl
  der Dateien mit der eigenen vergleichen. Die Meldung von `git commit` nennt
  sie selbst — „N files changed" gegen die eigene Zahl ist eine Sekunde.
* Fällt es auf: **vorwärts heilen, nie reverten.** Der Arbeitsbaum trägt die
  fremde Arbeit weiter, denn ein Commit über `GIT_INDEX_FILE` fasst ihn nicht
  an. Vor dem Heilen `git diff <fremder-commit> -- <dateien>` fahren: leer
  heißt, der Baum ist genau ihr committeter Stand und kein halber.
* Der Betroffenen sofort schreiben, mit beiden Hashes und dem Beleg, dass ihr
  Stand vollständig war. Sie sieht es sonst im Log und muss raten.
* **„Liegt noch etwas Halbes im Baum?" nie mit `git diff HEAD` beantworten**,
  solange irgendwer im Baum mit privatem Index committet. Der Index antwortet
  mit, und seine Löschungen sind keine. Stattdessen den Inhalt gegen den
  HEAD-Blob halten — und eine gemeldete Löschung erst glauben, wenn die Datei
  wirklich fehlt.

Verwandt, aber ein anderer Mechanismus: [[geteilter-index-haelt-alten-stand]]
(der Haupt-Index war von Anfang an alt), [[commit-o-nimmt-den-dateistand]] (der
Index hält fremde Dateien heraus, nicht den fremden Stand einer gemeinsamen),
[[privater-index-fester-name]] und [[parallele-sitzungen-solidon3d]].
