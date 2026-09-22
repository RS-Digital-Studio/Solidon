---
name: geteiltes-budget-bedient-die-reihenfolge
description: "Eine Rechengrenze, die sich mehrere Aufrufe teilen, ist ein Wettlauf: Die ersten bekommen alles, die späteren still nichts — und die Zahl im Code sieht großzügig aus."
metadata:
  type: feedback
---

**Ein Budget je Aufruf ist kein Budget, sondern eine Reihenfolge.** Am
22.09.2026 in Solidon: `deviation._MAX_REFINEMENTS = 256` begrenzte die
Kantenarbeit der Formabweichung — je **Träger**, nicht je Dreieck. An einem
Ring aus 4 096 Dreiecken verbrauchten die ersten zwei Dutzend die Marke; alle
weiteren bekamen die rohe Rechteckklammer, im Mittel 0,16 mm breit, während
Ebene, Zylinder, Kugel und Kegel am selben Körper auf Mikrometer schlossen
(RM-202).

Zwei Dinge machten es unsichtbar:

- **Die Zahl sah großzügig aus.** 256 Verfeinerungen klingen nach viel. Sie
  sind es auch — für *ein* Dreieck. Wer die Konstante liest, denkt an die
  Rechnung, die er vor Augen hat, nicht an die tausend daneben.
- **Es gab keinen Fehler, nur weniger Genauigkeit.** Die Klammer blieb gültig,
  jedes Dreieck bekam eine Antwort, kein Test wurde rot. Der Nachbar-Test
  schrieb die Sache sogar fest: „das Budget ist gemeinsam" stand als Name
  eines grünen Tests.

**Why:** Eine geteilte Rechengrenze verhält sich anders als eine geteilte
Speichergrenze — sie läuft nicht über, sie wird still ungleich verteilt. Und
die Ungleichheit folgt der **Iterationsreihenfolge**, also einer Größe, die
mit dem Problem nichts zu tun hat: Dasselbe Dreieck bekommt eine andere
Antwort, je nachdem, an welcher Stelle der Liste es steht.

**How to apply:** Bei jeder Konstante, die Arbeit begrenzt, den Satz
hinschreiben: **„Das gilt je ___."** Steht dort etwas anderes als die
Einheit, deren Ergebnis am Ende gelesen wird, ist es ein Wettlauf. Der
Gegentest ist billig: **dieselbe Eingabe n-mal** durch den Aufruf schicken und
prüfen, dass alle n Ergebnisse gleich sind. Genau das prüft der umgeschriebene
Test heute.

Und wenn „je Einheit" zu teuer wird — hier der Fall, 4 ms je Dreieck —, ist
die Antwort nicht, das Budget wieder zu teilen, sondern die Rechnung zu
verbilligen: geschlossene Teilstellen statt blinder Halbierung, und dieselbe
Rechnung vektorisiert statt je Dreieck einmal. Am Ende war es genauer **und**
zehnmal schneller. Vergleiche [[schwelle-misst-die-falsche-achse]] (dieselbe
Familie: die Prüfung stand auf der falschen Größe) und
[[ziel-erreicht-heisst-nicht-heil-angekommen]].
