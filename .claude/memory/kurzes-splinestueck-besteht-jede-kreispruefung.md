---
name: kurzes-splinestueck-besteht-jede-kreispruefung
description: Jede glatte Kurve ist auf kurzer Strecke ein Kreis — Splinestücke von vier bis acht Streifen treffen Kreise auf Hundertstel µm; erst gleicher Radius über das ganze Stück plus genaue Ecken belegen einen Bogen
metadata:
  type: project
---

Beim Trennen extrudierter Umrisse in Bögen (RM-219, `features._arcs_of_a_prism`)
kamen am 25.09.2026 an Schriftzügen, Logos, Griffen und am Eiffelturm Dutzende
„Verrundungen" heraus, deren Radien wanderten (1,325 · 1,328 · 1,331 … an der
Werkzeugbox, 0,836 · 0,857 · 0,884 … am Eiffelturm). `fit_cylinder` nahm sie an:
Ein Stück von vier bis acht Streifen trifft einen Kreis bis auf 0,006 bis
0,08 µm — genauer als manche echte, gezeichnete Wand (R 10,000 am
Gartenschlauchhalter bis 0,08 µm). Weder Kreisfehler noch Streuung trennten die
Seiten; die Bereiche überlappten jedes Mal.

Getrennt hat erst, was einen Bogen ausmacht: **ein Radius über das ganze
Stück** (am Besenhalter streut er um höchstens 2,4 %, am Eiffelturm wanderte er
in einem Stück um bis zu 12 %), dazu genaue Ecken und eine Trennschwelle
oberhalb des Rauschens (5 % statt 2 %).

**Why:** Der Abstand einer glatten Kurve zu ihrem Schmiegekreis wächst mit der
dritten Potenz der Länge. Jede Formprüfung an kurzen Stücken wird deshalb von
Splines bestanden, und jede Trennschwelle im Rauschband erzeugt kurze Stücke.

**How to apply:** Wer eine Rundform aus Stücken zusammensetzt oder eine
Schwelle für Stücke wählt, fragt die Eigenschaft über das ganze Stück, nicht
nur den Fit; und misst an beiden Seiten — Bögen mit gezeichneten Radien
(wenige Nachkommastellen) gegen Schrift, Logos, Streben. Verwandt:
[[rueckfallregel-an-ihren-treffern-messen]], [[index-messen-und-pruefen]].
