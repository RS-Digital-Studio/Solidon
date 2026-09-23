---
name: mehr-kandidaten-pruefen-das-urteil
description: "Wer eine Suche mehr Kandidaten sehen lässt, findet auch die, die das Urteil bisher nur zufällig nie gesehen hat — die Druckausrichtung stellte Roberts Poolhalter danach auf eine Kante."
metadata:
  type: feedback
---

**Eine Vorauswahl schützt das Urteil dahinter, ohne dass es jemand merkt.**
Am 23.09.2026 in Solidon (RM-190): Die Orientierungssuche schnitt nur acht
Finalisten der Heuristik, und die ordnete nach der *Fläche* der Überhänge.
An Roberts Getränkehalter lagen die besten Lagen dort auf Rang 51 (Mast),
182 (Schirm), 25 und 99 (Halter). Eine zweite Finalistenliste nach dem
*geschätzten Stützraum* (Fläche mal Höhe über dem Bett) fand sie — und
stellte im selben Lauf beide Halter auf **Kanten**: 34 und 36 mm² Auflage,
über der kleinsten Aufstandsfläche von 17,6 mm², aber keine Kante so breit
wie eine Linie. `stands()` hatte diese Lagen nie beurteilen müssen; die
Heuristik ließ sie nicht durch.

**Why:** Ein Kriterium, das nur Lagen sieht, die eine andere Stufe schon
aussortiert hat, wird an der Vorauswahl mitgetestet, nicht an sich selbst.
Wer die Vorauswahl verbessert, reicht dem Urteil Fälle, für die es nie
geschrieben wurde.

**How to apply:** Nach jeder Erweiterung einer Kandidatenmenge das Vollfeld
fahren (jeden Kandidaten beurteilen, nicht nur die Finalisten) und die neuen
Sieger einzeln ansehen — nicht nur fragen, ob der Wert besser wurde. Hier
entschied erst die Auflage um eine halbe Linienbreite nach innen versetzt
(`Candidate.footing`) zwischen Stand und Kante. Siehe
[[ziel-erreicht-heisst-nicht-heil-angekommen]] und
[[gemessene-frage-ist-nicht-die-gestellte]].
