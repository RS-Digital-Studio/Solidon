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

**How to apply:** Commit-Meldungen mit `<<'ENDE'` schreiben (einfache
Anführungszeichen: keine Expansion von `$`, Backticks oder `\`), Umlaute
direkt tippen. Wer bei einem *anderen* Werkzeug unsicher ist, misst es an
einem Fall, dessen Ausgang er kennt, statt vorsorglich auszuweichen —
Ausweichen ist hier keine sichere Wahl, sondern ein anderer Regelbruch.
