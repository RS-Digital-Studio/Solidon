---
name: mittel-ueber-symmetrisches-entscheidet-nach-rauschen
description: "Ob eine Zelle vertieft oder erhaben ist, aus dem Mittel ihrer Dreiecksmitten gegen die Mittelebene zu lesen, entscheidet an einer durchgehenden Zelle nach Rundungsrauschen — die Wände liegen symmetrisch; was symmetrisch ist, hat kein Vorzeichen, und die Frage braucht einen anderen Zeugen"
metadata:
  node_type: memory
  type: feedback
  originSessionId: f56e0441-974f-4150-ac77-8e36658dc05b
  modified: 2026-09-22T09:45:00.000Z
---

Gemessen am 22.09.2026 an `perceive/patterns.py`: Die Seite einer Zelle —
vertieft oder erhaben — kam aus dem Mittel der Dreiecksmitten entlang der
Trägernormalen gegen die Mitte zwischen höchstem und tiefstem Punkt. Am
Halter (echte STL) sagte das „vertieft", an der synthetischen Wabenplatte
des Tests „erhaben" — dieselbe Geometrie, sechs Wände zwischen zwei Trägern,
symmetrisch um die Mittelebene. Das Mittel lag bei 10⁻¹⁵ auf der einen oder
der anderen Seite, und daran hingen Stopfenrichtung, Ebene der Mündung und
das Volumen nach dem Entfernen (92 177 statt 125 848 mm³).

**Why:** Eine durchgehende Zelle hat keine Seite; sie ist ein Loch. Ein
Zeuge, der an einer symmetrischen Menge ein Vorzeichen liest, liest
Rauschen — und Rauschen ist an jeder Datei anders, also fällt es an der
einen auf und an der anderen nicht.

**How to apply:** Erst die Frage prüfen, ob sie an dieser Menge überhaupt
eine Antwort hat: Zwei Träger → durchgehend → vertieft, ohne Mittel. Wo ein
Mittel über etwas Symmetrisches entscheidet, sucht man den Fall, in dem es
exakt null ist, und baut ihn als Test (`honeycomb_plate` in
`tests/test_pattern_features.py`). Siehe [[gegenprobe-bei-geaenderter-bauart]].
