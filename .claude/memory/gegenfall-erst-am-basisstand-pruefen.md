---
name: gegenfall-erst-am-basisstand-pruefen
description: Ein konstruierter Gegenfall taugt erst, wenn der Basisstand ihn richtig erkennt — sonst misst der Test, dass die neue Regel falschen Müll anders wegräumt
metadata:
  type: feedback
---

Für RM-243 (26.09.2026) sollte ein verrauschter Korbbogen R 10 · R 16 · R 10
belegen, dass echte Bögen bleiben. Der erste Aufbau (Bogen direkt auf der
Grundlinie, ±0,6 µm) lieferte schon **im Basisstand** R 8,68 · 9,997 · 10,004
und kein R 16 — ein Rauschstück, und der mittlere Bogen fehlte. Der Test
schlug mit der neuen Regel fehl, sagte darüber aber nichts: Verglichen wurden
zwei falsche Antworten. Erst eine Suche über Saat, Rauschen und Aufbau am
Basisstand fand Fälle, in denen er genau R 10 · R 10 · R 16 erkennt (5 mm
Flanken unter dem Bogen, Saat 4) — und daran misst der Test jetzt.

Ebenso radiales Rauschen gegen die Float32-Rundung: Bei gleichem Betrag
zerfiel die künstlich verrauschte Ellipse in Kreisstücke, die float32-gerundete
nicht; welche Art Rauschen die echte Datei trägt, gehört vorher gemessen.

**Why:** Ein Gegenfall prüft, dass die neue Regel nichts Richtiges wegnimmt.
Ist das Richtige im Basisstand gar nicht da, prüft er nichts.

**How to apply:** Vor jedem konstruierten Test erst den Basisstand darauf
fahren und das Sollbild dort bestätigen; bei verrauschten Aufbauten über
mehrere Saaten und Stärken suchen und den Test auf einen Fall setzen, den der
Basisstand richtig macht. Verwandt: [[zwischenkreis-an-der-naht-zweier-boegen]],
[[testprojekt-trifft-den-fall-nicht]], [[index-messen-und-pruefen]].
