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
* Eine „Erklärung statt Absturz" — hier war der Prüfsatz **falsch
  angewandt**, und der Punkt steht wieder im Abschnitt. Gemessen worden war
  `git show v0.3.0:app/i18n/locales/en.json`, also der Übersetzungskatalog;
  der kannte den Namen nicht. Das Register am Tag kennt ihn:
  `git show v0.3.0:app/core/geom/prepare_ops.py | grep 'name="'` zeigt
  `resize_hole` mit dem Titel „Bohrung ändern". Ein Kunde auf 0.3.0 konnte
  also hineinlaufen (3d-druck-a0, nachgerechnet an einem Kundenteil).

**Der Prüfstein hat eine zweite Seite, und sie ist am selben Tag ebenfalls
zugeschnappt: die Neuerung, die es schon gab.** Derselbe Abschnitt zählte fünf
Handlungen an einem erkannten Merkmal als neu auf, darunter „in der Größe
ändern" — und `resize_hole` steht im Tag. Neu war nicht die Handlung, sondern
**wofür** sie gilt (Zapfen, Kuppel). Aus dem einen Punkt wurden zwei, und beide
sind wahr.

|  Was der Punkt sagt | Was den Tag zu fragen ist | Befehl |
|---|---|---|
| „behoben", „geht wieder", „nicht mehr" | War der **Auslöser** erreichbar? | `git tag --contains <ursache>` |
| „neu", „jetzt auch", „lässt sich jetzt" | Gab es die **Funktion** schon? | `git show <tag>:<register> \| grep 'name="'` |

**Und der Prüfstein fragt nach dem Auslöser, nicht nach dem Alter der
Operation.** Genau daran hing der vierte Fall oben: Die Operation war alt, nur
ihre Absage war falsch. Wer „ist die Operation neu?" fragt statt „war der
Auslöser erreichbar?", streicht einen richtigen Punkt.

**Why:** Ein Changelog ist eine Aussage über das **Produkt**, nicht über
die Arbeit. Wer eine Behebung meldet, behauptet damit den Fehler — und der
Leser prüft, ob er ihn hatte. Bei einem Fehler, der nie ausgeliefert war,
kostet das Vertrauen ohne jeden Nutzen. Die Versuchung ist groß, weil der
Reparatur-Commit echt ist und sich wie ein Fortschritt anfühlt; er ist aber
die Korrektur eines Zwischenstands, den niemand gesehen hat.

**How to apply:** Vor jedem Behebungs-Punkt die Ursache suchen und
`git tag --contains` fragen; vor jedem „neu"-Punkt das Register am Tag.
Und wenn der Prüfstein sich unterwegs schärft, die schon gefällten Befunde
**noch einmal** damit fahren — ein korrigierter Prüfstein ist wertlos, solange
die Befunde stehen bleiben, die mit dem alten entstanden sind. Drei Ausgänge: Fehler war in einer Version →
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
