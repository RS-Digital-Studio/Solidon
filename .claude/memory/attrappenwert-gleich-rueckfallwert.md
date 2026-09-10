---
name: attrappenwert-gleich-rueckfallwert
description: "Eine Attrappe, deren Wert zufällig dem Rückfallwert des Prüflings entspricht, macht jede Gegenprobe blind — die Mutation ist vom Fix nicht zu unterscheiden"
metadata:
  type: feedback
---

Die Tiefenstufe fällt ohne Maßstab auf 0,1 mm je Bildpunkt zurück. Die
Testattrappe lieferte **zehn** Bildpunkte je Millimeter — also genau denselben
Faktor. Der Test war grün, und die Gegenprobe blieb es auch, als die ganze
Rechnung durch den Rückfall ersetzt wurde: Zwei gleiche Zahlen sind nicht zu
unterscheiden. Mit acht statt zehn fiel sie sofort (10.09.2026).

**Why:** Es ist die Schwester von „zwei Felder mit gleichem Wert machen jeden
Test grün, der nur eines liest" ([[sollwert-aus-dem-pruefling]],
`.claude/rules/tests.md`) — nur liegt der zweite Wert hier nicht im Datensatz,
sondern **im Prüfling**, als sein Rückfall. Man sieht ihn beim Schreiben des
Tests nicht, weil man auf die Rechnung schaut und nicht auf ihren Notausgang.

**How to apply:** Wer eine Attrappe für eine Größe baut, liest zuerst den
Rückfallwert des Prüflings für genau diese Größe (`return 0.1`, `or 1.0`,
`getattr(..., default)`) und wählt einen Attrappenwert, der ihm **nicht**
gleicht — auch nicht als Kehrwert. Und die Gegenprobe mutiert nicht irgendeine
Zeile, sondern ersetzt die Rechnung durch genau diesen Rückfall.
