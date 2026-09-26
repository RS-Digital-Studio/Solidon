---
name: shapely-buffer-methode-16-funktion-8-segmente
description: geometry.buffer(r) nimmt 16 Segmente je Viertelkreis, shapely.buffer(arr, r) nur 8 — derselbe Umkreis kam um 6 mm² anders heraus.
metadata:
  type: reference
---

In Shapely 2.1 hat die Methode `BaseGeometry.buffer(distance, quad_segs=16)` eine
andere Vorgabe als die vektorisierte Funktion `shapely.buffer(geometry, distance,
quad_segs=8)`. Beim Umbau von `analysis.channel_space` auf vektorisierte Puffer
(26.09.2026) wichen die Kanalumkreise an der Waschschüssel um bis zu 3,8 mm² je
Scheibe ab, die Vereinigung um 6 mm² — ohne dass sich an der Rechnung etwas
geändert hatte.

**How to apply:** Wer einen `.buffer(...)`-Aufruf in `shapely.buffer(array, ...)`
umschreibt (oder umgekehrt), gibt `quad_segs` ausdrücklich an und vergleicht
gegen die alte Fassung Fläche für Fläche. In `analysis.py` steht die Zahl als
`CHANNEL_QUAD_SEGMENTS = 16`. Siehe [[neue-analyse-je-stueck-am-gitterwerk-messen]].
