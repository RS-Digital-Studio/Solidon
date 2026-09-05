---
name: any-ueber-einen-flicken-misst-den-rand
description: "any(bedingung for dreieck in flicken) antwortet nicht „ist dieser Fleck so\", sondern „grenzt er an so etwas an\" — der Rand entscheidet, und jeder Fleck hat einen."
metadata:
  node_type: memory
  type: feedback
  originSessionId: 880d8f7a-c07e-4b8f-b374-5bef80997d00
  modified: 2026-09-04T15:45:21.479Z
---

Am 04.09.2026 in `app/core/perceive/features.py`. Eine Facette sollte nicht als
ebene Fläche gelten, wenn sie auf einer Rundung sitzt:

```python
not any(int(index) in curved for index in facet)
```

`curved` enthält jedes Dreieck, das **einen Nachbarn** mit flachem Knickwinkel
hat. Für einen Mantelstreifen eines Zylinders trifft das auf alle zu — richtig
verworfen. Für die **Deckfläche eines Gewindebolzens** trifft es auf ihren Rand
zu, denn der grenzt an den Gewindekamm; ein einziges Dreieck genügt, und die
ganze Facette fällt. Danach passte die Erkennung dort eine Kugel Ø 23,4 mm ein,
und ein Test, der zusicherte „neben einem Gewinde steht nichts", wurde rot.

**Why:** `any` über die Mitglieder eines Flickens beantwortet eine andere Frage
als die gestellte. Gefragt war „ist dieser Fleck Teil einer Rundung"; gemessen
wurde „hat dieser Fleck irgendwo einen gerundeten Nachbarn". Die zweite Frage
ist für **jeden** Fleck fast immer mit ja zu beantworten, denn jeder Fleck hat
einen Rand, und der Rand liegt definitionsgemäß neben etwas anderem. Je
größer der Fleck, desto harmloser der Rand — und desto irreführender das
Ergebnis. Dieselbe Familie wie
[[gemessene-frage-ist-nicht-die-gestellte]], nur mit einem Quantor als
Fehlerquelle.

**Der naheliegende Ausweg ist der Anteil, und er hat hier nicht getragen.**
Gemessen: die falschen Mantelstreifen liegen zwischen 0,00 und 0,85 gerundeter
Dreiecke, die echte Deckfläche bei 0,15 — keine Trennung. Ein Anteil ist eben
auch nur eine gemittelte Randmessung.

**How to apply:** Wo eine Eigenschaft über einen Fleck geprüft wird, erst
fragen, ob sie am **Rand** oder im **Inneren** wohnt.

- Eigenschaften, die aus der Nachbarschaft kommen (Knickwinkel, Zugehörigkeit,
  Anschluss), sind Randeigenschaften. `any` darüber misst den Rand.
- Was das Innere beschreibt, ist die Normalenstreuung des Flickens selbst, sein
  Rückstand gegen eine Ebene, seine eigene Krümmung — Größen, die keinen
  Nachbarn brauchen.

Und wenn kein inneres Maß zur Hand ist: den Befund festhalten statt eine
Schwelle raten. Verwandt: [[die-halbe-regel-sieht-aus-wie-eine-ganze]],
[[schranke-aus-einem-messwert-ist-geraten]].
