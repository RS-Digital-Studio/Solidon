---
name: schranke-aus-einem-messwert-ist-geraten
description: "Eine Toleranz nach einem einzigen gemessenen Fall zu setzen, sieht aus wie Messen und ist Raten — der zweite Fall liegt oft knapp dahinter."
metadata:
  type: feedback
---

Am 03.09.2026 zweimal in derselben Stunde, an derselben Funktion.

Kegelstücke, die zu **einem** Kegel gehören, sollten wieder
zusammengeführt werden. Zwei Schranken entscheiden das, und beide habe ich
nach dem ersten gemessenen Fall gesetzt:

| Schranke | gesetzt auf | erster Fall | zweiter Fall |
|---|---|---|---|
| Halbwinkel | 5° | 2,2° | **5,74°** — blieb draußen |
| Achse | 2° (vom Ring geerbt) | — | **3,6°** — blieb draußen |

Beide Male sah die Zahl gemessen aus: Sie stand neben einem echten Messwert,
mit Reserve. Beide Male lag der nächste Fall knapp darüber, und beide
Male war der Grund derselbe — **je kleiner ein Ausschnitt, desto ungenauer
fittet er**. Der Fall, an dem ich gemessen hatte, war zufällig der
gutmütige.

3d-druck-a0 hat am selben Tag denselben Fall an einer anderen Konstante:
`FLAT_RIM = 0,05` aus **einem** Kuppelfall, bei dem die Spanne null war. Dort
hat es gehalten — weil die Grenze mit der Ringgröße skaliert. Seine
Formulierung trifft es: „Das ist Glück und kein Verfahren."

**Why:** Eine Toleranz beschreibt eine **Streuung**, und eine Streuung hat man
nicht nach einem Wert. Der erste Fall liefert die Größenordnung, nicht
die Grenze. Die Versuchung ist groß, weil das Ergebnis stimmt: Der Test
wird grün, der Befund verschwindet, und dass die Schranke nur diesen einen
Fall deckt, sieht man erst am nächsten Modell — oder gar nicht, weil
das Merkmal dort einfach fehlt.

**How to apply:** Vor dem Setzen einer Toleranz **zwei** Dinge messen:

1. **Den schlechtesten Fall, nicht den ersten.** Bei Einpassungen ist das der
   kleinste Ausschnitt — also den Prüfkörper so bauen, dass ein Splitter
   entsteht, nicht nur die saubere Fläche.
2. **Den Abstand zur Gegenseite.** Eine Schranke taugt, wenn zwischen „gehört
   dazu" und „gehört nicht dazu" eine Größenordnung liegt. Bei der
   Spitze war es 0,15 mm gegen 30 mm — dort ist die genaue Zahl gleichgültig.
   Beim Winkel lagen 5,74 gegen 30, aber die Schranke saß bei 5: **die
   Größenordnung war da, die Zahl saß trotzdem falsch.**

Und wo die Schranke **nicht** die trennende ist, gehört genau das an sie
geschrieben. Die Winkelschranke oben fängt nur einen groben Ausreißer
ab, bevor ein Fit dafür gerechnet wird; getrennt wird über die Spitze.
Der Test misst sie deshalb nicht, und **auch das steht dort** — sonst
hält der nächste Leser eine grüne Suite für einen Beleg, den
sie nicht liefert.

Verwandt: [[zwei-schwellen-eine-frage]] (dort stimmen die Zahlen einzeln und
widersprechen sich zu zweit), [[abgelesene-zahl-altert-still]],
[[mutation-die-den-fall-nicht-trifft]] (die Gegenprobe, die eine
ungemessene Schranke aufdeckt).
