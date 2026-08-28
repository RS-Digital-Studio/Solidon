---
name: heredoc-kann-umlaute
description: "Aus Angst vor Quoting-Fallen ASCII zu schreiben bricht die Sprachregel — das Heredoc überträgt Umlaute einwandfrei, gemessen."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: fd3340f1-dc7c-45b2-a76c-25431a7a9212
  modified: 2026-08-27T10:59:51.660Z
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

**How to apply:** Commit-Meldungen **und jedes Patchskript mit deutschem Text**
mit dem **Write-Werkzeug** in eine Datei schreiben, dann `git commit -F <datei>`
beziehungsweise das Skript laufen lassen. Das umgeht die Quoting-Frage
vollständig, statt sie richtig zu beantworten — und es ist die einzige Fassung,
die drei Anläufe überlebt hat. (Die Nachbarsitzung hat es am 28.08.2026 so
gemacht und nachgezählt: fünf Zeilen mit echten Umlauten.)

Bleibt ein Heredoc unvermeidlich, dann `<<'ENDE'` (einfache Anführungszeichen:
keine Expansion von `$`, Backticks oder `\`) und Umlaute direkt tippen. Wer bei
einem *anderen* Werkzeug unsicher ist, misst es an einem Fall, dessen Ausgang er
kennt, statt vorsorglich auszuweichen — Ausweichen ist hier keine sichere Wahl,
sondern ein anderer Regelbruch.
