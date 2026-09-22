---
name: skript-im-worktree-laedt-app-aus-dem-hauptbaum
description: "Ein Hilfsskript, das in einem Worktree läuft und `import app` schreibt, lädt die editierbar installierte `app` aus F:\\3D Druck — sys.path[0] ist der Skriptordner, nicht das Arbeitsverzeichnis; Sonden und Messwerkzeuge müssen den Baum selbst vorn in den Suchpfad stellen."
metadata: 
  node_type: memory
  type: project
  originSessionId: 49da6b80-5991-4fc3-a51f-b6e09a938d38
  modified: 2026-09-14T16:31:44.408Z
---

Zwei Agenten sind am 14.09.2026 unabhängig hineingelaufen: Die
Vorschau-Sonde (W3) maß eine Stunde lang den Hauptbaum, an dem drei andere
Sitzungen schrieben, obwohl sie „im Worktree" lief — aufgefallen an einem
`AttributeError` auf `_first_chosen`, einen Namen, den es im Worktree nirgends
gab. Ein Werkzeug (W2), das eine geänderte Message-ID suchte, fand die alte
und meldete „die Quelle hat sich nicht geändert".

Der Grund: `app` ist in der `.venv` editierbar installiert und zeigt auf
`F:\3D Druck\app`. Bei `python skript.py` ist `sys.path[0]` das Verzeichnis
des Skripts (im Scratchpad), nicht das Arbeitsverzeichnis — `import app`
trifft also die Installation. `python -m pytest` aus dem Worktree ist nicht
betroffen, dort steht das Arbeitsverzeichnis vorn.

**Why:** Eine Messung, die stillschweigend einen anderen Baum misst, liefert
saubere Zahlen zur falschen Frage — und in einem Baum, den gerade andere
ändern, sogar wechselnde.

**How to apply:** Jede Sonde und jedes Hilfsskript, das außerhalb von pytest
läuft, setzt zuerst `sys.path.insert(0, <baum>)` (oder liest `PROBE_ROOT`)
und prüft einmal `app.__file__`, bevor es misst. Siehe
[[hilfsmodul-verstellt-den-suchpfad]] und [[messung-traegt-nur-am-ort-ihrer-messung]].

**Der Vorsatz allein reicht nicht — das ausgefuehrte Skript setzt den Pfad
selbst.** Am 22.09.2026 stand die Regel hier und war befolgt: Der Aufruf
lautete `python -c "sys.path.insert(0, worktree); exec(open(sonde).read())"`.
Die Sonde brachte ihren eigenen `sys.path.insert(0, r"F:D Druck")` mit, und
der lief **nach** meinem. Gemessen wurde der Hauptbaum. Zwei Minuten lang sah
die Ausgabe plausibel aus; aufgefallen ist es erst an einem Wert, der nicht
zum Stand passte.

**Deshalb: Der Baum ist ein Argument, und die Herkunft wird gedruckt.**

    TREE = sys.argv[1]
    sys.path.insert(0, TREE)
    ...
    where = str(Path(F.__file__).resolve())
    if not where.startswith(str(Path(TREE).resolve())):
        raise SystemExit(f"falscher Baum geladen: {where}")
    print(f"gemessen wird {where}")

Die gedruckte Zeile ist der eigentliche Gewinn, nicht die Prüfung: Sie macht
eine stille Annahme sichtbar, auch wenn sie stimmt — und in der Ausgabedatei
steht sie noch, wenn man die Zahlen eine Stunde später liest.
