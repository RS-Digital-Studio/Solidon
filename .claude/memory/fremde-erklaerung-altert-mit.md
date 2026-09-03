---
name: fremde-erklaerung-altert-mit
description: "Eine Erklärung für eine wiederkehrende Warnung stimmt zum Zeitpunkt ihrer Messung — und wird danach zur Standardantwort, die niemand mehr prüft."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: e44e7ebf-a72f-4543-a02a-0efbcc35b48d
  modified: 2026-09-03T05:13:08.503Z
---

03.09.2026: Eine Stunde gewartet, bis a0 sein Tor freigibt. Sein Prozess war
längst tot; das Schloss lag 75 Minuten verwaist da, und `gate_lock.py status`
sagte es mir bei **jedem** Aufruf — „Der Prozessbaum des Halters hat in zwei
Sekunden keine Rechenzeit verbraucht."

Gesehen habe ich die Warnung fünfmal. Abgetan habe ich sie fünfmal mit
derselben Begründung, und die stammte nicht von mir: a0 hatte um 06:30
gemessen, dass sein Lauf rechnet (24,9 CPU-Sekunden in 25), und erklärt, die
Zwei-Sekunden-Warnung treffe in der Bausteinphase fast immer zu. **Das war
richtig — um 06:30.** Danach ist der Prozess gestorben, und ich habe die
Erklärung weiterbenutzt wie eine Eigenschaft der Lage statt wie eine Messung
mit Zeitstempel.

**Why:** Eine eigene Messung altert sichtbar — man weiß, wann man gemessen
hat ([[abgelesene-zahl-altert-still]], [[messung-galt-fuer-den-stand-davor]]).
Eine **fremde** Erklärung altert unsichtbar: Sie kommt ohne Zeitstempel an,
erklärt genau das, was man gerade sieht, und wird damit zur Standardantwort
auf eine wiederkehrende Warnung. Je öfter die Warnung kommt, desto fester
sitzt die Erklärung — obwohl jede Wiederholung ein neuer Anlass wäre, sie zu
prüfen.

**How to apply:** Eine Warnung, die man zum zweiten Mal mit derselben
Begründung abtut, wird nachgemessen — nicht erklärt. Hier kostete das zwanzig
Sekunden: `Get-Process -Id N | Select CPU` zweimal im Abstand, oder ob die
Ausgabedatei wächst ([[.claude/rules/tests.md]], „Steht er oder rechnet er?").
Die Faustregel: **Beim ersten Mal glaubt man die Erklärung, beim zweiten Mal
prüft man sie.**

Und wer wartet, prüft ohnehin lieber selbst: `gate_lock.py status` sagt
inzwischen von sich aus „Ein verwaistes Schloss liegt da", sobald der Prozess
nicht mehr lebt.
