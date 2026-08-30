---
name: rezept-ist-der-fund-op-ist-die-ursache
description: Zwei als Bausteinfehler gemeldete Befunde waren Fehler in Galerie-Rezepten — und beide Male war die richtige Antwort eine fehlende Prüfung in der Operation.
metadata: 
  node_type: memory
  type: feedback
  originSessionId: f1fa50e5-23de-4673-8c99-66e1556eff5d
  modified: 2026-08-30T22:18:39.367Z
---

In der Nacht zum 31.08.2026 wurden zwei Befunde als Fehler an einem **Baustein**
gemeldet. Beide waren Fehler im **Rezept**, das ihn benutzt — und beide Male lag
die eigentliche Lücke doch in der **Operation**, nur an anderer Stelle als
gemeldet.

**Fall 1: „`screw_lid` hat eine stille Untergrenze um 66,8 mm."** Der Baustein
war unschuldig: Auf drei unabhängig gemessenen Wegen wächst der Deckel korrekt
mit, konstant Dose plus 5,3 mm von ⌀30 bis ⌀120. Die 66,8 kamen aus dem
Galerie-Rezept, das nach dem Deckel eine Rändelung mit `wrap_diameter = 65.3`
legt — einer **fest eingetragenen Zahl**, abgelesen bei einer Dose von ⌀60.
Stellt jemand den Projektparameter auf ⌀50, läuft das Muster um einen Zylinder,
den es nicht mehr gibt. 65,3 plus zweimal 0,8 mm Musterhöhe = 66,9.

**Fall 2: „`insert_living_hinge` hat ein Koordinatenproblem."** Auch hier war der
Baustein in Ordnung. Das Rezept setzte `axis="x"`, weil das nach der Biegeachse
klingt — `axis` ist aber die Richtung, in die der Baustein *zeigt*. Die Hülle
sprang von 28 auf 90 mm Höhe.

**Die Regel:** Wer einen Fehler in einem Rezept findet, hat meistens eine
**fehlende Prüfung in der Operation** gefunden. Das Rezept ist der Fund, nicht
die Ursache — es zu reparieren behebt einen Fall und lässt die Falle für jeden
nächsten stehen. Die Frage lautet nicht „welcher Wert ist falsch", sondern
„warum durfte er falsch sein, ohne dass jemand es sagt".

Beide Fälle endeten deshalb in einem Befund an der Op, nicht in einer
Rezeptkorrektur (die gehört dem, der das Rezept hält).

**Zwei Messlehren dazu, beide teuer erkauft:**

- **Die Hüllgröße allein zeigt es nicht.** Bei `axis="x"` lag der *Boden* des
  Teils bei z = −17 — es ragte unter die Bauplatte. Sichtbar wurde das erst, als
  ich neben der Größe auch `bounds.minimum` ausgab. Ein Körper kann wasserdicht,
  einteilig und volumenplausibel sein und trotzdem an einer Stelle stehen, an
  der er nicht druckbar ist.
- **Eine Prüfung, die nur eine Richtung kennt, schweigt bei der anderen.** Der
  erste Rändelungs-Befund maß „Wickelzylinder breiter als der Körper". Der
  schlimmere Fall war der umgekehrte: ein *kleinerer* Wickel, der im Hohlraum
  liegt und als 553 lose Stücke danebenfällt — dort schwieg er zu Recht und
  trotzdem falsch. Die Teilezahl fängt beide, ist binär statt toleranzbehaftet.

Verwandt mit [[testprojekt-trifft-den-fall-nicht]] (ausgeliefert enthält, was die
Anwendung erzeugt) und [[fehlalarm-den-mehrere-fuer-einen-halten]].
