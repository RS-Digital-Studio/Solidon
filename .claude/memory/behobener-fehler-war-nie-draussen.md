---
name: behobener-fehler-war-nie-draussen
description: "Ein Changelog-Punkt über einen Fehler, den keine veröffentlichte Version hatte, lässt den Kunden bei sich suchen — Prüfsatz: git tag --contains <ursache>."
metadata:
  type: feedback
---

Am 03.09.2026 stand im Changelog für 0.3.1: „Das Kürzelfenster zeigt
**wieder** jeden Eintrag." Gemessen:

```
v0.3.0 sitzt auf 478ebd88   ->  03.09. 04:18
eb979353 (Fehler entsteht)  ->  03.09. 12:35
8c759134 (Fehler behoben)   ->  03.09. 12:49
git tag --contains eb979353 ->  leer
```

Der Fehler existierte **vierzehn Minuten**, zwischen zwei internen Commits,
acht Stunden nach dem Tag — und in keiner Version, die jemand
herunterladen konnte. Entstanden war er aus einem halben Zwischenstand: Eine
Umbenennung lag ungestaged im Baum, ein fremder Commit nahm den Dateistand
mit, und eine Stelle rief den alten Namen noch. Der Reparatur-Commit war
richtig — als **Changelog-Punkt** war er falsch.

**Der Prüfsatz, der es entscheidet:** `git tag --contains <ursache>` ist
leer **und** die Ursache liegt hinter dem letzten Tag → kein Kunde hat es je
gesehen, also gibt es nichts zu melden.

Angewandt auf alle Behebungs-Punkte desselben Abschnitts fielen **zwei
weitere** durch, und ein vierter Fall lag daneben:

* Ein Klick-Problem am neuen Bewegungsgriff — Ursache 14:52, behoben
  15:35, beides am selben Tag hinter dem Tag. Gestrichen.
* „Das Material steht an der alten Stelle nicht mehr über" — die
  Ursache war die **neue** Funktion selbst. Nicht gestrichen, sondern zur
  Eigenschaft umgeschrieben: „wird die alte Stelle sauber gefüllt". Wahr,
  und verspricht keine Behebung.
* Eine „Erklärung statt Absturz" für eine Operation, die es in der
  Vorversion gar nicht gab (`git show v0.3.0:app/i18n/locales/en.json` kennt
  ihren Namen nicht). Dort konnte nichts abstürzen.

**Why:** Ein Changelog ist eine Aussage über das **Produkt**, nicht über
die Arbeit. Wer eine Behebung meldet, behauptet damit den Fehler — und der
Leser prüft, ob er ihn hatte. Bei einem Fehler, der nie ausgeliefert war,
kostet das Vertrauen ohne jeden Nutzen. Die Versuchung ist groß, weil der
Reparatur-Commit echt ist und sich wie ein Fortschritt anfühlt; er ist aber
die Korrektur eines Zwischenstands, den niemand gesehen hat.

**How to apply:** Vor jedem Behebungs-Punkt die Ursache suchen und
`git tag --contains` fragen. Drei Ausgänge: Fehler war in einer Version →
Punkt bleibt. Fehler entstand und verging zwischen zwei Commits → streichen.
Der „Fehler" ist ein Rand der neuen Funktion → als **Eigenschaft** schreiben,
nicht als Behebung.

Und die Umkehrung, die am selben Tag ein Fehlalarm von mir war: Commits, die
**in** der Vorversion liegen, fehlen in einem Abschnitt „seit der Vorversion"
zu Recht. Ich hatte „liegen darin" als „im Bereich seit dem Tag" gelesen; der
Kunde hatte sie längst. Ein Satz darüber im Changelog wäre die
Erklärung einer Nicht-Differenz.

Verwandt: [[aus-kundensicht-perfekt]] (derselbe Maßstab, hier auf einen
Text angewandt), [[gemessene-frage-ist-nicht-die-gestellte]] (mein „liegen
darin" war die engere Frage), [[commit-o-nimmt-den-dateistand]] (so entstand
der Zwischenstand überhaupt).
