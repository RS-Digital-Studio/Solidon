---
name: commit-meldung-ist-eine-geteilte-datei
description: "Ein privater Index trennt den Baum, nicht die Meldung — `git commit -F` schreibt nach `.git/COMMIT_EDITMSG`, und zwei gleichzeitige Commits tauschen ihre Texte."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 4e2b249b-1d42-4020-bb0e-bdcf350ef625
  modified: 2026-08-30T23:29:43.105Z
---

Am 31.08.2026 landete mein Hauptweg-Test unter der Commit-Meldung einer
Nachbarsitzung: `9c76620f "Das Handbuch kannte die Tauschbörse nicht"` enthielt
`tests/test_catalog_ui.py` mit 154 Zeilen — meinen Test. Meine eigene Meldung
kommt in der Historie gar nicht vor, ihr Handbuch-Commit lief nicht und lag
danach noch ungestaged im Baum.

**Why:** `git commit -F <datei>` liest die Meldung und schreibt sie nach
`.git/COMMIT_EDITMSG`. Diese Datei gehört dem **Repository**, nicht der
Sitzung. Der private Index (`GIT_INDEX_FILE`) trennt den *Baum* — gegen diesen
Fall hilft er nichts, denn er trennt die Meldung nicht. Zwei Commits in
derselben Sekunde greifen auf dieselbe Datei zu, und der zweite findet den
Text des ersten vor.

Inhaltlich geht dabei nichts verloren: Beide Dateistände sind korrekt, nur die
Zuordnung stimmt nicht. Geradeziehen ginge nur über eine History-Umschreibung
und ist das nach dem Push nicht wert.

**Der eigentliche Fehler war die Kontrolle.** Die Ausgabe sagte
`[main 9c76620f] Das Handbuch kannte die Tauschbörse nicht` und darunter
`1 file changed, 154 insertions(+)`. Die **Zahl** passte zu meinem Test, also
habe ich sie geglaubt — und die Zeile darüber überflogen, obwohl dort ein
fremder Satz stand. Dieselbe Familie wie
[[sollprobe-liest-den-fremden-commit]]: Was man am eigenen Commit prüft, muss
den eigenen Commit meinen, und der Umfang allein weist ihn nicht aus.

**Von der anderen Seite sieht es aus wie ein bekannter Fall, und das ist die
Falle.** Bei 15 scheiterte derselbe Wettlauf mit
`fatal: cannot lock ref 'HEAD'` — dem Fehler aus
[[blob-commit-verliert-den-wettlauf]], dessen Regel lautet: *nicht passiert,
Index neu bauen*. Die Regel stimmt und führt hier trotzdem in die Irre, denn
`git log` zeigte danach **die eigene Meldung** an der Spitze. Es sah aus, als
wäre der Commit doch gelaufen; erst `git show --numstat` nannte eine fremde
Datei, und erst `grep` in `HEAD:app/core/manual.py` bewies, dass die eigene
Arbeit *nicht* drin war.

Der Satz dazu: **Ein gescheiterter Commit heißt „meiner ist nicht passiert",
nicht „hier ist nichts passiert."** Wer nach dem Fehler nur den Index neu baut
und committet, tut das Richtige — wer vorher `git log` liest und die eigene
Meldung sieht, hört auf und hält die Arbeit für erledigt.

**How to apply:** Die Zeile, die `git commit` ausgibt, **ganz** lesen — Hash,
**Betreff** und Umfang, nicht nur die Zahl. Und nach einem gescheiterten
Commit nicht die Meldung im Log suchen, sondern **den Inhalt**: `git show
--numstat <hash>` oder ein `grep` auf die Zeile, die man geschrieben hat. Stimmt der Betreff nicht mit der
eigenen Meldung überein, hat ein Wettlauf stattgefunden; dann sofort der
anderen Sitzung Bescheid geben, denn deren Commit ist wahrscheinlich gar nicht
gelaufen und ihre Arbeit liegt noch im Baum. Wer es ganz vermeiden will,
committet in einem eigenen Worktree — der hat sein eigenes `.git`-Verzeichnis
und damit seine eigene `COMMIT_EDITMSG` ([[sonde-im-geteilten-baum]]).

## Wieder passiert am 03.09.2026 — und diesmal hat die Kontrolle gegriffen

`61588789` trägt die Meldung „Ein Punkt in der ausgelieferten 0.3.1 versprach,
was sie nicht hält" (3d-druck-a0, über Bohrungsstopfen) und enthält
`app/ui/viewport.py` mit meinem `_shape_actor` — der Griff, der wieder an die
Öffnung gehört. Zwei Commits um 21:00:45 und 21:01:35, `.git/COMMIT_EDITMSG`
trug a0s Text.

**Der Unterschied zum ersten Mal ist die Kontrolle.** Am 31.08. passte die
Zeilenzahl zu meinem Inhalt, und der falsche Betreff fiel nicht auf. Diesmal
stand er in der Ausgabe, wurde gelesen und sofort untersucht — der Commit war
vier Minuten später als solcher benannt, statt Wochen später jemanden zu
verwirren.

**Was daraus folgt und was nicht.** Vermeiden lässt sich der Fall nicht: `-F`
schreibt immer über dieselbe Datei, und wann eine Nachbarsitzung committet, ist
nicht messbar. Erkennen lässt er sich in einer Sekunde, und das ist der ganze
Schutz: **Nach jedem Commit den Betreff der Ausgabe gegen den erwarteten
lesen.** Der Fehler ist nicht die Verwechslung, sondern eine Verwechslung, die
niemand bemerkt.
