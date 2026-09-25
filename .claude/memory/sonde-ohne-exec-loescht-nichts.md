---
name: sonde-ohne-exec-loescht-nichts
description: "Eine Fenstersonde, die nur processEvents pumpt, stellt DeferredDelete nie zu — deleteLater räumt dort nichts, je Klick sammelten sich 30 Widgets an und die Messung wurde langsamer; im Warteschritt sendPostedEvents(None, DeferredDelete)"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 726f8b37-9708-4940-a4ba-a97ab4a2dcda
  modified: 2026-09-25T15:59:50.874Z
---

`slot_probe.py` treibt das echte Fenster ohne `exec()` und pumpt nur
`QApplication.processEvents()`. Qt stellt `DeferredDelete` dort nicht zu:
Was die Anwendung mit `deleteLater` wegräumt, blieb in der Sonde stehen. Am
25.09.2026 wuchs so die Zahl der nativen Widgets je Bohrungsklick um 30
(106 → 291 nach sechs Klicks, „weg 0"), und die Klickzeit der Sonde stieg mit
— eine Last, die es im Programm nicht gibt.

**Why:** Die Sonde misst sonst einen Zustand, den kein Kunde hat, und ein
Befund wie „es entsteht ein Leck" wäre falsch gewesen.

**How to apply:** Jede Sonde, die ohne Ereignisschleife pumpt, ruft im
Warteschritt `QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)`
(steht seitdem in `idle()` von `slot_probe.py`). Wer ein Leck vermutet,
prüft zuerst, ob gelöscht würde, wenn die Schleife liefe.
Zusammenhang: [[native-flaeche-steckt-geschwister-an]], [[sondenbau]].
