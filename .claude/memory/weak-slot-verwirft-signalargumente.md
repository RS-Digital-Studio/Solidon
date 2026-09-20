---
name: weak-slot-verwirft-signalargumente
description: ui/leash.weak_slot reicht Signalargumente nur mit forward=True weiter; ein Slot mit Parametern bekommt sonst keine und schweigt — die Kandidatenbetonung im Fragedialog kam so nie an
metadata: 
  node_type: memory
  type: project
  originSessionId: f56e0441-974f-4150-ac77-8e36658dc05b
  modified: 2026-09-20T15:11:38.963Z
---

`app/ui/leash.py::weak_slot(owner, call, *bound, forward=False)` **verwirft,
was das Signal schickt**, solange `forward=True` fehlt. Ein Empfänger mit
Parametern (`_emphasise_candidate(self, current, _previous)`) bekommt dann
nur den Besitzer, wirft einen `TypeError` im Slot — und Qt schluckt ihn:
kein roter Test, kein Fenster, nichts. Gefunden am 20.09.2026 durch den
ersten Fenstertest, der die Betonung über eine **Zeilenänderung** prüfte
statt über den direkten Aufruf beim Szenenaufbau (`scene_ready` rief die
Methode selbst und sah deshalb richtig aus).

**Why:** Die Falle steht im Docstring von `weak_slot` („Was das Signal
schickt, wird verworfen"), und genau deshalb prüft sie niemand ein zweites
Mal ([[benannte-falle-schuetzt-nicht]]). Ein direkt aufgerufener Slot deckt
den Signalweg nicht ([[signal-passt-an-den-falschen-slot]]).

**How to apply:** Bei jedem `weak_slot(...)` an ein Signal mit Argumenten,
die der Empfänger braucht, `forward=True` setzen — und im Test das Signal
auslösen (`setCurrentRow`, Klick), nicht die Methode rufen. Ein Slot, der
nie ankommt, ist im Bild nur daran zu sehen, dass sich nichts ändert.
