---
name: schranke-statt-antwort-je-punkt
description: "Wer nur das Maximum braucht, misst exakt nur die Punkte, deren Schranke es heben kann — an Nadeldreiecken zehnmal schneller als die volle Antwort je Punkt; und die Kugel um den Schwerpunkt ist an Nadeln die falsche Hülle"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: ebc8112f-3e6f-44e4-b117-6d2044e135a9
  modified: 2026-09-22T08:16:03.843Z
---

`on_surface` beantwortet je Punkt Ort, Abstand und Dreieck; `deviation` wollte
davon eine Zahl, das Maximum. An CAD-Exporten mit Nadeldreiecken (Besenhalter,
97 Prozent Nadeln; Zylinder aus 2 048 Sektionen) kostete die volle Antwort
2,9 s, weil die Kugel um den Schwerpunkt eines langen Dreiecks Hunderte
Bewerber je Punkt einschließt — und weder eine engere Schranke noch ein
Hüllkörperbaum noch ein Raster machten das grundsätzlich billiger (alles
gemessen am 22.09.2026: BVH 3–5× an Nadeln, 2× langsamer an Kugeln; Raster
ohne Budget 1,3 Milliarden Registrierungen).

**Why:** Die Frage entscheidet die Rechnung. Das Maximum braucht je Punkt nur
eine obere Schranke; sobald ein gemessener Abstand über der Schranke eines
Punkts liegt, ist der Punkt erledigt. Mit der Schranke aus dem nächsten
Schwerpunkt, nach dem ersten Maß enger aus acht Schwerpunkten und den
Dreiecken an den nächsten Ecken, blieben am Besenhalter 22 Prozent der Punkte
für die exakte Rechnung: 2,9 → 0,25 s, gleiche Zahl bis 1e-12.

**How to apply:** Vor einer Beschleunigung fragen, welche Frage der Aufrufer
stellt — je Punkt oder in Summe. Bei einer Summe (Maximum, Anzahl über einer
Schwelle) Schranken zuerst, exakt nur für die Kandidaten, in wachsenden
Portionen, mit Rundungsboden statt `> 0`. Und an Nadeln die Zahl der
*Paare* messen, nicht nur die Zeit: Sie sagt, ob die Hülle das Problem ist.
Verwandt: [[lineares-sieb-vor-der-verfeinerung-ist-unsicher]] (eine Schranke
ist exakt, ein Sieb nicht).
