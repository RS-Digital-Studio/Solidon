---
name: heredoc-verschluckt-backslash-n
description: Bash-Heredoc + Python-Patchskript macht aus \n echte Zeilenumbrüche — dreimal an einem Abend kaputte Stringliterale erzeugt; Mehrzeiliges ohne Escapes bauen.
metadata:
  type: feedback
---

Wer über das Bash-Werkzeug ein Python-Patchskript im Heredoc (`<<'PYEOF'`)
schreibt und darin `"…\n"` in einen Ersetzungstext legt, bekommt in der
geschriebenen Datei einen **echten Zeilenumbruch** statt der zwei Zeichen —
das Stringliteral der Zieldatei ist damit zerrissen (SyntaxError „unterminated
string literal"). Am 25.08.2026 dreimal zugeschnappt (tests/test_manual.py,
tests/test_translations.py, app/cli/main.py), obwohl der zitierte
Heredoc-Delimiter Wörtlichkeit verspricht; irgendein Glied der Kette faltet
eine Escape-Ebene zusammen. `\\n` doppelt zu schreiben half ebenfalls nicht
zuverlässig.

**Why:** Der Fehler entsteht still beim Schreiben und fällt erst beim
nächsten Testlauf als Sammelfehler auf; wer ihn nicht kennt, sucht im
eigenen Ersetzungstext statt in der Transportkette.

**How to apply:** Mehrzeilige Einfügungen ohne Backslash-Folgen bauen —
echte Dreifach-Anführungszeichen mit echten Zeilenumbrüchen, `chr(10)`/
`chr(4)` für Steuerzeichen, oder die Datei zeilenweise mit einer Liste von
Zeilen und `"\n".join` IM ZIEL erzeugen (der join-String entsteht dann im
laufenden Python, nicht im Transport). Für punktuelle Edits das Edit-Werkzeug
nehmen — es transportiert wörtlich. Nach jedem Patch sofort ruff/pytest über
die Datei; der Hook meldet den Riss in Sekunden.
