---
name: fuenf-tests-eine-lage
description: "Fünf Sollwert-Tests in derselben entarteten Lage sind ein Test; der Normalfall einer Funktion ist oft genau die Lage, in der ein Term wegfällt."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 7fe92054-2daa-4d76-92ed-67a2464096bd
  modified: 2026-08-27T18:44:56.582Z
---

`axis_hit` (Ziehgriff, 27.08.2026) hatte einen Vorzeichenfehler im Zähler und
gab damit die Höhe um `2·s·(n·d)` verschoben zurück. Fünf Sollwert-Tests
standen daneben, alle fünf grün, alle fünf mit richtig hergeleiteter Erwartung —
und **alle fünf mit einem Blick quer zur Achse**, also `n·d = 0`. Genau dort
verschwindet der Fehlerterm. Gemessen an einem Strahl, der die Achse exakt
trifft: 90 statt 10.

Der Fehler war nicht, dass die Erwartungen aus dem Prüfling kamen (das tun sie
nicht, siehe [[sollwert-aus-dem-pruefling]]). Der Fehler war die **Lage**: Die
Querschau ist der Normalfall des Ziehgriffs, also der Fall, den man beim
Schreiben und beim Prüfen zuerst nimmt — und ausgerechnet in ihm kürzt sich der
Term weg.

**Warum:** Fünf Tests in derselben entarteten Lage sind ein Test mit fünf
Namen. Die Zahl der Assertions sagt nichts über die Abdeckung; was zählt, ist
die Zahl der **unabhängig variierten** Größen. Bei einer Formel ist das jeder
Faktor, der im Fehlerterm vorkommen könnte — nicht die Eingaben, die man von
der Anwendung her im Kopf hat.

**Wie anwenden:** Bei jeder Formel mit mehr als zwei Größen einen Testfall
nehmen, der den *Normalfall verlässt* — schräg statt quer, drei Achsen statt
zwei. Und bevorzugt einen, dessen Sollwert **konstruktionsfrei** feststeht: Bei
einem Abstandsproblem ist das der exakte Treffer (Abstand null), denn seine
Antwort liest man ab, statt sie herzuleiten — eine Herleitung kann denselben
Denkfehler haben wie der Prüfling. Ein Vergleichstest („kurz gleich lang",
„zweimal gleich") sieht einen konstanten Fehlerterm nie; wenn der Docstring das
nicht selbst sagt, liest er sich als Beleg
([[benannte-falle-schuetzt-nicht]]).

Und die Gegenprobe gehört dazu: Der neue Test wird gegen die **alte** Fassung
gefahren. Fällt er dort nicht, prüft er den Fehler nicht, den er behauptet.
Verwandt: [[was-die-suite-nicht-findet]],
[[gemessene-frage-ist-nicht-die-gestellte]].
