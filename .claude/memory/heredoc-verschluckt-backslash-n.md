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

**Die Schwester dazu, am 30.08.2026 zugeschnappt: Backticks in `python -c "..."`.**
Ein Erinnerungs-Nachtrag wurde über `python -c "…"` in **doppelten**
Anführungszeichen geschrieben. Der Text enthielt einen Markdown-Codespan mit
einem Git-Aufruf darin. Bash führte den Backtick-Inhalt als Kommando aus und
setzte dessen Ausgabe ein — die Fehlermeldung landete auf stderr, der Codespan
verschwand spurlos, und in der Datei stand „Attribution braucht  auf den
Zeileninhalt".

**Still, wie die andere Falle:** Das Skript meldete Erfolg, die Datei war
geschrieben, nur der Inhalt war ein anderer. Aufgefallen ist es an einer
beiläufigen Fehlerzeile über der Erfolgsmeldung.

Gegengift ist dasselbe: **geschütztes Heredoc** (`<<'MARKE'`), nie doppelte
Anführungszeichen um Text mit Backticks, Dollarzeichen oder Ausrufezeichen. Und
danach **lesen, was dasteht** — nicht dem Rückgabewert des Schreibens glauben.

**Und die dritte Gestalt, am selben Tag zweimal hintereinander: die
Escape-Folge im Patchskript selbst.** Ein Skript sollte
`self._details = "\n".join(lines)` in eine Datei schreiben. Über ein
Heredoc durchgereicht wurde aus `\n` ein **echter Zeilenumbruch** — das
String-Literal zerbrach, und ruff meldete elf Folgefehler quer durch die
Datei, von denen keiner die Ursache nannte.

**Der Reparaturversuch lief in dieselbe Falle.** Ein zweites Skript, das den
kaputten Text gegen den heilen tauschen sollte, faltete beim Durchreichen
erneut — und schrieb denselben Schaden zurück. Das Skript meldete
„repariert".

Gelöst, indem der Ersatz **aus Teilen gebaut** wird: `chr(92)` liefert den
Backslash im laufenden Python, und durch die Shell muss keiner. Dieselbe
Technik trägt für Dollarzeichen und Backticks.

**Why (für alle drei Gestalten dasselbe):** Zwischen dem, was ich schreibe,
und dem, was in der Datei landet, liegen zwei Interpreten — die Shell und
Python. Jeder frisst seine eigenen Sonderzeichen, und beide melden Erfolg.

**How to apply:** Wo ein Skript Sonderzeichen in eine Datei schreiben soll,
baue sie aus `chr(...)` statt sie zu escapen. Und danach **lesen, was
dasteht** — nicht dem Rückgabewert des Schreibens glauben. `sed -n` auf die
geänderten Zeilen kostet eine Sekunde.

