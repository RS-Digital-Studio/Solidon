---
name: versatz-sieht-aus-wie-viele-abweichungen
description: Zwei Listen über den Index verglichen, eine hat einen Eintrag mehr — ab da ist jede weitere Abweichung nur der Versatz.
metadata:
  type: feedback
---

Am 03.09.2026 verglich ich zwei Schichtlisten derselben Geometrie, einmal über
den übersetzten Schichtkern und einmal über GEOS. Der Bericht lautete: „erste
Abweichung bei Schicht 47, 4483,56 gegen 4471,50". Daraus wurde die Meldung
„die beiden Wege rechnen verschieden", und 3d-druck-85 gab sie als Faktor 2,3
an Robert weiter.

Beide Listen waren verschieden **lang** — 204 gegen 205. Ab der fehlenden
Stelle vergleicht man Schicht *n* der einen mit Schicht *n+1* der anderen, also
verschiedene Höhen. Nach Höhe statt nach Position verglichen:

    nur bei GEOS: [9.5]     gemeinsame Schichten: 204, flächenverschieden: 0

Es rechnete nichts falsch. Es fehlte eine Schicht.

**Why:** Ein Versatz sieht aus wie viele Abweichungen und liest sich wie ein
schwererer Befund, als er ist — er führt die Suche in die Rechnung, während die
Ursache im Zusammenbau liegt. Und er ist ansteckend: **Eine echte Abweichung
ist punktuell, ein Versatz hört ab seiner Stelle nicht mehr auf.** Das ist das
Warnzeichen, und es kostet nichts, darauf zu sehen.

**How to apply:** Zwei Folgen nie über die Position vergleichen, ohne vorher
ihre Länge zu prüfen — und wenn sie gleich lang sein sollten, ist die
Ungleichheit selbst schon der Befund. Wo es einen natürlichen Schlüssel gibt
(hier die Höhe), über den vergleichen und die Differenzmengen beider Richtungen
ausgeben; sie sagen mehr als die erste abweichende Stelle. Häufen sich
Abweichungen ab einem Punkt und reißen nicht mehr ab, ist Versatz die erste
Hypothese, nicht die letzte.

Verwandt: [[gemessene-frage-ist-nicht-die-gestellte]] — dort antwortet die
Messung auf eine andere Frage, hier auf dieselbe Frage über den falschen
Paaren. Und [[eigener-messfehler-widerlegt-den-befund-nicht]]: Der Befund
blieb echt, nur seine Erklärung war falsch.
