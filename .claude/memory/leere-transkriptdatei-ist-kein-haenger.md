---
name: leere-transkriptdatei-ist-kein-haenger
description: "Die Ausgabedatei eines Hintergrund-Agenten kann über eine Stunde 0 Byte bleiben, während er arbeitet — am 14.09.2026 zwei arbeitende Reviewer als „hängend\" beendet; nur der Abbruchbericht zeigte den Fortschritt. Liveness über den Abbruchbericht oder eine Nachricht prüfen, nicht über die Dateigröße."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 1ca7314c-d749-4b85-aac6-9da0d8f5da54
  modified: 2026-09-14T12:12:00.330Z
---

Am 14.09.2026 liefen drei `solidon3d-review`-Agenten parallel über je einen
Commit. Einer schrieb sein Transkript laufend (861 KB nach 90 Minuten), die
zwei anderen hielten ihre Ausgabedatei bei **0 Byte** — auch nach 90 Minuten.
Ich hielt sie für hängend (Verdacht: `git show` im Pager) und beendete sie;
der Abbruchbericht des einen lautete „Now I read the current HEAD state of the
touched code" — er hatte den ganzen Diff gelesen und arbeitete. Beim zweiten
Anlauf dasselbe: nach 27 Minuten 0 Byte, beendet, Abbruchbericht „Now let me
check the key code at HEAD". Zweimal arbeitende Reviewer getötet, zweimal
die Wartezeit von vorn.

**Why:** Die Transkriptdatei wächst nicht gleichmäßig mit der Arbeit — ob und
wann sie geschrieben wird, hängt offenbar davon ab, was der Agent tut (der
eine, der schrieb, fuhr Sonden über Bash; die zwei, die nicht schrieben, lasen
mit Read und Grep). Die Dateigröße ist damit kein Maß für Leben, und „seit
dem Start 0 Byte" ist kein Befund, sondern die Abwesenheit eines Signals
(vgl. [[zustandswert-widerlegt-keinen-haenger]] — hier umgekehrt: ein
fehlender Wert beweist keinen Hänger).

**How to apply:** Bevor ein Hintergrund-Agent als hängend beendet wird:
`ListAgents` zeigt nur „running", das reicht nicht; eine Nachricht über
`SendMessage` mit der Bitte um einen Einzeiler Stand, oder schlicht warten —
ein Review mit opus/max über 1 500 Diff-Zeilen dauert ein bis zwei Stunden.
Wer trotzdem beendet, liest den Abbruchbericht (`<result>` in der
Benachrichtigung): Steht dort ein Satz mitten aus der Arbeit, war der Agent
nicht hängend, und der Neustart kostet die ganze Zeit noch einmal. Lange
Reviews besser sequenziell mit Zeitziel im Auftrag starten, statt parallel
und mit Ungeduld.
