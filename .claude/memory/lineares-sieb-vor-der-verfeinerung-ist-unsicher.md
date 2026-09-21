---
name: lineares-sieb-vor-der-verfeinerung-ist-unsicher
description: "Ein lineares Vorfit (Normalen und Mitten, wie bis zur 0.4.4) taugt nicht als Sieb vor der Verfeinerung an Stützpunkten — am Korpus liegt er bei angenommenen Kugeln bis zum 10⁹-Fachen neben dem Endmaß; erst messen, welche Spanne ein Sieb lassen müsste, bevor man es baut"
metadata:
  node_type: memory
  type: feedback
  originSessionId: f56e0441-974f-4150-ac77-8e36658dc05b
  modified: 2026-09-21T15:25:48.682Z
---

Gemessen am 21.09.2026 an der Merkmalserkennung: Die verrauschte Freiform
mit 200 000 Dreiecken stellt 5 400 Flecken, und jeder kostet eine Lesung der
Stützpunkte und drei begrenzte Löser. Nahe lag ein Sieb: der lineare Fit aus
Facettennormalen und -mitten (bis zur 0.4.4 das ganze Maß), und nur wer dort
unter dem Vierfachen der Toleranz liegt, bekommt die Verfeinerung. Vor dem
Einbau die Spanne gemessen — Sieb gegen Endmaß bei jedem angenommenen Fit
über zwölf Testdateien: Kugel bis 1 144 (Toleranz 0,02, 18 Dreiecke, Endmaß
10⁻¹⁶), Kegel bis 12× die Toleranz, Torus bis 27×. Das Sieb hätte die Hälfte
der echten Formen verworfen. Ebenso `method="lm"` mit geschlossener
Ableitung: 4,5 → 3,8 s, aber 158 von 4 031 Läufen enden in anderen Minima
als der Trust-Region-Weg.

**Why:** Die Verfeinerung an belegten Stützpunkten (P1.2) findet Formen, die
der lineare Fit gar nicht sieht — kleine Kugeln aus achtzehn Dreiecken. Ein
Sieb aus dem alten Verfahren misst eine andere Frage als das neue.

**How to apply:** Ein Sieb vor einer teuren Stufe erst einbauen, wenn die
Spanne zwischen Sieb und Endmaß am Korpus gemessen ist — mit einer Sonde,
die beide Werte je angenommenem Fall aufzeichnet. Was billig ist und dieselbe
Antwort gibt: Antworten je Netz und Fleck merken (`_remembered`) und die
Ableitung geschlossen mitgeben (Ableitung gegen Differenzen bis 10⁻⁹ prüfen,
Ergebnisse vergleichen). Siehe [[gemessene-frage-ist-nicht-die-gestellte]]
und [[schranke-aus-einem-messwert-ist-geraten]].
