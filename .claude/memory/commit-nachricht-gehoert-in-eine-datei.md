---
name: commit-nachricht-gehoert-in-eine-datei
description: Commit-Nachrichten über Write in eine Datei schreiben, nie über ein Heredoc — sonst kostet ein Encoding-Fehler die Umlaute.
metadata:
  type: feedback
---

Am 30.08.2026 ist ein Commit mit **ASCII-Ersatzformen** hinausgegangen —
`fuenf`, `faellt`, `dauerhaft`, `ausdruecklich`, `Schliessen`. Die Sprachregel
verlangt echte Umlaute, und der Text war schon gepusht, als es auffiel.

**Der Weg dorthin ist der eigentliche Fund.** Unmittelbar davor war ein Skript
über `python - << 'ENDE'` an einem Umlaut gescheitert:

    SyntaxError: invalid character '—' (U+2014)

Python liest `stdin` mit der System-Codepage, nicht mit UTF-8. Aus diesem einen
echten Fehler wurde die falsche Verallgemeinerung „Sonderzeichen sind hier
gefährlich", und die nächste Commit-Nachricht entstand vorsorglich in ASCII.

**Why:** [[heredoc-kann-umlaute]] hält fest, dass ein Heredoc Umlaute sauber
überträgt — und das stimmt für `cat > datei << 'ENDE'`. Es stimmt **nicht**
für `python - << 'ENDE'`: Dort ist nicht das Heredoc das Problem, sondern
Pythons `stdin`-Decoder. Zwei verschiedene Wege, ein Name, und die Erinnerung
deckte nur den einen ab.

**How to apply:** Eine Commit-Nachricht entsteht als **Datei über das
Write-Werkzeug**, dann `git commit -F <datei>`. Write schreibt UTF-8, unabhängig
von jeder Codepage. Dasselbe gilt für Patch-Skripte mit deutschem Text: Datei
schreiben und fahren, nicht durch `stdin` schieben.

Wo ein Skript doch über `stdin` muss, gehören Sonderzeichen als
`\uXXXX`-Escapes hinein — das ist reines ASCII im Quelltext und echtes UTF-8 im
Ergebnis.

**Und die Prüfung danach kostet eine Sekunde:**

```bash
git log -1 --format=%B | grep -oE "[a-zä-ü]+(ae|oe|ue|ss)[a-zä-ü]*"
```

Verwandt: [[heredoc-verschluckt-backslash-n]] — dieselbe Familie, andere
Ursache: Dort faltet Bash die Escape-Folge, hier verschluckt Python das
Zeichen. Beide enden damit, dass etwas im Repository steht, das dort nicht
stehen soll.
