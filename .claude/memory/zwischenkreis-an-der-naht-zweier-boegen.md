---
name: zwischenkreis-an-der-naht-zweier-boegen
description: Ein Stück über der Naht zweier tangentialer Bögen passt gut auf einen Zwischenkreis (R 15,1 zwischen R 10 und R 16) — jede Regel über Folgen eingepasster Kreise braucht die Bestätigung durch ein zweites Stück
metadata:
  type: project
---

Beim Erkennen wandernder Umrisse (RM-243, `features._wandering_outline`,
26.09.2026) fiel ein verrauschter Korbbogen R 10 · R 16 · R 10 als „Verlauf“
durch: Die Nachtrennung schnitt ein Stück aus 48 Dreiecken quer über die Naht
von R 10 und R 16, und `fit_cylinder` nahm es als guten Kreis R 15,1 an. Damit
stand eine steigende Folge 9,9 → 15,1 → 16,1 da, die es in der Konstruktion
nicht gibt. Ebenso ein Rauschstück R 8,68 an der Ecke zur Flanke.

Gehalten hat erst die **Bestätigung**: Ein echter Bogen zerfällt im Rauschen in
mehrere Stücke, die alle auf seinem Kreis liegen; ein Spline trägt auf jedem
Stück einen eigenen. Gezählt werden nur unbestätigte Kreise, und ein
bestätigter hält die Folge an — dann hat das Nahtstück keinen Nachbarn mehr.
Danach waren 72 Korbbogenfälle (Saat, Rauschen, Flanken) Merkmal für Merkmal
gleich wie vorher.

**Why:** Die Einpassung sieht nur ihr Stück. Über einer tangentialen Naht
liegen die Punkte auf zwei Kreisen, die sich dort berühren, und ein Kreis
dazwischen trifft beide Hälften innerhalb des Fitvertrags.

**How to apply:** Wer aus eingepassten Stücken auf Konstruktion oder Verlauf
schließt (Ketten, Radiusfolgen, Paare), fragt zuerst, ob ein zweites Stück den
Kreis bestätigt — und prüft `_lies_on_the_cylinder` nicht gegen Splitter aus
zwei Dreiecken, die liegen auf jedem nahen Kreis. Verwandt:
[[kurzes-splinestueck-besteht-jede-kreispruefung]],
[[gegenfall-erst-am-basisstand-pruefen]], [[index-messen-und-pruefen]].
