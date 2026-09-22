---
name: ziel-erreicht-heisst-nicht-heil-angekommen
description: "Eine Annahmeprüfung, die nur die verlangte Größe misst, nimmt jedes Ergebnis an, das die Zahl trifft — auch ein kaputtes; und gerade dort schweigt sie."
metadata:
  type: feedback
---

**Wer prüft, ob ein Verfahren sein Ziel erreicht hat, hat noch nicht geprüft,
ob das Ergebnis brauchbar ist.** Am 22.09.2026 in Solidon: `decimate_mesh`
rief den zweiten Solver nur, wenn `fast_simplification` die *Dreieckszahl*
nicht schaffte. Ob danach noch ein Körper da ist, fragte die Bedingung nicht —
und genau das war der Fehler, RM-076 und RM-129, über Monate ausgeliefert:

| Körper | Ziel | bekommen | Zustand |
|---|---|---|---|
| erzeugte Eule (325 244) | 150 000 | **150 000** | 10 offene Teile, 11 verzweigte Kanten |
| Voronoi-Spiderman (885 570) | 30 000 | **30 000** | 12 Teile statt 2, offen |
| Kumiko-Gitter (94 990) | 30 000 | **30 000** | 2 054 Teile, ein Drittel Volumen weg |

Jedes Ziel punktgenau getroffen. Der Rückfall, der alle drei Fälle hätte
prüfen können, lief nie — er war an die Zahl gebunden, und die stimmte ja.

**Why:** Die Zahl ist das, was der Nutzer *eingetippt* hat, und deshalb liest
sie sich wie das, was er *wollte*. Er wollte aber ein druckbares Teil mit
weniger Dreiecken, und die Zahl beschreibt nur die zweite Hälfte davon. Eine
Bedingung, die nur sie misst, nimmt jedes Ergebnis an, das die Eingabe
wiederholt — und je gewaltsamer ein Verfahren die Zahl erzwingt, desto
sicherer trifft es sie. Dieselbe Signatur wie bei
[[schwelle-misst-die-falsche-achse]]: **je schlimmer der Fall, desto stiller
die Prüfung.**

Dazu kommt, dass der Nachbar es richtig machte und das trotzdem nicht half:
`_manifold_decimation` prüfte sein eigenes Ergebnis seit jeher auf Dichtheit,
Teilzahl, Volumen und Abweichung. Zwei Wege zum selben Ziel, einer mit
Abnahme, einer ohne — und der ohne war der erste.

**How to apply:** Bei jeder Stelle, die ein Ergebnis *annimmt* (nicht: erzeugt),
zwei Sätze hinschreiben: **was das Verfahren liefern sollte** und **woran man
merkt, dass es kaputt ist**. Prüft die Bedingung nur den ersten, fehlt der
zweite — und er fehlt meistens, weil das Verfahren „funktioniert hat".

Der Griff, der es hier aufdeckte: dieselbe Kennzahl **vor und nach** der
Operation in einer Zeile ausgeben, nicht nur die Zielgröße. „885 570 → 30 000"
sieht nach Erfolg aus; „2 Teile → 12 Teile, dicht → offen" daneben nicht mehr.
Vergleiche [[zwei-dinge-nur-eines-geprueft]] und
[[roh-gegen-gerendert-vergleichen]].
