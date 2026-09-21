---
name: qmenu-exec-blockiert-offscreen-und-laesst-sich-nicht-patchen
description: "Ein QMenu.exec in einem Bedienweg hält offscreen die Suite an, und monkeypatch.setattr(QMenu, 'exec', …) greift an PySide-Typen nicht — Kontextmenüs über popup + triggered bauen, dann sind sie prüfbar"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 7708995f-8153-4da1-9385-1fa5f014d252
  modified: 2026-09-21T15:11:50.034Z
---

Am 21.09.2026 stand `test_surface_placement_ui.py` zehn Minuten ohne Ausgabe:
`py-spy dump` zeigte `_reference_menu → menu.exec`. Der Test hatte
`monkeypatch.setattr(QMenu, "exec", choose_from)` gesetzt, und das sah nach
einer Attrappe aus — gewirkt hat es nicht: Die Bindung `menu.exec` löst am
Shiboken-Typ weiter auf die native Methode auf, und offscreen wartet die
auf einen Klick, den es nie gibt.

**Why:** Ein `exec` ist eine zweite Ereignisschleife mitten im Fluss. Im
Betrieb hält sie den Aufrufer an (ein `exec` aus einem Arbeiterrückruf ist
schon deshalb falsch); im Test ist sie ein Hänger ohne rotes Wort — dieselbe
Gestalt wie der modale Absturzbericht in
[[absturzbericht-haelt-die-suite-an]].

**How to apply:** Ein Kontextmenü, das ein Bedienweg öffnet, wird über
`menu.popup(pos)` gezeigt, `menu.triggered` trägt die Wahl, `aboutToHide →
deleteLater` räumt es weg; die Methode gibt das Menü zurück. Der Test löst
`customContextMenuRequested.emit(...)` aus, findet das sichtbare Menü über
`findChildren(QMenu)`, liest `actions()` und ruft `action.trigger()`. Was
sich an einem Qt-Typ nicht patchen lässt, wird gar nicht erst gepatcht —
und wer einen Fenstertest über zwei Minuten hängen sieht, liest den Stapel
statt zu warten.
