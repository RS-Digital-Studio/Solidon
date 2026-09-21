---
name: zeitgeber-startet-arbeiter-nach-dem-warten
description: "Exit 127 nach „60 passed" mit „QThread: Destroyed while thread is still running" — ein singleShot(0) aus dem Test startete den Vorschauzeichner erst im Teardown, nach allen Wartezeiten; bei gc.get_objects() nach laufenden QThreads am Sitzungsende suchen, dann fragen, wer sie NACH dem Warten gestartet hat"
metadata:
  node_type: memory
  type: feedback
  originSessionId: f56e0441-974f-4150-ac77-8e36658dc05b
  modified: 2026-09-21T16:45:00.000Z
---

Gemessen am 21.09.2026: Fünf Tests in `test_operation_ui.py` bestanden
einzeln und beendeten den Prozess trotzdem mit Exit 127 und dem Satz
`QThread: Destroyed while thread '' is still running` — auch am Stand der
0.4.4. Eine Sonde mit `pytest_sessionfinish`, die `gc.get_objects()` nach
laufenden `QThread` durchsucht, nannte den `_ThumbnailWorker` des Objektbaums:
ein Auftrag, nicht abgebrochen, in 0,02 s fertig, sobald jemand wartete.
Niemand wartete, weil er erst **nach** dem Warten gestartet worden war: Der
Test lief ohne Ereignisrunde durch, der `singleShot(0)` aus `show_scene`
feuerte erst bei den `processEvents()` der Aufräum-Fixture — hinter
`release()` und `wait_for_all()`.

**Why:** Ein Warten schützt nur vor dem, was schon läuft. Was ein Zeitgeber
danach anstößt, überlebt jedes Warten davor; und das Fenster wird im Test nie
zerstört, also feuert der Zeitgeber, anders als in der laufenden Anwendung.

**How to apply:** Bei „Destroyed while thread is still running" zuerst
den Thread benennen (Sonde am Sitzungsende) und dann fragen, **wann** er
gestartet wurde — nicht nur, ob jemand auf ihn wartet. Die Abhilfe gehört
zur Freigabe: `ObjectTree.release` leert den Vorrat, bevor es wartet, und
`MainWindow.release` ruft es; ein freigegebenes Widget fängt nichts mehr an.
Siehe [[hintergrundlauf-meldet-seinen-wrapper]] und
[[verwaiste-widgets-sterben-im-falschen-moment]].
