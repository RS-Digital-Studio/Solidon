---
name: rueckfallregel-an-ihren-treffern-messen
description: Eine Rückfallregel, deren Fälle der Hauptweg längst nimmt, zeigt im Korpus nur noch ihre Fehlgriffe — zählen, was sie verwirft; ein Fortschritt über der Schweißtoleranz ist Rauschen
metadata:
  type: project
---

Die Gewindestapelregel (`features._without_thread_turns`) verwarf Zylinder als
Gewindegänge, sobald drei koaxiale innerhalb der Fitstreuung (8 %) einen Lauf
bildeten, der sich um mehr als die Schweißtoleranz verlängerte. Seit die
Wendelsuche (`helix.py`) Gewinde belegt, trifft der Rückfallweg keine mehr:
Über 208 Dateien und die gedruckten Gewinde M3 bis M8 mit abgeschalteter
Wendelsuche fand er am 25.09.2026 kein belegtes Gewinde, verwarf aber in 13
Dateien echte Zylinder — die Flaschentaschen R 49 des Flaschenhalters (ihre
Wandstücke beginnen um Hundertstel versetzt), 30 von 45 Zylindern am
Besenhalter (Absätze, Bögen getrennter Teile), die Buchstabenbögen des
Screen-Covers. RM-219 kam als „Nadeldreiecke" ins Register; die Ursache war
die Regel.

**Why:** Ein Merkmal, das eine Regel still verwirft, fällt niemandem auf — es
fehlt einfach. Und eine Toleranz, die als „hat sich bewegt" gelesen wird,
zählt Rechenrauschen: Die Schweißtoleranz sagt, wann zwei Punkte derselbe
Ort sind, nicht, wann ein Stück weiter reicht als ein anderes.

**How to apply:** Wer eine verwerfende Regel anfasst oder einer misstraut,
zählt am Korpus, **was** sie verwirft, und prüft Stichproben davon — nicht nur,
ob sie an ihrem Musterfall greift. Bedingungen aus der Geometrie der Sache
(eine Wendel: ein Teil, eine Materialseite, Gänge laufen ineinander) statt
aus einer Streuungsgrenze. Verwandt: [[gefahren-ist-nicht-gefordert]],
[[index-messen-und-pruefen]].
