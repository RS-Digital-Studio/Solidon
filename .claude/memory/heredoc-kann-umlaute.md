---
name: heredoc-kann-umlaute
description: "Aus Angst vor Quoting-Fallen ASCII zu schreiben bricht die Sprachregel — das Heredoc überträgt Umlaute einwandfrei, gemessen."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: fd3340f1-dc7c-45b2-a76c-25431a7a9212
  modified: 2026-08-30T21:51:15.391Z
---

Ein `git commit -F - <<'MELDUNG'` überträgt **Umlaute unverändert**. Gemessen
am 27.08.2026: „Zwölf Rückmeldungen, größer als groß — ähnlich, öfter, süß"
kam als 70 Bytes für 58 Zeichen heraus, also sauber UTF-8, mit Gedankenstrich.

**Why:** An dem Tag waren mehrere Bash-Fallen zugeschnappt — Backticks als
Kommandosubstitution, deutsche Anführungszeichen, die einen Python-String
beendeten ([[heredoc-verschluckt-backslash-n]]). Die Lehre daraus wurde zu
breit gezogen: Ich schrieb zwei Commit-Meldungen vorsorglich in ASCII
(„zwoelf", „Rueckmeldungen") und brach damit die Regel, die überall gilt —
echte Umlaute, keine ae/oe/ue-Ersatzschreibung. Die Meldungen stehen so auf
`origin`; geradezuziehen wären sie nur per Force-Push.

Die eigentliche Falle war nicht das Heredoc, sondern die **Verallgemeinerung**:
„Bash hat mich heute dreimal reingelegt" wurde zu „Bash kann kein UTF-8". Das
eine ist eine Beobachtung, das andere eine Behauptung über ein Werkzeug —
und die kostet eine Sekunde zu prüfen ([[messwerkzeug-misst-sich-selbst]]).

**Wiederholung am 28.08.2026, und sie ist der wichtigere Teil dieser
Notiz.** Diese Datei existierte, sagte genau das Richtige, und ich habe es
trotzdem wieder falsch gemacht: **drei** Commits mit null Umlauten
(87b00475, e1f3637c, a2f5d8f0), ein vierter mit zweien (725777b7). Alle vier
über ein Heredoc geschrieben, alle vier vorsorglich in ASCII. Gefunden hat es
eine Nachbarsitzung, nicht ich.

Damit ist die Lehre nicht mehr „das Heredoc kann Umlaute" — das wusste ich —,
sondern: **Im Moment des Schreibens denkt niemand an diese Notiz.** Eine Regel,
die Sorgfalt in einem einzelnen Befehl verlangt, verliert gegen die Gewohnheit
([[benannte-falle-schuetzt-nicht]]). Was hilft, ist ein anderes *Werkzeug*,
nicht ein besserer Vorsatz.

Dieselbe Familie, dritte Gestalt, am selben Tag zweimal: Ein deutsches
**schließendes** Anführungszeichen, versehentlich als gerades `"` getippt,
beendet einen Python-String mitten im Satz. Einmal in einem Test, einmal in
genau dem Skript, das diese Zeilen hier eintragen sollte.

**Dritter Rückfall am 30.08.2026 — und er zeigt, wo die Regel bisher zu eng
formuliert war.** Drei Commits ohne einen einzigen Umlaut (`55dadda1`,
`b3b1bd8f`, `dc01cc3d`: „faellt", „unvollstaendiger", „Raendelung"), während
fünf Commits desselben Abends über Write-Dateien tadellos waren
(`42e6303d`, `9306ed26`, `afebc431`, `33c55c51`, `d50f4942`). Der Unterschied
ist genau das Werkzeug — und diesmal war es **kein Heredoc, sondern `printf`**.

Die Notiz hieß „Heredoc kann Umlaute", also las ich sie als Aussage über das
Heredoc und nicht als Anweisung über deutschen Text. Mit einem anderen
Bash-Werkzeug fühlte sich die Vorsicht wieder neu und begründet an. **Die
Regel ist nicht „das Heredoc ist sicher", sondern: kein deutscher Text geht
durch die Shell** — nicht per Heredoc, nicht per `printf`, nicht per `-m`, und
auch nicht per `echo`.

**How to apply:** Commit-Meldungen **und jedes Patchskript mit deutschem Text**
mit dem **Write-Werkzeug** in eine Datei schreiben, dann `git commit -F <datei>`
beziehungsweise das Skript laufen lassen. Das umgeht die Quoting-Frage
vollständig, statt sie richtig zu beantworten — und es ist die einzige Fassung,
die vier Anläufe überlebt hat. Die Gegenprobe kostet nichts und findet den
Rückfall sofort: `git log -1 --format=%B | grep -cE "ä|ö|ü|ß"` — steht dort
eine Null unter einem deutschen Absatz, ist es passiert.

Bleibt ein Heredoc unvermeidlich, dann `<<'ENDE'` (einfache Anführungszeichen:
keine Expansion von `$`, Backticks oder `\`) und Umlaute direkt tippen. Wer bei
einem *anderen* Werkzeug unsicher ist, misst es an einem Fall, dessen Ausgang er
kennt, statt vorsorglich auszuweichen — Ausweichen ist hier keine sichere Wahl,
sondern ein anderer Regelbruch.
