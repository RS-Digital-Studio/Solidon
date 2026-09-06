---
name: lokale-umgebung-python-version
description: "Die .venv des Hauptbaums läuft seit dem 06.09.2026 auf Python 3.14.7 (Entscheidung Robert); die alte 3.13-Umgebung liegt als .venv-313-alt daneben — ruff merkt es nicht, wenn eine venv die falsche Version hat."
metadata:
  type: project
  originSessionId: f07e3f31-b0f2-4cae-b55c-218ecd11e007
  modified: 2026-09-06T13:21:58.228Z
---

**Stand seit dem 06.09.2026:** `requires-python >= 3.14`, ruff- und
mypy-Ziel `py314`, die CI auf CPython 3.14.7. Entscheidung Robert an diesem
Tag („3.14 ist dann auch im Hauptbaum, CI und alles daran anpassen"), nachdem
die Gesamtdurchsicht 01a07020 an 97 Stellen die ungeklammerte Ausnahmegruppe
(`except A, B:`) aus 3.14 geschrieben hatte — der Code lief auf 3.13 nicht
mehr, bevor die Grenze irgendwo erklärt war. `F:\3D Druck\.venv` ist seitdem
eine 3.14.7-Umgebung (gebaut aus `constraints.txt` mit VTK 9.7.0, PySide6
6.11.2, pygfx 0.17.0); die alte 3.13-Umgebung (1,6 GB, VTK 9.6.2) ist am
selben Tag auf Roberts Wunsch gelöscht worden.

**Die Vorgeschichte, die den Test erklärt:** Am 06.08.2026 lief die `.venv`
auf 3.11.9, während `pyproject.toml` `>=3.13` verlangte. Seit den ersten
PEP-695-Typparametern brach damit der Import der Anwendung: pytest, mypy, CLI
und Fenster waren tot, die CI blieb grün. `tests/test_toolchain.py` hält den
Fall seitdem fest — Interpreter gegen `requires-python`, Zielversionen von
mypy und ruff gegen dieselbe Angabe.

**Why:** Ein grüner `ruff`-Lauf beweist hier nichts. Ruff bringt einen eigenen
Parser mit `target-version` mit und sieht den Interpreter nie an; mypy meldet
bei einem Abbruch „1 error … errors prevented further checking" und hat dabei
**null** Dateien geprüft.

**How to apply:** Beim Neuaufbau einer Umgebung `py -0` prüfen — 3.14, 3.13,
3.11 und 3.9 liegen alle auf der Maschine, und `python -m venv` nimmt sonst
die falsche. Ein Worktree mit alter `.venv` (3.13) macht den
pre-commit-Hook nutzlos und langsam: Die Sprachprüfung parst den 3.14-Code
nicht und winkt nach vier Minuten als „fremde Arbeit" durch — siehe
[[worktree-venv-verstellt-den-hook]]. Meldet mypy „errors prevented further
checking", ist die Zahl der geprüften Dateien die Auskunft, nicht der
Exit-Code.
