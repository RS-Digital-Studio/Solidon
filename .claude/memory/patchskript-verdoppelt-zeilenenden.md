---
name: patchskript-verdoppelt-zeilenenden
description: "read_text(newline=\"\") plus write_text() ohne newline macht aus jedem \\r\\n ein \\r\\r\\n — ruff format zerlegt die Datei danach in doppelt so viele halbe Zeilen."
metadata:
  node_type: memory
  type: feedback
---

Am 31.08.2026 habe ich `tests/test_analysis_ui.py` mit einem Python-Skript
gepatcht und dabei zerstört. Das Muster:

```
t = D.read_text(encoding="utf-8", newline="")   # \r\n bleibt erhalten
zeilen = t.split("\n")                           # jede Zeile endet auf \r
...
D.write_text("\n".join(zeilen), encoding="utf-8")   # <- hier
```

`write_text` ohne `newline=""` fährt den Text-Modus, und der übersetzt auf
Windows jedes `\n` nach `\r\n`. Aus `Zeile\r` + `\n` wird `Zeile\r\r\n`.

Das allein wäre reparabel. Der Schaden kam vom nächsten Befehl in derselben
Kette: `ruff format` liest `\r` als Zeilenende alter Machart, sieht also
zwischen jeder echten Zeile eine leere, normalisiert alles auf `\r` — und
reduziert dabei Leerzeilen nach PEP-8. Danach hatte die Datei 2863 Stücke,
kein einziges `\n`, und die ursprüngliche Aufteilung war nicht mehr
zurückrechenbar. `ruff check` meldete 22 Importblöcke als unsortiert, was wie
ein Formatierungsproblem aussieht und keines war.

**Why:** Der Fehler ist unsichtbar, weil beide Aufrufe für sich richtig
aussehen. `newline=""` beim Lesen ist sogar die vorsichtige Wahl — sie
verhindert, dass Python die Zeilenenden still vereinheitlicht. Genau deshalb
muss sie beim Schreiben wiederholt werden, und das vergisst man, weil dort
nichts danach aussieht, als würde es etwas verändern.

**How to apply:**

* **`newline=""` gehört an beide Enden** oder an keines. Wer beim Lesen
  vorsichtig ist, muss es beim Schreiben auch sein.
* Sicherer ist, die Zeilenenden gar nicht durch das Skript zu tragen: beim
  Lesen `.replace("\r\n", "\n")`, am Ende einmal zurück. Dann arbeiten alle
  Suchmuster mit `\n`, und die Datei bekommt genau ein Zeilenende zurück.
  Nebeneffekt: Suchstrings mit LF treffen auch in einer CRLF-Datei — sonst
  scheitert jedes `assert t.count(ALT) == 1` ohne erkennbaren Grund.
* **Vor dem Formatierer prüfen, nicht danach.** `ruff format` in derselben
  Kette hat den reparablen Schaden in einen unreparablen verwandelt. Ein
  `python -c "print(Path(...).read_bytes().count(b'\r\r'))"` zwischen Patch
  und Formatierer kostet nichts.
* **Repariert wird vorwärts, und der Weg dahin ist ein Vergleich.** Ich habe
  den HEAD-Blob geholt, beide Stände auf Inhaltszeilen reduziert (leere weg)
  und gediffed. 48 Diffzeilen, alle meine — damit stand fest, dass ein Neubau
  aus HEAD plus meinem Block nichts fremdes verliert. Ohne diesen Vergleich
  wäre der Neubau ein Revert auf Verdacht gewesen.

Verwandt: [[heredoc-verschluckt-backslash-n]] (dieselbe Familie: Ebenen, die
Escape-Folgen umschreiben), [[patchskript-schneidet-fremdes-weg]] (dort
löscht das Skript fremde Arbeit, hier die eigene Struktur).
