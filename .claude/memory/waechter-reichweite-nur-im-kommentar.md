---
name: waechter-reichweite-nur-im-kommentar
description: "Ein Kommentar, der die Reichweite eines Wächters behauptet, ist keine Messung — und der Fehler landet genau in der ungeprüften Lücke."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 6caddfb7-eab2-4fff-96cd-208918c20603
  modified: 2026-08-26T07:05:17.827Z
---

Ein Wächter über sechs Sprachen trug den Kommentar: „Der Stamm ‚oper' trägt
durch alle sechs Sprachen — Operationen, operations, operaciones, **opérations**,
operazioni, operações." Das Muster war `[Oo]per\w*`. Französisch schreibt
`opér` — das `é` steht an der Stelle, an der das Muster ein `e` verlangt.

Gemessen: fünf Sprachen treffen, Französisch nicht. Und genau dort stand dann
der Fehler — drei Stellen nannten 87 Operationen, während der Statistikblock
derselben Seite 91 sagte. Der Kommentar nannte den einen Fall, der nicht
funktionierte, ausdrücklich beim Namen.

Dazu kam ein zweites Loch derselben Art: Ein Test namens
„both_languages_state_the_same_numbers" verglich Deutsch gegen Englisch. Vier
der sechs Sprachen prüfte niemand.

**Why:** Ein Kommentar über die Reichweite eines Wächters liest sich wie ein
Beleg und ist keiner. Wer ihn schreibt, hat die Reichweite gedacht, nicht
gemessen — und was in einer Aufzählung steht, wirkt geprüft, gerade weil es
dasteht. Das ist gefährlicher als ein fehlender Kommentar: Der nächste Leser
sucht das Loch nicht mehr, weil der Kommentar es bereits ausschließt.

**How to apply:** Behauptet ein Kommentar, ein Muster oder eine Prüfung decke
eine Menge ab, dann probier die Menge durch, bevor du ihm glaubst — drei Zeilen
in der Konsole, ein Eintrag je Fall, und die Tabelle steht. Das gilt besonders,
wo Sprachen, Plattformen oder Dateiendungen aufgezählt werden: Die Ausnahme ist
meistens die mit dem Sonderzeichen. Und ein Test, dessen Name eine Menge nennt
(„beide Sprachen", „jede Plattform"), wird über einen `glob` gezogen, nicht über
eine Liste — dann nimmt er das Siebte vom ersten Tag an mit.

Verwandt: [[messwerkzeug-misst-sich-selbst]], [[eine-kette-endet-am-letzten-glied]],
[[was-die-suite-nicht-findet]].
