---
name: ungenutzter-import-reisst-den-prozess
description: "Zwei deterministische Risse (0xc0000374 im gc.collect nach dem Fensterabbau, test_filament_picker.py) bisektierten auf je einen Qt-Import — QMouseEvent am 14.09., QSpinBox am 15.09.2026. Die Ursache war keiner der Namen, sondern PySides verzögerte Typinitialisierung (6.11.2); PYSIDE6_OPTION_LAZY=0 macht beide Stände grün. Bei einem Heap-Riss nach einem Commit erst die Importe verdächtigen — und dann die Einstellung, die entscheidet, wann ein Import etwas tut."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 1ca7314c-d749-4b85-aac6-9da0d8f5da54
  modified: 2026-09-15T15:40:00.000Z
---

Am 14.09.2026 riss `tests/test_filament_picker.py` deterministisch mit
`0xc0000374` (Heap) im `gc.collect` des Teardowns. Bisektiert in einem
Scratch-Worktree — Commit, Datei, Gruppe, Zeile — bis auf
`from PySide6.QtGui import QMouseEvent` in `app/ui/labels.py`, ungenutzt.
Der Import fiel, ein Wächter hielt den Namen fern, und die Lehre hieß: Der
Riss liegt in der Typregistrierung von PySide.

Am 15.09.2026 riss dieselbe Datei wieder, dieselbe Stelle, deterministisch
lokal wie im Windows-CI des Tags `v0.4.2`. Bisektiert über 76 Commits (der
Zwischenstand war nur durch einen geänderten Assert-Text rot, deshalb zählte
im zweiten Durchgang nur Exit 127 als schlecht) auf `98bf029e`, darin auf
`panels.py`, darin auf `QSpinBox` im `from PySide6.QtWidgets import (...)`.
Drei Varianten am HEAD: Import ohne Nutzung **rot**, Nutzung über
`QtWidgets.QSpinBox` ohne Import **grün**, keines von beiden grün. Also
nicht der Name — sondern **wann** er aufgelöst wird. PySide 6.11.2 legt Typen
erst beim ersten Zugriff an (`len(vars(PySide6.QtWidgets))` ist 15 nach dem
Import, 206 mit `PYSIDE6_OPTION_LAZY=0`). Mit dieser Variable lief der HEAD
durch — **und der Stand vom 14.09. mit dem `QMouseEvent`-Import ebenfalls.**
Preis: 60 ms beim PySide-Import, 6 MB.

**Why:** Die erste Bisektion war richtig und ihre Lehre falsch. Sie fand die
Zeile, die den Riss *auslöste*, und schloss auf das Symbol; die Ursache war
die Einstellung, die entscheidet, was ein Import überhaupt tut. Ein Wächter
gegen den Namen hielt am 15.09. nichts — der nächste Import eines anderen
Typs in einer anderen Datei traf dieselbe Mine
([[bekannte-familie-erklaert-nicht-den-ausloeser]],
[[waechter-sieht-nur-das-getane]]). Der Stapel zeigte `gc.collect`, die
nächste Allokation ([[absturz-frame-ist-die-naechste-allokation]]).

**How to apply:** `app/ui/__init__.py` setzt `PYSIDE6_OPTION_LAZY=0` beim
Betreten des Pakets; `app.py` lädt das Paket als ersten Import (Skriptweg
des gebauten Pakets), `tests/conftest.py` vor jeder Testdatei.
`test_the_interface_loads_qt_types_before_the_first_window` hält es. Bei
einem Riss dieser Gestalt: die Importe als Kandidaten fahren, **und** die
Variable als Gegenprobe — ist sie versehentlich weg oder kommt PySide vor
`app.ui` in den Prozess, ist das die Frage, nicht der Name. Ob mit der
Vorgabe auch die wandernden Risse der Fensterdateien aus dem August fallen,
sagt erst das Tor über Wochen. Worktree-Weg: [[zweite-sitzung-im-selben-baum]].
