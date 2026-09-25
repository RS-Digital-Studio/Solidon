---
name: heredoc-frisst-den-backslash
description: "Ein \\n in einem Shell-Heredoc wird zum echten Zeilenumbruch und zerreißt die Datei, die es schreiben soll."
metadata:
  node_type: memory
  type: feedback
  originSessionId: eda33e4f-279c-48e3-bf58-acf625bcf116
  modified: 2026-09-25T11:21:55.546Z
---

Am 10.09.2026 zweimal hintereinander dieselbe Sache: Ein Python-Schnipsel als
`python - <<'PYEOF'` geschrieben, darin ein `"\n"` im Ersatztext — und die
Shell machte daraus einen echten Zeilenumbruch. Beide Male stand danach eine
syntaktisch kaputte Datei im Baum (`tools/memory_index.py`,
`tests/test_memory_index.py`), beide Male kostete das Heilen mehr Zeit als das
Schreiben.

**Warum es zweimal passieren konnte:** Beim ersten Mal sah es aus wie ein
Tippfehler, nicht wie ein Muster. Das Quoting `<<'PYEOF'` schützt `$` und
Backticks — aber der Text geht trotzdem durch die Shell, und `\n` in einem
doppelt gequoteten Python-String ist danach ein Zeilenumbruch.

**Wie es geht:** Das Skript mit dem Write-Werkzeug in den Scratchpad legen und
mit `python <datei>` fahren. Dann sieht Python genau die Bytes, die gemeint
waren. Für eine einzelne Ersetzung ohne Escapes reicht das Edit-Werkzeug.

**Woran man es merkt, bevor es weh tut:** Enthält der Ersatztext einen
Backslash — `\n`, `\r`, `\t`, eine Regex —, gehört er nicht in ein Heredoc.
Das ist dieselbe Grenze wie in
[[deutscher-text-geht-nicht-durch-die-shell]], nur eine Zeichenklasse weiter.

**Die stille Gestalt davon, und sie überlebt jeden Lauf** (25.09.2026): Ein
Pfad wie ``F:\3D Dateien`` in einem gewöhnlichen Docstring ist für Python ein
Oktal-Escape — die Datei kompiliert, kein Test wird rot, und im Docstring
steht das Steuerzeichen 0x03. Sechs Docstrings in `tests/` trugen es, einer
davon roh als Byte. Seither meldet `tests/test_source_escapes.py`
jedes Oktal-Escape außer `\0` und jedes rohe Steuerzeichen; geschrieben wird
``F:\\3D`` oder ein roher String.

**Und ein Nachbar davon:** Wer den Umlaut umgeht, um das Escaping zu
vermeiden, tauscht einen Fehler gegen einen anderen — „zerreisst" statt
„zerreißt" verstößt gegen die Sprachregelung. Beides zusammen ging heute
zweimal daneben; der Ausweg ist derselbe: die Datei schreiben, nicht die
Shell füttern.
