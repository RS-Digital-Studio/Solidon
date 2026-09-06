---
name: deutscher-text-geht-nicht-durch-die-shell
description: "Fünf Fallen einer Familie — Escape-Folgen, Backticks, stdin-Codepage, deutsches Schlusszeichen, CRLF-Verdopplung — und die eine Regel dagegen: Text über das Write-Werkzeug in eine Datei, Skripte aus Dateien fahren, danach lesen, was dasteht."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 604362f2-7546-4f58-8ac6-a717d093adc0
  modified: 2026-09-06T13:27:05.677Z
---

Zwischen dem, was ich schreibe, und dem, was in der Datei oder im Commit
landet, liegen zwei Interpreten — die Shell und Python —, und jeder frisst
seine eigenen Sonderzeichen, während beide Erfolg melden. Zwischen dem 25.08.
und dem 31.08.2026 ist dieselbe Familie in fünf Gestalten zugeschnappt, jede
mehrfach; drei Rückfälle passierten, *obwohl* die Notiz dazu schon existierte.

| Gestalt | Was passiert | Gemessen |
|---|---|---|
| `"\n"` im Heredoc-Patchskript | irgendeine Ebene faltet die Escape-Folge, das Zieldateiliteral zerreißt (`unterminated string literal`); der Reparaturversuch faltet erneut | 25.08. dreimal, 30.08. zweimal |
| Backticks in `python -c "…"` | Bash führt den Codespan als Kommando aus und setzt seine Ausgabe ein — der Text fehlt, das Skript meldet Erfolg | 30.08. |
| `python - << 'ENDE'` mit Umlaut | Python liest `stdin` mit der System-Codepage: `SyntaxError: invalid character '—'`; aus dem Fehler wurde vorsorgliches ASCII im nächsten Commit | 30.08. |
| Deutsches Schlusszeichen `“` als `"` getippt | beendet den Python-String mitten im Satz; das öffnende `„` steht richtig da, das Auge liest das Paar als ganz | 30.08. dreimal |
| `newline=""` nur beim Lesen | `write_text` übersetzt `\n` nach `\r\n`, aus `\r`+`\n` wird `\r\r\n`; `ruff format` in derselben Kette macht daraus 2863 Stücke ohne ein einziges `\n` | 31.08., `test_analysis_ui.py` |

Und die Verallgemeinerung war jedes Mal der teurere Fehler: „Bash hat mich
heute dreimal reingelegt" wurde zu „Bash kann kein UTF-8", und vier Commits
gingen vorsorglich in ASCII hinaus (`87b00475`, `e1f3637c`, `a2f5d8f0`,
`55dadda1`, `b3b1bd8f`, `dc01cc3d`) — ein Bruch der Sprachregel, der nur per
Force-Push zu heilen wäre. Gemessen überträgt `git commit -F - <<'MELDUNG'`
Umlaute sauber (70 Bytes für 58 Zeichen). Das Heredoc war nie das Problem;
`printf`, `-m` und `echo` sind dieselbe Shell.

**Why:** Eine Regel, die Sorgfalt in einem einzelnen Befehl verlangt, verliert
gegen die Gewohnheit ([[benannte-falle-schuetzt-nicht]]). Im Moment des
Schreibens denkt niemand an diese Notiz. Was hilft, ist ein anderes
*Werkzeug*, nicht ein besserer Vorsatz.

**How to apply:**

* **Kein deutscher Text geht durch die Shell** — nicht per Heredoc, `printf`,
  `-m`, `echo` oder `python -c`. Commit-Meldungen und Patchskripte entstehen
  über das **Write-Werkzeug** als Datei (UTF-8, ohne Codepage), dann
  `git commit -F <datei>` beziehungsweise das Skript aus der Datei fahren. Für
  punktuelle Änderungen das Edit-Werkzeug: Es transportiert wörtlich.
* Bleibt ein Heredoc unvermeidlich: `<<'ENDE'` (keine Expansion von `$`,
  Backticks, `\`), Umlaute direkt tippen, Sonderzeichen im Skript aus
  `chr(...)` bauen statt sie zu escapen; über `stdin` nur als `\uXXXX`.
* In Assert-Meldungen `!r` statt Anführungszeichen: `f"{schluessel!r} fiele
  auf {ziel!r}"` kann nicht brechen und zeigt unsichtbare Zeichen mit.
* `newline=""` gehört an **beide** Enden oder an keines; sicherer: beim Lesen
  `.replace("\r\n", "\n")`, am Ende einmal zurück. Und **vor** dem Formatierer
  prüfen (`read_bytes().count(b"\r\r")`), nicht danach — `ruff format` macht
  aus einem reparablen Schaden einen unreparablen.
* Danach **lesen, was dasteht**, nicht dem Rückgabewert glauben: `sed -n` auf
  die geänderten Zeilen; für den Commit
  `git log -1 --format=%B | grep -cE "ä|ö|ü|ß"` — eine Null unter einem
  deutschen Absatz heißt, es ist passiert.

Verwandt: [[patchskript-schneidet-fremdes-weg]] (dort löscht das Skript
fremde Arbeit, hier die eigene Struktur), [[messwerkzeug-misst-sich-selbst]]
(ein Werkzeug an einem Fall mit bekanntem Ausgang messen, statt vorsorglich
auszuweichen).

**Nachtrag 03.09.2026 — auch Backslash-Escapes gehen nicht durch.** Ein
Patchskript im Heredoc, das `b"\0" * 4096` in eine Python-Datei schreiben
sollte, schrieb ein echtes NUL-Byte: mypy „Source code string cannot contain
null bytes", pytest ein Sammelfehler in drei Dateien, und die erste Reparatur
mit `data.replace(b"\x00", b"\0")` — wieder im Heredoc — änderte nichts, weil
dieselbe Übersetzung sie traf. Sicher war erst die escape-freie Form:
`bytes([0])` und `bytes([92, 48])`. Wer im Heredoc Backslashes braucht, baut sie
aus `chr(92)` oder Byte-Zahlen, oder schreibt das Skript mit dem Write-Werkzeug.

**Nachtrag 06.09.2026 — auch `<<'PYEOF'` schützt Backslashes nicht.** Ein
Patchskript mit `'"<?php\\n"\n'` im quoted Heredoc fand seinen Anker nicht
(`count == 0`), obwohl der Ankertext wörtlich in der Datei stand; dasselbe Skript
über das Write-Werkzeug als Datei traf sofort. Und ein Heredoc mit `„…“` im
Python-Quelltext brach die Shell ganz („unexpected EOF while looking for
matching `''“). Regel für diese Umgebung: **jedes Patchskript, das
Backslashes, typografische Anführungszeichen oder mehr als ein paar Zeilen
hat, entsteht über das Write-Werkzeug**; das Heredoc bleibt für ASCII-kurze
Einzeiler.
