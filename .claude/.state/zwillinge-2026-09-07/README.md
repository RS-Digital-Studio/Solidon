# Zwillingsmessung vom 07.09.2026

Rohfunde und Messskript zur Durchsicht „Doppelte Stellen und Zwillinge"
(ROADMAP-Abschnitt gleichen Datums; Konzept `konzepte/konzept-zwillinge-2026-09.md`).
Gemessen gegen `d9999d1b`.

| Datei | Was |
|---|---|
| `twin_scan.py` | sieben Fragen über einen Baum, nur `ast`, kein `eval` |
| `twin_diff.py` | zwei Funktionen nebeneinander: Körper ohne Docstring, Ähnlichkeit, Diff |
| `scan_app.txt` | Lauf über `app/` — 260 Dateien, 190 223 Zeilen, 5 956 Funktionen |
| `scan_tools.txt` | Lauf über `tools/` |
| `scan_tests.txt` | Lauf über `tests/` |

Aufruf, aus dem Projektstamm:

```
.venv\Scripts\python.exe .claude\.state\zwillinge-2026-09-07\twin_scan.py app > ausgabe.txt
.venv\Scripts\python.exe .claude\.state\zwillinge-2026-09-07\twin_diff.py app/x.py:12 app/y.py:34
```

Zwei Fallen, beide am 07.09. zugeschnappt:

* **Windows-Pfad, kein Git-Bash-Pfad.** `/c/Users/…` findet unter Windows
  nichts, und das Skript meldet dann null Zwillinge über null Dateien. Die
  Kopfzeile „Funktionen/Methoden: 5956" ist die Mindestzählung — fehlt sie oder
  ist sie klein, ist der Lauf ungültig.
* **Abschnitte 2 und 3 zählen Zeilen samt Docstring.** Ein Einzeiler unter
  zehn Zeilen Erklärung gilt als „acht Zeilen". Die Zahl „ab vier
  Anweisungen des Körpers: 0 Gruppen" steht im Konzept §0.3 und kam aus einem
  Nachlauf über `functions()` mit dem Feld `stmts`.

Wie die anderen Messskripte hier: Wegwerfwerkzeug, von ruff und mypy
ausgenommen (`pyproject.toml`), belegt seine Zahl nur unverändert.
