---
name: rendercanvas-takt-bremst-nicht
description: "rendercanvas nimmt max_fps=30 und liest sich, als warte jede Bestellung 33 ms — gemessen wartet sie am Qt-Bildschirmweg 2,5 ms im Median, und Kameragesten zeichnen mit 30 wie mit 144 gleich oft; ein Takt nach dem Bildschirm war gebaut und ist wieder draußen"
metadata:
  node_type: memory
  type: project
  originSessionId: 726f8b37-9708-4940-a4ba-a97ab4a2dcda
  modified: 2026-09-25T15:59:56.762Z
---

Am 25.09.2026 (RM-232) sah die Zeitleiste eines Bohrungsklicks so aus, als
warte jedes Bild auf den 33-ms-Takt von rendercanvas (`QRenderWidget` ohne
`max_fps`, Scheduler in `rendercanvas/core/scheduler.py`). Gebaut war
schnell ein Takt nach der Bildwiederholrate des Bildschirms (144 und 120 Hz
an dieser Maschine). Die direkte Messung widersprach: Eine Bestellung
`render()` wartet im Median 2,5 ms bis zum Zeichnen, höchstens 7,4; eine
Kamerageste zeichnet mit 30 wie mit Bildschirmtakt 41 bis 48 Bilder je
Sekunde bei gleicher Hauptfadenlast.

**Why:** Den Quelltext eines Schedulers zu lesen ist keine Messung seiner
Wirkung — hier läuft der Weg über `_rc_request_draw` → `_time_to_draw` und
Qts Malrunde, nicht über den Takt.

**How to apply:** Vor einer Änderung am Bildtakt `scenario_bestellung.py`
und `scenario_zug.py` fahren (`.claude/.state/rm-232-erster-klick-2026-09-25/`,
Schalter `PROBE_FPS`); steht auch in `app/ui/render/CLAUDE.md` unter „Was
gemessen ist". Zusammenhang: [[viewport-zwei-renderer-messen]].
