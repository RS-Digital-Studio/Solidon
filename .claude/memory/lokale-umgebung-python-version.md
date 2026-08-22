---
name: lokale-umgebung-python-version
description: "Die .venv muss auf Python 3.13 laufen — ruff merkt es nicht, wenn sie es nicht tut."
metadata: 
  node_type: memory
  type: project
  originSessionId: 51fc77ef-9303-4ab8-8343-709c36dc0ed3
  modified: 2026-08-06T15:47:02.003Z
---

Am 06.08.2026 lief `F:\3D Druck\.venv` auf **Python 3.11.9**, während
`pyproject.toml` `>=3.13` verlangt und die CI 3.13 fährt. Seit den ersten
PEP-695-Typparametern (087e321) brach damit der Import der Anwendung: pytest,
mypy, CLI und Fenster waren tot, die CI blieb grün.

**Behoben:** Python 3.13.14 per winget installiert (`--scope user`, liegt unter
`%LOCALAPPDATA%\Programs\Python\Python313`), `.venv` neu angelegt und gegen
`constraints.txt` bestückt. `tests/test_toolchain.py` hält den Fall jetzt fest —
Interpreter gegen `requires-python`, Zielversionen von mypy und ruff gegen
dieselbe Angabe.

**Why:** Ein grüner `ruff`-Lauf beweist hier nichts. Ruff bringt einen eigenen
Parser mit `target-version = py313` mit und sieht den Interpreter nie an; mypy
meldet bei einem Abbruch „1 error … errors prevented further checking" und hat
dabei **null** Dateien geprüft. Dieselbe Mechanik hat das Tor schon beim
numpy-2.5-Vorfall zwei Tage zuvor blind gemacht.

**How to apply:** Beim Neuaufbau einer Umgebung `py -0` prüfen — 3.11 und 3.9
liegen auch auf der Maschine, und `python -m venv` nimmt sonst die falsche.
Meldet mypy „errors prevented further checking", ist die Zahl der geprüften
Dateien die interessante Angabe, nicht die Zahl der Fehler. Siehe
[[parallele-sitzungen-formwerk]] — der venv-Neubau trifft parallele Sitzungen
mit, sie bauen sie unter Umständen gleichzeitig neu.
