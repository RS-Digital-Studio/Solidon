---
name: deutsches-schlusszeichen-beendet-den-string
description: "In `f\"… „{wert}\"…\"` ist das Schlusszeichen ein ASCII-Quote und beendet den String — dreimal an einem Tag ein Syntaxfehler."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 60dfe3ed-7cce-4c68-a256-9db7aac288cb
  modified: 2026-08-30T18:56:01.979Z
---

Deutsche Anführungszeichen sind **zwei verschiedene Zeichen**: `„` (U+201E)
öffnet, `“` (U+201C) schließt. Wer das schließende als `"` tippt, beendet
damit den Python-String.

```python
f"{name}: „{knopf.text()}" trägt den Akzent"   # Syntaxfehler
f"{name}: „{knopf.text()}“ trägt den Akzent"   # richtig
```

Am 30.08.2026 dreimal zugeschnappt, in drei verschiedenen Dateien
(`tests/test_style.py`, `tests/test_recipe_dialog.py`, ein Prüfskript). Der
Fehler ist beim Schreiben unsichtbar, weil das öffnende `„` korrekt dasteht
und das Auge das Paar als vollständig liest.

**Why:** Die Sprachregel dieses Projekts verlangt echte Typografie, und
zugleich sieht ein ASCII-`"` in einer Editoranzeige fast aus wie `“`. Das
Muster tritt genau dort auf, wo beides zusammenkommt: in einer deutschen
Assert-Meldung innerhalb eines f-Strings.

**How to apply:** Zwei Auswege, und der zweite ist der bessere:

* Beim Schreiben auf das **schließende** Zeichen achten — es ist das, das man
  falsch macht, nie das öffnende.
* **In Assert-Meldungen `!r` statt Anführungszeichen nehmen.** `f"{schluessel!r}
  fiele auf {ziel!r}"` liest sich in der Fehlerausgabe genauso gut, kann nicht
  brechen und zeigt zusätzlich unsichtbare Zeichen. Nach dem dritten Mal habe
  ich genau darauf umgestellt.

Nicht zu verwechseln mit [[heredoc-verschluckt-backslash-n]] — dort frisst die
Shell ein Escape, hier ist das Zeichen selbst das falsche.
