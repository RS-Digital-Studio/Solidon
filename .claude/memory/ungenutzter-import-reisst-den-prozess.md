---
name: ungenutzter-import-reisst-den-prozess
description: "`from PySide6.QtGui import QMouseEvent` in app/ui/labels.py — ungenutzt — riss test_filament_picker.py deterministisch mit 0xc0000374 im gc.collect; bisektiert am 14.09.2026 bis auf diese eine Zeile. Bei einem Heap-Riss nach einem Commit erst die Importe verdächtigen, dann den Code."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 1ca7314c-d749-4b85-aac6-9da0d8f5da54
  modified: 2026-09-14T09:03:38.344Z
---

Am 14.09.2026 meldete die Nachbarsitzung einen Riss (`0xc0000374`,
Heap-Korruption) in `tests/test_filament_picker.py`, bisektiert über Commits
auf `b13100ff` — meinen Vorschau/Checkbox-Commit. Verdacht: `RowCheckBox`
und der Ereignisfilter an der Beschriftung, „ein Kind, das Qt und Python
beide freigeben". Plausibel, und falsch.

Was wirklich half: ein Scratch-Worktree (`git worktree add --detach`) bei
`b13100ff`, darin alle sieben geänderten Dateien auf den grünen Stand
`99b51979` zurück, dann **gruppenweise** wieder vor (Viewport grün,
Session+Fenster grün, labels-Gruppe rot), dann innerhalb von `labels.py`
**Zeile für Zeile**: ohne die Klassen rot, ohne den Filter rot — nur die
drei Importzeilen unterschieden sich noch. Pur grün, plus `QCheckBox` grün,
plus `QEvent` grün, plus `from PySide6.QtGui import QMouseEvent` **rot**.
Der Name wurde in dieser Fassung nirgends benutzt.

**Why:** Der Riss lag in der Typregistrierung von PySide, nicht in unserem
Code — und die Bisektion über *Verhalten* (Filter weg, Überschreibungen weg)
fand nichts, weil jede Fassung den Import behielt. Der Stapel zeigte
`gc.collect` im Teardown, also die nächste Allokation
([[absturz-frame-ist-die-naechste-allokation]]), und der Verdacht aus der
Bauart des Codes war eine Zuordnung nach Familie
([[bekannte-familie-erklaert-nicht-den-ausloeser]]).

**How to apply:** Bei einem nativen Riss nach einem Commit den Worktree
gegen den letzten grünen Stand bisektieren — Datei, Gruppe, Zeile —, und die
**Importzeilen als eigene Kandidaten** fahren, nicht nur den Code darunter.
`QMouseEvent` in `app/ui/labels.py` ist tabu; der Wächter
`test_labels_do_not_name_the_mouse_event_type` in
`tests/test_language_rules.py` hält es über den Syntaxbaum fest, in jeder
Schreibweise. Ein Filter fragt `event.type()` und liest `button()` über
`getattr`. **Die Reichweite ist der Prozess, nicht das Symbol:**
`app/ui/viewport.py` importiert und benutzt `QMouseEvent` und reißt nicht —
die Bisektion gilt für diese Datei in dieser Modulmenge, nicht für den Namen
an sich. Siehe
[[zweite-sitzung-im-selben-baum]] für den Worktree-Weg und
[[waechter-lesen-kommentare-mit]] dafür, warum der Wächter den Baum liest.
